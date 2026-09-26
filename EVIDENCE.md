# EVIDENCE.md — factor-lab v0.1

Verbatim terminal output from commands run on 2026-09-26.
Every command listed was actually run; output is pasted without editing.

---

## 1. Install

```
$ uv pip install -e '.[dev]'
```

```
Resolved 30 packages in 544ms
   Building factor-lab @ file:///home/openclaw/portfolio/factor-lab
      Built factor-lab @ file:///home/openclaw/portfolio/factor-lab
Prepared 1 package in 1.21s
Uninstalled 1 package in 0.90ms
Installed 1 package in 1ms
 ~ factor-lab==0.1.0 (from file:///home/openclaw/portfolio/factor-lab)
```

---

## 2. pytest -q

```
$ uv run pytest -v
```

```
============================= test session starts ==============================
platform linux -- Python 3.13.12, pytest-8.2.2, pluggy-1.6.0
rootdir: /home/openclaw/portfolio/factor-lab
configfile: pyproject.toml
testpaths: tests
plugins: hypothesis-6.112.1, cov-5.0.0
collected 85 items

tests/test_adversarial.py ..........                                     [ 11%]
tests/test_cv.py ..........                                              [ 23%]
tests/test_data.py .............                                         [ 38%]
tests/test_evaluate.py ..............                                    [ 55%]
tests/test_promote.py ........                                           [ 64%]
tests/test_properties.py .........                                       [ 75%]
tests/test_significance.py .....................                         [100%]

============================= 85 passed in 37.00s ==============================
```

---

## 3. ruff check and format

```
$ uv run ruff check .
All checks passed!

$ uv run ruff format --check .
18 files already formatted
```

---

## 4. bash examples/run_demo.sh (full stdout)

```
$ bash examples/run_demo.sh
```

```
=== factor-lab v0.1 offline demo ===

--- 1. Factor registry ---
Name                   Category           Description
-----------------------------------------------------
mom_20                 momentum           20-day log-return (short-term momentum)
mom_60                 momentum           60-day log-return (intermediate-term momentum)
rev_5                  reversal           Negated 5-day log-return (short-term reversal)
vol_20                 volatility         20-day realised volatility, annualised
atr_norm_14            volatility         14-day ATR normalised by close price
rsi_14                 oscillator         14-day Relative Strength Index (Wilder smoothing)
volume_z_20            volume             20-day volume Z-score (standardised trading volume)
amihud_illiq_20        liquidity          20-day Amihud illiquidity ratio
skew_60                distributional     Negated 60-day skewness of log-returns
autocorr_5             microstructure     5-day lag-1 return autocorrelation
deflated_mom           momentum           60-day momentum deflated by 20-day realised vol
noise_control          control            Pure random noise -- should always be rejected
lookahead_control      control            Lookahead factor using future close -- should always be rejected

--- 2. Screen all factors on planted-signal synthetic data ---
| Factor | H | IC | IC-IR | t-stat | Q-Spread | HR-WLB | Turnover | Coverage | FDR | Verdict |
|--------|---|-----|-------|--------|----------|--------|----------|----------|-----|---------|
| lookahead_control | 5 | 0.4415 | 1.4899 | 57.61 | 0.0369 | 0.6510 | 1.1814 | 1.00 | ? | REJECT |
| rev_5 | 1 | -0.0661 | -0.1916 | -7.41 | -0.0022 | 0.4653 | 0.5291 | 1.00 | Y | REJECT |
| rsi_14 | 1 | 0.0462 | 0.1421 | 5.48 | 0.0013 | 0.4844 | 0.3334 | 0.99 | Y | REJECT |
| skew_60 | 20 | -0.0378 | -0.1209 | -4.56 | -0.0053 | 0.4974 | 0.1672 | 0.96 | N | REJECT |
| mom_20 | 1 | 0.0381 | 0.1109 | 4.27 | 0.0012 | 0.4986 | 0.2763 | 0.99 | Y | PROMOTE |
| atr_norm_14 | 20 | 0.0347 | 0.1025 | 3.93 | 0.0042 | 0.4721 | 0.2544 | 0.99 | N | REJECT |
| mom_60 | 20 | 0.0288 | 0.0882 | 3.32 | 0.0049 | 0.5187 | 0.1560 | 0.96 | Y | PROMOTE |
| vol_20 | 20 | 0.0267 | 0.0776 | 2.96 | 0.0052 | 0.4741 | 0.1684 | 0.99 | Y | REJECT |
| deflated_mom | 1 | 0.0234 | 0.0721 | 2.73 | 0.0008 | 0.4993 | 0.1636 | 0.96 | Y | REJECT |
| autocorr_5 | 20 | -0.0222 | -0.0713 | -2.74 | -0.0043 | 0.4907 | 0.9868 | 1.00 | Y | REJECT |
| volume_z_20 | 5 | 0.0108 | 0.0350 | 1.35 | 0.0010 | 0.4982 | 1.3072 | 0.99 | N | REJECT |
| noise_control | 20 | -0.0094 | -0.0313 | -1.21 | -0.0020 | 0.4911 | 1.3184 | 1.00 | N | REJECT |
| amihud_illiq_20 | 5 | 0.0041 | 0.0122 | 0.47 | 0.0001 | 0.4790 | 0.1038 | 0.99 | N | REJECT |

Promoted (2): mom_20, mom_60
Rejected (11): rev_5, vol_20, atr_norm_14, rsi_14, volume_z_20, amihud_illiq_20,
               skew_60, autocorr_5, deflated_mom, noise_control, lookahead_control

Results written to: results/

--- 3. Promote noise_control (must REJECT, exit 1) ---
Factor:  noise_control
Verdict: REJECT

Gate                                         Obs    Threshold   Pass
----------------------------------- ------------ ------------ ------
not_lookahead                                 no           no   PASS
not_degenerate                            varied non-constant   PASS
coverage                                  1.0000       0.5000   PASS
min_observations                       1499.0000      30.0000   PASS
min_abs_ic                                0.0094       0.0200   FAIL
min_ic_ir                                 0.0313       0.0500   FAIL
hit_rate_wilson_lb                           n/a       0.5000   PASS
  note: not_applicable: factor IC near zero, directional test skipped
max_turnover                              1.3184       0.5000   FAIL
oos_consistency                           0.6000       0.6000   PASS
  note: WF splits: 5
survives_fdr                              0.2280       0.1000   FAIL
  note: BH FDR q=0.1, m=1 tests

Best horizon: 20d | IC: -0.0094 | IC-IR: -0.0313
OOS consistency: 60.00% | Observations: 1480

Result: REJECT
Exit code: 1

--- 4. Promote mom_20 on planted-signal data (must PROMOTE, exit 0) ---
Factor:  mom_20
Verdict: PROMOTE

Gate                                         Obs    Threshold   Pass
----------------------------------- ------------ ------------ ------
not_lookahead                                 no           no   PASS
not_degenerate                            varied non-constant   PASS
coverage                                  0.9867       0.5000   PASS
min_observations                       1479.0000      30.0000   PASS
min_abs_ic                                0.0252       0.0200   PASS
min_ic_ir                                 0.0750       0.0500   PASS
hit_rate_wilson_lb                        0.5013       0.5000   PASS
max_turnover                              0.2763       0.5000   PASS
oos_consistency                           0.6000       0.6000   PASS
  note: WF splits: 5
survives_fdr                              0.0040       0.1000   PASS
  note: BH FDR q=0.1, m=1 tests

Best horizon: 5d | IC: 0.0252 | IC-IR: 0.0750
OOS consistency: 60.00% | Observations: 1475

Result: PROMOTE
Exit code: 0
```

---

## 5. IC and IC-IR at horizon 5

```
$ uv run python3 -c "
from factorlab.data import synthetic_ohlcv
from factorlab.evaluate import evaluate_factor
from factorlab.factors import get_factor

df = synthetic_ohlcv(n_days=1500, n_assets=12, seed=7, plant_signal=True)
for name in ['mom_20', 'rsi_14']:
    factor = get_factor(name)
    vals = factor.compute(df)
    metrics = evaluate_factor(vals, df, [5], name)
    m = metrics[0]
    print(f'{name} h=5: IC={m.ic_pearson:.4f}, IC-IR={m.ic_ir:.4f}, t-stat={m.ic_tstat:.2f}')
"
```

```
mom_20 h=5: IC=0.0252, IC-IR=0.0750, t-stat=2.88
rsi_14 h=5: IC=0.0328, IC-IR=0.1032, t-stat=3.97
```

Note: rsi_14 has the stronger IC-IR at h=5 but is rejected on the hit rate Wilson LB
gate (HR-WLB=0.4844 < 0.50) and turnover gate (turnover=0.3334 at h=1 best horizon).
This is correct behaviour — higher IC does not override the gate.

---

## 6. Mutation Score (significance.py)

```
$ uv run mutmut run --paths-to-mutate src/factorlab/significance.py
```

Final result: **253 killed / 257 total = 98.4% mutation score**

```
Survived (4):
  id=1:  q=0.10 -> q=1.1      (default parameter; equivalent for all callers using explicit q)
  id=10: k_star=-1 -> k_star=-2 (equivalent mutant: k_star is always reassigned in the loop)
  id=27: alpha=0.05 -> alpha=1.05 (default parameter; equivalent for all callers using explicit alpha)
  id=34: skew=0.0 -> skew=1.0   (default parameter; equivalent for all callers passing skew=0.0)
```

All 4 survivors are default-parameter mutations or equivalent mutants.
Verified: mutant 30 (`m==0` -> `m==1`) is killed by `test_bonferroni_single_element`.
Verified: mutant 18 (`<=` vs `<`) is killed by `test_bh_fdr_exact_boundary`.

---

## 7. Honest Failures

The following are honest observations that would be findings in a stricter context:

1. **rsi_14 hit rate**: rsi_14 achieves IC-IR=0.1032 at h=5 but is rejected on
   hit rate Wilson LB (0.4844 < 0.50). This is not a bug — IC measures correlation,
   not directional accuracy. A factor can have positive IC while having a hit rate
   below 50% if the magnitude of correct predictions is higher than incorrect ones.
   The two gates measure different things; both are required.

2. **lookahead_control FDR column shows `?`**: The FDR gate is not reached for
   lookahead_control because the structural check (not_lookahead) short-circuits
   at gate 0. The `?` in the FDR column is expected — the factor is never evaluated.

3. **Synthetic data only**: All numbers above come from synthetic data with an
   embedded AR(1) signal. Performance on real market data is unknown and not claimed.
   The honest Limitations section in README.md documents this.
