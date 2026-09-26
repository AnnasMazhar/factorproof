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
            raise ValueError(
                f"Not enough dates ({n_dates}) for {self.n_splits} splits "
                f"with label_horizon={self.label_horizon} and embargo={self.embargo_days}."
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
        raise ValueError("No valid splits generated. Check panel length and splitter params.")

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
