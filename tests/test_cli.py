"""
CLI subprocess tests for factor-lab.

These tests exercise the CLI entry point as a subprocess so that the exit
codes, stdout, and stderr are validated end-to-end independently of any
internal import state.  All commands run on small synthetic datasets
(n_days=400, n_assets=6) to keep the suite fast.

Fault targeted: cli.py had 0% test coverage; broken CLI plumbing or bad exit
codes could go undetected.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PY = sys.executable
_MODULE = "factorlab.cli"


def _run(*args: str, input_: str | None = None) -> subprocess.CompletedProcess:
    """Run factor-lab CLI as a subprocess and return the result."""
    cmd = [_PY, "-m", _MODULE, *args]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        input=input_,
    )


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


def test_list_exits_0():
    """factor-lab list must exit 0 and print at least one factor name."""
    result = _run("list")
    assert result.returncode == 0, f"list exited {result.returncode}\n{result.stderr}"
    assert "mom_20" in result.stdout, f"Expected factor names in output:\n{result.stdout}"


def test_list_contains_all_required_factors():
    """factor-lab list must include the control factors used in demos."""
    result = _run("list")
    assert result.returncode == 0
    for name in ("mom_20", "noise_control", "lookahead_control"):
        assert name in result.stdout, f"Factor {name!r} missing from list output"


# ---------------------------------------------------------------------------
# promote — signal (exit 0 = PROMOTE)
# ---------------------------------------------------------------------------


def test_promote_signal_exits_0():
    """factor-lab promote mom_20 --data signal must exit 0 (PROMOTE).

    Fault detected: a bug in the promotion gate or CLI plumbing could
    silently change the exit code, breaking the documented contract.
    """
    result = _run("promote", "mom_20", "--data", "signal")
    assert result.returncode == 0, (
        f"promote mom_20 --data signal should exit 0 (PROMOTE).\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "PROMOTE" in result.stdout, f"Expected PROMOTE in output:\n{result.stdout}"


def test_promote_signal_shows_gate_table():
    """Promotion output must include all 10 gate codes."""
    result = _run("promote", "mom_20", "--data", "signal")
    assert result.returncode == 0
    for gate in (
        "not_lookahead",
        "not_degenerate",
        "coverage",
        "min_observations",
        "min_abs_ic",
        "min_ic_ir",
        "hit_rate_wilson_lb",
        "max_turnover",
        "oos_consistency",
        "survives_fdr",
    ):
        assert gate in result.stdout, f"Gate {gate!r} missing from promote output:\n{result.stdout}"


def test_promote_fdr_multiplicity_in_output():
    """promote output must report m=3 when 3 horizons are searched.

    Fault targeted: BH was called with m=1 (selection bias). The note
    field is the only externally visible signal that the correction uses
    the right family size.
    """
    result = _run("promote", "mom_20", "--data", "signal")
    assert result.returncode == 0
    # The survives_fdr note line must mention m=3
    lines = result.stdout.splitlines()
    fdr_note_lines = [line for line in lines if "BH FDR" in line]
    assert fdr_note_lines, f"No FDR note line found in:\n{result.stdout}"
    assert any("m=3" in line for line in fdr_note_lines), (
        "Expected 'm=3' in FDR note, got:\n" + "\n".join(fdr_note_lines)
    )


# ---------------------------------------------------------------------------
# promote — noise (exit 1 = REJECT)
# ---------------------------------------------------------------------------


def test_promote_noise_factor_exits_1():
    """factor-lab promote noise_control --data signal must exit 1 (REJECT).

    The noise_control factor is pure noise; it must be rejected.
    A wrong exit code would silently break the 'reject-on-fail' contract.
    """
    result = _run("promote", "noise_control", "--data", "signal")
    assert result.returncode == 1, (
        f"promote noise_control should exit 1 (REJECT).\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "REJECT" in result.stdout, f"Expected REJECT in output:\n{result.stdout}"


def test_promote_unknown_factor_exits_nonzero():
    """factor-lab promote unknown_xyz must exit non-zero with an error message."""
    result = _run("promote", "unknown_xyz_factor_that_does_not_exist", "--data", "signal")
    assert result.returncode != 0, f"Unknown factor should exit non-zero, got {result.returncode}"
    # Error should appear in stderr
    assert (
        result.stderr or "Error" in result.stdout
    ), f"Expected error message for unknown factor.\nstdout: {result.stdout}\nstderr: {result.stderr}"


def test_promote_plant_signal_no_op_note():
    """--plant-signal with --data signal must emit a note to stderr (not silently ignore)."""
    result = _run("promote", "mom_20", "--data", "signal", "--plant-signal")
    # Should still succeed
    assert result.returncode == 0, f"Unexpected failure:\n{result.stderr}"
    # Note should appear
    assert (
        "no effect" in result.stderr or "Note:" in result.stderr
    ), f"Expected note about --plant-signal no-op, got stderr: {result.stderr!r}"


# ---------------------------------------------------------------------------
# screen
# ---------------------------------------------------------------------------


def test_screen_exits_0():
    """factor-lab screen --data signal --horizons 1 must exit 0 and write results."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = _run(
            "screen",
            "--data",
            "signal",
            "--horizons",
            "1",
            "--out",
            tmpdir,
        )
        assert result.returncode == 0, (
            f"screen exited {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        # factor_table.md must be written
        assert (
            Path(tmpdir) / "factor_table.md"
        ).exists(), "factor_table.md not written by screen command"


def test_screen_output_contains_promoted_rejected_summary():
    """screen output must include a Promoted/Rejected summary line."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = _run(
            "screen",
            "--data",
            "signal",
            "--horizons",
            "1",
            "--out",
            tmpdir,
        )
        assert result.returncode == 0
        assert (
            "Promoted" in result.stdout or "Rejected" in result.stdout
        ), f"No Promoted/Rejected summary in output:\n{result.stdout}"


def test_screen_writes_html_report():
    """screen must write report.html alongside the markdown table."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = _run(
            "screen",
            "--data",
            "signal",
            "--horizons",
            "1",
            "--out",
            tmpdir,
        )
        assert result.returncode == 0
        assert (Path(tmpdir) / "report.html").exists(), "report.html not written by screen command"
