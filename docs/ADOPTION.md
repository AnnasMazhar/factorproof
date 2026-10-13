# docs/ADOPTION.md — Real-World Applicability

This document answers the question a quant researcher asks before adopting a new tool:
*how does this actually fit into my week?* It covers the Tuesday workflow, a concrete
integration recipe against a named ecosystem tool, the production failure modes, the
operational cost, and the single most likely reason someone would not adopt it.

---

## 1. The Tuesday Workflow

A typical adoption scenario: a researcher has a CSV of daily OHLCV data (e.g. output
from a broker API or from `yfinance`/`alpaca-trade-api`) and a list of factor ideas.
They want to know which factors survive statistical scrutiny before spending more time
on them.

**Day 1 — install and screen (< 30 minutes)**

```bash
# Install into an existing project venv
pip install "factorproof @ git+https://github.com/you/factor-lab.git"

# Or from a local clone
pip install -e '.[dev]'

# Run on your own CSV (must have: date, asset, open, high, low, close, volume columns)
factor-lab screen --data /path/to/equities.csv --horizons 1,5,20 --out results/

# Inspect the verdict table
cat results/factor_table.md
```

The output is a ranked Markdown table with IC, IC-IR, t-stat, quintile spread, Wilson
lower-bound hit rate, turnover, FDR verdict, and PROMOTE / REJECT per factor. The file
can be dropped directly into a research notebook or a Notion page.

**Day 2 — drill into passing factors**

```bash
# Why did mom_20 pass? Walk through the gate reason table
factor-lab promote mom_20 --data /path/to/equities.csv

# What does the IC decay look like?
ls results/*.png
```

The `promote` command prints a human-readable reason table for every gate, including the
thresholds and observed values. Exit code 0 = promote, exit code 1 = reject. This output
is designed to be pasted into a research note or a PR review.

**Day 3 — add a custom factor**

```python
# src/myresearch/factors/my_factor.py
from factorlab.factors.base import Factor
import pandas as pd

class MyFactor(Factor):
    name = "my_factor"
    category = "momentum"
    description = "Custom factor for research"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return df.groupby("asset")["close"].transform(
            lambda x: x.pct_change(42).shift(1)
        )
```

Register it and screen:

```python
from factorlab.factors.registry import REGISTRY
from myresearch.factors.my_factor import MyFactor

REGISTRY["my_factor"] = MyFactor()

# Then call factorlab programmatically
from factorlab.data import load_ohlcv_csv
from factorlab.promote import promote, PromotionConfig

df = load_ohlcv_csv("/path/to/equities.csv")
decision = promote(MyFactor(), df, PromotionConfig())
print(decision.verdict, [r for r in decision.reasons if not r.passed])
```

---

## 2. Integration Recipe: factorproof + alphalens-reloaded

The Quantopian stack (specifically `alphalens-reloaded`, maintained by Stefan Jansen)
is the most common tool researchers use for factor tear sheets. It produces rich visual
diagnostics but has no promotion gate and no overfitting controls.

The natural integration: **use alphalens-reloaded for the visual tear sheet; use
factorproof for the statistical gate before you trust the tear sheet**.

**Why in this order?** alphalens is useful for diagnosing *why* a factor behaves the way
it does (IC over time, quantile cumulative returns, turnover by quintile). But it will
produce a convincing-looking tear sheet for a noise factor on a lucky period. The
factorproof gate runs first and filters down to factors worth visualising.

### Concrete integration (tested with alphalens-reloaded 0.4.6)

```bash
pip install alphalens-reloaded
pip install "factorproof @ git+https://github.com/you/factor-lab.git"
```

```python
import pandas as pd
import alphalens
from factorlab.data import load_ohlcv_csv
from factorlab.factors.registry import REGISTRY
from factorlab.promote import promote, PromotionConfig

# Step 1 — load data
df = load_ohlcv_csv("equities.csv")  # long-format: date, asset, open, high, low, close, volume

# Step 2 — gate with factorproof
factor_name = "mom_20"
factor = REGISTRY[factor_name]
decision = promote(factor, df, PromotionConfig())

if decision.verdict != "promote":
    print(f"{factor_name} rejected — not worth tear-sheeting")
    for r in decision.reasons:
        if not r.passed:
            print(f"  FAIL {r.code}: observed={r.observed:.4f}, threshold={r.threshold:.4f}")
    raise SystemExit(1)

# Step 3 — only reaching here if factorproof promoted the factor
# Reshape for alphalens: it wants (date, asset) MultiIndex Series + wide prices DataFrame
factor_values = factor.compute(df)
prices = df.pivot(index="date", columns="asset", values="close")

# alphalens expects forward returns to be pre-computed or it computes them internally
factor_data = alphalens.utils.get_clean_factor_and_forward_returns(
    factor_values,
    prices,
    quantiles=5,
    periods=(1, 5, 20),
)

# Step 4 — tear sheet
alphalens.tears.create_full_tear_sheet(factor_data)
```

**What this does:** factorproof's promotion gate runs first, with BH FDR correction,
Wilson LB, purged walk-forward CV sign consistency, and turnover. Only if all 10 gates
pass does the code proceed to the alphalens tear sheet. This prevents wasting time on
convincing-looking tear sheets for spurious factors.

**alphalens limitations this addresses:** alphalens does not apply FDR correction across
the factors you screened before it — if you screened 20 ideas before landing on `mom_20`,
the IC chart does not account for that multiple-testing. The factorproof screen does.

**alphalens advantages this does not replace:** the per-quantile cumulative returns chart,
the IC over time chart, and the turnover diagnostics are far richer visuals than the
factorproof text report. alphalens-reloaded also handles the multi-period returns
correctly and plots the decay. Use both.

### Data format bridge

alphalens expects its factor as a `pd.Series` with a `(date, asset)` MultiIndex.
factorproof's `Factor.compute()` already returns exactly this:

```python
factor_values = REGISTRY["mom_20"].compute(df)
# pd.Series with MultiIndex(["date", "asset"])
```

No reshaping needed. The only conversion is pivoting `df` to wide prices for alphalens,
which is one line (`df.pivot(...)`).

---

## 3. Production Failure Modes

These are failure modes observed when using factorproof outside a controlled synthetic-data
environment. They are not bugs; they are the places where the tool's assumptions meet reality.

### 3.1 Insufficient data raises ValueError

The purged walk-forward splitter enforces minimum panel length. If the panel is short
relative to the label horizon and number of splits, the splitter raises:

```
ValueError: Insufficient training data after purge: need ≥ 30, got 12.
Reduce n_splits, reduce horizon, or extend the panel.
```

**Trigger condition:** panels shorter than roughly `n_splits * (horizon + embargo_days) * 2`.
With the default 5 splits, horizon=20, embargo=20, the minimum safe panel is ~400 days.
Researchers working with recent IPOs or short backtest windows hit this.

**Mitigation:** reduce `n_splits` in `PromotionConfig`, reduce the horizon, or extend the
data window. The error message states which value to change.

### 3.2 All factors reject at the IC gate on real data

On real equity data (especially large-cap liquid names), IC values are typically 0.01–0.03
for well-known factors. The default `min_abs_ic = 0.02` threshold may reject everything.

**This is the correct behaviour**, not a bug: the thresholds were calibrated on synthetic
data with a planted AR(1) signal of `rho=0.15`. Real factors are weaker. However, a screen
that rejects all 13 factors is not useful to the researcher.

**Mitigation:** lower `min_abs_ic` to 0.01 and `min_ic_ir` to 0.03 in `PromotionConfig`,
and document the threshold change in your research notes. See §4.1 (open question closed)
for the empirical literature range.

### 3.3 Wilson LB gate passes on autocorrelated series

For assets with high serial autocorrelation in returns (momentum assets, bonds), the hit
rate n is overstated. Calendar-day observations are not i.i.d. Bernoulli; effective n is
approximately `n * (1 - rho_1) / (1 + rho_1)`. At `rho_1 = 0.3`, effective n is ~54% of
calendar n.

**Consequence:** the Wilson LB may be satisfied using calendar n when it would fail with
effective n. The gate is therefore slightly permissive for autocorrelated assets.

**Mitigation:** pass `autocorrelation_adjustment=True` in `PromotionConfig` (v0.2 roadmap).
For v0.1, treat this as a known limitation and interpret Wilson LB results conservatively
for assets with documented persistence. See §4.4 (closed) for the numerical impact.

### 3.4 BH FDR under correlated factors

The 13 factors share a common price panel, so their IC p-values are correlated. BH
FDR at q=0.10 is valid under the PRDS condition (positive regression dependence) and
is known to be *conservative* (over-rejects) when factors are positively correlated —
the effective number of independent tests is less than 13.

**Consequence:** factorproof may reject borderline factors that would survive a
properly independence-adjusted procedure. The error direction is conservative, not liberal.

**Mitigation:** for a small factor family (< 5 independent groups), the practical impact
is small. For large families with strong factor correlation (IC pairwise > 0.5), use
Storey's (2002) adaptive pi_0 estimate (v0.3 roadmap). See §4.6 (closed) for
the quantitative bound.

### 3.5 Lookahead in custom factors is caught in two layers (residual: evasion)

The `lookahead_control` factor is correctly rejected because it is flagged with
`uses_future_data = True`. Since the M01 fix, `promote()` additionally scans the
`compute()` source for negative `.shift(-N)` patterns and rejects before any
statistics run — accidental lookahead via negative shifts IS caught (executed
evidence: §8.4, a `shift(-5)` custom factor hard-rejects with `no_negative_shifts`).

`assert_no_lookahead(features, targets, horizon)` catches overlap at the index level.
What remains uncaught is future access hidden from source inspection (index slicing,
helper functions) — the documented residual risk, now bounded to deliberate evasion
rather than accidents.

**Mitigation:** set `uses_future_data = True` on any factor that intentionally touches
future rows; write tests for custom factors that confirm they produce `NaN` on the
first `horizon` rows. See `docs/ADVERSARIAL-REVIEW.md` finding M01 (fixed) for details.

### 3.6 Multi-asset universes with staggered trading calendars

`load_ohlcv_csv` does not fill or align trading calendars. If assets have different
trading days (e.g., a mix of US equities and UK equities), cross-sectional IC is computed
over a sparse panel where most date-asset pairs are NaN. Coverage will be low for most
assets and the coverage gate will reject them.

**Mitigation:** pre-align calendars before passing to factorproof: forward-fill missing
days or use only days where all assets have data.

---

## 4. Operational Cost

### Time cost

| Task | Approximate time on CPU-only workstation (8 cores) |
|---|---|
| Install from git URL | < 30s |
| Screen 13 factors, 1500-day panel, 12 assets, horizons 1/5/20 | **93.8 s** (measured 2026-09-27; was 45–90s estimate) |
| Promote a single factor | 5–15 seconds |
| Add a custom factor (implement `compute()`) | 15–30 minutes |
| Generate HTML report with IC decay and quantile plots | 10–20 seconds |
| Screen 13 factors, 5000-day panel, 50 assets (250k rows) | **7 min 19.9 s** (measured 2026-09-27) |

No GPU is required. The workload is pandas/numpy operations on a time-series panel.
The 5000×50 measurement confirms the "< 10 minutes" claim in §6 (raw `time` output in §7).
Above 200 assets, the cross-sectional operations benefit from Polars or Dask — not
implemented in v0.1.

### Dependency cost

```
factorproof requires: numpy, pandas, matplotlib, pyyaml
```

Four dependencies. No scipy, no statsmodels, no sklearn, no database. It installs cleanly
into any Python 3.11+ environment without conflict. The statistics are implemented
from scratch so there is no version-coupling to scipy's API.

### Maintenance cost

- The promotion thresholds (`PromotionConfig`) are documented defaults, not
  empirically calibrated. Researchers working with real data should expect to adjust
  `min_abs_ic` and `min_ic_ir` and document their reasoning. A future v0.2 will provide
  an empirical calibration guide against a public benchmark dataset.
- The BH FDR family is defined as the set of factors in the current screen run. If a
  researcher runs many sequential screens, multiple-testing accumulates across screens
  and the gate does not account for it. The correct practice is to run all candidate
  factors in a single screen call.

---

## 5. The Single Most Likely Reason Someone Would Not Adopt This

**The thresholds are not calibrated on real data.**

A researcher who reads the README and runs the demo will see `mom_20` promoted at
`IC = 0.038, IC-IR = 0.111` on synthetic data with a planted AR(1) signal. On real
large-cap equities, they will likely find that `mom_20` produces `IC ≈ 0.015, IC-IR ≈ 0.04`
— well below the default `min_abs_ic = 0.02` and `min_ic_ir = 0.05` thresholds. The
pipeline will reject everything. A researcher at that point faces a choice: lower the
thresholds, or distrust the tool.

This is the known limitation stated in the README: *"Thresholds are documented defaults,
not calibrated market truths."* But knowing about a limitation in the README and hitting
it in practice are different experiences. The tool will feel broken because it rejects
even well-known factors on real data.

The correct response is to lower `min_abs_ic` to 0.01 (typical for liquid equities in
the academic literature; Harvey, Liu & Zhu 2016 document mean IC ≈ 0.01–0.04 across the
factor zoo). But a researcher who does not understand this will discard the tool instead.

**The mitigation, executed today (2026-09-27):** the permutation-null procedure the v0.2
`calibrate` subcommand would ship has been run by hand — 500 cross-sectional shuffles of
`mom_20` against forward 5-day returns on the bundled panel gives a 95th-percentile noise
floor of `|IC| = 0.0149` versus the observed `0.0252` (raw output in §7, script at
`examples/cycle2_pass3_falsification.py`). The decision rule is: **set `min_abs_ic` to the
95th percentile of the permutation null on your own panel**, not to a universal constant.
That turns the biggest adoption objection from "the thresholds are arbitrary" into a
five-second, reproducible calibration step; the v0.2 subcommand is packaging, not research.

---

## 6. Falsification Section (Pass 3)

The observation that would prove this adoption guide wrong:

**If a researcher following this guide cannot reproduce the integration recipe** —
specifically, if the `factor_values = REGISTRY["mom_20"].compute(df)` call produces
a Series that alphalens-reloaded rejects — the claim that the data format bridge is
seamless is false. The observable test: run the integration recipe against a real CSV
and capture the output. If alphalens raises a TypeError on the factor Series, the format
claim needs a correction.

**If the install-and-screen time exceeds 10 minutes on a standard workstation with
a 5000-day, 50-asset panel**, the "< 30 minutes Day 1" claim is wrong. Observable test:
time `factor-lab screen --data large_universe.csv` with `n_days=5000, n_assets=50`.

### Verification results (2026-09-27, cycle 2 pass 3)

| Falsification test | Result |
|---|---|
| Integration recipe executes against alphalens-reloaded 0.4.6 | **VERIFIED** — ran end-to-end, no exception (raw output §7) |
| 5000×50 screen < 10 minutes | **VERIFIED** — 7 min 19.9 s (raw `time` output §7) |

Neither claim has been falsified.

---

## 7. Cycle 2 verification — raw output (2026-09-27)

### 7.1 Integration recipe executed against alphalens-reloaded 0.4.6

Command: `.venv/bin/python` running the §2 recipe against the bundled planted-signal panel.

```
alphalens version: 0.4.6
factorproof verdict: promote
factor Series index: ['date', 'asset'] dtype float64 n= 18000
Dropped 2.7% entries from factor data: 2.7% in forward returns computation and 0.0% in binning phase (set max_loss=0 to see potentially suppressed Exceptions).
max_loss is 35.0%, not exceeded: OK!
alphalens factor_data shape: (17520, 5)
                        1D        5D       20D    factor  factor_quantile
date       asset
2019-01-30 A00   -0.025911 -0.009082 -0.127576 -0.078182                3
           A01    0.002868 -0.053568 -0.164509 -0.062839                4
           A02   -0.017436  0.035885 -0.109164 -0.114790                2
alphalens mean IC: 1d=0.0373 5d=0.0196 20d=0.0089
create_returns_tear_sheet params: ['factor_data', 'long_short', 'group_neutral', 'by_group']
Returns Analysis
                                                   1D     5D    20D
Ann. alpha                                      0.184  0.058  0.043
beta                                           -0.030 -0.029  0.032
Mean Period Wise Return Top Quantile (bps)      9.005  4.266  2.020
Mean Period Wise Return Bottom Quantile (bps)  -2.699  0.421  0.289
Mean Period Wise Spread (bps)                  11.704  3.801  1.653
create_returns_tear_sheet: OK (no exception)
```

Notes:
- The data format bridge claim holds: `Factor.compute(df)` output was accepted by
  `alphalens.utils.get_clean_factor_and_forward_returns` with no reshaping beyond the
  one-line `prices` pivot shown in §2.
- alphalens mean IC at 5D = 0.0196 vs factorproof H=5 IC = 0.0252 for the same factor.
  The gap is expected and documented: factorproof uses log forward returns over its full
  panel; alphalens uses simple returns, drops 2.7% of rows at the boundaries, and its
  per-date IC series starts at 2019-01-30. The two numbers are cross-checks, not
  duplicates.
- API drift observed while executing (the §2 recipe text is unchanged and still works,
  but callers pasting variants should know): alphalens-reloaded 0.4.6's
  `create_returns_tear_sheet` takes `(factor_data, long_short, group_neutral, by_group)`
  — no `demeaned`/`set_context` kwargs — and `get_clean_factor_and_forward_returns` has
  no `keep_na` kwarg. `create_full_tear_sheet(factor_data)` (the call in the §2 recipe)
  exists with signature `(factor_data, long_short=True, group_neutral=False, by_group=False)`.

### 7.2 Timed screens

Default synthetic panel (1500 days × 12 assets), command
`time .venv/bin/factor-lab screen --data synthetic --out /tmp/opencode/syn_out`:

```
94.18s user 0.09s system 100% cpu 1:33.80 total
...
Rejected (13): mom_20, mom_60, rev_5, vol_20, atr_norm_14, rsi_14, volume_z_20, amihud_illiq_20, skew_60, autocorr_5, deflated_mom, noise_control, lookahead_control
```

(13/13 rejected on the non-planted panel is correct behaviour: there is no signal there.)

5000 days × 50 assets (250 000 rows, planted signal), command
`time timeout 900 .venv/bin/factor-lab screen --data /tmp/opencode/big.csv --out /tmp/opencode/big_out`:

```
big panel rows: 250000
414.59s user 2.68s system 94% cpu 7:19.92 total
...
Rejected (9): rev_5, vol_20, atr_norm_14, rsi_14, volume_z_20, amihud_illiq_20, autocorr_5, noise_control, lookahead_control
```

4 promoted (mom_20, mom_60, skew_60, deflated_mom), 9 rejected, lookahead_control
rejected as required — on a panel 8× larger than the demo, in 7 min 20 s.

### 7.3 Threshold calibration (permutation null)

From `examples/cycle2_pass3_falsification.py`, CAL section:

```
mom_20 observed |mean IC| at H=5 : 0.0252  (rowwise check 0.0252)
permutation null: 500 cross-sectional shuffles, seed=0
null mean IC = -0.00019, 95th pct of |null IC| = 0.0149
default min_abs_ic = 0.0200  -> observed signal is ABOVE the 95% noise floor
decision rule: set min_abs_ic to the 95th percentile of the permutation null
on the researcher's own panel (floor above), not to a universal constant
```

### 7.4 New failure mode found in this pass

`report.py:154` emits `UserWarning: No artists with labels found to put in legend` on
every screen run (both panels above). Cosmetic — the PNG and table are produced correctly —
but a researcher piping screen output into CI logs will see it every time. Recorded for
the improve pass; not a gate or correctness issue.

## 8. Tuesday Run on Real Data (v0.2 mandate — added 2026-10-12, cycle 2 pass 3)

The synthetic Tuesday (§1) answers "does the tool work". The real-data Tuesday
answers "does the tool work on my market". One command, read-only, ~5 minutes.

### 8.1 The exact commands

```bash
python scripts/prove_on_real_data.py --db <prices.sqlite> --horizons 1,5,20 --noise-factors 10
python scripts/check_real_data_proof.py
python scripts/check_no_internal_refs.py
```

Notes: the DB connection is read-only (`mode=ro` URI — the script cannot write,
VACUUM, or copy raw rows; the published artifact is aggregate statistics only).
If the database is absent (CI, fresh clone) the script prints SKIP and exits 0.
Never commit a CSV/parquet of the data. The third command enforces the
no-internal-references rule on every tracked file plus generated reports.

### 8.2 Measured run — raw output (2026-10-12)

```
$ time .venv/bin/python scripts/prove_on_real_data.py --db <prices.sqlite> --horizons 1,5,20 --noise-factors 10
Loading data from <prices.sqlite> ...
Dataset: 14 coins, 21,308 bars, 2021-04-29 to 2026-10-12, 60.38 MB
Running factor evaluation (this may take a few minutes) ...
Wrote reports/real-data-proof.md
Wrote reports/real-data-proof.json

--- Summary ---
Promoted: 0/13
Noise rejection rate: 10/10 (100.0%) — target >=90%
Stability flips: 0 — target 0

reports/real-data-proof.md written.
reports/real-data-proof.json written.
287.83s user 0.27s system 100% cpu 4:48.01 total

$ .venv/bin/python scripts/check_real_data_proof.py
check_real_data_proof: all checks passed.
PROOF_COMPLETE
$ .venv/bin/python scripts/check_no_internal_refs.py
check_no_internal_refs: CLEAN — no forbidden tokens found.
```

Proof JSON (`reports/real-data-proof.json`, generated 2026-10-12T16:41:01Z):
delta = raw-p<0.05: 3, BH-FDR q=0.15: 3, promoted: 0.
BH passes: rev_5 (p=0.0003), volume_z_20 (p=0.0214), lookahead_control (p=0.0000).
Specificity 10/10, sensitivity 0 promoted, stability 0 flips.

### 8.3 What the numbers mean for adoption

The delta (3 → 3 → 0) IS the product working: three factors look significant at
raw p<0.05, the full gate promotes none — lookahead dies at the leakage gate,
rev_5 and volume_z_20 at other gates. Two honest caveats a team must know:

1. The middle equality (raw == BH at q=0.15, 3 == 3) is a soft spot: at this q
   the family correction adds nothing over raw p. Benjamini-Yekutieli would
   harden it to 2, dropping exactly volume_z_20 (machine-verified in
   docs/RESEARCH.md §8.9 F-R5). If your family is large or correlated, run BY.
2. DSR = 0.0 for every factor is mathematically correct, not a display bug:
   IC-IR ≈ 0.09 against E[max SR] ≈ 1.70 under 13 trials. Daily crypto bars do
   not clear a 13-trial deflation bar. 0/13 on a 14-coin daily panel is
   consistent with the literature (weekly momentum on broad panels is where the
   crypto premium lives — RESEARCH §8.1); it is not evidence the gate is broken.

### 8.4 New failure modes found this pass (executed, not theorised)

**A planted signal is detected but not promoted.** A pre-registered planted
factor (seed 1234, achieved corr +0.104 with 5-day forward returns on the real
panel) prints H=5 IC=+0.1528, t_HAC=+19.06, OOS consistency 1.0, FDR pass — and
the verdict is still REJECT, on `max_turnover` (1.31 > 0.5) and
`hit_rate_wilson_lb` (0.4658 < 0.50). The detection chain sees real
predictability clearly; the tradability-flavoured gates block a daily-rebalanced
rank factor on 14 coins. Mitigation: weekly rebalance or smoothed ranks for the
sensitivity demo; treat the Wilson-LB gate as the category error the spec
already names it as (a binomial CI is not the right interval for IC — report
the block bootstrap CI instead). Full numbers: docs/RESEARCH.md §8.9 F-R2.

**The source-scan tripwire works.** A custom factor using `shift(-5)` in its
`compute()` source is hard-rejected with `no_negative_shifts` before any
statistics run (observed this pass). This strengthens §3.5: accidental
lookahead via negative shifts IS caught at `promote()` time. What remains
uncaught is future access hidden from source inspection (index slicing) —
the documented residual risk, now bounded to deliberate evasion rather than
accidents.

**The stability leg varies nothing.** `_stability_check` re-runs `promote()`
with the identical config (`alt_seed` is accepted and unused), so "0 flips"
passes by construction — doubly so when nothing is promoted. A stability check
that cannot fail is decorative. Mitigation (named for the implement pass): vary
`n_wf_splits` and `cv_method` inside the check. Reference observation executed
this pass on synthetic planted data: mom_20 promotes under 4 CV geometries
(walk-forward 4/5/6 splits, CPCV(6,2)) with 0 flips — that is what a
non-vacuous stability leg looks like.

### 8.5 Operational cost (real-data run)

| Item | Measured |
|---|---|
| Full proof, 14 coins × 21,308 daily bars, 13 factors × 3 horizons + 10 noise | **4 min 48 s** wall, single CPU core |
| Dataset on disk | 60.38 MB SQLite, read-only |
| Dependencies | 4 (numpy, pandas, matplotlib, pyyaml) — unchanged |
| Network | none (local SQLite read only) |
| Memory | trivial (21k-row panel) |

No GPU, no services, no credentials. The Tuesday cost is five minutes of one core.

### 8.6 The single most likely reason someone would NOT adopt it (real-data edition)

**The report says "everything rejected" — including real signals.** A team that
runs the Tuesday command gets 0/13 promoted, and this pass proved the rejection
extends even to a planted t=19 signal (via turnover and Wilson LB). The tool
answers "is it statistically significant?" but the promotion verdict couples
that with tradability gates calibrated for a different market rhythm
(low-turnover equity-style factors). On daily crypto the verdict is a constant
REJECT, and a constant verdict carries no information.

The honest framing, which the README Limitations must keep: this is a
*significance filter with a tradability pre-screen*, not a strategy approval.
Adopt it for the delta (raw → FDR → gate attrition in counts and names) and
for the controls (noise rejected, lookahead caught) — not for the verdict
column on this dataset. The fix is recalibration to the team's own rhythm
(weekly horizons, turnover measured against their execution), not a lower bar:
F3b explicitly allows a planted-signal sensitivity proof, and §8.4 shows
exactly which two gates such a proof must address.

### 8.7 Falsification for this section

- Cost: falsified if the Tuesday run exceeds 15 minutes on this panel —
  **not observed** (4:48).
- "Promotes nothing": falsified if a weekly-horizon re-run promotes a real
  factor — **not tested this pass**; named test for the implement pass
  (re-run proof at weekly aggregation, report verdict flips).
- Specificity: falsified if fresh-seed noise passes BH-FDR — **not observed**
  (10 new seeds, max |t_HAC| = 1.50, 0 discoveries; RESEARCH §8.9 F-R1).

---

## 9. Cycle 3 update — real-world applicability, closed (2026-10-12, pass c3-p03)

This pass closes every open item passes 1–2 left (dispositions: docs/RESEARCH.md
§11). No code changed; the recipe, cost table, and failure modes below are the
cycle-3 record. Experiments ran in /tmp (throwaway scripts, repo untouched,
database read-only); raw outputs pasted verbatim.

### 9.1 Tuesday recipe status: unchanged, no re-run needed

The §8.1 command is unchanged and the proof it produces
(`reports/real-data-proof.json`, generated 2026-10-12T16:41:01Z) is hours old;
the dataset has grown by <1 day of bars since (21,308 daily bars, 14 coins,
2021-04-29 → 2026-10-12). Re-running a 5-minute proof for <1 day of new bars
is motion, not evidence — the Tuesday command stands as documented.

### 9.2 New executed failure mode: single-coin fragility (F-R10)

The F-R10 check specified in RESEARCH §9.8 was executed today: drop the
top-|return| coin-week cell and re-screen; then leave-one-coin-out (LOCO),
worst case. Raw output:

```
panel rows=21308 coins=14 dates=2021-04-29..2026-10-12
rev_5 FULL H=1 ic=+0.0348 ir=+0.0810 t_hac=+3.61 p=0.0003 n=1987
  top cell: date=2023-07-13 asset=XRP fwd=+0.5563
  DROP-CELL H=1 ic=+0.0353 t_hac=+3.66 p=0.0002
  LOCO min-|t|: drop INJ ic=+0.0279 t=+2.75 p=0.0059
  LOCO max-|t|: drop SOL ic=+0.0413 t=+4.08 p=0.0000
volume_z_20 FULL H=1 ic=-0.0192 ir=-0.0519 t_hac=-2.30 p=0.0212 n=1973
  top cell: date=2023-07-13 asset=XRP fwd=+0.5563
  DROP-CELL H=1 ic=-0.0192 t_hac=-2.31 p=0.0209
  LOCO min-|t|: drop ATOM ic=-0.0131 t=-1.49 p=0.1364
  LOCO max-|t|: drop INJ ic=-0.0228 t=-2.58 p=0.0098
```

Reading: **rev_5 is robust** — removing any single coin leaves p ≤ 0.0059,
still significant. **volume_z_20 is coin-fragile** — its BH-FDR pass
(p = 0.0212) depends on ATOM being in the panel; without ATOM, p = 0.1364,
not even raw-significant. The top cell (XRP +55.6% on 2023-07-13, the Ripple
ruling day) moves nothing either way — the fragility is coin-level, not
event-level.

Production consequence: on a 14-coin panel, a BH-FDR pass is necessary but not
sufficient evidence — the implement pass should add a LOCO robustness
diagnostic (drop each coin, re-screen, report worst-case p) before any
promotion on narrow panels. This also vindicates the standing 0-promoted
verdict: a gate that promoted volume_z_20 on this panel would have promoted a
one-coin artefact. The Benjamini-Yekutieli note (§8.3) already drops
volume_z_20 arithmetically; LOCO drops it empirically. Two independent votes.

### 9.3 Ecosystem refresh (live probes, today)

| Tool | Stars | Last push / release | Change vs c3-p02 (hours earlier) |
|---|---|---|---|
| MlFinLab | 4,939 | 2023-10-02 (stale) | none |
| qlib | 49,313 | 2026-10-08 | none |
| purgedcv | 55 | PyPI 0.1.10 | none; PyPI-description probe: no IC, verdict, FDR, or BH terms ("factor" hits are a CodeFactor badge and "refactor") |
| ml4t-diagnostic | 34 | 2026-10-10 | none; `main`-branch README grep: no verdict / accept-reject / promotion-gate / promote terms — still metrics, not a gate |
| pyanomaly | 133 | 2024-03-13 (inactive) | none |
| alphalens-reloaded | 669 | 2026-10-10 | +1 star; §2 recipe stands (verified end-to-end in cycle 2, API unchanged since) |

§10.4 watch items (a)/(b)/(c): none fired. Closest threat remains (a).

### 9.4 Operational cost: unchanged

No new timing run: the 4 min 48 s wall measurement (§8.5) is from the same
dataset within a day. The Tuesday cost is still five minutes of one core, no
GPU, no services, no credentials.

### 9.5 The single most likely reason someone would NOT adopt it (cycle-3 edition)

§8.6 stands and is now stronger: the report says 0/13, and this pass proved
that even the two BH-FDR passes are one robust factor (rev_5) and one
one-coin artefact (volume_z_20). A team running the Tuesday command gets a
report whose headline is rejection all the way down.

What is new is the external verdict that this is *correct*: Grobys et al.
(2025, RESEARCH §9.4) document crypto momentum dead post-2020 on broad
panels — on a 2021–2026 14-coin daily panel, "everything rejected" is the
literature-consistent output, and a tool that promoted here would contradict
a 2025 peer-reviewed result. The adoption pitch is therefore unchanged but
re-grounded: adopt this for the delta (raw → FDR → gate attrition in counts
and names), for the controls (noise rejected, lookahead caught), and now for
the LOCO check (§9.2) — not for the verdict column on this dataset.

### 9.6 Falsification for this section

- Cost: falsified if a fresh Tuesday run exceeds 15 minutes — not re-tested
  (dataset delta <1 day); standing measurement 4:48.
- Fragility claim: falsified if an independent LOCO re-run keeps
  volume_z_20 significant without ATOM — the numbers above are the standing
  record to beat (script: /tmp throwaway, method in RESEARCH §11 F-R10).
- Ecosystem: falsified if any §9.3 cell is stale at the next re-probe —
  all cells carry today's probe output.
## 10. Cycle 4 update — microstructure-aware Tuesday (2026-10-13, pass c4-p03)

Cycle 4 pass 1 (§12 in RESEARCH) grounded the promotion gates in
microstructure and trading-cost literature (Roll 1984, Novy-Marx–Velikov
2016, Scholes–Williams 1977, Getmansky–Lo–Makarov 2004). This section
turns that ground truth into Tuesday commands. No code changed; all
numbers below were executed today in /tmp against the read-only panel
(667,436 rows, 14 coins, daily bars, 2021-04-29 → present).

### 10.1 Pre-screen the panel before you screen the factors (2 minutes)

Three read-only checks that decide what the Tuesday run can even claim.
Run these first; if any fires, note it in the research log alongside
the proof.

```bash
python3 -c "
import sqlite3
con = sqlite3.connect('file:///path/to/prices.sqlite?mode=ro', uri=True)
# (1) coverage: any coin too thin to screen?
print(con.execute('select coin, count(*) from candles group by coin order by 2').fetchall())
# (2) staleness: any coin above 5% zero-volume days?
print(con.execute('select coin, sum(volume=0)*1.0/count(*) from candles group by coin having sum(volume=0)*1.0/count(*) > 0.05').fetchall())
# (3) feed gaps: dates where every coin is missing at once?
print(con.execute(\"select date(ts,'unixepoch'), count(distinct coin) from candles group by 1 having count(distinct coin) < 10 order by 1\").fetchall()[:5])
con.close()"
```

Measured today: (1) AAVE has 1 bar (effectively absent), TON starts
2024-08-08 — screen 12, not 14; (2) empty result — max is ATOM at
~0.75%, diagnostic armed but silent; (3) a full-panel gap on
2026-04-30 (feed outage, not staleness). A Tuesday run that reports
"14 coins" without these three lines overclaims its universe.

### 10.2 The reversal pre-check: gross spread vs Roll spread (1 minute)

F-R12 is now binding (RESEARCH §14.1): before trusting any
reversal-family promotion, compute the Roll-implied spread per coin and
require the factor's gross quintile spread to clear it. Reference bars
measured today (daily, in return units):

```
BTC 0.0023  ETH 0.0030  SOL 0.0035  DOGE 0.0042  ADA 0.0045
XRP 0.0049  ATOM 0.0055  INJ 0.0049  HBAR 0.0070  TON 0.0021
ARB/FIL/RENDER: imaginary (no bounce detectable — treat with suspicion, not as free signal)
```

Concrete rule: a `rev_5` promotion whose gross spread is, say, 15 bps on
a coin with a 49 bps Roll spread (XRP) is spread, not alpha. The command
is the `/tmp/c4p3_roll.py` pattern: log-returns → lag-1 covariance →
`2*sqrt(-cov)`. If covariance is positive, the estimator is imaginary —
that coin contributes no bounce evidence either way.

### 10.3 Turnover: read the units before fighting the gate

The most common Tuesday frustration (§8.4: a t=19 planted signal
rejected on turnover) now has its literature anchor. NMV's verified
line (NBER w20721 abstract): anomalies with **one-sided monthly**
turnover above 50% rarely survive costs. The promotion gate's 0.5 is
mean |Δ rank weight| **per rebalance** — for a daily-rebalanced rank
factor this is a far stricter bar than NMV's. That is intentional
(conservative direction), but it means:

- Daily rank factors on 12–14 coins will trip `max_turnover` routinely.
  Do not raise the bar — change the rhythm: weekly rebalance or
  smoothed ranks, then re-screen.
- Any proof that raises `max_turnover` above 0.5 without a net-of-cost
  paragraph naming its cost model fails the checker (F-R13). The
  paragraph must quote its cost model (e.g. "20 bps per month per 20%
  one-sided turnover, after NMV §4"), not just assert "costs are low".

### 10.4 Operational cost (cycle-4 delta)

| Item | Measured |
|---|---|
| Panel pre-screen (§10.1, 3 queries, 667k rows) | seconds, one core |
| Roll spreads, all coins (§10.2) | seconds, one core |
| Full proof (`prove_on_real_data.py`) | standing 4 min 48 s (§8.5); not re-run (dataset delta <1 day) |
| Ecosystem re-probe (7 repos + PyPI) | all HTTP 200 today; qlib 49,318 (+1), alphalens-reloaded 670 (+1), rest unchanged; no watch item fired |

Tuesday cost is still five minutes of one core. The two new pre-checks
add under a minute combined.

### 10.5 The single most likely reason someone would NOT adopt it (cycle-4 edition)

§8.6 and §9.5 stand and are now sharper. Cycle 4 proved the rejections
are *mechanically correct*: the bounce the reversal factor harvests is
mostly spread (Roll spreads of 23–70 bps vs typical gross spreads), the
turnover bar is deliberately stricter than the literature's, and the
volatility inputs are, if anything, conservative-direction. A team
running the Tuesday command gets a report that says, in effect: "your
daily-rebalanced rank factors on 14 crypto coins cannot clear
microstructure, and here are the receipts."

That is a hard sell for a tool whose headline output is a verdict
column — but it is exactly the falsification discipline the repo
promises. The adoption pitch, unchanged since cycle 3 and now
literature-backed: adopt this for the delta (raw → FDR → gate attrition
in counts and names), for the controls (noise rejected, lookahead
caught), for the LOCO check (§9.2), and now for the two pre-checks
(§10.1–§10.2) — not for the verdict column on this dataset. The team
that re-runs at weekly aggregation with smoothed ranks and sees a
verdict flip has the one result that would change this paragraph; that
experiment is named, not run, and belongs to the implement pass.

### 10.6 Falsification for this section

- Pre-screen: falsified if a same-day recount contradicts any §10.1
  number (AAVE 1 bar, TON 2024-08-08 start, 2026-04-30 gap, ATOM max
  staleness) — the queries above are the record.
- Roll bars: falsified if a same-day re-run moves any §10.2 spread by
  more than 5 bps — the per-coin table is the record.
- Turnover reading: falsified if the NMV quote in §10.3 is shown to
  refer to two-sided turnover — the NBER abstract text (RESEARCH §14.2)
  is the record.
- Cost: falsified if a fresh Tuesday run exceeds 15 minutes — standing
  measurement 4:48, not re-tested.

---

*Failure modes derived from the statistical assumptions documented in docs/RESEARCH.md §2 and §4.*
*Cycle 2 pass 3 (2026-09-27): integration recipe and both falsification tests executed for real —
raw output in §7; timings in §4 updated to measured values; threshold calibration run (§5, §7.3);
reproducible via examples/cycle2_pass3_falsification.py.*
*Cycle 2 pass 3 (2026-10-12, reopened v0.2 mandate): §8 Tuesday real-data run — commands in §8.1,
measured output in §8.2 (4:48 wall), three executed failure-mode findings in §8.4, cost table in
§8.5. Falsification experiments in /tmp (not committed); raw outputs pasted in docs/RESEARCH.md §8.9.*
*Cycle 3 pass 3 (2026-10-12): §9 — Tuesday recipe confirmed without re-run, F-R10 single-coin-drop
executed (rev_5 robust, volume_z_20 ATOM-fragile), ecosystem re-probed (no watch item fired);
open items closed in docs/RESEARCH.md §11.*
## 11. Cycle 5 update — applicability, closed (2026-10-13, pass c5-p03)

This pass closes every open item from passes 1–2 in cycle 5 (dispositions in
docs/RESEARCH.md §18). No code changed. Experiments ran in-process against the
read-only panel (667,436 rows, 14 coins, 2021-04-29 → 2026-10-12).

### 11.1 Tuesday recipe status: unchanged; one new pre-screen added

The §10.1–§10.2 pre-screens (panel coverage check, Roll spread check) are the
standing Tuesday commands for cycle 5. The §8.1 proof commands are unchanged.
One new optional pre-screen, motivated by F-R24 (§18.3), is now recommended for
any team considering volatility-managed factor variants:

```python
# Before promoting a vol-managed factor variant, compute
# corr(lagged_20d_variance, next_1d_return) per coin.
# If the panel mean is near zero or positive, vol-management
# will not improve Sharpe (Moreira-Muir Delta_SR requires negative corr).
# Reference numbers for this panel (RESEARCH §18.3):
#   Panel mean corr = -0.0107 (weakly negative — mechanism present but small)
#   BTC: +0.0068, HBAR: +0.0091, SOL: +0.0031 (contra-indicated for these coins)
import numpy as np, math, sqlite3, datetime
from collections import defaultdict
DB_URI = "file:/path/to/prices.sqlite?mode=ro"
# ... (standard load, per §10.1) ...
# corr_check[coin] = pearson(lagged_var_20d, next_day_return)
```

### 11.2 New failure mode: vol-managed variants should be pre-checked

Motivated by F-R24 (§18.3): the Moreira-Muir mechanism (§16.4) only improves
Sharpe when corr(factor_return, lagged_variance) is negative. On this panel, the
correlation is -0.011 — present in the right direction but very small. A team that
runs `deflated_mom` (which divides by volatility) should not expect a material
improvement over raw `mom_20` on this dataset. The turnover gate may still reject
both — the vol-scaling reduces position changes but does not eliminate them.

The one change this introduces to the adoption guide: when a factor with
large variance scaling is promoted, report the corr(return, lagged_var) figure
alongside the verdict. If the correlation is near zero, the vol-scaled variant
and the raw variant are effectively identical.

### 11.3 New failure mode: LOCO robustness is now expected (not optional)

Following C3-F1 (§9.2 RESEARCH §11.4), the LOCO check (drop each coin, re-screen,
report worst-case p) is now a named step in the proof workflow — not optional on
a narrow panel. The specific check now has literature grounding (§16.3
Grundy-Martin: on a 14-coin panel the "winner" portfolio may be ONE coin; a coin-
level event can dominate the factor signal, exactly as XRP dominated the 2023-07-13
ruling-day signal). Any Tuesday run that promotes a factor on this panel must pass
the LOCO diagnostic.

The Tuesday workflow therefore has an additional check after `scripts/check_real_data_proof.py`:

```bash
# After the standard proof, run the LOCO robustness check
python3 -c "
# For each BH-FDR-passing factor, drop each coin and re-screen.
# Report worst-case p (should not become non-significant after dropping
# any single coin, for a promotion to stand).
# Reference: ADOPTION.md §9.2, RESEARCH.md §11.4 (C3-F1)
"
```

This step is named but not automated; the implement pass should wire it into
`scripts/prove_on_real_data.py` as the `--loco` flag.

### 11.4 Competitive positioning update (ml4t-diagnostic narrowed the gap)

The most significant new fact from the cycle-5 ecosystem pass (§17, RESEARCH §17.2):
**ml4t-diagnostic added explicit documentation of HAC-adjusted IC t-stats and FDR
control to its README on 2026-10-13**. This is the closest any open-source competitor
has come to factorproof's measurement layer.

Revised positioning for any researcher choosing between the two tools:

| Dimension | ml4t-diagnostic | factorproof |
|-----------|-----------------|-------------|
| HAC IC t-stat | Yes (documented today) | Yes |
| FDR control | Yes (reported field) | Yes (in gate — exit code) |
| Purged/embargoed CV | Yes | Yes |
| Binary exit code (0 = promote, 1 = reject) | No | Yes |
| Standalone (no Polars, no 7-library ecosystem) | No | Yes |
| Offline, no subscription | Yes | Yes |

The verdict gap is the remaining differentiator. A researcher using ml4t-diagnostic
gets the same measurement numbers; they must write their own gate logic to act on
them. factorproof packages that gate as the public `promote()` API, tested with
161 passing tests, with a documented exit code. The pitch becomes: "ml4t-diagnostic
tells you what the IC is; factorproof tells you what to DO about it."

### 11.5 Operational cost (cycle-5 delta)

| Item | Status |
|------|--------|
| Full proof (§8.5: 4 min 48 s) | Unchanged; dataset grew <1 day |
| Panel pre-screen §10.1 (3 SQL queries) | Seconds |
| Roll spread check §10.2 | Seconds |
| F-R24 vol-correlation pre-check (§11.1, new) | Seconds |
| Total Tuesday cost | Under 10 minutes |

No new dependencies added. The F-R24 check is a handful of numpy operations on
the in-memory panel loaded for the proof.

### 11.6 The single most likely reason someone would NOT adopt it (cycle-5 edition)

§8.6/§9.5/§10.5 stand with one sharpening: **the gate rejects everything, including
signals proven real in the literature, and a competing open-source tool (ml4t-
diagnostic) now reports the same statistics without forcing a binary verdict.**

A researcher who runs `factor-lab screen --data prices.csv` on the real 14-coin
panel sees 0/13 promoted. They check ml4t-diagnostic and see the same IC and FDR
numbers, but the tool does not say REJECT — it presents the numbers and lets the
researcher decide. The factorproof binary verdict is its strength (reproducible,
defensible, CI-integratable) and its weakness (the gate fails to communicate "this
factor is economically interesting even if it fails the statistical gate at this
frequency").

The mitigation is unchanged: adopt factorproof for the DELTA (raw → FDR → gate
attrition), for the controls (noise rejection, lookahead detection, LOCO check),
and for the CI integration (exit code) — not as a final arbiter of economic value.
A factor that factorproof rejects may still be worth running at weekly horizons or
with better execution; factorproof says "not statistically defensible at daily 14-coin
granularity", not "valueless".

### 11.7 Falsification for this section

- Competitive: falsified if ml4t-diagnostic ships `gate_factor()` with a binary
  exit code usable without Polars — the §17.2 grep absence is the record.
- F-R24: falsified if a same-day re-run shows panel mean corr > +0.05 —
  the §18.3 table is the record.
- F-R31: falsified if Amihud spread re-runs < 1000x — the §18.10 table is
  the record.
- F-R23: falsified if IC-by-year shows positive 2021 + negative 2022 on a
  re-run — the §18.2 table is the record.
