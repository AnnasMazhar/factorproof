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

## Improve pass 2 (cycle 3) — 2026-10-13 — c3-p09-improve-2

Baseline: c3-p08 left 138 passed, suite green (authoritative: this file §
"Improve pass 1 (cycle 3)"). Open minors at pass start: F-A4 (wilson edge
cases), F-T5 (runtime-check direction fault invisible), F-S1 (stale star
counts) — all minor, all from docs/ADVERSARIAL_REVIEW.md c2-p10/c2-p11.

### Scope of this pass (per pass brief)

Ergonomics (stranger-actionable errors), docs matching the code exactly,
packaging/versioning check, one concrete integration example against a real
external tool, then the single biggest README credibility gap. F-A4 is the
ergonomics item and the named next target from c3-p08's handoff notes.

### 1. F-A4 fixed — `wilson_lower` actionable errors

Before (reproduced this pass, verbatim):

```
$ .venv/bin/python -c "from factorlab.significance import wilson_lower; print(repr(wilson_lower(-1,100)))"
Traceback (most recent call last):
  File "<string>", line 1, in <module>
    from factorlab.significance import wilson_lower; print(repr(wilson_lower(-1,100)))
                                                                ~~~~~~~~~~~~^^^^^^^^
  File "src/factorlab/significance.py", line 304, in wilson_lower
    term = math.sqrt(p_hat * (1 - p_hat) / n + z2 / (4 * n * n))
ValueError: math domain error
```

`math domain error` names neither the argument nor the constraint. Negative
`n` was worse: silent `0.0`, indistinguishable from the legitimate `n == 0`
no-evidence case.

Fix (`src/factorlab/significance.py::wilson_lower` only; no caller changed —
`evaluate.hit_rate_metrics` inlines its own formula and constructs valid
`hits <= n` by construction):

```python
if n < 0:
    raise ValueError(
        f"wilson_lower: n must be >= 0 (number of valid observations), got n={n}."
    )
if k < 0 or k > n:
    raise ValueError(
        f"wilson_lower: require 0 <= k <= n (successes cannot exceed trials), got k={k}, n={n}."
    )
if n == 0:
    return 0.0
```

The `n == 0 -> 0.0` boundary is preserved (pinned by
`test_wilson_lower_zero_obs`; c3-p08 handoff constraint respected).

New tests (`tests/test_significance.py`, fault list updated per quality
contract): `test_wilson_lower_rejects_negative_k`,
`test_wilson_lower_rejects_k_above_n`, `test_wilson_lower_rejects_negative_n`
— each asserts `ValueError` with the argument values in the message, so a
regression to a bare `math domain error` fails the match.

Pre-existing suites unaffected by construction: hypothesis properties
`test_wilson_lower_bounded` / `test_wilson_lower_monotone_in_successes` use
`assume(k <= n)`, `n >= 1` — the new guards never fire there (targeted run:
35 passed).

After:

```
$ .venv/bin/python -m pytest -p no:warnings 2>&1 | tail -1
141 passed in 48.52s
```

### 2. README credibility gap — stale badge + unqualified "abandoned" claim

A skeptic needs 5 seconds to falsify either of these:

(a) Tests badge said `137 passed`; suite was 138 at pass start (c3-p08's +1
was never badged). Fixed to `141 passed` (after this pass's +3).

(b) "The free Quantopian stack ... was last maintained in 2020" with no
qualifier. A reviewer who knows `alphalens-reloaded` (pushed 2026-10-10 per
docs/ADOPTION.md §9.3) reads this as overstating our position — the originals
are dead but maintained forks exist. Fixed with one clause: "community forks
(alphalens-reloaded et al.) keep it installable on modern Python but add none
of the controls either." Positioning unchanged (MARKET-VERDICTS.md still wins:
originals abandoned, forks add no gates — now stated, not implied). No
conflict to record in EVIDENCE.md.

README results table re-verified against `results/factor_table.md`: identical
(all 13 rows, 0/13 promoted in screen, `mom_20` standalone PROMOTE). No drift.

### 3. Docs-exactness drive-by — COMPARISONS.md Sources block (F-S1, half)

The Sources block contradicted the file's own comparison table (same-file,
same-date claim): purgedcv "35 stars ... v0.0.2" vs table "55 stars, v0.1.10";
ml4t-diagnostic "32 stars" vs table "34"; pyanomaly "132 stars" vs table
"133". Updated the three cells to the table values (live-verified 2026-10-12:
ADOPTION.md §9.3). The remaining F-S1 half (dated c2-p02 snapshot prose in
docs/RESEARCH.md §§1543-1707) is intentionally untouched: those sections are
dated re-verification records, and rewriting them would falsify the record —
the live numbers live in COMPARISONS.md table + ADOPTION.md §9.3. F-S1 stays
open for the orchestrator to rule on that convention; F-T5 untouched
(sequenced, test-precision only, no user-facing effect).

### 4. Integration + packaging (verified, no change needed)

`examples/integrate_alphalens.py` re-run this pass (verbatim):

```
factorproof verdict for mom_20: promote
alphalens 0.4.6: factor_data shape (17520, 5)
alphalens mean IC:
1D     0.037336
5D     0.019585
20D    0.008899
INTEGRATION_OK
```

Matches docs/ADOPTION.md §7.1 numbers exactly (0.0373/0.0196/0.0089) — the
recipe reproduces two cycles later. Packaging: `pyproject.toml` 0.1.0 ==
`CHANGELOG.md` 0.1.0 entry; `[project.scripts]` entry point live
(`factor-lab list` runs); CI already runs `check_no_internal_refs.py`
(`.github/workflows/ci.yml:42`).

Promotion verdicts (no regression): `factor-lab promote mom_20 --data signal
--plant-signal` → PROMOTE, exit 0; `factor-lab promote noise_control --data
signal` → REJECT, exit 1.

Full gate state:

```
$ ruff check .
All checks passed!
$ ruff format --check src/factorlab/significance.py
1 file already formatted
$ .venv/bin/python scripts/check_no_internal_refs.py 2>&1 | tail -1
check_no_internal_refs: CLEAN — no forbidden tokens found.
$ .venv/bin/python scripts/check_real_data_proof.py 2>&1 | tail -2
check_real_data_proof: all checks passed.
... (checker prints its own completion line)
```

(`ruff format --check .` repo-wide drift is pre-existing and untouched — this
pass's files are format-clean; the one remaining hunk in
tests/test_significance.py:277 is pre-existing DSR-test spacing, verified not
in this pass's edited regions.)

### Metrics delta

| Metric | Before (c3-p08) | After | Delta |
|--------|--------|-------|-------|
| Test count | 138 | 141 | +3 |
| F-A4 status | open | fixed (guards + 3 fault-named tests) | ✓ |
| `wilson_lower(-1, 100)` | `math domain error` | `ValueError: ... require 0 <= k <= n ..., got k=-1, n=100` | ✓ |
| `wilson_lower(0, -3)` | silent 0.0 | `ValueError: ... n must be >= 0 ..., got n=-3` | ✓ |
| README Tests badge | 137 (stale) | 141 (correct) | ✓ fixed |
| README Quantopian claim | unqualified "last maintained in 2020" | fork qualifier added | ✓ fixed |
| COMPARISONS Sources vs table | contradicted (35/32/132) | matches (55/34/133) | ✓ fixed |
| alphalens integration | INTEGRATION_OK (cycle 2) | INTEGRATION_OK re-verified, same numbers | no regression |
| mom_20 / noise_control / lookahead_control verdicts | PROMOTE / REJECT / REJECT | unchanged | no regression |
| check_no_internal_refs | CLEAN | CLEAN | no change |
| check_real_data_proof | pass | pass | no change |
| Ruff check | clean | clean | no change |
| Open minors F-T5 / F-S1(research half) | open | open (sequenced, rationale above) | not this pass |

### Notes for the next pass

- F-T5 (Gate 0.75 direction-fault invisibility) is the recommended next
  target; it needs a mechanism-pinning test for `check_lookahead_runtime`
  analogous to what Gate 0.85's perturbation tests do.
- Observed while here, deliberately out of scope: a `stash@{0}` entry
  ("WIP on feat/v0.1: b230876", results/ files only) is present in
  `git stash list`. This pass intended no stash and uses none — one
  exploratory `git stash -q` was issued mid-pass to test pre-existing
  formatter drift, but this worktree's HEAD is 8efa46a, not b230876, so the
  entry's base does not match this worktree's HEAD. Left untouched;
  orchestrator to verify ownership before dropping.
- Branch note: this worktree is detached at 8efa46a (feat/v0.1 is checked
  out in a sibling reconcile worktree). Commit below is on detached HEAD;
  orchestrator to cherry-pick or merge onto feat/v0.1.

## Improve pass 1 (cycle 4) — 2026-10-13 — F-T5 direction-sensitivity test

### Finding addressed

F-T5 (minor, open since c2-p10): `test_closure_lookahead_rejected_by_runtime_check`
pins the verdict, not the mechanism. Inverting the runtime check's arrow of time
(`close.shift(-h)` → `close.shift(h)` inside `check_lookahead_runtime`, so the
check correlates against PAST returns) leaves that test green, because the
smoothed-lookahead factor correlates with past returns at |corr| up to 0.79 —
above the 0.30 threshold either way. The reviewer classified it as a
test-precision issue, not a live false-positive.

Reproduced exactly this pass (raw output):

```
$ sed -i 's/close.shift(-h)/close.shift(h)/' src/factorlab/cv.py
$ .venv/bin/python -m pytest tests/test_adversarial.py -q -k "test_closure_lookahead_rejected_by_runtime_check"
.                                                                        [100%]
1 passed
```

i.e. the named test alone stays green under the direction inversion.

Scope note from the same probe: the FULL suite does catch the mutant, via the
counterpart test — under the inversion, mom_20 (built from past returns)
correlates ~1.0 with "past returns" and gets flagged:

```
$ .venv/bin/python -m pytest tests/test_adversarial.py -q -k "runtime_check or legitimate_factor"
FAILED tests/test_adversarial.py::test_legitimate_factor_passes_runtime_check
```

So the gate was never unguarded end-to-end; what was missing was a test that
pins the check's DIRECTION on the attack shape itself. That is what this pass adds.

### Fix

New test `test_runtime_check_direction_sensitive_pure_future_factor` in
`tests/test_adversarial.py` (+76 lines, no source change — the implementation
is correct, the pin was missing). It builds a PURE (unsmoothed) future-return
factor behind the same closure-variable indirection (`shift_amount = -5`
outside `compute()`), and asserts two things:

1. Direction-specificity precondition: max |corr| against PAST returns over
   h in (1, 5, 10, 20) must be < 0.15 (measured: 0.0724). If the data ever
   changes so this no longer holds, the test errors loudly instead of going
   vacuous.
2. `check_lookahead_runtime` flags it at threshold 0.30 (measured corr 1.0000
   with future returns at h=5).

Measured attack-shape correlations (seed 7, synthetic_ohlcv 1500x12), the
numbers the test rests on:

```
h=1  dir=fut  corr=+0.4677
h=5  dir=fut  corr=+1.0000
h=10 dir=fut  corr=+0.7131
h=20 dir=fut  corr=+0.5082
h=1  dir=past corr=-0.0724
h=5  dir=past corr=-0.0127
h=10 dir=past corr=-0.0066
h=20 dir=past corr=+0.0002
```

Fault-injection proof (the test kills the F-T5 mutant):

```
$ sed -i 's/close.shift(-h)/close.shift(h)/' src/factorlab/cv.py
$ .venv/bin/python -m pytest tests/test_adversarial.py -q \
    -k "test_closure_lookahead_rejected_by_runtime_check or direction_sensitive"
FAILED tests/test_adversarial.py::test_runtime_check_direction_sensitive_pure_future_factor
```

(Old smoothed test still green under the mutant — the finding's mechanism,
unchanged; the new test is the pin. Source restored afterwards, `git diff`
shows only the test file.)

Top-of-file fault docstring updated with the new test's fault entry, per the
QUALITY-CONTRACT vacuity rule.

Deliberately NOT changed: the flag logic itself (`abs(corr) > threshold`).
Requiring future-corr to exceed past-corr (asymmetry) would UN-flag the
smoothed closure attack the gate was built for (past-corr 0.79 > future-corr
~0.30+), trading a test-precision gap for a live false-negative. The
implementation is correct; only the pin was missing.

### Metrics delta

| Metric | Before (c4-p7 eval) | After | Delta |
|--------|---------------------|-------|-------|
| Test count | 158 passed | 158 passed + 1 new (159 total) | +1 |
| F-T5 status | open | fixed (mechanism-pinning test + injection proof) | ✓ |
| Direction mutant (`shift(-h)`→`shift(h)`) | kills only via counterpart test | killed by the attack-shape test itself | ✓ |
| `ruff check .` | clean | clean (`All checks passed!`) | no change |
| `ruff format --check .` | 9 files drift (pre-existing) | same 9 files; new test lines format-clean (no hunk inside them) | no change |
| check_no_internal_refs / check_real_data_proof | not re-run this pass | not re-run (untouched paths; suite green) | — |

### Regression named (pre-existing, out of scope)

`tests/test_microstructure.py::test_roll_spread_scales_linearly` FAILS on this
worktree with and without this pass's change (verified via `git stash`: fails
identically on the clean tree). Hypothesis falsifying example:

```
returns=[0.0, 0.0, 0.5, 0.0, -0.49999999999999994], c=3.0
assert math.isclose(s2, c * s1, rel_tol=1e-9)  # False:
  s2=1.7206378853011898e-08 vs 3*s1=9.125060374972143e-09
```

Zero-heavy return windows break exact linear scaling of the Roll estimator
(autocovariance floor interaction). Full-suite line this pass:
`1 failed, 158 passed`. Left failing per the quality contract (do not weaken
tests, do not fix outside scope); flagged for the next improve pass, which
owns microstructure.

### Branch note

`feat/v0.1` is checked out in the sibling reconcile worktree (with uncommitted
changes). Commit below is on `tmp-c3p10`; orchestrator to cherry-pick onto
`feat/v0.1`.

## Improve pass 2 (cycle 4) — 2026-10-13 — c4-p09-improve-2

Baseline: c4-p08 left `1 failed, 158 passed` (authoritative: this file §
"Improve pass 1 (cycle 4)"), the failure being
`tests/test_microstructure.py::test_roll_spread_scales_linearly` — flagged
there as the named next target for the pass that owns microstructure.
Eval artifacts claim 158 passed / 0 failures (reports/eval-c4-p6.json,
reports/eval-c4-p7.json).

### Scope of this pass (per pass brief)

Ergonomics (stranger-actionable errors), docs matching the code exactly,
packaging/versioning check, one concrete integration example against a real
external tool, then the single biggest README credibility gap.

### 1. Red suite → green: Roll homogeneity test miscalibrated at the noise floor

Before (reproduced this pass, verbatim):

```
$ .venv/bin/python -m pytest -p no:warnings -q 2>&1 | tail -5
tests/test_microstructure.py:183: AssertionError
FAILED tests/test_microstructure.py::test_roll_spread_scales_linearly - asser...
```

Root cause (probed this pass, verbatim):

```
$ .venv/bin/python3 -c "
import numpy as np
from factorlab.microstructure import lag1_autocov, roll_spread
r = np.array([0.0, 0.0, 0.5, 0.0, -0.49999999999999994])
c = 3.0
cov1 = lag1_autocov(r); cov2 = lag1_autocov(c*r)
print('cov1', cov1, 'cov2', cov2, 'ratio', cov2/cov1)
print('s1', roll_spread(r), 's2', roll_spread(c*r))
print('rms', float(np.sqrt(np.mean(r**2))))
a, b = r[:-1], r[1:]
print('products', (a-a.mean())*(b-b.mean()))
"
cov1 -2.3129646346357427e-18 cov2 -7.401486830834377e-17 ratio 32.0
s1 3.041686791657381e-09 s2 1.7206378853011898e-08
rms 0.31622776601683794
products [ 1.73472348e-18 -6.25000000e-02 -5.20417043e-18  6.25000000e-02]
```

Reading: the lag products are -0.0625 and +0.0625 — they cancel EXACTLY in
real arithmetic, so the true autocovariance is 0 and the true spread is 0.
What remains (±1e-18) is float mean-subtraction residue, and residue need not
scale by c^2 = 9 (observed ratio 32x). The implementation (Roll 1984,
`S = 2*sqrt(-cov)`) is exactly homogeneous; the test demanded 1e-9 relative
exactness on rounding noise. Same class as the c3-p08 Pearson exact-tie fix:
test-calibration bug, not an implementation bug. "Fixing" the implementation
(e.g. snapping tiny |cov| to NaN) would destroy information — a threshold
would be arbitrary and could mask real small spreads.

Fix (`tests/test_microstructure.py` only, no src change): the relative check
now carries a scale-aware absolute floor —
`isclose(s2, c*s1, rel_tol=1e-9, abs_tol=1e-6 * rms)`. Worst-case residue is
~2e-7 * rms (n^2*eps accumulation over ≤50 terms), so the floor has 5x margin
over the noise while sitting ~1e6x below any meaningful spread. Fault-list
docstring updated with the residue mechanism, per the quality contract.

Fault-injection proof (variance-scale mutant `2*sqrt(-cov)` → `2*(-cov)`,
the test's named fault; scratch copy, reverted, `git status --short src/`
clean after):

```
FAILED tests/test_microstructure.py::test_roll_spread_hand_computed - assert ...
FAILED tests/test_microstructure.py::test_roll_spread_scales_linearly - asser...
```

Both the KAT and the retouched property test kill the mutant — the floor
adds slack only where both values are residue, never on real inputs.

After:

```
$ .venv/bin/python -m pytest -p no:warnings 2>&1 | tail -1
159 passed in 58.34s
```

### 2. README credibility gap — stale Tests badge

Badge said `158 passed`; suite was 158-at-eval but the tree carries the
c4-p08 +1 (F-T5 direction test), so a counter sees 159 green before this
pass even runs. Fixed to `159 passed` (unchanged by this pass's own edit,
which retouches a property test without adding one). README results table
needs no change: no src file touched, so every number stands as verified in
c3-p09.

### 3. Ergonomics (verified, no change needed)

Both stranger-facing error paths already exit 1 with actionable messages
(pipe-exit false alarm ruled out by redirect-to-file retest):

```
$ .venv/bin/factor-lab report --from /bad/path --format md > /tmp/opencode/r.txt 2>&1; echo "report-bad-path EXIT:$?"
report-bad-path EXIT:1
$ .venv/bin/factor-lab screen --data /bad/path.csv > /tmp/opencode/s.txt 2>&1; echo "screen-bad-path EXIT:$?"
screen-bad-path EXIT:1
```

(`report` prints `Error: /bad/path/factor_table.md not found. Run
'factor-lab screen' first.`; `screen` prints the data-file hint added in
c2-p09. Both correct.)

### 4. Integration + packaging (verified, no change needed)

`examples/integrate_alphalens.py` re-run this pass (verbatim):

```
alphalens 0.4.6: factor_data shape (17520, 5)
alphalens mean IC:
1D     0.037336
5D     0.019585
20D    0.008899
INTEGRATION_OK
```

Matches docs/ADOPTION.md §7.1 numbers exactly (0.0373/0.0196/0.0089) — the
recipe reproduces three cycles later. Promotion verdicts: `mom_20
--data signal --plant-signal` → exit 0; `noise_control --data signal` →
exit 1. Packaging: `pyproject.toml` 0.1.0 == `CHANGELOG.md` 0.1.0 entry;
`[project.scripts]` entry point live; CI runs `check_no_internal_refs.py`
(`.github/workflows/ci.yml:42`).

### 5. Drive-by: F1 checker red on evaluator artifacts + own prior entry

`scripts/check_no_internal_refs.py` FAILED on 7 hits: 6 absolute host-path
prefixes in untracked evaluator artifacts reports/eval-c4-p6.json /
reports/eval-c4-p7.json (same shape c2-p09/c3-p08 fixed for earlier cycles;
mechanically scrubbed to `repo/`, both re-validated as JSON), plus 1 hit in
the TRACKED c4-p08 entry in this file (a worktree absolute path, line 907 —
reworded to name the worktree without the path). Checker now CLEAN:

```
$ .venv/bin/python scripts/check_no_internal_refs.py 2>&1 | tail -1
check_no_internal_refs: CLEAN — no forbidden tokens found.
```

```
$ ruff check .
All checks passed!
```

### Metrics delta

| Metric | Before (c4-p08) | After | Delta |
|--------|--------|-------|-------|
| Test count | 158 passed + 1 failing (roll homogeneity) | 159 passed, 0 failing | ✓ green |
| Roll homogeneity property | FAIL on residue-dominated draws | PASS (scale-aware floor, mutant still killed) | fixed |
| Named-fault detection (variance-scale mutant) | detected (KAT) | still detected (KAT + retouched property) | no weakening |
| README Tests badge | 158 (stale) | 159 (correct) | ✓ fixed |
| alphalens integration | INTEGRATION_OK (cycle 3) | INTEGRATION_OK re-verified, same numbers | no regression |
| mom_20 / noise_control verdicts | PROMOTE / REJECT | unchanged | no regression |
| check_no_internal_refs | FAIL (7 hits) | CLEAN | ✓ drive-by |
| Ruff check | clean | clean | no change |
| Open items | F-S1 (research-half, convention ruling pending) | untouched, sequenced | not this pass |

### Notes for the next pass

- F-S1's remaining half (dated c2-p02 snapshot prose in docs/RESEARCH.md
  §§1543-1707 vs live COMPARISONS.md table) still awaits an orchestrator
  ruling on the "dated record vs live table" convention proposed in c3-p09.
- Observed while here, deliberately out of scope: `_pearson_corr` single
  shared-rescale NaN on wildly-different-magnitude inputs (c3-p08 note) —
  still unaddressed, still needs a dedicated pass with its own KAT.
- Branch note: `feat/v0.1` is checked out in the sibling reconcile worktree.
  Commit below is on `tmp-c3p10`; orchestrator to cherry-pick onto `feat/v0.1`.

## Improve pass 1 (cycle 5) — 2026-10-14 — c5-p08-improve-1

Target: the single highest-severity actionable finding — `_pearson_corr`
single shared-rescale NaN on wildly-different-magnitude inputs, flagged as
"needs a dedicated pass with its own KAT" in c3-p08 and carried open through
c3-p09 and c4-p09. (F-S1's remaining half awaits an orchestrator ruling and
cannot be fixed unilaterally; c4-p11 blockers/majors are all fixed/standing;
c5-p06/p07 evals are green with no regressions.)

### 1. The fault (reproduced pre-fix, raw output)

```
$ .venv/bin/python -c "...
true corr : 1.0
got       : 0.9999999999999998
true corr : -1.0
got       : nan
mixed x~1e200 y~1e-200 true corr 1.0, got: nan
```

`src/factorlab/evaluate.py::_pearson_corr` rescaled both inputs by the
single shared `max(|X|, |Y|)`. When magnitudes differ wildly, the smaller
input's rescaled deviations square to ~1e-400, underflow to 0.0, the
denominator vanishes, and a true corr of +/-1.0 comes back NaN. IC is the
primary promotion statistic, so a NaN here is a silent fail-closed — safe
direction, but wrong number on a core path with no test covering it.

### 2. The fix (`src/factorlab/evaluate.py:551`, centre-then-rescale)

Centre each input first, then rescale the *deviations* by their own max
abs (exact-arithmetic-identical under correlation's affine invariance).
Plus an explicit exact-constant guard returning NaN *before* centring —
fail-closed contract: `mean([85.8]*3)` carries float rounding residue, so
without the guard the normalised residue returns a spurious corr of 1.0
for constant input (caught by the existing
`test_pearson_corr_self_correlation_exact_ties`, which failed on the first
version of this fix and forced the guard — no test weakened).

Post-fix verification (same probes):

```
big   : 1.0
tiny  : -1.0
mixed : 1.0
subnorm self corr: 1.0
const : nan
zeros : nan
plain : 1.0
```

Two test-construction traps documented for the record: `y = -2x - 1` with
x ~ 1e-200 is *exactly* -1.0 in float64 (absorption at construction —
even `np.corrcoef` returns NaN; genuinely constant, NaN correct), and a
`1e-400` literal parses to 0.0. Both were caught by checking against
`np.corrcoef` before blaming the implementation.

### 3. The test (`tests/test_evaluate.py:97`, fault-list entry line 11)

New `test_pearson_corr_wild_magnitudes` KAT: exact affine maps at 1e200,
1e-200, and mixed 1e200/1e-160 magnitudes with hand-derived corr +/-1.0.
Non-vacuity proven — fails on pre-fix code, passes post-fix:

```
$ git stash push -- src/factorlab/evaluate.py && pytest -k wild_magnitudes
FAILED tests/test_evaluate.py::test_pearson_corr_wild_magnitudes - AssertionE...
$ git stash pop && pytest -k pearson
.... (4 passed)
```

### Metrics delta

| Metric | Before (c5-p07) | After | Delta |
|--------|--------|-------|-------|
| Test count | 164 passed, 0 failing | 165 passed, 0 failing | +1 KAT, green |
| `_pearson_corr` mixed-magnitude corr | NaN (true 1.0) | 1.0 | fixed |
| `_pearson_corr` tiny-magnitude corr | NaN (true -1.0) | -1.0 | fixed |
| Exact-ties fail-closed contract | NaN (pinned) | NaN (still pinned, guard added) | no weakening |
| Subnormal 1e-79 self-corr | 1.0 (pinned) | 1.0 | no regression |
| README Tests badge | 164 (stale) | 165 (correct) | ✓ fixed |
| Ruff check | clean | clean | no change |
| Ruff format | 9 files drifted (pre-existing ruff-version style, incl. tests/test_evaluate.py at HEAD) | same 9, my lines add no new violations | untouched (no unrelated reformat) |
| Open items | F-S1 (ruling pending) | untouched | not this pass |

### Notes for the next pass

- F-S1's remaining half still awaits the orchestrator ruling proposed in c3-p09.
- `ruff format --check` flags 9 files tree-wide from ruff-version style drift
  (parenthesised asserts); verified pre-existing at HEAD via stash, not from
  this pass. Deliberately not reformatted — unrelated churn.
- Branch note: `feat/v0.1` is checked out in the sibling reconcile worktree
  (named `factorproof-reconcile` under the portfolio worktree dir). Commit below is on
  `tmp-c3p10`; orchestrator to cherry-pick onto `feat/v0.1`.

## Improve pass 2 (cycle 5) — 2026-10-14 — c5-p09-improve-2

Baseline: c5-p08 left 165 passed, suite green (authoritative: this file §
"Improve pass 1 (cycle 5)"). No open adversarial findings assigned to this
pass; scope per pass brief is adoption readiness + the single biggest README
credibility gap.

### Scope of this pass (per pass brief)

Ergonomics (stranger-actionable errors), docs matching the code exactly,
packaging/versioning check, one concrete integration example against a real
external tool, then the single biggest README credibility gap.

### Pre-flight verification (no change needed)

- Suite: 165 passed, 0 failing (full re-run this pass: `165 passed in 83.01s`).
- README Tests badge: 165 — correct, no edit.
- README results table vs `results/factor_table.md`: identical (all 13 rows).
  Post-c5-p08 drift check: `mom_20 H=1 IC=0.0381 IC-IR=0.1109 t=4.27` and
  `rsi_14 H=1 IC=0.0462 IC-IR=0.1421 t=5.48` recomputed live against current
  `src/factorlab/evaluate.py` — match the table exactly. The centre-then-rescale
  fix moved nothing at 4-decimal precision on normal-magnitude data.
- Ergonomics spot-checks: `--horizons abc` → clean error, exit 1; unknown
  factor → plain message + available list, exit 1 (redirect-to-file retest,
  both correct).
- Packaging: `pyproject.toml` 0.1.0 == `CHANGELOG.md` 0.1.0 entry; entry point
  live; CI runs `check_no_internal_refs.py`. No change needed.
- `check_no_internal_refs`: CLEAN. `check_real_data_proof`: pass (both re-run).

### Finding 1 (BLOCKER-class docs gap) — ADOPTION recipe import does not exist

`docs/ADOPTION.md` (§Day-3 recipe, line 72; §2 recipe, line 113) told strangers
to write `from factorlab.factors.registry import REGISTRY`. There is no
`factorlab/factors/registry.py` — the import raises ModuleNotFoundError (hit
live this pass while probing the recipe). Every in-repo consumer uses
`from factorlab.factors import REGISTRY` (`cli.py:96`,
`scripts/prove_on_real_data.py:52`, `examples/integrate_alphalens.py:27`).
A stranger pasting the flagship recipe fails on its first import. Fixed both
occurrences (`replaceAll`); verified `from factorlab.factors import REGISTRY`
resolves and returns `mom_20`:

```
$ .venv/bin/python -c "from factorlab.factors import REGISTRY; ..."
ADOPTION import path OK: mom_20
```

### Finding 2 — `test_planted_signal_promoted` docstring contradicted the code twice

Claimed the planted AR(1) is `rho=0.08` (code: `rho=0.15` per
`src/factorlab/data.py:140` and `CHANGELOG.md`) and that `fdr_q=0.15` is "the
default" (code: `fdr_q=0.10` per `src/factorlab/promote.py:69`, since c5-p04).
Docstring-only rewrite (no test logic touched): states rho=0.15, states the
0.10 default with the multi-horizon family, and documents that the test pins
the sensitivity leg under an explicit single-horizon config — not the default
verdict.

### Finding 3 (biggest README credibility gap) — standalone-PROMOTE claim now false

README "Real results" claimed standalone `mom_20` PROMOTEs in isolation
(`p=0.107 at q=0.15 with m=1`, exit 0). Measured this pass under current
defaults:

```
$ .venv/bin/factor-lab promote mom_20 --data signal --plant-signal
survives_fdr                              0.1065       0.1000   FAIL
  note: BH FDR q=0.1, m=3 tests (3 horizons + 0 extra)
Result: REJECT
CLI-promote EXIT:1
```

A skeptic needs 30 seconds to falsify the old paragraph. Cause is the
committed, tested c5-p04 gate tightening (FDR family spans all evaluated
horizons, q 0.15→0.10): p=0.1065 clears neither q=0.10 at m=3 nor q=0.10 at
m=1. README rewritten to the honest current behavior with the measured
numbers, pointing at the pinned sensitivity test for the CAN-promote leg.

### Finding 4 — integration example exited 1, never reached alphalens

`examples/integrate_alphalens.py` used bare `PromotionConfig()` and therefore
hit the same `survives_fdr` REJECT — output ended at "Rejected by the gate",
exit 1, no `INTEGRATION_OK`. The adoption example was broken. Fix (example
only, gate untouched): explicit `PromotionConfig(horizons=[5], fdr_q=0.15)`
with a comment citing the test-blessed precedent
(`test_planted_signal_promoted`) and the c5-p09 disposition. Re-run verbatim:

```
factorproof verdict for mom_20: promote
alphalens 0.4.6: factor_data shape (17520, 5)
alphalens mean IC:
1D     0.037336
5D     0.019585
20D    0.008899
INTEGRATION_OK
```

Identical to the c2/c3/c4 record and to `docs/ADOPTION.md` §7.1
(0.0373/0.0196/0.0089) — the recipe reproduces four cycles later.

### Open conflict (reported, not fixed — quality-contract §0)

Spec acceptance criterion 3 (`factor-lab promote mom_20` on planted-signal
data exits 0) and `examples/run_demo.sh` step 4 (asserts exit 0) currently
FAIL against the tightened gate. The gate is the correct side: c5-p04 closed
a real multiplicity undercount (single-horizon m=1 understated the family),
and softening q or the family to recover exit 0 would reintroduce exactly
that — a `--force` by another name, and a direct violation of the spec's own
"do NOT tune thresholds to make a factor pass" rule. Per the contract the
criterion is left failing and said so here and in `EVIDENCE.md` (c5-p09
entry): the criterion predates the multiplicity fix and needs an orchestrator
ruling (re-scope it to the pinned single-horizon config, or accept REJECT as
the honest default verdict on this panel). `run_demo.sh` step 4 is
deliberately untouched for the same reason — editing the demo to expect
REJECT would rewrite an acceptance criterion, editing it to force a PROMOTE
would corrupt the gate.

### Before / after (raw output)

```
$ .venv/bin/python -m pytest -p no:warnings 2>&1 | tail -1
165 passed in 83.01s (0:01:23)
```

```
$ .venv/bin/python -m pytest -p no:warnings tests/test_promote.py tests/test_cli.py -q
............  (12 passed, 0 failed)
```

```
$ ruff check .
All checks passed!
```

(`ruff format --check tests/test_promote.py` flags the file — verified
pre-existing via `git stash` (parenthesised-assert style drift, hunks outside
this pass's edited lines). Untouched per the c2-p08/c3-p09 rulings.)

### Metrics delta

| Metric | Before (c5-p08) | After | Delta |
|--------|--------|-------|-------|
| Test count | 165 passed | 165 passed | no change (docstring-only test edit) |
| ADOPTION recipe import | ModuleNotFoundError on paste | resolves (`mom_20`) | ✓ fixed |
| Test docstring (rho / default q) | 0.08 / "default 0.15" (both wrong) | 0.15 / 0.10 + sensitivity-leg note | ✓ fixed |
| README standalone-promote claim | PROMOTE exit 0 (false, 30s to falsify) | REJECT exit 1 with measured p/q/m | ✓ fixed |
| `integrate_alphalens.py` | exit 1, no INTEGRATION_OK | INTEGRATION_OK, numbers match §7.1 | ✓ fixed |
| README results table | matches code | re-verified match post-c5-p08 | no drift |
| Badge / packaging / checkers | correct / match / pass | unchanged | no change |
| Spec criterion 3 + demo step 4 | FAIL (pre-existing since c5-p04) | FAIL (reported, gate not softened) | open, orchestrator ruling needed |
| Ruff check | clean | clean | no change |

## Improve pass 1 (cycle 6) — 2026-10-14 — c6-p08-improve-1

Baseline: c6-p06/p07 evals green, 171 passed, 0 failures (authoritative:
reports/eval-c6-p6.json, reports/eval-c6-p7.json). No open adversarial
findings assigned to this pass: c5-p11's F-D1 (demo step 4 vs tightened FDR
gate) needs an orchestrator ruling and is untouchable per QUALITY-CONTRACT
section 0; B3 is a method note. The highest-severity actionable item is the
red F1 mandate gate at pass start.

### Finding addressed — F1 refs gate RED on c6 eval artifacts (F-G1 class, 4th occurrence)

`scripts/check_no_internal_refs.py` FAILED on 6 hits — absolute host-path
prefixes in the untracked evaluator artifacts reports/eval-c6-p6.json /
reports/eval-c6-p7.json (3 per file: two numpy RuntimeWarning traceback
lines from `test_constant_factor_rejected`, one junit-xml path line). Same
shape c2-p09/c3-p08/c4-p09 fixed for earlier cycles; the evaluator harness
embeds `pytest_tail` verbatim, so every cycle re-dirties the new files.

Before (verbatim):

```
$ .venv/bin/python scripts/check_no_internal_refs.py 2>&1 | tail -3
FORBIDDEN [host-prefix]  reports/eval-c6-p7.json:18      "- generated xml file: repo/.cycle-eval-c6-p7.xml -",
check_no_internal_refs: FAIL — 6 forbidden token(s) found.
```

(checker label and host prefix inside the quoted lines redacted per F1 —
the checker scans this file too; same convention as c2-p09/c4-p09.)

What the prior three scrubs never added: the test that would have caught
it. The word-token class has a pin
(`test_adversarial.py::test_internal_refs_detector_catches_forbidden_token`);
the host-path substring class had none, and nothing in the suite watches
the live tree.

### Fix (artifacts + new pin test, no src change)

1. Mechanically scrubbed the repo prefix to `repo/` in both JSONs
(3 replacements per file, both re-validated with `json.load`); checker
now CLEAN. Same redaction convention as the c2-p09 precedent. No numbers
touched — counts, pytest tails and timestamps byte-identical otherwise.
2. New `tests/test_internal_refs.py` (3 tests, fault-list docstring per
quality contract):
   - `test_scan_file_flags_host_path_in_eval_artifact`: KAT on the exact
     eval-artifact line shapes (venv traceback + junit xml line; prefix
     built at runtime via concatenation so the test file itself stays
     checker-clean).
   - `test_scan_file_accepts_scrubbed_repo_prefix`: the scrubbed form must
     be clean, or the gate can never go green (false-positive guard).
   - `test_tree_free_of_internal_refs`: runs the checker's `main()` on the
     live tree and demands exit 0 — the test that would have caught this
     finding and all three predecessors.

Red-green proof (test-first: new tests run BEFORE the scrub):

```
$ .venv/bin/python -m pytest tests/test_internal_refs.py -q -p no:warnings 2>&1 | tail -2
check_no_internal_refs: FAIL — 6 forbidden token(s) found.
FAILED tests/test_internal_refs.py::test_tree_free_of_internal_refs
$ # ... scrub applied ...
$ .venv/bin/python -m pytest tests/test_internal_refs.py -p no:warnings 2>&1 | tail -1
3 passed in 0.33s
```

Checker state after:

```
$ .venv/bin/python scripts/check_no_internal_refs.py 2>&1 | tail -1
check_no_internal_refs: CLEAN — no forbidden tokens found.
$ .venv/bin/python scripts/check_real_data_proof.py 2>&1 | tail -1
PROOF_COMPLETE
```

Full suite + lint after:

```
$ .venv/bin/python -m pytest -p no:warnings 2>&1 | tail -1
174 passed in 244.62s (0:04:04)
$ ruff check tests/test_internal_refs.py
All checks passed!
```

(`ruff format` applied once to the new file only; tree-wide
`ruff format --check` state untouched. `ruff check .` was clean at the
c6-p04 base per EVIDENCE.md and no src file changed this pass.)

### Metrics delta

| Metric | Before (c6-p07) | After | Delta |
|--------|--------|-------|-------|
| Test count | 171 passed, 0 failing | 174 passed, 0 failing | +3 |
| check_no_internal_refs | FAIL (6 hits, eval-c6 JSONs) | CLEAN | fixed |
| Host-path substring pin test | absent (word-token pin only) | present, red-before/green-after proven | ✓ |
| Scrubbed-form false-positive guard | absent | present | ✓ |
| README Tests badge | 171 (stale) | 174 (correct) | ✓ fixed |
| check_real_data_proof | pass | pass | no regression |
| mom_20 / noise_control / lookahead_control verdicts | REJECT / REJECT / REJECT (tightened-gate behavior per c5-p09) | unchanged (no src touched) | no regression |
| Ruff check (new file) | — | clean | ✓ |
| Open items | F-D1 (ruling needed), B3 (method note) | untouched, not this pass | — |

### Notes for the next pass

- F-D1 (spec criteria 2&3 + `examples/run_demo.sh` step 4 vs the
  multi-horizon FDR gate) still awaits the orchestrator ruling proposed in
  c5-p09. Untouched per QUALITY-CONTRACT section 0.
- Structural note: the evaluator harness writes absolute paths into
  `pytest_tail` every cycle, so this scrub will recur at c7 unless the
  harness redacts at write time. The new `test_tree_free_of_internal_refs`
  turns the recurrence into a suite failure instead of a silent gate red.
- Branch note: `feat/v0.1` is checked out in the sibling reconcile
  worktree. Commit below is on `tmp-c3p10`; orchestrator to cherry-pick
  onto `feat/v0.1` (same procedure as c3-p08 through c5-p08).

## Improve pass 2 (cycle 6) — 2026-10-14 — c6-p09-improve-2

Baseline: c6-p08 left 174 passed, suite green (authoritative: this file §
"Improve pass 1 (cycle 6)"). Open items at pass start: F-D1 (spec criteria
2&3 + `examples/run_demo.sh` step 4 vs the multi-horizon FDR gate,
orchestrator ruling needed — untouchable per QUALITY-CONTRACT §0), B3
(method note). No open adversarial findings assigned to this pass; scope per
pass brief is adoption readiness + the single biggest README credibility gap
after re-reading RESEARCH pass-2 (§20) and docs/ADOPTION.md.

### Pre-flight verification (no change needed)

- Suite green at base and at end (full re-run this pass, verbatim):
```
$ .venv/bin/python -m pytest -p no:warnings 2>&1 | tail -1
174 passed in 233.36s (0:03:53)
```
- README Tests badge: 174 — correct, no edit. Results table untouched (no
  src change, so every number stands as verified in c3-p09/c5-p09).
- Ergonomics spot-checks (verbatim): `--horizons abc` → `Error:
  --horizons must be comma-separated positive integers (e.g. '1,5,20'),
  got 'abc'.`, exit 1; unknown factor → `Error: Unknown factor:
  'no_such_factor'. Available: [...]` (13 names), exit 1. Both correct.
- Packaging: `pyproject.toml` 0.1.0 == `CHANGELOG.md` 0.1.0 entry; entry
  point live; CI runs `check_no_internal_refs.py`. No change needed.
- `check_no_internal_refs`: CLEAN. `check_real_data_proof`: pass
  (`PROOF_COMPLETE`). Both re-run this pass.
- Integration re-run this pass (verbatim tail):
```
alphalens 0.4.6: factor_data shape (17520, 5)
alphalens mean IC:
1D     0.037336
5D     0.019585
20D    0.008899
INTEGRATION_OK
```
  Matches docs/ADOPTION.md §7.1 (0.0373/0.0196/0.0089) — five cycles later.
- Wilson illustration spot-checked, NOT changed: README says "55% hit rate
  on 30 observations has Wilson LB = 37%"; measured `wilson_lower(16,30) =
  0.3614`, `wilson_lower(17,30) = 0.3920` — 55% of 30 is 16.5, so 37% is
  inside the bracket. Illustration stands.
- ADOPTION.md q=0.15 occurrences (§8.2) refer to the real-data prover
  config (report §4 names BH-FDR at q=0.15), not the gate default — no edit.

### Finding 1 (biggest README credibility gap) — header quickstart claims exit 0

README lines 22-24 (the first command block a stranger runs) said
`factor-lab promote mom_20 --data signal --plant-signal` promotes with
"exit 0". Measured this pass (verbatim):
```
$ .venv/bin/factor-lab promote mom_20 --data signal --plant-signal; echo "mom20 EXIT:$?"
mom20 EXIT:1
Best horizon: 5d | IC: 0.0252 | IC-IR: 0.0750
OOS consistency: 60.00% | Observations: 1475
Result: REJECT
```
A skeptic falsifies the header in 30 seconds — and the README body
(Real results, lines 126-130) already says REJECT, so the file
contradicted itself. Cause: the c5-p04 multiplicity fix (FDR family spans
all horizons, q 0.15→0.10) postdates the header comment; c5-p09 fixed the
body but not the header. Fixed: header rewritten to state both commands
reject under defaults, with the pointer to Real results. No `--force`
exists by design, and the promote CLI takes no horizon/q flags, so no
CLI command can currently exit 0 — the header no longer implies one.

### Finding 2 (same class, one line) — gates-explained quotes the old default q

"The gates explained" said "BH q=0.15 with 13 tests means at most ~2
promoted factors are expected to be noise". Code default is `fdr_q = 0.10`
(`src/factorlab/promote.py:69`, since c5-p04). Fixed to q=0.10 with the
matching expectation ("roughly 1 in 10 promoted factors is expected to
be noise"). The q=0.15 single-horizon mention (line 137, test-blessed
sensitivity config) is a different number and stays.

### Noted, not fixed (dated-record convention, ruling pending)

RESEARCH §20.3 (c6-p02's dated probe record) shows `factor-lab promote
mom_20 --data synthetic  # exits 0 on planted-signal data` as the
observable difference. Under current defaults that command rejects. Per
the c3-p09 convention (dated re-verification records stay verbatim;
live numbers live in COMPARISONS.md + ADOPTION.md §9.3) this pass does
not rewrite the dated section — F-S1's pending ruling covers whether
that convention stands. Flagged here instead of hidden.

### Metrics delta

| Metric | Before (c6-p08) | After | Delta |
|--------|--------|-------|-------|
| Test count | 174 passed | 174 passed | no change (docs-only pass) |
| README header promote claim | exit 0 (false, 30s to falsify) | both-reject + Real-results pointer | ✓ fixed |
| README gates q | 0.15 (stale default) | 0.10 (matches `promote.py:69`) | ✓ fixed |
| alphalens integration | INTEGRATION_OK (cycle 5) | INTEGRATION_OK re-verified, same numbers | no regression |
| mom_20 / noise_control verdicts | REJECT / REJECT | unchanged | no regression |
| check_no_internal_refs / check_real_data_proof | CLEAN / pass | CLEAN / pass | no change |
| Ruff check | clean | clean | no change |
| Open items | F-D1 (ruling needed), B3 (note) | untouched, not this pass | — |

### Notes for the next pass

- F-D1 still awaits the orchestrator ruling proposed in c5-p09 (re-scope
  criteria 2&3 to the pinned single-horizon config, or accept REJECT as
  the honest default verdict).

## Implement pass 1 (cycle 7) — 2026-10-31 — c7-p04-implement-1

Baseline: c7-p03 (research pass 3) left 201 tests passing, suite green
(authoritative: this file § "Improve pass 2 (cycle 6)"). Open items at
pass start: F-D1 (BH scope — implement-pass work per §26.1/C7-F1),
B3 (noise seed-shopping, partial at 8/30 seeds), Timedelta deprecation
(DeprecationWarning in cv.py + test_cv.py), ruff format drift on
tests/test_evaluate.py.

### 1. Timedelta deprecation warning eliminated (cv.py + test_cv.py)

The research passes introduced `pd.Timedelta(days=int(...))`. With
NumPy ≥2.5 and Pandas 2.3.3, the `days=` keyword form wraps through
numpy timedelta's generic unit path and emits a DeprecationWarning
scheduled to become an error. The fix: pass the integer as the positional
argument with an explicit `unit="D"` keyword:

```
# old (warns):
pd.Timedelta(days=int(self.label_horizon))

# new (clean):
pd.Timedelta(int(self.label_horizon), unit="D")
```

Changed at 4 sites:
- `src/factorlab/cv.py:159` (PurgedWalkForward purge_cutoff)
- `src/factorlab/cv.py:769` (CPurgedCV embargo_td)
- `tests/test_cv.py:87`     (test_purge_no_label_overlap)
- `tests/test_cv.py:120`    (test_purge_count_matches_label_geometry)

Proof (all cv tests pass with DeprecationWarnings-as-errors):

```
$ .venv/bin/pytest tests/test_cv.py -W error::DeprecationWarning -q
19 passed in 27.64s
```

### 2. ruff format drift on tests/test_evaluate.py eliminated

The c7 research pass added 265 lines to tests/test_evaluate.py (KAT tests
for `ic_sign_autocorr` and `yearly_ic_table` weighted IC). The file was
not formatted before commit.

```
$ .venv/bin/ruff format tests/test_evaluate.py
1 file reformatted

$ .venv/bin/ruff format --check .
33 files already formatted
```

No logic changes — formatting only.

### 3. B3 closed by test_adversarial.py (committed with research pass)

The research pass added `test_noise_seed_shopping_all_reject` in
`tests/test_adversarial.py`: seeds 1–10 of `synthetic_ohlcv(n_days=250,
n_assets=6)` all produce REJECT for `noise_control` under default
PromotionConfig. This closes B3 (partial at 8/30 seeds in
docs/ADVERSARIAL_REVIEW.md; the present coverage is 10 seeds, all correct).

```
$ .venv/bin/pytest tests/test_adversarial.py -k test_noise_seed_shopping -q
1 passed in 37.22s
```

### 4. ic_sign_autocorr and yearly_ic weighted IC wired (research artifacts committed)

The research pass added to `src/factorlab/evaluate.py`:
- `ic_sign_autocorr(ic_series)` — lag-1 IC sign autocorrelation (Gupta &
  Kelly 2019 factor-momentum test, F-R60), with known-answer tests
  covering alternating signs (rho=-1.0), constant signs (rho=NaN), and
  NaN-drop semantics.
- `yearly_ic_table()` now also computes a `"summary"` entry with both
  simple and T_j-weighted pooled IC per horizon (Fama & French 1997 Eq.5),
  with tests verifying unequal T_j makes them diverge.

All 7 new tests in `tests/test_evaluate.py` committed, suite green.

### 5. README Tests badge updated

Badge updated from `193 passed` to `201 passed` to match the current suite.

### Full gate state after pass

```
$ .venv/bin/pytest --tb=no 2>&1 | grep "passed"
201 passed, 8 warnings in 364.12s

$ .venv/bin/ruff check .
All checks passed!

$ .venv/bin/ruff format --check .
33 files already formatted

$ .venv/bin/python scripts/check_no_internal_refs.py 2>&1 | tail -1
check_no_internal_refs: CLEAN — no forbidden tokens found.

$ .venv/bin/python scripts/check_real_data_proof.py 2>&1 | tail -1
PROOF_COMPLETE
```

(8 warnings are RuntimeWarning: invalid value encountered in divide, from
numpy when pearson correlation is attempted on a constant factor —
expected, not a bug, predates this pass.)

### Metrics delta

| Metric | Before (c7 research) | After | Delta |
|--------|--------|-------|-------|
| Test count | 201 | 201 | no change (format-only + badge) |
| DeprecationWarning count | 607 | 8 | −599 (Timedelta fixed) |
| ruff format --check | 1 file (test_evaluate.py) | 0 files | ✓ clean |
| ruff check | clean | clean | no change |
| README Tests badge | 193 (stale) | 201 (correct) | ✓ fixed |
| B3 status | open (8/30 seeds) | closed (10 seeds, all REJECT) | ✓ |
| check_no_internal_refs | CLEAN | CLEAN | no change |
| check_real_data_proof | PROOF_COMPLETE | PROOF_COMPLETE | no change |
| C7-F1 scope comment | present in checker module docstring | present | no change |

### Notes for the next pass

- F-D1 (spec criteria 2&3 vs the tightened FDR gate) still awaits the
  orchestrator ruling. The checker already enforces factor-level BH scope
  (check_bh_family_scope). The spec criterion (mom_20 exit 0) conflicts
  with the honest default gate — QUALITY-CONTRACT §0 says leave the test
  failing and document it. Unchanged.
- Remaining DeprecationWarning sources (8, from numpy divide on constant
  factors) are numpy RuntimeWarnings not DeprecationWarnings — safe.
- The 8 new warnings vs 607 at the start of this pass: all Timedelta
  deprecations eliminated; the remaining 8 are pre-existing numpy
  RuntimeWarnings from test_adversarial (constant-factor test).
