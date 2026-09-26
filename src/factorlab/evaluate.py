"""
factorlab.evaluate — factor evaluation metrics.

All metrics are computed per (factor, horizon) pair.
Deterministic: no internal randomness without an explicit seed argument.

References:
- IC methodology: Grinold & Kahn (2000) "Active Portfolio Management", 2nd ed.
  ISBN 0071376151. Chapter 10 defines IC as the cross-sectional correlation
  between factor scores and forward returns.
- Wilson score interval (hit rate lower bound): Wilson (1927) J. American
  Statistical Association 22(158):209-212. Implemented from first principles.
- Quantile spread: standard in the quantitative finance literature; see also
  Asness et al. (2013) J. Portfolio Management 39(5):18-36.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class FactorMetrics:
    """All evaluation metrics for one (factor, horizon) pair."""

    factor_name: str
    horizon: int
    ic_pearson: float
    ic_spearman: float
    ic_ir: float
    ic_tstat: float
    ic_decay: dict[int, float]  # horizon -> mean IC
    quantile_spread: float
    monotonicity: float  # Spearman of quantile-rank vs mean-return
    hit_rate: float
    hit_rate_wilson_lb: float  # Wilson lower bound (see significance.py)
    turnover: float
    coverage: float
    n_obs: int  # number of non-NaN cross-sections
    verdicts: dict[str, bool] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Forward returns
# ---------------------------------------------------------------------------


def forward_returns(
    df: pd.DataFrame,
    horizons: list[int],
) -> dict[int, pd.DataFrame]:
    """Compute per-asset forward log-returns at each horizon.

    Returns a dict: horizon -> DataFrame with columns (date, asset, fwd_ret).
    The return at date t for horizon h is log(close_{t+h} / close_t).
    No lookahead: the return is tagged to the date of the factor observation (t),
    but is only computable when t+h is available.

    Parameters
    ----------
    df:
        Tidy OHLCV panel (date, asset, close, ...).
    horizons:
        List of forward-return horizons in trading days.
    """
    close = df.pivot(index="date", columns="asset", values="close")
    out: dict[int, pd.DataFrame] = {}
    for h in horizons:
        # log(C_{t+h}) - log(C_t)
        fwd = np.log(close.shift(-h) / close)
        long = fwd.stack(future_stack=True).reset_index()
        long.columns = pd.Index(["date", "asset", "fwd_ret"])
        out[h] = long
    return out


# ---------------------------------------------------------------------------
# Core metrics
# ---------------------------------------------------------------------------


def information_coefficient(
    factor_vals: pd.Series,
    fwd_ret: pd.DataFrame,
    method: Literal["pearson", "spearman"] = "pearson",
) -> tuple[float, float, float, float]:
    """Compute mean IC, IC-IR, and t-stat via cross-sectional correlation per date.

    The IC is computed for each date as the cross-sectional Pearson (or Spearman)
    correlation between factor values and forward returns across assets.
    Then we take mean(IC) as the IC estimate and std(IC) as the noise.

    IC-IR = mean(IC) / std(IC)
    t-stat = IC-IR * sqrt(n_dates)

    Reference: Grinold & Kahn (2000) "Active Portfolio Management", ch. 10.

    Parameters
    ----------
    factor_vals:
        Series with MultiIndex (date, asset).
    fwd_ret:
        DataFrame with columns (date, asset, fwd_ret).
    method:
        'pearson' or 'spearman'.

    Returns
    -------
    (mean_ic, ic_ir, ic_tstat, n_dates)
    """
    # Merge factor and forward returns on (date, asset)
    factor_df = factor_vals.reset_index()
    factor_df.columns = pd.Index(["date", "asset", "factor"])

    merged = pd.merge(factor_df, fwd_ret, on=["date", "asset"], how="inner")
    merged = merged.dropna(subset=["factor", "fwd_ret"])

    if merged.empty:
        return float("nan"), float("nan"), float("nan"), 0

    ics_per_date = []
    for _, grp in merged.groupby("date"):
        if len(grp) < 2:  # noqa: PLR2004
            continue
        f = grp["factor"].values
        r = grp["fwd_ret"].values
        if method == "spearman":
            f = _rankdata(f)
            r = _rankdata(r)
        ic = _pearson_corr(f, r)
        if not math.isnan(ic):
            ics_per_date.append(ic)

    if len(ics_per_date) < 2:  # noqa: PLR2004
        return float("nan"), float("nan"), float("nan"), len(ics_per_date)

    ic_arr = np.array(ics_per_date)
    mean_ic = float(np.mean(ic_arr))
    std_ic = float(np.std(ic_arr, ddof=1))
    ic_ir = mean_ic / std_ic if std_ic > 0 else float("nan")
    n = len(ic_arr)
    ic_tstat = ic_ir * math.sqrt(n) if not math.isnan(ic_ir) else float("nan")
    return mean_ic, ic_ir, ic_tstat, n


def ic_decay(
    factor_vals: pd.Series,
    fwd_returns_dict: dict[int, pd.DataFrame],
) -> dict[int, float]:
    """Compute mean IC at each horizon (IC decay curve).

    Parameters
    ----------
    factor_vals:
        Series with MultiIndex (date, asset).
    fwd_returns_dict:
        Dict mapping horizon -> forward-return DataFrame.

    Returns
    -------
    Ordered dict: horizon -> mean IC.
    """
    result: dict[int, float] = {}
    for h in sorted(fwd_returns_dict):
        mean_ic, _, _, _ = information_coefficient(factor_vals, fwd_returns_dict[h], "pearson")
        result[h] = mean_ic
    return result


def quantile_analysis(
    factor_vals: pd.Series,
    fwd_ret: pd.DataFrame,
    n_quantiles: int = 5,
) -> tuple[float, float, dict[int, float]]:
    """Compute quantile spread and monotonicity.

    Bins factor values into n_quantiles per date (cross-sectional), computes
    mean forward return per quantile bin, and returns the spread (Q_top - Q_bottom)
    and monotonicity (Spearman correlation of quantile rank vs mean return).

    Returns
    -------
    (spread, monotonicity, per_quantile_mean_return dict)
    """
    factor_df = factor_vals.reset_index()
    factor_df.columns = pd.Index(["date", "asset", "factor"])

    merged = pd.merge(factor_df, fwd_ret, on=["date", "asset"], how="inner")
    merged = merged.dropna(subset=["factor", "fwd_ret"])

    if merged.empty:
        return float("nan"), float("nan"), {}

    quantile_rets: dict[int, list[float]] = {q: [] for q in range(1, n_quantiles + 1)}

    for _, grp in merged.groupby("date"):
        if len(grp) < n_quantiles:
            continue
        f = grp["factor"].values
        r = grp["fwd_ret"].values
        ranks = _rankdata(f)  # 1 = smallest
        # Divide into n_quantiles bins by rank percentile
        percentiles = (ranks - 1) / (len(ranks) - 1) if len(ranks) > 1 else ranks * 0
        q_labels = np.floor(percentiles * n_quantiles).astype(int).clip(0, n_quantiles - 1) + 1
        for q in range(1, n_quantiles + 1):
            mask = q_labels == q
            if mask.any():
                quantile_rets[q].append(float(np.mean(r[mask])))

    q_means: dict[int, float] = {}
    for q, rets in quantile_rets.items():
        q_means[q] = float(np.mean(rets)) if rets else float("nan")

    valid_qs = [(q, m) for q, m in q_means.items() if not math.isnan(m)]
    if len(valid_qs) < 2:  # noqa: PLR2004
        return float("nan"), float("nan"), q_means

    q_ranks = np.array([v[0] for v in valid_qs], dtype=float)
    q_ret_vals = np.array([v[1] for v in valid_qs], dtype=float)

    spread = float(q_ret_vals[-1] - q_ret_vals[0])  # top - bottom
    mono = float(_pearson_corr(_rankdata(q_ranks), _rankdata(q_ret_vals)))
    return spread, mono, q_means


def hit_rate_metrics(
    factor_vals: pd.Series,
    fwd_ret: pd.DataFrame,
) -> tuple[float, float, int]:
    """Compute directional hit rate and Wilson lower bound.

    Hit rate = fraction of (date, asset) observations where sign(factor) == sign(fwd_ret).
    Wilson lower bound at 95% confidence (z=1.96).

    Wilson (1927) interval:
        p_hat = k/n
        lb = (p_hat + z^2/(2n) - z*sqrt(p_hat*(1-p_hat)/n + z^2/(4n^2))) /
             (1 + z^2/n)

    No scipy: implemented from first principles.

    Returns
    -------
    (hit_rate, wilson_lower_bound, n_valid_obs)
    """
    factor_df = factor_vals.reset_index()
    factor_df.columns = pd.Index(["date", "asset", "factor"])

    merged = pd.merge(factor_df, fwd_ret, on=["date", "asset"], how="inner")
    merged = merged.dropna(subset=["factor", "fwd_ret"])
    # Only count non-zero factor values (zero = no directional prediction)
    merged = merged[merged["factor"] != 0.0]

    n = len(merged)
    if n == 0:
        return float("nan"), float("nan"), 0

    hits = int((np.sign(merged["factor"].values) == np.sign(merged["fwd_ret"].values)).sum())
    p_hat = hits / n
    hr = float(p_hat)

    z = 1.96  # 95% confidence
    z2 = z * z
    term_under_root = p_hat * (1 - p_hat) / n + z2 / (4 * n * n)
    lb = (p_hat + z2 / (2 * n) - z * math.sqrt(term_under_root)) / (1 + z2 / n)

    return hr, float(lb), n


def coverage_fraction(factor_vals: pd.Series) -> float:
    """Fraction of non-NaN factor observations.

    A factor with low coverage wastes capital and introduces survivorship bias.
    """
    total = len(factor_vals)
    if total == 0:
        return 0.0
    return float(factor_vals.notna().sum() / total)


def turnover_metric(factor_vals: pd.Series) -> float:
    """Mean absolute change in cross-sectional rank weight between rebalances.

    For each date pair (t, t-1), compute the rank-normalised weight change
    across all assets. Low turnover is preferable (lower transaction costs).

    Reference: Grinold & Kahn (2000) ch. 14 discuss turnover measurement.
    """
    wide = factor_vals.unstack(level="asset")  # date × asset
    if wide.empty or len(wide) < 2:  # noqa: PLR2004
        return float("nan")

    def _rank_weights(row: pd.Series) -> pd.Series:
        """Rank-normalise a cross-section to portfolio weights."""
        vals = row.dropna()
        if len(vals) == 0:
            return row * 0
        ranks = _rankdata(vals.values)
        # Centre and scale to sum to 1 (long-short weight scheme)
        centred = ranks - ranks.mean()
        denom = np.abs(centred).sum()
        if denom == 0:
            return pd.Series(0.0, index=vals.index)
        weights = centred / denom
        return pd.Series(weights, index=vals.index)

    weight_frames = []
    for date, row in wide.iterrows():
        w = _rank_weights(row)
        w.name = date
        weight_frames.append(w)

    W = pd.DataFrame(weight_frames).fillna(0.0)
    delta = W.diff().iloc[1:]
    mean_turnover = float(delta.abs().sum(axis=1).mean())
    return mean_turnover


# ---------------------------------------------------------------------------
# Main evaluation entry point
# ---------------------------------------------------------------------------


def evaluate_factor(
    factor_vals: pd.Series,
    df: pd.DataFrame,
    horizons: list[int],
    factor_name: str = "",
    n_quantiles: int = 5,
) -> list[FactorMetrics]:
    """Compute all metrics for a factor across multiple horizons.

    Parameters
    ----------
    factor_vals:
        Factor output Series with MultiIndex (date, asset).
    df:
        Original OHLCV panel (used to compute forward returns).
    horizons:
        List of horizons in trading days.
    factor_name:
        Name for reporting.
    n_quantiles:
        Number of quantile bins.

    Returns
    -------
    List of FactorMetrics, one per horizon.
    """
    fwd_dict = forward_returns(df, horizons)
    cov = coverage_fraction(factor_vals)
    to = turnover_metric(factor_vals)

    decay = ic_decay(factor_vals, fwd_dict)

    results = []
    for h in horizons:
        fwd = fwd_dict[h]
        ic_p, ic_ir_p, ic_t_p, n_obs = information_coefficient(factor_vals, fwd, "pearson")
        ic_s, _, _, _ = information_coefficient(factor_vals, fwd, "spearman")
        spread, mono, _ = quantile_analysis(factor_vals, fwd, n_quantiles)
        hr, hr_lb, _ = hit_rate_metrics(factor_vals, fwd)

        results.append(
            FactorMetrics(
                factor_name=factor_name,
                horizon=h,
                ic_pearson=ic_p,
                ic_spearman=ic_s,
                ic_ir=ic_ir_p,
                ic_tstat=ic_t_p,
                ic_decay=decay,
                quantile_spread=spread,
                monotonicity=mono,
                hit_rate=hr,
                hit_rate_wilson_lb=hr_lb,
                turnover=to,
                coverage=cov,
                n_obs=n_obs,
            )
        )
    return results


# ---------------------------------------------------------------------------
# Private math utilities (no scipy)
# ---------------------------------------------------------------------------


def _pearson_corr(x: np.ndarray, y: np.ndarray) -> float:
    """Pearson correlation coefficient, implemented from first principles.

    Reference: Pearson (1895) Philosophical Transactions, Series A, 187:253-318.
    corr(X, Y) = cov(X,Y) / (std(X) * std(Y))
              = sum((x-xbar)*(y-ybar)) / sqrt(sum((x-xbar)^2) * sum((y-ybar)^2))
    """
    if len(x) < 2:  # noqa: PLR2004
        return float("nan")
    xd = x - x.mean()
    yd = y - y.mean()
    denom = math.sqrt((xd**2).sum() * (yd**2).sum())
    if denom == 0:
        return float("nan")
    return float((xd * yd).sum() / denom)


def _rankdata(x: np.ndarray) -> np.ndarray:
    """Rank data (1 = smallest), with average ranks for ties.

    Equivalent to scipy.stats.rankdata with method='average'.
    Reference: standard ordinal ranking used in Spearman correlation.
    """
    n = len(x)
    order = np.argsort(x, kind="stable")
    ranks = np.empty(n, dtype=float)
    i = 0
    while i < n:
        j = i
        while j < n - 1 and x[order[j]] == x[order[j + 1]]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0  # 1-based
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    return ranks
