# factor-lab

The overfitting controls that quant research actually needs — without a £100/month licence.

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Tests](https://img.shields.io/badge/tests-96%20passed-brightgreen)
![Ruff](https://img.shields.io/badge/ruff-clean-brightgreen)
![Licence](https://img.shields.io/badge/licence-MIT-green)

**For quant researchers** who want purged walk-forward CV, Benjamini-Hochberg FDR
correction, Newey-West HAC t-stats, and a promotion gate that says no — under MIT,
offline, no subscription. MlFinLab does more; it costs £100+VAT/month per user.
This does less and costs nothing.

```bash
# Install (no network at test time)
uv venv && uv pip install -e '.[dev]'

# Screen 13 factors, reject the noise
factor-lab screen --data signal --horizons 1,5,20

# Promote a real signal (exit 0) or reject noise (exit 1)
factor-lab promote mom_20 --data signal --plant-signal
factor-lab promote noise_control --data signal
```

## What problem this solves

Most published factors are noise. A 2020 meta-study counted over 400 factor
anomalies in the academic literature; the majority do not replicate out of
sample once corrected for data mining. The typical factor research workflow
makes this worse: the researcher tests dozens of ideas, picks the one that worked,
and publishes it as if it were the only thing ever tested.

factor-lab exists to refuse promotion to weak signals. It builds the statistical
scaffolding that most factor research skips: purged cross-validation to prevent
lookahead, Newey-West HAC correction for overlapping labels, Benjamini-Hochberg
FDR correction across the full factor family tested, Wilson lower bounds on hit
rate, and walk-forward OOS consistency checks. A factor either survives all gates
or it does not ship.

The reference implementation of these techniques (MlFinLab) is not open source:
the licence prohibits redistribution, derivatives, and any competing product, and
your improvements become the licensor's property. The free Quantopian stack
(alphalens, pyfolio, empyrical) has none of these controls and was last maintained
in 2020. See [COMPARISONS.md](COMPARISONS.md) for the full table.

## Design

```
synthetic_ohlcv / load_ohlcv_csv
        |
        v
   Factors (13)           -- compute() -> pd.Series with (date, asset) index
        |
        v
PurgedWalkForward CV      -- leakage-safe train/test splits
        |
        v
evaluate_factor            -- IC, IC-IR, HAC t-stat, quantile spread, hit rate
        |
        v
significance              -- Wilson LB, BH FDR, Deflated Sharpe, Bootstrap CI
        |
        v
promote()                  -- 10 gates; all must pass
        |
      PROMOTE / REJECT
        |
        v
report.to_markdown / to_html
```

## Install

```bash
uv venv && uv pip install -e '.[dev]'
```

Requires Python 3.11+. No network access in tests.

## 60-second quickstart

```bash
# Screen all 13 factors on synthetic data with a planted momentum signal
factor-lab screen --data signal --horizons 1,5,20 --out results/

# Promote or reject a single factor
factor-lab promote mom_20 --data signal --plant-signal
factor-lab promote noise_control --data signal

# List all available factors
factor-lab list

# Full pipeline demo
bash examples/run_demo.sh
```

## Real results (from examples/run_demo.sh)

Run on synthetic data with an embedded AR(1) momentum signal (rho=0.08).
13 factors screened at horizons 1, 5, 20 days with Newey-West HAC t-stats.

| Factor | H | IC | IC-IR | t-stat | Q-Spread | HR-WLB | Turnover | Coverage | FDR | Verdict |
|--------|---|-----|-------|--------|----------|--------|----------|----------|-----|---------|
| lookahead_control | 5 | 0.4415 | 1.4899 | 65.06 | 0.0369 | 0.6510 | 1.1814 | 1.00 | ? | REJECT |
| rev_5 | 1 | -0.0661 | -0.1916 | -7.41 | -0.0022 | 0.4653 | 0.5291 | 1.00 | Y | REJECT |
| rsi_14 | 1 | 0.0462 | 0.1421 | 5.48 | 0.0013 | 0.4844 | 0.3334 | 0.99 | Y | REJECT |
| skew_60 | 20 | -0.0378 | -0.1209 | -1.36 | -0.0053 | 0.4974 | 0.1672 | 0.96 | N | REJECT |
| mom_20 | 1 | 0.0381 | 0.1109 | 4.27 | 0.0012 | 0.4986 | 0.2763 | 0.99 | N | REJECT |
| atr_norm_14 | 20 | 0.0347 | 0.1025 | 1.18 | 0.0042 | 0.4721 | 0.2544 | 0.99 | N | REJECT |
| mom_60 | 20 | 0.0288 | 0.0882 | 0.99 | 0.0049 | 0.5187 | 0.1560 | 0.96 | N | REJECT |
| vol_20 | 20 | 0.0267 | 0.0776 | 0.82 | 0.0052 | 0.4741 | 0.1684 | 0.99 | N | REJECT |
| deflated_mom | 1 | 0.0234 | 0.0721 | 2.73 | 0.0008 | 0.4993 | 0.1636 | 0.96 | N | REJECT |
| autocorr_5 | 20 | -0.0222 | -0.0713 | -1.81 | -0.0043 | 0.4907 | 0.9868 | 1.00 | Y | REJECT |
| volume_z_20 | 5 | 0.0108 | 0.0350 | 1.40 | 0.0010 | 0.4982 | 1.3072 | 0.99 | N | REJECT |
| noise_control | 20 | -0.0094 | -0.0313 | -1.21 | -0.0020 | 0.4911 | 1.3184 | 1.00 | N | REJECT |
| amihud_illiq_20 | 5 | 0.0041 | 0.0122 | 0.25 | 0.0001 | 0.4790 | 0.1038 | 0.99 | N | REJECT |

Promoted in screen: 0/13 (all factors rejected under HAC + BH FDR across 13 factors).
Promoted (standalone): `mom_20` promotes in isolation (IC=0.025, p=0.107 at q=0.15 with m=1).

**Why does the screen reject everything?** HAC t-stats at H=20 are ~3x lower than naive t-stats
due to overlapping-label autocorrelation. Combined with FDR over 13 factors (BH threshold for
rank 6 = 0.069), no factor survives. This is correct behaviour — this AR(1) signal (rho=0.08)
is genuinely weak when measured honestly. `factor-lab promote mom_20 --data signal` demonstrates
the pipeline CAN promote a real signal when evaluated in isolation (exit 0; see step 4 of demo).

## The gates explained

**Why Wilson lower bound on hit rate?**
Raw hit rate has high variance for small n. Requiring the 95% Wilson lower bound
above 50% means the signal must be statistically significant even under the
pessimistic end of the confidence interval. A factor with 55% hit rate on 30
observations has Wilson LB = 37% — the gate would correctly reject it.

**Why Benjamini-Hochberg FDR correction?**
If you test 13 factors, you expect 5% * 13 = 0.65 spurious discoveries at alpha=5%.
FDR correction controls the expected fraction of false discoveries. BH q=0.15
with 13 tests means at most ~2 promoted factors are expected to be noise.

**Why Newey-West HAC t-stats?**
With a forward-return horizon H > 1, consecutive per-date IC values share H-1
overlapping days. This autocorrelation inflates the naive t-stat by roughly sqrt(H)
(up to ~4.5x at H=20). The HAC standard error (Newey & West 1987, max_lags = H-1)
corrects for this. The pipeline uses HAC t-stats exclusively in the promotion gate;
the naive t-stat is exposed as `ic_tstat_naive` for diagnostic comparison only.

**Why purged walk-forward CV?**
Standard K-fold can use 2025 data to predict 2020 returns — structural lookahead.
Walk-forward preserves temporal ordering. The purge zone removes training samples
whose label window overlaps the test window (not just the feature window). The
embargo adds a gap of at least H days after each test window to prevent the target
distribution leaking through adjacency.

## What this proves

This is the same evidence discipline applied to a live 13-factor trading system
(Olympus V3). The production system uses IC gates, Wilson LB on hit rate, FDR
correction, and walk-forward CV to decide which factors to deploy. factor-lab
makes the same machinery available standalone, under MIT, inspectable.

The pipeline is designed to reject the author's own favourite factors. That is
the point.

## Limitations

- **Synthetic data only in this demo.** No real-market results are shown. Performance
  on real data is unknown and not claimed.
- **Single asset class.** The evaluation framework is equity-centric; no
  cross-asset correlation is modelled.
- **No transaction cost model in v0.1.** The turnover gate penalises high turnover
  but does not compute net-of-cost returns.
- **Survivorship not modelled.** Synthetic assets do not go bankrupt or delist.
- **Deflated Sharpe is not in the promotion gate.** It is computed and tested but
  is not wired into `promote()` by default. See `COMPARISONS.md`.
- **Factor independence assumed for FDR.** In practice, momentum factors share
  data; the effective number of independent tests is less than 13. The BH
  correction is therefore conservative (over-rejects), not anti-conservative.
- **Lookahead detection is opt-in.** The `uses_future_data` flag prevents known
  structural lookahead; it does not catch subtle contamination in custom factors.
  See `docs/ADVERSARIAL-REVIEW.md` finding M01.
- **MlFinLab is more complete.** It ships triple-barrier labelling, meta-labelling,
  PBO, haircut Sharpe, and an entire financial-ML ecosystem. If you can pay for a
  commercial licence, it is the broader tool. See `COMPARISONS.md`.

## Roadmap

- v0.2: real-data CSV workflow, transaction cost model, factor combination
- v0.3: cross-asset extension, group-adjusted FDR (Storey 2002)
- v0.4: HTML dashboard with interactive quantile plots
