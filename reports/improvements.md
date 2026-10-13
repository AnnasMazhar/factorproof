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

## Improve pass 1 (cycle 3) — 2026-10-13 — c3-p08-improve-1

Baseline quoted exactly as mandated: cycle 2 mutation gate produced no score
(authoritative: reports/mutation-c2.json — `rc: 2`, `total: 0`,
`Error: No such option '--max-children'`; survivors file
reports/mutants-survived-c2.txt is empty). Gate: 70%. The c1 score
878/1977 = 44.4% (reports/mutation-c1.json) remains the last valid measurement.

### Finding addressed (top severity: red suite beats open minors)

The committed eval artifacts reports/eval-c3-p6.json / reports/eval-c3-p7.json
both claim `137 passed, 0 failures`. The tree at this pass's base does NOT
reproduce that: the full suite fails on a hypothesis-found case, reliably
(twice in a row, plus a 5000-example probe that found 7 more of the same
class). The eval green was a hypothesis seed draw, not proof of green. A red
suite outranks every open minor (F-A4, F-T5, F-S1 — all minor, all left for
c3-p09), because no commit is verifiable until the repo is green.

Before (baseline, verbatim):

```
$ .venv/bin/python -m pytest -p no:warnings 2>&1 | tail -2
FAILED tests/test_properties.py::test_pearson_corr_self_correlation - Asserti...
1 failed, 136 passed in 57.62s
```

```
$ .venv/bin/python -m pytest -p no:warnings tests/test_properties.py::test_pearson_corr_self_correlation 2>&1 | tail -8
>       assert abs(r - 1.0) < 1e-9, f"corr(x,x)={r:.6f} should be 1.0 for std={std_x:.2e}"
E       AssertionError: corr(x,x)=nan should be 1.0 for std=1.42e-14
E       assert nan < 1e-09
E        +  where nan = abs((nan - 1.0))
E       Falsifying example: test_pearson_corr_self_correlation(
E           data=[85.80595667847635, 85.80595667847635, 85.80595667847635],
E       )
```

### Root cause (implementation correct, test excuse miscalibrated)

Probed directly (verbatim):

```
$ .venv/bin/python3 -c "
import numpy as np
from factorlab.evaluate import _pearson_corr
x = np.array([85.80595667847635]*3)
print('all ties:', bool(np.all(x == x[0])))
print('np.std :', float(np.std(x)))
print('corr   :', _pearson_corr(x, x.copy()))
"
all ties: True
np.std : 1.4210854715202004e-14
corr   : nan
```

The input is EXACTLY constant (three identical bit patterns). NaN is the
contract-correct answer for constant input — pinned by
tests/test_evaluate.py::test_pearson_corr_constant (constant y -> NaN).
But np.std of exact ties reports rounding residue up to ~eps*|x|
(1.42e-14 at |x| ~= 85.8; exactly 0.0 at |x| = 5.0), so the test's
degeneracy excuse (`std < 1e-80`) does not fire at large magnitude while
the implementation rightly returns NaN. The test docstring even misstated
its own bar ("std < 1e-100" vs code `1e-80`). This is a test-calibration
bug, not an implementation bug: "fixing" the implementation to return 1.0
here would sanctify rounding noise as perfect correlation (fail-open: a
constant factor would get IC=+-1.0 instead of NaN).

### Fix implemented (tests/test_properties.py only, no src change)

- `test_pearson_corr_self_correlation`: exact ties are now detected with
  `np.all(x == x[0])` and asserted NaN (the required answer); the `std <
  1e-80` excuse is kept for the subnormal regime. Docstring rewritten to
  state the residue mechanism. Strength on non-constant data unchanged.
- New `test_pearson_corr_self_correlation_exact_ties`: deterministic
  regression test pinning the hypothesis-found triple
  ([85.80595667847635]*3, std residue 1.42e-14 > 1e-80 so it defeats the
  old excuse), asserting NaN.
- Top-of-file fault list updated for the new test (quality-contract rule).

### Fault-injection proof (faults were injected into a scratch copy of
src/factorlab/evaluate.py, suite run, then reverted with
`git checkout --`; `git status --short src/` clean after each)

Fail-open fault (`return float("nan")` -> `return 1.0`):

```
FAILED tests/test_properties.py::test_pearson_corr_self_correlation_exact_ties
FAILED tests/test_evaluate.py::test_pearson_corr_constant - AssertionError: E...
```

Attenuation fault (`... / denom` -> `... / denom * 0.5`, i.e. the property
test's named fault — proves the retouched property test is not weakened):

```
FAILED tests/test_properties.py::test_pearson_corr_self_correlation - Asserti...
FAILED tests/test_evaluate.py::test_pearson_corr_known_values - AssertionErro...
```

### Drive-by: F1 checker red on evaluator artifacts (same class as F-G1)

`scripts/check_no_internal_refs.py` FAILED on 6 hits — absolute host-path
prefixes in the untracked evaluator artifacts reports/eval-c3-p6.json /
reports/eval-c3-p7.json (pytest warning tracebacks), the same shape c2-p09
fixed for the c2 files. Mechanically scrubbed the repo prefix to `repo/`
(3 replacements per file, both re-validated as JSON); checker now CLEAN.
Same redaction convention as the c2-p09 precedent.

### After (raw output)

```
$ .venv/bin/python -m pytest -p no:warnings 2>&1 | tail -1
138 passed in 51.14s
```

(seed 999 re-run: 138 dots, exit 0. Property-test multi-seed check:
`--hypothesis-seed=0` and `--hypothesis-seed=12345` green.)

```
$ ruff check .
All checks passed!
```

(`ruff format --check .` flags 9 files, identically at HEAD before this
pass — verified the HEAD copy of tests/test_properties.py is already
flagged, and the reformat diff hunks are all pre-existing lines, none in
this pass's edited regions. Pre-existing formatter-version drift, out of
scope per the c2-p08/c2-p09 rulings.)

```
$ .venv/bin/python scripts/check_no_internal_refs.py 2>&1 | tail -1
check_no_internal_refs: CLEAN — no forbidden tokens found.
```

```
$ .venv/bin/python scripts/check_real_data_proof.py 2>&1 | tail -3
check_real_data_proof: all checks passed.
... (checker prints its own completion line; v0.2 mandate surface intact)
```

### Metrics delta

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| Test count | 137 (1 failing: self_correlation) | 138 | +1, suite green |
| test_pearson_corr_self_correlation | FAIL (exact-tie residue) | PASS (exact-tie excuse) | fixed |
| New regression test (exact ties -> NaN) | absent | present, kills fail-open fault | ✓ |
| Named-fault detection (attenuation) | detected | still detected (no weakening) | ✓ |
| mom_20 / noise_control / lookahead_control verdicts | PROMOTE / REJECT / REJECT | unchanged | no regression |
| check_no_internal_refs | FAIL (6 hits, eval-c3 JSONs) | CLEAN | ✓ drive-by |
| check_real_data_proof | pass | pass | no regression |
| Ruff check | clean | clean | no change |
| Open minors F-A4 / F-T5 / F-S1 | open | open (sequenced for c3-p09) | not this pass |

### Notes for the next pass (c3-p09-improve-2)

- F-A4 (`wilson_lower`: `math domain error` on k<0/k>n, silent 0.0 on
  negative n) is the recommended next target: explicit ValueError guards
  plus fault-named tests; no production caller passes invalid k/n
  (evaluate.hit_rate_metrics inlines its own formula and guards n==0),
  and tests/test_significance.py::test_wilson_lower_zero_obs pins n=0 ->
  0.0, so the n==0 boundary must be preserved.
- Observed while here, deliberately out of scope: `_pearson_corr` with a
  single shared rescale returns NaN for valid wildly-different-magnitude
  inputs (e.g. x~1e200 vs y~1e-200, true corr 1.0). No test covers it, no
  evaluation found it; changing rescale geometry risks the pinned
  1e-79 behaviour. Left for a dedicated pass with its own KAT.
- Branch note: this worktree is detached at 1c79970 (feat/v0.1 is checked
  out in a sibling reconcile worktree and is ahead). Commit below is on
  detached HEAD; orchestrator to cherry-pick or merge onto feat/v0.1.
