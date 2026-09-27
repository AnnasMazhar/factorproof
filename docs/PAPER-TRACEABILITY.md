# PAPER-TRACEABILITY.md — factor-lab v0.1.1

Method → Implementation → Test → Evidence traceability table.
Covers every statistical method cited in README, EVIDENCE.md, and the promotion gate.
See `docs/IMPLEMENTATION-NOTES.md` for the detailed equation derivations.

---

## 1. Benjamini-Hochberg FDR Correction

**Reference:** Benjamini & Hochberg (1995) J. Royal Statistical Society B 57(1):289-300.

**Algorithm (BH-1995):**
- Order m p-values p_(1) ≤ ... ≤ p_(m)
- Find k* = max{i : p_(i) ≤ (i/m)·q}
- Reject H_(1), ..., H_(k*)

**Implementation:**
- `src/factorlab/significance.py:benjamini_hochberg` — direct transcription of Algorithm 1
- `src/factorlab/promote.py:promote` Gate 8 — builds the BH family from all horizon
  p-values (m = len(horizons)) plus any extra-factor p-values from screen mode.
  **Multiplicity fix (v0.1.1):** previously used m=1 (only the best horizon's p-value),
  which is selection bias identical to what this library exists to prevent. Now m = number
  of horizons actually searched per factor.

**Tests:**
- `tests/test_significance.py:test_benjamini_hochberg_*` — unit tests for BH procedure
- `tests/test_promote.py:test_fdr_multiplicity_spans_horizons_searched` — asserts m=3
  when 3 horizons are evaluated; **fails if m=1 is used**
- `tests/test_promote.py:test_fdr_multiplicity_single_horizon_gives_m1` — asserts m=1
  with single horizon (no over-correction)

**Evidence:** EVIDENCE.md §11a — m=3 confirmed in CLI output note field.

---

## 2. Newey-West HAC t-statistic

**Reference:** Newey & West (1987) Econometrica 55(3):703-708.

**Algorithm:** Bartlett-kernel HAC standard error.
    V_HAC = γ₀ + 2·Σᵢ₌₁ᴸ (1 − l/(L+1))·γₗ
    SE_HAC = sqrt(V_HAC / T)
    t_HAC = mean(IC) / SE_HAC
    L = max_lags = H − 1 (horizon-1 lags to capture label overlap)

**Implementation:**
- `src/factorlab/evaluate.py:_newey_west_se` — Bartlett kernel
- `src/factorlab/evaluate.py:information_coefficient` — returns `ic_tstat` (HAC) and
  `ic_tstat_naive` (diagnostic, not used in gate)

**Tests:**
- `tests/test_evaluate.py:test_hac_tstat_reduced_by_overlap`
- `tests/test_adversarial.py:test_hac_tstat_lower_than_naive_at_h20`

**Evidence:** EVIDENCE.md §5, §6 — HAC/naive ratio > 1.5 at H=20 confirmed.

---

## 3. Purged Walk-Forward Cross-Validation

**Reference:** López de Prado (2018) "Advances in Financial Machine Learning" ch. 7.

**Algorithm:**
- Split dates into N sequential train/test folds (walk-forward, no future leakage)
- Purge: remove training rows whose forward-label window overlaps the test window
- Embargo: add ≥H days gap after each test fold

**Implementation:**
- `src/factorlab/cv.py:PurgedWalkForward` — split generator
- `src/factorlab/cv.py:evaluate_walk_forward` — takes a `PurgedWalkForward` splitter
  (not a list of splits); **OOS IC bug fix (v0.1.1):** `prove_on_real_data.py` was
  passing `list(cv.split(df))` instead of `cv`; the bare `except Exception` hid the
  `AttributeError`, producing OOS IC = nan for all real-data rows.

**Tests:**
- `tests/test_cv.py:test_purged_walk_forward_*` — split structure, no leakage
- `tests/test_promote.py:test_planted_signal_promoted` — end-to-end OOS check

**Evidence:** EVIDENCE.md §11d — root cause documented; fix applied.

---

## 4. Wilson Score Lower Bound on Hit Rate

**Reference:** Wilson (1927) J. American Statistical Association 22(158):209-212.

**Algorithm:** 95% lower confidence bound for binomial proportion p:
    LB = (p̂ + z²/2n − z·sqrt(p̂(1−p̂)/n + z²/4n²)) / (1 + z²/n)
    z = 1.96 (95% one-sided, conservatively)

**Implementation:**
- `src/factorlab/significance.py:wilson_lower_bound`

**Tests:**
- `tests/test_significance.py:test_wilson_lower_bound_*`
- `tests/test_promote.py:test_planted_signal_promoted` — asserts LB ≥ 0.505

**Evidence:** EVIDENCE.md §11b — hit_rate_wilson_lb = 0.5124 vs threshold 0.5000 (+0.0124 margin).

---

## 5. Deflated Sharpe Ratio (DSR)

**Reference:** Bailey & López de Prado (2014) J. Portfolio Management 40(5):94-107.

**Algorithm:**
    SR* = (1−γ)·Z(1−1/n) + γ·Z(1−1/(n·e))   (expected max SR from n trials)
    DSR = Φ((SR − SR*) · sqrt(T−1) / sqrt(1 − skew·SR + (kurt−1)/4·SR²))

DSR returns a probability in [0,1].  Values near 0 indicate the observed SR is below
the expected maximum from n trials (not a computation error; correctly shows near-0
for small SR with many trials).

**v0.1.1 display fix:** Previously formatted as "{:.4f}" causing "0.0000" to appear
indistinguishable from nan.  Now formatted as "<0.001" when value < 0.001.

**Implementation:**
- `src/factorlab/significance.py:deflated_sharpe_ratio`
- `scripts/prove_on_real_data.py:_fmt_prob` — display formatter

**Tests:**
- `tests/test_significance.py:test_deflated_sharpe_ratio_*`

**Evidence:** EVIDENCE.md §11d — Defl Sharpe display clarified; not a computation bug.

---

## 6. Summary of v0.1.1 Fixes vs Cited Methods

| Finding | Method Affected | Fix Applied | Test Covering Fix |
|---------|----------------|-------------|-------------------|
| BH m=1 selection bias | BH FDR (§1) | m = len(horizons) | test_fdr_multiplicity_spans_horizons_searched |
| fdr_q raised to 0.15 | BH FDR (§1) | Reverted to 0.10 + stronger signal | test_planted_signal_promoted |
| OOS IC = nan | Purged WF CV (§3) | Pass cv splitter not splits list | test_planted_signal_promoted |
| Defl Sharpe = 0.0000 | DSR (§5) | _fmt_prob: show <0.001 for near-zero | (display only; no semantic bug) |
| --plant-signal no-op | CLI contract | Emit stderr note | test_promote_plant_signal_no_op_note |
