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
  NOTE: Wilson bounds are valid for the *hit rate* (a binomial proportion).
  For the IC estimand (a correlation), use block_bootstrap_ic_ci() instead.
- Quantile spread: standard in the quantitative finance literature; see also
  Asness et al. (2013) J. Portfolio Management 39(5):18-36.
- Newey-West HAC standard errors: Newey & West (1987) Econometrica 55(3):703-708.
  HAC corrects the IC t-stat for autocorrelation induced by overlapping labels.
  With horizon H, per-date ICs share H-1 overlapping days, inflating the naive
  t-stat by ~sqrt(H). The HAC t-stat uses max_lags = H-1 to correct this.
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
    ic_tstat: float  # Newey-West HAC t-stat (corrected, safe for promotion)
    ic_tstat_naive: float  # diagnostic_only=True — naive mean/std*sqrt(n), inflated by ~sqrt(H)
    ic_decay: dict[int, float]  # horizon -> mean IC
    quantile_spread: float
    monotonicity: float  # Spearman of quantile-rank vs mean-return
    hit_rate: float
    hit_rate_wilson_lb: float  # Wilson lower bound on hit rate (binomial proportion)
    # NOTE: for IC confidence intervals, use block_bootstrap_ic_ci() not Wilson
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
    horizon: int = 1,
) -> tuple[float, float, float, float, float]:
    """Compute mean IC, IC-IR, HAC t-stat, naive t-stat, and n_dates.

    The IC is computed for each date as the cross-sectional Pearson (or Spearman)
    correlation between factor values and forward returns across assets.
    Then we take mean(IC) as the IC estimate and std(IC) as the noise.

    IC-IR = mean(IC) / std(IC)

    Two t-statistics are returned:
    1. HAC t-stat (Newey-West): corrects for autocorrelation caused by overlapping
       label windows. With horizon H, per-date ICs share H-1 overlapping days,
       inflating the naive t-stat by ~sqrt(H). The HAC SE uses max_lags = H-1.
       This is the value that should be used in the promotion gate.

       Reference: Newey & West (1987) Econometrica 55(3):703-708.
       SE_HAC = sqrt((1/T^2) * sum_{l=-L}^{L} w_l * sum_{t} IC_t * IC_{t-|l|})
       where w_l = 1 - |l|/(L+1) (Bartlett kernel), L = H-1.

    2. Naive t-stat (diagnostic_only): ic_ir * sqrt(n_dates).
       Inflated by ~sqrt(H) for H > 1 due to overlapping labels. Do NOT use
       this value in promotion logic. Exposed for diagnostic comparison only.

    Reference: Grinold & Kahn (2000) "Active Portfolio Management", ch. 10.

    Parameters
    ----------
    factor_vals:
        Series with MultiIndex (date, asset).
    fwd_ret:
        DataFrame with columns (date, asset, fwd_ret).
    method:
        'pearson' or 'spearman'.
    horizon:
        Forward-return horizon in days. Used to set max_lags = H-1 for HAC.

    Returns
    -------
    (mean_ic, ic_ir, ic_tstat_hac, ic_tstat_naive, n_dates)
    """
    # Merge factor and forward returns on (date, asset)
    factor_df = factor_vals.reset_index()
    factor_df.columns = pd.Index(["date", "asset", "factor"])

    merged = pd.merge(factor_df, fwd_ret, on=["date", "asset"], how="inner")
    merged = merged.dropna(subset=["factor", "fwd_ret"])

    if merged.empty:
        return float("nan"), float("nan"), float("nan"), float("nan"), 0

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
        return float("nan"), float("nan"), float("nan"), float("nan"), len(ics_per_date)

    ic_arr = np.array(ics_per_date)
    mean_ic = float(np.mean(ic_arr))
    std_ic = float(np.std(ic_arr, ddof=1))
    ic_ir = mean_ic / std_ic if std_ic > 0 else float("nan")
    n = len(ic_arr)

    # Naive t-stat (diagnostic_only): inflated by ~sqrt(H) for H > 1
    ic_tstat_naive = ic_ir * math.sqrt(n) if not math.isnan(ic_ir) else float("nan")

    # Newey-West HAC t-stat: corrects for overlapping-label autocorrelation
    # max_lags = H-1 (one lag per overlapping period)
    max_lags = max(0, horizon - 1)
    se_hac = _newey_west_se(ic_arr, max_lags=max_lags)
    if se_hac > 0 and not math.isnan(se_hac):
        ic_tstat_hac = mean_ic / se_hac
    elif se_hac == 0 and mean_ic == 0:
        ic_tstat_hac = 0.0
    else:
        ic_tstat_hac = float("nan")

    return mean_ic, ic_ir, ic_tstat_hac, ic_tstat_naive, n


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
        mean_ic, _, _, _, _ = information_coefficient(
            factor_vals, fwd_returns_dict[h], "pearson", horizon=h
        )
        result[h] = mean_ic
    return result


def yearly_ic_table(
    factor_vals: pd.Series,
    df: pd.DataFrame,
    horizons: list[int],
) -> dict[int, list[dict[str, float | int]]]:
    """Per-calendar-year mean IC and HAC t-stat (regime-robustness table).

    Splits the factor's observation dates by calendar year and runs
    :func:`information_coefficient` on each year slice at each horizon.
    Forward returns are computed on the full panel first, so year-edge
    labels still use the correct t+h closes — only the grouping is yearly.

    This is the machine behind the "by-year IC" report section: a factor
    whose full-sample t-stat looks significant but whose yearly ICs flip
    sign is not robust across regimes.

    Parameters
    ----------
    factor_vals:
        Factor output Series with MultiIndex (date, asset).
    df:
        Original OHLCV panel (used to compute forward returns).
    horizons:
        List of horizons in trading days.

    Returns
    -------
    Dict mapping horizon -> list of {"year", "n", "ic", "t_hac"} dicts,
    years in ascending order. A year with fewer than 2 valid
    cross-sections keeps its (small) n with NaN statistics.

    An additional summary horizon key ``"summary"`` is added mapping to a
    dict of horizon -> {"ic": <simple mean>, "weighted_ic": <T_j-weighted>}.
    The T_j-weighted IC follows Fama & French (1997) Eq. 5, p. 1980::

        IC_pool = sum_j(T_j * IC_j) / sum_j(T_j)

    where T_j is the number of valid cross-sections in year j.  When regime
    windows differ in length, the weighted estimate gives more influence to
    years with more data (F-R57, docs/RESEARCH.md §24.6).
    """
    fwd_dict = forward_returns(df, horizons)
    dates = pd.DatetimeIndex(pd.to_datetime(factor_vals.index.get_level_values("date")))
    year_of = dates.year.to_numpy()
    out: dict[int, list[dict[str, float | int]]] = {}
    summary: dict[int, dict[str, float]] = {}
    for h in horizons:
        rows: list[dict[str, float | int]] = []
        for year in sorted(set(year_of.tolist())):
            sub = factor_vals[year_of == year]
            mean_ic, _, t_hac, _, n = information_coefficient(
                sub, fwd_dict[h], "pearson", horizon=h
            )
            rows.append({"year": int(year), "n": int(n), "ic": mean_ic, "t_hac": t_hac})
        out[h] = rows

        # T_j-weighted pooled IC (Fama & French 1997, Eq. 5, p. 1980).
        # Weight year j by T_j = n_j (number of valid cross-sections).
        # Years with NaN IC (n < 2) contribute 0 weight.
        valid_rows = [(r["n"], r["ic"]) for r in rows if not _isnan(r["ic"])]
        if valid_rows:
            sum_w = sum(n_j for n_j, _ in valid_rows)
            if sum_w > 0:
                weighted_ic: float = sum(n_j * ic_j for n_j, ic_j in valid_rows) / sum_w
            else:
                weighted_ic = float("nan")
            simple_ic: float = sum(ic_j for _, ic_j in valid_rows) / len(valid_rows)
        else:
            weighted_ic = float("nan")
            simple_ic = float("nan")
        summary[h] = {"ic": simple_ic, "weighted_ic": weighted_ic}

    # Expose summary under the string key "summary" for callers that want
    # the pooled estimates without altering the per-year list structure.
    out["summary"] = summary  # type: ignore[assignment]
    return out


def _isnan(x: float | int) -> bool:
    """Return True if x is NaN (works for both float and int)."""
    try:
        return x != x  # NaN != NaN
    except TypeError:
        return False


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
        ic_p, ic_ir_p, ic_t_hac, ic_t_naive, n_obs = information_coefficient(
            factor_vals, fwd, "pearson", horizon=h
        )
        ic_s, _, _, _, _ = information_coefficient(factor_vals, fwd, "spearman", horizon=h)
        spread, mono, _ = quantile_analysis(factor_vals, fwd, n_quantiles)
        hr, hr_lb, _ = hit_rate_metrics(factor_vals, fwd)

        results.append(
            FactorMetrics(
                factor_name=factor_name,
                horizon=h,
                ic_pearson=ic_p,
                ic_spearman=ic_s,
                ic_ir=ic_ir_p,
                ic_tstat=ic_t_hac,
                ic_tstat_naive=ic_t_naive,
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


def _newey_west_se(ic_arr: np.ndarray, max_lags: int) -> float:
    """Newey-West HAC standard error for the mean of ic_arr.

    Corrects for autocorrelation up to max_lags (use H-1 for horizon H).

    Reference: Newey & West (1987) Econometrica 55(3):703-708.
    Bartlett kernel weights: w_l = 1 - l/(L+1), l = 1, ..., L.

    The long-run variance estimator is:
        V_HAC = gamma_0 + 2 * sum_{l=1}^{L} w_l * gamma_l
    where gamma_l = (1/T) * sum_{t=l+1}^{T} (x_t - xbar)(x_{t-l} - xbar)

    The HAC SE of the sample mean is sqrt(V_HAC / T).

    Cross-section note (F-R54, docs/RESEARCH.md 26.13): this is a
    time-series HAC for the mean of an IC series. When choosing between
    NW and two-way clustered SEs on the cross-section, Petersen (2009)
    Sec. III.C: NW is the right estimator below N=30 firm clusters;
    revisit double-clustering at N>=50.

    Parameters
    ----------
    ic_arr:
        1-D array of IC values (time series).
    max_lags:
        Maximum lag L = H-1 where H is the forward-return horizon.

    Returns
    -------
    HAC standard error of the mean.
    """
    t = len(ic_arr)
    if t < 2:  # noqa: PLR2004
        return float("nan")

    xc = ic_arr - ic_arr.mean()  # demeaned

    # Lag-0 autocovariance
    gamma0 = float(np.dot(xc, xc) / t)

    if max_lags == 0:
        # No overlap correction — same as naive SE
        return math.sqrt(gamma0 / t) if gamma0 >= 0 else float("nan")

    lrv = gamma0
    for lag in range(1, min(max_lags, t - 1) + 1):
        bartlett_w = 1.0 - lag / (max_lags + 1)
        gamma_l = float(np.dot(xc[lag:], xc[:-lag]) / t)
        lrv += 2.0 * bartlett_w * gamma_l

    # lrv can be negative (e.g. alternating series) — clamp to zero
    if lrv < 0:
        lrv = 0.0

    return math.sqrt(lrv / t)


def block_bootstrap_ic_ci(
    ic_arr: np.ndarray,
    horizon: int,
    n_boot: int = 2000,
    alpha: float = 0.05,
    seed: int = 0,
) -> tuple[float, float]:
    """Block bootstrap confidence interval for the mean IC.

    Uses non-overlapping blocks of length = horizon to respect the
    autocorrelation structure induced by overlapping forward-return labels.

    Wilson bounds are correct for hit rate (binomial proportion) but NOT for
    IC (a correlation). This function provides the correct CI for IC.

    Reference: Efron & Tibshirani (1993) "An Introduction to the Bootstrap"
    ISBN 0412042312. Chapter 8 discusses block bootstrap for dependent data.

    Parameters
    ----------
    ic_arr:
        1-D array of per-date IC values.
    horizon:
        Forward-return horizon. Used as block size.
    n_boot:
        Number of bootstrap replications.
    alpha:
        Significance level (default 0.05 → 95% CI).
    seed:
        RNG seed for determinism.

    Returns
    -------
    (lower, upper) percentile bootstrap confidence interval.
    """
    t = len(ic_arr)
    block_size = max(1, horizon)
    n_blocks = max(1, t // block_size)

    rng = np.random.default_rng(seed)
    boot_means = np.empty(n_boot)

    # Build non-overlapping blocks
    block_starts = list(range(0, n_blocks * block_size, block_size))
    blocks = [ic_arr[s : s + block_size] for s in block_starts if s + block_size <= t]
    if not blocks:
        blocks = [ic_arr]

    for i in range(n_boot):
        chosen = rng.choice(len(blocks), size=len(blocks), replace=True)
        resampled = np.concatenate([blocks[j] for j in chosen])
        boot_means[i] = float(np.mean(resampled))

    lower = float(np.percentile(boot_means, 100 * alpha / 2))
    upper = float(np.percentile(boot_means, 100 * (1 - alpha / 2)))
    return (lower, upper)


def _pearson_corr(x: np.ndarray, y: np.ndarray) -> float:
    """Pearson correlation coefficient, implemented from first principles.

    Reference: Pearson (1895) Philosophical Transactions, Series A, 187:253-318.
    corr(X, Y) = cov(X,Y) / (std(X) * std(Y))
               = sum((x-xbar)*(y-ybar)) / sqrt(sum((x-xbar)^2) * sum((y-ybar)^2))

    Scale-invariance note: corr(a*X + c, b*Y + d) == corr(X, Y) for a, b > 0,
    so each input is centred first and the *deviations* are rescaled by
    their own max abs. Rescaling raw inputs by max(|X|, |Y|) is not enough:
    when one input's variation sits far below its own level (e.g.
    Y = -2X - 1 with X ~ 1e-200, so Y ~ -1 with 1e-200 wiggles), the
    centred deviations square to ~1e-400, which underflows to 0.0, the
    denominator vanishes, and a true corr of -1.0 comes back NaN. The same
    happens with a single shared rescale when the two inputs' magnitudes
    differ wildly (X ~ 1e200, Y ~ 1e-200: Y/scale ~ 1e-400 rounds to 0.0).
    Centring-then-rescaling-deviations is exact-arithmetic-identical and
    keeps every squared term near unit magnitude. Without any rescale,
    inputs with |x| ~ 1e-79 produce a denominator sum-of-squares ~1e-317,
    which is subnormal in float64 (min normal 2.2e-308, ~27 bits of
    precision left), and corr(x, x) comes back as 0.9999999953 instead
    of 1.0.
    """
    if len(x) < 2:  # noqa: PLR2004
        return float("nan")
    if bool(np.all(x == x[0])) or bool(np.all(y == y[0])):
        # Fail closed: an exactly-constant input has undefined correlation,
        # and a constant factor given +/-1.0 instead of NaN could pass gates
        # it must fail (NaN propagates to rejection). Checked before
        # centring because mean() of identical floats can carry rounding
        # residue (e.g. mean([85.8]*3) != 85.8), which would otherwise
        # normalise into a spurious corr of 1.0.
        return float("nan")
    xd = x - x.mean()
    yd = y - y.mean()
    sx = float(np.max(np.abs(xd)))
    sy = float(np.max(np.abs(yd)))
    if sx == 0 or sy == 0:
        return float("nan")
    xs = xd / sx
    ys = yd / sy
    denom = math.sqrt((xs**2).sum() * (ys**2).sum())
    if denom == 0:
        return float("nan")
    return float((xs * ys).sum() / denom)


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


# ---------------------------------------------------------------------------
# Clark-West MSPE-adjusted OOS statistic (F-R53)
# ---------------------------------------------------------------------------


def clark_west_stat(
    bench_errors: np.ndarray,
    model_errors: np.ndarray,
    bench_preds: np.ndarray,
    model_preds: np.ndarray,
    max_lags: int = 0,
) -> float:
    """Clark-West MSPE-adjusted OOS test statistic (eq. 11).

    For a nested pair (benchmark = restricted model, factor model =
    full model) evaluated on the same OOS dates, define per date t:

        f_t = e0_t**2 - (e1_t**2 - (p1_t - p0_t)**2)

    where e = actual - predicted (signed forecast error) and p is the
    prediction; the (p1 - p0)**2 term corrects the finite-sample bias
    that makes the larger model look worse OOS even under the null.
    The statistic is:

        f_bar = mean(f_t);  CW = f_bar / SE_HAC(f_bar, lags=max_lags)

    Under H0 (nested benchmark correctly specified) CW is asymptotically
    standard normal; evidence of OOS predictive content at the one-sided
    5% level is CW > 1.645.

    Reference: Clark, T.E. & West, K.D. (2007) "Approximately Normal
    Tests for Equal Predictive Accuracy in Nested Models", Journal of
    Econometrics 138(1):291-311, eq. 11 (p. 299). Assumptions: nested
    models, recursive (expanding) OOS estimation, covariance-stationary
    forecast errors (same stationarity assumption as Newey-West).
    Known failure mode: liberal (over-rejects) when the OOS window is
    short (P < 50); use max_lags = H - 1 when labels overlap by H-1 days.

    Conventions: if the two models are identical the statistic is 0.0
    (no evidence either way). NaN if there are fewer than 2 observations
    or the HAC standard error is not estimable.

    Parameters
    ----------
    bench_errors:
        Signed forecast errors of the benchmark model (actual - p0).
    model_errors:
        Signed forecast errors of the factor model (actual - p1).
    bench_preds:
        Benchmark predictions p0, same shape as bench_errors.
    model_preds:
        Factor-model predictions p1, same shape as model_preds.
    max_lags:
        HAC lags for the Newey-West SE of f_bar (H-1 for horizon H).

    Returns
    -------
    Clark-West statistic (float).
    """
    e0 = np.asarray(bench_errors, dtype=float)
    e1 = np.asarray(model_errors, dtype=float)
    p0 = np.asarray(bench_preds, dtype=float)
    p1 = np.asarray(model_preds, dtype=float)
    if e0.shape != e1.shape or e0.shape != p0.shape or e0.shape != p1.shape:
        raise ValueError("bench_errors, model_errors, bench_preds, model_preds must align")
    if e0.ndim != 1 or len(e0) < 2:
        return float("nan")

    f = e0**2 - (e1**2 - (p1 - p0) ** 2)
    f_bar = float(np.mean(f))
    if f_bar == 0.0 and not np.any(f):
        return 0.0  # identical models: no evidence either way
    se = _newey_west_se(f, max_lags=max_lags)
    if math.isnan(se) or se <= 0.0:
        return float("nan")
    return f_bar / se


def oos_cw_stat(
    factor_vals: pd.Series,
    df: pd.DataFrame,
    splits,
    horizon: int,
    min_train_obs: int = 30,
) -> float:
    """Clark-West statistic over walk-forward OOS dates for one factor.

    Wires clark_west_stat onto the purged walk-forward infrastructure
    (F-R53, docs/RESEARCH.md 24.1). The nested pair, per Clark & West's
    intercept-only benchmark:

        benchmark: p0 = pooled expanding mean of forward returns (a)
        factor model: p1 = a + b * x  (pooled expanding OLS of the
            forward return on the factor value, estimated on all
            earlier dates whose label window lies strictly before t,
            mirroring the PurgedWalkForward purge rule s + H < t)

    f_t is averaged over the cross-section at each OOS date, then
    CW = mean(f) / HAC_SE(f, lags=horizon-1). One-sided: > 1.645
    indicates magnitude-weighted OOS content; the sign-consistency
    gate alone cannot see this (it is magnitude-blind).

    Parameters
    ----------
    factor_vals:
        Factor output Series with MultiIndex (date, asset).
    df:
        Tidy long-format OHLCV panel.
    splits:
        Iterable of walk-forward split objects exposing .test_idx
        (iloc positions into df), as produced by PurgedWalkForward.split.
    horizon:
        Forward-return horizon whose labels drive the comparison.
    min_train_obs:
        Minimum pooled estimation rows before CW is computed; below
        this the result is NaN (estimation noise dominates, per the
        P < 50 failure mode in Clark & West).

    Returns
    -------
    Clark-West statistic for the factor's OOS dates (float, possibly NaN).
    """
    dates = pd.DatetimeIndex(sorted(df["date"].unique()))
    date_pos = {d: i for i, d in enumerate(dates)}

    fwd_df = forward_returns(df, [horizon])[horizon]
    # forward_returns returns a long DataFrame (date, asset, fwd_ret); convert
    # to a MultiIndex Series so it can be concat'd with factor_vals.
    fwd_series = fwd_df.set_index(["date", "asset"])["fwd_ret"]
    combined = pd.concat([factor_vals.rename("x"), fwd_series.rename("r")], axis=1, join="inner")
    combined = combined.dropna()
    if combined.empty:
        return float("nan")

    obs_by_pos: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    for d, grp in combined.groupby(level="date", sort=True):
        pos = date_pos.get(d)
        if pos is None:
            continue
        obs_by_pos[pos] = (grp["x"].to_numpy(dtype=float), grp["r"].to_numpy(dtype=float))

    test_positions = sorted(
        {
            date_pos[d]
            for spl in splits
            for d in df.iloc[spl.test_idx]["date"].unique()
            if d in date_pos
        }
    )
    if len(test_positions) < 2:
        return float("nan")

    sx = sy = sxx = sxy = 0.0
    n_train = 0
    flush_pos = 0
    f_vals: list[float] = []
    for pos in test_positions:
        # Expanding window with purge: a training observation at date s is
        # usable only once its label (realised at s + horizon) is known
        # strictly before pos.
        while flush_pos + horizon < pos:
            if flush_pos in obs_by_pos:
                x, r = obs_by_pos[flush_pos]
                sx += float(x.sum())
                sy += float(r.sum())
                sxx += float((x * x).sum())
                sxy += float((x * r).sum())
                n_train += int(len(x))
            flush_pos += 1
        if n_train < min_train_obs or pos not in obs_by_pos:
            f_vals.append(float("nan"))
            continue
        denom = n_train * sxx - sx * sx
        if denom == 0.0:
            f_vals.append(float("nan"))
            continue
        b = (n_train * sxy - sx * sy) / denom
        a = (sy - b * sx) / n_train
        x, r = obs_by_pos[pos]
        p0 = np.full_like(r, a)
        p1 = a + b * x
        f_vals.append(float(np.mean((r - p0) ** 2 - ((r - p1) ** 2 - (p1 - p0) ** 2))))

    f_arr = np.array([v for v in f_vals if not math.isnan(v)], dtype=float)
    if len(f_arr) < 2:
        return float("nan")
    f_bar = float(f_arr.mean())
    if f_bar == 0.0:
        return 0.0
    se = _newey_west_se(f_arr, max_lags=horizon - 1)
    if math.isnan(se) or se <= 0.0:
        return float("nan")
    return f_bar / se


def ic_sign_autocorr(ic_series: list[float]) -> dict[str, float]:
    """Lag-1 IC sign autocorrelation (factor-momentum OOS-consistency test).

    Measures whether the sign of the IC in split t predicts the sign in
    split t+1 — the empirical test for factor momentum in the sense of
    Gupta & Kelly (2019) *Factor Momentum Everywhere*, JPM 45(3):13-36.

    If the OOS-consistency gate (≥60% of splits with positive IC) has
    predictive power for FUTURE IC, the lag-1 IC sign autocorrelation
    (rho) should be positive and statistically distinguishable from zero.
    If rho ≈ 0, the gate tests past IC quality but does not predict future
    IC — an honest finding reported as F-R60 in docs/RESEARCH.md §24.9.

    Method
    ------
    Given a sequence of per-split IC values [ic_0, ..., ic_{T-1}]:

    1. Binarise: s_t = sign(ic_t) ∈ {-1, +1} (NaN splits dropped).
    2. Lag-1 autocorrelation of the sign series::

           rho = corr(s_t, s_{t-1}) = Pearson(s_1…s_{T-1}, s_0…s_{T-2})

    3. Hypothesis test: under H0 rho=0, the approximate SE is 1/sqrt(T-1)
       where T-1 = number of consecutive sign pairs.  The t-statistic is
       rho * sqrt(T-1).  This is an asymptotic normal approximation valid
       for T >= 6; smaller T returns NaN for t_stat.

    Parameters
    ----------
    ic_series:
        Ordered list of per-split IC values (e.g. from walk-forward CV).
        NaN values are dropped before the autocorrelation is computed.

    Returns
    -------
    Dict with keys:

    * ``"rho"`` — lag-1 Pearson autocorrelation of the sign series.
    * ``"t_stat"`` — asymptotic t-statistic under H0: rho=0.
    * ``"n_pairs"`` — number of consecutive sign pairs used.
    * ``"pct_positive"`` — fraction of non-NaN splits with positive IC.

    All float; NaN if fewer than 4 valid IC values (3 pairs minimum for
    a non-trivial estimate and t-stat).
    """
    valid = [ic for ic in ic_series if not (ic != ic)]  # drop NaN
    if len(valid) < 4:
        return {
            "rho": float("nan"),
            "t_stat": float("nan"),
            "n_pairs": 0,
            "pct_positive": float("nan"),
        }

    signs = np.array([1.0 if v >= 0.0 else -1.0 for v in valid])
    pct_pos = float((signs > 0).sum()) / len(signs)

    # Lag-1 pairs: x = signs[:-1], y = signs[1:]
    x = signs[:-1]
    y = signs[1:]
    n_pairs = len(x)

    # Pearson correlation of the binary sign series
    rho = _pearson_corr(x, y)

    # Asymptotic t-stat: rho * sqrt(n_pairs) under H0: rho = 0
    if n_pairs >= 3 and not math.isnan(rho):  # noqa: PLR2004
        t_stat = rho * math.sqrt(n_pairs)
    else:
        t_stat = float("nan")

    return {
        "rho": rho,
        "t_stat": t_stat,
        "n_pairs": n_pairs,
        "pct_positive": pct_pos,
    }
