"""
factorlab.promote — evidence-gated factor promotion.

The gate exists to refuse promotion to weak signals.
It is deliberately strict: pass all criteria or reject.
There is no --force flag. That is the point.

Gate sequence follows the pipeline:
    1. Structural checks (degenerate, coverage, lookahead)
    2. Sample size floor
    3. IC metrics (mean IC, IC-IR)
    4. Hit rate Wilson lower bound
    5. Walk-forward OOS consistency
    6. FDR (multiple-testing correction)
    7. Turnover ceiling
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

from .cv import (
    CPurgedCV,
    PurgedWalkForward,
    check_lookahead,
    check_lookahead_runtime,
    check_lookahead_source,
    evaluate_cpcv,
    evaluate_walk_forward,
)
from .data import synthetic_ohlcv
from .evaluate import evaluate_factor
from .factors.base import Factor
from .significance import benjamini_hochberg

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class PromotionConfig:
    """Configurable thresholds for the promotion gate.

    Defaults are conservative; tune only with documented justification.
    """

    min_observations: int = 30
    """Minimum number of non-overlapping cross-sections (hard floor)."""

    min_ic_ir: float = 0.05
    """Minimum |IC-IR| across horizons."""

    min_abs_ic: float = 0.02
    """Minimum |mean IC| at the best horizon."""

    hit_rate_wilson_lb: float = 0.5
    """Wilson lower bound on directional hit rate (must exceed 50%)."""

    max_turnover: float = 0.5
    """Maximum mean absolute rank-weight change per rebalance."""

    oos_consistency_min: float = 0.60
    """Fraction of walk-forward splits that must agree in IC sign."""

    fdr_q: float = 0.10
    """FDR level for Benjamini-Hochberg correction.

    Default 0.10 per Benjamini & Hochberg (1995).  The BH procedure is applied
    across all hypothesis tests actually run for this factor, including one test
    per horizon searched (see Gate 8 comment below).  Do not raise this default
    to compensate for a weak signal — use a stronger signal instead.
    """

    coverage_min: float = 0.50
    """Minimum fraction of non-NaN observations."""

    n_wf_splits: int = 5
    """Number of walk-forward splits (used when cv_method='walk_forward')."""

    embargo_days: int = 20
    """Embargo days in walk-forward/CPCV splits. Must be >= max(horizons) = 20."""

    cv_method: str = "walk_forward"
    """Cross-validation method: 'walk_forward' (default) or 'cpcv'.

    'walk_forward': PurgedWalkForward — n_wf_splits sequential folds.
    'cpcv': CPurgedCV — C(n_cpcv_groups, k_cpcv_test) combinatorial folds.
    CPCV generates more OOS paths (e.g. C(6,2)=15 vs 5 walk-forward),
    producing more robust sign-consistency estimates at the cost of
    training set size per split.
    """

    n_cpcv_groups: int = 6
    """Number of date groups for CPCV (used when cv_method='cpcv')."""

    k_cpcv_test: int = 2
    """Number of groups held out as test per CPCV combination."""

    n_days: int = 2000
    """Synthetic data length (overridable).

    Default 2000 days gives enough observations to provide clear margins on all
    gates for a genuine AR(1) signal (rho=0.15, n_assets=20).  The original
    1500-day default produced knife-edge margins on hit_rate_wilson_lb and
    oos_consistency; 2000 days clears all gates with >=0.01 margin per gate.
    """

    n_assets: int = 20
    """Synthetic data asset count (overridable).

    Default 20 assets.  More cross-sectional observations per date strengthen
    IC estimates and Wilson lower bounds without altering the factor library.
    Original 12-asset default produced marginal hit-rate LB.
    """

    seed: int = 7
    """RNG seed for synthetic data (deterministic)."""

    horizons: list[int] = field(default_factory=lambda: [1, 5, 20])
    """Forward-return horizons to evaluate."""


# ---------------------------------------------------------------------------
# Reason codes
# ---------------------------------------------------------------------------


@dataclass
class Reason:
    """One gate criterion with its pass/fail status and observed value."""

    code: str
    passed: bool
    observed: float | str
    threshold: float | str
    note: str = ""


# ---------------------------------------------------------------------------
# Promotion decision
# ---------------------------------------------------------------------------


@dataclass
class PromotionDecision:
    """Full promotion verdict with ordered evidence."""

    factor_name: str
    verdict: Literal["promote", "reject"]
    reasons: list[Reason]
    best_horizon: int
    best_ic: float
    best_ic_ir: float
    oos_consistency: float
    n_obs: int

    def __str__(self) -> str:
        lines = [
            f"Factor:  {self.factor_name}",
            f"Verdict: {self.verdict.upper()}",
            "",
            f"{'Gate':<35} {'Obs':>12} {'Threshold':>12} {'Pass':>6}",
            f"{'-'*35} {'-'*12} {'-'*12} {'-'*6}",
        ]
        for r in self.reasons:
            obs = f"{r.observed:.4f}" if isinstance(r.observed, float) else str(r.observed)
            thr = f"{r.threshold:.4f}" if isinstance(r.threshold, float) else str(r.threshold)
            mark = "PASS" if r.passed else "FAIL"
            lines.append(f"{r.code:<35} {obs:>12} {thr:>12} {mark:>6}")
            if r.note:
                lines.append(f"  note: {r.note}")
        lines.append("")
        lines.append(
            f"Best horizon: {self.best_horizon}d | IC: {self.best_ic:.4f} | IC-IR: {self.best_ic_ir:.4f}"
        )
        lines.append(f"OOS consistency: {self.oos_consistency:.2%} | Observations: {self.n_obs}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main gate
# ---------------------------------------------------------------------------


def promote(
    factor: Factor,
    df,  # pd.DataFrame — not typed here to avoid circular import at module level
    cfg: PromotionConfig | None = None,
    extra_factors_p_values: list[float] | None = None,
) -> PromotionDecision:
    """Evaluate a factor and return a promotion decision.

    Parameters
    ----------
    factor:
        Factor instance to evaluate.
    df:
        OHLCV panel (tidy long format).
    cfg:
        PromotionConfig. Uses defaults if None.
    extra_factors_p_values:
        Additional p-values from other factors in the same screening session,
        for FDR correction across the full family. If None, only this factor
        is tested (conservative: Bonferroni with m=1 == no correction).

    Returns
    -------
    PromotionDecision with verdict and ordered reason table.
    """
    if cfg is None:
        cfg = PromotionConfig()

    reasons: list[Reason] = []

    # ------------------------------------------------------------------
    # Gate 0: Lookahead contamination — structural flag
    # ------------------------------------------------------------------
    is_lookahead = check_lookahead(factor)
    reasons.append(
        Reason(
            code="not_lookahead",
            passed=not is_lookahead,
            observed="yes" if is_lookahead else "no",
            threshold="no",
            note="Factor has uses_future_data=True flag — structural lookahead."
            if is_lookahead
            else "",
        )
    )
    if is_lookahead:
        return PromotionDecision(
            factor_name=factor.name,
            verdict="reject",
            reasons=reasons,
            best_horizon=-1,
            best_ic=float("nan"),
            best_ic_ir=float("nan"),
            oos_consistency=float("nan"),
            n_obs=0,
        )

    # ------------------------------------------------------------------
    # Gate 0.5: Lookahead contamination — source inspection (M01 fix)
    #
    # A factor may use future data without setting uses_future_data=True.
    # This gate inspects the compute() source for negative-shift patterns
    # (.shift(-N)) that access future rows. These are lookahead by construction
    # unless the factor has explicitly acknowledged them via uses_future_data=True
    # (which Gate 0 already handles by blocking those factors before this point).
    #
    # If negative shifts are found, the factor is rejected with a description
    # of the specific patterns, so the author can audit and, if the usage is
    # intentional (e.g. labelling future returns in a supervised context that is
    # not a promotion factor), they can explicitly set uses_future_data=True.
    #
    # Source unavailable (lambdas, REPL, compiled): gate passes with a warning note.
    # ------------------------------------------------------------------
    source_patterns = check_lookahead_source(factor)
    if source_patterns:
        reasons.append(
            Reason(
                code="no_negative_shifts",
                passed=False,
                observed=", ".join(source_patterns),
                threshold="none",
                note=(
                    "compute() contains negative-shift patterns that access future rows: "
                    + ", ".join(source_patterns)
                    + ". Set uses_future_data=True if this is intentional."
                ),
            )
        )
        return PromotionDecision(
            factor_name=factor.name,
            verdict="reject",
            reasons=reasons,
            best_horizon=-1,
            best_ic=float("nan"),
            best_ic_ir=float("nan"),
            oos_consistency=float("nan"),
            n_obs=0,
        )

    # ------------------------------------------------------------------
    # Gate 0.75: Lookahead contamination — runtime detection (F-A3 fix)
    #
    # Source inspection can be bypassed by hiding the shift amount in a
    # closure variable (e.g. `shift_amount = -5; close.shift(shift_amount)`).
    # Runtime detection checks if the factor is highly correlated with FUTURE
    # returns, which is impossible without lookahead.
    #
    # A legitimate factor predicting future returns will have IC ~0.02-0.10.
    # A factor using future data (even smoothed) will have IC ~0.30+.
    # Threshold 0.30 catches lookahead while allowing legitimately predictive
    # factors. This is more sensitive than 0.80 because smoothing can dilute
    # a perfect lookahead signal.
    # ------------------------------------------------------------------
    is_runtime_lookahead, runtime_reason = check_lookahead_runtime(factor, df, threshold=0.30)
    if is_runtime_lookahead:
        reasons.append(
            Reason(
                code="no_future_correlation",
                passed=False,
                observed="high",
                threshold="< 0.30",
                note=runtime_reason,
            )
        )
        return PromotionDecision(
            factor_name=factor.name,
            verdict="reject",
            reasons=reasons,
            best_horizon=-1,
            best_ic=float("nan"),
            best_ic_ir=float("nan"),
            oos_consistency=float("nan"),
            n_obs=0,
        )

    # ------------------------------------------------------------------
    # Compute factor values and metrics
    # ------------------------------------------------------------------
    factor_vals = factor.compute(df)

    # Gate 1: Not degenerate (non-constant output, coverage >= min)
    cov = float(factor_vals.notna().sum() / len(factor_vals)) if len(factor_vals) > 0 else 0.0
    is_constant = bool(factor_vals.dropna().nunique() <= 1) if factor_vals.notna().any() else True

    reasons.append(
        Reason(
            code="not_degenerate",
            passed=not is_constant,
            observed="constant" if is_constant else "varied",
            threshold="non-constant",
            note="Factor returns a single unique value across all observations."
            if is_constant
            else "",
        )
    )
    reasons.append(
        Reason(
            code="coverage",
            passed=cov >= cfg.coverage_min,
            observed=cov,
            threshold=cfg.coverage_min,
        )
    )

    if is_constant or cov < cfg.coverage_min:
        return PromotionDecision(
            factor_name=factor.name,
            verdict="reject",
            reasons=reasons,
            best_horizon=-1,
            best_ic=float("nan"),
            best_ic_ir=float("nan"),
            oos_consistency=float("nan"),
            n_obs=0,
        )

    # ------------------------------------------------------------------
    # Gate 2: Minimum observations
    # ------------------------------------------------------------------
    metrics_list = evaluate_factor(
        factor_vals=factor_vals,
        df=df,
        horizons=cfg.horizons,
        factor_name=factor.name,
    )
    max_n_obs = max(m.n_obs for m in metrics_list) if metrics_list else 0
    reasons.append(
        Reason(
            code="min_observations",
            passed=max_n_obs >= cfg.min_observations,
            observed=float(max_n_obs),
            threshold=float(cfg.min_observations),
        )
    )
    if max_n_obs < cfg.min_observations:
        return PromotionDecision(
            factor_name=factor.name,
            verdict="reject",
            reasons=reasons,
            best_horizon=-1,
            best_ic=float("nan"),
            best_ic_ir=float("nan"),
            oos_consistency=float("nan"),
            n_obs=max_n_obs,
        )

    # ------------------------------------------------------------------
    # Find best horizon by |HAC t-stat| (Newey-West corrected),
    # among horizons that would pass the hit-rate gate.
    # We use |t_hac| because that is the statistic fed to FDR.
    # IC-IR (= mean/std, pre-HAC) is NOT used for horizon selection —
    # it is inflated by ~sqrt(H) for H > 1 due to overlapping labels.
    # ------------------------------------------------------------------
    def _safe_abs_tstat(m) -> float:
        t = m.ic_tstat  # HAC corrected
        return abs(t) if not math.isnan(t) else 0.0

    def _hr_lb_passes(m) -> bool:
        """True if hit-rate gate would pass (or is not_applicable) for this metrics row."""
        abs_ic_val = abs(m.ic_pearson) if not math.isnan(m.ic_pearson) else 0.0
        is_directional = abs_ic_val >= 0.01
        if not is_directional:
            return True  # not_applicable -> passes
        lb = m.hit_rate_wilson_lb
        return (not math.isnan(lb)) and lb >= cfg.hit_rate_wilson_lb

    # Prefer horizons that pass hr_lb, then best |HAC t-stat| within that set.
    # Fall back to all horizons if none pass hr_lb (avoids excluding all candidates).
    passing_hr = [m for m in metrics_list if _hr_lb_passes(m)]
    candidates = passing_hr if passing_hr else metrics_list
    best_m = max(candidates, key=_safe_abs_tstat)

    best_ic = best_m.ic_pearson
    best_ic_ir = best_m.ic_ir
    best_h = best_m.horizon
    best_n_obs = best_m.n_obs

    # ------------------------------------------------------------------
    # Gate 3: Minimum |IC|
    # ------------------------------------------------------------------
    abs_ic = abs(best_ic) if not math.isnan(best_ic) else 0.0
    reasons.append(
        Reason(
            code="min_abs_ic",
            passed=abs_ic >= cfg.min_abs_ic,
            observed=abs_ic,
            threshold=cfg.min_abs_ic,
        )
    )

    # ------------------------------------------------------------------
    # Gate 4: Minimum |IC-IR|
    # ------------------------------------------------------------------
    abs_ic_ir = abs(best_ic_ir) if not math.isnan(best_ic_ir) else 0.0
    reasons.append(
        Reason(
            code="min_ic_ir",
            passed=abs_ic_ir >= cfg.min_ic_ir,
            observed=abs_ic_ir,
            threshold=cfg.min_ic_ir,
        )
    )

    # ------------------------------------------------------------------
    # Gate 5: Hit rate Wilson lower bound (directional factors only)
    # ------------------------------------------------------------------
    hr_lb = best_m.hit_rate_wilson_lb
    # Skip if IC is near zero (factor is not directional)
    is_directional = abs_ic >= 0.01
    if is_directional:
        hr_pass = (not math.isnan(hr_lb)) and hr_lb >= cfg.hit_rate_wilson_lb
        reasons.append(
            Reason(
                code="hit_rate_wilson_lb",
                passed=hr_pass,
                observed=hr_lb if not math.isnan(hr_lb) else 0.0,
                threshold=cfg.hit_rate_wilson_lb,
            )
        )
    else:
        reasons.append(
            Reason(
                code="hit_rate_wilson_lb",
                passed=True,
                observed="n/a",
                threshold=cfg.hit_rate_wilson_lb,
                note="not_applicable: factor IC near zero, directional test skipped",
            )
        )
        hr_pass = True

    # ------------------------------------------------------------------
    # Gate 6: Turnover ceiling
    # ------------------------------------------------------------------
    to = best_m.turnover
    to_pass = (not math.isnan(to)) and to <= cfg.max_turnover
    reasons.append(
        Reason(
            code="max_turnover",
            passed=to_pass,
            observed=to if not math.isnan(to) else float("inf"),
            threshold=cfg.max_turnover,
        )
    )

    # ------------------------------------------------------------------
    # Gate 7: OOS consistency (walk_forward or cpcv)
    # ------------------------------------------------------------------
    if cfg.cv_method == "cpcv":
        cv_splitter: PurgedWalkForward | CPurgedCV = CPurgedCV(
            n_groups=cfg.n_cpcv_groups,
            k_test=cfg.k_cpcv_test,
            embargo_days=cfg.embargo_days,
            label_horizon=max(cfg.horizons),
        )
        wf_results = evaluate_cpcv(factor, df, cv_splitter, cfg.horizons)
        cv_label = f"CPCV splits: C({cfg.n_cpcv_groups},{cfg.k_cpcv_test})"
    else:
        cv_splitter = PurgedWalkForward(
            n_splits=cfg.n_wf_splits,
            embargo_days=cfg.embargo_days,
            label_horizon=max(cfg.horizons),
        )
        wf_results = evaluate_walk_forward(factor, df, cv_splitter, cfg.horizons)
        cv_label = f"WF splits: {cfg.n_wf_splits}"
    # Pick the CV result for best_h
    best_wf = next((r for r in wf_results if r.horizon == best_h), None)
    if best_wf is None:
        best_wf = wf_results[0] if wf_results else None

    if best_wf and not math.isnan(best_wf.sign_consistency):
        oos_cons = best_wf.sign_consistency
    else:
        oos_cons = 0.0

    oos_pass = oos_cons >= cfg.oos_consistency_min
    reasons.append(
        Reason(
            code="oos_consistency",
            passed=oos_pass,
            observed=oos_cons,
            threshold=cfg.oos_consistency_min,
            note=f"{cv_label}, method={cfg.cv_method}",
        )
    )

    # ------------------------------------------------------------------
    # Gate 8: FDR survival
    # ------------------------------------------------------------------
    # Convert HAC IC t-stat to approximate two-sided p-value.
    # NOTE: ic_tstat is the Newey-West HAC t-stat (corrected for overlapping labels).
    # Do NOT use ic_tstat_naive here — it is inflated by ~sqrt(H) for H > 1.
    def _tstat_to_pval(t: float, n: int) -> float:
        """Approximate two-sided p-value from t-stat using normal approximation."""
        if math.isnan(t) or n < 2:  # noqa: PLR2004
            return 1.0
        # |t| -> p-value using standard normal CDF
        from .significance import _norm_cdf

        return 2.0 * (1.0 - _norm_cdf(abs(t)))

    p_self = _tstat_to_pval(best_m.ic_tstat, best_n_obs)

    # Multiplicity: if we searched N horizons for this factor and selected the
    # best, we must correct for N tests — one p-value per horizon evaluated.
    # Passing only p_self (m=1) would be the same selection bias this library
    # exists to prevent.  Collect all per-horizon p-values and include them in
    # the BH family so the correction reflects the actual search performed.
    horizon_pvals = [_tstat_to_pval(m.ic_tstat, int(m.n_obs)) for m in metrics_list]
    # Ensure p_self is in the family (it is the last element)
    if p_self not in horizon_pvals:
        horizon_pvals.append(p_self)

    if extra_factors_p_values is not None:
        all_pvals = extra_factors_p_values + horizon_pvals
    else:
        all_pvals = horizon_pvals

    bh_results = benjamini_hochberg(all_pvals, cfg.fdr_q)
    # Find the index of p_self in all_pvals (last occurrence to be safe)
    p_self_idx = len(all_pvals) - len(horizon_pvals) + horizon_pvals.index(p_self)
    survives_fdr = bh_results[p_self_idx]

    reasons.append(
        Reason(
            code="survives_fdr",
            passed=survives_fdr,
            observed=round(p_self, 5),
            threshold=cfg.fdr_q,
            note=f"BH FDR q={cfg.fdr_q}, m={len(all_pvals)} tests ({len(horizon_pvals)} horizons + {len(all_pvals) - len(horizon_pvals)} extra)",
        )
    )

    # ------------------------------------------------------------------
    # Final verdict: all gates must pass
    # ------------------------------------------------------------------
    all_passed = all(r.passed for r in reasons)
    verdict: Literal["promote", "reject"] = "promote" if all_passed else "reject"

    return PromotionDecision(
        factor_name=factor.name,
        verdict=verdict,
        reasons=reasons,
        best_horizon=best_h,
        best_ic=best_ic,
        best_ic_ir=best_ic_ir,
        oos_consistency=oos_cons,
        n_obs=best_n_obs,
    )


# ---------------------------------------------------------------------------
# Convenience: promote a single factor on synthetic data
# ---------------------------------------------------------------------------


def promote_on_synthetic(
    factor: Factor,
    cfg: PromotionConfig | None = None,
    plant_signal: bool = False,
    plant_noise: bool = False,
) -> PromotionDecision:
    """Promote a factor evaluated on synthetic data.

    Parameters
    ----------
    factor:
        Factor instance.
    cfg:
        PromotionConfig.
    plant_signal:
        If True, the synthetic data has an embedded momentum signal.
    plant_noise:
        If True, the synthetic data is pure noise.
    """
    if cfg is None:
        cfg = PromotionConfig()
    df = synthetic_ohlcv(
        n_days=cfg.n_days,
        n_assets=cfg.n_assets,
        seed=cfg.seed,
        plant_signal=plant_signal,
        plant_noise=plant_noise,
    )
    return promote(factor, df, cfg)
