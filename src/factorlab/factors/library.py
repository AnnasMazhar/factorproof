"""
factorlab.factors.library — all factor implementations.

Factor design references (see docs/RESEARCH.md for full citations):
- Momentum: Jegadeesh & Titman (1993) J. Finance 48(1):65-91
- Reversal: De Bondt & Thaler (1985) J. Finance 40(3):793-808
- RSI: Wilder (1978) "New Concepts in Technical Trading Systems"
- ATR: Wilder (1978) ibid.
- Amihud illiquidity: Amihud (2002) J. Financial Markets 5(1):31-56
- Skewness: Harvey & Siddique (2000) J. Finance 55(3):1263-1295
- Autocorrelation: Lo & MacKinlay (1988) Rev. Financial Studies 1(1):41-66
- Volume Z-score: Karpoff (1987) J. Financial Quantitative Analysis 22(1):109-126
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .base import Factor

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pivot_close(df: pd.DataFrame) -> pd.DataFrame:
    """Pivot close prices to wide format (index=date, columns=asset)."""
    return df.pivot(index="date", columns="asset", values="close")


def _pivot_col(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """Pivot an arbitrary column to wide format."""
    return df.pivot(index="date", columns="asset", values=col)


def _melt(wide: pd.DataFrame) -> pd.Series:
    """Melt wide factor DataFrame to long MultiIndex Series (date, asset)."""
    long = wide.stack(future_stack=True)
    long.index.names = ["date", "asset"]
    return long.rename("value")


def _rolling_apply(series: pd.Series, window: int, func) -> pd.Series:
    """Apply func over a rolling window; return NaN where window is incomplete."""
    return series.rolling(window=window, min_periods=window).apply(func, raw=True)


# ---------------------------------------------------------------------------
# Momentum
# ---------------------------------------------------------------------------


class Mom20(Factor):
    """20-day cross-sectional momentum (returns over past 20 trading days).

    Reference: Jegadeesh & Titman (1993) J. Finance 48(1):65-91.
    The factor is the log-return over a 20-day lookback, capturing
    short-term price continuation patterns.

    Fault this test detects: sign flip in log-return computation.
    """

    name = "mom_20"
    category = "momentum"
    description = "20-day log-return (short-term momentum)"
    params = {"window": 20}

    def compute(self, df: pd.DataFrame) -> pd.Series:
        close = _pivot_close(df)
        # Log-return over window days: log(P_t / P_{t-20})
        ret = np.log(close / close.shift(self.params["window"]))
        return _melt(ret)


class Mom60(Factor):
    """60-day cross-sectional momentum.

    Reference: Jegadeesh & Titman (1993) J. Finance 48(1):65-91.
    Intermediate-term momentum over a 60-day lookback (approx. 3 months).

    Fault this test detects: off-by-one in shift period.
    """

    name = "mom_60"
    category = "momentum"
    description = "60-day log-return (intermediate-term momentum)"
    params = {"window": 60}

    def compute(self, df: pd.DataFrame) -> pd.Series:
        close = _pivot_close(df)
        ret = np.log(close / close.shift(self.params["window"]))
        return _melt(ret)


# ---------------------------------------------------------------------------
# Reversal
# ---------------------------------------------------------------------------


class Rev5(Factor):
    """5-day short-term reversal.

    Reference: De Bondt & Thaler (1985) J. Finance 40(3):793-808.
    Negated 5-day log-return; the sign flip captures the reversal
    (past losers outperform past winners in the short term).

    Fault this test detects: missing negation — reversal becoming momentum.
    """

    name = "rev_5"
    category = "reversal"
    description = "Negated 5-day log-return (short-term reversal)"
    params = {"window": 5}

    def compute(self, df: pd.DataFrame) -> pd.Series:
        close = _pivot_close(df)
        # Negated: high recent return → low factor → bottom quantile → expected outperformance
        ret = -np.log(close / close.shift(self.params["window"]))
        return _melt(ret)


# ---------------------------------------------------------------------------
# Volatility
# ---------------------------------------------------------------------------


class Vol20(Factor):
    """20-day realised volatility (annualised std of log-returns).

    Reference: Ang et al. (2006) J. Finance 61(1):259-299.
    High-volatility assets tend to underperform (the low-vol anomaly),
    so this factor has a typically negative expected IC with future returns.

    Fault this test detects: missing annualisation factor (sqrt 252).
    """

    name = "vol_20"
    category = "volatility"
    description = "20-day realised volatility, annualised"
    params = {"window": 20}

    def compute(self, df: pd.DataFrame) -> pd.Series:
        close = _pivot_close(df)
        log_ret = np.log(close / close.shift(1))
        # Annualised vol: std of daily log-returns * sqrt(252)
        vol = log_ret.rolling(window=self.params["window"], min_periods=self.params["window"]).std()
        vol_ann = vol * np.sqrt(252)
        return _melt(vol_ann)


class Atr14Norm(Factor):
    """Normalised 14-day Average True Range.

    Reference: Wilder (1978) "New Concepts in Technical Trading Systems", ISBN 0894590278.
    ATR = mean of True Range over 14 days, normalised by closing price.
    True Range = max(H-L, |H-prev_C|, |L-prev_C|).

    Fault this test detects: wrong True Range formula (missing prior close).
    """

    name = "atr_norm_14"
    category = "volatility"
    description = "14-day ATR normalised by close price"
    params = {"window": 14}

    def compute(self, df: pd.DataFrame) -> pd.Series:
        w = self.params["window"]
        # Work in wide format for vectorised computation
        high = _pivot_col(df, "high")
        low = _pivot_col(df, "low")
        close = _pivot_close(df)

        prev_close = close.shift(1)
        tr = np.maximum(
            high - low,
            np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)),
        )
        atr = tr.rolling(window=w, min_periods=w).mean()
        atr_norm = atr / close.where(close > 0)
        return _melt(atr_norm)


# ---------------------------------------------------------------------------
# Oscillator
# ---------------------------------------------------------------------------


class Rsi14(Factor):
    """14-day Relative Strength Index.

    Reference: Wilder (1978) "New Concepts in Technical Trading Systems", ISBN 0894590278.
    RSI = 100 - 100/(1 + avg_gain/avg_loss) over 14 days.
    Values < 30 indicate oversold (contrarian buy signal);
    values > 70 indicate overbought (contrarian sell signal).
    We return RSI directly; lower RSI = better expected return (reversal).

    Fault this test detects: avg_gain / avg_loss arithmetic inversion.
    """

    name = "rsi_14"
    category = "oscillator"
    description = "14-day Relative Strength Index (Wilder smoothing)"
    params = {"window": 14}

    def compute(self, df: pd.DataFrame) -> pd.Series:
        w = self.params["window"]
        close = _pivot_close(df)
        delta = close.diff(1)

        gain = delta.clip(lower=0.0)
        loss = (-delta).clip(lower=0.0)

        avg_gain = gain.rolling(window=w, min_periods=w).mean()
        avg_loss = loss.rolling(window=w, min_periods=w).mean()

        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100.0 - (100.0 / (1.0 + rs))

        return _melt(rsi)


# ---------------------------------------------------------------------------
# Volume / Liquidity
# ---------------------------------------------------------------------------


class VolumeZ20(Factor):
    """20-day volume z-score.

    Reference: Karpoff (1987) J. Financial Quantitative Analysis 22(1):109-126.
    Standardised volume relative to its 20-day mean and std.
    Abnormal volume often accompanies price moves.

    Fault this test detects: division by zero when std is zero (constant volume).
    """

    name = "volume_z_20"
    category = "volume"
    description = "20-day volume Z-score (standardised trading volume)"
    params = {"window": 20}

    def compute(self, df: pd.DataFrame) -> pd.Series:
        w = self.params["window"]
        volume = _pivot_col(df, "volume")
        mu = volume.rolling(window=w, min_periods=w).mean()
        sigma = volume.rolling(window=w, min_periods=w).std()
        z = (volume - mu) / sigma.replace(0, np.nan)
        return _melt(z)


class Amihud20(Factor):
    """20-day Amihud illiquidity ratio.

    Reference: Amihud (2002) J. Financial Markets 5(1):31-56.
    ILLIQ_t = (1/D) * sum_d(|R_d| / Vol_d)
    where |R_d| is the absolute daily log-return and Vol_d is dollar volume.
    Higher ILLIQ = less liquid = higher expected return (liquidity premium).

    Fault this test detects: missing absolute value on return.
    """

    name = "amihud_illiq_20"
    category = "liquidity"
    description = "20-day Amihud illiquidity ratio"
    params = {"window": 20}

    def compute(self, df: pd.DataFrame) -> pd.Series:
        w = self.params["window"]
        close = _pivot_close(df)
        volume = _pivot_col(df, "volume")

        log_ret = np.log(close / close.shift(1))
        abs_ret = log_ret.abs()

        # Dollar volume proxy: close * volume
        dollar_vol = close * volume
        dollar_vol = dollar_vol.replace(0, np.nan)

        daily_illiq = abs_ret / dollar_vol
        illiq = daily_illiq.rolling(window=w, min_periods=w).mean()
        # Scale by 1e6 to bring into a readable magnitude
        return _melt(illiq * 1e6)


# ---------------------------------------------------------------------------
# Distributional
# ---------------------------------------------------------------------------


class Skew60(Factor):
    """60-day skewness of log-returns.

    Reference: Harvey & Siddique (2000) J. Finance 55(3):1263-1295.
    Investors prefer positive skew (lottery-like payoffs) and require
    a risk premium for negative skew. Higher skew → lower expected return.
    The factor is negated so high skew assets rank lower.

    Fault this test detects: missing negation of skewness.
    """

    name = "skew_60"
    category = "distributional"
    description = "Negated 60-day skewness of log-returns"
    params = {"window": 60}

    def compute(self, df: pd.DataFrame) -> pd.Series:
        w = self.params["window"]
        close = _pivot_close(df)
        log_ret = np.log(close / close.shift(1))
        # pandas rolling skew uses the same formula as scipy.stats.skew with bias=False
        skewness = log_ret.rolling(window=w, min_periods=w).skew()
        # Negate: lottery preference → investors overprice positive-skew assets
        return _melt(-skewness)


# ---------------------------------------------------------------------------
# Micro-structure
# ---------------------------------------------------------------------------


class Autocorr5(Factor):
    """5-day lag-1 return autocorrelation.

    Reference: Lo & MacKinlay (1988) Rev. Financial Studies 1(1):41-66.
    Positive autocorrelation suggests momentum; negative suggests mean-reversion.
    Computed as Pearson correlation between r_t and r_{t-1} over a 5-day window.

    Fault this test detects: using variance instead of covariance (returns constant 1).
    """

    name = "autocorr_5"
    category = "microstructure"
    description = "5-day lag-1 return autocorrelation"
    params = {"window": 5}

    def compute(self, df: pd.DataFrame) -> pd.Series:
        w = self.params["window"]
        close = _pivot_close(df)
        log_ret = np.log(close / close.shift(1))

        def _autocorr_lag1(x: np.ndarray) -> float:
            """Pearson correlation between x[:-1] and x[1:]."""
            if len(x) < 3:  # noqa: PLR2004
                return np.nan
            a = x[:-1]
            b = x[1:]
            a_d = a - a.mean()
            b_d = b - b.mean()
            denom = np.sqrt((a_d**2).sum() * (b_d**2).sum())
            if denom == 0:
                return np.nan
            return float((a_d * b_d).sum() / denom)

        ac = log_ret.rolling(window=w, min_periods=w).apply(_autocorr_lag1, raw=True)
        return _melt(ac)


# ---------------------------------------------------------------------------
# Composite
# ---------------------------------------------------------------------------


class DeflatedMom(Factor):
    """Deflated momentum: 60-day momentum adjusted by 20-day realised vol.

    Divides the 60-day log-return by the 20-day annualised vol (Sharpe-like).
    This reduces the effect of high-volatility assets dominating momentum ranks.

    Reference: Moskowitz, Ooi & Pedersen (2012) J. Financial Economics 104(2):228-250
    discuss time-series momentum and vol-scaling.

    Fault this test detects: using raw return instead of vol-scaled return.
    """

    name = "deflated_mom"
    category = "momentum"
    description = "60-day momentum deflated by 20-day realised vol"
    params = {"mom_window": 60, "vol_window": 20}

    def compute(self, df: pd.DataFrame) -> pd.Series:
        close = _pivot_close(df)
        log_ret = np.log(close / close.shift(1))

        mom = np.log(close / close.shift(self.params["mom_window"]))
        vol = log_ret.rolling(
            window=self.params["vol_window"], min_periods=self.params["vol_window"]
        ).std() * np.sqrt(252)

        deflated = mom / vol.replace(0, np.nan)
        return _melt(deflated)


# ---------------------------------------------------------------------------
# Controls (deliberately bad — gate must detect and reject these)
# ---------------------------------------------------------------------------


class NoiseControl(Factor):
    """Pure seeded random noise — no predictive content.

    This is a deliberate control. The promotion gate MUST reject it.
    The factor generates independent Gaussian noise per (date, asset).

    Fault this test detects: promotion gate passing factors with no IC.
    """

    name = "noise_control"
    category = "control"
    description = "Pure random noise — should always be rejected"
    params = {"seed": 42}

    def compute(self, df: pd.DataFrame) -> pd.Series:
        close = _pivot_close(df)
        rng = np.random.default_rng(self.params["seed"])
        noise = pd.DataFrame(
            rng.standard_normal(close.shape),
            index=close.index,
            columns=close.columns,
        )
        return _melt(noise)


class LookaheadControl(Factor):
    """Deliberately uses future data — pipeline MUST detect and reject this.

    Uses the NEXT period's close price divided by current close as the factor.
    This has perfect predictive power because it leaks the future return.
    The leakage detection system must flag it as invalid.

    Fault this test detects: lookahead contamination going undetected.
    """

    name = "lookahead_control"
    category = "control"
    description = "Lookahead factor using future close — should always be rejected"
    params = {}
    # Flag for downstream lookahead detection
    uses_future_data: bool = True

    def compute(self, df: pd.DataFrame) -> pd.Series:
        close = _pivot_close(df)
        # shift(-1) = next period's close — pure lookahead contamination
        future_ret = np.log(close.shift(-1) / close)
        return _melt(future_ret)
