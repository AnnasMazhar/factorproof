"""check_no_internal_refs.py — scan tracked files for forbidden internal tokens.

Exits non-zero on any hit. Wire into CI so the repo never ships internal references.

Forbidden tokens (case-insensitive):
  v3, sats, olympus, plutus, annasclaw
  plus absolute host paths (/home/openclaw/)

Also scans generated directories: results/, reports/

Usage:
    python scripts/check_no_internal_refs.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Token definitions
# ---------------------------------------------------------------------------

# Whole-word forbidden identifiers (case-insensitive)
FORBIDDEN_TOKENS: list[tuple[str, str]] = [
    (r"\bv3\b", "V3"),
    (r"\bsats\b", "SATS"),
    (r"\bolympus\b", "Olympus"),
    (r"\bplutus\b", "plutus"),
    (r"\bannasclaw\b", "annasclaw"),
]

# Forbidden literal substrings (no word-boundary — these are path fragments)
FORBIDDEN_SUBSTRINGS: list[tuple[str, str]] = [
    (r"/home/openclaw/", "/home/openclaw/"),
]

# Compiled patterns: list of (pattern, label)
PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(tok, re.IGNORECASE), label)
    for tok, label in FORBIDDEN_TOKENS + FORBIDDEN_SUBSTRINGS
]

# Directories to always scan even if not tracked
GENERATED_DIRS: list[str] = ["results", "reports"]

# Extensions that are plain text (others are skipped)
TEXT_EXTENSIONS: set[str] = {
    ".py",
    ".md",
    ".rst",
    ".txt",
    ".sh",
    ".yml",
    ".yaml",
    ".toml",
    ".cfg",
    ".ini",
    ".json",
    ".html",
    ".css",
    ".js",
    ".csv",
    ".tsv",
}

# Files to always skip
SKIP_NAMES: set[str] = {
    "check_no_internal_refs.py",  # this script itself names the tokens
    "uv.lock",
    "SOURCES.txt",
}

# Directories to always skip
SKIP_DIRS: set[str] = {
    ".venv",
    ".git",
    ".ruff_cache",
    ".hypothesis",
    ".pytest_cache",
    "__pycache__",
    "node_modules",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def git_tracked_files(repo_root: Path) -> list[Path]:
    """Return list of files tracked by git."""
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        return [repo_root / p for p in result.stdout.splitlines() if p.strip()]
    except subprocess.CalledProcessError:
        return []


def generated_files(repo_root: Path) -> list[Path]:
    """Return files in generated dirs that exist on disk."""
    found: list[Path] = []
    for d in GENERATED_DIRS:
        gen_dir = repo_root / d
        if gen_dir.is_dir():
            found.extend(gen_dir.rglob("*"))
    return [f for f in found if f.is_file()]


def should_skip(path: Path) -> bool:
    """Return True if this file should not be scanned."""
    if path.name in SKIP_NAMES:
        return True
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        return True
    for part in path.parts:
        if part in SKIP_DIRS:
            return True
    return False


def scan_file(path: Path) -> list[tuple[int, str, str]]:
    """Return list of (lineno, matched_token_label, line_text) for hits."""
    hits: list[tuple[int, str, str]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return hits
    for lineno, line in enumerate(text.splitlines(), start=1):
        for pat, label in PATTERNS:
            if pat.search(line):
                hits.append((lineno, label, line.rstrip()))
    return hits


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    tracked = git_tracked_files(repo_root)
    generated = generated_files(repo_root)

    # Deduplicate
    all_files: set[Path] = set(tracked) | set(generated)

    total_hits: int = 0

    for fpath in sorted(all_files):
        if should_skip(fpath):
            continue
        hits = scan_file(fpath)
        if hits:
            rel = fpath.relative_to(repo_root)
            for lineno, label, line in hits:
                print(f"FORBIDDEN [{label}]  {rel}:{lineno}  {line[:120]}")
                total_hits += 1

    if total_hits == 0:
        print("check_no_internal_refs: CLEAN — no forbidden tokens found.")
        return 0
    else:
        print(f"\ncheck_no_internal_refs: FAIL — {total_hits} forbidden token(s) found.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
