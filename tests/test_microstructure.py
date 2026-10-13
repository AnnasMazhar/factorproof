"""
Tests for factorlab.microstructure (cycle 4, implement pass 1 — F-R12/F-R14/F-R15).

Faults detected per test:
    test_roll_spread_hand_computed:
        Fault: wrong Roll transcription (e.g. missing factor of 2, sqrt of
        +cov instead of -cov, population vs sample covariance mix-up).
    test_lag1_autocorr_hand_computed:
        Fault: wrong pairing (r_t with r_t instead of r_{t-1}) or wrong
        normalisation in the Pearson lag-1 computation.
    test_roll_spread_positive_cov_is_nan:
        Fault: clamping an imaginary Roll spread to 0.0 instead of NaN,
        which would hide the absence of the bounce mechanism (F-R12).
    test_roll_spread_degenerate_is_nan:
        Fault: crash or garbage spread on constant/degenerate return series.
    test_lag1_autocorr_alternating_is_minus_one:
        Fault: sign error in the lag pairing (would return +1.0).
    test_zero_volume_share_bounds:
        Fault: share outside [0, 1] (e.g. counting NaNs as zero-volume).
    test_zero_volume_share_hand_computed:
        Fault: off-by-one in the zero-volume count.
    test_staleness_flag_threshold:
        Fault: >= vs > confusion at the 5% boundary, or flagging every coin.
    test_find_missing_dates_detects_gap:
        Fault: gap detection that only looks at one coin (a single-coin gap
        is staleness, not a feed gap) or that misses interior dates.
    test_find_missing_dates_no_gap:
        Fault: false-positive gaps on a complete daily panel.
    test_panel_bias_direction_names_sign:
        Fault: inverted bounce/trend labelling (would flip the DSR caveat).
    test_dsr_bias_caveat_names_direction:
        Fault: caveat sentence that states the threshold but not the bias
        direction (the exact F-R15 transfer requirement).
    test_roll_spread_scales_linearly:
        Fault: non-homogeneous spread (e.g. variance used where the spread
        needs the standard-deviation scale).
    test_roll_spread_nonnegative_when_real:
        Fault: negative spread from a sign error under the square root.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from hypothesis import given, settings
from hypothesis import strategies as st

from factorlab.microstructure import (
    AUTOCORR_CAVEAT_THRESHOLD,
    STALENESS_THRESHOLD,
    dsr_bias_caveat,
    find_missing_dates,
    lag1_autocorr,
    lag1_autocov,
    panel_bias_direction,
    roll_spread,
    staleness_flags,
    zero_volume_share,
)

# Hand-computed reference (verified with an independent calculation):
#   r = [0.01, -0.02, 0.03, -0.01, 0.02]
#   a = r[:-1] = [0.01, -0.02, 0.03, -0.01], mean_a = 0.0025
#   b = r[1:]  = [-0.02, 0.03, -0.01, 0.02], mean_b = 0.005
#   products of deviations = [-0.0001875, -0.0005625, -0.0004125, -0.0001875]
#   sum = -0.00135; cov (ddof=1) = -0.00135 / 3 = -0.00045
#   spread = 2*sqrt(0.00045) = 0.042426406871192854
#   std_a = 0.022173..., std_b = 0.023805..., rho = -0.8525371202334079
_KAT_RETURNS = np.array([0.01, -0.02, 0.03, -0.01, 0.02])
_KAT_COV = -0.00045
_KAT_SPREAD = 0.042426406871192854
_KAT_RHO = -0.8525371202334079


def test_lag1_autocov_hand_computed() -> None:
    assert math.isclose(lag1_autocov(_KAT_RETURNS), _KAT_COV, rel_tol=1e-12)


def test_roll_spread_hand_computed() -> None:
    assert math.isclose(roll_spread(_KAT_RETURNS), _KAT_SPREAD, rel_tol=1e-9)


def test_lag1_autocorr_hand_computed() -> None:
    assert math.isclose(lag1_autocorr(_KAT_RETURNS), _KAT_RHO, rel_tol=1e-9)


def test_roll_spread_positive_cov_is_nan() -> None:
    # Strictly trending series: lag-1 autocovariance > 0 -> imaginary spread.
    trending = np.array([0.01, 0.02, 0.03, 0.04, 0.05, 0.06])
    assert lag1_autocov(trending) > 0.0
    assert math.isnan(roll_spread(trending))


def test_roll_spread_degenerate_is_nan() -> None:
    assert math.isnan(roll_spread(np.zeros(10)))
    assert math.isnan(roll_spread(np.array([0.01, 0.01])))
    assert math.isnan(lag1_autocorr(np.zeros(10)))


def test_lag1_autocorr_alternating_is_minus_one() -> None:
    alt = np.array([0.05, -0.05] * 10)
    assert math.isclose(lag1_autocorr(alt), -1.0, rel_tol=1e-9)


def test_zero_volume_share_hand_computed() -> None:
    v = np.array([0.0, 10.0, 0.0, 5.0, 0.0, 0.0, 3.0, 8.0, 0.0, 2.0])
    assert zero_volume_share(v) == 0.5


def test_zero_volume_share_bounds() -> None:
    assert zero_volume_share(np.ones(100)) == 0.0
    assert zero_volume_share(np.zeros(100)) == 1.0


def test_staleness_flag_threshold() -> None:
    assert STALENESS_THRESHOLD == 0.05
    flags = staleness_flags({"thin": 0.051, "edge": 0.05, "liquid": 0.0075})
    assert flags == {"thin": True, "edge": False, "liquid": False}


def test_find_missing_dates_detects_gap() -> None:
    days = pd.date_range("2026-04-25", "2026-05-05", freq="D")
    present = [d for d in days if d != pd.Timestamp("2026-04-30")]
    assert find_missing_dates(pd.Series(present)) == [pd.Timestamp("2026-04-30")]


def test_find_missing_dates_no_gap() -> None:
    days = pd.date_range("2021-04-29", "2021-05-29", freq="D")
    assert find_missing_dates(pd.Series(days)) == []


def test_panel_bias_direction_names_sign() -> None:
    bounce = {"A": -0.06, "B": -0.04, "C": 0.01}
    assert panel_bias_direction(bounce) == "bounce-type"
    trend = {"A": 0.06, "B": 0.04, "C": -0.01}
    assert panel_bias_direction(trend) == "trend-type"
    assert panel_bias_direction({}) == "unclassified"
    assert panel_bias_direction({"A": float("nan")}) == "unclassified"


def test_dsr_bias_caveat_names_direction() -> None:
    bounce_txt = dsr_bias_caveat("bounce-type", 0.1145)
    assert "bounce-type" in bounce_txt
    assert "OVERstated" in bounce_txt
    assert "conservative" in bounce_txt
    trend_txt = dsr_bias_caveat("trend-type", 0.25)
    assert "trend-type" in trend_txt
    assert "UNDERstated" in trend_txt
    assert "optimistic" in trend_txt
    assert str(AUTOCORR_CAVEAT_THRESHOLD) in bounce_txt


@given(
    st.lists(
        st.floats(min_value=-0.5, max_value=0.5, allow_nan=False, allow_infinity=False),
        min_size=5,
        max_size=50,
    )
)
@settings(max_examples=100)
def test_roll_spread_nonnegative_when_real(returns: list[float]) -> None:
    s = roll_spread(np.asarray(returns))
    assert math.isnan(s) or s >= 0.0


@given(
    st.lists(
        st.floats(min_value=-0.5, max_value=0.5, allow_nan=False, allow_infinity=False),
        min_size=5,
        max_size=50,
    ),
    st.floats(min_value=0.5, max_value=3.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100)
def test_roll_spread_scales_linearly(returns: list[float], c: float) -> None:
    r = np.asarray(returns)
    s1, s2 = roll_spread(r), roll_spread(c * r)
    if math.isnan(s1):
        assert math.isnan(s2)
    else:
        assert math.isclose(s2, c * s1, rel_tol=1e-9)
