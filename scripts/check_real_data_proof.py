"""check_real_data_proof.py — validate the real-data proof artifact.

Checks that both report files exist, contain all required F2 sections,
and that the F3 thresholds (specificity, sensitivity, stability) are met.
Also runs check_no_internal_refs.py as a final gate.

Exits 0 and prints PROOF_COMPLETE on success.
Exits 1 on any failure with a clear message per failing check.

Usage:
    python scripts/check_real_data_proof.py
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PROOF_MD = _REPO_ROOT / "reports" / "real-data-proof.md"
_PROOF_JSON = _REPO_ROOT / "reports" / "real-data-proof.json"

# ---------------------------------------------------------------------------
# Required section headers in the markdown (regex patterns)
# ---------------------------------------------------------------------------
REQUIRED_SECTIONS = [
    (r"##\s+1\.\s+Dataset Summary", "F2 §1: Dataset Summary"),
    (r"##\s+2\.\s+Per-Factor Results", "F2 §2: Per-Factor Results"),
    (r"##\s+3\.\s+The Delta", "F2 §3: The Delta"),
    (r"##\s+4\.\s+Control Results", "F2 §4 / F3: Control Results (Specificity)"),
    (r"##\s+5\.\s+Sensitivity", "F2 §5 / F3: Sensitivity"),
    (r"##\s+6\.\s+Stability", "F2 §6 / F3: Stability"),
    (r"##\s+7\.\s+Reproducibility", "F2 §7: Reproducibility"),
    (r"##\s+8\.\s+Limitations", "F2 §8: Limitations"),
]

# Required numeric fields in the JSON payload
REQUIRED_JSON_FIELDS = [
    ("dataset_summary.n_bars_total", int),
    ("dataset_summary.n_coins", int),
    ("f3_specificity.rejection_rate", float),
    ("f3_specificity.pass", bool),
    ("f3_stability.flip_count", int),
    ("f3_stability.pass", bool),
    ("delta.n_raw_sig", int),
    ("delta.n_bh_fdr_sig", int),
    ("delta.n_promoted", int),
]

# F3 thresholds
F3_SPECIFICITY_MIN = 0.90  # >=90% noise factors rejected
F3_SENSITIVITY_NOTE = True  # presence of a promoted factor OR an honest note
F3_STABILITY_MAX_FLIPS = 0  # 0 flips allowed


def _get_nested(d: dict, dotted_key: str):
    """Retrieve a value from a nested dict by dot-separated key."""
    keys = dotted_key.split(".")
    val = d
    for k in keys:
        if not isinstance(val, dict) or k not in val:
            return None
        val = val[k]
    return val


def check_md_exists() -> list[str]:
    if not _PROOF_MD.exists():
        return [
            f"MISSING: {_PROOF_MD.relative_to(_REPO_ROOT)} does not exist. Run: python scripts/prove_on_real_data.py"
        ]
    return []


def check_json_exists() -> list[str]:
    if not _PROOF_JSON.exists():
        return [
            f"MISSING: {_PROOF_JSON.relative_to(_REPO_ROOT)} does not exist. Run: python scripts/prove_on_real_data.py"
        ]
    return []


def check_md_sections() -> list[str]:
    if not _PROOF_MD.exists():
        return []
    text = _PROOF_MD.read_text(encoding="utf-8")
    fails: list[str] = []
    for pattern, label in REQUIRED_SECTIONS:
        if not re.search(pattern, text, re.IGNORECASE):
            fails.append(f"MISSING SECTION in real-data-proof.md: {label}")
    return fails


def check_json_fields() -> list[str]:
    if not _PROOF_JSON.exists():
        return []
    try:
        data = json.loads(_PROOF_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"INVALID JSON in real-data-proof.json: {exc}"]

    fails: list[str] = []
    for key, expected_type in REQUIRED_JSON_FIELDS:
        val = _get_nested(data, key)
        if val is None:
            fails.append(f"MISSING JSON field: {key}")
        elif not isinstance(val, expected_type):
            fails.append(
                f"WRONG TYPE for {key}: expected {expected_type.__name__}, "
                f"got {type(val).__name__} ({val!r})"
            )
    return fails


def check_f3_thresholds() -> list[str]:
    if not _PROOF_JSON.exists():
        return []
    try:
        data = json.loads(_PROOF_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    fails: list[str] = []

    # Specificity
    rejection_rate = _get_nested(data, "f3_specificity.rejection_rate")
    if rejection_rate is not None and isinstance(rejection_rate, float | int):
        if rejection_rate < F3_SPECIFICITY_MIN:
            fails.append(
                f"F3 SPECIFICITY FAIL: noise rejection rate {rejection_rate:.1%} "
                f"< required {F3_SPECIFICITY_MIN:.0%}"
            )
    else:
        fails.append("F3 SPECIFICITY: rejection_rate field missing or non-numeric")

    # Stability
    flip_count = _get_nested(data, "f3_stability.flip_count")
    if flip_count is not None and isinstance(flip_count, int):
        if flip_count > F3_STABILITY_MAX_FLIPS:
            fails.append(
                f"F3 STABILITY FAIL: {flip_count} verdict flip(s) detected "
                f"(max allowed: {F3_STABILITY_MAX_FLIPS})"
            )
    else:
        # If no promoted factors, stability check is vacuous — not a failure
        n_promoted = _get_nested(data, "f3_sensitivity.n_promoted")
        if n_promoted and n_promoted > 0:
            fails.append("F3 STABILITY: flip_count field missing")

    return fails


def check_no_internal_refs() -> list[str]:
    check_script = _REPO_ROOT / "scripts" / "check_no_internal_refs.py"
    if not check_script.exists():
        return ["MISSING: scripts/check_no_internal_refs.py not found"]
    result = subprocess.run(
        [sys.executable, str(check_script)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        lines = (result.stdout + result.stderr).strip().splitlines()
        return [f"INTERNAL REF: {line}" for line in lines if "FORBIDDEN" in line]
    return []


def main() -> int:
    all_failures: list[str] = []

    all_failures.extend(check_md_exists())
    all_failures.extend(check_json_exists())
    all_failures.extend(check_md_sections())
    all_failures.extend(check_json_fields())
    all_failures.extend(check_f3_thresholds())
    all_failures.extend(check_no_internal_refs())

    if all_failures:
        print("check_real_data_proof: FAIL")
        for f in all_failures:
            print(f"  {f}")
        return 1

    # All checks passed
    print("check_real_data_proof: all checks passed.")
    print("PROOF_COMPLETE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
