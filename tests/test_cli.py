"""
CLI ergonomics tests.

Faults detected per test:
    test_screen_bad_horizons_clean_error:
        Fault: cmd_screen raising an unhandled ValueError traceback on
        non-integer --horizons input (stranger sees internals, no fix hint).
    test_screen_zero_horizons_clean_error:
        Fault: cmd_screen accepting non-positive horizons that break
        evaluation downstream instead of rejecting at the argument layer.
    test_explain_unknown_factor_clean_error:
        Fault: cmd_explain printing the KeyError repr (extra quoting) for an
        unknown factor name instead of a plain actionable message.
"""

from __future__ import annotations

import argparse

from factorlab.cli import cmd_explain, cmd_screen


def _screen_args(horizons: str) -> argparse.Namespace:
    return argparse.Namespace(data="synthetic", horizons=horizons, out="/tmp/bad_h", seed=7)


def test_screen_bad_horizons_clean_error(capsys) -> None:
    rc = cmd_screen(_screen_args("abc"))
    assert rc == 1
    err = capsys.readouterr().err
    assert "--horizons must be comma-separated positive integers" in err
    assert "'abc'" in err


def test_screen_zero_horizons_clean_error(capsys) -> None:
    rc = cmd_screen(_screen_args("1,0,20"))
    assert rc == 1
    err = capsys.readouterr().err
    assert "--horizons must be comma-separated positive integers" in err


def test_explain_unknown_factor_clean_error(capsys) -> None:
    args = argparse.Namespace(factor="nosuchfactor")
    rc = cmd_explain(args)
    assert rc == 1
    err = capsys.readouterr().err
    assert err.startswith("Error: Unknown factor: 'nosuchfactor'.")
    assert "Available:" in err
