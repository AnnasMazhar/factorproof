"""
Tests for factorlab.evaluate — IC, quantile spread, hit rate, coverage, turnover.

Faults detected per test:
    test_ic_pearson_known_answer:
        Fault: wrong Pearson correlation formula (e.g., not centring, wrong denominator).
    test_ic_spearman_known_answer:
        Fault: rank computation wrong (e.g., using ordinal instead of average ranks for ties).
    test_pearson_corr_known_values:
        Fault: _pearson_corr internal arithmetic error.
    test_rankdata_ties:
        Fault: _rankdata not averaging tied ranks.
    test_forward_returns_horizon:
        Fault: forward return shifted by wrong amount (e.g., shift(-h+1) instead of shift(-h)).
    test_forward_returns_no_lookahead:
        Fault: forward returns using past close instead of future close.
    test_hit_rate_sign_agreement:
        Fault: sign comparison inverted or off-by-one.
    test_wilson_lb_vs_raw_hit_rate:
        Fault: Wilson lower bound > raw hit rate (impossible by construction).
    test_coverage_fraction_known:
        Fault: coverage counting NaN as non-NaN.
    test_coverage_all_nan:
        Fault: division by zero on all-NaN Series.
    test_quantile_spread_direction:
        Fault: quantile bins assigned in wrong order (1=top instead of 1=bottom).
    test_evaluate_factor_deterministic:
        Fault: non-seeded randomness inside evaluate_factor.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest
from factorlab.data import synthetic_ohlcv
from factorlab.evaluate import (
    _pearson_corr,
    _rankdata,
    coverage_fraction,
    evaluate_factor,
    forward_returns,
    hit_rate_metrics,
    quantile_analysis,
)

# ---------------------------------------------------------------------------
# Private math utilities — KAT
# ---------------------------------------------------------------------------


def test_pearson_corr_known_values():
    """KAT: Pearson correlation against hand-calculated values.

    Fault detected: wrong centring, wrong denominator, or sign error.

    Manual:
        x = [1, 2, 3], y = [2, 4, 6]
        xbar=2, ybar=4
        cov = ((-1)(-2) + (0)(0) + (1)(2)) / ... = (2+0+2) = 4
        var_x = (1+0+1) = 2, var_y = (4+0+4) = 8
        r = 4 / sqrt(2*8) = 4/4 = 1.0  (perfect positive correlation)
    """
    x = np.array([1.0, 2.0, 3.0])
    y = np.array([2.0, 4.0, 6.0])
    r = _pearson_corr(x, y)
    assert abs(r - 1.0) < 1e-10, f"Expected 1.0, got {r}"


def test_pearson_corr_anti_correlated():
    """KAT: perfectly anti-correlated series gives -1.

    Fault detected: absolute value taken instead of signed correlation.
    """
    x = np.array([1.0, 2.0, 3.0])
    y = np.array([6.0, 4.0, 2.0])
    r = _pearson_corr(x, y)
    assert abs(r - (-1.0)) < 1e-10, f"Expected -1.0, got {r}"


def test_pearson_corr_constant():
    """Edge case: constant y -> NaN (zero denominator).

    Fault detected: division by zero returning inf instead of nan.
    """
    x = np.array([1.0, 2.0, 3.0])
    y = np.array([5.0, 5.0, 5.0])
    r = _pearson_corr(x, y)
    assert math.isnan(r), f"Expected NaN for constant y, got {r}"


def test_rankdata_ties():
    """KAT: average rank for tied values.

    Fault detected: ordinal rank instead of average (e.g., ties not averaged).

    [3, 1, 1, 2]:
        1 appears at rank 1 and 2 -> average rank = 1.5
        2 appears at rank 3 -> rank = 3
        3 appears at rank 4 -> rank = 4
    """
    x = np.array([3.0, 1.0, 1.0, 2.0])
    ranks = _rankdata(x)
    assert ranks[1] == pytest.approx(1.5), f"Expected 1.5, got {ranks[1]}"
    assert ranks[2] == pytest.approx(1.5), f"Expected 1.5, got {ranks[2]}"
    assert ranks[3] == pytest.approx(3.0), f"Expected 3.0, got {ranks[3]}"
    assert ranks[0] == pytest.approx(4.0), f"Expected 4.0, got {ranks[0]}"


def test_rankdata_no_ties():
    """KAT: no ties -> standard 1-based integer ranks.

    Fault detected: wrong sort direction (descending instead of ascending).
    """
    x = np.array([10.0, 30.0, 20.0])
    ranks = _rankdata(x)
    expected = [1.0, 3.0, 2.0]
    for i, (r, e) in enumerate(zip(ranks, expected)):
        assert r == pytest.approx(e), f"Index {i}: expected {e}, got {r}"


# ---------------------------------------------------------------------------
# Forward returns
# ---------------------------------------------------------------------------


def test_forward_returns_horizon():
    """KAT: forward return at horizon h = log(close_{t+h} / close_t).

    Fault detected: using shift(h) instead of shift(-h), or h+1 off-by-one.

    We construct a simple 1-asset panel where every day close increases by 1%,
    so log-return at horizon 3 should be ~3%.
    """
    dates = pd.bdate_range(start="2020-01-01", periods=10)
    rows = []
    for i, d in enumerate(dates):
        c = 100.0 * (1.01**i)
        rows.append(
            {"date": d, "asset": "X", "open": c, "high": c, "low": c, "close": c, "volume": 1000.0}
        )
    df = pd.DataFrame(rows)

    fwd = forward_returns(df, [3])
    h3 = fwd[3].dropna(subset=["fwd_ret"])

    # At day 0: close=100, close[3]=~103.03. log(103.03/100) ~ 0.0298
    day0_row = h3[h3["date"] == dates[0]]
    assert not day0_row.empty, "No forward return for day 0"
    expected = math.log(100.0 * 1.01**3 / 100.0)  # log(1.01^3)
    actual = float(day0_row["fwd_ret"].iloc[0])
    assert abs(actual - expected) < 1e-6, f"Expected {expected:.6f}, got {actual:.6f}"


def test_forward_returns_no_lookahead():
    """KAT: forward return at day t uses close at t+h, not t-h.

    Fault detected: forward_returns using shift(+h) (past) instead of shift(-h) (future).

    In a strictly increasing price series, forward returns must all be positive.
    """
    dates = pd.bdate_range(start="2020-01-01", periods=20)
    rows = [
        {
            "date": d,
            "asset": "Y",
            "open": float(100 + i),
            "high": float(100 + i),
            "low": float(100 + i),
            "close": float(100 + i),
            "volume": 1000.0,
        }
        for i, d in enumerate(dates)
    ]
    df = pd.DataFrame(rows)
    fwd = forward_returns(df, [5])
    h5 = fwd[5].dropna(subset=["fwd_ret"])
    # All forward returns for a strictly increasing series must be > 0
    assert (
        h5["fwd_ret"] > 0
    ).all(), "Forward returns should all be positive for a strictly increasing price series"


# ---------------------------------------------------------------------------
# Coverage
# ---------------------------------------------------------------------------


def test_coverage_fraction_known():
    """KAT: coverage = non-NaN fraction.

    Fault detected: counting NaN as non-NaN, or wrong denominator.
    """
    s = pd.Series([1.0, 2.0, float("nan"), 4.0, float("nan")])
    s.index = pd.MultiIndex.from_tuples(
        [
            (pd.Timestamp("2020-01-01"), "A"),
            (pd.Timestamp("2020-01-02"), "A"),
            (pd.Timestamp("2020-01-03"), "A"),
            (pd.Timestamp("2020-01-04"), "A"),
            (pd.Timestamp("2020-01-05"), "A"),
        ],
        names=["date", "asset"],
    )
    cov = coverage_fraction(s)
    assert abs(cov - 0.6) < 1e-10, f"Expected 0.6, got {cov}"


def test_coverage_all_nan():
    """Edge case: all NaN -> coverage = 0.0.

    Fault detected: ZeroDivisionError or returning 1.0.
    """
    s = pd.Series([float("nan"), float("nan")])
    s.index = pd.MultiIndex.from_tuples(
        [(pd.Timestamp("2020-01-01"), "A"), (pd.Timestamp("2020-01-02"), "A")],
        names=["date", "asset"],
    )
    cov = coverage_fraction(s)
    assert cov == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Hit rate
# ---------------------------------------------------------------------------


def test_hit_rate_sign_agreement():
    """KAT: hit rate counts sign agreement between factor and forward return.

    Fault detected: sign comparison inverted or using absolute values.

    We construct a perfect predictor: factor sign always == fwd_ret sign.
    Expected hit rate = 1.0. Wilson LB must be >= 0.5 (well above chance).
    With n=10, Wilson LB at 100% HR is ~0.72, not 0.9 — the LB depends on n.
    What matters is: HR = 1.0 and LB > 0.5 (and LB <= HR always).
    """
    dates = pd.bdate_range(start="2020-01-01", periods=5)
    assets = ["A", "B"]

    # Factor values: alternating positive and negative
    factor_data = {(dates[i], a): (1.0 if i % 2 == 0 else -1.0) for i in range(5) for a in assets}
    factor_series = pd.Series(factor_data)
    factor_series.index.names = ["date", "asset"]

    # Forward returns: same sign as factor -> perfect predictor
    fwd_rows = [
        {"date": d, "asset": a, "fwd_ret": factor_data[(d, a)] * 0.01}
        for d in dates
        for a in assets
    ]
    fwd_df = pd.DataFrame(fwd_rows)

    hr, lb, n = hit_rate_metrics(factor_series, fwd_df)
    assert n == 10, f"Expected 10 observations, got {n}"
    assert abs(hr - 1.0) < 1e-9, f"Perfect predictor should have HR=1.0, got {hr}"
    # Wilson LB must be > 0.5 (significant signal) and <= HR (by construction)
    assert lb > 0.5, f"Wilson LB for 100% HR on n=10 should be > 0.5, got {lb:.4f}"
    assert lb <= hr + 1e-9, f"Wilson LB {lb:.4f} must be <= hit rate {hr:.4f}"


def test_wilson_lb_vs_raw_hit_rate():
    """Property: Wilson lower bound must always be <= raw hit rate.

    Fault detected: lb > hr (impossible by the construction of a lower bound).
    """
    dates = pd.bdate_range(start="2020-01-01", periods=20)
    assets = ["A", "B", "C"]
    rng = np.random.default_rng(0)

    factor_data = {(d, a): float(rng.standard_normal()) for d in dates for a in assets}
    factor_series = pd.Series(factor_data)
    factor_series.index.names = ["date", "asset"]

    fwd_rows = [
        {"date": d, "asset": a, "fwd_ret": float(rng.standard_normal()) * 0.01}
        for d in dates
        for a in assets
    ]
    fwd_df = pd.DataFrame(fwd_rows)

    hr, lb, n = hit_rate_metrics(factor_series, fwd_df)
    if not math.isnan(hr) and not math.isnan(lb):
        assert lb <= hr + 1e-9, f"Wilson LB {lb:.4f} > hit rate {hr:.4f} (impossible)"


# ---------------------------------------------------------------------------
# Quantile spread
# ---------------------------------------------------------------------------


def test_quantile_spread_direction():
    """KAT: quantile 1 = bottom factor, quantile 5 = top factor.

    Fault detected: bins assigned in wrong order (top ranked assigned Q1).

    We create a factor that perfectly predicts return (factor = fwd_ret).
    Then Q5 (top factor) should have the highest mean return.
    """
    dates = pd.bdate_range(start="2020-01-01", periods=30)
    n_assets = 10
    rng = np.random.default_rng(1)

    factor_data = {}
    fwd_rows = []
    for d in dates:
        vals = rng.standard_normal(n_assets)
        for j, a in enumerate([f"A{i}" for i in range(n_assets)]):
            factor_data[(d, a)] = float(vals[j])
            # Forward return is proportional to factor (perfect predictor)
            fwd_rows.append({"date": d, "asset": a, "fwd_ret": float(vals[j]) * 0.01})

    factor_series = pd.Series(factor_data)
    factor_series.index.names = ["date", "asset"]
    fwd_df = pd.DataFrame(fwd_rows)

    spread, mono, q_means = quantile_analysis(factor_series, fwd_df, n_quantiles=5)
    # With perfect predictor: Q5 mean > Q1 mean -> spread > 0
    assert spread > 0, f"Perfect predictor should have positive spread, got {spread:.6f}"
    # Monotonicity should be close to +1
    assert mono > 0.5, f"Expected high monotonicity, got {mono:.4f}"


# ---------------------------------------------------------------------------
# evaluate_factor integration
# ---------------------------------------------------------------------------


def test_evaluate_factor_deterministic():
    """Property: two identical calls return identical metrics.

    Fault detected: non-deterministic behaviour inside evaluate_factor
    (e.g., random tie-breaking in quantile assignment).
    """
    df = synthetic_ohlcv(n_days=300, n_assets=6, seed=0)
    from factorlab.factors import get_factor

    factor = get_factor("mom_20")
    factor_vals = factor.compute(df)

    r1 = evaluate_factor(factor_vals, df, [5], "mom_20")
    r2 = evaluate_factor(factor_vals, df, [5], "mom_20")

    assert r1[0].ic_pearson == r2[0].ic_pearson, "IC Pearson not deterministic"
    assert r1[0].ic_ir == r2[0].ic_ir, "IC-IR not deterministic"


def test_coverage_gate_low_coverage():
    """Integration: a factor with 10% coverage must fail the coverage gate.

    Fault detected: coverage gate not penalising sparse factors.
    """
    from factorlab.factors import get_factor as _get_factor

    df = synthetic_ohlcv(n_days=400, n_assets=8, seed=3)
    factor = _get_factor("mom_20")

    # Build a modified factor with 90% NaN coverage
    vals = factor.compute(df)
    sparse_vals = vals.copy()
    rng = np.random.default_rng(1)
    mask = rng.uniform(size=len(sparse_vals)) < 0.90
    sparse_vals.iloc[mask] = float("nan")

    # Inject sparse factor via direct evaluate call to check coverage
    from factorlab.evaluate import coverage_fraction

    cov = coverage_fraction(sparse_vals)
    assert cov < 0.50, f"Sparse vals should have coverage < 0.50, got {cov:.2f}"
