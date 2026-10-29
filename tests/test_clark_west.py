"""
Clark-West MSPE-adjusted OOS statistic tests (F-R53, docs/RESEARCH.md 24.1).

Faults detected per test:
    test_clark_west_kat_hand_computed:
        Fault: wrong adjustment-term sign (f = e0^2 - e1^2 - (p1-p0)^2
        instead of e0^2 - (e1^2 - (p1-p0)^2)) or a dropped adjustment
        term — hand-worked numbers pin Clark & West eq. 11 exactly.
    test_clark_west_identical_models_is_zero:
        Fault: non-zero CW for a model identical to the benchmark
        (spurious OOS content invented from nothing).
    test_clark_west_sign_tracks_adjusted_mspe:
        Fault: CW sign detached from the adjusted MSPE comparison —
        CW > 0 must require the benchmark to lose the f_t comparison.
    test_clark_west_order_invariance_zero_lags:
        Fault: statistic depending on observation order when max_lags=0
        (HAC-free SE must be a function of the empirical distribution
        of f only).
    test_clark_west_raises_on_misaligned_inputs:
        Fault: silently broadcasting misaligned error/prediction arrays
        into a plausible-looking statistic.
    test_walk_forward_result_carries_cw:
        Fault: WalkForwardResult dropping the oos_cw_stat field wiring —
        the F-R53 diagnostic silently becomes NaN in promote notes.
    test_oos_cw_stat_deterministic_and_finite_on_synthetic:
        Fault: oos_cw_stat non-deterministic or always-NaN on a clean
        synthetic panel (diagnostic dead on arrival).
    test_oos_cw_stat_null_and_signal_ordering:
        Fault: wiring estimating the expanding OLS on the test window
        itself or swapping benchmark/factor roles — the planted-signal
        factor must beat a pure-noise factor under the same splitter.
"""

from __future__ import annotations

import math

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from factorlab.cv import PurgedWalkForward, WalkForwardResult, evaluate_walk_forward
from factorlab.data import synthetic_ohlcv
from factorlab.evaluate import clark_west_stat, oos_cw_stat
from factorlab.factors import get_factor

_FINITE = st.floats(
    min_value=-100.0, max_value=100.0, allow_nan=False, allow_infinity=False
)


def test_clark_west_kat_hand_computed() -> None:
    """KAT: Clark & West (2007) eq. 11 on a hand-worked 3-date example.

    Actuals r = (3, -1, 2); benchmark p0 = (0, 0, 0); factor model
    p1 = (2, -1, 1).  Errors: e0 = r - p0 = (3, -1, 2),
    e1 = r - p1 = (1, 0, 1).

        f_t = e0^2 - (e1^2 - (p1 - p0)^2)
        f_0 = 9  - (1 - 4) = 12          [(p1[0]-p0[0])^2 = (2-0)^2 = 4]
        f_1 = 1  - (0 - 1) =  2          [(p1[1]-p0[1])^2 = (-1-0)^2 = 1]
        f_2 = 4  - (1 - 1) =  4          [(p1[2]-p0[2])^2 = (1-0)^2 = 1]
        f_bar = 18/3 = 6.0
        xc = f - f_bar = (6, -4, -2); sum xc^2 = 36+16+4 = 56
        gamma0 = 56/3; SE(max_lags=0) = sqrt(gamma0/n) = sqrt(56/9)
        CW = 6.0 / sqrt(56/9) = 2.4054 (4 dp)

    The original research-pass derivation incorrectly stated f_2 = 3 by
    computing (p1[2]-p0[2])^2 = 0; the correct value is (1-0)^2 = 1,
    giving f_2 = 4. The implementation follows eq. 11 exactly.

    Fault detected: wrong sign on the (p1-p0)^2 adjustment or a missing
    adjustment term changes f and therefore CW.
    """
    r = np.array([3.0, -1.0, 2.0])
    p0 = np.array([0.0, 0.0, 0.0])
    p1 = np.array([2.0, -1.0, 1.0])
    cw = clark_west_stat(r - p0, r - p1, p0, p1, max_lags=0)
    # Hand-derived: f=[12,2,4], f_bar=6, demeaned=[6,-4,-2],
    # gamma0 = 56/3, SE = sqrt(56/9), CW = 6 / sqrt(56/9)
    expected = 6.0 / math.sqrt(56.0 / 9.0)
    assert abs(cw - expected) < 1e-9, (cw, expected)
    assert abs(cw - 2.4054) < 5e-4, cw


def test_clark_west_identical_models_is_zero() -> None:
    """CW is exactly 0.0 when the factor model IS the benchmark.

    Fault detected: invented OOS evidence for a model that adds nothing.
    """
    e0 = np.array([1.5, -0.5, 2.0, 0.25])
    p0 = np.array([0.1, 0.2, 0.3, 0.4])
    cw = clark_west_stat(e0, e0.copy(), p0, p0.copy(), max_lags=0)
    assert cw == 0.0, cw


def test_clark_west_sign_tracks_adjusted_mspe() -> None:
    """CW > 0 iff the factor model wins the adjusted MSPE comparison.

    Same actuals as the KAT; a worse factor model (p1 pushes away from
    the actuals) must produce CW < 0.

    Fault detected: sign flip in f_t or in the final ratio.
    """
    r = np.array([3.0, -1.0, 2.0])
    p0 = np.zeros(3)
    better = clark_west_stat(r - p0, r - np.array([2.0, -1.0, 1.0]), p0, np.array([2.0, -1.0, 1.0]), max_lags=0)
    worse_p1 = np.array([-2.0, 1.0, -1.0])
    worse = clark_west_stat(r - p0, r - worse_p1, p0, worse_p1, max_lags=0)
    assert better > 0.0, better
    assert worse < 0.0, worse


@given(
    obs=st.lists(
        st.tuples(_FINITE, _FINITE, _FINITE, _FINITE),
        min_size=8,
        max_size=24,
    )
)
@settings(max_examples=100, deadline=None)
def test_clark_west_order_invariance_zero_lags(obs: list[tuple[float, float, float, float]]) -> None:
    """Property: with max_lags=0 the statistic ignores observation order.

    The HAC-free SE of the mean depends only on the empirical
    distribution of f_t; reordering dates must not move CW (beyond
    floating-point noise), and NaN results must be NaN for both orders.

    Fault detected: accidental order dependence (e.g. a running
    accumulator that is not reset, or lag machinery active at lags=0).
    """
    arr = np.asarray(obs, dtype=float)
    e0, e1, p0, p1 = arr[:, 0], arr[:, 1], arr[:, 2], arr[:, 3]
    cw1 = clark_west_stat(e0, e1, p0, p1, max_lags=0)
    cw2 = clark_west_stat(e0[::-1], e1[::-1], p0[::-1], p1[::-1], max_lags=0)
    if math.isnan(cw1) or math.isnan(cw2):
        assert math.isnan(cw1) and math.isnan(cw2), (cw1, cw2)
    else:
        assert abs(cw1 - cw2) < 1e-9, (cw1, cw2)


def test_clark_west_raises_on_misaligned_inputs() -> None:
    """Byzantine: mismatched array lengths must raise, not broadcast.

    Fault detected: silent numpy broadcasting of a length-1 array
    against length-N errors, producing a plausible-looking statistic
    from garbage inputs.
    """
    import pytest

    with pytest.raises(ValueError):
        clark_west_stat(
            np.array([1.0, 2.0]),
            np.array([1.0]),
            np.array([0.0, 0.0]),
            np.array([0.0, 0.0]),
            max_lags=0,
        )
    with pytest.raises(ValueError):
        clark_west_stat(
            np.array([1.0, 2.0]),
            np.array([1.0, 2.0]),
            np.array([0.0]),
            np.array([0.0, 0.0]),
            max_lags=0,
        )


def test_walk_forward_result_carries_cw() -> None:
    """F-R53 wiring: WalkForwardResult exposes oos_cw_stat (default NaN).

    Fault detected: field dropped from the dataclass or never populated —
    promote notes would silently lose the CW diagnostic.
    """
    r = WalkForwardResult(
        factor_name="x",
        horizon=5,
        per_split_ic=[0.1],
        oos_mean_ic=0.1,
        oos_ic_ir=0.5,
        sign_consistency=1.0,
        n_splits=1,
    )
    assert math.isnan(r.oos_cw_stat)
    r2 = WalkForwardResult(
        factor_name="x",
        horizon=5,
        per_split_ic=[0.1],
        oos_mean_ic=0.1,
        oos_ic_ir=0.5,
        sign_consistency=1.0,
        n_splits=1,
        oos_cw_stat=2.0,
    )
    assert r2.oos_cw_stat == 2.0


def _wf(factor_name: str, df, horizon: int = 5):
    sp = PurgedWalkForward(n_splits=4, embargo_days=5, label_horizon=5)
    return evaluate_walk_forward(get_factor(factor_name), df, sp, [horizon])[0]


def test_oos_cw_stat_deterministic_and_finite_on_synthetic() -> None:
    """Wiring: CW is deterministic and finite on a clean synthetic panel.

    Fault detected: oos_cw_stat always returning NaN (estimation sample
    never reaching min_train_obs, or an alignment bug dropping every
    date) — the diagnostic would be dead code.
    """
    df = synthetic_ohlcv(n_days=600, n_assets=8, seed=7, plant_signal=True)
    res1 = _wf("mom_20", df)
    res2 = _wf("mom_20", df)
    assert res1.oos_cw_stat == res1.oos_cw_stat, "CW is NaN on a clean panel"
    assert res1.oos_cw_stat == res2.oos_cw_stat, "CW is not deterministic"


def test_oos_cw_stat_null_and_signal_ordering() -> None:
    """Wiring: planted-signal momentum outranks a pure-noise control.

    On the planted-signal panel the momentum factor's expanding OLS has
    real slope content; the seeded noise factor does not. If the wiring
    estimated on the test window itself, or swapped the benchmark and
    factor-model roles, this ordering breaks.

    Values pinned from the run recorded in EVIDENCE.md (c7-p04);
    margins chosen from the observed spread, not the other way round.
    """
    df = synthetic_ohlcv(n_days=600, n_assets=8, seed=7, plant_signal=True)
    sig = _wf("mom_20", df)
    noise = _wf("noise_control", df)
    assert sig.oos_cw_stat > noise.oos_cw_stat, (
        f"signal CW={sig.oos_cw_stat} noise CW={noise.oos_cw_stat}"
    )


def test_oos_cw_stat_nan_on_too_short_history() -> None:
    """min_train_obs floor: CW is NaN when the estimation sample is tiny.

    Fault detected: producing a confident statistic from fewer than 30
    pooled estimation rows (the Clark-West small-P liberal failure mode).
    """
    df = synthetic_ohlcv(n_days=80, n_assets=4, seed=7)
    vals = get_factor("mom_20").compute(df)
    sp = PurgedWalkForward(n_splits=2, embargo_days=5, label_horizon=5)
    splits = list(sp.split(df))
    cw = oos_cw_stat(vals, df, splits, horizon=5, min_train_obs=10_000)
    assert math.isnan(cw), cw
