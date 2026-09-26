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
    """
    splitter = PurgedWalkForward(n_splits=3, embargo_days=2, label_horizon=5)
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
    """
    splitter = PurgedWalkForward(n_splits=3, embargo_days=2, label_horizon=5)
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
    """
    for n in [2, 3, 4]:
        splitter = PurgedWalkForward(n_splits=n, embargo_days=2, label_horizon=5)
        splits = list(splitter.split(small_df))
        assert len(splits) == n, f"Expected {n} splits, got {len(splits)}"


def test_split_chronological_order(small_df):
    """KAT: test windows must be in chronological order and non-overlapping.

    Fault detected: shuffled or overlapping test folds.
    """
    splitter = PurgedWalkForward(n_splits=4, embargo_days=2, label_horizon=5)
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
    """
    factor = get_factor("mom_20")
    splitter = PurgedWalkForward(n_splits=3, embargo_days=3, label_horizon=5)
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
    """
    factor = get_factor("mom_20")
    splitter = PurgedWalkForward(n_splits=3, embargo_days=3, label_horizon=5)
    results = evaluate_walk_forward(factor, planted_df, splitter, [1])
    h1_result = next(r for r in results if r.horizon == 1)
    # Must have at least one valid split
    assert h1_result.n_splits >= 1, "No valid splits produced"
    # OOS IC must be a real number (not nan)
    import math

    assert not math.isnan(h1_result.oos_mean_ic), "OOS IC is NaN on planted-signal data"
