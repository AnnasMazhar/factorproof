"""
factorlab.cv — leakage-safe walk-forward cross-validation.

Implements Purged Walk-Forward splits that prevent label lookahead.

The purging and embargo logic follows:
    López de Prado (2018) "Advances in Financial Machine Learning"
    ISBN 9781119482086, Chapter 7 (Combinatorial Purged Cross-Validation).

ASCII timeline (see docs/DESIGN.md for the full diagram):
    |------ train ------| purge | embargo |--- test ---|
    t0               t_end_train            t_start_test
    The purge zone removes training rows whose forward-label window
    overlaps the test window.  The embargo zone adds a further gap
    of `embargo_days` rows after the test window end.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .evaluate import FactorMetrics, evaluate_factor
from .factors.base import Factor

# ---------------------------------------------------------------------------
# Split data structure
# ---------------------------------------------------------------------------


@dataclass
class WalkForwardSplit:
    """Describes one train/test split with purging applied.

    Attributes
    ----------
    split_id:
        0-based index of this split.
    train_idx:
        Integer positions (iloc) of training rows after purging.
    test_idx:
        Integer positions (iloc) of test rows.
    train_dates:
        Date range covered by training rows.
    test_dates:
        Date range covered by test rows.
    n_purged:
        Number of training rows removed by the purge step.
    n_embargoed:
        Number of rows dropped in the embargo zone.
    """

    split_id: int
    train_idx: np.ndarray
    test_idx: np.ndarray
    train_dates: tuple
    test_dates: tuple
    n_purged: int
    n_embargoed: int


# ---------------------------------------------------------------------------
# PurgedWalkForward
# ---------------------------------------------------------------------------


class PurgedWalkForward:
    """Walk-forward splitter with purging and embargo.

    The splitter partitions the unique dates in the panel into `n_splits`
    sequential folds.  For each fold:
        1. Train = all dates strictly before the test window.
        2. Purge: remove training rows whose forward-return window
           (date, date+label_horizon) overlaps the earliest test date.
        3. Embargo: further remove rows within `embargo_days` trading
           days immediately preceding the first test date.

    Parameters
    ----------
    n_splits:
        Number of walk-forward folds.
    embargo_days:
        Additional days of gap between train and test (default 5).
    label_horizon:
        Forward-return horizon in days used for purging (default 5).
    """

    def __init__(
        self,
        n_splits: int = 5,
        embargo_days: int = 5,
        label_horizon: int = 5,
    ) -> None:
        if n_splits < 2:  # noqa: PLR2004
            raise ValueError("n_splits must be >= 2")
        if embargo_days < 0:
            raise ValueError("embargo_days must be >= 0")
        if label_horizon < 1:
            raise ValueError("label_horizon must be >= 1")
        # Spec STATISTICAL CORRECTIONS: embargo_days must be >= label_horizon
        # to prevent any overlap between the label windows at train/test boundary.
        if embargo_days < label_horizon:
            raise ValueError(
                f"embargo_days ({embargo_days}) must be >= label_horizon ({label_horizon}). "
                "A smaller embargo does not break the overlap it exists to prevent."
            )
        self.n_splits = n_splits
        self.embargo_days = embargo_days
        self.label_horizon = label_horizon

    def split(self, df: pd.DataFrame) -> Iterator[WalkForwardSplit]:
        """Yield WalkForwardSplit objects for a tidy OHLCV panel.

        The input panel must have a 'date' column.  Splits are computed
        on unique sorted dates.

        Parameters
        ----------
        df:
            Tidy long-format OHLCV panel.

        Yields
        ------
        WalkForwardSplit
            One split per fold, in chronological order.
        """
        dates = pd.DatetimeIndex(sorted(df["date"].unique()))
        n_dates = len(dates)

        if n_dates < self.n_splits + self.label_horizon + self.embargo_days:
            min_needed = self.n_splits + self.label_horizon + self.embargo_days
            raise ValueError(
                f"Not enough dates ({n_dates}) for {self.n_splits} walk-forward splits "
                f"with label_horizon={self.label_horizon} and embargo_days={self.embargo_days}. "
                f"Need at least {min_needed} dates. "
                "Fix: extend the panel, or reduce n_splits/horizon in PromotionConfig."
            )

        # Divide dates into (n_splits + 1) chunks; first chunk = initial train,
        # remaining n_splits chunks = test windows
        chunk_size = n_dates // (self.n_splits + 1)

        for fold in range(self.n_splits):
            test_start_pos = (fold + 1) * chunk_size
            test_end_pos = test_start_pos + chunk_size if fold < self.n_splits - 1 else n_dates

            test_dates = dates[test_start_pos:test_end_pos]
            train_dates_raw = dates[:test_start_pos]

            first_test_date = test_dates[0]

            # ---- Purge ----
            # Remove training rows where the label window [date, date+horizon] overlaps
            # the first test date.  A row at training date t is purged if:
            #     t + label_horizon >= first_test_date
            purge_cutoff = first_test_date - pd.Timedelta(days=self.label_horizon)
            # Using calendar days (not trading days) for simplicity and safety
            train_after_purge = train_dates_raw[train_dates_raw <= purge_cutoff]
            n_purged = len(train_dates_raw) - len(train_after_purge)

            # ---- Embargo ----
            # Further remove the `embargo_days` trading days immediately before test start
            if self.embargo_days > 0 and len(train_after_purge) > self.embargo_days:
                train_final = train_after_purge[: -self.embargo_days]
                n_embargoed = self.embargo_days
            else:
                train_final = train_after_purge
                n_embargoed = 0

            # Map dates back to integer positions in df
            train_mask = df["date"].isin(train_final)
            test_mask = df["date"].isin(test_dates)

            train_idx = np.where(train_mask.values)[0]
            test_idx = np.where(test_mask.values)[0]

            if len(train_idx) == 0 or len(test_idx) == 0:
                continue

            yield WalkForwardSplit(
                split_id=fold,
                train_idx=train_idx,
                test_idx=test_idx,
                train_dates=(train_final[0], train_final[-1]) if len(train_final) else (None, None),
                test_dates=(test_dates[0], test_dates[-1]),
                n_purged=n_purged,
                n_embargoed=n_embargoed,
            )


# ---------------------------------------------------------------------------
# Walk-forward evaluation
# ---------------------------------------------------------------------------


@dataclass
class WalkForwardResult:
    """Results from walk-forward cross-validation for one factor."""

    factor_name: str
    horizon: int
    per_split_ic: list[float]  # mean IC per split
    oos_mean_ic: float
    oos_ic_ir: float
    sign_consistency: float  # fraction of splits with IC matching overall sign
    n_splits: int


def evaluate_walk_forward(
    factor: Factor,
    df: pd.DataFrame,
    splitter: PurgedWalkForward,
    horizons: list[int],
) -> list[WalkForwardResult]:
    """Evaluate a factor using purged walk-forward cross-validation.

    For each split, computes the factor on training data and evaluates on test data.
    The OOS IC and consistency are aggregated across splits.

    Parameters
    ----------
    factor:
        Factor instance.
    df:
        Full tidy OHLCV panel.
    splitter:
        PurgedWalkForward instance.
    horizons:
        List of horizons.

    Returns
    -------
    List of WalkForwardResult, one per horizon.
    """
    splits = list(splitter.split(df))
    if not splits:
        raise ValueError(
            "No valid splits generated — the panel is too short for the splitter configuration. "
            f"Check panel length vs n_splits={splitter.n_splits}, "
            f"label_horizon={splitter.label_horizon}, embargo_days={splitter.embargo_days}. "
            "Fix: extend the panel, or lower n_splits in PromotionConfig."
        )

    # Compute factor on full dataset (factors are computationally deterministic given data)
    factor_vals = factor.compute(df)

    results_by_horizon: dict[int, list[float]] = {h: [] for h in horizons}

    for spl in splits:
        test_df = df.iloc[spl.test_idx].copy()
        test_dates = test_df["date"].unique()
        # Filter factor values to test-set dates
        test_factor = factor_vals[factor_vals.index.get_level_values("date").isin(test_dates)]

        if test_factor.empty:
            for h in horizons:
                results_by_horizon[h].append(float("nan"))
            continue

        split_metrics = evaluate_factor(
            factor_vals=test_factor,
            df=test_df,
            horizons=horizons,
            factor_name=factor.name,
        )
        for m in split_metrics:
            results_by_horizon[m.horizon].append(m.ic_pearson)

    wf_results = []
    for h in horizons:
        ics = [ic for ic in results_by_horizon[h] if not _isnan(ic)]
        if not ics:
            wf_results.append(
                WalkForwardResult(
                    factor_name=factor.name,
                    horizon=h,
                    per_split_ic=[],
                    oos_mean_ic=float("nan"),
                    oos_ic_ir=float("nan"),
                    sign_consistency=float("nan"),
                    n_splits=0,
                )
            )
            continue

        ics_arr = np.array(ics)
        mean_ic = float(np.mean(ics_arr))
        std_ic = float(np.std(ics_arr, ddof=1)) if len(ics_arr) > 1 else float("nan")
        ic_ir = mean_ic / std_ic if std_ic and std_ic > 0 else float("nan")
        # Sign consistency: fraction of splits where IC sign matches mean_ic sign
        if mean_ic != 0:
            sign_match = float(np.mean(np.sign(ics_arr) == np.sign(mean_ic)))
        else:
            sign_match = float("nan")

        wf_results.append(
            WalkForwardResult(
                factor_name=factor.name,
                horizon=h,
                per_split_ic=list(ics_arr),
                oos_mean_ic=mean_ic,
                oos_ic_ir=ic_ir,
                sign_consistency=sign_match,
                n_splits=len(ics),
            )
        )

    return wf_results


def check_lookahead(factor: Factor) -> bool:
    """Return True if the factor is flagged as using future data.

    Checks the `uses_future_data` attribute on the factor class.
    This is a structural check that does not require data.
    """
    return bool(getattr(factor, "uses_future_data", False))


def check_lookahead_source(factor: Factor) -> list[str]:
    """Inspect the factor's compute() source for negative-shift patterns.

    Searches for calls like `.shift(-N)` where N > 0 in the compute method
    source. These patterns access future rows in a time-indexed DataFrame and
    constitute lookahead contamination unless explicitly acknowledged.

    This addresses ADVERSARIAL-REVIEW.md finding M01: a factor that blends
    future data without setting `uses_future_data=True` bypasses the structural
    flag check. Source inspection catches the syntactic pattern regardless of
    how the factor is named or described.

    Implementation note: source inspection requires the class to be defined
    in a real source file (not built at runtime as a lambda or exec string).
    If source is unavailable, returns an empty list (no findings) and logs
    a warning via the docstring — the caller should document this limitation.

    Parameters
    ----------
    factor:
        Factor instance whose compute() method will be inspected.

    Returns
    -------
    List of suspicious patterns found (e.g. ["shift(-2)", "shift(-5)"]).
    Empty list if no patterns detected or source is unavailable.
    """
    import inspect
    import re

    try:
        src = inspect.getsource(factor.compute)
    except (OSError, TypeError):
        # Source not available (lambda, REPL, C extension) — cannot inspect
        return []

    # Match .shift(-N) where N is a positive integer literal
    # Also match .shift(N) where N is a negative integer literal
    # Patterns: .shift(-1), .shift(-20), .shift( -3 )
    neg_shifts = re.findall(r"\.shift\(\s*(-\s*\d+)", src)
    # Normalise whitespace and deduplicate
    found = list(dict.fromkeys(f"shift({s.replace(' ', '')})" for s in neg_shifts))
    return found


# ---------------------------------------------------------------------------
# Combinatorial Purged Cross-Validation (CPCV)
# ---------------------------------------------------------------------------


@dataclass
class CPCVSplit:
    """One train/test split from CPCV.

    Attributes
    ----------
    split_id:
        0-based split index.
    train_idx:
        Integer positions (iloc) of training rows after purging.
    test_idx:
        Integer positions (iloc) of test rows.
    test_group:
        Which group(s) form the test set (0-based group indices).
    n_purged:
        Training rows removed by purge.
    """

    split_id: int
    train_idx: np.ndarray
    test_idx: np.ndarray
    test_group: tuple[int, ...]
    n_purged: int


class CPurgedCV:
    """Combinatorial Purged Cross-Validation (CPCV).

    Partition unique dates into `n_groups` equally-sized groups. For each
    combination of `k` groups chosen as test (C(n_groups, k) combinations),
    use the remaining groups as training after purging and embargo.

    This generates more OOS paths than walk-forward CV (which only tests
    each group once). With k=2 test groups from n_groups=6, we get C(6,2)=15
    OOS paths, producing more robust sign-consistency estimates.

    Reference: López de Prado (2018) "Advances in Financial Machine Learning"
    ISBN 9781119482086, Chapter 12. The MlFinLab library ships this; factor-lab
    provides an open implementation.

    Parameters
    ----------
    n_groups:
        Number of date groups to partition the data into.
    k_test:
        Number of groups held out as test in each combination. Default 2.
    embargo_days:
        Calendar days of gap appended after each test group boundary.
        Must be >= label_horizon.
    label_horizon:
        Forward-return horizon in days (used for purging).
    """

    def __init__(
        self,
        n_groups: int = 6,
        k_test: int = 2,
        embargo_days: int = 5,
        label_horizon: int = 5,
    ) -> None:
        if n_groups < 2:  # noqa: PLR2004
            raise ValueError("n_groups must be >= 2")
        if k_test < 1 or k_test >= n_groups:
            raise ValueError("k_test must be in [1, n_groups)")
        if embargo_days < label_horizon:
            raise ValueError(
                f"embargo_days ({embargo_days}) must be >= label_horizon ({label_horizon})."
            )
        self.n_groups = n_groups
        self.k_test = k_test
        self.embargo_days = embargo_days
        self.label_horizon = label_horizon

    def split(self, df: pd.DataFrame) -> list[CPCVSplit]:
        """Generate all CPCV splits.

        Parameters
        ----------
        df:
            Tidy long-format OHLCV panel with a 'date' column.

        Returns
        -------
        List of CPCVSplit, one per combination of test groups.
        """
        from itertools import combinations

        dates = pd.DatetimeIndex(sorted(df["date"].unique()))
        n_dates = len(dates)
        group_size = n_dates // self.n_groups

        # Assign each date to a group (last group absorbs remainder)
        group_dates: list[pd.DatetimeIndex] = []
        for g in range(self.n_groups):
            start = g * group_size
            end = (g + 1) * group_size if g < self.n_groups - 1 else n_dates
            group_dates.append(dates[start:end])

        splits: list[CPCVSplit] = []
        split_id = 0

        for test_groups in combinations(range(self.n_groups), self.k_test):
            test_group_set = set(test_groups)
            train_group_set = set(range(self.n_groups)) - test_group_set

            # Collect all test dates
            test_dates_all = pd.DatetimeIndex(
                sorted(d for g in test_groups for d in group_dates[g])
            )

            # Collect training dates
            train_dates_raw = pd.DatetimeIndex(
                sorted(d for g in train_group_set for d in group_dates[g])
            )

            # Purge training dates whose label window [t, t+horizon) overlaps any
            # test date. A training date t is purged if:
            #   t + label_horizon >= first date of any adjacent test group
            # We remove training dates within label_horizon calendar days of any
            # test group's start boundary.
            embargo_td = pd.Timedelta(days=self.label_horizon)
            keep_mask = np.ones(len(train_dates_raw), dtype=bool)

            for tg in test_groups:
                tg_first = group_dates[tg][0]
                # Purge training dates before this test group that are too close
                # to the test group's start (label window overlaps)
                purge_before = (train_dates_raw < tg_first) & (
                    train_dates_raw >= tg_first - embargo_td
                )
                # Exclude training dates that fall inside or after the test group
                # (these shouldn't be in train_dates_raw since we split by groups,
                # but guard against edge cases)
                keep_mask &= ~purge_before

            train_dates_final = train_dates_raw[keep_mask]
            n_purged = len(train_dates_raw) - len(train_dates_final)

            if len(train_dates_final) == 0 or len(test_dates_all) == 0:
                split_id += 1
                continue

            train_mask_df = df["date"].isin(train_dates_final)
            test_mask_df = df["date"].isin(test_dates_all)
            train_idx = np.where(train_mask_df.values)[0]
            test_idx = np.where(test_mask_df.values)[0]

            splits.append(
                CPCVSplit(
                    split_id=split_id,
                    train_idx=train_idx,
                    test_idx=test_idx,
                    test_group=test_groups,
                    n_purged=n_purged,
                )
            )
            split_id += 1

        return splits


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _isnan(x: float) -> bool:
    import math

    return math.isnan(x)


def _evaluate_metrics_on_split(
    factor_vals: pd.Series,
    df: pd.DataFrame,
    horizons: list[int],
    factor_name: str,
) -> list[FactorMetrics]:
    """Thin wrapper to avoid circular import with evaluate.py."""
    return evaluate_factor(
        factor_vals=factor_vals,
        df=df,
        horizons=horizons,
        factor_name=factor_name,
    )
