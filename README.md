# factorproof

The overfitting controls that quant research actually needs — without a £100/month licence.

The package is `factor-lab`; the CLI is `factor-lab` (repo name `factorproof`).

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![CI](https://github.com/AnnasMazhar/factorproof/actions/workflows/ci.yml/badge.svg)
![Ruff](https://img.shields.io/badge/ruff-clean-brightgreen)
![Licence](https://img.shields.io/badge/licence-MIT-green)

**For quant researchers** who want purged walk-forward CV, combinatorial purged CV (CPCV),
Benjamini-Hochberg FDR correction, Newey-West HAC t-stats, and a promotion gate that says
no — under MIT, offline, no subscription. MlFinLab does more; it costs £100+VAT/month per
user. This does less and costs nothing.

```bash
# Install (no network at test time)
uv venv && uv pip install -e '.[dev]'

# Screen 13 factors, reject the noise
factor-lab screen --data signal --horizons 1,5,20

# Promote a real signal (exit 0) or reject noise (exit 1)
factor-lab promote mom_20 --data signal
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
factor-lab promote mom_20 --data signal
factor-lab promote noise_control --data signal

# List all available factors
factor-lab list

# Full pipeline demo
bash examples/run_demo.sh
```

`--plant-signal` is accepted as a flag but has no effect when `--data=signal` (signal
mode always embeds the momentum signal). It applies to `--data synthetic` only.

## Real results (from `factor-lab screen --data signal --horizons 1,5,20`)

Run on synthetic data with an embedded AR(1) momentum signal (rho=0.15).
13 factors screened at horizons 1, 5, 20 days with Newey-West HAC t-stats.

| Factor | H | IC | IC-IR | t-stat | Q-Spread | HR-WLB | Turnover | Coverage | FDR | Verdict |
|--------|---|-----|-------|--------|----------|--------|----------|----------|-----|---------|
| lookahead_control | 5 | 0.4545 | 1.9920 | 99.40 | 0.0382 | 0.6592 | 1.1982 | 1.00 | ? | REJECT |
| rev_5 | 1 | -0.0738 | -0.2623 | -11.72 | -0.0025 | 0.4572 | 0.5227 | 1.00 | Y | REJECT |
| rsi_14 | 1 | 0.0361 | 0.1506 | 6.71 | 0.0012 | 0.4856 | 0.3263 | 0.99 | Y | REJECT |
| mom_20 | 1 | 0.0347 | 0.1268 | 5.64 | 0.0010 | 0.5124 | 0.2702 | 0.99 | Y | PROMOTE |
| atr_norm_14 | 20 | -0.0360 | -0.1165 | -1.49 | -0.0069 | 0.4805 | 0.2190 | 0.99 | Y | REJECT |
| mom_60 | 20 | 0.0316 | 0.1139 | 1.39 | 0.0070 | 0.5171 | 0.1600 | 0.97 | Y | PROMOTE |
| vol_20 | 20 | -0.0307 | -0.0984 | -1.21 | -0.0046 | 0.4819 | 0.1446 | 0.99 | N | REJECT |
| deflated_mom | 1 | 0.0199 | 0.0829 | 3.65 | 0.0007 | 0.5105 | 0.1679 | 0.97 | Y | REJECT |
| skew_60 | 20 | 0.0171 | 0.0701 | 0.92 | 0.0025 | 0.5076 | 0.1625 | 0.97 | N | REJECT |
| volume_z_20 | 1 | 0.0077 | 0.0332 | 1.48 | 0.0003 | 0.4983 | 1.3095 | 0.99 | N | REJECT |
| noise_control | 1 | 0.0075 | 0.0331 | 1.48 | 0.0001 | 0.4937 | 1.3287 | 1.00 | N | REJECT |
| autocorr_5 | 5 | -0.0063 | -0.0258 | -0.87 | -0.0009 | 0.4937 | 0.9851 | 1.00 | N | REJECT |
| amihud_illiq_20 | 20 | 0.0046 | 0.0153 | 0.19 | -0.0033 | 0.4819 | 0.0874 | 0.99 | N | REJECT |

Promoted (2): mom_20, mom_60
Rejected (11): rev_5, vol_20, atr_norm_14, rsi_14, volume_z_20, amihud_illiq_20,
               skew_60, autocorr_5, deflated_mom, noise_control, lookahead_control

**Why does the screen promote 2/13?** HAC t-stats at H=20 are ~3x lower than naive t-stats
due to overlapping-label autocorrelation. Combined with BH FDR (q=0.10, 13 factors in family),
only factors with strong signals at short horizons survive. `mom_20` and `mom_60` both pass all
10 gates on this AR(1) synthetic dataset (rho=0.15). On real daily crypto bars, the gate
correctly promotes 0/13 — see `reports/real-data-proof.md`.

## The gates explained

**Why Wilson lower bound on hit rate?**
Raw hit rate has high variance for small n. Requiring the 95% Wilson lower bound
above 50% means the signal must be statistically significant even under the
pessimistic end of the confidence interval. A factor with 55% hit rate on 30
observations has Wilson LB = 37% — the gate would correctly reject it.

**Why Benjamini-Hochberg FDR correction?**
If you test 13 factors, you expect 5% * 13 = 0.65 spurious discoveries at alpha=5%.
FDR correction controls the expected fraction of false discoveries. BH q=0.10
with 13 tests means at most ~1.3 promoted factors are expected to be noise.

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

The pipeline is designed to reject the author's favourite factors. That is the point:
IC gates, Wilson lower bounds on hit rate, Benjamini-Hochberg FDR correction across the
factor family, deflated Sharpe for the number of trials actually run, and purged
walk-forward cross-validation with an embargo. Every part of the decision is inspectable
and every number is reproducible from this repository alone, under MIT.

## Limitations

- **Real-data report committed.** `reports/real-data-proof.md` is present in the repository.
  It was generated by `scripts/prove_on_real_data.py` against a private multi-year daily OHLCV
  dataset (daily crypto bars, 2021→present, 14 coins).  Zero factors are promoted on real data
  at daily granularity — the gate correctly rejects them all.  No real-market performance is
  claimed; the report documents what happens when the gate is run honestly on live price history.
- **Single asset class.** The evaluation framework is crypto-daily-centric; no
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
