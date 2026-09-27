# docs/IMPLEMENTATION-NOTES.md — factor-lab v0.1

Traceability map: each core algorithm traced from reference equation to
implementation code to test.

---

## 1. Information Coefficient (IC) and Newey-West HAC t-stat

**Reference:** Grinold & Kahn (2000) ch. 10.
    IC_t = corr(f_t, r_{t+h})  (cross-sectional, per date)
    mean_IC = mean over dates
    IC_IR = mean_IC / std_IC

**HAC t-stat reference:** Newey & West (1987) Econometrica 55(3):703-708.
With forward-return horizon H, per-date IC values share H−1 overlapping days,
inducing autocorrelation that inflates the naive t-stat by ~sqrt(H). The HAC SE:
    V_HAC = gamma_0 + 2 * sum_{l=1}^{L} (1 - l/(L+1)) * gamma_l
    SE_HAC = sqrt(V_HAC / T)
    t_HAC = mean_IC / SE_HAC
where gamma_l is the lag-l autocovariance, L = max_lags = H-1 (Bartlett kernel).

The naive t-stat is: t_naive = IC_IR * sqrt(T), exposed as ic_tstat_naive
(diagnostic only — not used in the promotion gate).

**Implementation:**
    `src/factorlab/evaluate.py:information_coefficient` — returns 5-tuple including HAC t-stat
    `src/factorlab/evaluate.py:_newey_west_se` — implements Bartlett kernel HAC SE
    `src/factorlab/evaluate.py:block_bootstrap_ic_ci` — block bootstrap CI for IC mean

**Tests:**
    `tests/test_evaluate.py:test_ic_pearson_known_answer`
    `tests/test_evaluate.py:test_ic_spearman_known_answer`
    `tests/test_evaluate.py:test_hac_vs_naive_tstat_at_horizon_1` (max_lags=0 → no correction)
    `tests/test_evaluate.py:test_hac_tstat_reduced_by_overlap` (AR(1) series: HAC SE >= naive)
    `tests/test_evaluate.py:test_noise_control_naive_inflated_hac_not_at_h20` (H=20 ratio >= 2x)
    `tests/test_evaluate.py:test_block_bootstrap_ic_ci_contains_mean`
    `tests/test_properties.py:test_pearson_corr_symmetry`
    `tests/test_properties.py:test_pearson_corr_self_correlation`
    `tests/test_properties.py:test_rankdata_sum`

---

## 2. Wilson Lower Bound

**Reference:** Wilson (1927) JASA 22(158):209-212, equation (1).
    lb = (p_hat + z^2/(2n) - z*sqrt(p_hat*(1-p_hat)/n + z^2/(4n^2))) /
         (1 + z^2/n)
where p_hat=k/n, z=1.96 (95% CI).

**Implementation:**
    `src/factorlab/significance.py:wilson_lower`
    `src/factorlab/evaluate.py:hit_rate_metrics` (calls the formula inline for hit rate)

**Tests (KAT — hand computed):**
    `tests/test_significance.py:test_wilson_lower_hand_computed`
    Manual derivation for k=55, n=100:
        p_hat = 0.55
        z^2 = 3.8416
        term = sqrt(0.002475 + 0.000096) = 0.050705
        numerator = 0.55 + 0.019208 - 1.96*0.050705 = 0.469826
        denominator = 1.038416
        lb = 0.452...   (expected: ~0.4524)
    `tests/test_properties.py:test_wilson_lower_monotone_in_successes`
    `tests/test_properties.py:test_wilson_lower_bounded`

---

## 3. Benjamini-Hochberg FDR

**Reference:** Benjamini & Hochberg (1995) JRSS-B 57(1):289-300.
    Algorithm from p.291:
    1. Order m p-values p_(1) <= ... <= p_(m)
    2. k* = max{i : p_(i) <= (i/m)*q}
    3. Reject H_(1), ..., H_(k*)

**Implementation:**
    `src/factorlab/significance.py:benjamini_hochberg`

**Tests (KAT — textbook example):**
    `tests/test_significance.py:test_bh_fdr_hand_computed`
    Using m=6, q=0.05, p-values=[0.210, 0.001, 0.039, 0.008, 0.450, 0.041]:
        Sorted: [0.001, 0.008, 0.039, 0.041, 0.210, 0.450]
        Thresholds: [0.00833, 0.01667, 0.025, 0.03333, 0.04167, 0.05]
        k* = 2 (0.001 and 0.008 both pass)
    `tests/test_significance.py:test_bh_fdr_exact_boundary`
    `tests/test_properties.py:test_bh_fdr_subset_monotone`

---

## 4. Deflated Sharpe Ratio

**Reference:** Bailey & Lopez de Prado (2014) JPM 40(5):94-107, equations 5-6, 11.
    SR* = (1 - gamma_EM) * z(1 - 1/n) + gamma_EM * z(1 - 1/(n*e))
    DSR = Phi( (SR - SR*) * sqrt(T-1) / sqrt(1 - skew*SR + (kurt-1)/4 * SR^2) )
where gamma_EM = 0.5772156649 (Euler-Mascheroni), Phi = normal CDF.

**Implementation:**
    `src/factorlab/significance.py:deflated_sharpe_ratio`
    `src/factorlab/significance.py:_norm_cdf` (Abramowitz & Stegun 26.2.17)
    `src/factorlab/significance.py:_norm_ppf` (A&S 26.2.22)

**Tests:**
    `tests/test_significance.py:test_deflated_sharpe_decreases_with_n_trials`
    `tests/test_significance.py:test_deflated_sharpe_single_trial`
    `tests/test_significance.py:test_deflated_sharpe_negative_sr`
    `tests/test_properties.py:test_deflated_sharpe_in_unit_interval`

---

## 5. Purged Walk-Forward Cross-Validation

**Reference:** Lopez de Prado (2018) "Advances in Financial Machine Learning" ch. 7.

Purge logic:
    Training sample at date t is purged if:
        t + label_horizon >= first_test_date
    (equivalently: label window overlaps test window)

    Embargo: further remove `embargo_days` rows at the end of the training set
    (gap between train end and test start >= embargo_days).

ASCII timeline (from docs/DESIGN.md):
    |------- train ------|  purge  | embargo |--- test ---|
    t_start           t_purge_cutoff           t_test_start

**Implementation:**
    `src/factorlab/cv.py:PurgedWalkForward.split`

**Enforcement:** `embargo_days >= label_horizon` is enforced at `__init__` time
(raises `ValueError`). A smaller embargo allows the label window at the train/test
boundary to overlap the test window, defeating the purge.

**Tests (structural):**
    `tests/test_cv.py:test_purge_no_label_overlap` — asserts no train date has
        label window reaching into the test set
    `tests/test_cv.py:test_no_train_test_date_overlap` — asserts empty intersection
    `tests/test_cv.py:test_embargo_removes_gap` — asserts gap >= embargo_days
    `tests/test_cv.py:test_correct_number_of_splits`
    `tests/test_cv.py:test_split_chronological_order`
    `tests/test_cv.py:test_embargo_less_than_horizon_raises` — enforcement test
    `tests/test_cv.py:test_embargo_equal_to_horizon_is_valid` — boundary case

---

## 5b. Combinatorial Purged CV (CPCV)

**Reference:** López de Prado (2018) "Advances in Financial Machine Learning"
ISBN 9781119482086, Chapter 12.

CPCV partitions data into n_groups groups and tests each C(n_groups, k_test)
combination of k_test groups. This produces more OOS paths than walk-forward CV.

**Implementation:**
    `src/factorlab/cv.py:CPurgedCV`

**Tests:**
    `tests/test_cv.py:test_cpcv_generates_correct_number_of_splits` — C(n,k) count
    `tests/test_cv.py:test_cpcv_no_train_test_overlap` — no date in both sets
    `tests/test_cv.py:test_cpcv_embargo_less_than_horizon_raises` — enforcement

---

## 6. ATR (Average True Range)

**Reference:** Wilder (1978) ISBN 0894590278.
    TR = max(H - L, |H - prev_C|, |L - prev_C|)
    ATR_14 = mean(TR over 14 periods)
    ATR_norm = ATR / close

**Implementation:**
    `src/factorlab/factors/library.py:Atr14Norm.compute`

**Tests:**
    `tests/test_adversarial.py:test_constant_price_series_no_crash` — verifies
        ATR does not return inf for zero-range candles

---

## 7. RSI (Relative Strength Index)

**Reference:** Wilder (1978) ISBN 0894590278.
    delta = close.diff()
    avg_gain = mean(positive deltas over 14 periods)
    avg_loss = mean(|negative deltas| over 14 periods)
    RS = avg_gain / avg_loss
    RSI = 100 - 100/(1 + RS)

**Implementation:**
    `src/factorlab/factors/library.py:Rsi14.compute`

---

## 8. Amihud Illiquidity

**Reference:** Amihud (2002) JFM 5(1):31-56, equation (1).
    ILLIQ_t = (1/D) * sum_d( |R_d| / V_d )
where |R_d| is absolute daily log-return, V_d is dollar volume (close * volume).

**Implementation:**
    `src/factorlab/factors/library.py:Amihud20.compute`
    Scaled by 1e6 to bring to readable magnitude.

---

## 9. Forward Returns (no-lookahead)

**Contract:** Feature at time t predicts target at t+h.
    fwd_ret_{t,h} = log(close_{t+h} / close_t)

The forward return is computed as `close.shift(-h)` — shift backward in time by h
steps so that fwd_ret at date t is the log-return from t to t+h.

**Lookahead guard:**
    `src/factorlab/data.py:assert_no_lookahead` — raises if max feature date >=
    min target date.

    `src/factorlab/factors/library.py:LookaheadControl` — uses `close.shift(-1)`
    (next period's close), flagged with `uses_future_data=True`.
    `src/factorlab/cv.py:check_lookahead` — checks this flag before any computation.
    The gate rejects any factor with this flag set.

**Tests:**
    `tests/test_cv.py:test_lookahead_factor_flagged`
    `tests/test_cv.py:test_clean_factor_not_flagged`
    `tests/test_data.py:test_assert_no_lookahead_raises_on_overlap`
    `tests/test_data.py:test_assert_no_lookahead_passes_clean`
    `tests/test_evaluate.py:test_forward_returns_no_lookahead`
    `tests/test_promote.py:test_lookahead_control_rejected_structurally`

---

## 10. Coverage Penalty

Any factor with < 50% non-NaN coverage is rejected by the gate
(`not_degenerate` + `coverage` gates in `src/factorlab/promote.py:promote`).

**Implementation:**
    `src/factorlab/evaluate.py:coverage_fraction`

**Tests:**
    `tests/test_evaluate.py:test_coverage_fraction_known` — KAT, 3/5 non-NaN = 0.6
    `tests/test_evaluate.py:test_coverage_all_nan`
    `tests/test_adversarial.py:test_all_nan_factor_rejected`
    `tests/test_adversarial.py:test_constant_factor_rejected`
    `tests/test_promote.py:test_low_coverage_factor_rejected`
    `tests/test_properties.py:test_coverage_fraction_in_unit_interval`

---

## 11. Report Stability

The markdown report must be timestamp-free to be diff-friendly.
`src/factorlab/report.py:to_markdown` contains no `datetime.now()` calls
or wall-clock references.

**Test:**
    `tests/test_adversarial.py:test_report_markdown_timestamp_free`
    Checks for YYYY-MM-DD and HH:MM:SS patterns in the output.

---

## 12. Synthetic Data Planted Signal

The `plant_signal=True` flag in `synthetic_ohlcv` adds AR(1) autocorrelation
with rho=0.15 to returns:
    persistent_t = rho * persistent_{t-1} + log_return_t

This embeds a genuine short-term momentum signal. With rho=0.15, n=1500 days,
12 assets, the expected IC at horizon 5 is ~0.025 (observed: 0.0252 in test run).

**Tests:**
    `tests/test_promote.py:test_planted_signal_promoted` — verifies mom_20 passes all
        gates on the planted-signal dataset at horizon 5

**Reference:** Jegadeesh & Titman (1993) motivate the AR(1) structure in returns.
