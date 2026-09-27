# Real-Data Proof — factor-lab promotion gate

_Lane: `factorproof-realdata`, branch `proof/realdata`. Every number below is pasted
from a run of a committed script against the real dataset; commands and commit SHAs
are stated so each block can be reproduced verbatim._

## 0. Provenance

- **Claim under test:** the 10-gate promotion pipeline, run on real daily crypto bars,
  (a) promotes nothing it should refuse, (b) refuses known noise, (c) does not change
  verdicts under purge/embargo ablation, (d) generalises to unseen windows, and
  (e) survives adversarial pressure and mutation testing.
- **Dataset:** 14 coins (AAVE, ADA, ARB, ATOM, BTC, DOGE, ETH, FIL, HBAR, INJ, RENDER,
  SOL, TON, XRP), 21,128 daily bars, 2021-04-29 → 2026-09-27, 60.29 MB
  (read-only `prices.sqlite`, referenced by repo-root symlink; path never written
  into any tracked file).
- **Commits (this lane, oldest → newest):**

```
$ git log --oneline -3
d62cff9 chore: record proof, leakage and unseen-split run outputs
a0847fb feat: add leakage, unseen-split and adversarial attack evidence scripts
068c9ee fix: pass splitter to walk-forward and emit raw per-factor table
```

- **Environment:** Python 3.13, `uv` venv, pytest 107 passed, `ruff check` /
  `ruff format --check` clean, `scripts/check_no_internal_refs.py` CLEAN
  (verified after each commit in this doc).

---

## 1. Deliverable 1 — full pipeline on real data

```
$ python scripts/prove_on_real_data.py
```

Raw stdout (complete):

```
Loading data from prices.sqlite ...
Dataset: 14 coins, 21,128 bars, 2021-04-29 to 2026-09-27, 60.29 MB
Running factor evaluation (this may take a few minutes) ...

=== PER-FACTOR RESULTS (real data, n stated for every number) ===
factor              h  n_obs       IC    ICIR    tHAC    p_raw  OOS_IC nSp    nTe     DSR  BH verdict
lookahead_control   5   1973   0.4176  1.1760  62.772   0.0000  0.4163   5  17838  0.0000   Y reject
amihud_illiq_20    20   1938  -0.0536 -0.1369  -1.754   0.0794 -0.0564   5  17838  0.0000   N reject
atr_norm_14        20   1944  -0.0503 -0.1290  -1.738   0.0821 -0.0524   5  17838  0.0000   N reject
vol_20             20   1938  -0.0450 -0.1136  -1.502   0.1330 -0.0401   5  17838  0.0000   N reject
deflated_mom       20   1898   0.0333  0.0923   1.220   0.2226  0.0455   5  17838  0.0000   N reject
skew_60            20   1898   0.0294  0.0885   1.223   0.2212  0.0383   5  17838  0.0000   N reject
mom_20             20   1938   0.0327  0.0873   1.272   0.2035  0.0415   5  17838  0.0000   N reject
mom_60             20   1898   0.0333  0.0839   1.089   0.2763  0.0348   5  17838  0.0000   N reject
rev_5               1   1972   0.0329  0.0764   3.393   0.0007  0.0261   5  17838  0.0000   Y reject
rsi_14             20   1944   0.0210  0.0584   0.914   0.3605  0.0370   5  17838  0.0000   N reject
volume_z_20        20   1939   0.0170  0.0477   1.439   0.1503  0.0177   5  17838  0.0000   N reject
noise_control       1   1977  -0.0122 -0.0379  -1.687   0.0916 -0.0120   5  17838  0.0000   N reject
autocorr_5         20   1953   0.0037  0.0103   0.306   0.7593 -0.0102   5  17838  0.0000   N reject

(n_obs = cross-sectional dates with factor+label; OOS_IC = purged walk-forward mean test IC over nSp splits, nTe = test (date,asset) rows; DSR = deflated Sharpe probability, inputs n_obs x n_trials=13; BH = Benjamini-Hochberg q=0.15 across m=13 family p-values)

=== SEEDED NOISE CONTROLS (promote() verdict) ===
noise_0        h= 5 n=  1973 tHAC= -2.375 p=  0.0176 BH=N reject
noise_1        h= 5 n=  1973 tHAC= -0.907 p=  0.3645 BH=N reject
noise_2        h= 5 n=  1973 tHAC= -1.283 p=  0.1996 BH=N reject
noise_3        h= 5 n=  1973 tHAC= -1.017 p=  0.3084 BH=N reject
noise_4        h= 5 n=  1973 tHAC= -1.873 p=  0.0611 BH=N reject
noise_5        h= 5 n=  1973 tHAC=  0.297 p=  0.7667 BH=N reject
noise_6        h= 5 n=  1973 tHAC=  0.677 p=  0.4986 BH=N reject
noise_7        h=20 n=  1958 tHAC= -1.714 p=  0.0865 BH=N reject
noise_8        h= 1 n=  1977 tHAC= -1.437 p=  0.1506 BH=N reject
noise_9        h=20 n=  1958 tHAC= -1.794 p=  0.0729 BH=N reject

stability flips on promoted set: 0 []
promoted: 0/13
Wrote reports/real-data-proof.md
Wrote reports/real-data-proof.json

--- Summary ---
Promoted: 0/13
Noise rejection rate: 10/10 (100.0%) — target >=90%
Stability flips: 0 — target 0

reports/real-data-proof.md written.
reports/real-data-proof.json written.
```

CI validation of the generated artifact:

```
$ python scripts/check_real_data_proof.py
check_real_data_proof: all checks passed.
PROOF_COMPLETE
```

**Reading of the table:** two factors pass FDR (BH=Y) — `rev_5` (p=0.0007, refused on
turnover 0.6135 > 0.5) and `lookahead_control` (a planted-leakage control, refused by
the structural `uses_future_data` gate; its IC=0.4176 is exactly the trap the gate must
spring). Every other factor fails at least one statistical gate. Note the two horizon
selection rules in play: this table selects each factor's horizon by |IC-IR| for
display; `promote()` selects by |t-HAC| among horizons passing the hit-rate floor.
Binding gates per factor under `promote()`'s own selection are printed by the leakage
experiment in §2.

**Bug fixed in this lane (068c9ee):** `evaluate_walk_forward` takes the splitter, not a
materialised split list. Earlier runs passed a list, the resulting `AttributeError`
was swallowed, and OOS_IC printed `nan` for every factor. The table above is from the
fixed script; OOS_IC is populated (nSp=5, nTe=17,838 for every factor).

---

## 2. Deliverable 2 — leakage / ablation experiment

Design (four arms over the same 13 registry factors + 2 controls, each a full
`promote()` pass on the same panel):

| arm | what it changes |
|---|---|
| `correct` | shipped pipeline (purged CV + HAC t + BH q=0.15) |
| `no_purge_embargo` | subclass bypassing purge/embargo validation; train = all dates strictly before the test window |
| `shuffled_labels` | per-asset time-permuted `close` (labels destroyed), factor values frozen from the real panel |
| `naive_t` | HAC SE replaced by i.i.d. SE (`_newey_west_se` patched → naive t) |

```
$ python scripts/leakage_experiment.py --arms all
```

Raw stdout (complete):

```
Dataset: 14 coins, 21,128 bars, 2021-04-29 to 2026-09-27

=== ARM: correct ===
mom_20             reject   survives_fdr=0.2034 (thr 0.15)
mom_60             reject   min_abs_ic=0.0015 (thr 0.02); min_ic_ir=0.0035 (thr 0.05); survives_fdr=0.8775 (thr 0.15)
rev_5              reject   max_turnover=0.6135 (thr 0.5)
vol_20             reject   hit_rate_wilson_lb=0.4796 (thr 0.5)
atr_norm_14        reject   hit_rate_wilson_lb=0.4796 (thr 0.5)
rsi_14             reject   min_abs_ic=0.0064 (thr 0.02); min_ic_ir=0.0174 (thr 0.05); survives_fdr=0.6477 (thr 0.15)
volume_z_20        reject   min_abs_ic=0.0172 (thr 0.02); min_ic_ir=0.0463 (thr 0.05); max_turnover=1.1153 (thr 0.5)
amihud_illiq_20    reject   hit_rate_wilson_lb=0.4796 (thr 0.5)
skew_60            reject   min_abs_ic=0.0169 (thr 0.02); min_ic_ir=0.0485 (thr 0.05); hit_rate_wilson_lb=0.4927 (thr 0.5)
autocorr_5         reject   min_abs_ic=0.0037 (thr 0.02); min_ic_ir=0.0103 (thr 0.05); max_turnover=0.9902 (thr 0.5); survives_fdr=0.7589 (thr 0.15)
deflated_mom       reject   min_abs_ic=0.0021 (thr 0.02); min_ic_ir=0.0056 (thr 0.05); oos_consistency=0.4 (thr 0.6); survives_fdr=0.8075 (thr 0.15)
noise_control      reject   min_abs_ic=0.0045 (thr 0.02); min_ic_ir=0.0139 (thr 0.05); max_turnover=1.3199 (thr 0.5); survives_fdr=0.5376 (thr 0.15)
lookahead_control  reject   not_lookahead=yes (thr no)

=== ARM: no_purge_embargo ===
mom_20             reject   survives_fdr=0.2034 (thr 0.15)
mom_60             reject   min_abs_ic=0.0015 (thr 0.02); min_ic_ir=0.0035 (thr 0.05); survives_fdr=0.8775 (thr 0.15)
rev_5              reject   max_turnover=0.6135 (thr 0.5)
vol_20             reject   hit_rate_wilson_lb=0.4796 (thr 0.5)
atr_norm_14        reject   hit_rate_wilson_lb=0.4796 (thr 0.5)
rsi_14             reject   min_abs_ic=0.0064 (thr 0.02); min_ic_ir=0.0174 (thr 0.05); survives_fdr=0.6477 (thr 0.15)
volume_z_20        reject   min_abs_ic=0.0172 (thr 0.02); min_ic_ir=0.0463 (thr 0.05); max_turnover=1.1153 (thr 0.5)
amihud_illiq_20    reject   hit_rate_wilson_lb=0.4796 (thr 0.5)
skew_60            reject   min_abs_ic=0.0169 (thr 0.02); min_ic_ir=0.0485 (thr 0.05); hit_rate_wilson_lb=0.4927 (thr 0.5)
autocorr_5         reject   min_abs_ic=0.0037 (thr 0.02); min_ic_ir=0.0103 (thr 0.05); max_turnover=0.9902 (thr 0.5); survives_fdr=0.7589 (thr 0.15)
deflated_mom       reject   min_abs_ic=0.0021 (thr 0.02); min_ic_ir=0.0056 (thr 0.05); oos_consistency=0.4 (thr 0.6); survives_fdr=0.8075 (thr 0.15)
noise_control      reject   min_abs_ic=0.0045 (thr 0.02); min_ic_ir=0.0139 (thr 0.05); max_turnover=1.3199 (thr 0.5); survives_fdr=0.5376 (thr 0.15)
lookahead_control  reject   not_lookahead=yes (thr no)

=== ARM: shuffled_labels ===
mom_20             reject   min_abs_ic=0.0065 (thr 0.02); min_ic_ir=0.0202 (thr 0.05); oos_consistency=0.4 (thr 0.6); survives_fdr=0.3551 (thr 0.15)
mom_60             reject   min_abs_ic=0.0049 (thr 0.02); min_ic_ir=0.0144 (thr 0.05); survives_fdr=0.5267 (thr 0.15)
rev_5              reject   min_abs_ic=0.0086 (thr 0.02); min_ic_ir=0.0259 (thr 0.05); max_turnover=0.6135 (thr 0.5); survives_fdr=0.2507 (thr 0.15)
vol_20             reject   min_abs_ic=0.004 (thr 0.02); min_ic_ir=0.0125 (thr 0.05); oos_consistency=0.4 (thr 0.6); survives_fdr=0.5553 (thr 0.15)
atr_norm_14        reject   min_abs_ic=0.0028 (thr 0.02); min_ic_ir=0.0088 (thr 0.05); survives_fdr=0.6897 (thr 0.15)
rsi_14             reject   min_abs_ic=0.0049 (thr 0.02); min_ic_ir=0.0156 (thr 0.05); survives_fdr=0.4881 (thr 0.15)
volume_z_20        reject   min_abs_ic=0.0062 (thr 0.02); min_ic_ir=0.0192 (thr 0.05); max_turnover=1.1153 (thr 0.5); survives_fdr=0.4008 (thr 0.15)
amihud_illiq_20    reject   min_abs_ic=0.0031 (thr 0.02); min_ic_ir=0.0089 (thr 0.05); survives_fdr=0.6729 (thr 0.15)
skew_60            reject   min_abs_ic=0.0018 (thr 0.02); min_ic_ir=0.0057 (thr 0.05); oos_consistency=0.4 (thr 0.6); survives_fdr=0.804 (thr 0.15)
autocorr_5         reject   min_abs_ic=0.0068 (thr 0.02); min_ic_ir=0.0208 (thr 0.05); max_turnover=0.9902 (thr 0.5); survives_fdr=0.3559 (thr 0.15)
deflated_mom       reject   min_abs_ic=0.0038 (thr 0.02); min_ic_ir=0.0118 (thr 0.05); survives_fdr=0.6015 (thr 0.15)
noise_control      reject   min_abs_ic=0.0048 (thr 0.02); min_ic_ir=0.0148 (thr 0.05); max_turnover=1.3199 (thr 0.5); oos_consistency=0.4 (thr 0.6); survives_fdr=0.5105 (thr 0.15)
lookahead_control  reject   not_lookahead=yes (thr no)

=== ARM: naive_t ===
mom_20             promote  -
mom_60             reject   min_abs_ic=0.0015 (thr 0.02); min_ic_ir=0.0035 (thr 0.05); survives_fdr=0.8775 (thr 0.15)
rev_5              reject   max_turnover=0.6135 (thr 0.5)
vol_20             reject   hit_rate_wilson_lb=0.4289 (thr 0.5)
atr_norm_14        reject   hit_rate_wilson_lb=0.4279 (thr 0.5)
rsi_14             reject   min_abs_ic=0.0064 (thr 0.02); min_ic_ir=0.0174 (thr 0.05); survives_fdr=0.4415 (thr 0.15)
volume_z_20        reject   min_abs_ic=0.017 (thr 0.02); min_ic_ir=0.0477 (thr 0.05); max_turnover=1.1153 (thr 0.5)
amihud_illiq_20    reject   hit_rate_wilson_lb=0.4292 (thr 0.5)
skew_60            reject   hit_rate_wilson_lb=0.4881 (thr 0.5)
autocorr_5         reject   min_abs_ic=0.0037 (thr 0.02); min_ic_ir=0.0103 (thr 0.05); max_turnover=0.9902 (thr 0.5); survives_fdr=0.6475 (thr 0.15)
deflated_mom       reject   min_abs_ic=0.0021 (thr 0.02); min_ic_ir=0.0056 (thr 0.05); oos_consistency=0.4 (thr 0.6); survives_fdr=0.8075 (thr 0.15)
noise_control      reject   min_abs_ic=0.0045 (thr 0.02); min_ic_ir=0.0139 (thr 0.05); max_turnover=1.3199 (thr 0.5); survives_fdr=0.5379 (thr 0.15)
lookahead_control  reject   not_lookahead=yes (thr no)

=== VERDICT MATRIX ===
factor                       correct  no_purge_embargo   shuffled_labels           naive_t
mom_20                        reject            reject            reject           PROMOTE
mom_60                        reject            reject            reject            reject
rev_5                         reject            reject            reject            reject
vol_20                        reject            reject            reject            reject
atr_norm_14                   reject            reject            reject            reject
rsi_14                        reject            reject            reject            reject
volume_z_20                   reject            reject            reject            reject
amihud_illiq_20               reject            reject            reject            reject
skew_60                       reject            reject            reject            reject
autocorr_5                    reject            reject            reject            reject
deflated_mom                  reject            reject            reject            reject
noise_control                 reject            reject            reject            reject
lookahead_control             reject            reject            reject            reject

=== FLIPS (promoted under ablation, refused by correct pipeline) ===
no_purge_embargo: none
shuffled_labels: none
naive_t: mom_20
flip_present: True

Wrote reports/leakage-experiment.json
```

**Findings:**

1. **Purge/embargo ablation changes nothing** — the `no_purge_embargo` arm is
   byte-identical to `correct` for all 13 factors (same verdicts, same observed
   values, same binding gates). This is not a coincidence: `evaluate_walk_forward`
   computes metrics only on `test_idx`; `train_idx` never enters any statistic
   (factors are deterministic transforms of price history strictly before the test
   window; labels are computed inside the window). The purge/embargo machinery is
   correct but inert on this pipeline. Reported as-is per the spec's
   "controls change nothing" clause.
2. **HAC is load-bearing** — with the HAC correction removed, `mom_20` flips to
   PROMOTE. Its naive t ≈ IC-IR × √n ≈ 0.0873 × √1938 ≈ 3.85 → p ≈ 10⁻⁴, which
   clears FDR even at m=13; under Newey-West with max_lags = h−1 the same evidence
   yields t=1.27, p=0.2035, refused. Overlapping h=20 labels inflate the naive
   t-stat by roughly 3× — exactly what HAC is for. The correct pipeline refuses;
   the ablated one does not.
3. **Shuffled labels are refused** — destroying the return series leaves every
   factor rejected (negative control holds; no promotion from pure chance alignment
   with fabricated labels in this run).

---

## 3. Deliverable 3 — unseen-split outcome check

Design: for each of 5 purged walk-forward splits, run the full gate on the TRAIN
window only, then measure what happened in the NEXT window (first 4 splits never
seen before; split 4's test window is the last year of data). Outcomes:

- `GOOD_PROMOTION` — promoted, test IC keeps sign and |IC| ≥ 0.02
- `FALSE_PROMOTION` — promoted, test window contradicts the claim
- `MISSED_SIGNAL` — refused, test window shows sign-consistent |IC| ≥ 0.02
- `CORRECT_REFUSAL` — refused, test window does not vindicate it
- `N/A_STRUCTURAL` — rejected before statistics (lookahead control)

```
$ python scripts/unseen_split_check.py --n-splits 5
```

Raw stdout (complete):

```
Dataset: 14 coins, 21,128 bars, 2021-04-29 to 2026-09-27

=== SPLIT BOUNDARIES (purged walk-forward, embargo=20d, horizon=20d) ===
 k train window                   n test window                   n purged embo
 0 2021-04-29..2022-02-12       290 2022-03-24..2023-02-15      329     19   20
 1 2021-04-29..2023-01-07       619 2023-02-16..2024-01-10      329     19   20
 2 2021-04-29..2023-12-02       948 2024-01-11..2024-12-04      329     19   20
 3 2021-04-29..2024-10-26      1277 2024-12-05..2025-10-29      329     19   20
 4 2021-04-29..2025-09-20      1606 2025-10-30..2026-09-27      333     19   20

=== PER-SPLIT OUTCOMES ===
 k factor             train     h   IC_tr   IC_te  n_te outcome
 0 mom_20             reject   20  0.0010  0.0655   309 MISSED_SIGNAL
 0 mom_60             reject   20  0.0708 -0.0778   309 CORRECT_REFUSAL
 0 rev_5              reject    5  0.0850 -0.0425   324 CORRECT_REFUSAL
 0 vol_20             reject    1 -0.0518 -0.0478   328 MISSED_SIGNAL
 0 atr_norm_14        reject    1 -0.0301 -0.0394   328 MISSED_SIGNAL
 0 rsi_14             reject   20 -0.0084  0.0424   309 CORRECT_REFUSAL
 0 volume_z_20        reject    5 -0.0381  0.0108   324 CORRECT_REFUSAL
 0 amihud_illiq_20    reject    1 -0.0390 -0.0067   328 CORRECT_REFUSAL
 0 skew_60            reject    5  0.0421 -0.0005   324 CORRECT_REFUSAL
 0 autocorr_5         reject   20  0.0233  0.0302   309 MISSED_SIGNAL
 0 deflated_mom       reject   20  0.0550 -0.0386   309 CORRECT_REFUSAL
 0 noise_control      reject   20 -0.0096  0.0194   309 CORRECT_REFUSAL
 0 lookahead_control  reject    -       -       -     - N/A_STRUCTURAL
 1 mom_20             reject    5 -0.0077 -0.0299   324 MISSED_SIGNAL
 1 mom_60             reject   20  0.0052  0.1182   309 MISSED_SIGNAL
 1 rev_5              reject    1  0.0570  0.0195   328 CORRECT_REFUSAL
 1 vol_20             reject    1 -0.0557  0.0004   328 CORRECT_REFUSAL
 1 atr_norm_14        reject    1 -0.0399 -0.0002   328 CORRECT_REFUSAL
 1 rsi_14             reject   20 -0.0073  0.0020   309 CORRECT_REFUSAL
 1 volume_z_20        reject    5 -0.0281 -0.0022   324 CORRECT_REFUSAL
 1 amihud_illiq_20    reject    1 -0.0386 -0.0204   328 MISSED_SIGNAL
 1 skew_60            reject    5  0.0204  0.0192   324 CORRECT_REFUSAL
 1 autocorr_5         reject   20  0.0213 -0.0067   309 CORRECT_REFUSAL
 1 deflated_mom       reject   20  0.0124  0.1459   309 MISSED_SIGNAL
 1 noise_control      reject   20 -0.0057 -0.0106   309 CORRECT_REFUSAL
 1 lookahead_control  reject    -       -       -     - N/A_STRUCTURAL
 2 mom_20             reject   20  0.0074  0.0810   309 MISSED_SIGNAL
 2 mom_60             reject   20  0.0054  0.1348   309 MISSED_SIGNAL
 2 rev_5              reject    1  0.0496  0.0394   328 MISSED_SIGNAL
 2 vol_20             reject    1 -0.0386 -0.0250   328 MISSED_SIGNAL
 2 atr_norm_14        reject    5 -0.0097  0.0046   324 CORRECT_REFUSAL
 2 rsi_14             reject    5 -0.0098  0.0136   324 CORRECT_REFUSAL
 2 volume_z_20        reject    5 -0.0105 -0.0378   324 MISSED_SIGNAL
 2 amihud_illiq_20    reject    5 -0.0056 -0.0879   324 MISSED_SIGNAL
 2 skew_60            reject    5  0.0194  0.0134   324 CORRECT_REFUSAL
 2 autocorr_5         reject   20  0.0244 -0.0522   309 CORRECT_REFUSAL
 2 deflated_mom       reject    5 -0.0025  0.0666   324 CORRECT_REFUSAL
 2 noise_control      reject    5 -0.0069 -0.0174   324 CORRECT_REFUSAL
 2 lookahead_control  reject    -       -       -     - N/A_STRUCTURAL
 3 mom_20             reject   20  0.0181  0.1108   309 MISSED_SIGNAL
 3 mom_60             reject    1 -0.0030 -0.0101   328 CORRECT_REFUSAL
 3 rev_5              reject    1  0.0439  0.0359   328 MISSED_SIGNAL
 3 vol_20             reject    1 -0.0355 -0.0617   328 MISSED_SIGNAL
 3 atr_norm_14        reject    5 -0.0068 -0.1139   324 MISSED_SIGNAL
 3 rsi_14             reject    5 -0.0075  0.0421   324 CORRECT_REFUSAL
 3 volume_z_20        reject    5 -0.0239  0.0204   324 CORRECT_REFUSAL
 3 amihud_illiq_20    reject    1 -0.0346 -0.0440   328 MISSED_SIGNAL
 3 skew_60            reject   20  0.0360 -0.0363   309 CORRECT_REFUSAL
 3 autocorr_5         reject   20  0.0099 -0.0295   309 CORRECT_REFUSAL
 3 deflated_mom       reject    1 -0.0033  0.0065   328 CORRECT_REFUSAL
 3 noise_control      reject    1 -0.0089 -0.0122   328 CORRECT_REFUSAL
 3 lookahead_control  reject    -       -       -     - N/A_STRUCTURAL
 4 mom_20             promote  20  0.0426 -0.0620   313 FALSE_PROMOTION
 4 mom_60             reject    1 -0.0042  0.0037   332 CORRECT_REFUSAL
 4 rev_5              reject    1  0.0413 -0.0057   332 CORRECT_REFUSAL
 4 vol_20             reject    1 -0.0360 -0.0535   332 MISSED_SIGNAL
 4 atr_norm_14        reject    1 -0.0316 -0.0760   332 MISSED_SIGNAL
 4 rsi_14             reject    1 -0.0081  0.0144   332 CORRECT_REFUSAL
 4 volume_z_20        reject    5 -0.0106 -0.0001   328 CORRECT_REFUSAL
 4 amihud_illiq_20    reject    1 -0.0345 -0.0026   332 CORRECT_REFUSAL
 4 skew_60            reject    1  0.0085  0.0602   332 MISSED_SIGNAL
 4 autocorr_5         reject    1 -0.0046  0.0216   332 CORRECT_REFUSAL
 4 deflated_mom       reject    1 -0.0016 -0.0084   332 CORRECT_REFUSAL
 4 noise_control      reject   20  0.0068  0.0244   313 MISSED_SIGNAL
 4 lookahead_control  reject    -       -       -     - N/A_STRUCTURAL

=== COUNTS ===
splits: 5 | factors: 13 | decisions: 60 (+5 structural)
FALSE_PROMOTION: 1
MISSED_SIGNAL: 23
CORRECT_REFUSAL: 36
N/A_STRUCTURAL: 5
promoted decisions: 1

Wrote reports/unseen-split.json
```

**Findings:**

- The gate promoted exactly **once** across 60 walk-forward decisions — `mom_20` on
  split 4's train window (2021-04-29 → 2025-09-20, IC=0.0426) — and the following
  never-seen window (2025-10-30 → 2026-09-27) moved the opposite way
  (IC=−0.0620): **1 FALSE_PROMOTION out of 1 promotion**.
- 36 CORRECT_REFUSAL / 60 decisions. 23 MISSED_SIGNAL — the gate errs heavily
  toward refusal (by design: 0.02 floor + HAC + FDR), and momentum-family factors
  in particular showed sign-consistent |IC| ≥ 0.02 in test windows the full-sample
  run refuses (e.g. `mom_20` test ICs of 0.0655 / 0.0810 / 0.1108 across splits
  0/2/3).
- Honest reading: full-sample conservatism (§1: 0/13) does **not** imply the
  per-decision error rate is low; with one promotion observed, its observed false
  rate is 1/1. Small-n caveat applies — this is 1 promotion, not a rate estimate.

---

## 4. Deliverable 4 — adversarial attacks + mutation testing

See `docs/ADVERSARIAL_REVIEW.md` (attack pass appended this lane) and
`reports/mutation-realdata.json` (scoped mutmut run over
`cv.py`/`significance.py`/`promote.py`). Raw attack output is embedded there.
Machine-readable: `reports/adversarial-attacks.json`.

---

## 5. Verdict

**Proven (on this dataset, this commit):**

1. Full pipeline promotes 0/13 registry factors; refuses 10/10 seeded noise
   controls; 0 stability flips (CI: `PROOF_COMPLETE`).
2. Purge/embargo ablation is verdict-inert (identical output) — the controls are
   correct but never binding; HAC is the binding overlap control (removing it
   promotes `mom_20`).
3. Shuffled labels: 0 promotions (negative control holds).
4. Unseen-window outcomes are recorded honestly: 36 correct refusals,
   23 misses, 1 false promotion of 1 promotion.

**Headline numbers:** 0/13 promoted · 10/10 noise rejected · 1 ablation flip
(`mom_20` under naive-t) · 1 FALSE_PROMOTION / 1 promoted decision ·
see `docs/ADVERSARIAL_REVIEW.md` for the adversarial false-positive rate.

**Not proven:** (a) low per-attempt false-positive rate under an adaptive
adversary (§3's 1/1 and the seed-scan result in the adversarial review bound
this directly); (b) that purge/embargo protects *this* pipeline — inert here
because evaluation is test-window-only (it would bind a fit-on-train pipeline);
(c) sensitivity — no registry factor genuinely predicts daily crypto returns on
this panel, so the gate's power (ability to promote a real signal) is only
demonstrated on planted synthetic signals, not on real alpha; (d) generalisation
beyond these 14 coins / daily bars / 2021-2026 window.

---

## 6. Reproduce

```bash
ln -sf <path-to>/prices.sqlite prices.sqlite   # gitignored; never committed
python scripts/prove_on_real_data.py           # §1, writes reports/real-data-proof.*
python scripts/leakage_experiment.py --arms all  # §2, writes reports/leakage-experiment.json
python scripts/unseen_split_check.py --n-splits 5 # §3, writes reports/unseen-split.json
python scripts/adversarial_attacks.py --seeds 100 # §4, writes reports/adversarial-attacks.json
python scripts/check_real_data_proof.py        # CI gate → PROOF_COMPLETE
python scripts/check_no_internal_refs.py       # no host paths / tokens in any tracked file
pytest -q && ruff check . && ruff format --check .
```

## 7. Limitations

- Single dataset, single granularity (daily), 14 coins; no cross-market validation.
- DSR column uses IC-IR as a Sharpe proxy with n_trials=13 — reported as computed;
  it is a diagnostic, not a trading-Sharpe claim.
- Two horizon-selection rules coexist (display table: |IC-IR|; `promote()`:
  |t-HAC| among hit-rate-passing horizons); binding gates quoted in §2 come from
  `promote()` itself.
- `unseen_split_check` computes realised test IC within the test window only
  (last `horizon` dates carry NaN labels and drop out; n_te stated per row).
