# reports/improvements.md — factor-lab improvement log

## Improve pass 2 (cycle 1) — 2026-09-27

### Findings addressed

Three issues fixed: one credibility-breaking fact error in the README, one stale badge,
and actionable error messages for the two most common failure paths.

---

#### Finding 1 (BLOCKER) — rho=0.08 in README, code has rho=0.15

The README stated `rho=0.08` twice in the "Real results" section. `src/factorlab/data.py`
line 140 has `rho = 0.15`. A reviewer running `grep rho src/factorlab/data.py` would
immediately find the conflict. Fixed: both README occurrences corrected to `rho=0.15`.

Files changed: `README.md` (lines 101, 125).

---

#### Finding 2 (MINOR) — badge stale: `96 passed` vs actual `105`

The Tests badge in README said `96 passed`. Actual count after pass 1: 105.

```
$ .venv/bin/pytest 2>&1 | tail -1
105 passed in 27.14s
```

Fixed: badge updated to `105 passed`.

Files changed: `README.md` (line 6).

---

#### Finding 3 (ADOPTION) — error messages non-actionable on three paths

**a) `load_ohlcv_csv` — missing columns**

Before:
```
ValueError: Missing columns in CSV: {'high', 'low', 'open', 'volume'}
```
A stranger sees the missing set but not what columns ARE required. After:
```
ValueError: CSV is missing required columns: ['high', 'low', 'open', 'volume'].
Required: ['asset', 'close', 'date', 'high', 'low', 'open', 'volume'].
Found: ['asset', 'close', 'date'].
```

**b) `PurgedWalkForward.split` — panel too short**

Before:
```
ValueError: Not enough dates (45) for 5 splits with label_horizon=20 and embargo=20.
```
After:
```
ValueError: Not enough dates (45) for 5 walk-forward splits with label_horizon=20
and embargo_days=20. Need at least 45 dates. Fix: extend the panel, or reduce
n_splits/horizon in PromotionConfig.
```
(also tells user the fix)

**c) `evaluate_walk_forward` — no splits generated**

Before:
```
ValueError: No valid splits generated. Check panel length and splitter params.
```
After includes splitter config and fix instruction.

**d) CLI — missing data file raises unhandled traceback**

Before: `factor-lab screen --data /bad/path.csv` printed a FileNotFoundError traceback.
After: clean error with actionable hint:
```
Error: data file not found: '/bad/path.csv'.
Use --data synthetic, --data signal, --data noise, or a valid CSV path.
EXIT: 1
```

Files changed: `src/factorlab/data.py`, `src/factorlab/cv.py`, `src/factorlab/cli.py`,
`tests/test_data.py` (regex updated to match new wording; fault detection unchanged).

---

### Metrics delta

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| Test count | 105 | 105 | no change |
| README rho claim | 0.08 (wrong) | 0.15 (matches code) | ✓ fixed |
| Tests badge | 96 (stale) | 105 (correct) | ✓ fixed |
| CLI missing-file error | traceback | clean message + hint | ✓ |
| CSV missing-columns error | set of missing only | missing + required + found | ✓ |
| Panel-too-short error | no fix hint | fix instruction included | ✓ |
| Ruff clean | yes | yes | no change |

---



### Finding addressed

**M01 (major)** from `docs/ADVERSARIAL-REVIEW.md`:

> A factor that blends future data without setting `uses_future_data=True` bypasses
> all gates and can be PROMOTED. The statistical tests cannot detect subtle lookahead
> contamination.

The adversarial review demonstrated this with `SlightLookahead` — a factor combining
20-day momentum with 10% weight on a 4-day future return window (`shift(-2)`) — which
was PROMOTED (IC=0.032, IC-IR=0.074) because Gate 0 only fires for factors that
explicitly declare `uses_future_data=True`.

---

### Before (baseline)

```
$ .venv/bin/pytest --tb=short 2>&1 | tail -3
102 passed in 27.52s
```

SlightLookahead (from adversarial review M01) bypasses detection:

```python
class SlightLookahead(Factor):
    uses_future_data = False   # NOT flagged
    def compute(self, df):
        mom = log(close / close.shift(20))
        future_smooth = log(close.shift(-2) / close.shift(2)) * 0.1  # lookahead
        return melt(mom + future_smooth)
```

Result before fix:

```
Factor:  slight_lookahead
Verdict: PROMOTE            ← wrong; factor uses future data
IC=0.032, IC-IR=0.074
```

M01 status: `accepted_limitation` — no code path detected this.

---

### Fix implemented

**`src/factorlab/cv.py`** — added `check_lookahead_source(factor) -> list[str]`:

Inspects the `compute()` method source with `inspect.getsource()` and searches for
`.shift(-N)` patterns via regex. Returns a list of suspicious patterns (e.g.
`["shift(-2)"]`) or empty list if none found or source is unavailable.

The regex `r'\.shift\(\s*(-\s*\d+)'` matches:
- `.shift(-1)`, `.shift(-20)`, `.shift( -3 )` (with whitespace)
- Does NOT match `.shift(5)` (positive shifts access past data — legitimate)

**`src/factorlab/promote.py`** — added Gate 0.5 (`no_negative_shifts`):

Inserted between Gate 0 (structural flag) and computing factor values. If
`check_lookahead_source()` finds negative shifts, the factor is immediately rejected
with a reason listing the specific patterns and instructing the author to set
`uses_future_data=True` if the usage is intentional.

Gate sequence is now:
1. Gate 0: `not_lookahead` — structural `uses_future_data` flag
2. Gate 0.5: `no_negative_shifts` — source inspection for `.shift(-N)` ← new
3. Gate 1+: statistical gates (degenerate, coverage, IC, etc.)

**`tests/test_adversarial.py`** — 3 new tests:

- `test_slight_lookahead_detected_by_source_inspection`: replicates exact M01 attack;
  asserts `SlightLookahead` is now REJECTED with `no_negative_shifts` gate FAIL
- `test_check_lookahead_source_finds_negative_shifts`: KAT on regex — verifies
  `shift(-1)`, `shift(-20)` detected; `shift(5)` (past data) NOT detected
- `test_clean_factor_no_negative_shifts`: regression — all 12 non-lookahead registered
  factors must return empty list from `check_lookahead_source()`

---

### After

```
$ .venv/bin/pytest --tb=short 2>&1 | tail -3
105 passed in 27.64s
```

SlightLookahead is now rejected:

```
$ python -c "
from factorlab.data import synthetic_ohlcv
from factorlab.factors.base import Factor
from factorlab.factors.library import _pivot_close, _melt
from factorlab.promote import promote, PromotionConfig
import numpy as np

class SlightLookahead(Factor):
    name = 'slight_lookahead'
    category = 'test'
    description = 'test'
    params = {}
    uses_future_data = False

    def compute(self, df):
        close = _pivot_close(df)
        mom = np.log(close / close.shift(20))
        future_smooth = np.log(close.shift(-2) / close.shift(2)) * 0.1
        return _melt(mom + future_smooth)

df = synthetic_ohlcv(n_days=500, n_assets=6, seed=7, plant_signal=True)
decision = promote(SlightLookahead(), df)
print(decision)
"
Factor:  slight_lookahead
Verdict: REJECT

Gate                                         Obs    Threshold   Pass
----------------------------------- ------------ ------------ ------
not_lookahead                                 no           no   PASS
no_negative_shifts                      shift(-2)         none   FAIL
  note: compute() contains negative-shift patterns that access future rows: shift(-2). Set uses_future_data=True if this is intentional.
```

---

### Metrics delta

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| Test count | 102 | 105 | +3 |
| M01 status | `accepted_limitation` | `fixed` | ✓ |
| SlightLookahead verdict | PROMOTE | REJECT | ✓ |
| mom_20 (planted signal) | PROMOTE | PROMOTE | no change |
| noise_control | REJECT | REJECT | no change |
| lookahead_control | REJECT | REJECT | no change |
| All 12 clean factors source-clean | — | confirmed | ✓ |
| Ruff clean | yes | yes | no change |

---

### Limitations of the fix

- **Source availability**: `inspect.getsource()` requires the factor to be defined in a
  real source file. Factors defined in the REPL, via `exec()`, or in C extensions cannot
  be inspected. The gate passes with `not_applicable` note in these cases.
- **Indirect patterns**: a factor that stores a negatively-shifted series in a helper
  function called by `compute()` will not be caught (only `compute()` itself is inspected).
  Authors must ensure the top-level `compute()` method directly contains the shift call.
- **Intentional labelling factors**: a supervised labelling helper that computes future
  returns for training targets would be rejected by this gate. These should set
  `uses_future_data=True` explicitly — which is the correct contract.

M01 is downgraded from `accepted_limitation` to `fixed` in `docs/ADVERSARIAL-REVIEW.md`.

---

## Improve pass 2 (cycle 2) — 2026-10-12 — c2-p09-improve-2

Baseline quoted exactly as mandated: cycle 1 mutation gate killed 878/1977 mutants = 44.4%
(authoritative: reports/mutation-c1.json). Gate: 70%.

### Scope of this pass

Adoption readiness + ecosystem gaps: stranger-actionable errors, docs matching the code
exactly, packaging/versioning check, one concrete integration example against a real
external tool — then the single biggest README credibility gap fixed.

### Finding addressed (credibility gap)

**Docs contradicted the code on lookahead detection.** After the cycle-1 M01 fix (Gate 0.5
source scan for `.shift(-N)`), `README.md` Limitations still said "Lookahead detection is
opt-in ... it does not catch subtle contamination", and `docs/ADOPTION.md` §3.5 said the
same — while §8.4 of the same file documented the tripwire catching a `shift(-5)` factor.
A skeptical reviewer running the M01 attack would see REJECT where the docs promise a miss.
Fixed: README bullet rewritten to "two-layered, not airtight" (flag + source scan; residual
is evasion-only); ADOPTION §3.5 rewritten to match §8.4, with the executed evidence cited.

**Stale Tests badge:** `110 passed` vs actual `130` at pass start. Fixed to `133 passed`
(after this pass's +3 tests).

### Ergonomics fixes (with tests)

1. `factor-lab screen --horizons abc` raised an unhandled `ValueError` traceback. Now:
```
Error: --horizons must be comma-separated positive integers (e.g. '1,5,20'), got 'abc'.
```
exit 1. Non-positive horizons (`1,0,20`) rejected the same way.
2. `explain`/`promote` on an unknown factor printed the KeyError repr
(`Error: "Unknown factor: ..."` with extra quoting). Now prints the plain message with
the available-factor list, exit 1.
3. `tests/test_cli.py` (new, 3 tests, fault-list docstring per quality contract).

### Integration example (real external tool)

`examples/integrate_alphalens.py` (new, committed): gates `mom_20` on the planted-signal
panel, then hands the identical `Factor.compute()` Series to alphalens-reloaded 0.4.6
`get_clean_factor_and_forward_returns`. Prints SKIP + exit 0 when alphalens is absent so
fresh clones stay green. Executed 2026-10-12:

```
factorproof verdict for mom_20: promote
alphalens 0.4.6: factor_data shape (17520, 5)
alphalens mean IC:
1D     0.037336
5D     0.019585
20D    0.008899
INTEGRATION_OK
```

Matches `docs/ADOPTION.md` §7.1 numbers (0.0373/0.0196/0.0089) — the recipe reproduces.

### Drive-by: checker-clean generated reports

`scripts/check_no_internal_refs.py` FAILED on 6 hits — all absolute host-path
prefixes (redacted here; the literal path tripped the very checker being
documented) embedded in the untracked evaluator artifacts `reports/eval-c2-p6.json` /
`reports/eval-c2-p7.json` (pytest warning tracebacks). Mechanically scrubbed the repo
prefix to `repo/` (JSON re-validated); checker now CLEAN. Not caused by this pass;
pre-existing since the c2-p06/p07 eval runs.

### Packaging / versioning check

`pyproject.toml` 0.1.0 matches `CHANGELOG.md` 0.1.0 entry; `[project.scripts]` entry point
verified live (`factor-lab` CLI runs from the venv); CI already runs
`check_no_internal_refs.py`. No change needed. `ruff format --check` drift (9 files) is
pre-existing and untouched — this pass's files (`cli.py`, `test_cli.py`,
`integrate_alphalens.py`) are all format-clean.

### Before / after (raw output)

```
$ .venv/bin/python -m pytest 2>&1 | tail -1
133 passed, 2 warnings in 42.52s
```

```
$ ruff check .
All checks passed!
```

```
$ .venv/bin/python scripts/check_no_internal_refs.py
check_no_internal_refs: CLEAN — no forbidden tokens found.
```

### Metrics delta

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| Test count | 130 | 133 | +3 |
| README Tests badge | 110 (stale) | 133 (correct) | ✓ fixed |
| README lookahead limitation | contradicted code | matches Gate 0.5 | ✓ fixed |
| ADOPTION §3.5 vs §8.4 | contradicted | consistent | ✓ fixed |
| `--horizons abc` | traceback | clean error + hint | ✓ |
| Unknown-factor error | repr-quoted | plain message | ✓ |
| alphalens integration | recipe text only | committed runnable script, INTEGRATION_OK | ✓ |
| check_no_internal_refs | FAIL (6 hits) | CLEAN | ✓ |
| mom_20 / noise_control / lookahead_control verdicts | PROMOTE / REJECT / REJECT | unchanged | no regression |
| Ruff check | clean | clean | no change |

## Improve pass 1 (cycle 2) — 2026-10-12 — c2-p08-improve-1

Baseline quoted exactly as mandated: cycle 1 mutation gate killed 878/1977 mutants = 44.4%
(authoritative: reports/mutation-c1.json). Gate: 70%.

### Finding addressed

**F-T3 (minor — highest-severity open finding)** from `docs/ADVERSARIAL_REVIEW.md`
(independent pass-1 review, c2-p06/p07):

> `test_purge_no_label_overlap` docstring claims it detects "purge step missing or
> label_horizon not applied", but injecting exactly that fault leaves the whole suite
> green: with `embargo_days >= label_horizon` the embargo independently enforces
> `label_end < first_test_date`, so the test cannot distinguish "purge broken" from
> "purge working".

Reproduced before fixing (fault: `purge_cutoff = first_test_date - Timedelta(days=0)`):

```
$ .venv/bin/pytest tests/test_cv.py -q   # under injected purge-zeroed fault
tests/test_cv.py:126: AssertionError
=========================== short test summary info ============================
FAILED tests/test_cv.py::test_purge_count_matches_label_geometry - AssertionE...
```

Note: under the fault, ONLY the new test fails — confirming it isolates the purge
step while the old joint-property test stays green (the masking F-T3 describes).

### Fix implemented

- `tests/test_cv.py::test_purge_count_matches_label_geometry` (new): asserts
  `spl.n_purged` equals an independently recomputed count of raw training dates
  whose label window `[t, t+label_horizon]` reaches the first test date, derived
  from the date index without touching the splitter's purge code path. Also guards
  `expected_purged > 0` so the fixture cannot silently lose discriminating power.
- `tests/test_cv.py::test_purge_no_label_overlap` docstring corrected: now states it
  verifies the joint purge+embargo property and points to the new test for the
  purge-only check. Top-of-file fault list updated for both tests.
- Drive-by wording fixes for the other two open minors (one line each, no behaviour
  change): F-T2 (`tests/test_significance.py::test_bh_fdr_hand_computed` docstring now
  attributes the `<=`-boundary fault to `test_bh_fdr_exact_boundary`); F-L1
  (`docs/RESEARCH.md` §2.4 DSR DOI now reads "enters a redirect loop (curl: maximum
  50 redirects followed)" instead of "returns HTTP 302 redirect to publisher page").

### Before / after (raw output)

```
# before (eval-c2-p7 baseline): 129 passed
# after:
$ .venv/bin/pytest --tb=short 2>&1 | grep -E "passed|failed" | tail -3
130 passed, 2 warnings in 44.88s
```

```
$ ruff check .
All checks passed!
```

Note: `ruff format --check .` flags 9 files, identically before and after this pass
(verified via `git stash`); pre-existing formatter-version drift, out of scope.

### Metrics delta

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| Test count | 129 | 130 | +1 |
| F-T3 status | open | fixed (new killing test + corrected attribution) | ✓ |
| F-T2 status | open | fixed (docstring attribution) | ✓ |
| F-L1 status | open | fixed (wording) | ✓ |
| Purge-zeroed fault detection | suite green (fault masked) | new test FAILS, rest green | ✓ |
| mom_20 / noise_control / lookahead_control verdicts | PROMOTE / REJECT / REJECT | unchanged | no regression |
| Ruff check | clean | clean | no change |
