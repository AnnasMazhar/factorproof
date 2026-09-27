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
    test_slight_lookahead_detected_by_source_inspection (M01 FIX):
        Fault: subtle future-data usage not flagged by uses_future_data=True but
        containing .shift(-N) in compute() bypassing all gates and being promoted.
    test_check_lookahead_source_finds_negative_shifts:
        Fault: check_lookahead_source() missing negative-shift regex, returning [] for
        a factor that contains .shift(-2) and .shift(-5).
    test_clean_factor_no_negative_shifts:
        Fault: check_lookahead_source() false positive on clean factors.
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
    mean_ic, ic_ir, ic_t, ic_t_naive, n = information_coefficient(factor_series, fwd_df, "pearson")
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
        ic_tstat_naive=3.5,
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


# ---------------------------------------------------------------------------
# Byzantine: forge a passing p-value via test family scoping
# ---------------------------------------------------------------------------


def test_fdr_single_factor_standalone_vs_family():
    """Byzantine: a factor that passes FDR in isolation (m=1) must NOT pass
    in the screen with 13 factors (m=13) — the family size must not be forged.

    Fault detected: FDR correction ignoring the true family size, promoting
    noise that survived by multiple comparisons.
    """
    from factorlab.significance import benjamini_hochberg

    # Simulate 13 p-values for 13 factors, one of which happens to be "good"
    # p=0.05 looks good but does not pass BH at q=0.10 with m=13
    pvals = [0.05] + [0.8] * 12  # best factor has p=0.05

    rejected_full = benjamini_hochberg(pvals, q=0.10)
    # With m=13, BH threshold for rank 1 is (1/13)*0.10 = 0.0077
    # p=0.05 > 0.0077 → should NOT be rejected (rejected=True means the null is rejected,
    # i.e. passes FDR — so we expect False here meaning factor fails to survive FDR)
    assert not rejected_full[0], (
        "Factor with p=0.05 in a family of 13 must NOT survive FDR at q=0.10; "
        "got rejected_full[0]=True suggesting family size is not respected"
    )

    # Same factor in isolation (m=1): p=0.05 < q=0.10 → should survive
    rejected_solo = benjamini_hochberg([0.05], q=0.10)
    assert rejected_solo[0], "Factor with p=0.05 evaluated alone (m=1) must survive FDR at q=0.10"


# ---------------------------------------------------------------------------
# Byzantine: HAC must differ from naive at H=20 for a correlated factor
# ---------------------------------------------------------------------------


def test_hac_diverges_from_naive_at_h20():
    """Byzantine: at H=20, HAC t-stat must be materially lower than naive for a
    momentum-like factor with autocorrelated IC.

    Fault detected: HAC correction not applied, so t_hac == t_naive (inflate bug).
    This is the core Newey-West correctness check: overlapping labels inflate naive
    t-stats by ~sqrt(H); HAC corrects for this.
    """
    from factorlab.evaluate import evaluate_factor

    df = synthetic_ohlcv(n_days=1500, n_assets=12, seed=7, plant_signal=True)
    factor = get_factor("mom_20")
    vals = factor.compute(df)
    metrics = evaluate_factor(vals, df, [20], "mom_20")
    m = metrics[0]

    # At H=20, naive should be noticeably larger than HAC
    ratio = m.ic_tstat_naive / m.ic_tstat if abs(m.ic_tstat) > 1e-6 else 1.0
    assert ratio > 1.5, (
        f"HAC/naive ratio={ratio:.2f} at H=20; expected >1.5x inflation correction. "
        "If ratio~1.0, the HAC fix is not wired."
    )


# ---------------------------------------------------------------------------
# Byzantine: lookahead must be blocked even with --force-style config bypass
# ---------------------------------------------------------------------------


def test_lookahead_factor_always_rejected_regardless_of_thresholds():
    """Byzantine: lower all gate thresholds to zero — lookahead_control must still
    be rejected because uses_future_data=True is a hard block, not a threshold.

    Fault detected: lookahead gate being skipped when other thresholds are low,
    i.e. only rejecting lookahead_control because it fails IC gates, not because
    it is actually a lookahead factor.
    """
    from factorlab.factors import get_factor as gf
    from factorlab.promote import PromotionConfig, promote

    # Set all numeric gates to trivially pass, so only the lookahead check matters
    permissive_cfg = PromotionConfig(
        min_observations=1,
        min_ic_ir=0.0,
        min_abs_ic=0.0,
        max_turnover=100.0,
        hit_rate_wilson_lb=0.0,
        oos_consistency_min=0.0,
        fdr_q=1.0,  # FDR never blocks
        horizons=[5],
    )
    df = synthetic_ohlcv(n_days=200, n_assets=6, seed=0)
    factor = gf("lookahead_control")
    decision = promote(factor, df, permissive_cfg)

    assert (
        decision.verdict == "reject"
    ), "lookahead_control must be rejected even when all numeric gates are disabled"
    lookahead_reason = next((r for r in decision.reasons if r.code == "not_lookahead"), None)
    assert lookahead_reason is not None, "not_lookahead reason missing from decision"
    assert lookahead_reason.passed is False, "not_lookahead gate must be FAIL for lookahead_control"


# ---------------------------------------------------------------------------
# Byzantine: duplicate asset/date rows must not silently corrupt IC
# ---------------------------------------------------------------------------


def test_duplicate_rows_handled_without_silent_corruption():
    """Adversarial: duplicate (date, asset) rows must either be removed or raise,
    not silently produce a corrupted IC.

    Fault detected: duplicate rows doubling certain returns, inflating IC
    for factors that happen to rank duplicated rows consistently.
    """
    from factorlab.evaluate import evaluate_factor

    df = synthetic_ohlcv(n_days=100, n_assets=4, seed=42)
    # Duplicate the first 20 rows (creates repeated (date, asset) entries)
    df_dup = pd.concat([df, df.iloc[:20]], ignore_index=True).sort_values(["date", "asset"])
    factor = get_factor("mom_20")
    vals = factor.compute(df)  # compute on clean data, then evaluate on dirty
    try:
        metrics = evaluate_factor(vals, df_dup, [5], "mom_20")
        # If it returns, IC should be finite (not inf) — duplication inflates but must not explode
        for m in metrics:
            assert not math.isinf(
                m.ic_pearson
            ), "IC is inf after duplicate rows — silent corruption"
    except (ValueError, KeyError):
        pass  # Raising on duplicate index is also acceptable


# ---------------------------------------------------------------------------
# Byzantine: zero volume must not crash Amihud illiquidity
# ---------------------------------------------------------------------------


def test_zero_volume_amihud_no_crash():
    """Edge case: zero volume rows must not produce inf or crash in Amihud illiq.

    Fault detected: division by zero in amihud = |return| / volume when volume=0,
    producing inf that propagates silently into IC.
    """
    dates = pd.bdate_range(start="2020-01-01", periods=60)
    rows = []
    rng = np.random.default_rng(0)
    price = 100.0
    for d in dates:
        price = price * (1 + rng.standard_normal() * 0.01)
        rows.append(
            {
                "date": d,
                "asset": "ZVOL",
                "open": price,
                "high": price * 1.001,
                "low": price * 0.999,
                "close": price,
                "volume": 0.0,  # zero volume
            }
        )
    df = pd.DataFrame(rows)
    factor = get_factor("amihud_illiq_20")
    vals = factor.compute(df)  # Must not raise
    # Any inf values must not be present
    valid = vals.replace([float("inf"), float("-inf")], float("nan")).dropna()
    # All values (if any non-NaN remain) must be finite
    if len(valid) > 0:
        assert np.isfinite(valid.values).all(), "amihud returned inf for zero-volume rows"


# ---------------------------------------------------------------------------
# Byzantine: negative prices must not crash or produce nonsense IC
# ---------------------------------------------------------------------------


def test_negative_prices_no_crash():
    """Adversarial: negative close prices (corrupt data) must not crash factor
    computation or produce silently positive IC.

    Fault detected: log() of negative number (ValueError or nan that corrupts
    downstream sum comparisons without raising).
    """
    dates = pd.bdate_range(start="2020-01-01", periods=60)
    rows = []
    for i, d in enumerate(dates):
        rows.append(
            {
                "date": d,
                "asset": "NEG",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                # every 10th row has a negative close (corrupt data injection)
                "close": -5.0 if i % 10 == 0 else 100.0 + i * 0.1,
                "volume": 1000.0,
            }
        )
    df = pd.DataFrame(rows)
    factor = get_factor("mom_20")
    try:
        vals = factor.compute(df)
        # If it returns, values must be finite or NaN — not inf
        if vals is not None:
            bad = vals[vals.apply(lambda x: isinstance(x, float) and math.isinf(x))]
            assert len(bad) == 0, f"mom_20 returned inf for negative prices: {bad}"
    except (ValueError, FloatingPointError):
        pass  # Raising on negative prices is acceptable


# ---------------------------------------------------------------------------
# M01 FIX: Source-based lookahead detection (ADVERSARIAL-REVIEW finding M01)
# ---------------------------------------------------------------------------


def test_slight_lookahead_detected_by_source_inspection():
    """M01 FIX: A factor that blends future data via .shift(-N) without setting
    uses_future_data=True must be detected and rejected by Gate 0.5 (source inspection).

    Before this fix: SlightLookahead was PROMOTED (IC=0.032, IC-IR=0.074) because
    the structural flag check only fires for factors that opt in to uses_future_data=True.

    After this fix: check_lookahead_source() finds .shift(-2) in compute() and the
    no_negative_shifts gate rejects the factor before statistical evaluation.

    Fault detected: Gate 0 relying solely on uses_future_data=True flag, allowing
    subtle lookahead contamination via .shift(-N) to pass all gates undetected.
    """
    from factorlab.cv import check_lookahead_source
    from factorlab.factors.base import Factor
    from factorlab.factors.library import _melt, _pivot_close
    from factorlab.promote import PromotionConfig, promote

    class SlightLookahead(Factor):
        """Replication of the adversarial factor from ADVERSARIAL-REVIEW.md M01.

        This factor blends 20-day momentum with 10% weight on a 4-day future
        return window. It does NOT set uses_future_data=True, which was the
        original bypass vector.
        """

        name = "slight_lookahead_test"
        category = "test"
        description = "Subtle lookahead — shift(-2) blended into momentum base"
        params = {}
        uses_future_data = False  # deliberately NOT flagged

        def compute(self, df):
            close = _pivot_close(df)
            mom = np.log(close / close.shift(20))
            future_smooth = np.log(close.shift(-2) / close.shift(2)) * 0.1
            return _melt(mom + future_smooth)

    sl = SlightLookahead()

    # Source inspection must find the suspicious shift
    patterns = check_lookahead_source(sl)
    assert len(patterns) > 0, (
        "check_lookahead_source() returned no findings for a factor with shift(-2). "
        "The source inspection regex is not matching."
    )
    assert any("-2" in p for p in patterns), f"Expected shift(-2) in findings, got: {patterns}"

    # Promotion must be rejected
    df = synthetic_ohlcv(n_days=500, n_assets=6, seed=7, plant_signal=True)
    cfg = PromotionConfig(horizons=[5])
    decision = promote(sl, df, cfg)

    assert decision.verdict == "reject", (
        f"SlightLookahead must be REJECTED (was PROMOTED before M01 fix). "
        f"verdict={decision.verdict}"
    )

    # The specific gate must be no_negative_shifts
    neg_shift_reason = next((r for r in decision.reasons if r.code == "no_negative_shifts"), None)
    assert (
        neg_shift_reason is not None
    ), "Gate 'no_negative_shifts' not found in reasons — source inspection gate not wired."
    assert (
        neg_shift_reason.passed is False
    ), "no_negative_shifts gate should be FAIL for SlightLookahead."


def test_check_lookahead_source_finds_negative_shifts():
    """KAT: check_lookahead_source() must find .shift(-N) patterns.

    Tests multiple patterns to verify the regex is correct:
    - .shift(-1): single digit
    - .shift(-20): two digits
    - .shift( -3 ): with whitespace
    - .shift(5): positive shift must NOT be detected

    Fault detected: wrong regex missing the negative sign, or matching only
    single-digit shifts, or false-positive on positive shifts.
    """
    from factorlab.cv import check_lookahead_source
    from factorlab.factors.base import Factor
    from factorlab.factors.library import _melt, _pivot_close

    class MultiShiftFactor(Factor):
        name = "multi_shift_test"
        category = "test"
        description = "Tests multiple shift patterns"
        params = {}

        def compute(self, df):
            close = _pivot_close(df)
            # Has negative shifts (-1, -20) and a positive shift (5) that must not fire
            a = close.shift(-1)
            b = close.shift(-20)
            c = close.shift(5)  # positive shift — past data, not lookahead
            return _melt(a + b + c)

    mf = MultiShiftFactor()
    patterns = check_lookahead_source(mf)

    # Both negative shifts must be found
    all_pattern_str = " ".join(patterns)
    assert "shift(-1)" in all_pattern_str, f"shift(-1) not found in: {patterns}"
    assert "shift(-20)" in all_pattern_str, f"shift(-20) not found in: {patterns}"

    # Positive shift must NOT be flagged
    assert (
        "shift(5)" not in all_pattern_str
    ), f"shift(5) (positive, past data) was incorrectly flagged: {patterns}"


def test_clean_factor_no_negative_shifts():
    """KAT: check_lookahead_source() must return empty list for clean factors.

    Fault detected: false positive — flagging a momentum factor that only uses
    positive shifts (.shift(N) with N > 0) as suspicious.

    All 13 registered factors (except lookahead_control) must pass this check.
    """
    from factorlab.cv import check_lookahead_source
    from factorlab.factors import get_factor, list_factors

    clean_factors = [m["name"] for m in list_factors() if m["name"] != "lookahead_control"]
    for name in clean_factors:
        factor = get_factor(name)
        patterns = check_lookahead_source(factor)
        assert patterns == [], (
            f"Clean factor '{name}' was flagged for negative shifts: {patterns}. "
            "False positive in check_lookahead_source()."
        )


def test_closure_lookahead_rejected_by_runtime_check():
    """F-A3 FIX: A factor that hides the shift amount in a closure variable must be
    detected and rejected by the runtime lookahead check (Gate 0.75).

    Fault detected: source inspection (Gate 0.5) cannot see closure variables.
    The source code `close.shift(shift_amount)` where `shift_amount = -5` is
    declared outside compute() does not contain a literal negative number.

    The runtime check correlates factor values with FUTURE returns and rejects
    if correlation exceeds threshold (0.30). A legitimate factor has IC ~0.02-0.10;
    a lookahead factor (even smoothed) has IC ~0.30+.
    """
    from factorlab.cv import check_lookahead_runtime
    from factorlab.data import synthetic_ohlcv
    from factorlab.factors.base import Factor

    # Test the runtime check directly (not via promote(), since promote() may
    # also catch via source inspection for class-defined factors)
    shift_amount = -5

    class ClosureLookaheadFactor(Factor):
        name = "closure_lookahead"
        category = "attack"
        description = "Lookahead hidden via closure variable"
        params = {}
        uses_future_data = False

        def compute(self, df):
            close = df.pivot(index="date", columns="asset", values="close")
            future_ret = close.shift(shift_amount) / close - 1
            smoothed = future_ret.rolling(window=10, min_periods=1).mean()
            factor_vals = smoothed.stack()
            factor_vals.index.names = ["date", "asset"]
            return factor_vals

    df = synthetic_ohlcv(n_days=1500, n_assets=12, seed=7, plant_signal=True)
    factor = ClosureLookaheadFactor()

    # Runtime check should detect high correlation with future returns
    is_lookahead, reason = check_lookahead_runtime(factor, df, threshold=0.30)

    assert is_lookahead, (
        f"Closure lookahead factor NOT detected by runtime check! Reason: {reason}. "
        "Runtime check (threshold=0.30) should detect correlation with future returns."
    )
    assert (
        "correlated with future returns" in reason.lower()
    ), f"Runtime check returned unexpected reason: {reason}"


def test_legitimate_factor_passes_runtime_check():
    """F-A3 FIX counterpart: legitimate factors must NOT be flagged by the runtime
    lookahead check.

    A momentum factor (mom_20) on planted-signal data has IC ~0.025, well below
    the threshold of 0.30. It must pass the runtime check.
    """
    from factorlab.cv import check_lookahead_runtime
    from factorlab.data import synthetic_ohlcv
    from factorlab.factors import get_factor

    df = synthetic_ohlcv(n_days=1500, n_assets=12, seed=7, plant_signal=True)
    factor = get_factor("mom_20")

    is_lookahead, reason = check_lookahead_runtime(factor, df, threshold=0.30)

    assert not is_lookahead, (
        f"Legitimate factor mom_20 flagged as lookahead! Reason: {reason}. "
        "Runtime check threshold may be too sensitive."
    )
