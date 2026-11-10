"""microstructure.py — market-microstructure diagnostics for the real-data proof.

Implements, from first principles (numpy only, no scipy/statsmodels):

- Roll (1984) implied effective spread: ``S = 2 * sqrt(-cov(r_t, r_{t-1}))``.
  Under Roll's model (efficient price = random walk + bid-ask bounce), the
  first-order return autocovariance equals ``-S^2 / 4``. When the sample
  autocovariance is positive the estimator is imaginary — that is a real
  outcome (no bounce mechanism), reported as NaN, never clamped to zero.
- Lag-1 return autocorrelation per coin (Pearson, sample covariance ddof=1;
  the ddof cancels in the correlation).
- Zero-volume share per coin + the 5% staleness flag (research item F-R14).
- Full-panel feed-gap detection: dates inside [min, max] with zero rows for
  every coin (research item F-R14, e.g. the 2026-04-30 gap).
- The DSR bias-direction caveat naming bounce-type vs trend-type panels
  (research item F-R15).

References (verified URLs in docs/RESEARCH.md §12.9):
- Roll, R. (1984). "A Simple Implicit Measure of the Effective Bid-Ask
  Spread in an Efficient Market." Journal of Finance 39(4):1127–1139.
- Getmansky, Lo & Makarov (2004). NBER w9571 — smoothing direction:
  positive lag-1 autocorrelation understates vol (Sharpe overstated);
  negative lag-1 (bounce-type) overstates vol (Sharpe conservative).
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

#: Zero-volume-day share above which a coin is flagged as stale (F-R14).
STALENESS_THRESHOLD = 0.05

#: |lag-1 autocorrelation| above which a DSR input must carry the
#: smoothing/bounce caveat (F-R15, from the §12.4 GLM design consequence).
AUTOCORR_CAVEAT_THRESHOLD = 0.2


def log_returns(closes: np.ndarray) -> np.ndarray:
    """Log returns of a close-price vector. Requires positive prices."""
    closes = np.asarray(closes, dtype=float)
    if closes.size < 2:
        raise ValueError("need at least 2 closes to compute returns")
    if bool(np.any(closes <= 0) or np.any(~np.isfinite(closes))):
        raise ValueError("closes must be finite and positive")
    return np.diff(np.log(closes))


def lag1_autocorr(x: np.ndarray) -> float:
    """Pearson lag-1 autocorrelation. NaN when degenerate (n < 3 or zero variance)."""
    x = np.asarray(x, dtype=float)
    n = x.size
    if n < 3:
        return float("nan")
    a, b = x[:-1], x[1:]
    sa, sb = float(np.std(a, ddof=1)), float(np.std(b, ddof=1))
    if sa == 0.0 or sb == 0.0 or not np.isfinite(sa) or not np.isfinite(sb):
        return float("nan")
    cov = float(np.sum((a - a.mean()) * (b - b.mean())) / (n - 2))
    return cov / (sa * sb)


def lag1_autocov(x: np.ndarray) -> float:
    """Sample lag-1 autocovariance (ddof=1). NaN when degenerate."""
    x = np.asarray(x, dtype=float)
    n = x.size
    if n < 3:
        return float("nan")
    a, b = x[:-1], x[1:]
    if float(np.std(a, ddof=1)) == 0.0 or float(np.std(b, ddof=1)) == 0.0:
        return float("nan")
    return float(np.sum((a - a.mean()) * (b - b.mean())) / (n - 2))


def roll_spread(returns: np.ndarray) -> float:
    """Roll (1984) implied effective spread: 2*sqrt(-cov(r_t, r_{t-1})).

    Returns NaN when the lag-1 autocovariance is non-negative (imaginary
    spread: no bid-ask bounce detectable) or the series is degenerate.
    A NaN here is informative, not missing — see F-R12.
    """
    cov1 = lag1_autocov(np.asarray(returns, dtype=float))
    if not np.isfinite(cov1) or cov1 >= 0.0:
        return float("nan")
    return float(2.0 * np.sqrt(-cov1))


def zero_volume_share(volume: np.ndarray) -> float:
    """Fraction of bars with zero (or non-positive) volume. Always in [0, 1]."""
    v = np.asarray(volume, dtype=float)
    if v.size == 0:
        raise ValueError("empty volume vector")
    return float(np.mean(v <= 0))


def staleness_flags(
    shares: Mapping[str, float], threshold: float = STALENESS_THRESHOLD
) -> dict[str, bool]:
    """Flag coins whose zero-volume share exceeds the staleness threshold."""
    return {coin: share > threshold for coin, share in shares.items()}


def find_missing_dates(dates: pd.Series) -> list[pd.Timestamp]:
    """Dates inside [min(dates), max(dates)] with zero rows (full-panel feed gaps).

    A gap spanning every coin simultaneously is missing data, not staleness —
    the proof must report it as such (F-R14).
    """
    if dates.empty:
        return []
    days = pd.to_datetime(dates).dt.normalize()
    full = pd.date_range(days.min(), days.max(), freq="D")
    present = set(days.unique())
    return [d for d in full if d not in present]


def panel_bias_direction(rhos: Mapping[str, float]) -> str:
    """Classify the panel by the mean of finite per-coin lag-1 autocorrelations.

    Returns "bounce-type" (mean rho < 0: vol overstated, DSR conservative),
    "trend-type" (mean rho > 0: vol understated, DSR optimistic), or
    "unclassified" when no finite rho is available.
    """
    vals = [r for r in rhos.values() if isinstance(r, float) and np.isfinite(r)]
    if not vals:
        return "unclassified"
    return "bounce-type" if float(np.mean(vals)) < 0.0 else "trend-type"


def dsr_bias_caveat(
    direction: str,
    max_abs_rho: float,
    threshold: float = AUTOCORR_CAVEAT_THRESHOLD,
) -> str:
    """One-sentence DSR bias caveat that names the direction (F-R15).

    The sentence must say which way the bias cuts — "conservative on
    bounce-type panels, optimistic on trend-type panels" — not just the
    threshold, because the sign of the panel autocorrelation decides
    whether reported DSR magnitudes are lower or upper bounds.
    """
    if direction == "bounce-type":
        bias = "conservative (bounce-type panel: return vol is slightly OVERstated)"
    elif direction == "trend-type":
        bias = "optimistic (trend-type panel: return vol is slightly UNDERstated)"
    else:
        bias = "of unknown direction (panel autocorrelation unclassified)"
    trigger = (
        f"Maximum |lag-1 autocorrelation| is {max_abs_rho:.4f} "
        f"(caveat threshold {threshold}), so the trigger does not fire; "
        if np.isfinite(max_abs_rho) and max_abs_rho <= threshold
        else f"Maximum |lag-1 autocorrelation| is {max_abs_rho:.4f}, above the "
        f"{threshold} caveat threshold; "
    )
    return (
        f"{trigger}reported DSR magnitudes are {bias} bounds on the true "
        "risk-adjusted figures, not point estimates. Verdicts are unaffected "
        "where DSR is zero — a bias on a zero still rejects."
    )
