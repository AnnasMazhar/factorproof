"""
Adversarial and edge-case tests.

These tests inject hostile or degenerate inputs.
At least one test here will fail a naive implementation.

Faults detected per test:
    test_empty_factor_series_does_not_crash:
        Fault: coverage_fraction crashing on empty Series.
    test_all_nan_factor_rejected:
        Fault: promote() not detecting all-NaN factor as degenerate.
    test_single_asset_does_not_crash:
        Fault: cross-sectional IC crashing when only 1 asset (can't compute corr).
    test_constant_price_series_no_crash:
        Fault: factor computation crashing on zero log-returns (division by zero in vol).
    test_factor_with_inf_values_handled:
        Fault: inf propagating into IC calculation silently (no NaN guard).
    test_large_input_no_overflow:
        Fault: integer overflow in rankdata sum check for large n.
    test_report_markdown_timestamp_free:
        Fault: report including wall-clock time, making it non-deterministic.
    test_unicode_asset_names:
        Fault: asset name handling crashing on Unicode characters.
    test_very_short_panel_rejected:
        Fault: promote() crashing instead of rejecting on insufficient data.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest
from factorlab.data import synthetic_ohlcv
from factorlab.factors import get_factor

# ---------------------------------------------------------------------------
# Empty / degenerate inputs
# ---------------------------------------------------------------------------


def test_empty_factor_series_does_not_crash():
    """Edge case: coverage_fraction on empty Series returns 0.0 without crash.

    Fault detected: ZeroDivisionError when len(factor_vals) == 0.
    """
    from factorlab.evaluate import coverage_fraction

    empty = pd.Series([], dtype=float)
    empty.index = pd.MultiIndex.from_tuples([], names=["date", "asset"])
    cov = coverage_fraction(empty)
    assert cov == 0.0


def test_all_nan_factor_rejected():
    """Adversarial: a factor returning all NaN must be rejected by the gate.

    Fault detected: coverage gate allowing 0% non-NaN to pass.

    A naive implementation might skip the coverage check or confuse
    0.0 (all NaN) with passing 0 >= 0 threshold.
    """
    from factorlab.factors.base import Factor
    from factorlab.promote import PromotionConfig, promote

    class AllNanFactor(Factor):
        name = "all_nan"
        category = "test"
        description = "Returns all NaN"
        params = {}

        def compute(self, df: pd.DataFrame) -> pd.Series:
            from factorlab.factors.library import _melt, _pivot_close

            c = _pivot_close(df)
            return _melt(pd.DataFrame(np.nan, index=c.index, columns=c.columns))

    df = synthetic_ohlcv(n_days=200, n_assets=4, seed=0)
    decision = promote(AllNanFactor(), df, PromotionConfig(horizons=[5]))
    assert decision.verdict == "reject", "All-NaN factor must be rejected"


def test_constant_factor_rejected():
    """Adversarial: a constant-output factor must fail the 'not_degenerate' gate.

    Fault detected: degenerate check missing (constant IC is undefined).
    """
    from factorlab.factors.base import Factor
    from factorlab.promote import PromotionConfig, promote

    class ConstFactor(Factor):
        name = "const_factor"
        category = "test"
        description = "Returns a constant"
        params = {}

        def compute(self, df: pd.DataFrame) -> pd.Series:
            from factorlab.factors.library import _melt, _pivot_close

            c = _pivot_close(df)
            return _melt(pd.DataFrame(1.0, index=c.index, columns=c.columns))

    df = synthetic_ohlcv(n_days=200, n_assets=4, seed=0)
    decision = promote(ConstFactor(), df, PromotionConfig(horizons=[5]))
    assert decision.verdict == "reject", "Constant factor must be rejected"

    degen_reason = next(r for r in decision.reasons if r.code == "not_degenerate")
    assert degen_reason.passed is False


def test_single_asset_does_not_crash():
    """Edge case: 1 asset in panel should not crash IC computation.

    Fault detected: cross-sectional IC crashing when groupby yields groups of size 1
    (Pearson corr undefined for n=1).
    """
    from factorlab.evaluate import evaluate_factor

    df = synthetic_ohlcv(n_days=100, n_assets=1, seed=0)
    factor = get_factor("mom_20")
    vals = factor.compute(df)
    metrics = evaluate_factor(vals, df, [5], "mom_20")
    # Should return metrics (possibly all NaN) without crashing
    assert len(metrics) == 1


def test_constant_price_series_no_crash():
    """Edge case: constant close prices must not crash vol_20 or atr_norm_14.

    Fault detected: division by zero in volatility (std=0) or ATR computation.
    """
    dates = pd.bdate_range(start="2020-01-01", periods=60)
    rows = [
        {
            "date": d,
            "asset": "FLAT",
            "open": 100.0,
            "high": 100.0,
            "low": 100.0,
            "close": 100.0,
            "volume": 1000.0,
        }
        for d in dates
    ]
    df = pd.DataFrame(rows)
    for name in ["vol_20", "atr_norm_14"]:
        factor = get_factor(name)
        vals = factor.compute(df)  # Must not raise
        # Vol of constant series should be 0 or NaN (not inf)
        valid = vals.dropna()
        if len(valid) > 0:
            assert not (valid == float("inf")).any(), f"{name} returned inf for constant prices"


# ---------------------------------------------------------------------------
# Inf / NaN propagation
# ---------------------------------------------------------------------------


def test_factor_with_inf_values_handled():
    """Adversarial: inf in factor values should not silently propagate to IC.

    Fault detected: inf in factor values being treated as a valid observation,
    producing inf IC or nan IC without warning.
    """
    from factorlab.evaluate import information_coefficient

    dates = pd.bdate_range(start="2020-01-01", periods=30)
    assets = ["A", "B", "C"]
    # Factor with some inf values
    data = {}
    for d in dates:
        for a in assets:
            data[(d, a)] = float("inf") if np.random.default_rng(0).uniform() < 0.1 else 1.0
    factor_series = pd.Series(data)
    factor_series.index.names = ["date", "asset"]

    # Forward returns: simple random
    rng = np.random.default_rng(1)
    fwd_rows = [
        {"date": d, "asset": a, "fwd_ret": float(rng.standard_normal()) * 0.01}
        for d in dates
        for a in assets
    ]
    fwd_df = pd.DataFrame(fwd_rows)

    # Should not raise; IC may be NaN or finite
    mean_ic, ic_ir, ic_t, n = information_coefficient(factor_series, fwd_df, "pearson")
    # The important thing: no exception raised, and result is finite or NaN (not inf)
    for val in [mean_ic, ic_ir, ic_t]:
        if not math.isnan(val):
            assert not math.isinf(val), f"IC computation returned inf: {val}"


# ---------------------------------------------------------------------------
# Large inputs (overflow guard)
# ---------------------------------------------------------------------------


def test_large_input_no_overflow():
    """Adversarial: _rankdata on 10000 elements must not overflow.

    Fault detected: int32 overflow in rank sum computation (use float ranks).
    """
    from factorlab.evaluate import _rankdata

    n = 10000
    x = np.random.default_rng(0).standard_normal(n)
    ranks = _rankdata(x)
    expected_sum = n * (n + 1) / 2.0
    assert abs(ranks.sum() - expected_sum) < 1.0, f"Rank sum overflow for n={n}"


# ---------------------------------------------------------------------------
# Report stability
# ---------------------------------------------------------------------------


def test_report_markdown_timestamp_free():
    """KAT: to_markdown output must not contain timestamp strings.

    Fault detected: timestamp embedded in report making it non-reproducible
    (diff-unfriendly, breaks the 'report is stable' criterion).
    """
    from factorlab.evaluate import FactorMetrics
    from factorlab.promote import PromotionDecision, Reason
    from factorlab.report import to_markdown

    m = FactorMetrics(
        factor_name="test_factor",
        horizon=5,
        ic_pearson=0.05,
        ic_spearman=0.04,
        ic_ir=0.30,
        ic_tstat=2.1,
        ic_decay={1: 0.06, 5: 0.05, 20: 0.03},
        quantile_spread=0.002,
        monotonicity=0.8,
        hit_rate=0.53,
        hit_rate_wilson_lb=0.50,
        turnover=0.12,
        coverage=0.95,
        n_obs=100,
    )
    d = PromotionDecision(
        factor_name="test_factor",
        verdict="promote",
        reasons=[Reason("survives_fdr", True, 0.02, 0.10)],
        best_horizon=5,
        best_ic=0.05,
        best_ic_ir=0.30,
        oos_consistency=0.80,
        n_obs=100,
    )
    md = to_markdown([m], [d])

    # Check for date/time patterns (YYYY, HH:MM:SS)
    import re

    has_timestamp = bool(re.search(r"\d{4}-\d{2}-\d{2}|\d{2}:\d{2}:\d{2}", md))
    assert not has_timestamp, f"Markdown report contains timestamp:\n{md[:200]}"


# ---------------------------------------------------------------------------
# Unicode asset names
# ---------------------------------------------------------------------------


def test_unicode_asset_names():
    """Edge case: Unicode asset names must not crash factor computation.

    Fault detected: string encoding error when asset name contains non-ASCII.
    A naive implementation using str.encode() without error handling will crash.
    """
    dates = pd.bdate_range(start="2020-01-01", periods=40)
    assets = ["AAPL", "GOOG", "日本語", "مرحبا"]
    rows = []
    rng = np.random.default_rng(0)
    price = 100.0
    for d in dates:
        for a in assets:
            price = price * (1 + rng.standard_normal() * 0.01)
            rows.append(
                {
                    "date": d,
                    "asset": a,
                    "open": price,
                    "high": price * 1.001,
                    "low": price * 0.999,
                    "close": price,
                    "volume": 1000.0,
                }
            )
    df = pd.DataFrame(rows)

    factor = get_factor("mom_20")
    try:
        vals = factor.compute(df)
        assert vals is not None
    except Exception as e:
        pytest.fail(f"mom_20 crashed on Unicode asset names: {e}")


# ---------------------------------------------------------------------------
# Very short panel
# ---------------------------------------------------------------------------


def test_very_short_panel_rejected():
    """Adversarial: panel with < min_observations data must be rejected cleanly.

    Fault detected: promote() crashing instead of returning a rejection with reason.
    """
    from factorlab.promote import PromotionConfig, promote

    tiny_df = synthetic_ohlcv(n_days=10, n_assets=3, seed=0)
    factor = get_factor("mom_20")
    cfg = PromotionConfig(min_observations=30, horizons=[5])
    decision = promote(factor, tiny_df, cfg)
    assert decision.verdict == "reject", "Very short panel must produce a rejection"
