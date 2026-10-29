"""
BH family-scope lock tests (C7-F1 / F-D1, docs/RESEARCH.md 26.1).

Faults detected per test:
    test_bh_scope_factor_level_vs_per_horizon_flips_noise_verdict:
        Fault: BH applied per-horizon independently (or on the full
        (factor, horizon) grid) instead of one best-horizon p per factor.
        On the KAT, per-horizon BH promotes a seeded noise control that
        the factor-level family rejects — scope is determinative.
    test_committed_proof_passes_scope_check:
        Fault: the committed proof artifact computed at an undeclared or
        wrong BH scope, or the checker refusing a valid proof.
    test_forged_per_horizon_flags_fail_scope_check:
        Fault: checker accepting bh_fdr_pass flags that do not match a
        factor-level BH recompute (flags flipped to per-horizon results).
    test_missing_family_declaration_fails_scope_check:
        Fault: checker accepting a proof whose markdown never states the
        BH family size (scope unverifiable).
    test_declared_family_size_mismatch_fails_scope_check:
        Fault: checker trusting a declared m that disagrees with the
        JSON's factor count.
    test_generator_md_prose_declares_scope:
        Fault: prove_on_real_data.py regenerating the proof with the old
        "across family" prose that hides the scope (no 'family: m factors').
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

from factorlab.significance import benjamini_hochberg

_CHECKER = Path(__file__).resolve().parents[1] / "scripts" / "check_real_data_proof.py"
_PROOF_JSON = Path(__file__).resolve().parents[1] / "reports" / "real-data-proof.json"
_PROOF_MD = Path(__file__).resolve().parents[1] / "reports" / "real-data-proof.md"
_GENERATOR = Path(__file__).resolve().parents[1] / "scripts" / "prove_on_real_data.py"

sys.path.insert(0, str(_CHECKER.parent))
import check_real_data_proof as checker  # noqa: E402


def _run_checker() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_CHECKER)], capture_output=True, text=True, timeout=120
    )


def _kat_rows() -> list[dict]:
    """13 factors x per-factor best-horizon KAT reproducing the real-panel structure.

    Each row is the factor's BEST-HORIZON p-value (the input to factor-level BH).

    noise_control: best horizon is H=5 where p=0.50 — under factor-level BH at
    q=0.15 it is NOT discovered because 0.50 clears no BH threshold.
    lookahead_control: best horizon is H=5, p=1e-8 — clearly discovered.

    The per-horizon view (H=1 across all 13 factors) uses p=1e-4 for
    noise_control at H=1, which IS discovered — demonstrating that the scope
    choice is determinative.
    """
    return [
        {"factor": "lookahead_control", "horizon": 5, "p_raw": 1e-8},
        {"factor": "rev_5", "horizon": 1, "p_raw": 3e-4},
        {"factor": "volume_z_20", "horizon": 1, "p_raw": 0.019},
        {"factor": "noise_control", "horizon": 5, "p_raw": 0.50},
        {"factor": "mom_20", "horizon": 5, "p_raw": 0.10},
        {"factor": "mom_60", "horizon": 5, "p_raw": 0.40},
        {"factor": "rsi_14", "horizon": 5, "p_raw": 0.50},
        {"factor": "vol_20", "horizon": 5, "p_raw": 0.50},
        {"factor": "skew_20", "horizon": 5, "p_raw": 0.50},
        {"factor": "turn_20", "horizon": 5, "p_raw": 0.50},
        {"factor": "high_52w", "horizon": 5, "p_raw": 0.50},
        {"factor": "amihud_20", "horizon": 5, "p_raw": 0.50},
        {"factor": "ivff3_60", "horizon": 5, "p_raw": 0.50},
    ]


def _kat_h1_rows() -> list[dict]:
    """The same 13 factors' H=1 p-values for the per-horizon BH view.

    noise_control at H=1 has p=1e-4 (small), which IS discovered under
    per-horizon BH — the key difference from the factor-level view.
    """
    return [
        {"factor": "lookahead_control", "horizon": 1, "p_raw": 0.50},
        {"factor": "rev_5", "horizon": 1, "p_raw": 3e-4},
        {"factor": "volume_z_20", "horizon": 1, "p_raw": 0.019},
        {"factor": "noise_control", "horizon": 1, "p_raw": 1e-4},
        {"factor": "mom_20", "horizon": 1, "p_raw": 0.50},
        {"factor": "mom_60", "horizon": 1, "p_raw": 0.50},
        {"factor": "rsi_14", "horizon": 1, "p_raw": 0.50},
        {"factor": "vol_20", "horizon": 1, "p_raw": 0.50},
        {"factor": "skew_20", "horizon": 1, "p_raw": 0.50},
        {"factor": "turn_20", "horizon": 1, "p_raw": 0.50},
        {"factor": "high_52w", "horizon": 1, "p_raw": 0.50},
        {"factor": "amihud_20", "horizon": 1, "p_raw": 0.50},
        {"factor": "ivff3_60", "horizon": 1, "p_raw": 0.50},
    ]


def test_bh_scope_factor_level_vs_per_horizon_flips_noise_verdict() -> None:
    """C7-F1 KAT: per-horizon BH discovers the noise control; factor-level does not.

    13 best-horizon p-values at factor level (q=0.15):
        factor-level BH on (1e-8, 3e-4, 0.019, 0.10, 0.40, 0.50 x8)
        -> discovers {lookahead_control, rev_5, volume_z_20}; noise_control
        carries p=0.50 at its best horizon H=5 and is NOT discovered.

    Same 13 factors' H=1 p-values (per-horizon BH at q=0.15):
        noise_control has p=1e-4 at H=1 -> IS discovered;
        lookahead_control has p=0.50 at H=1 -> is NOT discovered.

    Fault detected: applying BH per-horizon (or over the 39-cell grid)
    instead of the factor set.
    """
    rows = _kat_rows()
    q = 0.15

    # Factor-level: one best-horizon p per factor.
    factor_p = [r["p_raw"] for r in rows]
    factor_mask = benjamini_hochberg(factor_p, q=q)
    factor_disc = {r["factor"] for r, m in zip(rows, factor_mask) if m}

    # Per-horizon (the bug): BH at H=1 with noise_control's H=1 p-value exposed.
    h1_rows = _kat_h1_rows()
    h1_mask = benjamini_hochberg([r["p_raw"] for r in h1_rows], q=q)
    h1_disc = {r["factor"] for r, m in zip(h1_rows, h1_mask) if m}

    assert factor_disc == {"lookahead_control", "rev_5", "volume_z_20"}
    assert h1_disc == {"noise_control", "rev_5", "volume_z_20"}
    # Scope is determinative, not cosmetic: the verdicts disagree.
    assert "noise_control" in h1_disc and "noise_control" not in factor_disc
    assert "lookahead_control" in factor_disc and "lookahead_control" not in h1_disc


def test_committed_proof_passes_scope_check() -> None:
    """The committed proof artifact declares and satisfies the factor-level scope.

    Fault detected: committed proof computed at another scope, or the
    checker regressing into false failures on a valid artifact.
    """
    fails = checker.check_bh_family_scope()
    assert fails == [], fails


def test_forged_per_horizon_flags_fail_scope_check(tmp_path: Path, monkeypatch) -> None:
    """Forged bh_fdr_pass flags (per-horizon results) fail the recompute.

    Fault detected: checker trusting stored flags instead of recomputing
    BH from p_raw at the declared m and q.
    """
    data = json.loads(_PROOF_JSON.read_text(encoding="utf-8"))
    rows = data["real_factors"]
    # Flip the noise_control flag on (it passes per-horizon BH at H=1
    # on the real panel) and correct the delta so only the flag check
    # can catch the forgery.
    for r in rows:
        if r["factor"] == "noise_control":
            r["bh_fdr_pass"] = True
    data["delta"]["n_bh_fdr_sig"] = sum(1 for r in rows if r.get("bh_fdr_pass"))
    forged_json = tmp_path / "real-data-proof.json"
    forged_json.write_text(json.dumps(data), encoding="utf-8")

    monkeypatch.setattr(checker, "_PROOF_JSON", forged_json)
    monkeypatch.setattr(checker, "_PROOF_MD", _PROOF_MD)
    fails = checker.check_bh_family_scope()
    assert any("BH SCOPE FAIL" in f and "noise_control" in f for f in fails), fails


def test_missing_family_declaration_fails_scope_check(tmp_path: Path, monkeypatch) -> None:
    """A proof whose markdown never states 'family: <m> factors' is rejected.

    Fault detected: checker accepting scope-unverifiable prose (the old
    "across family" wording).
    """
    md_text = _PROOF_MD.read_text(encoding="utf-8")
    stripped = md_text.replace(
        "family: 13 factors, one best-horizon p per factor; not per-horizon", "across family"
    )
    assert "family: 13 factors" not in stripped  # the old wording must be gone
    bad_md = tmp_path / "real-data-proof.md"
    bad_md.write_text(stripped, encoding="utf-8")

    monkeypatch.setattr(checker, "_PROOF_JSON", _PROOF_JSON)
    monkeypatch.setattr(checker, "_PROOF_MD", bad_md)
    fails = checker.check_bh_family_scope()
    assert fails and "family size" in fails[0], fails


def test_declared_family_size_mismatch_fails_scope_check(tmp_path: Path, monkeypatch) -> None:
    """Declared m disagreeing with the JSON's factor count is rejected.

    Fault detected: checker trusting prose over the artifact's own rows.
    """
    md_text = _PROOF_MD.read_text(encoding="utf-8")
    bad_md = tmp_path / "real-data-proof.md"
    bad_md.write_text(md_text.replace("family: 13 factors", "family: 39 factors"), encoding="utf-8")

    monkeypatch.setattr(checker, "_PROOF_JSON", _PROOF_JSON)
    monkeypatch.setattr(checker, "_PROOF_MD", bad_md)
    fails = checker.check_bh_family_scope()
    assert any("SCOPE FAIL" in f and "m=39" in f for f in fails), fails


def test_generator_md_prose_declares_scope() -> None:
    """prove_on_real_data.py emits the scope-declaring BH prose.

    Fault detected: generator regenerating the markdown with the old
    "across family" line that hides the family size — the checker would
    then reject a freshly generated proof.
    """
    src = _GENERATOR.read_text(encoding="utf-8")
    assert "family: {len(real_rows)} factors" in src
    assert "across family" not in src


def test_end_to_end_checker_green() -> None:
    """Full checker subprocess exits 0 and prints PROOF_COMPLETE.

    Fault detected: the new check_bh_family_scope wiring breaking the
    real proof gate (e.g. an import or path error at runtime).
    """
    proc = _run_checker()
    assert proc.returncode == 0, (proc.stdout, proc.stderr)
    assert "PROOF_COMPLETE" in proc.stdout


def test_hypothesis_bh_flags_match_scipy_style_reference() -> None:
    """Cross-check BH against a from-scratch reference on random p-vectors.

    Fault detected: a regression in benjamini_hochberg itself that would
    silently invalidate both the proof and the scope check.
    """
    from hypothesis import given, settings
    from hypothesis import strategies as st

    def ref_bh(p: list[float], q: float) -> list[bool]:
        m = len(p)
        order = sorted(range(m), key=lambda i: p[i])
        max_k = 0
        for k, i in enumerate(order, start=1):
            if p[i] <= q * k / m:
                max_k = k
        return [p[i] <= q * max_k / m for i in range(m)]

    @given(
        pvals=st.lists(
            st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
            min_size=1,
            max_size=20,
        ),
        q=st.floats(min_value=0.01, max_value=0.25),
    )
    @settings(max_examples=50, deadline=None)
    def _inner(pvals: list[float], q: float) -> None:
        if any(math.isnan(p) for p in pvals):
            return
        got = list(benjamini_hochberg(pvals, q=q))
        exp = ref_bh(pvals, q)
        assert [bool(x) for x in got] == exp, (pvals, q, got, exp)

    _inner()
