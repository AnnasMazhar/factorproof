# docs/ADVERSARIAL_REVIEW.md — factor-lab v0.1

## PASS c1-p10-adversarial-1 (cycle 1, adversarial pass 1 of 3)

Independent reviewer lane. This pass did not author the code under review. Commands below were
actually run; output is verbatim terminal output. Prior artifact `docs/ADVERSARIAL-REVIEW.md`
(hyphenated, earlier pass) was read first and is built on, not repeated.

Positioning check against `specs/MARKET-VERDICTS.md`: no conflict found — README.md leads with the
licence problem ("without a £100/month licence", line 3), `COMPARISONS.md` carries the
MlFinLab-vs-Quantopian-vs-this table, and both README and COMPARISIONS state MlFinLab is more
complete. Nothing to record in EVIDENCE.md as a conflict.

---

## 1. Claims audit — 3 most load-bearing README claims, attacked

### C1 — "Promote a real signal (exit 0) or reject noise (exit 1)" (README lines 22-24, 121)

Attack: run the exact commands from a clean shell and read the raw exit codes (the earlier
review's `EXIT=$?` was measured after a `| tail` pipe, i.e. it measured `tail`, not the CLI —
re-measured here without a pipe).

```
$ uv run factor-lab promote mom_20 --data signal --plant-signal >/dev/null 2>&1; echo "mom_20_planted=$?"
mom_20_planted=0
$ uv run factor-lab promote noise_control --data signal >/dev/null 2>&1; echo "noise=$?"
noise=1
$ uv run factor-lab promote mom_20 --data signal >/dev/null 2>&1; echo "mom_20_noPlant=$?"
mom_20_noPlant=0
```

Gate table for the standalone promotion claim (README: "mom_20 promotes in isolation
(IC=0.025, p=0.107 at q=0.15 with m=1)"):

```
$ uv run factor-lab promote mom_20 --data signal --plant-signal
Factor:  mom_20
Verdict: PROMOTE
min_abs_ic                                0.0252       0.0200   PASS
min_ic_ir                                 0.0750       0.0500   PASS
hit_rate_wilson_lb                        0.5013       0.5000   PASS
oos_consistency                           0.6000       0.6000   PASS
survives_fdr                              0.1065       0.1500   PASS
  note: BH FDR q=0.15, m=1 tests
```

**Verdict: CLAIM SUPPORTED.** Exit 0 / exit 1 as documented; IC=0.0252 (~0.025), FDR
p/q value 0.1065 (~0.107), q=0.15, m=1 all match the README sentence. Ten gates are
emitted, matching the README design diagram ("10 gates; all must pass").

### C2 — "Real results (from examples/run_demo.sh)": the README table is this demo's output

Attack: re-run the demo from scratch and diff every table row against README.

```
$ bash examples/run_demo.sh > /tmp/opencode/demo.txt 2>&1; echo "demo_exit=$?"
demo_exit=0
$ grep '^|' /tmp/opencode/demo.txt | sort -u > /tmp/opencode/dr.txt
$ grep '^|' README.md | sort -u > /tmp/opencode/rr.txt
$ diff /tmp/opencode/dr.txt /tmp/opencode/rr.txt && echo ROWS_IDENTICAL
ROWS_IDENTICAL
$ grep -n 'Promoted' /tmp/opencode/demo.txt
39:Promoted (0): none
$ sed -n '39,41p' /tmp/opencode/demo.txt
Promoted (0): none
Rejected (13): mom_20, mom_60, rev_5, vol_20, atr_norm_14, rsi_14, volume_z_20, amihud_illiq_20, skew_60, autocorr_5, deflated_mom, noise_control, lookahead_control
```

**Verdict: CLAIM SUPPORTED.** Every README table row (13 factors × 11 columns) is byte-identical
to a fresh demo run, and "0 promoted / 13 rejected" matches the README "0/13" claim. Note the
README sentence "Promoted in screen: 0/13..." is prose, not demo output — the demo's own line is
"Promoted (0): none"; substance matches.

### C3 — Positioning claims: MlFinLab £100+VAT and restrictive licence; Quantopian stack last maintained 2020

Attack: fetch the primary sources live.

```
$ curl -sS -L https://raw.githubusercontent.com/hudson-and-thames/mlfinlab/master/LICENSE.txt | grep -nE '6\.6|6\.7|14\.2|14\.3|14\.5' | head
160:6.6	The Licensee shall not lease, loan, resell, sublicense or otherwise distribute the Licensed Materials to any other
164:6.7	The Licensee and its Users undertake not to reverse engineer the Licensed Materials and agrees not to set up in
354:14.2	The Company possesses information that has been created, researched, or developed by the Company (including
362:14.3	All Proprietary Information herein shall be the Company's property and its assigns, who shall remain the sole
373:14.5	The Licensee agrees not to lease, loan, resell, sublicense or otherwise distribute any software or product

$ curl -sS -L https://hudsonthames.org/mlfinlab/ | grep -oiE '(£|\$)[ ]?[0-9]+[^<]{0,40}'
£100 (+VAT)

$ curl -sS "https://api.github.com/repos/quantopian/alphalens/commits?per_page=1" | grep -m1 '"date"'
        "date": "2020-04-27T18:40:41Z"
$ curl -sS "https://api.github.com/repos/quantopian/pyfolio/commits?per_page=1" | grep -m1 '"date"'
        "date": "2020-02-28T17:30:19Z"
$ curl -sS https://api.github.com/repos/hudson-and-thames/mlfinlab | grep -E '"(stargazers_count|pushed_at)"'
  "pushed_at": "2023-10-02T03:05:19Z",
  "stargazers_count": 4933,
```

**Verdict: CLAIM SUPPORTED.** Licence clauses 6.6 (no redistribution/sublicensing), 6.7 (no
reverse engineering / no competing product), 14.2/14.3 (proprietary info is the licensor's
property) exist verbatim; pricing page returns exactly `£100 (+VAT)`; alphalens' last commit is
2020-04-27 and pyfolio's 2020-02-28, so "last maintained in 2020" holds. mlfinlab repo state
(4,933 stars, pushed 2023-10-02) matches `docs/RESEARCH.md` §6.1 exactly.

### Incidental badge claims (checked while attacking)

```
$ uv run pytest
105 passed in 28.93s
$ uv run ruff check .
All checks passed!
$ uv run ruff format --check .
18 files already formatted
```

README badge "tests-105 passed" and "ruff-clean" are accurate as of this pass.

---

## 2. Citation audit — every link in docs/RESEARCH.md

Method: extracted all 40 unique URLs with `grep -oE 'https://[^ ]+' docs/RESEARCH.md`, probed each
with `curl -sS -o /dev/null -w '%{http_code}' -L --max-time 20 -A 'Mozilla/5.0 ... research-audit/1.0'`.

```
$ while read -r u; do code=$(curl ... "$u"); printf '%s %s\n' "$code" "$u"; done < links.txt | tee link_audit.txt | sort | uniq -c -w3
     33 200 ...
      6 403 ...
      1 curl: (47) Maximum (50) redirects followed
      1 302ERR https://doi.org/10.3905/jpm.2014.40.5.094
```

Non-200 detail (raw):

```
403 https://doi.org/10.1080/01621459.1927.10502953
403 https://doi.org/10.1093/rfs/1.1.41
403 https://doi.org/10.1093/rfs/hhv059
403 https://doi.org/10.1111/0022-1082.00247
403 https://doi.org/10.1111/j.1540-6261.1985.tb05004.x
403 https://doi.org/10.1111/j.1540-6261.1993.tb04702.x
curl: (47) Maximum (50) redirects followed
302ERR https://doi.org/10.3905/jpm.2014.40.5.094
```

Disposition:

- **33/40 → HTTP 200**, including every "Verified URL" alternative the file promises
  (jstor.org ×11, nber.org ×3, arxiv.org/abs/1405.4598, archive.org, ijcai.org PDF,
  taylorfrancis, wiley book page, all 10 §6.5 ecosystem URLs: mlfinlab LICENSE.txt,
  hudsonthames.org, quantopian/alphalens + pyfolio commits, alphalens-reloaded, qlib,
  purgedcv repo + PyPI, ml4t/diagnostic, pyanomaly).
- **6× 403**: publisher DOI resolvers (Wiley, OUP, T&F, Taylor Francis) bot-blocking. RESEARCH.md's
  header documents this explicitly and each has a 200-returning JSTOR/NBER/arXiv alternate in the
  same citation block — verified present above.
- **1× redirect loop**: `https://doi.org/10.3905/jpm.2014.40.5.094` (Bailey & López de Prado DSR)
  loops (`curl: (47) Maximum (50) redirects followed`, also fails with `--max-redirs 10` →
  `302 10`). RESEARCH.md §2.4 documents the DOI as "returns HTTP 302 redirect to publisher page"
  and supplies arXiv:1405.4598, which returns 200. So the citation resolves via the alternate,
  but the in-file description understates the failure (it is a loop, not a resolvable redirect).

**Support check (claim vs source), spot-verified against fetched text:** licence clauses ✓ (§C3
above), pricing ✓, competitor star counts / push dates ✓ (§6.1 table matches GitHub API),
Jegadeesh-Titman JSTOR 2328882 → 200 ✓, BH JSTOR 2346101 → 200 ✓, Wilson DOI → 403 with
JSTOR alternate 200 ✓, Wilson normal-approx formula 26.2.17 archive.org → 200 ✓.
No citation found that resolves to a page contradicting its claim.

---

## 3. Test-quality audit — 6 tests sampled, named fault injected, suite run

Driver: `/tmp/opencode/inject.py` — for each sample: back up source file, apply one exact string
mutation, run pytest, restore, then re-run the full suite to prove the tree is green.

| # | test | injected fault (one string mutation) | suite result |
|---|------|--------------------------------------|--------------|
| T1 | `tests/test_significance.py::test_wilson_lower_hand_computed` | drop `+ z2 / (4 * n * n)` from the Wilson denominator sqrt term | FAILED (exit 1) — DETECTED |
| T2 | `tests/test_significance.py::test_bh_fdr_hand_computed` | `if pval <= threshold:` → `if pval < threshold:` | FAILED (exit 1) — DETECTED, but by sibling test (see F-T2) |
| T3 | `tests/test_cv.py::test_purge_no_label_overlap` | purge window zeroed: `first_test_date - Timedelta(days=label_horizon)` → `days=0` | **GREEN (exit 0) — NOT DETECTED** (see F-T3) |
| T4 | `tests/test_evaluate.py::test_forward_returns_no_lookahead` | `close.shift(-h)` → `close.shift(h)` | FAILED (exit 1) — DETECTED |
| T5 | `tests/test_promote.py::test_noise_control_rejected` | verdict ignores gates: `"promote" if all_passed else "reject"` → `"promote"` | FAILED (exit 1) — DETECTED |
| T6 | `tests/test_adversarial.py::test_check_lookahead_source_finds_negative_shifts` | `check_lookahead_source` forced to `return []` | FAILED (exit 1) — DETECTED |

Raw output (abridged only to the assertion lines; full log `/tmp/opencode/inject_out.txt`):

```
### T1 wilson lower bound KAT
pytest tests/test_significance.py::test_wilson_lower_hand_computed -> exit 1 :: DETECTED (suite failed)
E       AssertionError: Expected ~0.4524, got 0.454249

### T2 BH threshold boundary
pytest tests/test_significance.py::test_bh_fdr_hand_computed -> exit 0 :: NOT DETECTED (suite still green)

### T3 purge honours label horizon
pytest tests/test_cv.py::test_purge_no_label_overlap -> exit 0 :: NOT DETECTED (suite still green)

### T4 forward returns use future close
pytest tests/test_evaluate.py::test_forward_returns_no_lookahead -> exit 1 :: DETECTED (suite failed)
E       AssertionError: Forward returns should all be positive for a strictly increasing price series

### T5 verdict honours gate results
pytest tests/test_promote.py::test_noise_control_rejected -> exit 1 :: DETECTED (suite failed)
E       assert 'promote' == 'reject'

### T6 lookahead source inspection
pytest tests/test_adversarial.py::test_check_lookahead_source_finds_negative_shifts -> exit 1 :: DETECTED (suite failed)
E       AssertionError: shift(-1) not found in: []

### RESTORE CHECK (full suite)
pytest tests -> exit 0
```

T2 re-probed at full-suite level (the contract asks whether *the suite* fails):

```
=== T2 BH < vs <= full-suite exit=1 ===
E       AssertionError: p=0.10 at threshold boundary should be rejected
FAILED tests/test_significance.py::test_bh_fdr_exact_boundary - AssertionError
```

T3 re-probed: purge removed **and** embargo removed together:

```
purge_removed+embargo_removed -> tests/test_cv.py exit=1
=========================== short test summary info ============================
FAILED tests/test_cv.py::test_purge_no_label_overlap - AssertionError: Split ...
FAILED tests/test_cv.py::test_embargo_removes_gap - AssertionError: Split 0: gap between last train (2019-04-16) and first test (2019-04-17) is 0 positions, expected >= 5
full suite after restore exit=0
```

**Score: 5 of 6 named faults fail the suite.** T3's named fault alone does not (F-T3).

---

## 4. Bypass hunt (pass-1 scope: claim-adjacent attempts only)

- **Force flag:** `uv run factor-lab promote --force noise_control` → argparse
  `unrecognized arguments: --force`, exit 2. No override path exists (re-confirmed against the
  earlier pass).
- **Gate relaxation:** per earlier pass, permissive `PromotionConfig` alone does not promote
  noise (turnover + OOS-consistency + FDR still reject). Not re-litigated.
- **README command honesty:** the exact three commands printed in README lines 20-24 were run
  unmodified and behaved as printed (exit codes in §C1).

---

## Findings table

| id | severity | finding | evidence | status |
|----|----------|---------|----------|--------|
| F-T3 | minor | `test_purge_no_label_overlap` docstring claims it detects "purge step missing or label_horizon not applied", but injecting exactly that fault leaves the whole suite green: with `embargo_days >= label_horizon` the embargo independently enforces `label_end < first_test_date`, so the test cannot distinguish "purge broken" from "purge working". The *property* is still safe (combined purge+embargo removal fails the test); only the stated per-fault detection claim is false. | inject.py T3 → `pytest tests` exit 0; purge+embargo removal → `tests/test_cv.py` exit 1 (raw output §3) | open |
| F-T2 | minor | `test_bh_fdr_hand_computed`'s own KAT values do not sit on the `<=` boundary, so it alone does not fail when the BH comparison is mutated to strict `<`; detection comes from sibling `test_bh_fdr_exact_boundary`. Suite-level detection is real, single-test attribution in the docstring is slightly over-claimed. | inject.py T2 node run exit 0; full-suite run exit 1 via `test_bh_fdr_exact_boundary` (raw output §3) | open |
| F-L1 | minor | `docs/RESEARCH.md` §2.4 says the DSR DOI "returns HTTP 302 redirect to publisher page"; the live behaviour is a redirect **loop** (curl exit 47, 50 redirects; `--max-redirs 10` → `302 10`). The arXiv alternate in the same block returns 200, so the citation itself resolves. Wording inaccuracy only. | link audit raw output §2 | open |
| P01 | — | Positioning conflict with `MARKET-VERDICTS.md`: none found. README leads with the licence problem, COMPARISONS.md table present, MlFinLab-more-complete stated. | README lines 3, 12-13, 42-46, 183-185; RESEARCH.md §6.1 | refuted (no conflict) |

Claims C1/C2/C3: all three **supported** — no blocker, no major. Findings above are test/doc
precision issues, not safety regressions: the leakage property, the gate verdict, and the
promotion exit-code contract all survived attack.

### Status key
- `open`: reported for the builder; not yet fixed (reviewer does not fix code)
- `refuted`: attack attempted, claim held

---

## Summary

- 3 load-bearing README claims attacked with concrete commands: 3/3 supported
- 40 citation links probed: 33×200, 6×403 (documented publisher bot-blocking, alternates all 200),
  1× redirect loop (documented alternate 200); no contradicting source found
- 6 tests fault-injected: 5/6 fail the suite on their named fault; 1 (T3) masked by embargo → F-T3
- Full suite green after every mutation restored: `105 passed in 28.93s`, ruff check + format clean
- 0 blockers, 0 majors, 3 minors open, 1 positioning non-conflict recorded
