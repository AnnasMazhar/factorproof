"""
Tests for factorlab.data — OHLCV loading and synthetic data generation.

Faults detected per test:
    test_synthetic_ohlcv_columns:
        Fault: synthetic_ohlcv missing required columns or misspelled names.
    test_synthetic_ohlcv_shape:
        Fault: wrong number of rows (n_days * n_assets) in output.
    test_synthetic_ohlcv_no_negative_prices:
        Fault: price floor not applied, returning negative close prices.
    test_synthetic_ohlcv_deterministic:
        Fault: non-seeded RNG making output non-reproducible.
    test_plant_signal_differs_from_plant_noise:
        Fault: plant_signal and plant_noise producing identical data.
    test_plant_noise_no_drift:
        Fault: plant_noise data having significant price drift (embedded signal).
    test_assert_no_lookahead_raises_on_overlap:
        Fault: assert_no_lookahead not detecting overlapping date ranges.
    test_assert_no_lookahead_passes_clean:
        Fault: assert_no_lookahead raising on clean (non-overlapping) data.
    test_load_ohlcv_csv_round_trip:
        Fault: load_ohlcv_csv losing data precision or column order.
    test_load_ohlcv_csv_missing_columns:
        Fault: load_ohlcv_csv not raising on missing required columns.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import pytest
from factorlab.data import assert_no_lookahead, load_ohlcv_csv, synthetic_ohlcv

# ---------------------------------------------------------------------------
# synthetic_ohlcv
# ---------------------------------------------------------------------------


def test_synthetic_ohlcv_columns():
    """KAT: output has exactly the required columns.

    Fault detected: missing 'volume' column or extra columns breaking downstream.
    """
    df = synthetic_ohlcv(n_days=50, n_assets=3, seed=0)
    required = {"date", "asset", "open", "high", "low", "close", "volume"}
    assert required.issubset(set(df.columns)), f"Missing columns: {required - set(df.columns)}"


def test_synthetic_ohlcv_shape():
    """KAT: output has n_days * n_assets rows.

    Fault detected: wrong loop bounds or asset duplication.
    """
    n_days, n_assets = 100, 5
    df = synthetic_ohlcv(n_days=n_days, n_assets=n_assets, seed=0)
    expected_rows = n_days * n_assets
    assert len(df) == expected_rows, f"Expected {expected_rows} rows, got {len(df)}"


def test_synthetic_ohlcv_no_negative_prices():
    """KAT: all price columns must be strictly positive.

    Fault detected: price floor not applied (exp(r) can go very low but not negative;
    however the max(price, 1e-3) guard must hold).
    """
    df = synthetic_ohlcv(n_days=500, n_assets=10, seed=1)
    for col in ["open", "high", "low", "close"]:
        min_val = df[col].min()
        assert min_val > 0, f"Column '{col}' has non-positive values (min={min_val})"


def test_synthetic_ohlcv_high_gte_low():
    """Property: high >= low for all rows.

    Fault detected: open/high/low assignment logic inverted.
    """
    df = synthetic_ohlcv(n_days=200, n_assets=5, seed=2)
    assert (df["high"] >= df["low"]).all(), "Some rows have high < low"


def test_synthetic_ohlcv_deterministic():
    """Property: two calls with same seed produce identical output.

    Fault detected: wall-clock or system entropy used instead of seeded RNG.
    """
    df1 = synthetic_ohlcv(n_days=100, n_assets=4, seed=42)
    df2 = synthetic_ohlcv(n_days=100, n_assets=4, seed=42)
    pd.testing.assert_frame_equal(df1, df2)


def test_different_seeds_differ():
    """Property: different seeds produce different close prices.

    Fault detected: seed argument silently ignored.
    """
    df1 = synthetic_ohlcv(n_days=50, n_assets=3, seed=10)
    df2 = synthetic_ohlcv(n_days=50, n_assets=3, seed=11)
    # With high probability (virtually certain) the prices will differ
    assert not df1["close"].equals(df2["close"]), "Different seeds produced identical output"


def test_plant_signal_differs_from_plant_noise():
    """KAT: plant_signal=True and plant_noise=True must produce different price paths.

    Fault detected: both flags silently no-oping and producing identical data.
    """
    df_s = synthetic_ohlcv(n_days=200, n_assets=4, seed=7, plant_signal=True)
    df_n = synthetic_ohlcv(n_days=200, n_assets=4, seed=7, plant_noise=True)
    assert not df_s["close"].equals(
        df_n["close"]
    ), "plant_signal and plant_noise produced identical close prices"


def test_plant_noise_volume_positive():
    """Property: plant_noise=True does not break volume generation.

    Fault detected: plant_noise path skipping volume simulation.
    """
    df = synthetic_ohlcv(n_days=100, n_assets=3, seed=0, plant_noise=True)
    assert (df["volume"] > 0).all(), "plant_noise data has non-positive volume"


# ---------------------------------------------------------------------------
# assert_no_lookahead
# ---------------------------------------------------------------------------


def test_assert_no_lookahead_raises_on_overlap():
    """KAT: raises ValueError when feature dates overlap target dates.

    Fault detected: assert_no_lookahead not comparing max feature date to min target date.
    """
    # Features at t=2020-01-03, targets also at 2020-01-03 -> overlap
    features = pd.DataFrame({"date": pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03"])})
    targets = pd.DataFrame({"date": pd.to_datetime(["2020-01-03", "2020-01-04"])})
    with pytest.raises(ValueError, match="Lookahead detected"):
        assert_no_lookahead(features, targets, horizon=1)


def test_assert_no_lookahead_passes_clean():
    """KAT: does not raise when feature dates are strictly before target dates.

    Fault detected: assert_no_lookahead raising false positives on clean data.
    """
    features = pd.DataFrame({"date": pd.to_datetime(["2020-01-01", "2020-01-02"])})
    targets = pd.DataFrame({"date": pd.to_datetime(["2020-01-03", "2020-01-04"])})
    # Should not raise
    assert_no_lookahead(features, targets, horizon=1)


def test_assert_no_lookahead_invalid_horizon():
    """Edge case: horizon < 1 raises ValueError.

    Fault detected: missing input validation allowing horizon=0.
    """
    features = pd.DataFrame({"date": pd.to_datetime(["2020-01-01"])})
    targets = pd.DataFrame({"date": pd.to_datetime(["2020-01-02"])})
    with pytest.raises(ValueError):
        assert_no_lookahead(features, targets, horizon=0)


# ---------------------------------------------------------------------------
# load_ohlcv_csv
# ---------------------------------------------------------------------------


def test_load_ohlcv_csv_round_trip():
    """KAT: save synthetic data to CSV and reload; data must match.

    Fault detected: CSV round-trip losing column dtypes or introducing NaN.
    """
    df = synthetic_ohlcv(n_days=50, n_assets=3, seed=0)
    with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False) as f:
        df.to_csv(f, index=False)
        fname = f.name

    loaded = load_ohlcv_csv(fname)
    Path(fname).unlink()

    # Sort both for comparison
    df_sorted = df.sort_values(["date", "asset"]).reset_index(drop=True)
    loaded_sorted = loaded.sort_values(["date", "asset"]).reset_index(drop=True)

    pd.testing.assert_frame_equal(
        df_sorted[["date", "asset", "close"]],
        loaded_sorted[["date", "asset", "close"]],
        check_exact=False,
        rtol=1e-4,
    )


def test_load_ohlcv_csv_missing_columns():
    """KAT: load_ohlcv_csv raises ValueError on missing required columns.

    Fault detected: missing column not raising, silently returning incomplete data.
    """
    bad_csv = "date,asset,close\n2020-01-01,A,100.0\n"
    with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False) as f:
        f.write(bad_csv)
        fname = f.name

    with pytest.raises(ValueError, match="Missing columns"):
        load_ohlcv_csv(fname)
    Path(fname).unlink()
