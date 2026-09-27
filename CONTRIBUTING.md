# CONTRIBUTING.md

## Getting started

```bash
git clone https://github.com/AnnasMazhar/factor-lab.git
cd factor-lab
uv venv && uv pip install -e '.[dev]'
pytest -q       # all tests must pass
ruff check .    # must be clean
```

## Adding a factor

1. Subclass `Factor` in `src/factorlab/factors/library.py`.
2. Set `name`, `category`, `description`, `params`.
3. Implement `compute(df) -> pd.Series` with MultiIndex (date, asset).
4. Register in `src/factorlab/factors/__init__.py` `REGISTRY`.
5. Add at least one known-answer test (KAT) in `tests/test_evaluate.py`:
   - Derive the expected IC value outside the codebase (by hand or from a published example).
   - Docstring must name the fault the test detects.
6. If the factor uses future data, set `uses_future_data: bool = True` on the class.

## Code standards

- Python 3.11+ syntax, type hints on all public functions.
- `ruff check .` and `ruff format --check .` must pass before submitting a PR.
- `pytest -q` must pass with no network calls.
- No bare `except:`, no `assert` in library code, no commented-out blocks.
- Conventional commits: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`.

## Test rules (quality contract)

Every test must carry a docstring naming the fault it detects. Tests that only
assert `result is not None` or snapshot unverified output will be rejected in review.
Self-consistency tests (my code agrees with my other code) are not evidence.
Every core algorithm must be validated against at least one published value,
first-principles derivation, or external specification.

## Pull request checklist

- [ ] `pytest -q` passes offline
- [ ] `ruff check .` and `ruff format --check .` clean
- [ ] New factor: KAT added, fault named, `IMPLEMENTATION-NOTES.md` updated
- [ ] Conventional commit message, no AI attribution in commit trailer
- [ ] No network calls in tests or library code
