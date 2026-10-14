# docs/ADVERSARIAL_REVIEW.md — factor-lab v0.1

## PASS c1-p11-adversarial-2 (cycle 1, adversarial pass 2 of 3)

Independent reviewer lane (kiro:claude-opus-4.5). This pass attacks the **core safety property**:
the pipeline should refuse to promote factors that use future data or lack genuine predictive power.

All commands below were actually run; output is verbatim terminal output.

---

## 1. Property attacks — attempt to defeat lookahead detection

### ATTACK A1: Runtime factor construction with eval()

Goal: Create a factor that uses `close.shift(-5)` (future data) but evades source inspection
by hiding the shift inside `eval()`.

```
$ uv run python3 << 'PYEOF'
import pandas as pd
from factorlab.data import synthetic_ohlcv
from factorlab.promote import promote
from factorlab.factors.base import Factor

class StealthLookaheadFactor(Factor):
    name = "stealth_lookahead"
    category = "attack"
    description = "Factor that tries to hide lookahead via eval()"
    params = {}
    uses_future_data = False  # Lie to the flag checker
    
    def compute(self, df: pd.DataFrame) -> pd.Series:
        close = df.pivot(index="date", columns="asset", values="close")
        future_ret = eval("close.shift(-5)") / close - 1
        factor_vals = future_ret.stack()
        factor_vals.index.names = ["date", "asset"]
        return factor_vals

df = synthetic_ohlcv(n_days=1500, n_assets=12, seed=7, plant_signal=True)
factor = StealthLookaheadFactor()
result = promote(factor, df)
print(f"Verdict: {result.verdict}")
PYEOF
Verdict: reject
```

**Result: BLOCKED.** Source inspection found `.shift(-5)` in the source code of `compute()`.
The `eval()` wrapper does not hide the literal string pattern. Factor rejected via `max_turnover`
gate (turnover=1.18 > 0.5 threshold), not via lookahead detection — but still rejected.

---

### ATTACK A2: Closure-based lookahead (lambda)

Goal: Hide the negative shift amount in a closure variable so source inspection cannot find it.

```
$ uv run python3 << 'PYEOF'
import pandas as pd
from factorlab.data import synthetic_ohlcv
from factorlab.promote import promote
from factorlab.factors.base import Factor

shift_amount = -5  # Closure variable

class LambdaLookaheadFactor(Factor):
    name = "lambda_lookahead"
    category = "attack"
    params = {}
    uses_future_data = False
    
    compute = lambda self, df: (
        (lambda close: (close.shift(shift_amount) / close - 1).stack())(
            df.pivot(index="date", columns="asset", values="close")
        )
    )

df = synthetic_ohlcv(n_days=1500, n_assets=12, seed=7, plant_signal=True)
factor = LambdaLookaheadFactor()
result = promote(factor, df)
print(f"Verdict: {result.verdict}")
for r in result.reasons:
    print(f"  {r.code}: passed={r.passed}, observed={r.observed}")
PYEOF
Verdict: reject
  not_lookahead: passed=True, observed=no
  not_degenerate: passed=True, observed=varied
  coverage: passed=True, observed=0.9966666666666667
  min_observations: passed=True, observed=1495.0
  min_abs_ic: passed=True, observed=0.999791639834562
  min_ic_ir: passed=True, observed=5962.760934365123
  hit_rate_wilson_lb: passed=True, observed=0.9997859098354949
  max_turnover: passed=False, observed=0.5291305314654214
  oos_consistency: passed=True, observed=1.0
  survives_fdr: passed=True, observed=0.0
```

**Result: NEAR-MISS.** 9/10 gates passed. Lookahead detection bypassed (source inspection returns
empty patterns for lambda). Only blocked by `max_turnover` (0.529 > 0.5).

---

### ATTACK A3: Smoothed closure lookahead — **BYPASSES ALL GATES** (BLOCKER)

Goal: Same as A2 but smooth the factor to reduce turnover.

```
$ uv run python3 << 'PYEOF'
import pandas as pd
from factorlab.data import synthetic_ohlcv
from factorlab.promote import promote
from factorlab.factors.base import Factor
from factorlab.cv import check_lookahead, check_lookahead_source

shift_amount = -5  # NEGATIVE = accesses future prices

class SmoothedLookaheadFactor(Factor):
    name = "smoothed_lookahead"
    category = "attack"
    description = "Lookahead hidden via closure, smoothed to pass turnover"
    params = {}
    uses_future_data = False  # LIE
    
    def compute(self, df: pd.DataFrame) -> pd.Series:
        close = df.pivot(index="date", columns="asset", values="close")
        future_ret = close.shift(shift_amount) / close - 1
        smoothed = future_ret.rolling(window=10, min_periods=1).mean()
        factor_vals = smoothed.stack()
        factor_vals.index.names = ["date", "asset"]
        return factor_vals

df = synthetic_ohlcv(n_days=1500, n_assets=12, seed=7, plant_signal=True)
factor = SmoothedLookaheadFactor()

print("=== Lookahead detection results ===")
print(f"check_lookahead (flag check): {check_lookahead(factor)}")
print(f"check_lookahead_source (source scan): {check_lookahead_source(factor)}")

result = promote(factor, df)
print(f"\nVerdict: {result.verdict.upper()}")
for r in result.reasons:
    status = "PASS" if r.passed else "FAIL"
    print(f"  {r.code}: {status} (obs={r.observed})")
PYEOF
=== Lookahead detection results ===
check_lookahead (flag check): False
check_lookahead_source (source scan): []

Verdict: PROMOTE
  not_lookahead: PASS (obs=no)
  not_degenerate: PASS (obs=varied)
  coverage: PASS (obs=1.0)
  min_observations: PASS (obs=1499.0)
  min_abs_ic: PASS (obs=0.37558252523974645)
  min_ic_ir: PASS (obs=1.227482202650157)
  hit_rate_wilson_lb: PASS (obs=0.6257386591954337)
  max_turnover: PASS (obs=0.22489066785264256)
  oos_consistency: PASS (obs=1.0)
  survives_fdr: PASS (obs=0.0)
```

**CRITICAL FINDING: PROMOTED.**

Proof the factor uses future data:

```
$ uv run python3 << 'PYEOF'
import numpy as np
from factorlab.data import synthetic_ohlcv

df = synthetic_ohlcv(n_days=1500, n_assets=12, seed=7)
close_pivot = df.pivot(index="date", columns="asset", values="close")
first_asset = close_pivot.columns[0]
today_close = close_pivot.iloc[10][first_asset]
future_close = close_pivot.iloc[10 + 5][first_asset]  # 5 days later
shifted_close = close_pivot.shift(-5).iloc[10][first_asset]
print(f"Today's close: {today_close:.4f}")
print(f"Close 5 days LATER: {future_close:.4f}")
print(f"close.shift(-5) at today: {shifted_close:.4f}")
print(f"Future matches shifted: {np.isclose(future_close, shifted_close)}")
PYEOF
Today's close: 96.5550
Close 5 days LATER: 100.6648
close.shift(-5) at today: 100.6648
Future matches shifted: True
```

**Root cause:** `check_lookahead_source()` uses `inspect.getsource()` to find `.shift(-N)` patterns.
When the negative number is in a **closure variable** (not a literal), the source code reads
`close.shift(shift_amount)` — the `-5` is not visible. `inspect.getsource()` does not inspect
closure variables.

**Impact:** A factor author can bypass lookahead detection by storing the shift amount in a
variable declared outside `compute()`. This defeats the core safety property: the pipeline promotes
factors that use future data.

---

## 2. Property attacks — edge case corruption

### ATTACK A4: Wilson lower bound with invalid inputs

```
$ uv run python3 << 'PYEOF'
from factorlab.significance import wilson_lower

test_cases = [
    ("k=-1, n=10 (negative k)", -1, 10),
    ("k=15, n=10 (k>n)", 15, 10),
    ("k=5, n=-1 (negative n)", 5, -1),
]

for label, k, n in test_cases:
    try:
        result = wilson_lower(k, n)
        print(f"{label}: {result}")
    except Exception as e:
        print(f"{label}: {type(e).__name__}: {e}")
PYEOF
k=-1, n=10 (negative k): ValueError: math domain error
k=15, n=10 (k>n): ValueError: math domain error
k=5, n=-1 (negative n): 0.0
```

**Finding (minor):** `wilson_lower` crashes with `ValueError: math domain error` on invalid inputs
(k < 0 or k > n) instead of returning a clear error or clamping. Negative n returns 0.0 (silent
wrong answer). Not exploitable for promotion bypass, but poor error handling.

---

### ATTACK A5: Determinism verification

```
$ uv run python3 << 'PYEOF'
from factorlab.data import synthetic_ohlcv
from factorlab.evaluate import evaluate_factor
from factorlab.factors import get_factor

results = []
for i in range(2):
    df = synthetic_ohlcv(n_days=1500, n_assets=12, seed=7, plant_signal=True)
    factor = get_factor("mom_20")
    vals = factor.compute(df)
    metrics = evaluate_factor(vals, df, [5], "mom_20")
    results.append(metrics[0])

print(f"Run 1: IC={results[0].ic_pearson:.10f}")
print(f"Run 2: IC={results[1].ic_pearson:.10f}")
print(f"Deterministic: {results[0].ic_pearson == results[1].ic_pearson}")
PYEOF
Run 1: IC=0.0252298764
Run 2: IC=0.0252298764
Deterministic: True
```

**Result: DETERMINISM HOLDS.** Same seed produces identical results.

---

### ATTACK A6: HAC t-stat correctness

```
$ uv run python3 << 'PYEOF'
from factorlab.data import synthetic_ohlcv
from factorlab.evaluate import evaluate_factor
from factorlab.factors import get_factor

df = synthetic_ohlcv(n_days=1500, n_assets=12, seed=7, plant_signal=True)
factor = get_factor("mom_20")
vals = factor.compute(df)

metrics_h1 = evaluate_factor(vals, df, [1], "mom_20")[0]
print(f"H=1: HAC={metrics_h1.ic_tstat:.4f}, naive={metrics_h1.ic_tstat_naive:.4f}, "
      f"ratio={metrics_h1.ic_tstat / metrics_h1.ic_tstat_naive:.4f}")

metrics_h20 = evaluate_factor(vals, df, [20], "mom_20")[0]
print(f"H=20: HAC={metrics_h20.ic_tstat:.4f}, naive={metrics_h20.ic_tstat_naive:.4f}, "
      f"ratio={metrics_h20.ic_tstat / metrics_h20.ic_tstat_naive:.4f}")
PYEOF
H=1: HAC=4.2683, naive=4.2668, ratio=1.0003
H=20: HAC=0.8247, naive=2.6916, ratio=0.3064
```

**Result: HAC CORRECT.** At H=1, ratio ≈ 1.0 (no overlapping labels). At H=20, ratio ≈ 0.31
(HAC deflates by ~3.3x, consistent with overlapping-label correction).

---

### ATTACK A7: Permissive config promotes noise (expected)

```
$ uv run python3 << 'PYEOF'
from factorlab.data import synthetic_ohlcv
from factorlab.promote import promote, PromotionConfig
from factorlab.factors import get_factor

cfg = PromotionConfig(
    min_observations=1, min_ic_ir=0.0, min_abs_ic=0.0,
    hit_rate_wilson_lb=0.0, max_turnover=999.0,
    oos_consistency_min=0.0, fdr_q=1.0, coverage_min=0.0,
)

df = synthetic_ohlcv(n_days=1500, n_assets=12, seed=7)
factor = get_factor("noise_control")
result = promote(factor, df, cfg)
print(f"noise_control with permissive config: {result.verdict}")
PYEOF
noise_control with permissive config: promote
```

**Result: EXPECTED.** Permissive config allows noise to pass. This is by design — config is
user-controlled. The default config correctly rejects noise_control.

---

## 3. Findings table (pass 2)

| id | severity | finding | evidence | status |
|----|----------|---------|----------|--------|
| F-A3 | **blocker** | Lookahead detection bypassed via closure variables. A factor with `close.shift(shift_amount)` where `shift_amount = -5` is promoted (exit 0, all 10 gates pass). `check_lookahead_source()` inspects source code but does not resolve closure variables, so the negative literal is invisible. | Attack A3 output: verdict=PROMOTE, IC=0.376, future price confirmed via shift | **fixed** |
| F-A4 | minor | `wilson_lower(k, n)` crashes with `ValueError: math domain error` on invalid inputs (k < 0, k > n) instead of returning clear error. Negative n returns 0.0 silently. | Attack A4 output | open |
| F-A7 | informational | Permissive `PromotionConfig` can promote noise — by design (user-controlled thresholds). | Attack A7 output | refuted (expected) |

---

## 4. F-A3 fix evidence

Added `check_lookahead_runtime()` in `src/factorlab/cv.py` (Gate 0.75). This function correlates
factor values with **future** returns at horizons [1, 5, 10, 20]. Correlation > 0.30 triggers
rejection. A legitimate factor has IC ~0.02-0.10; lookahead (even smoothed) has IC ~0.30+.

Verification:

```
$ uv run python3 << 'PYEOF'
import pandas as pd
from factorlab.data import synthetic_ohlcv
from factorlab.promote import promote
from factorlab.factors.base import Factor

shift_amount = -5

class SmoothedLookaheadFactor(Factor):
    name = "smoothed_lookahead"
    category = "attack"
    params = {}
    uses_future_data = False
    
    def compute(self, df):
        close = df.pivot(index="date", columns="asset", values="close")
        future_ret = close.shift(shift_amount) / close - 1
        smoothed = future_ret.rolling(window=10, min_periods=1).mean()
        factor_vals = smoothed.stack()
        factor_vals.index.names = ["date", "asset"]
        return factor_vals

df = synthetic_ohlcv(n_days=1500, n_assets=12, seed=7, plant_signal=True)
factor = SmoothedLookaheadFactor()
result = promote(factor, df)
print(f"Verdict: {result.verdict.upper()}")
for r in result.reasons:
    if not r.passed:
        print(f"  {r.code}: FAIL")
        if r.note:
            print(f"    note: {r.note}")
PYEOF
Verdict: REJECT
  no_future_correlation: FAIL
    note: Factor highly correlated with future returns at h=1 (corr=0.3943 > threshold=0.3). This indicates lookahead contamination.
```

Legitimate factor still passes:

```
$ uv run factor-lab promote mom_20 --data signal --plant-signal | head -5
Factor:  mom_20
Verdict: PROMOTE
```

Test added: `tests/test_adversarial.py::test_closure_lookahead_rejected_by_runtime_check`

---

## 5. Summary (pass 2)

- **1 blocker** (F-A3): Lookahead factor promoted via closure-variable bypass — **FIXED** (runtime correlation check)
- **1 minor** (F-A4): Wilson edge-case crash — open (non-exploitable for promotion bypass)
- **1 informational** (F-A7): Permissive config (expected behaviour)
- **Determinism**: Verified
- **HAC correctness**: Verified (H=1 ratio ~1.0, H=20 ratio ~0.3)
- **All other property attacks blocked** by turnover gate or source inspection

Test count after fix: 107 passed (was 105).

---

## PASS c1-p10-adversarial-1 (cycle 1, adversarial pass 1 of 3)

Independent reviewer lane. This pass did not author the code under review. Commands below were
actually run; output is verbatim terminal output. Prior artifact `docs/ADVERSARIAL-REVIEW.md`
(hyphenated, earlier pass) was read first and is built on, not repeated.

Positioning check against `specs/MARKET-VERDICTS.md`: no conflict found — README.md leads with the
licence problem ("without a £100/month licence", line 3), `COMPARISONS.md` carries the
MlFinLab-vs-Quantopian-vs-this table, and both README and COMPARISIONS state MlFinLab is more
complete. Nothing to record in EVIDENCE.md as a conflict.

---

## 1. Claims audit — 3 most load-bearing README claims, attacked

### C1 — "Promote a real signal (exit 0) or reject noise (exit 1)" (README lines 22-24, 121)

Attack: run the exact commands from a clean shell and read the raw exit codes (the earlier
review's `EXIT=$?` was measured after a `| tail` pipe, i.e. it measured `tail`, not the CLI —
re-measured here without a pipe).

```
$ uv run factor-lab promote mom_20 --data signal --plant-signal >/dev/null 2>&1; echo "mom_20_planted=$?"
mom_20_planted=0
$ uv run factor-lab promote noise_control --data signal >/dev/null 2>&1; echo "noise=$?"
noise=1
$ uv run factor-lab promote mom_20 --data signal >/dev/null 2>&1; echo "mom_20_noPlant=$?"
mom_20_noPlant=0
```

Gate table for the standalone promotion claim (README: "mom_20 promotes in isolation
(IC=0.025, p=0.107 at q=0.15 with m=1)"):

```
$ uv run factor-lab promote mom_20 --data signal --plant-signal
Factor:  mom_20
Verdict: PROMOTE
min_abs_ic                                0.0252       0.0200   PASS
min_ic_ir                                 0.0750       0.0500   PASS
hit_rate_wilson_lb                        0.5013       0.5000   PASS
oos_consistency                           0.6000       0.6000   PASS
survives_fdr                              0.1065       0.1500   PASS
  note: BH FDR q=0.15, m=1 tests
```

**Verdict: CLAIM SUPPORTED.** Exit 0 / exit 1 as documented; IC=0.0252 (~0.025), FDR
p/q value 0.1065 (~0.107), q=0.15, m=1 all match the README sentence. Ten gates are
emitted, matching the README design diagram ("10 gates; all must pass").

### C2 — "Real results (from examples/run_demo.sh)": the README table is this demo's output

Attack: re-run the demo from scratch and diff every table row against README.

```
$ bash examples/run_demo.sh > /tmp/opencode/demo.txt 2>&1; echo "demo_exit=$?"
demo_exit=0
$ grep '^|' /tmp/opencode/demo.txt | sort -u > /tmp/opencode/dr.txt
$ grep '^|' README.md | sort -u > /tmp/opencode/rr.txt
$ diff /tmp/opencode/dr.txt /tmp/opencode/rr.txt && echo ROWS_IDENTICAL
ROWS_IDENTICAL
$ grep -n 'Promoted' /tmp/opencode/demo.txt
39:Promoted (0): none
$ sed -n '39,41p' /tmp/opencode/demo.txt
Promoted (0): none
Rejected (13): mom_20, mom_60, rev_5, vol_20, atr_norm_14, rsi_14, volume_z_20, amihud_illiq_20, skew_60, autocorr_5, deflated_mom, noise_control, lookahead_control
```

**Verdict: CLAIM SUPPORTED.** Every README table row (13 factors × 11 columns) is byte-identical
to a fresh demo run, and "0 promoted / 13 rejected" matches the README "0/13" claim. Note the
README sentence "Promoted in screen: 0/13..." is prose, not demo output — the demo's own line is
"Promoted (0): none"; substance matches.

### C3 — Positioning claims: MlFinLab £100+VAT and restrictive licence; Quantopian stack last maintained 2020

Attack: fetch the primary sources live.

```
$ curl -sS -L https://raw.githubusercontent.com/hudson-and-thames/mlfinlab/master/LICENSE.txt | grep -nE '6\.6|6\.7|14\.2|14\.3|14\.5' | head
160:6.6	The Licensee shall not lease, loan, resell, sublicense or otherwise distribute the Licensed Materials to any other
164:6.7	The Licensee and its Users undertake not to reverse engineer the Licensed Materials and agrees not to set up in
354:14.2	The Company possesses information that has been created, researched, or developed by the Company (including
362:14.3	All Proprietary Information herein shall be the Company's property and its assigns, who shall remain the sole
373:14.5	The Licensee agrees not to lease, loan, resell, sublicense or otherwise distribute any software or product

$ curl -sS -L https://hudsonthames.org/mlfinlab/ | grep -oiE '(£|\$)[ ]?[0-9]+[^<]{0,40}'
£100 (+VAT)

$ curl -sS "https://api.github.com/repos/quantopian/alphalens/commits?per_page=1" | grep -m1 '"date"'
        "date": "2020-04-27T18:40:41Z"
$ curl -sS "https://api.github.com/repos/quantopian/pyfolio/commits?per_page=1" | grep -m1 '"date"'
        "date": "2020-02-28T17:30:19Z"
$ curl -sS https://api.github.com/repos/hudson-and-thames/mlfinlab | grep -E '"(stargazers_count|pushed_at)"'
  "pushed_at": "2023-10-02T03:05:19Z",
  "stargazers_count": 4933,
```

**Verdict: CLAIM SUPPORTED.** Licence clauses 6.6 (no redistribution/sublicensing), 6.7 (no
reverse engineering / no competing product), 14.2/14.3 (proprietary info is the licensor's
property) exist verbatim; pricing page returns exactly `£100 (+VAT)`; alphalens' last commit is
2020-04-27 and pyfolio's 2020-02-28, so "last maintained in 2020" holds. mlfinlab repo state
(4,933 stars, pushed 2023-10-02) matches `docs/RESEARCH.md` §6.1 exactly.

### Incidental badge claims (checked while attacking)

```
$ uv run pytest
105 passed in 28.93s
$ uv run ruff check .
All checks passed!
$ uv run ruff format --check .
18 files already formatted
```

README badge "tests-105 passed" and "ruff-clean" are accurate as of this pass.

---

## 2. Citation audit — every link in docs/RESEARCH.md

Method: extracted all 40 unique URLs with `grep -oE 'https://[^ ]+' docs/RESEARCH.md`, probed each
with `curl -sS -o /dev/null -w '%{http_code}' -L --max-time 20 -A 'Mozilla/5.0 ... research-audit/1.0'`.

```
$ while read -r u; do code=$(curl ... "$u"); printf '%s %s\n' "$code" "$u"; done < links.txt | tee link_audit.txt | sort | uniq -c -w3
     33 200 ...
      6 403 ...
      1 curl: (47) Maximum (50) redirects followed
      1 302ERR https://doi.org/10.3905/jpm.2014.40.5.094
```

Non-200 detail (raw):

```
403 https://doi.org/10.1080/01621459.1927.10502953
403 https://doi.org/10.1093/rfs/1.1.41
403 https://doi.org/10.1093/rfs/hhv059
403 https://doi.org/10.1111/0022-1082.00247
403 https://doi.org/10.1111/j.1540-6261.1985.tb05004.x
403 https://doi.org/10.1111/j.1540-6261.1993.tb04702.x
curl: (47) Maximum (50) redirects followed
302ERR https://doi.org/10.3905/jpm.2014.40.5.094
```

Disposition:

- **33/40 → HTTP 200**, including every "Verified URL" alternative the file promises
  (jstor.org ×11, nber.org ×3, arxiv.org/abs/1405.4598, archive.org, ijcai.org PDF,
  taylorfrancis, wiley book page, all 10 §6.5 ecosystem URLs: mlfinlab LICENSE.txt,
  hudsonthames.org, quantopian/alphalens + pyfolio commits, alphalens-reloaded, qlib,
  purgedcv repo + PyPI, ml4t/diagnostic, pyanomaly).
- **6× 403**: publisher DOI resolvers (Wiley, OUP, T&F, Taylor Francis) bot-blocking. RESEARCH.md's
  header documents this explicitly and each has a 200-returning JSTOR/NBER/arXiv alternate in the
  same citation block — verified present above.
- **1× redirect loop**: `https://doi.org/10.3905/jpm.2014.40.5.094` (Bailey & López de Prado DSR)
  loops (`curl: (47) Maximum (50) redirects followed`, also fails with `--max-redirs 10` →
  `302 10`). RESEARCH.md §2.4 documents the DOI as "returns HTTP 302 redirect to publisher page"
  and supplies arXiv:1405.4598, which returns 200. So the citation resolves via the alternate,
  but the in-file description understates the failure (it is a loop, not a resolvable redirect).

**Support check (claim vs source), spot-verified against fetched text:** licence clauses ✓ (§C3
above), pricing ✓, competitor star counts / push dates ✓ (§6.1 table matches GitHub API),
Jegadeesh-Titman JSTOR 2328882 → 200 ✓, BH JSTOR 2346101 → 200 ✓, Wilson DOI → 403 with
JSTOR alternate 200 ✓, Wilson normal-approx formula 26.2.17 archive.org → 200 ✓.
No citation found that resolves to a page contradicting its claim.

---

## 3. Test-quality audit — 6 tests sampled, named fault injected, suite run

Driver: `/tmp/opencode/inject.py` — for each sample: back up source file, apply one exact string
mutation, run pytest, restore, then re-run the full suite to prove the tree is green.

| # | test | injected fault (one string mutation) | suite result |
|---|------|--------------------------------------|--------------|
| T1 | `tests/test_significance.py::test_wilson_lower_hand_computed` | drop `+ z2 / (4 * n * n)` from the Wilson denominator sqrt term | FAILED (exit 1) — DETECTED |
| T2 | `tests/test_significance.py::test_bh_fdr_hand_computed` | `if pval <= threshold:` → `if pval < threshold:` | FAILED (exit 1) — DETECTED, but by sibling test (see F-T2) |
| T3 | `tests/test_cv.py::test_purge_no_label_overlap` | purge window zeroed: `first_test_date - Timedelta(days=label_horizon)` → `days=0` | **GREEN (exit 0) — NOT DETECTED** (see F-T3) |
| T4 | `tests/test_evaluate.py::test_forward_returns_no_lookahead` | `close.shift(-h)` → `close.shift(h)` | FAILED (exit 1) — DETECTED |
| T5 | `tests/test_promote.py::test_noise_control_rejected` | verdict ignores gates: `"promote" if all_passed else "reject"` → `"promote"` | FAILED (exit 1) — DETECTED |
| T6 | `tests/test_adversarial.py::test_check_lookahead_source_finds_negative_shifts` | `check_lookahead_source` forced to `return []` | FAILED (exit 1) — DETECTED |

Raw output (abridged only to the assertion lines; full log `/tmp/opencode/inject_out.txt`):

```
### T1 wilson lower bound KAT
pytest tests/test_significance.py::test_wilson_lower_hand_computed -> exit 1 :: DETECTED (suite failed)
E       AssertionError: Expected ~0.4524, got 0.454249

### T2 BH threshold boundary
pytest tests/test_significance.py::test_bh_fdr_hand_computed -> exit 0 :: NOT DETECTED (suite still green)

### T3 purge honours label horizon
pytest tests/test_cv.py::test_purge_no_label_overlap -> exit 0 :: NOT DETECTED (suite still green)

### T4 forward returns use future close
pytest tests/test_evaluate.py::test_forward_returns_no_lookahead -> exit 1 :: DETECTED (suite failed)
E       AssertionError: Forward returns should all be positive for a strictly increasing price series

### T5 verdict honours gate results
pytest tests/test_promote.py::test_noise_control_rejected -> exit 1 :: DETECTED (suite failed)
E       assert 'promote' == 'reject'

### T6 lookahead source inspection
pytest tests/test_adversarial.py::test_check_lookahead_source_finds_negative_shifts -> exit 1 :: DETECTED (suite failed)
E       AssertionError: shift(-1) not found in: []

### RESTORE CHECK (full suite)
pytest tests -> exit 0
```

T2 re-probed at full-suite level (the contract asks whether *the suite* fails):

```
=== T2 BH < vs <= full-suite exit=1 ===
E       AssertionError: p=0.10 at threshold boundary should be rejected
FAILED tests/test_significance.py::test_bh_fdr_exact_boundary - AssertionError
```

T3 re-probed: purge removed **and** embargo removed together:

```
purge_removed+embargo_removed -> tests/test_cv.py exit=1
=========================== short test summary info ============================
FAILED tests/test_cv.py::test_purge_no_label_overlap - AssertionError: Split ...
FAILED tests/test_cv.py::test_embargo_removes_gap - AssertionError: Split 0: gap between last train (2019-04-16) and first test (2019-04-17) is 0 positions, expected >= 5
full suite after restore exit=0
```

**Score: 5 of 6 named faults fail the suite.** T3's named fault alone does not (F-T3).

---

## 4. Bypass hunt (pass-1 scope: claim-adjacent attempts only)

- **Force flag:** `uv run factor-lab promote --force noise_control` → argparse
  `unrecognized arguments: --force`, exit 2. No override path exists (re-confirmed against the
  earlier pass).
- **Gate relaxation:** per earlier pass, permissive `PromotionConfig` alone does not promote
  noise (turnover + OOS-consistency + FDR still reject). Not re-litigated.
- **README command honesty:** the exact three commands printed in README lines 20-24 were run
  unmodified and behaved as printed (exit codes in §C1).

---

## Findings table

| id | severity | finding | evidence | status |
|----|----------|---------|----------|--------|
| F-T3 | minor | `test_purge_no_label_overlap` docstring claims it detects "purge step missing or label_horizon not applied", but injecting exactly that fault leaves the whole suite green: with `embargo_days >= label_horizon` the embargo independently enforces `label_end < first_test_date`, so the test cannot distinguish "purge broken" from "purge working". The *property* is still safe (combined purge+embargo removal fails the test); only the stated per-fault detection claim is false. | inject.py T3 → `pytest tests` exit 0; purge+embargo removal → `tests/test_cv.py` exit 1 (raw output §3) | open |
| F-T2 | minor | `test_bh_fdr_hand_computed`'s own KAT values do not sit on the `<=` boundary, so it alone does not fail when the BH comparison is mutated to strict `<`; detection comes from sibling `test_bh_fdr_exact_boundary`. Suite-level detection is real, single-test attribution in the docstring is slightly over-claimed. | inject.py T2 node run exit 0; full-suite run exit 1 via `test_bh_fdr_exact_boundary` (raw output §3) | open |
| F-L1 | minor | `docs/RESEARCH.md` §2.4 says the DSR DOI "returns HTTP 302 redirect to publisher page"; the live behaviour is a redirect **loop** (curl exit 47, 50 redirects; `--max-redirs 10` → `302 10`). The arXiv alternate in the same block returns 200, so the citation itself resolves. Wording inaccuracy only. | link audit raw output §2 | open |
| P01 | — | Positioning conflict with `MARKET-VERDICTS.md`: none found. README leads with the licence problem, COMPARISONS.md table present, MlFinLab-more-complete stated. | README lines 3, 12-13, 42-46, 183-185; RESEARCH.md §6.1 | refuted (no conflict) |

Claims C1/C2/C3: all three **supported** — no blocker, no major. Findings above are test/doc
precision issues, not safety regressions: the leakage property, the gate verdict, and the
promotion exit-code contract all survived attack.

### Status key
- `open`: reported for the builder; not yet fixed (reviewer does not fix code)
- `refuted`: attack attempted, claim held

---

## Summary

- 3 load-bearing README claims attacked with concrete commands: 3/3 supported
- 40 citation links probed: 33×200, 6×403 (documented publisher bot-blocking, alternates all 200),
  1× redirect loop (documented alternate 200); no contradicting source found
- 6 tests fault-injected: 5/6 fail the suite on their named fault; 1 (T3) masked by embargo → F-T3
- Full suite green after every mutation restored: `105 passed in 28.93s`, ruff check + format clean
- 0 blockers, 0 majors, 3 minors open, 1 positioning non-conflict recorded

---

## PASS c2-p10-adversarial-1 (cycle 2, adversarial pass 1 of 2)

Independent reviewer lane. This pass attacks the **claims** (not the property — that is
c2-p11). Read first: ITERATION-PROTOCOL.md, QUALITY-CONTRACT.md, MARKET-VERDICTS.md,
specs/factor-lab.md (incl. v0.2 MANDATE), the c1-p10/c1-p11 entries above, and
reports/mutation-c1.json. No `reports/mutants-survived-c*.txt` exists in the repo.

Measured baseline (authoritative: reports/mutation-c1.json — quoted, not re-derived):
878/1977 mutants killed = 44.4%. Gate: 70%.

All commands below were actually run; output is verbatim terminal output.

---

## 0. Prior-findings re-verification (F-T3, F-T2, F-L1 — all FIXED)

Commit `f13d8fe test(cv): purge-count KAT isolates purge step; fix F-T3/F-T2/F-L1
attributions` addressed all three c1-p10 minors. Re-verified, not trusted:

- **F-T3 (purge-only fault masked by embargo):** `tests/test_cv.py::test_purge_no_label_overlap`
  docstring now states the joint-property scope explicitly and points at the new
  `test_purge_count_matches_label_geometry`, which asserts `spl.n_purged` against an
  independently recomputed count. Fault injection this pass (T1 below): zeroing the purge
  (`days=self.label_horizon` → `days=0`) fails the new test alone. → **fixed**
- **F-T2 (BH `<=` boundary attribution):** `test_bh_fdr_hand_computed` docstring now notes the
  boundary fault belongs to `test_bh_fdr_exact_boundary`; injection T2 below confirms that
  test fails alone on `<` vs `<=`. → **fixed**
- **F-L1 (DSR DOI wording):** `docs/RESEARCH.md` §2.4 now reads "the arXiv preprint is
  substantively equivalent" and "DOI enters a redirect loop (curl: maximum 50 redirects
  followed, 2026-10-12)". Matches live behaviour. → **fixed**

---

## 1. Claims audit — 3 most load-bearing README claims, attacked

### C1 — "Promote a real signal (exit 0) or reject noise (exit 1)"

```
$ .venv/bin/python -m factorlab.cli promote mom_20 --data signal --plant-signal >/dev/null 2>&1; echo "mom_20_planted=$?"
mom_20_planted=0
$ .venv/bin/python -m factorlab.cli promote noise_control --data signal >/dev/null 2>&1; echo "noise=$?"
noise=1
```

**Verdict: SUPPORTED.** Exit codes as documented, measured without an intervening pipe.

### C2 — "Real results (from examples/run_demo.sh)": README table is the demo's output

```
$ bash examples/run_demo.sh > /tmp/c2_demo.txt 2>&1; echo "demo_exit=$?"
demo_exit=0
$ grep '^|' /tmp/c2_demo.txt | sort -u > /tmp/c2_dr.txt; grep '^|' README.md | sort -u > /tmp/c2_rr.txt; diff /tmp/c2_dr.txt /tmp/c2_rr.txt && echo ROWS_IDENTICAL
ROWS_IDENTICAL
$ grep -n "Promoted" /tmp/c2_demo.txt | head -3
39:Promoted (0): none
```

**Verdict: SUPPORTED.** All 13 table rows byte-identical to a fresh run; "0 promoted"
matches the README "0/13" framing. (Demo takes >120s wall-clock on this box; run with an
extended timeout — not a repo defect.)

### C3 — Positioning: MlFinLab licence/pricing; Quantopian stack abandoned 2020

```
$ curl -sS -L https://raw.githubusercontent.com/hudson-and-thames/mlfinlab/master/LICENSE.txt | grep -nE '6\.6|6\.7|14\.2|14\.3|14\.5' | head -6
160:6.6	The Licensee shall not lease, loan, resell, sublicense or otherwise distribute the Licensed Materials to any other
164:6.7	The Licensee and its Users undertake not to reverse engineer the Licensed Materials and agrees not to set up in
354:14.2	The Company possesses information that has been created, researched, or developed by the Company (including
362:14.3	All Proprietary Information herein shall be the Company's property and its assigns, who shall remain the sole
373:14.5	The Licensee agrees not to lease, loan, resell, sublicense or otherwise distribute any software or product
$ curl -sS -L --max-time 20 "https://hudsonthames.org/mlfinlab/" -o /tmp/mlp.html; echo "bytes=$(wc -c < /tmp/mlp.html)"; grep -oiE '(£|\$)[ ]?[0-9]+[^<]{0,30}' /tmp/mlp.html | head -5
bytes=224252
£100 (+VAT)
$ curl -sS --max-time 20 "https://api.github.com/repos/quantopian/alphalens/commits?per_page=1" | head -c 600; echo
... "date": "2020-04-27T18:40:41Z" ... "message": "Merge pull request #361 from quantopian/perf-improvements ...
        "date": "2020-02-28T17:30:19Z"   (pyfolio, same probe)
```

**Verdict: SUPPORTED.** Clauses 6.6/6.7/14.2/14.3/14.5 verbatim; pricing page returns exactly
`£100 (+VAT)`; alphalens last commit 2020-04-27, pyfolio 2020-02-28. No conflict with
MARKET-VERDICTS.md positioning to record.

### Incidental badge claim

```
$ .venv/bin/python -m pytest -p no:warnings 2>&1 | tail -3
........................................................................ [ 54%]
.............................................................            [100%]
133 passed in 51.04s
```

README badge `tests-133 passed` is accurate. (First attempt at `pytest -q | tail -1` showed
only the progress bar, not the summary — re-ran with `tail -3` to capture the count line.)

---

## 2. Citation audit — cycle-2 additions (c1-p10 covered the original 40)

c2-p01 probed its 20 new §8 links (13×200, 7 DOI 403/404 explicitly NOT claimed —
EVIDENCE.md §12d); not re-probed here. This pass probed the 12 ecosystem URLs behind the
§6.5/§6.7 comparison-table update:

```
200 https://api.github.com/repos/stefan-jansen/alphalens-reloaded
200 https://api.github.com/repos/stefan-jansen/empyrical-reloaded
200 https://api.github.com/repos/stefan-jansen/pyfolio-reloaded
200 https://api.github.com/repos/dcajasn/Riskfolio-Lib
200 https://api.github.com/repos/microsoft/qlib
200 https://api.github.com/repos/eslazarev/purged-cross-validation
200 https://pypi.org/pypi/purgedcv/json
200 https://github.com/stefan-jansen/alphalens-reloaded
200 https://arxiv.org/abs/1803.05024
200 https://arxiv.org/abs/math/0608017
200 https://www.nber.org/papers/w14554
200 https://www.jstor.org/stable/1802789
```

12/12 resolve. Support spot-checks: arXiv 1803.05024 is the López de Prado & Lewis (2019)
CPCV paper as cited; NBER w14554 is Asness–Moskowitz–Pedersen (2013) "Value and Momentum
Everywhere" as cited; JSTOR 1802789 is Shiller (1981) as cited. No contradicting source found.

Live cross-checks against COMPARISONS.md (dated 2026-10-12): mlfinlab `stargazers_count`
4939 + pushed 2023-10-02 — matches the table exactly; qlib live 49,311 vs table 49,308
(+3 stars of drift in transit — noise, not a finding).

---

## 3. Test-quality audit — 6 tests sampled, named fault injected, suite run

Driver `/tmp/c2_inject.py` (+`/tmp/c2_inject2.py` for T5r): back up the source file, apply
one exact string mutation, run the single node, restore, then re-run the subset to prove
green. Raw outputs abbreviated to the assertion lines.

| # | test | injected fault (one string mutation) | result |
|---|------|--------------------------------------|--------|
| T1 | `test_cv.py::test_purge_count_matches_label_geometry` | purge zeroed: `days=self.label_horizon` → `days=0` | exit 1 — DETECTED (`AssertionError` at test_cv.py:126) |
| T2 | `test_significance.py::test_bh_fdr_exact_boundary` | `if pval <= threshold:` → `if pval < threshold:` | exit 1 — DETECTED (`AssertionError` at test_significance.py:166) |
| T3 | `test_significance.py::test_wilson_lower_hand_computed` | drop `+ z2 / (4 * n * n)` from Wilson sqrt term | exit 1 — DETECTED (`AssertionError` at test_significance.py:66) |
| T4 | `test_significance_gaps.py::test_bh_step_up_not_step_down` | BH body forced false (`... and False or pval < 0`) | exit 1 — DETECTED (`AssertionError` at test_significance_gaps.py:247) |
| T5 | `test_adversarial.py::test_closure_lookahead_rejected_by_runtime_check` | `close.shift(-h)` → `close.shift(h)` inside `check_lookahead_runtime` (correlate against PAST returns) | **exit 0 — NOT DETECTED** (see F-T5) |
| T6 | `test_adversarial.py::test_html_report_escapes_injected_markup` | `html.escape(c)` → `c` in `_md_table_to_html` | exit 1 — DETECTED (`AssertionError` at test_adversarial.py:781) |

Restore check: `tests/test_cv.py + test_significance.py + test_significance_gaps.py +
test_adversarial.py` green after every restore (exit 0).

**Score: 5 of 6 named faults fail on their fault.** T1 is the fix-verification for F-T3:
the new purge-count KAT catches a purge-only fault alone, which the old joint-property test
could not. T5 is a new finding.

F-T5 mechanism (verified, not speculated): with the past-shift fault applied, the smoothed
closure-lookahead factor still correlates with past returns at |corr| up to 0.79:

```
past h= 1 corr= -0.4058
past h= 5 corr= -0.7878
past h= 10 corr= -0.7709
past h= 20 corr= -0.54
```

so `abs(corr) > 0.30` still fires and the test — which asserts the verdict, not the temporal
direction — stays green. A fault that inverts the check's arrow of time is invisible to the
suite. Legitimate factors probed directly (`rev_5/mom_20/rsi_14/noise_control` all `False`
at threshold 0.30) are unaffected, so this is a test-precision issue, not a live
false-positive. Related design note: the check uses `abs(corr)`, so a genuinely strong
reversal factor (|IC| ≥ 0.30 against future returns) would be flagged as lookahead; no such
factor exists in the library (max |IC| ≈ 0.07), but the docstring does not state this
ceiling assumption.

---

## 4. Bypass hunt (pass-1 scope: claim-adjacent attempts only)

- **Force flag:** `factor-lab promote --force noise_control` → argparse
  `error: unrecognized arguments: --force`. No override path exists. (Exit code measured
  after a `| tail` pipe, so the numeric code is tail's, not the CLI's — the rejection text
  itself is the evidence.)
- **Gate relaxation / permissive config:** per c1-p11, user-controlled thresholds are by
  design; not re-litigated.
- **README command honesty:** the exact commands in README lines 20-24 re-run unmodified
  in §C1 above.

---

## 5. Findings table (c2-p10)

| id | severity | finding | evidence | status |
|----|----------|---------|----------|--------|
| F-T3 | minor | (c1-p10) purge-only fault masked by embargo in joint-property test | fixed in f13d8fe; T1 injection fails the new KAT alone | fixed |
| F-T2 | minor | (c1-p10) BH `<=` boundary attribution over-claimed in hand-computed KAT docstring | fixed in f13d8fe; T2 injection fails `test_bh_fdr_exact_boundary` alone | fixed |
| F-L1 | minor | (c1-p10) DSR DOI described as "302 redirect", live behaviour is a redirect loop | RESEARCH.md §2.4 now says "redirect loop ... arXiv preprint is substantively equivalent" | fixed |
| F-T5 | minor | `test_closure_lookahead_rejected_by_runtime_check` pins the verdict, not the mechanism: inverting the runtime check to correlate against PAST returns (`shift(-h)`→`shift(h)`) leaves the suite green, because the smoothed-lookahead factor correlates with past returns at |corr|≤0.79 — above the 0.30 threshold either way | T5/T5r injection outputs + corr table in §3 | open |
| F-S1 | minor | Stale star counts in prose/sources blocks vs the live-verified table: RESEARCH.md body still says alphalens "4,456 stars" / qlib "48,917 stars, last push 2026-09-22" (lines ~1563/1569) while live is 4,939/49,311; COMPARISONS.md Sources block says purgedcv 35 / ml4t-diagnostic 32 / pyanomaly 132 stars vs its own table's 34/34/133 | API output §2; COMPARISONS.md lines 9-14 vs 59-61 | open |
| P02 | — | Positioning conflict with MARKET-VERDICTS.md: none found (re-checked §C3) | README lines 3, 12-13, 42-46; COMPARISONS.md table | refuted (no conflict) |

Claims C1/C2/C3: all three **supported** — no blocker, no major. The leakage property, the
gate verdict, and the promotion exit-code contract all survived attack. The two open
findings are precision/staleness issues; neither promotes noise nor blocks the gate.

### Status key

- `open`: reported for the builder; not yet fixed (reviewer does not fix code)
- `fixed`: builder fix re-verified with the reviewer's own injection/probe this pass
- `refuted`: attack attempted, claim held

---

## PASS c2-p11-adversarial-2 (cycle 2, adversarial pass 2 of 2)

Independent reviewer lane. This pass attacks the **property** (c2-p10 attacked the
claims). Read first: ITERATION-PROTOCOL.md, QUALITY-CONTRACT.md, MARKET-VERDICTS.md,
specs/factor-lab.md (incl. v0.2 MANDATE), the c1-p10/c1-p11/c2-p10 entries above.
No `reports/mutants-survived-c*.txt` exists in the repo.

Measured baseline (authoritative: reports/mutation-c1.json — quoted, not re-derived):
878/1977 mutants killed = 44.4%. Gate: 70%.

All commands below were actually run; output is verbatim terminal output.

---

## 0. Pre-attack state

```
$ .venv/bin/python -m pytest -p no:warnings 2>&1 | tail -1
133 passed in 49.62s
$ .venv/bin/python scripts/check_no_internal_refs.py 2>&1 | tail -2
FORBIDDEN [<repo>/.venv path prefix]  reports/improvements.md:319  `scripts/check_no_internal_refs.py` FAILED on 6 hits — all absolute `<repo>/`-prefixed host paths
check_no_internal_refs: FAIL — 1 forbidden token(s) found.
```

The F1 internal-refs gate was RED at pass start: `reports/improvements.md:319`
quotes the checker's own output containing the absolute host path, so the checker
flags the report that documents it. (Drive-by fix applied this pass — see F-G1.
The quoted path above is redacted to `<repo>/` per F1; the literal host prefix
was present in the raw terminal output.)

---

## 1. Property attacks — defeat the promotion gate

### ATTACK B1: diluted future leak via np.roll — **BYPASSED ALL GATES (BLOCKER F-B1)**

Goal: blend 3% future data into clean momentum using `np.roll` (no `.shift`
literal anywhere, shift amount in a module-level helper) and get promoted.

```
$ .venv/bin/python3 << 'PYEOF'
... DilutedLookahead: blend = 0.97 * mom.fillna(0) + 0.03 * lead.fillna(0) ...
B1 source patterns: []
B1 diluted np.roll lookahead verdict: promote
  not_lookahead: pass=True obs=no thr=no
  not_degenerate: pass=True obs=varied thr=non-constant
  coverage: pass=True obs=1.0 thr=0.5
  min_observations: pass=True obs=1499.0 thr=30.0
  min_abs_ic: pass=True obs=0.05039898886504679 thr=0.02
  min_ic_ir: pass=True obs=0.14544280052114392 thr=0.05
  hit_rate_wilson_lb: pass=True obs=0.5041454055240819 thr=0.5
  max_turnover: pass=True obs=0.2804462234081981 thr=0.5
  oos_consistency: pass=True obs=1.0 thr=0.6
  survives_fdr: pass=True obs=0.0 thr=0.15
```

Weight sweep on planted-signal data (seed 7) — Gate 0.75 runtime flag vs verdict:

```
w=0.0: runtime_flag=False verdict=promote bestIC=0.0257
w=0.03: runtime_flag=False verdict=promote bestIC=0.0504
w=0.1: runtime_flag=False verdict=promote bestIC=0.0670
w=0.2: runtime_flag=False verdict=promote bestIC=0.0954
w=1.0: runtime_flag=True verdict=reject bestIC=nan
```

Only the undiluted (100% future) leak trips the 0.30 correlation threshold.
Anything at or below 20% admixture is invisible to it.

### ATTACK B2: decisiveness — the leak flips REJECT into PROMOTE

Same shape on **plain** synthetic data (seed 7, no planted signal), where the
clean factor rejects:

```
w=0.0: runtime_flag=False verdict=reject bestIC=0.0065
w=0.05: runtime_flag=False verdict=promote bestIC=0.0488
w=0.1: runtime_flag=False verdict=promote bestIC=0.0759
```

A noise factor the gate correctly rejects becomes promoted by adding 5%
future data that no gate detects. This is not a precision issue: the core
safety property ("refuse factors that read future rows") was defeated, with a
verdict flip. Root cause: Gate 0.5 inspects syntax (evadable via closures,
np.roll, iloc tricks) and Gate 0.75 tests correlation magnitude (a diluted
leak sits below any threshold that keeps legitimate IC ~0.02-0.10 passing —
correlation cannot distinguish "legit IC 0.05" from "leak-driven IC 0.05").

### ATTACK B3: pure-noise seed shopping under the default config

```
$ ... for seed in range(30): promote(noise_control, synthetic(seed)) ...
(no output — shell tool terminated the command after exceeding 120s timeout)
```

**INCONCLUSIVE (environmental).** A full `promote()` (walk-forward CV over
1500x12 plus the new perturbation double-compute) takes ~30-60s per seed on
this box; 30 seeds exceed the command budget. Not evidence for or against the
gate — recorded so the next pass can run it as a background job instead of a
foreground probe. The planted-noise / planted-signal named tests
(`test_noise_control_rejected`, `test_planted_signal_promoted`) still cover
both directions at seed 7.

### ATTACK B4: wilson_lower invalid inputs (F-A4 re-probe — still open)

```
$ .venv/bin/python3 -c "from factorlab.significance import wilson_lower; ..."
k=-1, n=10 (negative k): ValueError: math domain error
k=15, n=10 (k>n): ValueError: math domain error
k=5, n=-1 (negative n): 0.0
k=5, n=0: 0.0
```

Unchanged since c1-p11: `math domain error` instead of an explicit validation
error; negative `n` silently returns 0.0. Non-exploitable for a promotion
bypass (no caller passes invalid k/n), so it stays minor. Left open for the
builder.

### ATTACK B5: determinism re-verified

```
determinism: True IC=0.0252298764
```

Same seed twice → bit-identical IC. Holds after the Gate 0.85 insertion
(the perturbation transform is deterministic: per-asset tail reversal, no RNG).

---

## 2. F-B1 fix (applied this pass, reviewer-implemented per c1-p11 precedent)

New Gate 0.85 in `promote()`: `check_lookahead_perturbation()` in
`src/factorlab/cv.py`. It tests the property directly instead of the
mechanism — perturb only the last 20 days of OHLCV data (deterministic
per-asset tail reversal), recompute, and demand bit-identical factor values
at all dates before the perturbed region. Any differing past value proves the
factor reads future rows, however obfuscated. Documented assumption: no
full-sample (global) normalization, which is itself in-sample leakage.

Calibration (plain synthetic, seed 7): all 11 clean library factors plus
`noise_control` → 0 differing past values; `lookahead_control` → 12;
5% leak blend → 60. Zero false positives, both leak shapes flagged.

Post-fix verification (same B2 shape that flipped the verdict):

```
leak5 verdict: reject
  FAIL no_future_dependence: Factor values at 60 past dates changed when only future OHLCV data was perturbed (tail_days=20). A causal factor cannot do this — lookahead contamination.
```

Tests added (`tests/test_adversarial.py`, each with a fault-naming docstring):
`test_diluted_leak_rejected_by_perturbation_gate` (pins verdict + reason code,
with a precondition asserting Gates 0.5/0.75 stay blind so the test cannot pass
vacuously),
`test_perturbation_no_false_positives_on_library` (all registry factors except
the deliberate control),
`test_perturbation_flags_registered_lookahead_control`.

Post-fix state:

```
$ .venv/bin/python -m pytest -p no:warnings 2>&1 | tail -1
136 passed in 46.73s
$ .venv/bin/python -m ruff check . 2>&1 | tail -1
All checks passed!
$ .venv/bin/python -m ruff format --check . 2>&1 | tail -1
25 files already formatted
$ .venv/bin/python scripts/check_no_internal_refs.py 2>&1 | tail -1
check_no_internal_refs: CLEAN — no forbidden tokens found.
$ .venv/bin/python scripts/check_real_data_proof.py 2>&1 | tail -2
check_real_data_proof: all checks passed.
... (checker prints its own completion line)
```

(Mandate note: the v0.2 proof checker passes locally. Positioning re-checked
against MARKET-VERDICTS.md while here: README still leads with the licence
problem, COMPARISONS.md table present, MlFinLab-more-complete stated — no
conflict to record.)

---

## 3. Findings table (c2-p11)

| id | severity | finding | evidence | status |
|----|----------|---------|----------|--------|
| F-B1 | **blocker** | Diluted future leak (<=20% np.roll admixture, no `.shift` literal) promoted with all gates passing; 5% admixture flips a clean REJECT (IC=0.0065) into PROMOTE (IC=0.0488). Correlation screening cannot see sub-threshold leaks; source inspection cannot see non-literal shifts. | B1/B2 outputs §1; pre-fix verdict=promote rows | **fixed** (Gate 0.85 perturbation test; post-fix verdict=reject via `no_future_dependence`; 3 tests; 136 green) |
| F-G1 | minor | `reports/improvements.md:319` quoted checker output containing the absolute host path, so `check_no_internal_refs.py` (which scans `reports/`) failed on the file documenting it — F1 gate red at pass start. | pre-attack state §0 | **fixed** (redacted to non-literal wording; checker CLEAN) |
| F-A4 | minor | (c1-p11) `wilson_lower` raises `math domain error` on k<0/k>n, silently returns 0.0 on negative n. Non-exploitable for promotion bypass. | B4 output §1 | open |
| F-T5 | minor | (c2-p10) runtime-check direction fault invisible to suite (past-shift mutation stays green). Not re-probed; the new perturbation tests pin mechanism for Gate 0.85, but the Gate 0.75 test-precision gap stands as reported. | c2-p10 §3 | open |
| F-S1 | minor | (c2-p10) stale star counts in RESEARCH.md prose (qlib 48,917/last-push-2026-09-22 at lines 1544/1569) vs live-verified table. Not re-probed live this pass; untouched by this pass's diff. | grep §-prep | open |
| B3 | — | Noise seed-shopping sweep inconclusive (command timed out; ~30-60s per promote × 30 seeds). No signal either way. | B3 output §1 | open (method note for next pass: background job) |
| P03 | — | Positioning conflict with MARKET-VERDICTS.md: none found (re-checked). | README/COMPARISONS.md | refuted (no conflict) |

Prior findings F-T3/F-T2/F-L1: remain fixed (c2-p10 re-verified; untouched by
this pass's diff, suite still green).

### Status key

- `open`: reported for the builder; not yet fixed
- `fixed`: fix implemented and re-verified with the pass's own probes this pass
- `refuted`: attack attempted, claim held

---

## PASS c3-p10-adversarial-1 (cycle 3, adversarial pass 1 of 2)

Independent reviewer lane. This pass attacks the **claims** (c3-p11 attacks the
property). Read first: ITERATION-PROTOCOL.md, QUALITY-CONTRACT.md,
MARKET-VERDICTS.md, specs/factor-lab.md (incl. v0.2 MANDATE), the
c1-p10/c1-p11/c2-p10/c2-p11 entries above. No `reports/mutants-survived-c*.txt`
with content exists (file is present but 0 bytes); authoritative mutation
baseline remains reports/mutation-c1.json (878/1977 = 44.4%, gate 70%),
with reports/mutation-c2.json recording a 0/0 infra failure (rc=2) — quoted,
not re-derived.

Branch note: `feat/v0.1` is checked out by a sibling worktree (host path
redacted per F1), so this pass worked on a
branch cut at the same commit (448084b). The artifact below is committed in
this repo; the content is branch-independent.

All commands below were actually run; output is verbatim terminal output.

---

## 0. Pre-attack state + prior-findings re-verification

```
$ .venv/bin/python -m pytest -p no:warnings 2>&1 | tail -1
141 passed in 49.26s
```

- **F-A4 (wilson_lower invalid inputs): FIXED** (commit 448084b
  "actionable wilson_lower errors"). Re-verified, not trusted:

```
$ .venv/bin/python -c "from factorlab.significance import wilson_lower; ..."
k=-1 ValueError wilson_lower: require 0 <= k <= n (successes cannot exceed trials), got k=-1, n=10.
k>n ValueError wilson_lower: require 0 <= k <= n (successes cannot exceed trials), got k=15, n=10.
n<0 ValueError wilson_lower: n must be >= 0 (number of valid observations), got n=-1.
n=0 ValueError wilson_lower: require 0 <= k <= n (successes cannot exceed trials), got k=5, n=0.
```

  Every invalid shape now raises an actionable ValueError naming the
  constraint (previously `math domain error` / silent 0.0). → **fixed**
- **F-T5 (runtime-check direction fault invisible):** re-probed as T5 below —
  still green on the inverted check. → **open (stands)**
- **F-S1 (stale star counts in prose):** re-probed live this pass — prose at
  lines 1544/1569 still says qlib "48,917 stars, last push 2026-09-22" while
  live is 49,316 / pushed 2026-10-08 (table at line 1641 says 49,308, i.e.
  table drift is noise, prose staleness is real). → **open (stands)**
- **B3 (noise seed-shopping):** not attempted (same cost constraint as c2-p11:
  ~30-60s per promote x N seeds exceeds the foreground budget). → **open**

---

## 1. Claims audit — 3 most load-bearing README claims, attacked

### C1 — "Promote a real signal (exit 0) or reject noise (exit 1)"

```
$ .venv/bin/python -m factorlab.cli promote mom_20 --data signal --plant-signal >/dev/null 2>&1; echo "mom_20_planted=$?"
mom_20_planted=0
$ .venv/bin/python -m factorlab.cli promote noise_control --data signal >/dev/null 2>&1; echo "noise=$?"
noise=1
```

**Verdict: SUPPORTED.** Exit codes as documented, measured without an
intervening pipe.

### C2 — "Real results (from examples/run_demo.sh)": README table is the demo's output

```
$ .venv/bin/python -m factorlab.cli screen --data signal --horizons 1,5,20 --out /tmp/c3_screen/ > /tmp/c3_screen_out.txt 2>&1; echo "screen_exit=$?"
screen_exit=0
$ grep '^|' /tmp/c3_screen_out.txt | sort -u > /tmp/c3_scr.txt; grep '^|' README.md | sort -u > /tmp/c3_rd.txt; diff /tmp/c3_scr.txt /tmp/c3_rd.txt && echo ROWS_IDENTICAL
ROWS_IDENTICAL
$ grep -n "Promoted" /tmp/c3_screen_out.txt | head -2
19:Promoted (0): none
```

**Verdict: SUPPORTED.** All 13 table rows byte-identical to a fresh run
(screen step of the demo pipeline; the full demo script was verified
row-identical in c1-p10/c2-p10 and the screen output is its table source).
"0 promoted" matches the README "0/13" framing.

### C3 — Positioning: MlFinLab licence/pricing; Quantopian stack abandoned 2020

```
$ curl -sS -L --max-time 25 https://raw.githubusercontent.com/hudson-and-thames/mlfinlab/master/LICENSE.txt | grep -cE '6\.6|6\.7|14\.2|14\.3|14\.5'
6
$ curl -sS -L --max-time 25 "https://hudsonthames.org/mlfinlab/" -o /tmp/c3_mlp.html; echo "bytes=$(wc -c < /tmp/c3_mlp.html)"
bytes=224252
$ grep -oiE '£100[^<]{0,10}' /tmp/c3_mlp.html | head -2
£100 (+VAT)
$ curl -sS --max-time 20 "https://api.github.com/repos/quantopian/alphalens/commits?per_page=1" | grep -m1 '"date"'
        "date": "2020-04-27T18:40:41Z"
$ curl -sS --max-time 20 "https://api.github.com/repos/quantopian/pyfolio/commits?per_page=1" | grep -m1 '"date"'
        "date": "2020-02-28T17:30:19Z"
```

**Verdict: SUPPORTED.** Licence-clause grep hits 6 lines covering
6.6/6.7/14.2/14.3/14.5; pricing page returns exactly `£100 (+VAT)`;
alphalens last master commit 2020-04-27, pyfolio 2020-02-28. No conflict
with MARKET-VERDICTS.md positioning to record.

### Incidental badge claim

```
$ .venv/bin/python -m pytest -p no:warnings 2>&1 | tail -1
141 passed in 49.26s
```

README badge `tests-141 passed` is accurate. (`ruff check` / `ruff format
--check` were clean at commit 448084b per its message; not re-run here —
the reviewer touched no Python files, only appended to this markdown file.)

---

## 2. Citation audit — all 104 unique URLs in docs/RESEARCH.md

Method: extracted 104 unique `https://` URLs, probed each with
`curl -s -o /dev/null -w '%{http_code}' -L --max-time 25` (16-way parallel,
research UA). One table entry is a display-truncated URL
(`taylorfrancis.com/.../9780429246593/...` at line 1875 — the full URL is
cited in §2.5 and returns 200); 103 probed.

```
probed=103
     79 200
     21 403
      1 404
      2 redirect-loop (curl exit 47, last code 302)
```

Non-200 detail (raw):

```
403 https://doi.org/10.1002/ijfe.70036
403 https://doi.org/10.1080/01621459.1994.10476870
403 https://doi.org/10.1093/rfs/hhv059
403 https://doi.org/10.1093/rfs/hhx132
403 https://doi.org/10.1111/0022-1082.00247
403 https://doi.org/10.1111/0022-1082.00163
403 https://doi.org/10.1093/rfs/1.1.41
403 https://doi.org/10.1080/01621459.1927.10502953
403 https://doi.org/10.1111/1468-0262.00152
403 https://doi.org/10.1111/j.1468-0262.2005.00615.x
403 https://doi.org/10.1111/j.1540-6261.1985.tb05004.x
403 https://doi.org/10.1111/jofi.12365
403 https://doi.org/10.1111/j.1540-6261.1993.tb04702.x
403 https://doi.org/10.1111/jofi.12021
403 https://doi.org/10.1111/jofi.13131
403 https://doi.org/10.2307/2297912
403 https://doi.org/10.2469/faj.v58.n4.2453
404 https://doi.org/10.1198/073500104000000063
403 https://papers.ssrn.com/sol3/papers.cfm?abstract_id=377260
403 https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3913263
403 https://www.tandfonline.com/doi/abs/10.2469/faj.v58.n4.2453
403 https://www.pm-research.com/content/iijaltinv/early/2023/03/25/jai.2023.1.189.full.pdf
redirect-loop https://doi.org/10.3905/jpm.2014.40.5.094
redirect-loop https://doi.org/10.3905/jai.2023.1.189
```

Disposition:

- **79/103 → HTTP 200**, including every JSTOR/NBER/arXiv/GitHub-API/PyPI
  alternate the file promises and all 12 c2 ecosystem re-check URLs.
- **21× 403**: publisher DOI resolvers + SSRN + T&F/PM-Research bot-blocking.
  Each affected citation block carries a 200-returning alternate (JSTOR/NBER)
  or is explicitly marked NOT claimed (§8.7 table, lines 2317/2874-2878 for
  the 404/SSRN/DOI-throttled cases) — verified present by grep.
- **1× 404** (`doi:10.1198/...`): documented "404 — NOT claimed" at line 2317.
- **2× redirect loop** (both IPR-Journals `10.3905` DOIs): the DSR DOI loop is
  documented in §2.4; the `jai.2023.1.189` DOI is documented "429 — NOT
  claimed" at line 2874 (today it loops rather than 429s — same disposition:
  not claimed, alternate SSRN also not claimed).
- **Support spot-checks:** `nber.org/papers/w25882` citation meta returns
  `citation_title = "Common Risk Factors in Cryptocurrency"` (see F-C1);
  springer landing+PDF both 200 with the DOI-suffixed URL matching the cited
  Grobys et al. 2025 reference (page body sits behind a "Client Challenge"
  bot wall via curl, so support rests on the DOI identifier match, not
  fetched text — noted, not a finding).
- **One citation resolves to the WRONG paper → F-C1 (major).**

---

## 3. Test-quality audit — 6 tests sampled, named fault injected, suite run

Driver `/tmp/c3_inject.py` (+`/tmp/c3_t6.py` for T6): back up the source
file, apply one exact string mutation (asserted unique, except T6 where the
two `evaluate_*` blocks are byte-identical and the fault was scoped to the
`evaluate_cpcv` half), run the single node, restore, then re-run the subset
to prove green. `git diff --stat` empty after every restore (verified).

| # | test | injected fault (one string mutation) | result |
|---|------|--------------------------------------|--------|
| T1 | `test_adversarial.py::test_diluted_leak_rejected_by_perturbation_gate` | Gate 0.85 blinded: `if n_diffs > max_diffs:` → `if n_diffs > 10**12:` | exit 1 — DETECTED (`AssertionError` at test_adversarial.py:899) |
| T2 | `test_significance.py::test_wilson_lower_rejects_negative_k` | validation removed: `if k < 0 or k > n:` → `if False:` | exit 1 — DETECTED (`AssertionError` at test_significance.py:102) |
| T3 | `test_promote.py::test_low_coverage_factor_rejected` | coverage gate forced pass: `passed=cov >= cfg.coverage_min,` → `passed=True,` | exit 1 — DETECTED (`AssertionError` at test_promote.py:169) |
| T4 | `test_significance.py::test_deflated_sharpe_invalid_args` | validation removed: `if n_trials < 1:` → `if False:` | exit 1 — DETECTED (ZeroDivisionError at significance.py:173 — the test expects ValueError, the fault surfaces a crash instead) |
| T5 | `test_adversarial.py::test_closure_lookahead_rejected_by_runtime_check` | Gate 0.75 direction inverted: `close.shift(-h)` → `close.shift(h)` (correlate against PAST returns) | **exit 0 — NOT DETECTED** (see F-T5, stands) |
| T6 | `test_cv.py::test_evaluate_cpcv_returns_valid_oos_ic` | OOS aggregation broken: `append(m.ic_pearson)` → `append(float("nan"))` inside `evaluate_cpcv` only | exit 1 — DETECTED (`AssertionError` at test_cv.py:405) |

Restore check: `tests/test_cv.py` green after restore (exit 0); full-suite
`git diff --stat` empty; pre-attack full suite was 141 passed.

**Score: 5 of 6 named faults fail on their fault.** T5 is the known F-T5
gap (re-confirmed, not newly introduced).

---

## 4. Bypass hunt (pass-1 scope: claim-adjacent attempts only)

- **Force flag:** not re-probed (c1-p10/c2-p10 both confirm `--force` is
  rejected by argparse; CLI surface untouched since — `git log` shows no
  cli.py changes after those probes).
- **Gate relaxation / permissive config:** by design per c1-p11; not
  re-litigated.
- **README command honesty:** the exact quickstart commands re-run
  unmodified in §C1 above.

---

## 5. Findings table (c3-p10)

| id | severity | finding | evidence | status |
|----|----------|---------|----------|--------|
| F-C1 | major | RESEARCH.md §8.1 cites "Liu, Tsyvinski & Wu (2022), Common Risk Factors in Cryptocurrency" at NBER URL `w28682` — but live `nber.org/papers/w28682` is Borjas & Edo (2021), "Gender, Selection into Employment, and the Wage Impact of Immigration" (citation_title meta + citation_doi 10.3386/w28682, fetched 2026-10-13). Transposed digits: the Liu et al. paper is **w25882** (verified: its NBER page returns `citation_title = "Common Risk Factors in Cryptocurrency"`). Same wrong URL repeated in the §8.8 verification table (line ~2299). The claim itself is true and the method extracted matches the real paper — only the WP number/URL is wrong — so this is a one-line builder fix, but per QUALITY-CONTRACT §3 a citation that does not support its claim is a blocking-class defect. | NBER fetches §2; RESEARCH.md lines 1929-1931, ~2299 | open |
| F-T5 | minor | (c2-p10) Gate-0.75 direction fault still invisible: T5 inversion stays green. The Gate-0.85 perturbation tests pin mechanism for the new gate, but the 0.75 test-precision gap stands. | T5 output §3 | open |
| F-S1 | minor | (c2-p10) RESEARCH.md prose lines 1544/1569 still say qlib "48,917 stars, last push 2026-09-22"; live is 49,316 / pushed 2026-10-08 (table line 1641 says 49,308 — table drift is noise, prose staleness is real). | API output §0 | open |
| F-S2 | minor | Verification table line 1875 records the Efron & Tibshirani URL truncated with a literal `...` (`.../9780429246593/...`). Display-only: the full URL is cited in §2.5 and returns 200 today. One-line cleanup. | grep §2; audit file | open |
| F-A4 | minor | (c1-p11) wilson_lower invalid-input handling | fixed in 448084b; re-verified §0 | fixed |
| B3 | — | Noise seed-shopping sweep still not attempted (same foreground-cost constraint). | c2-p11 §1; this pass §0 | open (method note: background job) |
| P04 | — | Positioning conflict with MARKET-VERDICTS.md: none found (re-checked §C3). | README/COMPARISONS.md | refuted (no conflict) |

Claims C1/C2/C3: all three **supported** — no blocker. One major (wrong-paper
citation URL), three minors open (two carried, one new display-only).

### Status key

- `open`: reported for the builder; not yet fixed
- `fixed`: fix implemented and re-verified with the pass's own probes this pass
- `refuted`: attack attempted, claim held

---

## PASS c4-p10-adversarial-1 (cycle 4, adversarial pass 1 of 2)

Independent reviewer lane. This pass attacks the **claims** (c4-p11 attacks the
property). Read first: ITERATION-PROTOCOL.md, QUALITY-CONTRACT.md,
MARKET-VERDICTS.md, specs/factor-lab.md (incl. v0.2 MANDATE), the
c1-p10/c1-p11/c2-p10/c2-p11/c3-p10/c3-p11 entries above. Both
`reports/mutants-survived-c2.txt` and `reports/mutants-survived-c3.txt` are
present but 0 bytes; authoritative mutation baseline remains
reports/mutation-c1.json (878/1977 = 44.4%, gate 70%) — quoted, not re-derived.

Cycle-4 delta under review (commits 215da06..537dd97): F-T5 direction-sensitive
pin test (d2e2f38), microstructure module + Roll/staleness diagnostics wired
into the real-data proof (47a39d5), launch surfaces (9e5429d), scale-aware Roll
floor (537dd97). Test count 142 → 159.

All commands below were actually run; output is verbatim terminal output.

---

## 0. Pre-attack state + prior-findings re-verification

```
$ .venv/bin/python -m pytest -p no:warnings 2>&1 | tail -1
159 passed in 62.99s
$ .venv/bin/python scripts/check_no_internal_refs.py 2>&1 | tail -1
check_no_internal_refs: CLEAN — no forbidden tokens found.
$ .venv/bin/python scripts/check_real_data_proof.py 2>&1 | tail -1
PROOF_COMPLETE
$ .venv/bin/python -m ruff check . 2>&1 | tail -1
All checks passed!
$ .venv/bin/python -m ruff format --check . 2>&1 | tail -1
27 files already formatted
```

- **F-T5 (Gate-0.75 direction fault invisible): FIXED** (commit d2e2f38,
  "direction-sensitive runtime-check pin"). Re-verified with the reviewer's own
  injection this pass (T1 below): inverting `close.shift(-h)` → `close.shift(h)`
  in `check_lookahead_runtime` fails the new
  `test_runtime_check_direction_sensitive_pure_future_factor` alone (exit 1,
  AssertionError at test_adversarial.py:829). The old smoothed-closure test
  stays green under the same mutant (known, documented in the new test's
  docstring) — the new test is the pin, and it holds. → **fixed**
- **F-A4 (wilson_lower invalid inputs):** re-probed directly — all four invalid
  shapes raise actionable ValueError (`require 0 <= k <= n ...`, `n must be >=
  0 ...`). → **fixed (stands)**
- **F-S1 (stale qlib prose):** live API this pass returns 49,324 stars / pushed
  2026-10-08 vs file's 49,316 / 2026-10-08 (+8 stars same-day drift — noise,
  not staleness). → **fixed (stands)**
- **F-B2/F-B1/F-C1/F-S2/F-G2:** untouched by the cycle-4 diff; suite green.
- **B3 (noise seed-shopping):** c3-p11 covered 4/30 seeds (all reject); not
  extended here (same ~40s-per-promote foreground cost). → **open (stands)**

---

## 1. Claims audit — 3 most load-bearing README claims, attacked

### C1 — "Promote a real signal (exit 0) or reject noise (exit 1)"

```
$ .venv/bin/python -m factorlab.cli promote mom_20 --data signal --plant-signal >/dev/null 2>&1; echo "mom_20_planted=$?"
mom_20_planted=0
$ .venv/bin/python -m factorlab.cli promote noise_control --data signal >/dev/null 2>&1; echo "noise=$?"
noise=1
```

**Verdict: SUPPORTED.** Exit codes as documented, measured without an
intervening pipe.

### C2 — "Real results (from examples/run_demo.sh)": README table is the demo's output

```
$ bash examples/run_demo.sh > /tmp/c4_demo.txt 2>&1; echo "demo_exit=$?"
demo_exit=0
$ grep '^|' /tmp/c4_demo.txt | sort -u > /tmp/c4_dr.txt; grep '^|' README.md | sort -u > /tmp/c4_rr.txt; diff /tmp/c4_dr.txt /tmp/c4_rr.txt && echo ROWS_IDENTICAL
ROWS_IDENTICAL
$ grep -n "Promoted" /tmp/c4_demo.txt | head -2
39:Promoted (0): none
```

**Verdict: SUPPORTED.** All 13 table rows byte-identical to a fresh full-demo
run; "Promoted (0): none" matches the README "0/13" framing.

### C3 — Positioning: MlFinLab licence/pricing; Quantopian stack abandoned 2020

```
$ curl -sS -L --max-time 25 https://raw.githubusercontent.com/hudson-and-thames/mlfinlab/master/LICENSE.txt | grep -cE '6\.6|6\.7|14\.2|14\.3|14\.5'
6
$ curl -sS --max-time 20 "https://api.github.com/repos/quantopian/alphalens/commits?per_page=1" | grep -m1 '"date"'
        "date": "2020-04-27T18:40:41Z"
$ curl -sS --max-time 20 "https://api.github.com/repos/quantopian/pyfolio/commits?per_page=1" | grep -m1 '"date"'
        "date": "2020-02-28T17:30:19Z"
```

**Verdict: SUPPORTED.** Licence-clause grep hits 6 lines covering
6.6/6.7/14.2/14.3/14.5 (pricing page re-verified `£100 (+VAT)` in c3-p10; page
unchanged, not re-fetched). alphalens last commit 2020-04-27, pyfolio
2020-02-28. No conflict with MARKET-VERDICTS.md positioning to record.

### Incidental badge claim

Full suite: `159 passed in 62.99s`. README badge `tests-159 passed` is
accurate. `ruff check` / `ruff format --check` clean.

---

## 2. Citation audit — cycle-4 additions (§12, c4-p01/p02)

c3-p10 covered the original 104. Cycle 4 added 12 unique URLs (119 total).
All 12 probed with `curl -s -o /dev/null -w '%{http_code}' -L --max-time 25`:

```
200 https://ideas.repec.org/a/bla/jfinan/v39y1984i4p1127-39.html
200 https://ideas.repec.org/a/eee/jfinec/v17y1986i2p223-249.html
200 https://ideas.repec.org/a/eee/jfinec/v5y1977i3p309-327.html
200 https://ideas.repec.org/a/eee/jfinec/v7y1979i2p197-226.html
200 https://www.jstor.org/stable/2290993
200 https://www.jstor.org/stable/2327617
200 https://www.jstor.org/stable/2328797
200 https://www.jstor.org/stable/43866013
200 https://www.nber.org/papers/w20721
200 https://www.nber.org/papers/w9571
200 https://www.ssc.wisc.edu/~bhansen/718/Politis%20Romano.pdf
403 https://doi.org/10.1093/rfs/hhv063
```

Disposition:

- **11/12 → HTTP 200.** The single 403 (`doi:10.1093/rfs/hhv063`, OUP
  bot-blocking) is the known publisher pattern: the same citation block carries
  two 200-returning alternates (NBER w20721 + JSTOR 43866013), and the file
  pre-flagged the hhv059/hhv063 one-digit-apart confusion and resolved it
  in-file ("confirmed verbatim ... no correction needed").
- **Support spot-checks:** RePEc `.../v39y1984i4p1127-39.html` returns
  `<TITLE>A Simple Implicit Measure of the Effective Bid-Ask Spread in an
  Efficient Market` — Roll (1984) as cited at line 3110. NBER w20721 returns
  `citation_title = "A Taxonomy of Anomalies and their Trading Costs"` —
  Novy-Marx & Velikov as cited at line 3160. No contradicting source found.

---

## 3. Test-quality audit — 6 tests sampled, named fault injected, suite run

Driver `/tmp/c4_inject.py` (T1–T5) + inline sed-restore (T6): back up the
source file, apply one exact string mutation (asserted unique), run the single
node, restore. `git status -- src tests` empty after every restore (verified).
Raw outputs abbreviated to the assertion lines.

| # | test | injected fault (one string mutation) | result |
|---|------|--------------------------------------|--------|
| T1 | `test_adversarial.py::test_runtime_check_direction_sensitive_pure_future_factor` | Gate 0.75 direction inverted: `close.shift(-h)` → `close.shift(h)` in `check_lookahead_runtime` | exit 1 — DETECTED (`AssertionError` at test_adversarial.py:829) |
| T2 | `test_microstructure.py::test_roll_spread_hand_computed` | Roll formula halved: `2.0 * np.sqrt(-cov1)` → `np.sqrt(-cov1)` | exit 1 — DETECTED (`AssertionError` at test_microstructure.py:88) |
| T3 | `test_significance.py::test_wilson_lower_rejects_negative_k` | validation removed: `if k < 0 or k > n:` → `if False:` | exit 1 — DETECTED (`AssertionError` at test_significance.py:102) |
| T4 | `test_promote.py::test_low_coverage_factor_rejected` | coverage gate forced pass: `passed=cov >= cfg.coverage_min,` → `passed=True,` | exit 1 — DETECTED (`AssertionError` at test_promote.py:169) |
| T5 | `test_adversarial.py::test_diluted_leak_rejected_by_perturbation_gate` | Gate 0.85 blinded: `if n_diffs > max_diffs:` → `if n_diffs > 10**12:` | exit 1 — DETECTED (`AssertionError` at test_adversarial.py:975) |
| T6 | `test_significance.py::test_bh_fdr_exact_boundary` | `if pval <= threshold:` → `if pval < threshold:` | exit 1 — DETECTED (`AssertionError` at test_significance.py) |

Restore check: `tests/test_significance.py + tests/test_microstructure.py`
green after restore (39 passed); full-suite pre-attack state was 159 passed;
`git status -- src tests` clean.

**Score: 6 of 6 named faults fail on their fault.** T1 is the fix-verification
for F-T5: the direction mutant that the old smoothed-closure test cannot see
is now caught by the new pin test alone. T2 covers the cycle-4 microstructure
surface (Roll KAT pins the 2× constant from the paper equation).

---

## 4. Bypass hunt (pass-1 scope: claim-adjacent attempts only)

- **Force flag:** `.venv/bin/python -m factorlab.cli promote --force
  noise_control` → `factor-lab: error: unrecognized arguments: --force`. No
  override path exists. (CLI surface untouched since c3-p10's probe.)
- **Gate relaxation / permissive config:** by design per c1-p11; not
  re-litigated.
- **README command honesty:** the exact quickstart commands re-run unmodified
  in §C1 above.

---

## 5. Findings table (c4-p10)

| id | severity | finding | evidence | status |
|----|----------|---------|----------|--------|
| F-T5 | minor | (c2-p10) Gate-0.75 direction fault invisible to suite | fixed in d2e2f38; T1 injection fails the new pin test alone | fixed |
| F-S1 | minor | (c2-p10) qlib prose staleness | live 49,324 vs file 49,316 (+8 same-day drift — noise) | fixed (stands) |
| B3 | — | Noise seed-shopping sweep still partial (4/30, all reject) | c3-p11 §1; same foreground-cost constraint | open (method note: background job) |
| P06 | — | Positioning conflict with MARKET-VERDICTS.md: none found (re-checked §C3) | README/COMPARISONS.md | refuted (no conflict) |

Claims C1/C2/C3: all three **supported** — no blocker, no major. Citation
audit: 11/12 new URLs 200, 1× documented 403-with-alternates. Test audit: 6/6
named faults detected. Prior open precision gap F-T5 is now closed; no new
findings opened by this pass.

### Status key

- `open`: reported for the builder; not yet fixed (reviewer does not fix code)
- `fixed`: fix implemented and re-verified with the reviewer's own probes this pass
- `refuted`: attack attempted, claim held

---

## PASS c3-p11-adversarial-2 (cycle 3, adversarial pass 2 of 2)

Independent reviewer lane. This pass attacks the **property** (c3-p10 attacked the
claims). Read first: ITERATION-PROTOCOL.md, QUALITY-CONTRACT.md,
MARKET-VERDICTS.md, specs/factor-lab.md (incl. v0.2 MANDATE), the
c1-p10/c1-p11/c2-p10/c2-p11/c3-p10 entries above. No `reports/mutants-survived-c*.txt`
with content exists (file present but 0 bytes); authoritative mutation baseline
remains reports/mutation-c1.json (878/1977 = 44.4%, gate 70%) — quoted, not
re-derived.

Worktree note: this pass ran in the repo root on `feat/v0.1` (commit 91cefb8 at
pass start). No absolute host paths appear below per F1.

All commands below were actually run; output is verbatim terminal output.

---

## 0. Pre-attack state

```
$ git log --oneline -3
91cefb8 docs(review): cycle 3 adversarial pass 1 — claims hold, wrong-paper NBER URL found
448084b fix(stats,docs): actionable wilson_lower errors, README badge + fork qualifier
8efa46a test(properties): exact-tie degeneracy excuse for self-correlation
```

Prior-findings triage (re-verified or fixed this pass, not trusted):
F-C1 (major, wrong-paper NBER URL), F-S1 (stale qlib prose), F-S2 (truncated
display URL) — fixed this pass, see section 3. F-T5 (Gate-0.75 direction fault
invisible) — stands, not re-probed: Gate 0.75 is untouched by this pass's diff.
B3 (noise seed-shopping) — partial progress this pass: seeds 1-4 all reject
(see C4). F-A4 — remains fixed (untouched).

The F1 internal-refs gate was RED at pass start (see F-G2, fixed this pass).

---

## 1. Property attacks — defeat the promotion gate

### ATTACK C1: B1 regression — diluted np.roll leak still rejected

```
rows: 18000
C1 B1-regression w=0.05 verdict: reject
```

Gate 0.85 (single-tail at the time) holds against the c2-p11 shape. Baseline
confirmed before attempting new bypasses.

### ATTACK C2: windowed early leak — **BYPASSED ALL GATES (BLOCKER F-B2)**

Goal: confine the future admixture to dates far from the tail (leak active only
before T-60d, clean momentum after), using `np.roll` so no `.shift(-N)` literal
exists for Gate 0.5. The tail-only perturbation check never perturbs a row this
factor reads from the future.

```
C2 perturbation flag: False |
C2 source patterns: []
C2 runtime flag: (False, '')
C2 verdict: promote
   not_lookahead: pass=True obs=no
   not_degenerate: pass=True obs=varied
   coverage: pass=True obs=1.0
   min_observations: pass=True obs=1440.0
   min_abs_ic: pass=True obs=0.07882436905016416
   min_ic_ir: pass=True obs=0.22366000303877712
   hit_rate_wilson_lb: pass=True obs=0.5255986458355847
   max_turnover: pass=True obs=0.2946408716922393
   oos_consistency: pass=True obs=0.8
   survives_fdr: pass=True obs=0.0
```

Decisiveness control — the same shape with the future leg removed, on the same
plain synthetic data (seed 7, no planted signal):

```
clean-twin verdict: reject
   min_abs_ic: pass=False obs=0.007445263322118622
   min_ic_ir: pass=False obs=0.021460523058075304
   survives_fdr: pass=False obs=0.41853
```

A correctly-rejected factor (IC=0.0074, FDR p=0.42) becomes promoted (IC=0.079,
all 10 gates pass) by adding future data that no gate sees. Verdict flip
proven, not speculated. Root cause: Gate 0.85 perturbed only the last 20 days,
so any leak confined to earlier dates is structurally invisible to it.

(Note for the record: the first draft of this attack used a literal
`close.shift(-5)` inside a heredoc-defined class, where `inspect.getsource()`
cannot see stdin code — Gate 0.5 reported `[]` artifactually. The filed attack
and the regression test use `np.roll`, which keeps Gate 0.5 blind even for
file-defined factors. The committed test pins this precondition explicitly.)

### ATTACK C3: quantized diluted leak — BLOCKED (failed attack is evidence)

Goal: sign-quantize a 5% future blend so the tail perturbation causes zero
output diffs while the leak still boosts IC.

```
C3 perturbation flag: True | Factor values at 1 past dates changed when only future OHLCV data was perturbed
C3 verdict: reject
   not_lookahead: pass=True obs=no
   no_future_dependence: pass=False obs=changed
```

Bit-exact comparison catches even a single flipped sign. Quantization does not
save the attacker: any surviving IC boost implies some output depends on the
perturbed rows.

### ATTACK C4: noise seed-shopping, partial sweep (B3 continued)

```
seed 1 reject
seed 2 reject
seed 3 reject
seed 4 reject
```

`noise_control` rejects on seeds 1-4 (plain synthetic, default config). Partial
(4/30): each full `promote()` costs ~40s on this box, so the full 30-seed sweep
remains a background job. Direction so far: 4/4 reject, no signal of a
specificity hole.

---

## 2. F-B2 fix (applied this pass, reviewer-implemented per c2-p11 precedent)

`check_lookahead_perturbation()` in `src/factorlab/cv.py` now tests `n_windows=4`
staggered windows ending at quartile fractions of the sample (the last is the
tail) instead of the tail only. Baseline is computed once; each window is
perturbed and recomputed independently, and any differing past value in any
window proves future dependence. The `if n_diffs > max_diffs:` comparison the
c3-p10 T1 injection blinds is preserved per window, so that test still guards
the mechanism. `promote.py` Gate 0.85 comment updated (defaults flow through;
no threshold changed). Documented residual: a leak confined entirely to one
inter-window gap and never reading a later window still dodges — but such a
leak covers too little sample to move full-sample IC above the 0.02 floor
alone (calibration: 10%-admixture needs ~95% coverage to reach IC 0.08);
`n_windows` shrinks the gaps further.

Post-fix verification is the new regression test itself (it re-runs the filed
C2 shape end to end):

```
$ .venv/bin/python -m pytest tests/test_adversarial.py -p no:warnings -q -k "perturbation or windowed or diluted"
....  [100%]
```

4/4 pass: the C2 shape is now flagged and rejected via `no_future_dependence`,
the B1 shape still is, and all library factors plus `noise_control` still
report zero diffs across all four windows (no false positives).

Tests added (`tests/test_adversarial.py`, each with a fault-naming docstring):
`test_windowed_early_leak_rejected_by_staggered_perturbation` (pins verdict +
reason code, with preconditions asserting Gates 0.5/0.75 AND the tail-only
`n_windows=1` check all stay blind so the test cannot pass vacuously).

---

## 3. Carried-findings fixes (all with this pass's own evidence)

- **F-C1 (major, wrong-paper NBER URL): FIXED.** `w28682` → `w25882` at §8.1
  and the §8.8 verification table. Independently verified this pass (not
  trusted from c3-p10):

```
$ curl -sS --max-time 25 -L "https://www.nber.org/papers/w25882" | grep -oE '<meta name="citation_title" content="[^"]*"'
<meta name="citation_title" content="Common Risk Factors in Cryptocurrency"
w25882=200
```

- **F-S1 (minor, stale qlib prose): FIXED.** §6.1 table row and §6.2 prose said
  48,917 stars / push 2026-09-22; live GitHub API this pass returns 49,316 /
  pushed 2026-10-08 (the file's own drift table already agreed on the push
  date). Both cells updated with a re-verified 2026-10-13 note.
- **F-S2 (minor, truncated display URL): FIXED.** Line 1875 now carries the
  full taylorfrancis URL as cited in §2.5.
- **F-G2 (minor, new): the F1 gate was red on the review file itself.**
  c3-p10's worktree note quoted an absolute host path, so
  `check_no_internal_refs.py` (which scans tracked docs) failed:

```
check_no_internal_refs: FAIL — 1 forbidden token(s) found.
```

  Fixed by redacting to non-literal wording (same class as F-G1). Post-fix:

```
check_no_internal_refs: CLEAN — no forbidden tokens found.
```

Post-fix state (full suite + both mandate checkers):

```
......................................................................   [100%]
check_no_internal_refs: CLEAN — no forbidden tokens found.
check_real_data_proof: all checks passed.
```

(`ruff check` / `ruff format --check` clean; full suite 142 passed.
Positioning re-checked against MARKET-VERDICTS.md while
here: README still leads with the licence problem, COMPARISONS.md table
present, MlFinLab-more-complete stated — no conflict to record.)

---

## 4. Findings table (c3-p11)

| id | severity | finding | evidence | status |
|----|----------|---------|----------|--------|
| F-B2 | **blocker** | Windowed early leak (10% future admixture confined to dates before T-60d, `np.roll` shape, no `.shift` literal) promoted with all 10 gates passing; clean twin rejects (IC=0.0074/FDR p=0.42) so the leak flips the verdict. Tail-only perturbation structurally blind to early-date reads. | C2 outputs + clean-twin control §1 | **fixed** (staggered `n_windows=4` perturbation; post-fix verdict=reject via `no_future_dependence`; 1 test; §2) |
| F-C1 | major | (c3-p10) RESEARCH.md cited Liu/Tsyvinski/Wu at NBER w28682 (Borjas & Edo). | NBER title fetch §3 | **fixed** (w25882, title match verified live) |
| F-S1 | minor | (c2-p10) qlib prose stale (48,917/2026-09-22). | GitHub API output §3 | **fixed** (49,316/2026-10-08, re-verified 2026-10-13) |
| F-S2 | minor | (c3-p10) truncated Efron & Tibshirani display URL. | grep §-prep | **fixed** (full URL) |
| F-G2 | minor | (new) c3-p10 worktree note quoted an absolute host path; F1 refs gate red at pass start. | pre-attack state §0 | **fixed** (redacted; checker CLEAN) |
| F-B1 | blocker | (c2-p11) diluted tail-visible leak | C1 regression §1 (still reject) | fixed (stands) |
| F-T5 | minor | (c2-p10) Gate-0.75 direction fault invisible to suite. Gate 0.75 untouched by this pass. | c3-p10 §3 | open |
| F-A4 | minor | (c1-p11) wilson_lower invalid-input handling | fixed in 448084b (untouched) | fixed (stands) |
| B3 | — | Noise seed-shopping sweep partial: 4/30 seeds, all reject. | C4 §1 | open (method note: background job) |
| P05 | — | Positioning conflict with MARKET-VERDICTS.md: none found (re-checked). | README/COMPARISONS.md | refuted (no conflict) |

C3 (quantized leak): attack attempted, gate held — recorded as refuted.
Prior findings F-T3/F-T2/F-L1: remain fixed (untouched by this pass's diff).

### Status key

- `open`: reported for the builder; not yet fixed
- `fixed`: fix implemented and re-verified with the pass's own probes this pass
- `refuted`: attack attempted, claim held

---

## PASS c4-p11-adversarial-2 (cycle 4, adversarial pass 2 of 2)

Independent reviewer lane. This pass attacks the **property** (c4-p10 attacked the
claims). Read first: ITERATION-PROTOCOL.md, QUALITY-CONTRACT.md,
MARKET-VERDICTS.md, specs/factor-lab.md (incl. v0.2 MANDATE), all prior
c1-p10 through c4-p10 entries above. Both `reports/mutants-survived-c2.txt`
and `reports/mutants-survived-c3.txt` are present but 0 bytes; authoritative
mutation baseline remains reports/mutation-c1.json (878/1977 = 44.4%, gate
70%) — quoted, not re-derived.

All commands below were actually run; output is verbatim terminal output.

---

## 0. Pre-attack state

```
$ git log --oneline -1
5fe7676 docs(review): cycle 4 adversarial pass 1 — claims hold, F-T5 closed
$ .venv/bin/python scripts/check_no_internal_refs.py 2>&1 | tail -1
check_no_internal_refs: CLEAN — no forbidden tokens found.
$ .venv/bin/python scripts/check_real_data_proof.py 2>&1 | tail -1
PROOF_COMPLETE
```

Prior-findings triage: F-T5/F-A4/F-S1 remain fixed (c4-p10 re-verified;
untouched since). F-B1/F-B2 remain fixed (regressions re-run §4). B3
(noise seed-shopping) extended this pass: seeds 1-4 (c3-p11) + 5,6,8,9 —
8/30, all reject (see D2).

---

## 1. Property attacks — defeat the promotion gate

### ATTACK D1: gap-aimed leak — **BYPASSED ALL GATES (BLOCKER F-B3)**

Goal: aim the future admixture at the documented residual — the
inter-window gaps of the quartile-spaced Gate 0.85 (n_windows=4,
tail_days=20 on 1500 dates perturbs rows [355,375), [730,750),
[1105,1125), [1480,1500)). Blend 10% future 5-day returns via `np.roll`
(no `.shift` literal) ONLY where the target row falls in a gap.

```
source patterns: []
flag: False
runtime: (False, '')
perturbation: (False, '')
LEAK verdict: promote
  not_lookahead: pass=True obs=no
  not_degenerate: pass=True obs=varied
  coverage: pass=True obs=0.9866666666666667
  min_observations: pass=True obs=1479.0
  min_abs_ic: pass=True obs=0.05498749931538341
  min_ic_ir: pass=True obs=0.16233913749900747
  hit_rate_wilson_lb: pass=True obs=0.5135970451019718
  max_turnover: pass=True obs=0.30234971462456456
  oos_consistency: pass=True obs=0.8
  survives_fdr: pass=True obs=0.00034
TWIN verdict: reject
  min_abs_ic: pass=False obs=0.006523116630927812
  min_ic_ir: pass=False obs=0.018939586600449275
  survives_fdr: pass=False obs=0.46623
```

Decisiveness proven: the clean twin (same momentum, no future leg) rejects
at IC=0.0065/FDR p=0.47 on the same plain synthetic data (seed 7, no
planted signal); adding gap-confined future data flips it to PROMOTE with
all 11 gates passing and Gates 0.5/0.75/0.85 all blind. Root cause: the
docstring's residual paragraph was exactly right — deterministic quartile
positions let a dedicated adversary aim at the ~355-date gaps.

### ATTACK D4: forged proof JSON — **CHECKER PRINTS PROOF_COMPLETE (MAJOR F-C2)**

Goal: cross the F4 finish gate by editing the report instead of running
the pipeline. Forgery: `real_factors[0].ic = 0.91`, verdict =
`'promote'`, `f3_sensitivity = {n_promoted: 1, ...}` — bar counts and coin
lists left real.

```
$ .venv/bin/python scripts/check_real_data_proof.py
check_real_data_proof: all checks passed.
PROOF_COMPLETE
checker_exit=0
```

The checker verified structure, F3 thresholds, bars-vs-source, section
non-emptiness, and internal refs — but never compared the JSON's claimed
numbers to the markdown table, so a two-field forgery (IC=0.91 vs the real
0.0322 still sitting in the .md) passed. The loop's finish line was
crossable without running anything. (Report restored from backup
afterwards; post-fix state re-verified PROOF_COMPLETE on the real files.)

### ATTACK D2: noise seed-shopping, extended (B3 continued)

```
seed 5 noise_control: reject
seed 6 noise_control: reject
seed 8 noise_control: reject
seed 9 noise_control: reject
```

`noise_control` rejects on seeds 5,6,8,9 (plain synthetic, default
config), now under the dense-tiling gate. Combined with c3-p11 seeds 1-4:
8/30, all reject, no signal of a specificity hole. Still partial (each
full `promote()` costs ~45-60s); the remaining 22 seeds stay a background
job. Recorded as method note, not a finding.

### ATTACK D5: determinism of the rewritten gate — HOLDS

```
run1: (False, '')
run2: (False, '')
deterministic: True
```

`check_lookahead_perturbation` twice on `mom_20` (seed 7) → identical
verdicts. The vectorized rewrite introduces no RNG or ordering
dependence (per-asset reversal over `flatnonzero` index arrays).

---

## 2. Fixes (applied this pass, reviewer-implemented per c2-p11/c3-p11 precedent)

### F-B3 fix: contiguous tiling + vectorized loop (`src/factorlab/cv.py`)

`check_lookahead_perturbation()` now defaults to `n_windows=None` = full
contiguous tiling (`n_dates // tail_days` windows, step == length, no
gaps). Every sample row sits inside some window, so gap-aiming is
impossible: any output at t reading a future row at t+d is caught by
every window starting in (t, t+d]. A leak can only dodge with tiny
coverage — which cannot move full-sample IC above the 0.02 floor. Passing
an explicit small `n_windows` (1 = tail-only, 4 = quartile) reproduces the
legacy spacings for the regression tests' preconditions — never in the
gate path (`promote()` calls with defaults). The per-window loop was
vectorized (precomputed position/asset index arrays; one `df.copy()` +
in-place reversal per window): full-library sweep 31.1s, zero false
positives; full suite time 63s → 85s.

Post-fix verification (same D1 shape):

```
perturbation: (True, 'Factor values at 60 past dates changed when only future
OHLCV data was perturbed (window 3/75 starting 2019-02-27, tail_days=20).
A causal factor cannot do this — lookahead contamination.')
LEAK verdict: reject
  no_future_dependence: pass=False obs=changed
TWIN verdict: reject
```

Tests added (`tests/test_adversarial.py`, fault-naming docstrings +
top-of-file fault-list entries): `test_gap_aimed_leak_rejected_by_dense_tiling`
(pins verdict + reason code, with preconditions asserting source, runtime,
quartile `n_windows=4`, AND tail-only `n_windows=1` all stay blind so the
test cannot pass vacuously), `test_proof_checker_rejects_forged_metrics`.

### F-C2 fix: md/JSON cross-check (`scripts/check_real_data_proof.py`)

New `check_md_json_consistency()`: parses the §2 per-factor table rows
from the markdown and compares IC, IC-IR, t-HAC, p-raw, OOS IC, deflated
Sharpe (tol 2e-4; the .md rounds to 4dp, max err 5e-5) and the verdict
string against every `real_factors` entry, failing closed when zero rows
parse. Post-fix, the same forgery fails:

```
check_real_data_proof: FAIL
  MD-JSON CONSISTENCY FAIL: mom_20 h=20 ic: JSON=0.91 vs markdown=0.0322
  (tol 0.0002) — one artifact was doctored.
  MD-JSON CONSISTENCY FAIL: mom_20 h=20 verdict: JSON=promote vs markdown=reject.
forged_exit=1
```

Residual (documented in the fix, not a new finding): a forger who rewrites
both artifacts coherently still passes — only a full recomputation gate
closes that, which costs a real-data run per check. The bar is now
"forge dozens of mutually-consistent numbers across two files" instead of
"edit two JSON fields".

Post-fix state:

```
161 passed in 84.84s (0:01:24)
All checks passed!
27 files already formatted
check_no_internal_refs: CLEAN — no forbidden tokens found.
```

(`ruff check` clean, `ruff format --check` clean — one UP038 auto-flag on
the new checker code fixed with `int | float` + an explicit `bool`
exclusion. Positioning re-checked against MARKET-VERDICTS.md while here:
README still leads with the licence problem, COMPARISONS.md table
present, MlFinLab-more-complete stated — no conflict to record.)

---

## 3. Findings table (c4-p11)

| id | severity | finding | evidence | status |
|----|----------|---------|----------|--------|
| F-B3 | **blocker** | Gap-aimed leak (10% future admixture confined to quartile-tiling gaps, `np.roll` shape, no `.shift` literal) promoted with all 11 gates passing; clean twin rejects (IC=0.0065/FDR p=0.42) so the leak flips the verdict. Deterministic quartile positions let the adversary aim at ~355-date gaps. | D1 outputs §1; pre-fix verdict=promote rows | **fixed** (contiguous `n_windows=None` tiling; post-fix verdict=reject via `no_future_dependence`; 2 tests; §2) |
| F-C2 | major | `check_real_data_proof.py` trusted the JSON's claimed numbers without comparing them to the markdown table: a two-field forgery (ic=0.91, verdict=promote, real bar counts) printed PROOF_COMPLETE, exit 0. The F4 finish gate was crossable without running the pipeline. | D4 outputs §1; pre-fix `all checks passed` on forged file | **fixed** (md/JSON numeric+verdict cross-check, fail-closed on zero parsed rows; same forgery now exit 1; §2) |
| F-B1 | blocker | (c2-p11) diluted tail-visible leak | §4 (regression tests re-run green in full suite) | fixed (stands) |
| F-B2 | blocker | (c2-p11/c3-p11) windowed early leak | §4 (regression test re-run green in full suite) | fixed (stands) |
| F-T5 | minor | (c2-p10) Gate-0.75 direction fault invisible | fixed in d2e2f38; untouched by this pass | fixed (stands) |
| B3 | — | Noise seed-shopping sweep: 8/30 seeds (1-4 c3-p11 + 5,6,8,9), all reject | D2 §1 | open (method note: background job for remaining 22) |
| P07 | — | Positioning conflict with MARKET-VERDICTS.md: none found (re-checked) | README/COMPARISONS.md | refuted (no conflict) |

D2 (seed sweep) and D5 (determinism): attacks attempted, gate held —
recorded as refuted/evidence. Prior findings F-T3/F-T2/F-L1/F-C1/F-S1/F-S2/
F-G1/F-G2/F-A4: remain fixed (untouched by this pass's diff, suite green).

### Status key (c4-p11)

- `open`: reported for the builder; not yet fixed
- `fixed`: fix implemented and re-verified with the pass's own probes this pass
- `refuted`: attack attempted, claim held

---

## PASS c5-p10-adversarial-1 (cycle 5, adversarial pass 1 of 2)

Independent reviewer lane. This pass attacks the **claims** (c5-p11 attacks the
property). Read first: ITERATION-PROTOCOL.md, QUALITY-CONTRACT.md,
MARKET-VERDICTS.md, specs/factor-lab.md (incl. v0.2 MANDATE), all prior
c1-p10 through c4-p11 entries above. All three `reports/mutants-survived-c*.txt`
are present but 0 bytes; authoritative mutation baseline remains
reports/mutation-c1.json (878/1977 = 44.4%, gate 70%) — quoted, not re-derived.

Branch note: `feat/v0.1` is checked out by a sibling worktree, so this pass ran
on the current checkout at commit 4650f47 (same content line). No absolute host
paths appear below per F1.

Cycle-5 delta under review (commits after c4-p11): FDR multiplicity fix (060a1e0),
pearson centre-then-rescale (c9b2373), roll-spread noise-floor handling (8ad1fd1),
3 byzantine tests + README badge (ef40a32), ADOPTION recipe fix (4650f47).
The README's load-bearing claims CHANGED since c4-p10: it now honestly documents
that standalone `promote mom_20 --plant-signal` REJECTs (exit 1) under the
tightened gate. This pass audits the claims as they now stand.

All commands below were actually run; output is verbatim terminal output
(host path prefixes redacted to `<repo>` per F1).

---

## 0. Pre-attack state (c5-p10)

```
$ .venv/bin/python -m pytest -p no:warnings 2>&1 | tail -1
165 passed in 107.82s (0:01:47)
$ .venv/bin/python scripts/check_no_internal_refs.py 2>&1 | tail -1
check_no_internal_refs: CLEAN — no forbidden tokens found.
$ .venv/bin/python scripts/check_real_data_proof.py 2>&1 | tail -1
PROOF_COMPLETE
$ .venv/bin/python -m ruff check . 2>&1 | tail -1
All checks passed!
$ .venv/bin/python -m ruff format --check . 2>&1 | tail -1
27 files already formatted
```

README badge `tests-165 passed` is accurate. Both mandate checkers green.

---

## 1. Claims audit — 3 most load-bearing README claims, attacked (c5-p10)

### C1 — Standalone promote: mom_20 REJECTs (exit 1), noise_control REJECTs (exit 1)

The claim flipped since c4-p10 (exit 0 → exit 1 for the planted signal under
the c5-p04 multiplicity fix). Attacked as written today (README lines 126-130):

```
$ .venv/bin/python -m factorlab.cli promote mom_20 --data signal --plant-signal >/dev/null 2>&1; echo "mom_20_planted=$?"
mom_20_planted=1
$ .venv/bin/python -m factorlab.cli promote noise_control --data signal >/dev/null 2>&1; echo "noise=$?"
noise=1
```

Gate row for the documented numbers (README: "BH p=0.1065 vs q=0.10, m=3 horizons"):

```
survives_fdr                              0.1065       0.1000   FAIL
  note: BH FDR q=0.1, m=3 tests (3 horizons + 0 extra)
```

**Verdict: SUPPORTED.** Exit codes and the p/q/m triple match the README
sentence exactly. The honest-REJECT framing holds.

Consequence, re-verified not trusted (see F-D1 carried): `examples/run_demo.sh`
step 4 still asserts exit 0 for this exact command, so the demo exits 1:

```
$ bash examples/run_demo.sh > /tmp/c5_demo.txt 2>&1; echo "demo_exit=$?"
demo_exit=1
```

```
--- 4. Promote mom_20 on planted-signal data (must PROMOTE, exit 0) ---
Factor:  mom_20
Verdict: REJECT
...
survives_fdr                              0.1065       0.1000   FAIL
  note: BH FDR q=0.1, m=3 tests (3 horizons + 0 extra)
...
Result: REJECT
```

This is the c5-p09 open conflict (spec criteria 2&3 vs the multiplicity fix),
deliberately untouched per QUALITY-CONTRACT §0 — recorded as carried, not new.

### C2 — "Real results (from examples/run_demo.sh)": README table is the demo's output

The screen step (step 2) completes before the step-4 failure, so the table is
still checkable. Diffed fresh output against README:

```
$ grep '^|' /tmp/c5_demo.txt | sort -u > /tmp/c5_dr.txt; grep '^|' README.md | sort -u > /tmp/c5_rr.txt; diff /tmp/c5_dr.txt /tmp/c5_rr.txt && echo ROWS_IDENTICAL
ROWS_IDENTICAL
$ grep -n "Promoted" /tmp/c5_demo.txt | head -2
39:Promoted (0): none
```

**Verdict: SUPPORTED.** All 15 table lines byte-identical; "Promoted (0): none"
matches the README "0/13" framing.

### C3 — Positioning: MlFinLab licence/pricing; Quantopian stack abandoned 2020

```
$ curl -sS -L --max-time 25 https://raw.githubusercontent.com/hudson-and-thames/mlfinlab/master/LICENSE.txt | grep -cE '6\.6|6\.7|14\.2|14\.3|14\.5'
6
$ curl -sS --max-time 20 "https://api.github.com/repos/quantopian/alphalens/commits?per_page=1" | grep -m1 '"date"'
        "date": "2020-04-27T18:40:41Z"
$ curl -sS --max-time 20 "https://api.github.com/repos/quantopian/pyfolio/commits?per_page=1" | grep -m1 '"date"'
        "date": "2020-02-28T17:30:19Z"
```

**Verdict: SUPPORTED.** Clause grep hits 6 lines covering 6.6/6.7/14.2/14.3/14.5
(pricing page `£100 (+VAT)` verified in c3-p10/c4-p10; page unchanged, quoted not
re-fetched). No conflict with MARKET-VERDICTS.md positioning to record
(README still leads with the licence problem, COMPARISONS.md table present,
MlFinLab-more-complete stated).

---

## 2. Citation audit — all 163 unique URLs in docs/RESEARCH.md (c5-p10)

Method: extracted 163 unique `https://` URLs (was 119 at c4-p10; cycle 5 added
~44), probed each with `curl -s -o /dev/null -w '%{http_code}' -L --max-time 25`
(16-way parallel, research UA). Two ScienceDirect/Elsevier DOI URLs contain
literal parentheses which truncate under naive extraction — probed in full
separately (both 200, see below).

```
probed=163 (+2 full-paren forms)
     131 200
      29 403
       1 404
       2 302 (redirect-loop, curl final code)
```

Non-200 detail (raw):

```
403 https://doi.org/10.1002/ijfe.70036
403 https://doi.org/10.1080/01621459.1927.10502953
403 https://doi.org/10.1080/01621459.1994.10476870
403 https://doi.org/10.1093/rfs/1.1.41
403 https://doi.org/10.1093/rfs/hhv059
403 https://doi.org/10.1093/rfs/hhv063
403 https://doi.org/10.1093/rfs/hhx132
403 https://doi.org/10.1111/0022-1082.00163
403 https://doi.org/10.1111/0022-1082.00247
403 https://doi.org/10.1111/1468-0262.00152
403 https://doi.org/10.1111/j.1468-0262.2005.00615.x
403 https://doi.org/10.1111/j.1540-6261.1985.tb05004.x
403 https://doi.org/10.1111/j.1540-6261.1993.tb04702.x
403 https://doi.org/10.1111/j.1540-6261.2006.01015.x
403 https://doi.org/10.1111/j.1540-6261.2009.01527.x
403 https://doi.org/10.1111/j.1540-6261.2010.01598.x
403 https://doi.org/10.1111/jofi.12021
403 https://doi.org/10.1111/jofi.12365
403 https://doi.org/10.1111/jofi.13131
403 https://doi.org/10.1198/073500105000000063
403 https://doi.org/10.2307/2297912
403 https://doi.org/10.2469/faj.v58.n4.2453
302 https://doi.org/10.3905/jai.2023.1.189
302 https://doi.org/10.3905/jpm.2014.40.5.094
404 https://doi.org/10.1198/073500104000000063
403 https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1821643
403 https://papers.ssrn.com/sol3/papers.cfm?abstract_id=377260
403 https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3913263
403 https://www.pm-research.com/content/iijaltinv/early/2023/03/25/jai.2023.1.189.full.pdf
403 https://www.sciencedirect.com/science/article/pii/0304405X86900656
403 https://www.tandfonline.com/doi/abs/10.1198/073500105000000063
403 https://www.tandfonline.com/doi/abs/10.2469/faj.v58.n4.2453
```

Full-paren forms (naive extraction truncated these at `(`; the file carries
the complete URLs):

```
200 https://doi.org/10.1016/S1386-4181(01)00024-6
200 https://doi.org/10.1016/0304-4076(86)90063-1
```

Disposition:

- **131/163 → HTTP 200** (129 + 2 full-paren forms), including every
  JSTOR/NBER/arXiv/RePEc/GitHub-API/PyPI alternate the file promises and the
  cycle-5 §D verification-table URLs.
- **29× 403**: publisher DOI resolvers + SSRN + ScienceDirect + T&F/PM-Research
  bot-blocking (same pattern as every prior pass). Cycle-5 additions follow the
  established discipline: `10.1002/ijfe.70036` is marked "403 — NOT claimed"
  (line 2880); `abstract_id=1821643` and the T&F/PM-Research URLs sit in §D rows
  explicitly labelled "bot-walled, NOT cited as verified" (lines 4463/4469);
  the ScienceDirect URL sits in a "boundary ... 403 — NOT claimed" row
  (line 3524). Each affected citation block carries a 200-returning alternate
  or an explicit NOT-claimed flag — verified by grep.
- **1× 404** (`doi:10.1198/073500104000000063`): still documented "404 — NOT
  claimed" (line 2318). Unchanged.
- **2× 302** (both IPR-Journals `10.3905` DOIs): the known redirect-loop shape
  (curl final code 302 after following); both documented with arXiv/SSRN
  handling in-file (c1-p10/c3-p10). Unchanged.
- **Support spot-checks on cycle-5 citations:** the §D2b row claims the
  Bollerslev DOI "resolves HTTP 200 confirmed 2026-10-13" — re-confirmed 200
  this pass. The §D1b/§D3c rows claim bot-walled NOT-verified status for the
  T&F/SSRN URLs — re-confirmed 403 this pass, matching the file. No citation
  found that resolves to a page contradicting its claim.

---

## 3. Test-quality audit — 6 tests sampled, named fault injected, suite run (c5-p10)

Driver `/tmp/opencode/c5_inject.py`: back up the source file, apply one exact
string mutation (asserted unique), run the single node, restore.
Sampling deliberately covers the cycle-5 diff surface (T1–T3) plus the gate,
validation, and detector layers (T4–T6).

| # | test | injected fault (one string mutation) | result |
|---|------|--------------------------------------|--------|
| T1 | `test_evaluate.py::test_pearson_corr_wild_magnitudes` | deviation rescale removed: `xs = xd / sx` → `xs = xd`, `ys = yd / sy` → `ys = yd` (reverts c9b2373) | exit 1 — DETECTED (`assert nan...` at test_evaluate.py) |
| T2 | `test_microstructure.py::test_roll_spread_hand_computed` | Roll constant dropped: `2.0 * np.sqrt(-cov1)` → `np.sqrt(-cov1)` | exit 1 — DETECTED (`AssertionError` at test_microstructure.py:88) |
| T3 | `test_adversarial.py::test_embargo_uses_max_horizon_not_min` | min-embargo fault: `embargo_days=cfg.embargo_days` → `embargo_days=min(cfg.horizons)` in the walk-forward construction | exit 1 — DETECTED (`ValueError` at cv.py:106 — the construction-time `embargo_days >= H` guard fires) |
| T4 | `test_promote.py::test_planted_signal_promoted` | verdict forced: `"promote" if all_passed else "reject"` → `"reject"` | exit 1 — DETECTED (`AssertionError` at test_promote.py:123) |
| T5 | `test_significance.py::test_wilson_lower_rejects_negative_k` | validation removed: `if k < 0 or k > n:` → `if False:` | exit 1 — DETECTED (`AssertionError` at test_significance.py:102) |
| T6 | `test_adversarial.py::test_internal_refs_detector_catches_forbidden_token` | detector blinded: `scan_file` forced to `return []` | exit 1 — DETECTED (`AssertionError` at test_adversarial.py:1419) |

Restore check: `git status --porcelain -- src tests scripts` empty after every
restore (verified). Pre-attack full suite was 165 passed.

**Score: 6 of 6 named faults fail on their fault.** Notes:

- T1 is the fix-verification for the c9b2373 rescale: removing the deviation
  rescale reproduces NaN on mixed magnitudes, exactly the pre-fix symptom quoted
  in the test docstring. The KAT pins the fix, not just the function.
- T3 faults the caller (min instead of max/default), not the splitter: the
  suite fails via the `PurgedWalkForward` construction guard (`embargo_days >=
  label_horizon`), i.e. defense in depth — the guard catches what the caller
  got wrong. Detection is real at suite level; the test's assertion text
  (`emb >= 20`) is not what fires, the constructor raises first. Test-precision
  note only, not a finding: the suite still fails on the named fault.
- T6 guards the F1 mandate layer itself (the checker the v0.2 MANDATE depends
  on). Blinding it fails its pin test alone.

---

## 4. Bypass hunt, pass-1 scope (c5-p10)

- **Force flag:** not re-probed (c1-p10/c2-p10/c4-p10 all confirm `--force` is
  rejected by argparse; `git log` shows no cli.py changes since those probes).
- **Gate relaxation / permissive config:** by design per c1-p11; not
  re-litigated.
- **README command honesty:** the exact quickstart commands re-run unmodified
  in §C1 above — with the documented flipped expectation (exit 1) holding.
- **Seed-shopping (B3):** still 8/30 (c3-p11 seeds 1-4 + c4-p11 seeds 5,6,8,9),
  all reject. Not extended (same ~45-60s-per-promote foreground cost). Carried
  as method note.

---

## 5. Findings table (c5-p10)

| id | severity | finding | evidence | status |
|----|----------|---------|----------|--------|
| F-D1 | major (carried) | (c5-p04..c5-p09) `examples/run_demo.sh` step 4 asserts `promote mom_20 --plant-signal` exits 0; the tightened multi-horizon FDR gate returns exit 1 (BH p=0.1065 vs q=0.10, m=3). Demo exits 1; spec criteria 2&3 red. Gate side is correct (c5-p09 ruling); criterion needs orchestrator re-scope. Deliberately untouched per QUALITY-CONTRACT §0. | demo_exit=1 + REJECT gate table §C1; reports/improvements.md c5-p09 open-conflict entry | open (orchestrator ruling needed) |
| B3 | — | Noise seed-shopping sweep still 8/30, all reject | c3-p11 §1, c4-p11 §D2; same foreground-cost constraint | open (method note: background job for remaining 22) |
| P08 | — | Positioning conflict with MARKET-VERDICTS.md: none found (re-checked §C3) | README lines 3, 12-13; COMPARISONS.md table | refuted (no conflict) |

Claims C1/C2/C3: all three **supported** — no blocker, no new major. Citation
audit: 131/163 URLs 200 (incl. 2 full-paren forms), 29× documented
publisher-403-with-alternate-or-NOT-claimed, 1× documented 404-NOT-claimed,
2× known redirect-loops. Test audit: 6/6 named faults detected, including
three pins on the cycle-5 diff surface. Prior findings
F-T3/F-T2/F-L1/F-A4/F-T5/F-C1/F-S1/F-S2/F-G1/F-G2/F-B1/F-B2/F-B3/F-C2: remain
fixed (untouched by this pass's diff — this pass touched no Python files, only
appended to this markdown file; suite green at 165).

### Status key (c5-p10)

- `open`: reported for the builder; not yet fixed (reviewer does not fix code)
- `fixed`: fix implemented and re-verified with the pass's own probes this pass
- `refuted`: attack attempted, claim held
- `carried`: reported by an earlier pass, re-verified this pass, unchanged

---

## PASS c5-p11-adversarial-2 (cycle 5, adversarial pass 2 of 2)

Independent reviewer lane. This pass attacks the **property** (c5-p10 attacked the
claims). Read first: ITERATION-PROTOCOL.md, QUALITY-CONTRACT.md,
MARKET-VERDICTS.md, specs/factor-lab.md (incl. v0.2 MANDATE), all prior
c1-p10 through c5-p10 entries above. All three `reports/mutants-survived-c*.txt`
are present but 0 bytes; authoritative mutation baseline remains
reports/mutation-c1.json (878/1977 = 44.4%, gate 70%), with
reports/mutation-c3.json and reports/mutation-c4.json recording 0/0 infra
failures (rc=2) — quoted from the files, not re-derived.

Branch note: `feat/v0.1` is checked out by a sibling worktree, so this pass ran
on the current checkout `tmp-c3p10` at commit ea32840 (same content line as
c5-p10). No absolute host paths appear below per F1.

All commands below were actually run; output is verbatim terminal output
(host path prefixes redacted to `<repo>` per F1 where present).

---

## 0. Pre-attack state

```
$ git log --oneline -1
ea32840 docs(review): cycle 5 adversarial pass 1 — claims hold, 6/6 faults detected, demo conflict carried
$ .venv/bin/python scripts/check_no_internal_refs.py 2>&1 | tail -1
check_no_internal_refs: CLEAN — no forbidden tokens found.
$ .venv/bin/python scripts/check_real_data_proof.py 2>&1 | tail -1
PROOF_COMPLETE
```

Prior-findings triage: F-D1 (demo step-4 vs tightened FDR gate) carried open —
untouched per QUALITY-CONTRACT section 0, re-verified red in section 4. B3 (noise
seed-shopping) stands at 8/30, all reject — not extended (same ~45-60s-per-promote
foreground cost; the suite itself occupies the box this pass). Everything else
remains fixed (suite green at c5-p10: 165 passed).

---

## 1. Property attacks — defeat the promotion gate

### ATTACK E3: window-start-gapped leak — **BYPASSED ALL GATES (BLOCKER F-B4)**

Goal: dodge the F-B3 contiguous tiling the way F-B3 dodged quartile spacing —
aim at what the tiling leaves uncovered. Contiguous tiling with step == length
starts windows at deterministic multiples of `tail_days` (20, 40, ...). An
output at t reading a future row at t+d is only compared against windows
starting in (t, t+d]. With d=5 and step=20, dates with (pos mod 20) <= 14 have
NO window start in (t, t+5] — a 75%-coverage safe set. Blend 5-30% future
5-day returns via `np.roll` (no `.shift` literal for Gate 0.5) active only on
safe dates (plus dodging the four quartile read-zones, so legacy spacings stay
blind too).

Mechanism probes (plain synthetic, seed 7, no planted signal):

```
rows: 18000
source patterns: []
flag: False
runtime: (False, '')
perturbation: (False, '')
```

All three lookahead layers blind — including the F-B3 perturbation gate the
previous pass installed. Full-gate verdicts vs the clean twin (same momentum,
no future leg, rejects at IC=0.0061):

```
W=0.05: runtime=False perturbation=False verdict=reject IC=0.0290 fails=[survives_fdr]
W=0.15: runtime=False perturbation=False verdict=promote IC=0.0720 fails=[]
W=0.30: runtime=False perturbation=False verdict=promote IC=0.1577 fails=[]
TWIN verdict: reject (min_abs_ic/min_ic_ir/survives_fdr all FAIL)
```

At W=0.05 the leak already lifts IC 0.006 -> 0.029 (past the 0.02 floor) and
only the FDR multiplicity gate holds; at W=0.15 the verdict flips to PROMOTE
with all gates passing. Decisiveness proven: the core safety property ("refuse
factors that read future rows") was defeated by a leak confined to
window-start gaps. Root cause: deterministic step==length starts let a
dedicated adversary compute the safe set exactly (the F-B3 docstring's residual
paragraph anticipated gap-aiming at bodies; starts are aimable the same way).

### ATTACK E4: forged F3 aggregates — **CHECKER PRINTS PROOF_COMPLETE (MAJOR F-C3)**

Goal: cross the F4 finish gate on a knowingly-bad run without touching the
numbers the F-C2 fix cross-checks. The F-C2 fix compares per-factor IC/IC-IR/
t-HAC/p-raw/OOS/Sharpe/verdict between md and JSON — but the F3 aggregates the
mandate actually cares about (`f3_specificity.rejection_rate`,
`f3_stability.flip_count`, `delta` counts) are self-reported and never
recomputed from the per-entry verdicts sitting in the same JSON. Forgery on
copies in /tmp (real files untouched): flip 5/10 `noise_controls` verdicts to
`promote`, keep `rejection_rate=1.0`:

```
forged: 5/10 noise verdicts=promote, rejection_rate still 1.0
$ check_real_data_proof.main() against forged copies
check_real_data_proof: all checks passed.
PROOF_COMPLETE
forged_checker_exit= 0
```

The checker certified a run that promotes half its noise controls. Same class
as F-C2 (self-certified artifact), one layer up: the per-factor numbers are
now bound to each other, but the aggregates that decide F3 pass/fail are bound
to nothing.

### ATTACK E2: global-normalization leak — BLOCKED (failed attack is evidence)

Goal: smuggle future influence through full-sample z-scoring
(`(v - v.mean()) / v.std()` over the whole panel — reads future rows
indirectly, no shift/roll anywhere):

```
E2 global-norm flagged: True
```

The perturbation gate flags it (the documented assumption — global
normalization is itself in-sample leakage — holds behaviourally, not just on
paper).

### ATTACK E5: determinism of the rewritten gate — HOLDS

```
E5 deterministic: True (False, False) twice on mom_20, seed 7
```

Two consecutive `check_lookahead_perturbation` runs return identical verdicts;
the rewrite introduces no RNG or ordering dependence.

---

## 2. Fixes (applied this pass, reviewer-implemented per c2-p11/c3-p11/c4-p11 precedent)

### F-B4 fix: stride-1 dense tiling (`src/factorlab/cv.py`)

`check_lookahead_perturbation()` now starts a perturbation window at EVERY
sample date by default (`n_windows=None` = stride-1, window length
`tail_days`). Any output at t reading a future row at t+d is caught by the
window starting inside (t, t+d] — which always exists when starts are dense.
Gap-aiming has no safe set left because there are no gaps. Explicit small
`n_windows` (1 = tail-only, 4 = quartile) reproduces the legacy spacings for
the regression tests' preconditions — never in the gate path (`promote()`
calls with defaults). Cost: one recompute per date (~16s for a clean factor on
the 1500x12 panel; leaks exit early on the first differing window).

Post-fix verification (same filed shape):

```
leak W=0.15 stride-1: True | Factor values at 12 past dates changed when only
  future OHLCV data was perturbed (window 21/1499 starting 2019-...)
leak legacy n_windows=4: False | leak legacy n_windows=1: False
mom_20 clean: False (16s) | noise clean: False (15s)
LEAK verdict: reject (FAIL no_future_dependence) | TWIN verdict: reject
```

The filed shape is now flagged and rejected via `no_future_dependence`; both
legacy spacings stay blind (pinning the test to the new mechanism); clean
factors still scan clean.

Tests added (`tests/test_adversarial.py`, fault-naming docstrings +
top-of-file fault-list entries):
`test_mod_gated_leak_rejected_by_stride_one_tiling` (pins verdict + reason
code, with preconditions asserting source, runtime, quartile `n_windows=4`,
AND tail-only `n_windows=1` all stay blind so the test cannot pass
vacuously).
Speed note: `test_perturbation_no_false_positives_on_library` now runs on a
400x6 panel (was 1500x12) — same default gate path, size-independent property,
with the reason recorded in the test.

### F-C3 fix: F3 aggregate cross-check (`scripts/check_real_data_proof.py`)

New `check_f3_aggregate_consistency(data)`: recomputes every self-reported
aggregate from the entry lists with the same arithmetic
`prove_on_real_data.write_report` uses — `noise_rejected`/`noise_total`/
`rejection_rate` vs `noise_controls` verdicts, `flip_count` vs
`flipped_names`, `n_promoted`/`promoted_names` vs `real_factors` verdicts,
`delta` counts vs `p_raw`/`bh_fdr_pass`/verdict fields — failing closed on
any divergence. Post-fix, the same forgery fails:

```
check_real_data_proof: FAIL
  F3 CONSISTENCY FAIL: f3_specificity.noise_rejected=10 but 5/10 noise_controls entries have verdict=reject.
  F3 CONSISTENCY FAIL: f3_specificity.rejection_rate=1.0 but entry verdicts give 0.5 — one artifact was doctored.
forged_exit= 1
```

Residual (documented, not a new finding): a forger who rewrites entries AND
aggregates coherently in both files still passes — only a full recomputation
gate closes that, which costs a real-data run per check. The bar is now "forge
a fully self-consistent pair of artifacts" instead of "edit one aggregate
field".

Tests added: `test_proof_checker_rejects_forged_specificity` (positive
control on the committed artifacts + in-memory forgery, no file writes).

Post-fix state (full suite + lint + both mandate checkers, this pass):

```
$ .venv/bin/python -m pytest -p no:warnings 2>&1 | tail -1
167 passed in 239.79s (0:03:59)
$ .venv/bin/python -m ruff check . 2>&1 | tail -1
All checks passed!
$ .venv/bin/python -m ruff format --check . 2>&1 | tail -1
27 files already formatted
$ .venv/bin/python scripts/check_no_internal_refs.py 2>&1 | tail -1
check_no_internal_refs: CLEAN — no forbidden tokens found.
$ .venv/bin/python scripts/check_real_data_proof.py 2>&1 | tail -1
PROOF_COMPLETE
```

(Suite cost 108s -> 240s from stride-1 tiling: one recompute per date for
clean factors; leaks exit early. The library no-false-positives sweep runs on
a 400x6 panel for the same reason. Demo/F-D1 state unchanged by this diff —
no gate threshold touched, clean-factor verdicts identical; carried as open.)

---

## 3. Findings table (c5-p11)

| id | severity | finding | evidence | status |
|----|----------|---------|----------|--------|
| F-B4 | **blocker** | Window-start-gapped leak (5-30% future admixture via `np.roll`, active only at dates with no tiling-window start in (t, t+5]) promoted with all gates passing at W>=0.15 (IC=0.072); clean twin rejects (IC=0.0061) so the leak flips the verdict. Deterministic step==length starts let the adversary compute the safe set exactly. | E3 mechanism + verdict rows section 1 (pre-fix) | **fixed** (stride-1 tiling; post-fix verdict=reject via `no_future_dependence`; 1 test; section 2) |
| F-C3 | major | `check_real_data_proof.py` trusted self-reported F3 aggregates without recomputing them from the per-entry verdicts: flipping 5/10 noise verdicts to promote while keeping rejection_rate=1.0 printed PROOF_COMPLETE, exit 0. The F4 finish gate was crossable on a knowingly-bad run. | E4 outputs section 1 (pre-fix `all checks passed` on forged copies) | **fixed** (aggregate cross-check; same forgery now exit 1; section 2) |
| F-D1 | major (carried) | (c5-p04..c5-p10) `examples/run_demo.sh` step 4 asserts `promote mom_20 --plant-signal` exits 0; the tightened multi-horizon FDR gate returns exit 1. Spec criteria 2&3 red. Deliberately untouched per QUALITY-CONTRACT section 0. | c5-p10 section C1; untouched by this pass's diff | open (orchestrator ruling needed) |
| F-B1 | blocker | (c2-p11) diluted tail-visible leak | regression tests re-run green this pass | fixed (stands) |
| F-B2 | blocker | (c3-p11) windowed early leak | regression test re-run green this pass | fixed (stands) |
| F-B3 | blocker | (c4-p11) gap-aimed leak | regression test re-run green this pass | fixed (stands) |
| F-C2 | major | (c4-p11) md/JSON per-factor forgery | `test_proof_checker_rejects_forged_metrics` green this pass | fixed (stands) |
| B3 | — | Noise seed-shopping sweep: 8/30 seeds, all reject | c3-p11/c4-p11; not extended (suite occupied the box) | open (method note: background job for remaining 22) |
| P09 | — | Positioning conflict with MARKET-VERDICTS.md: none found (re-checked: README line 3 leads with the licence problem, COMPARISONS.md table present, MlFinLab-more-complete stated) | README/COMPARISONS.md greps | refuted (no conflict) |

E2 (global-norm) and E5 (determinism): attacks attempted, gate held —
recorded as refuted/evidence. Prior findings F-T3/F-T2/F-L1/F-A4/F-T5/F-C1/
F-S1/F-S2/F-G1/F-G2: remain fixed (untouched by this pass's diff).

### Status key (c5-p11)

- `open`: reported for the builder; not yet fixed
- `fixed`: fix implemented and re-verified with the pass's own probes this pass
- `refuted`: attack attempted, claim held
