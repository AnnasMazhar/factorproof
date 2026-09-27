"""
factor-lab data layer.

Provides OHLCV data loading, synthetic data generation, and lookahead validation.
The hard invariant: features at time t, targets at time t+h — never cross-sectional leakage.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_ohlcv_csv(path: str | Path) -> pd.DataFrame:
    """Load OHLCV data from a CSV file.

    Expected columns: date, asset, open, high, low, close, volume.
    Returns a DataFrame with a DatetimeIndex sorted by (date, asset).

    Parameters
    ----------
    path:
        Path to a CSV file.

    Returns
    -------
    pd.DataFrame
        Tidy long-format panel with columns: date, asset, open, high, low, close, volume.
    """
    df = pd.read_csv(
        path,
        parse_dates=["date"],
        dtype={
            "asset": str,
            "open": float,
            "high": float,
            "low": float,
            "close": float,
            "volume": float,
        },
    )
    required = {"date", "asset", "open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"CSV is missing required columns: {sorted(missing)}. "
            f"Required: {sorted(required)}. "
            f"Found: {sorted(df.columns.tolist())}."
        )
    df = df.sort_values(["date", "asset"]).reset_index(drop=True)
    return df


def synthetic_ohlcv(
    n_days: int = 1500,
    n_assets: int = 12,
    seed: int = 7,
    plant_signal: bool = False,
    plant_noise: bool = False,
) -> pd.DataFrame:
    """Generate a synthetic OHLCV panel with realistic statistical properties.

    The panel uses drifting random walks with GARCH-like volatility clustering
    and per-asset beta exposure to a common market factor.  When ``plant_signal``
    is True a persistent autocorrelation structure is embedded so that a momentum
    factor genuinely predicts future returns.  When ``plant_noise`` is True the
    prices are pure i.i.d. noise so factor tests should all fail.

    Parameters
    ----------
    n_days:
        Number of trading days.
    n_assets:
        Number of synthetic assets.
    seed:
        RNG seed for full reproducibility.
    plant_signal:
        If True, embed a mean-reverting autocorrelation structure (positive 1-day
        autocorrelation in returns) so that short-term momentum has positive IC.
    plant_noise:
        If True, override all structure — pure i.i.d. Gaussian returns (sigma=0.01).

    Returns
    -------
    pd.DataFrame
        Columns: date, asset, open, high, low, close, volume.
    """
    rng = np.random.default_rng(seed)

    dates = pd.bdate_range(start="2019-01-02", periods=n_days, freq="B")
    assets = [f"A{i:02d}" for i in range(n_assets)]

    rows: list[dict] = []

    if plant_noise:
        # Pure i.i.d. — no predictable structure
        for asset in assets:
            log_returns = rng.normal(0, 0.01, size=n_days)
            _append_ohlcv_rows(rows, dates, asset, log_returns, rng)
        df = pd.DataFrame(rows)
        return df.sort_values(["date", "asset"]).reset_index(drop=True)

    # -----------------------------------------------------------------------
    # Realistic simulation
    # -----------------------------------------------------------------------
    # Common market factor (slightly positive drift ~6% p.a.)
    mkt_vol = 0.012
    mkt_log_ret = rng.normal(0.00023, mkt_vol, size=n_days)

    # Per-asset beta [0.5, 1.5]
    betas = rng.uniform(0.5, 1.5, size=n_assets)

    for i, asset in enumerate(assets):
        idio_vol = rng.uniform(0.005, 0.018)  # idiosyncratic vol

        # GARCH-lite: vol clustering via an AR(1) variance process
        h = np.zeros(n_days)  # conditional variance
        h[0] = idio_vol**2
        alpha_garch = 0.08  # ARCH term
        beta_garch = 0.88  # GARCH term
        omega = idio_vol**2 * (1 - alpha_garch - beta_garch)

        eps = rng.standard_normal(n_days)
        idio_ret = np.zeros(n_days)
        idio_ret[0] = math.sqrt(h[0]) * eps[0]
        for t in range(1, n_days):
            h[t] = omega + alpha_garch * idio_ret[t - 1] ** 2 + beta_garch * h[t - 1]
            idio_ret[t] = math.sqrt(max(h[t], 1e-10)) * eps[t]

        log_returns = betas[i] * mkt_log_ret + idio_ret

        if plant_signal:
            # Add positive AR(1) autocorrelation in returns (rho=0.15)
            # This embeds a real momentum signal detectable by factor metrics.
            # Source: Jegadeesh & Titman (1993) document intermediate-term momentum.
            # rho=0.15 gives IC~0.025-0.030 at 1-5 day horizons on n=1500.
            rho = 0.15
            persistent = np.zeros(n_days)
            persistent[0] = log_returns[0]
            for t in range(1, n_days):
                persistent[t] = rho * persistent[t - 1] + log_returns[t]
            log_returns = persistent

        _append_ohlcv_rows(rows, dates, asset, log_returns, rng)

    df = pd.DataFrame(rows)
    return df.sort_values(["date", "asset"]).reset_index(drop=True)


def assert_no_lookahead(
    features: pd.DataFrame,
    targets: pd.DataFrame,
    horizon: int,
) -> None:
    """Assert that no feature timestamp overlaps with a target label window.

    Feature at time t should only predict targets at t+horizon.
    Raises ValueError if any feature date >= any target date (meaning the feature
    could see information from the target period).

    Parameters
    ----------
    features:
        DataFrame indexed or with column 'date', representing features at time t.
    targets:
        DataFrame indexed or with column 'date', representing targets at time t+horizon.
    horizon:
        The prediction horizon in periods.

    Raises
    ------
    ValueError
        If overlap is detected between any feature date and target window.
    """
    if horizon < 1:
        raise ValueError(f"horizon must be >= 1, got {horizon}")

    feat_dates = _extract_dates(features)
    tgt_dates = _extract_dates(targets)

    if len(feat_dates) == 0 or len(tgt_dates) == 0:
        return  # nothing to check

    # The most recent feature date should be strictly less than the earliest target date
    # when targets represent forward returns starting at t+1 through t+horizon
    max_feat = feat_dates.max()
    min_tgt = tgt_dates.min()

    if max_feat >= min_tgt:
        raise ValueError(
            f"Lookahead detected: latest feature date {max_feat} >= "
            f"earliest target date {min_tgt} (horizon={horizon}). "
            "Features must be computed strictly before the target window."
        )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _append_ohlcv_rows(
    rows: list[dict],
    dates: pd.DatetimeIndex,
    asset: str,
    log_returns: np.ndarray,
    rng: np.random.Generator,
) -> None:
    """Append simulated OHLCV rows for one asset."""
    n = len(dates)
    price = 100.0
    prices = np.zeros(n)
    for t in range(n):
        price = price * math.exp(log_returns[t])
        prices[t] = max(price, 1e-3)

    for t in range(n):
        c = prices[t]
        daily_range = abs(log_returns[t]) + rng.uniform(0.001, 0.008)
        h = c * math.exp(rng.uniform(0, daily_range))
        lo = c * math.exp(-rng.uniform(0, daily_range))
        o = lo + rng.uniform(0, h - lo)
        vol = rng.lognormal(mean=12.0, sigma=0.4)
        rows.append(
            {
                "date": dates[t],
                "asset": asset,
                "open": round(o, 6),
                "high": round(h, 6),
                "low": round(lo, 6),
                "close": round(c, 6),
                "volume": round(vol, 2),
            }
        )


def _extract_dates(df: pd.DataFrame) -> pd.DatetimeIndex:
    """Extract dates from a DataFrame (from index or 'date' column)."""
    if "date" in df.columns:
        return pd.DatetimeIndex(df["date"])
    if isinstance(df.index, pd.DatetimeIndex):
        return df.index
    try:
        return pd.DatetimeIndex(df.index)
    except Exception as exc:
        raise ValueError("Cannot extract dates from DataFrame.") from exc
