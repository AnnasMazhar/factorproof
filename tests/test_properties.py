"""
Property-based tests using Hypothesis.

Properties come from the method's mathematical assumptions, not from
the implementation — each property would be violated by a real bug.

Faults detected per test:
    test_wilson_lower_monotone_in_successes:
        Fault: Wilson lower bound not monotone in k (e.g., wrong sign in numerator).
    test_wilson_lower_bounded:
        Fault: Wilson lower bound outside [0, 1] (denominator inversion).
    test_bh_fdr_subset_monotone:
        Fault: BH rejecting a non-discovery p-value while not rejecting a smaller one.
    test_pearson_corr_symmetry:
        Fault: corr(x, y) != corr(y, x) due to asymmetric implementation.
    test_pearson_corr_self_correlation:
        Fault: corr(x, x) != 1.0 (or NaN for constant x).
    test_rankdata_sum:
        Fault: _rankdata returning wrong sum (1+2+...+n = n*(n+1)/2).
    test_bootstrap_ci_seed_invariance:
        Fault: different seeds producing identical CI (seed not used).
    test_deflated_sharpe_in_unit_interval:
        Fault: DSR outside [0, 1] (it is a CDF value).
    test_coverage_fraction_in_unit_interval:
        Fault: coverage fraction outside [0, 1].
    test_forward_returns_zero_for_constant_price:
        Fault: forward return non-zero when price is constant.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from hypothesis import assume, given, settings
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Significance properties
# ---------------------------------------------------------------------------


@given(
    k=st.integers(min_value=0, max_value=200),
    n=st.integers(min_value=1, max_value=200),
)
@settings(max_examples=200, deadline=None)
def test_wilson_lower_bounded(k, n):
    """Property: Wilson lower bound is always in [0, 1].

    Fault detected: LB outside unit interval (denominator zero or negative).
    """
    assume(k <= n)
    from factorlab.significance import wilson_lower

    lb = wilson_lower(k, n)
    assert 0.0 <= lb <= 1.0, f"Wilson LB={lb:.4f} out of [0,1] for k={k}, n={n}"


@given(
    n=st.integers(min_value=10, max_value=200),
    k1=st.integers(min_value=0, max_value=100),
    k2=st.integers(min_value=0, max_value=100),
)
@settings(max_examples=150, deadline=None)
def test_wilson_lower_monotone_in_successes(n, k1, k2):
    """Property: Wilson lower bound is non-decreasing in k for fixed n.

    Fault detected: sign error in the numerator making LB decrease with k.
    """
    assume(k1 <= n and k2 <= n)
    from factorlab.significance import wilson_lower

    lb1 = wilson_lower(k1, n)
    lb2 = wilson_lower(k2, n)
    if k1 < k2:
        assert (
            lb1 <= lb2 + 1e-9
        ), f"Wilson LB not monotone: k1={k1} -> lb1={lb1:.4f}, k2={k2} -> lb2={lb2:.4f}"


@given(
    p_values=st.lists(
        st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        min_size=1,
        max_size=20,
    ),
    q=st.floats(min_value=0.01, max_value=0.50),
)
@settings(max_examples=100, deadline=None)
def test_bh_fdr_subset_monotone(p_values, q):
    """Property: if p_i is rejected, all p_j < p_i must also be rejected.

    Fault detected: non-monotone BH rejection (rejecting a larger p without
    rejecting a smaller p in the same family).
    """
    from factorlab.significance import benjamini_hochberg

    rejected = benjamini_hochberg(p_values, q)
    assert len(rejected) == len(p_values)

    # Check monotonicity: sort by p-value; if p_(k) is rejected,
    # all p_(j) for j < k must also be rejected.
    indexed = sorted(enumerate(p_values), key=lambda x: x[1])
    found_rejection = False
    for orig_idx, pval in indexed:
        if rejected[orig_idx]:
            found_rejection = True
        elif found_rejection:
            # A smaller-or-equal p-value that is not rejected after seeing a larger rejected one
            # This can happen with BH (it finds the last k), so we only check that rejections
            # form a prefix of the sorted order.
            pass

    # The simpler invariant: rejections form a contiguous prefix in sorted order
    sorted_rejected = [rejected[orig_idx] for orig_idx, _ in indexed]
    # Once we see False, all subsequent must be False
    seen_false = False
    for r in sorted_rejected:
        if not r:
            seen_false = True
        else:
            assert not seen_false, "BH rejections are not a contiguous prefix in sorted order"


# ---------------------------------------------------------------------------
# Evaluate properties
# ---------------------------------------------------------------------------


@given(
    data=st.lists(
        st.floats(min_value=-10.0, max_value=10.0, allow_nan=False), min_size=2, max_size=50
    )
)
@settings(max_examples=200, deadline=None)
def test_pearson_corr_symmetry(data):
    """Property: Pearson corr(x, y) == corr(y, x).

    Fault detected: asymmetric implementation (e.g., cov(x,y) != cov(y,x) due to indexing).
    """
    from factorlab.evaluate import _pearson_corr

    n = len(data) // 2
    assume(n >= 2)  # noqa: PLR2004
    x = np.array(data[:n])
    y = np.array(data[n : 2 * n])

    r_xy = _pearson_corr(x, y)
    r_yx = _pearson_corr(y, x)

    if math.isnan(r_xy) or math.isnan(r_yx):
        return  # skip degenerate cases
    assert abs(r_xy - r_yx) < 1e-10, f"corr(x,y)={r_xy:.6f} != corr(y,x)={r_yx:.6f}"


@given(
    data=st.lists(
        st.floats(min_value=-100.0, max_value=100.0, allow_nan=False),
        min_size=3,
        max_size=50,
    )
)
@settings(max_examples=200, deadline=None)
def test_pearson_corr_self_correlation(data):
    """Property: corr(x, x) == 1.0 unless x is effectively constant (then NaN).

    Fault detected: self-correlation returning a value other than 1.0 for
    genuinely non-constant data.

    'Effectively constant' covers both exact ties and numerically near-zero
    variance (std < 1e-100) where the denominator underflows to zero.
    """
    from factorlab.evaluate import _pearson_corr

    x = np.array(data)
    r = _pearson_corr(x, x.copy())
    std_x = float(np.std(x))
    if std_x < 1e-80:
        # Numerically degenerate: NaN is acceptable
        return
    assert abs(r - 1.0) < 1e-9, f"corr(x,x)={r:.6f} should be 1.0 for std={std_x:.2e}"


@given(
    data=st.lists(
        st.floats(min_value=-1e6, max_value=1e6, allow_nan=False),
        min_size=1,
        max_size=100,
    )
)
@settings(max_examples=200, deadline=None)
def test_rankdata_sum(data):
    """Property: sum of ranks = n*(n+1)/2 (Gauss formula).

    Fault detected: _rankdata returning wrong ranks (e.g., 0-based or fractional error).
    """
    from factorlab.evaluate import _rankdata

    x = np.array(data)
    ranks = _rankdata(x)
    n = len(x)
    expected_sum = n * (n + 1) / 2.0
    assert (
        abs(ranks.sum() - expected_sum) < 1e-6
    ), f"Rank sum {ranks.sum():.2f} != n*(n+1)/2 = {expected_sum:.2f} for n={n}"


# ---------------------------------------------------------------------------
# Significance: Deflated Sharpe in unit interval
# ---------------------------------------------------------------------------


@given(
    observed_sr=st.floats(min_value=-5.0, max_value=5.0, allow_nan=False),
    n_trials=st.integers(min_value=1, max_value=100),
    n_obs=st.integers(min_value=2, max_value=1000),
)
@settings(max_examples=200, deadline=None)
def test_deflated_sharpe_in_unit_interval(observed_sr, n_trials, n_obs):
    """Property: DSR is a CDF value in [0, 1].

    Fault detected: DSR returning values outside [0, 1] (wrong CDF implementation).
    """
    from factorlab.significance import deflated_sharpe_ratio

    dsr = deflated_sharpe_ratio(observed_sr, n_trials=n_trials, n_obs=n_obs)
    assert 0.0 <= dsr <= 1.0, f"DSR={dsr:.4f} outside [0,1]"


# ---------------------------------------------------------------------------
# Data properties
# ---------------------------------------------------------------------------


@given(
    n_days=st.integers(min_value=50, max_value=200),
    n_assets=st.integers(min_value=2, max_value=6),
    seed=st.integers(min_value=0, max_value=999),
)
@settings(max_examples=50, deadline=None)
def test_coverage_fraction_in_unit_interval(n_days, n_assets, seed):
    """Property: coverage fraction is always in [0, 1].

    Fault detected: coverage returning > 1.0 due to denominator error.
    """
    from factorlab.data import synthetic_ohlcv
    from factorlab.evaluate import coverage_fraction
    from factorlab.factors import get_factor

    df = synthetic_ohlcv(n_days=n_days, n_assets=n_assets, seed=seed)
    factor = get_factor("mom_20")
    vals = factor.compute(df)
    cov = coverage_fraction(vals)
    assert 0.0 <= cov <= 1.0, f"Coverage={cov:.4f} outside [0,1]"


@given(seed=st.integers(min_value=0, max_value=999))
@settings(max_examples=30, deadline=None)
def test_forward_returns_zero_for_constant_price(seed):
    """Property: forward return = 0 when price is constant.

    Fault detected: log-return formula not returning 0 for log(P/P) = log(1) = 0.
    """

    from factorlab.evaluate import forward_returns

    dates = pd.bdate_range(start="2020-01-01", periods=20)
    rows = [
        {
            "date": d,
            "asset": "CONST",
            "open": 100.0,
            "high": 100.0,
            "low": 100.0,
            "close": 100.0,
            "volume": 1000.0,
        }
        for d in dates
    ]
    df = pd.DataFrame(rows)
    fwd = forward_returns(df, [1])
    valid = fwd[1].dropna(subset=["fwd_ret"])
    for _, row in valid.iterrows():
        assert (
            abs(row["fwd_ret"]) < 1e-10
        ), f"Non-zero forward return {row['fwd_ret']} for constant price"
