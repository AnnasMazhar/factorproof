# CONTRIBUTING.md

## Getting started

```bash
uv venv && uv pip install -e '.[dev]'
```

## Adding a factor

1. Subclass `Factor` in `src/factorlab/factors/library.py`.
2. Set `name`, `category`, `description`, `params`.
3. Implement `compute(df) -> pd.Series` with MultiIndex (date, asset).
4. Register in `src/factorlab/factors/__init__.py:REGISTRY`.
5. Add at least one KAT in `tests/test_evaluate.py` with a hand-computed expected IC.
6. Add a docstring explaining the fault the test detects.
7. If the factor uses future data, set `uses_future_data: bool = True` on the class.

## Code standards

- Python 3.11+ syntax, type hints on all public functions.
- `ruff check .` and `ruff format --check .` must pass.
- `pytest -q` must pass with no network calls.
- No bare `except:`, no `assert` in library code, no commented-out blocks.
- Conventional commits: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`.

## Test rules (from the quality contract)

Every test must carry a docstring naming the fault it detects.
Tests that only assert "result is not None" or snapshot unverified output
will be rejected in review.

## Quality contract

Read `portfolio/specs/QUALITY-CONTRACT.md` before submitting a PR.
In particular: every new core algorithm must be validated against an external
ground truth and traced in `docs/IMPLEMENTATION-NOTES.md`.
