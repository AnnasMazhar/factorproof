# EVIDENCE.md — LANE factorproof-polish pass

Branch: `polish/recruiter`. Commands run on 2026-09-27 in worktree
`/home/openclaw/worktrees/factorproof-polish`.

Prior evidence (install, pytest, HAC proofs, real-data proof, eval-findings fix) is
in `EVIDENCE.md` at the repository root (sections 1–12).

This file documents the independent-reviewer findings addressed in this pass.

---

## R1. README results table matches code output

**Claim:** `factor-lab screen --data signal --horizons 1,5,20` prints
`Promoted (2): mom_20, mom_60`; README table updated to match exactly.

**Command:**
```
$ .venv/bin/factor-lab screen --data signal --horizons 1,5,20
```

**Output:**
```
| Factor | H | IC | IC-IR | t-stat | Q-Spread | HR-WLB | Turnover | Coverage | FDR | Verdict |
|--------|---|-----|-------|--------|----------|--------|----------|----------|-----|---------|
| lookahead_control | 5 | 0.4545 | 1.9920 | 99.40 | 0.0382 | 0.6592 | 1.1982 | 1.00 | ? | REJECT |
| rev_5 | 1 | -0.0738 | -0.2623 | -11.72 | -0.0025 | 0.4572 | 0.5227 | 1.00 | Y | REJECT |
| rsi_14 | 1 | 0.0361 | 0.1506 | 6.71 | 0.0012 | 0.4856 | 0.3263 | 0.99 | Y | REJECT |
| mom_20 | 1 | 0.0347 | 0.1268 | 5.64 | 0.0010 | 0.5124 | 0.2702 | 0.99 | Y | PROMOTE |
| atr_norm_14 | 20 | -0.0360 | -0.1165 | -1.49 | -0.0069 | 0.4805 | 0.2190 | 0.99 | Y | REJECT |
| mom_60 | 20 | 0.0316 | 0.1139 | 1.39 | 0.0070 | 0.5171 | 0.1600 | 0.97 | Y | PROMOTE |
| vol_20 | 20 | -0.0307 | -0.0984 | -1.21 | -0.0046 | 0.4819 | 0.1446 | 0.99 | N | REJECT |
| deflated_mom | 1 | 0.0199 | 0.0829 | 3.65 | 0.0007 | 0.5105 | 0.1679 | 0.97 | Y | REJECT |
| skew_60 | 20 | 0.0171 | 0.0701 | 0.92 | 0.0025 | 0.5076 | 0.1625 | 0.97 | N | REJECT |
| volume_z_20 | 1 | 0.0077 | 0.0332 | 1.48 | 0.0003 | 0.4983 | 1.3095 | 0.99 | N | REJECT |
| noise_control | 1 | 0.0075 | 0.0331 | 1.48 | 0.0001 | 0.4937 | 1.3287 | 1.00 | N | REJECT |
| autocorr_5 | 5 | -0.0063 | -0.0258 | -0.87 | -0.0009 | 0.4937 | 0.9851 | 1.00 | N | REJECT |
| amihud_illiq_20 | 20 | 0.0046 | 0.0153 | 0.19 | -0.0033 | 0.4819 | 0.0874 | 0.99 | N | REJECT |

Promoted (2): mom_20, mom_60
Rejected (11): rev_5, vol_20, atr_norm_14, rsi_14, volume_z_20, amihud_illiq_20,
               skew_60, autocorr_5, deflated_mom, noise_control, lookahead_control
```

README "Real results" section updated to match this output exactly. **PASS**

---

## R2. --plant-signal removed from quickstart, documented as no-op

**Claim:** `--plant-signal` is not in the quickstart code block; a note explains it
has no effect when `--data=signal`.

**Verification:**
```
$ grep -n "plant.signal" README.md
101:`--plant-signal` is accepted as a flag but has no effect when `--data=signal`
```

No `--plant-signal` in any bash code block; documented in prose only. **PASS**

---

## R3. Static tests badge replaced with live CI badge

**Claim:** Static `tests-107 passed` badge removed; live CI badge present.

**Verification:**
```
$ grep "badge" README.md
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![CI](https://github.com/AnnasMazhar/factorproof/actions/workflows/ci.yml/badge.svg)
![Ruff](https://img.shields.io/badge/ruff-clean-brightgreen)
![Licence](https://img.shields.io/badge/licence-MIT-green)
```

No static tests badge. Live CI badge present. **PASS**

---

## R4. real-data-proof.md §3 q value corrected

**Claim:** §3 previously said "BH-FDR q=0.15"; corrected to q=0.10. Defl Sharpe
column retained with explanatory note (all 0.0000 — diagnostic only, not in gate).

**Verification:**
```
$ grep "q=0\." reports/real-data-proof.md
- Factors passing BH-FDR q=0.10 across family: **2**
```

```
$ grep -A5 "Note on the Defl Sharpe" reports/real-data-proof.md
> **Note on the Defl Sharpe column above:** All 13 values show 0.0000, including
> `lookahead_control` which has IC=0.42. This indicates the Deflated Sharpe
> computation on this dataset produces near-zero values — the column is not
> meaningful as presented. Deflated Sharpe is computed as a diagnostic but is
> **not wired into the promotion gate**; promotion is driven by the 10 gate
> criteria (IC, IC-IR, HAC t-stat, Wilson LB, BH-FDR, etc.). See README
> Limitations for the explicit caveat.
```

**PASS**

---

## R5. GitHub Release job in release.yml

**Claim:** `release.yml` now has a `github-release` job that creates a GitHub Release
with generated notes and attaches `dist/*` on any `v*` tag.

**Verification:**
```
$ grep -A20 "github-release:" .github/workflows/release.yml
  github-release:
    name: Create GitHub Release
    needs: build
    runs-on: ubuntu-latest
    permissions:
      contents: write

    steps:
      - name: Download dist packages
        uses: actions/download-artifact@v4
        with:
          name: python-package-distributions
          path: dist/

      - name: Create GitHub Release with artifacts
        uses: softprops/action-gh-release@v2
        with:
          generate_release_notes: true
          files: dist/*
```

**PASS**

---

## R6. Agent artifact files removed

**Claim:** `reports/eval-c*.json`, `reports/mutation-c*.json`, `reports/improvements.md`
are gone from the working tree and index.

**Verification:**
```
$ ls reports/
adversarial-attacks.json
leakage-experiment.json
real-data-proof.json
real-data-proof.md
unseen-split.json
```

No eval-c*, mutation-c*, or improvements.md. **PASS**

---

## R7. MANDATE references and pass-ID tokens removed

**Claim:** No "MANDATE" token and no `c1-p6` / `c2-p7` style tokens in tracked files
(excluding EVIDENCE.md which describes the removal).

**Command:**
```
$ grep -rn "MANDATE" . --include="*.md" --include="*.py" --include="*.yml" \
    --include="*.json" | grep -v ".git/" | grep -v "EVIDENCE"
(no output)

$ grep -rn "\bc[0-9]-p[0-9]\b" . --include="*.md" --include="*.py" \
    --include="*.yml" --include="*.json" | grep -v ".git/" | grep -v "EVIDENCE"
(no output)
```

**PASS**

---

## R8. Package/CLI clarification line in README

**Claim:** Line "The package is `factor-lab`; the CLI is `factor-lab` (repo name
`factorproof`)." appears near the top of README.md.

**Verification:**
```
$ head -6 README.md
# factorproof

The overfitting controls that quant research actually needs — without a £100/month licence.

The package is `factor-lab`; the CLI is `factor-lab` (repo name `factorproof`).
```

**PASS**

---

## R9. Repo-local git author set

**Claim:** `user.name` and `user.email` set at repo level (no history rewrite).

**Command:**
```
$ git config user.name "Syed Annas Bin Mazhar"
$ git config user.email "28944679+AnnasMazhar@users.noreply.github.com"
```

**Verification:**
```
$ git config user.name
Syed Annas Bin Mazhar

$ git config user.email
28944679+AnnasMazhar@users.noreply.github.com
```

noreply address from `gh api user --jq .email` (AnnasMazhar account). **PASS**

---

## R10. pytest -q — final verification (2026-09-27)

**Command:**
```
$ .venv/bin/python -m pytest --tb=short
```

**Output (final line):**
```
120 passed, 522 warnings in 307.34s (0:05:07)
```

**PASS** — 120 tests, 0 failures.

---

## R11. ruff check . — final verification

**Command:**
```
$ .venv/bin/ruff check .
```

**Output:**
```
All checks passed!
```

```
$ .venv/bin/ruff format --check .
25 files already formatted
```

**PASS**

---

## R12. check_no_internal_refs.py — final verification

**Command:**
```
$ .venv/bin/python scripts/check_no_internal_refs.py
```

**Output:**
```
check_no_internal_refs: CLEAN — no forbidden tokens found.
```

**PASS**
