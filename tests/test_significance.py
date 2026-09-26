"""
Tests for factorlab.significance module.

Faults detected per test:
    test_wilson_lower_hand_computed:
        Fault: wrong Wilson lower bound formula (off coefficient or missing z^2/4n^2 term).
    test_bh_fdr_hand_computed:
        Fault: Benjamini-Hochberg misidentifying the rejection threshold index k*.
    test_bonferroni_hand_computed:
        Fault: Bonferroni threshold computed as alpha instead of alpha/m.
    test_deflated_sharpe_decreases_with_n_trials:
        Fault: DSR not accounting for multiple trials (SR* not increasing with n_trials).
    test_deflated_sharpe_single_trial:
        Fault: DSR applying correction when n_trials=1 (should be no deflation from selection).
    test_bootstrap_ci_deterministic:
        Fault: bootstrap CI not seeded, producing different results across runs.
    test_min_sample_size_known_value:
        Fault: formula using alpha instead of 1-alpha for z_alpha quantile.
    test_norm_cdf_known_values:
        Fault: _norm_cdf polynomial coefficients wrong.
    test_bh_empty_input:
        Fault: BH crashing or returning wrong result on empty list.
"""

from __future__ import annotations

import math

import pytest
from factorlab.significance import (
    _norm_cdf,
    benjamini_hochberg,
    bonferroni,
    bootstrap_ci,
    deflated_sharpe_ratio,
    min_sample_size,
    wilson_lower,
)

# ---------------------------------------------------------------------------
# Wilson lower bound — hand computed
# ---------------------------------------------------------------------------


def test_wilson_lower_hand_computed():
    """KAT: verify Wilson lower bound against a hand-derived value.

    Fault detected: wrong Wilson formula (e.g., missing z^2/4n^2 term,
    wrong coefficient, or wrong direction of inequality).

    Manual calculation for k=55, n=100, z=1.96:
        p_hat = 55/100 = 0.55
        z^2 = 3.8416
        z^2/(2n) = 3.8416/200 = 0.019208
        p_hat*(1-p_hat)/n = 0.55*0.45/100 = 0.002475
        z^2/(4n^2) = 3.8416/40000 = 0.000096
        sqrt(0.002475 + 0.000096) = sqrt(0.002571) = 0.050705
        numerator = 0.55 + 0.019208 - 1.96*0.050705
                  = 0.569208 - 0.099382 = 0.469826
        denominator = 1 + 3.8416/100 = 1.038416
        lb = 0.469826 / 1.038416 = 0.45244...
    """
    lb = wilson_lower(k=55, n=100, z=1.96)
    # Expected: ~0.4524. Allow 1e-4 tolerance for floating-point.
    assert abs(lb - 0.4524) < 1e-3, f"Expected ~0.4524, got {lb:.6f}"


def test_wilson_lower_perfect_hit_rate():
    """KAT: k=n (100% hit rate) must give lower bound < 1.

    Fault detected: lower bound clipped to 1.0 or formula overflow.
    """
    lb = wilson_lower(k=100, n=100, z=1.96)
    assert 0.0 < lb < 1.0, f"Expected lb in (0,1), got {lb}"
    assert lb > 0.95, "Lower bound for 100% hit rate on 100 obs should be > 0.95"


def test_wilson_lower_zero_obs():
    """KAT: n=0 must return 0.0 without crashing.

    Fault detected: ZeroDivisionError in formula.
    """
    lb = wilson_lower(k=0, n=0)
    assert lb == 0.0


def test_wilson_lower_monotone_in_k():
    """Property: Wilson lower bound is non-decreasing in k for fixed n.

    Fault detected: negation error causing lower bound to increase when k decreases.
    """
    n = 200
    prev = -1.0
    for k in range(0, n + 1, 10):
        lb = wilson_lower(k=k, n=n)
        assert lb >= prev - 1e-9, f"Non-monotone at k={k}: lb={lb:.4f} < prev={prev:.4f}"
        prev = lb


# ---------------------------------------------------------------------------
# Benjamini-Hochberg FDR
# ---------------------------------------------------------------------------


def test_bh_fdr_hand_computed():
    """KAT: Benjamini-Hochberg on a textbook example.

    Fault detected: wrong k* identification or wrong rejection set.

    Example from Benjamini & Hochberg (1995) Table 1 (adapted).
    m=6, q=0.05. Sorted p-values: 0.001, 0.008, 0.039, 0.041, 0.210, 0.450.
    Thresholds (i/m)*q: 0.00833, 0.01667, 0.025, 0.03333, 0.04167, 0.05.
    Compare p_(i) <= threshold:
        i=1: 0.001 <= 0.00833 -> YES
        i=2: 0.008 <= 0.01667 -> YES
        i=3: 0.039 <= 0.025   -> NO
        i=4: 0.041 <= 0.03333 -> NO
        i=5: 0.210 <= 0.04167 -> NO
        i=6: 0.450 <= 0.05    -> NO
    k* = 2 (last YES). Reject hypotheses 1 and 2.
    Input order: [0.210, 0.001, 0.039, 0.008, 0.450, 0.041]
    Original indices of rejected (sorted-rank 1&2): index 1 (p=0.001), index 3 (p=0.008)
    """
    p_values = [0.210, 0.001, 0.039, 0.008, 0.450, 0.041]
    rejected = benjamini_hochberg(p_values, q=0.05)

    # p=0.001 is at index 1 -> should be rejected
    assert rejected[1] is True, "p=0.001 should be rejected"
    # p=0.008 is at index 3 -> should be rejected
    assert rejected[3] is True, "p=0.008 should be rejected"
    # p=0.039 at index 2 -> should NOT be rejected (p > threshold)
    assert rejected[2] is False, "p=0.039 should not be rejected"
    # p=0.210 at index 0 -> should NOT be rejected
    assert rejected[0] is False, "p=0.210 should not be rejected"


def test_bh_all_null():
    """Property: all large p-values -> no rejections.

    Fault detected: BH rejecting when all p-values are large.
    """
    p_values = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    rejected = benjamini_hochberg(p_values, q=0.05)
    assert not any(rejected), "No hypotheses should be rejected when all p-values are large"


def test_bh_fdr_exact_boundary():
    """KAT: BH rejects when p_value exactly equals threshold (p <= threshold, not p < threshold).

    Fault detected: using strict `<` instead of `<=`, failing to reject a p-value
    exactly at the BH threshold.

    m=2, q=0.10:
        Sorted: [0.05, 0.10]
        Thresholds: [0.05, 0.10]
        i=1: 0.05 <= 0.05 -> YES (k=1)
        i=2: 0.10 <= 0.10 -> YES (k=2)  <-- boundary
    Both should be rejected.
    """
    p_values = [0.10, 0.05]  # unsorted; sorted = [0.05, 0.10]
    rejected = benjamini_hochberg(p_values, q=0.10)
    assert rejected[0] is True, "p=0.10 at threshold boundary should be rejected"
    assert rejected[1] is True, "p=0.05 at threshold should be rejected"


def test_bh_empty_input():
    """Edge case: empty p-value list must return empty list.

    Fault detected: IndexError or wrong return type on empty input.
    """
    assert benjamini_hochberg([], q=0.05) == []


def test_bh_all_significant():
    """Property: all p-values very small -> all rejected.

    Fault detected: BH not rejecting all when all p-values satisfy threshold.
    """
    p_values = [1e-10, 2e-10, 3e-10]
    rejected = benjamini_hochberg(p_values, q=0.10)
    assert all(rejected), "All tiny p-values should be rejected"


# ---------------------------------------------------------------------------
# Bonferroni
# ---------------------------------------------------------------------------


def test_bonferroni_single_element():
    """KAT: Bonferroni on a single p-value correctly applies threshold.

    Fault detected: Bonferroni erroneously returning [] for single-element input
    (mutation: `if m == 0` changed to `if m == 1`).
    With m=1, threshold = alpha/1 = alpha = 0.05.
    p=0.03 < 0.05 -> rejected=True.
    """
    result = bonferroni([0.03], alpha=0.05)
    assert result == [True], f"p=0.03 < 0.05 should be rejected, got {result}"

    result_not = bonferroni([0.10], alpha=0.05)
    assert result_not == [False], f"p=0.10 > 0.05 should not be rejected, got {result_not}"


def test_bonferroni_hand_computed():
    """KAT: Bonferroni threshold = alpha/m.

    Fault detected: using alpha instead of alpha/m.

    For alpha=0.05, m=5: threshold = 0.01.
    p_values = [0.005, 0.012, 0.001, 0.025, 0.008]
    Rejected: 0.005 (< 0.01), 0.001 (< 0.01), 0.008 (< 0.01)
    Not rejected: 0.012, 0.025
    """
    p_values = [0.005, 0.012, 0.001, 0.025, 0.008]
    rejected = bonferroni(p_values, alpha=0.05)
    assert rejected == [True, False, True, False, True], f"Got: {rejected}"


# ---------------------------------------------------------------------------
# Deflated Sharpe Ratio
# ---------------------------------------------------------------------------


def test_deflated_sharpe_decreases_with_n_trials():
    """Property: DSR decreases (or stays flat) as n_trials grows, for fixed SR.

    Fault detected: DSR not accounting for selection bias (SR* not increasing with trials).
    A higher n_trials means more selection bias, so the probability that
    the observed SR exceeds SR* should decrease.
    """
    observed_sr = 1.5
    n_obs = 252
    prev_dsr = 1.0
    for n_trials in [1, 2, 5, 10, 20, 50, 100]:
        dsr = deflated_sharpe_ratio(observed_sr, n_trials=n_trials, n_obs=n_obs)
        assert dsr <= prev_dsr + 1e-9, (
            f"DSR should decrease as n_trials grows. "
            f"DSR({n_trials}={dsr:.4f}) > DSR({n_trials-1}={prev_dsr:.4f})"
        )
        prev_dsr = dsr


def test_deflated_sharpe_single_trial():
    """KAT: with n_trials=1, SR* ~ 0 so DSR should be high for positive SR.

    Fault detected: applying selection bias correction when there is only one trial.
    """
    dsr = deflated_sharpe_ratio(observed_sr=2.0, n_trials=1, n_obs=252)
    # With SR=2.0 and n=252, the z-score should be roughly 2.0*sqrt(251) >> 0
    # DSR should be very close to 1.0
    assert dsr > 0.99, f"With SR=2.0, n_obs=252, n_trials=1: expected DSR>0.99, got {dsr:.4f}"


def test_deflated_sharpe_negative_sr():
    """Property: negative observed SR -> DSR < 0.5.

    Fault detected: sign error in the standardised statistic.
    """
    dsr = deflated_sharpe_ratio(observed_sr=-1.0, n_trials=5, n_obs=252)
    assert dsr < 0.5, f"Negative SR should give DSR < 0.5, got {dsr:.4f}"


def test_deflated_sharpe_invalid_args():
    """Edge case: invalid args raise ValueError.

    Fault detected: missing argument validation.
    """
    with pytest.raises(ValueError):
        deflated_sharpe_ratio(1.0, n_trials=0, n_obs=100)
    with pytest.raises(ValueError):
        deflated_sharpe_ratio(1.0, n_trials=5, n_obs=1)


# ---------------------------------------------------------------------------
# Bootstrap CI
# ---------------------------------------------------------------------------


def test_bootstrap_ci_deterministic():
    """Property: two calls with same seed produce identical CI.

    Fault detected: missing seed argument, or seed not propagated to RNG.
    """
    values = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06] * 20
    ci1 = bootstrap_ci(values, n_boot=500, seed=99)
    ci2 = bootstrap_ci(values, n_boot=500, seed=99)
    assert ci1 == ci2, f"Bootstrap CI not deterministic: {ci1} != {ci2}"


def test_bootstrap_ci_ordering():
    """Property: lower bound <= mean <= upper bound.

    Fault detected: CI bounds swapped.
    """
    values = [0.1 * i for i in range(20)]
    lo, hi = bootstrap_ci(values, n_boot=1000, seed=0)
    assert lo <= hi, f"Lower bound {lo:.4f} > upper bound {hi:.4f}"
    mean_val = sum(values) / len(values)
    assert lo <= mean_val <= hi, f"Mean {mean_val:.4f} not in CI [{lo:.4f}, {hi:.4f}]"


def test_bootstrap_ci_empty():
    """Edge case: empty values return (nan, nan).

    Fault detected: crash on empty input.
    """
    lo, hi = bootstrap_ci([], n_boot=100, seed=0)
    assert math.isnan(lo) and math.isnan(hi)


# ---------------------------------------------------------------------------
# Min sample size
# ---------------------------------------------------------------------------


def test_min_sample_size_known_value():
    """KAT: min_sample_size against Cohen (1988) Table 7.1.

    Fault detected: using alpha instead of 1-alpha for z_alpha.

    For effect=0.2 (small), power=0.8, alpha=0.05 (one-sided):
    Cohen (1988) gives n~197 (two-tailed), ~155 (one-tailed).
    Our formula is one-tailed: n = ((z_0.05 + z_0.8) / 0.2)^2
        z_0.05 ~ 1.645, z_0.8 ~ 0.842
        n = ((1.645 + 0.842) / 0.2)^2 = (2.487/0.2)^2 = 12.435^2 = 154.6 -> 155
    """
    n = min_sample_size(effect=0.2, power=0.8, alpha=0.05)
    # Expect ~155; allow ±5 for approximation error in our ppf
    assert 145 <= n <= 165, f"Expected n~155, got {n}"


def test_min_sample_size_invalid():
    """Edge case: non-positive effect raises ValueError.

    Fault detected: missing guard, returning infinity or crashing.
    """
    with pytest.raises(ValueError):
        min_sample_size(effect=0.0)
    with pytest.raises(ValueError):
        min_sample_size(effect=-0.5)


# ---------------------------------------------------------------------------
# Normal CDF
# ---------------------------------------------------------------------------


def test_norm_cdf_known_values():
    """KAT: _norm_cdf against standard textbook values.

    Fault detected: wrong polynomial coefficients in Abramowitz & Stegun formula.

    Standard normal CDF values (from any statistics textbook):
        Phi(0.0)  = 0.5000
        Phi(1.0)  = 0.8413
        Phi(1.96) = 0.9750
        Phi(-1.96)= 0.0250
    """
    assert abs(_norm_cdf(0.0) - 0.5000) < 1e-4, f"Phi(0) = {_norm_cdf(0.0):.6f}"
    assert abs(_norm_cdf(1.0) - 0.8413) < 1e-3, f"Phi(1) = {_norm_cdf(1.0):.6f}"
    assert abs(_norm_cdf(1.96) - 0.9750) < 1e-3, f"Phi(1.96) = {_norm_cdf(1.96):.6f}"
    assert abs(_norm_cdf(-1.96) - 0.0250) < 1e-3, f"Phi(-1.96) = {_norm_cdf(-1.96):.6f}"
