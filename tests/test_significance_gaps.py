"""
Tests for factorlab.significance coverage gaps (cycle 2, implement pass 1).

Faults detected per test:
    test_correct_multiple_tests_counts:
        Fault: correct_multiple_tests mixing up BH/Bonferroni lists or counts
        (e.g. n_bh_discoveries computed from the Bonferroni list).
    test_correct_multiple_tests_empty:
        Fault: correct_multiple_tests crashing on an empty family.
    test_dsr_degenerate_variance_clamp_positive:
        Fault: sqrt of a non-positive variance term (NaN return or crash)
        when skew/kurtosis make the denominator non-positive.
    test_dsr_degenerate_variance_clamp_negative:
        Fault: same clamp path on the negative side returning NaN instead of 0.0.
    test_dsr_zero_sr_single_trial_is_half:
        Fault: wrong SR* baseline for n_trials=1 (must be exactly 0.0, so DSR(0)=0.5).
    test_norm_ppf_rejects_out_of_range:
        Fault: missing input validation, silently returning garbage for p outside (0, 1).
    test_norm_ppf_symmetry:
        Fault: broken reflection branch (p > 0.5 path inconsistent with p <= 0.5 path).
    test_norm_cdf_ppf_roundtrip:
        Fault: cdf/ppf pair inconsistent (wrong coefficients in either approximation).
    test_min_sample_size_known_cohen_value:
        Fault: wrong quantile (alpha instead of 1-alpha) or floor instead of ceil.
    test_min_sample_size_monotone:
        Fault: sample size not shrinking with effect / not growing with power.
    test_wilson_lower_never_exceeds_phat:
        Fault: bound above the point estimate (sign error in the Wilson formula).
    test_wilson_lower_zero_successes_is_zero:
        Fault: non-zero lower bound with zero successes.
    test_bh_step_up_not_step_down:
        Fault: first-crossing (step-down) implementation rejecting nothing when an
        early p-value misses but a later one hits its rank threshold.
    test_bh_contains_bonferroni_at_same_level:
        Fault: BH threshold scaled wrong (e.g. divided by m twice), dropping a
        hypothesis Bonferroni already rejects at the same level.
    test_bootstrap_ci_constant_input:
        Fault: CI not collapsing to the constant for degenerate input.
    test_bootstrap_ci_ignores_nans:
        Fault: NaNs leaking into the resample (NaN means) instead of being filtered.
"""

from __future__ import annotations

import math

import pytest
from factorlab.significance import (
    _norm_cdf,
    _norm_ppf,
    benjamini_hochberg,
    bonferroni,
    bootstrap_ci,
    correct_multiple_tests,
    deflated_sharpe_ratio,
    min_sample_size,
    wilson_lower,
)
from hypothesis import given
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# correct_multiple_tests — previously imported by tests but never called
# ---------------------------------------------------------------------------


def test_correct_multiple_tests_counts():
    """KAT: counts and lists agree with the standalone procedures.

    Fault detected: field mixup between BH and Bonferroni results.

    Hand-built family, q=0.10, alpha=0.05, m=4:
        p = [0.005, 0.02, 0.04, 0.50]
        BH thresholds: k=1: 0.025 -> 0.005 pass; k=2: 0.05 -> 0.02 pass;
                       k=3: 0.075 -> 0.04 pass; k=4: 0.10 -> 0.50 fail.
        k*=3 -> BH rejects first three.
        Bonferroni threshold: 0.05/4 = 0.0125 -> rejects only p=0.005.
    """
    res = correct_multiple_tests([0.005, 0.02, 0.04, 0.50], q=0.10, alpha=0.05)
    assert res.bh_rejected == [True, True, True, False]
    assert res.bonferroni_rejected == [True, False, False, False]
    assert res.n_bh_discoveries == 3
    assert res.n_bonferroni_discoveries == 1
    assert res.q_level == 0.10
    assert res.alpha_level == 0.05
    # Cross-check against the standalone procedures (not self-consistency:
    # the expected lists above are hand-derived).
    assert res.bh_rejected == benjamini_hochberg([0.005, 0.02, 0.04, 0.50], 0.10)
    assert res.bonferroni_rejected == bonferroni([0.005, 0.02, 0.04, 0.50], 0.05)


def test_correct_multiple_tests_empty():
    """Empty family must return empty lists and zero counts, not crash.

    Fault detected: len-zero family raising or returning None.
    """
    res = correct_multiple_tests([], q=0.10, alpha=0.05)
    assert res.bh_rejected == []
    assert res.bonferroni_rejected == []
    assert res.n_bh_discoveries == 0
    assert res.n_bonferroni_discoveries == 0


# ---------------------------------------------------------------------------
# Deflated Sharpe — degenerate variance clamp + single-trial baseline
# ---------------------------------------------------------------------------


def test_dsr_degenerate_variance_clamp_positive():
    """KAT: denom 1 - skew*SR + (kurt-3)/4*SR^2 <= 0 must clamp, not NaN.

    Fault detected: math.sqrt of a negative variance term (NaN/crash).

    Hand computation: SR=2.0, skew=1.0, kurt=3.0 -> denom = 1-2+0 = -1 <= 0.
    Clamped to 1e-9. SR* for n_trials=10 is ~1.58 < 2.0, so
    z = (2.0 - 1.58)*sqrt(251)/sqrt(1e-9) >> 0 -> Phi(z) = 1.0.
    """
    dsr = deflated_sharpe_ratio(observed_sr=2.0, n_trials=10, n_obs=252, skew=1.0, kurtosis=3.0)
    assert math.isfinite(dsr), f"DSR must be finite under clamp, got {dsr}"
    assert dsr == 1.0


def test_dsr_degenerate_variance_clamp_negative():
    """KAT: clamp path on the negative side must return 0.0, not NaN.

    Fault detected: same missing-clamp fault with opposite sign.

    Hand computation: SR=-5.0, skew=-1.0, kurt=3.0 -> denom = 1-5+0 = -4.
    z -> -inf -> Phi = 0.0.
    """
    dsr = deflated_sharpe_ratio(observed_sr=-5.0, n_trials=10, n_obs=252, skew=-1.0, kurtosis=3.0)
    assert math.isfinite(dsr), f"DSR must be finite under clamp, got {dsr}"
    assert dsr == 0.0


def test_dsr_zero_sr_single_trial_is_half():
    """KAT: DSR(0.0, n_trials=1, T) must be exactly 0.5.

    Fault detected: non-zero SR* baseline for a single trial.

    Hand computation: n_trials=1 -> sr_star=0.0; z=(0-0)*sqrt(T-1)/1=0;
    Phi(0)=0.5 within the 7.5e-8 documented error of the A&S 26.2.17 CDF.
    """
    assert deflated_sharpe_ratio(0.0, 1, 100) == pytest.approx(0.5, abs=1e-6)


# ---------------------------------------------------------------------------
# Normal ppf — validation, symmetry, round-trip
# ---------------------------------------------------------------------------


def test_norm_ppf_rejects_out_of_range():
    """ppf must raise ValueError for p outside (0, 1).

    Fault detected: missing validation returning a nonsense quantile.
    """
    for bad in (0.0, 1.0, -0.1, 1.5):
        with pytest.raises(ValueError):
            _norm_ppf(bad)


def test_norm_ppf_symmetry():
    """ppf(p) == -ppf(1-p): the reflection branch must agree.

    Fault detected: broken p > 0.5 branch.
    """
    for p in (0.9, 0.975, 0.6, 0.999):
        assert _norm_ppf(p) == pytest.approx(-_norm_ppf(1.0 - p), abs=1e-12)


def test_norm_cdf_ppf_roundtrip():
    """cdf(ppf(p)) == p within the documented 4.5e-4 ppf accuracy.

    Fault detected: coefficient error in either approximation.
    """
    for p in (0.025, 0.10, 0.50, 0.90, 0.975):
        assert _norm_cdf(_norm_ppf(p)) == pytest.approx(p, abs=1e-3)


# ---------------------------------------------------------------------------
# min_sample_size — Cohen KAT + monotonicity
# ---------------------------------------------------------------------------


def test_min_sample_size_known_cohen_value():
    """KAT: effect=0.5, power=0.8, alpha=0.05 -> n=25.

    Fault detected: wrong quantile direction or floor instead of ceil.

    Hand computation: z_alpha = ppf(0.95) = 1.6449, z_beta = ppf(0.8) = 0.8416.
    n = ((1.6449+0.8416)/0.5)^2 = (4.9730)^2 = 24.73 -> ceil = 25.
    (ppf error <= 4.5e-4 moves n by < 0.02, far from the integer boundary.)
    """
    assert min_sample_size(effect=0.5, power=0.8, alpha=0.05) == 25


def test_min_sample_size_monotone():
    """Larger effect -> smaller n; higher power -> larger n.

    Fault detected: inverted formula (effect in the numerator).
    """
    assert min_sample_size(effect=0.5) < min_sample_size(effect=0.2)
    assert min_sample_size(effect=0.5, power=0.9) >= min_sample_size(effect=0.5, power=0.5)


# ---------------------------------------------------------------------------
# Wilson lower bound — properties
# ---------------------------------------------------------------------------


@given(k=st.integers(min_value=1, max_value=99), n=st.integers(min_value=2, max_value=200))
def test_wilson_lower_never_exceeds_phat(k, n):
    """Property: Wilson LB is a *lower* bound: lb(k,n) <= k/n.

    Fault detected: sign error in the Wilson formula pushing lb above p_hat.
    """
    assume_k = min(k, n - 1)
    lb = wilson_lower(k=assume_k, n=n, z=1.96)
    assert lb <= assume_k / n


def test_wilson_lower_zero_successes_is_zero():
    """KAT: k=0 -> lb exactly 0.0 (numerator cancels: z^2/2n - z*(z/2n) = 0).

    Fault detected: positive lower bound with zero successes.
    """
    assert wilson_lower(k=0, n=100, z=1.96) == 0.0


# ---------------------------------------------------------------------------
# BH — step-up semantics + nesting inside Bonferroni
# ---------------------------------------------------------------------------


def test_bh_step_up_not_step_down():
    """KAT: a first-rank miss with later hits must still reject all three.

    Fault detected: first-crossing (step-down) loop that stops at the first
    rank missing its threshold.

    Hand computation, q=0.10, m=3, sorted p = [0.05, 0.06, 0.065]:
        k=1: 0.05 <= 0.0333? No. k=2: 0.06 <= 0.0667? Yes.
        k=3: 0.065 <= 0.10? Yes. Correct step-up: k*=3, reject all.
        Step-down bug: stop at k=1, reject none.
    """
    assert benjamini_hochberg([0.065, 0.05, 0.06], q=0.10) == [True, True, True]


@given(
    p_values=st.lists(
        st.sampled_from([0.001, 0.005, 0.01, 0.02, 0.04, 0.06, 0.10, 0.30, 0.80]),
        min_size=1,
        max_size=8,
    )
)
def test_bh_contains_bonferroni_at_same_level(p_values):
    """Property: at q == alpha, every Bonferroni rejection is also a BH rejection.

    Fault detected: BH threshold scaled by an extra 1/m (or any deflation that
    drops hypotheses Bonferroni already rejects at the same level).

    Proof sketch: Bonferroni rejects p_i <= a/m. In sorted order the rejected
    hypotheses are the smallest ones, so p_(j) <= a/m <= (j/m)*a for j >= 1,
    hence step-up k* covers them. Coarse grid keeps p-values off 1-ulp float
    boundaries so the property tests the math, not float rounding.
    """
    bh = benjamini_hochberg(list(p_values), q=0.05)
    bf = bonferroni(list(p_values), alpha=0.05)
    for i, rejected in enumerate(bf):
        if rejected:
            assert bh[i], f"BH dropped Bonferroni rejection at index {i}: {p_values}"


# ---------------------------------------------------------------------------
# Bootstrap CI — degenerate + NaN handling
# ---------------------------------------------------------------------------


def test_bootstrap_ci_constant_input():
    """CI of a constant sample collapses to the constant.

    Fault detected: resample/percentile path adding spread to degenerate input.
    """
    assert bootstrap_ci([2.5] * 50, n_boot=200, seed=0) == (2.5, 2.5)


def test_bootstrap_ci_ignores_nans():
    """NaNs must be filtered before resampling: same seed + same clean values
    -> identical CI with or without NaNs present.

    Fault detected: NaNs leaking into bootstrap means (NaN CI bounds).
    """
    clean = [1.0, 3.0, 2.0, 5.0, 4.0]
    with_nans = [1.0, float("nan"), 3.0, 2.0, float("nan"), 5.0, 4.0]
    assert bootstrap_ci(with_nans, n_boot=500, seed=3) == bootstrap_ci(clean, n_boot=500, seed=3)
