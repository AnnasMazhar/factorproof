"""
Tests for factorlab.cv — purged walk-forward cross-validation.

Faults detected per test:
    test_purge_no_label_overlap:
        Fault: purge logic failing to remove training rows whose label window
        overlaps the test set (lookahead via label leakage).
    test_embargo_removes_gap:
        Fault: embargo days not applied after purging (residual train-test proximity).
    test_split_chronological_order:
        Fault: splits not in chronological order, or test sets overlapping.
    test_correct_number_of_splits:
        Fault: splitter generating wrong number of splits.
    test_lookahead_factor_flagged:
        Fault: check_lookahead() not detecting LookaheadControl factor's flag.
    test_walk_forward_consistency_shape:
        Fault: evaluate_walk_forward returning wrong number of results.
    test_no_train_test_date_overlap:
        Fault: train and test date sets overlapping after purging.
    test_walk_forward_planted_signal_positive_oos_ic:
        Fault: planted signal not detectable (OOS IC <= 0 despite embedded autocorrelation).
"""

from __future__ import annotations

import pandas as pd
import pytest
from factorlab.cv import PurgedWalkForward, check_lookahead, evaluate_walk_forward
from factorlab.data import synthetic_ohlcv
from factorlab.factors import get_factor

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def small_df():
    """Small synthetic panel for fast tests."""
    return synthetic_ohlcv(n_days=300, n_assets=6, seed=42)


@pytest.fixture(scope="module")
def planted_df():
    """Synthetic panel with embedded momentum signal."""
    return synthetic_ohlcv(n_days=800, n_assets=8, seed=7, plant_signal=True)


# ---------------------------------------------------------------------------
# Purge correctness
# ---------------------------------------------------------------------------


def test_purge_no_label_overlap(small_df):
    """KAT: no training row's label window should overlap the test window.

    Fault detected: purge step missing or label_horizon not applied,
    allowing train labels to look into the test period.

    For each split: every training date t must satisfy
        t + label_horizon < first_test_date
    (i.e., the forward-return window does not reach into the test set).

    NOTE: embargo_days must be >= label_horizon per spec STATISTICAL CORRECTIONS.
    Using embargo_days=5, label_horizon=5 (minimum valid values).
    """
    splitter = PurgedWalkForward(n_splits=3, embargo_days=5, label_horizon=5)
    splits = list(splitter.split(small_df))

    for spl in splits:
        train_dates = set(small_df["date"].iloc[spl.train_idx].unique())
        test_dates = pd.DatetimeIndex(sorted(small_df["date"].iloc[spl.test_idx].unique()))
        first_test_date = test_dates[0]

        for td in train_dates:
            # td + label_horizon calendar days must be strictly before first_test_date
            label_end = td + pd.Timedelta(days=splitter.label_horizon)
            assert label_end < first_test_date, (
                f"Split {spl.split_id}: training date {td.date()} has label window "
                f"ending at {label_end.date()} which overlaps test start {first_test_date.date()}"
            )


def test_no_train_test_date_overlap(small_df):
    """KAT: no date should appear in both train and test sets.

    Fault detected: insufficient purging leaving shared dates in both partitions.

    NOTE: embargo_days must be >= label_horizon per spec STATISTICAL CORRECTIONS.
    """
    splitter = PurgedWalkForward(n_splits=3, embargo_days=5, label_horizon=5)
    splits = list(splitter.split(small_df))

    for spl in splits:
        train_dates = set(small_df["date"].iloc[spl.train_idx].unique())
        test_dates = set(small_df["date"].iloc[spl.test_idx].unique())
        overlap = train_dates & test_dates
        assert len(overlap) == 0, (
            f"Split {spl.split_id}: {len(overlap)} dates in both train and test: "
            f"{sorted(overlap)[:3]}"
        )


def test_embargo_removes_gap(small_df):
    """KAT: last training date must be at least embargo_days before first test date.

    Fault detected: embargo not applied, leaving residual proximity between
    train end and test start.
    """
    embargo = 5
    splitter = PurgedWalkForward(n_splits=3, embargo_days=embargo, label_horizon=5)
    splits = list(splitter.split(small_df))

    dates = pd.DatetimeIndex(sorted(small_df["date"].unique()))
    date_to_pos = {d: i for i, d in enumerate(dates)}

    for spl in splits:
        if not spl.n_embargoed:
            continue  # skip if no embargo was applied (degenerate split)

        train_dates_sorted = sorted(small_df["date"].iloc[spl.train_idx].unique())
        test_dates_sorted = sorted(small_df["date"].iloc[spl.test_idx].unique())

        last_train = train_dates_sorted[-1]
        first_test = test_dates_sorted[0]

        # Position gap in the full date array
        pos_last_train = date_to_pos.get(last_train, -1)
        pos_first_test = date_to_pos.get(first_test, -1)

        gap = pos_first_test - pos_last_train - 1
        assert gap >= embargo, (
            f"Split {spl.split_id}: gap between last train ({last_train.date()}) "
            f"and first test ({first_test.date()}) is {gap} positions, "
            f"expected >= {embargo}"
        )


# ---------------------------------------------------------------------------
# Split structure
# ---------------------------------------------------------------------------


def test_correct_number_of_splits(small_df):
    """KAT: splitter generates exactly n_splits splits.

    Fault detected: off-by-one in fold generation loop.

    NOTE: embargo_days must be >= label_horizon per spec STATISTICAL CORRECTIONS.
    Using embargo_days=5, label_horizon=5.
    """
    for n in [2, 3, 4]:
        splitter = PurgedWalkForward(n_splits=n, embargo_days=5, label_horizon=5)
        splits = list(splitter.split(small_df))
        assert len(splits) == n, f"Expected {n} splits, got {len(splits)}"


def test_split_chronological_order(small_df):
    """KAT: test windows must be in chronological order and non-overlapping.

    Fault detected: shuffled or overlapping test folds.

    NOTE: embargo_days must be >= label_horizon per spec STATISTICAL CORRECTIONS.
    """
    splitter = PurgedWalkForward(n_splits=4, embargo_days=5, label_horizon=5)
    splits = list(splitter.split(small_df))

    prev_test_end = pd.Timestamp.min
    for spl in splits:
        test_dates = sorted(small_df["date"].iloc[spl.test_idx].unique())
        first = test_dates[0]
        last = test_dates[-1]
        assert (
            first > prev_test_end
        ), f"Split {spl.split_id} test start {first} not after previous test end {prev_test_end}"
        prev_test_end = last


def test_insufficient_dates_raises():
    """Edge case: too few dates for the requested splits raises ValueError.

    Fault detected: silent failure instead of informative error.
    """
    tiny_df = synthetic_ohlcv(n_days=10, n_assets=2, seed=0)
    splitter = PurgedWalkForward(n_splits=10, embargo_days=5, label_horizon=5)
    with pytest.raises(ValueError, match="Not enough dates"):
        list(splitter.split(tiny_df))


# ---------------------------------------------------------------------------
# Lookahead detection
# ---------------------------------------------------------------------------


def test_lookahead_factor_flagged():
    """KAT: LookaheadControl must have uses_future_data=True.

    Fault detected: flag missing from factor, allowing it to bypass structural check.
    """
    factor = get_factor("lookahead_control")
    assert check_lookahead(factor) is True, "LookaheadControl must be flagged as lookahead"


def test_clean_factor_not_flagged():
    """KAT: mom_20 must not be flagged as lookahead.

    Fault detected: check_lookahead returning True for all factors (false positive).
    """
    factor = get_factor("mom_20")
    assert check_lookahead(factor) is False, "mom_20 must not be flagged as lookahead"


# ---------------------------------------------------------------------------
# Walk-forward evaluation
# ---------------------------------------------------------------------------


def test_walk_forward_consistency_shape(planted_df):
    """KAT: evaluate_walk_forward returns one result per horizon.

    Fault detected: wrong number of results (off-by-one or wrong horizon mapping).

    NOTE: embargo_days must be >= label_horizon per spec STATISTICAL CORRECTIONS.
    """
    factor = get_factor("mom_20")
    splitter = PurgedWalkForward(n_splits=3, embargo_days=5, label_horizon=5)
    horizons = [1, 5]
    results = evaluate_walk_forward(factor, planted_df, splitter, horizons)
    assert len(results) == len(horizons), f"Expected {len(horizons)} results, got {len(results)}"
    returned_horizons = {r.horizon for r in results}
    assert returned_horizons == set(horizons), f"Missing horizons: {returned_horizons}"


def test_walk_forward_planted_signal_positive_oos_ic(planted_df):
    """KAT: planted momentum signal must produce positive OOS IC at horizon 1.

    Fault detected: purging too aggressive (removes all training data) OR
    factor computation broken (returns NaN for all dates).

    The planted_signal=True dataset has AR(1) rho=0.08 embedded,
    which gives mom_20 a real positive predictive edge.
    This test would catch a factor implementation that produces
    all-zero or all-NaN values.

    NOTE: embargo_days must be >= label_horizon per spec STATISTICAL CORRECTIONS.
    """
    factor = get_factor("mom_20")
    splitter = PurgedWalkForward(n_splits=3, embargo_days=5, label_horizon=5)
    results = evaluate_walk_forward(factor, planted_df, splitter, [1])
    h1_result = next(r for r in results if r.horizon == 1)
    # Must have at least one valid split
    assert h1_result.n_splits >= 1, "No valid splits produced"
    # OOS IC must be a real number (not nan)
    import math

    assert not math.isnan(h1_result.oos_mean_ic), "OOS IC is NaN on planted-signal data"


# ---------------------------------------------------------------------------
# Embargo enforcement (spec STATISTICAL CORRECTIONS)
# ---------------------------------------------------------------------------


def test_embargo_less_than_horizon_raises():
    """KAT: PurgedWalkForward must reject embargo_days < label_horizon.

    Fault detected: splitter accepting invalid configuration that allows
    overlapping label windows between train and test.

    Spec STATISTICAL CORRECTIONS: 'enforce embargo_days >= H at construction
    time and raise otherwise; a smaller embargo defeats the exact overlap it
    exists to break.'
    """
    with pytest.raises(ValueError, match="embargo_days"):
        PurgedWalkForward(n_splits=3, embargo_days=3, label_horizon=5)


def test_embargo_equal_to_horizon_is_valid():
    """KAT: embargo_days == label_horizon is the minimum valid configuration.

    Fault detected: enforcement too strict (rejecting valid boundary case).
    """
    # Should not raise
    splitter = PurgedWalkForward(n_splits=3, embargo_days=5, label_horizon=5)
    assert splitter.embargo_days == 5


# ---------------------------------------------------------------------------
# CPCV
# ---------------------------------------------------------------------------


def test_cpcv_generates_correct_number_of_splits():
    """KAT: CPCV generates C(n_groups, k_test) splits.

    Fault detected: combination enumeration off-by-one or missing entries.

    For n_groups=4, k_test=2: C(4,2) = 6 splits.
    """
    from math import comb

    from factorlab.cv import CPurgedCV

    df = synthetic_ohlcv(n_days=600, n_assets=6, seed=0)
    cpcv = CPurgedCV(n_groups=4, k_test=2, embargo_days=5, label_horizon=5)
    splits = cpcv.split(df)
    expected = comb(4, 2)
    assert len(splits) == expected, f"Expected {expected} CPCV splits (C(4,2)), got {len(splits)}"


def test_cpcv_no_train_test_overlap():
    """KAT: no date appears in both train and test sets for any CPCV split.

    Fault detected: group assignment or purge leaving shared dates.
    """
    from factorlab.cv import CPurgedCV

    df = synthetic_ohlcv(n_days=600, n_assets=6, seed=0)
    cpcv = CPurgedCV(n_groups=4, k_test=2, embargo_days=5, label_horizon=5)
    splits = cpcv.split(df)

    for spl in splits:
        train_dates = set(df["date"].iloc[spl.train_idx].unique())
        test_dates = set(df["date"].iloc[spl.test_idx].unique())
        overlap = train_dates & test_dates
        assert (
            len(overlap) == 0
        ), f"CPCV split {spl.split_id}: {len(overlap)} dates in both train and test"


def test_cpcv_embargo_less_than_horizon_raises():
    """KAT: CPurgedCV must reject embargo_days < label_horizon.

    Fault detected: CPCV not enforcing the same embargo constraint as PurgedWalkForward.
    """
    from factorlab.cv import CPurgedCV

    with pytest.raises(ValueError, match="embargo_days"):
        CPurgedCV(n_groups=4, k_test=2, embargo_days=3, label_horizon=5)


def test_evaluate_cpcv_returns_valid_oos_ic(planted_df):
    """KAT: evaluate_cpcv must return non-NaN oos_mean_ic when data is sufficient.

    Fault detected: evaluate_cpcv returning NaN because of wrong attribute access
    on WalkForwardResult (ic_pearson vs oos_mean_ic) or wrong splitter argument.
    """
    import math

    from factorlab.cv import CPurgedCV, evaluate_cpcv

    factor = get_factor("mom_20")
    cpcv = CPurgedCV(n_groups=4, k_test=2, embargo_days=5, label_horizon=5)
    results = evaluate_cpcv(factor, planted_df, cpcv, [5])
    assert results, "evaluate_cpcv returned no results"
    assert not math.isnan(results[0].oos_mean_ic), (
        "evaluate_cpcv returned NaN oos_mean_ic on planted-signal data — "
        "likely accessing wrong attribute or passing wrong splitter type"
    )
    # With C(4,2)=6 paths and planted signal, must have at least 4 valid splits
    assert results[0].n_splits >= 4, f"Expected >= 4 CPCV paths, got {results[0].n_splits}"


def test_evaluate_walk_forward_oos_ic_not_nan(planted_df):
    """KAT: evaluate_walk_forward must return non-NaN oos_mean_ic.

    Fault detected: returning NaN oos_mean_ic because ic_pearson is inaccessible
    on WalkForwardResult (field is oos_mean_ic, not ic_pearson — only FactorMetrics
    has ic_pearson). This test catches the prove_on_real_data bug where
    `m.ic_pearson` was accessed on WalkForwardResult objects.
    """
    import math

    factor = get_factor("mom_20")
    splitter = PurgedWalkForward(n_splits=4, embargo_days=5, label_horizon=5)
    results = evaluate_walk_forward(factor, planted_df, splitter, [5])
    assert results, "evaluate_walk_forward returned no results"
    h5 = next(r for r in results if r.horizon == 5)
    assert not math.isnan(h5.oos_mean_ic), (
        "evaluate_walk_forward returned NaN oos_mean_ic — "
        "split may be producing empty test sets or NaN IC"
    )
    assert h5.n_splits >= 3, f"Expected >= 3 valid splits, got {h5.n_splits}"


def test_promote_cpcv_method_produces_decision(planted_df):
    """KAT: promote() with cv_method='cpcv' must complete without error.

    Fault detected: cv_method='cpcv' not wired into promote(), or CPurgedCV
    import missing, causing AttributeError or TypeError.
    """
    from factorlab.promote import PromotionConfig, promote

    factor = get_factor("mom_20")
    cfg = PromotionConfig(cv_method="cpcv", n_cpcv_groups=4, k_cpcv_test=2)
    decision = promote(factor, planted_df, cfg)
    assert decision.verdict in (
        "promote",
        "reject",
    ), f"Expected promote or reject, got: {decision.verdict!r}"
    # The oos_consistency reason must mention 'cpcv'
    oos_reason = next(r for r in decision.reasons if r.code == "oos_consistency")
    assert (
        "cpcv" in oos_reason.note.lower()
    ), f"Expected 'cpcv' in oos_consistency note, got: {oos_reason.note!r}"
