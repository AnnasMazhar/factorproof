"""Fault list (quality-contract rule - each test names the fault it detects):

- test_scan_file_flags_host_path_in_eval_artifact: the host-path substring
  class in check_no_internal_refs.py silently stops matching (pattern edited
  to cover word tokens only), so evaluator pytest tracebacks carrying
  absolute venv paths pass the gate unflagged.
- test_scan_file_accepts_scrubbed_repo_prefix: the scrub convention
  (repo-relative prefix) false-positives, i.e. a well-formed scrubbed
  artifact is still flagged and the gate can never go green.
- test_tree_free_of_internal_refs: dirty generated artifacts (eval JSONs
  embedding absolute host paths from pytest tracebacks) land in reports/
  again - the exact shape that turned the gate red in prior cycles.
  Runs the checker's main() against the live tree and demands exit 0.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_checker():
    checker_path = Path(__file__).resolve().parent.parent / "scripts" / "check_no_internal_refs.py"
    spec = importlib.util.spec_from_file_location("check_no_internal_refs", checker_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _host_prefix():
    # Built at runtime so this file never literally contains the forbidden
    # substring (the checker scans this file too).
    return "/home/" + "openclaw/"


def test_scan_file_flags_host_path_in_eval_artifact(tmp_path):
    """KAT on the eval-artifact line shapes that dirtied the gate."""
    checker = _load_checker()
    prefix = _host_prefix()
    dirty = tmp_path / "eval-shape.json"
    dirty.write_text(
        "\n".join(
            [
                '"  ' + prefix + "portfolio/factor-lab/.venv/lib/python3.13/"
                "site-packages/numpy/lib/_function_base_impl.py:3036: "
                'RuntimeWarning: invalid value encountered in divide",',
                '"- generated xml file: ' + prefix + "portfolio/factor-lab/"
                '.cycle-eval-c6-p7.xml -",',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    hits = checker.scan_file(dirty)
    assert len(hits) == 2, f"expected 2 host-path hits, got {hits}"


def test_scan_file_accepts_scrubbed_repo_prefix(tmp_path):
    """The scrubbed form must be clean, or the gate can never go green."""
    checker = _load_checker()
    clean = tmp_path / "eval-shape.json"
    clean.write_text(
        '"  repo/.venv/lib/python3.13/site-packages/numpy/lib/'
        "_function_base_impl.py:3036: RuntimeWarning: invalid value "
        'encountered in divide",\n'
        '"- generated xml file: repo/.cycle-eval-c6-p7.xml -",\n',
        encoding="utf-8",
    )
    assert checker.scan_file(clean) == [], "scrubbed artifact false-positived"


def test_tree_free_of_internal_refs():
    """The live tree (tracked files + reports/ + results/) must be clean."""
    checker = _load_checker()
    assert checker.main() == 0, (
        "check_no_internal_refs.main() is red on the live tree - "
        "a generated artifact embeds a forbidden token"
    )
