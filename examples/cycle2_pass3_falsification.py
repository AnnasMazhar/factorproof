"""Cycle 2 pass 3 falsification experiments — real-world applicability.

Runs fully offline against the installed ``factorlab`` package. Each experiment
maps to an open item in ``docs/RESEARCH.md``:

* C2-1 — does the HAC t-stat separate noise from signal at H=20?
* C2-2 — does CPCV reveal false OOS consistency in the walk-forward path?
* C2-3 — is the HAC t-stat sensitive to a mid-sample structural break?
* C2-4 — does BH FDR use nominal m, with no m_eff override?
* CAL  — permutation-null threshold calibration (closes the threshold question
         in docs/RESEARCH.md section 7.4)

Usage:
    .venv/bin/python examples/cycle2_pass3_falsification.py
"""

from __future__ import annotations

import inspect
import math

import numpy as np
import pandas as pd
from factorlab.cv import CPurgedCV, PurgedWalkForward, evaluate_walk_forward
from factorlab.data import synthetic_ohlcv
from factorlab.evaluate import evaluate_factor, forward_returns, information_coefficient
from factorlab.factors import REGISTRY
from factorlab.promote import PromotionConfig, promote
from factorlab.significance import _norm_cdf, benjamini_hochberg

PANEL_ARGS = dict(n_days=1500, n_assets=12, seed=7)


def _t_to_p(t: float, n: int) -> float:
    """Two-sided normal-approximation p-value from a t-statistic."""
    if math.isnan(t) or n < 2:  # noqa: PLR0
        return 1.0
    return 2.0 * (1.0 - _norm_cdf(abs(t)))


def section(title: str) -> None:
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def experiment_c2_1() -> None:
    """HAC t-stat at H=20: noise rejected, planted signal kept."""
    section("C2-1: HAC t-stat at H=20 (noise_control vs mom_20)")
    sig = synthetic_ohlcv(plant_signal=True, **PANEL_ARGS)
    nse = synthetic_ohlcv(plant_noise=True, **PANEL_ARGS)
    cfg20 = PromotionConfig(horizons=[20])
    for name, panel in (("noise_control", nse), ("mom_20", sig)):
        factor = REGISTRY[name]
        vals = factor.compute(panel)
        m = evaluate_factor(vals, panel, [20], name)[0]
        d = promote(factor, panel, cfg20)
        failed = [r.code for r in d.reasons if not r.passed]
        print(
            f"{name:<15} H=20: ic={m.ic_pearson:+.4f} naive_t={m.ic_tstat_naive:+7.2f} "
            f"hac_t={m.ic_tstat:+7.2f} n={m.n_obs} verdict={d.verdict.upper()} "
            f"failed_gates={failed}"
        )
        d_default = promote(factor, panel, PromotionConfig())
        print(
            f"{'':<15} default cfg (h=1,5,20): verdict={d_default.verdict.upper()} "
            f"best_horizon={d_default.best_horizon} best_ic={d_default.best_ic:+.4f} "
            f"failed_gates={[r.code for r in d_default.reasons if not r.passed]}"
        )


def _cpcv_consistency(factor, panel: pd.DataFrame, horizon: int) -> tuple[list[float], float]:
    """Mean IC per CPCV path and sign consistency across those paths."""
    cv = CPurgedCV(n_groups=6, k_test=2, embargo_days=20, label_horizon=horizon)
    fvals = factor.compute(panel)
    ics: list[float] = []
    for spl in cv.split(panel):
        test_df = panel.iloc[spl.test_idx]
        dates = test_df["date"].unique()
        tf = fvals[fvals.index.get_level_values("date").isin(dates)]
        if tf.empty:
            continue
        ics.append(float(evaluate_factor(tf, test_df, [horizon], factor.name)[0].ic_pearson))
    mean_ic = float(np.mean(ics))
    cons = float(np.mean(np.sign(ics) == np.sign(mean_ic))) if mean_ic != 0 else float("nan")
    return ics, cons


def experiment_c2_2() -> None:
    """Walk-forward vs CPCV sign consistency on a marginal factor."""
    section("C2-2: walk-forward vs CPCV sign consistency (H=5)")
    sig = synthetic_ohlcv(plant_signal=True, **PANEL_ARGS)
    splitter = PurgedWalkForward(n_splits=5, embargo_days=20, label_horizon=20)
    for name in ("mom_20", "rsi_14"):
        factor = REGISTRY[name]
        wf = {r.horizon: r for r in evaluate_walk_forward(factor, sig, splitter, [5])}[5]
        cpcv_ics, cpcv_cons = _cpcv_consistency(factor, sig, 5)
        n_neg_wf = sum(1 for ic in wf.per_split_ic if ic < 0)
        n_neg_cv = sum(1 for ic in cpcv_ics if ic < 0)
        print(f"{name}:")
        print(
            f"  walk-forward  : per-split IC {[round(x, 4) for x in wf.per_split_ic]} "
            f"-> consistency {wf.sign_consistency:.3f} ({n_neg_wf}/{wf.n_splits} negative)"
        )
        print(
            f"  CPCV (6,2)    : per-path IC {[round(x, 4) for x in cpcv_ics]}"
            f"\n                  -> consistency {cpcv_cons:.3f} ({n_neg_cv}/{len(cpcv_ics)} negative)"
        )


def _break_panel(panel: pd.DataFrame) -> pd.DataFrame:
    """Rebuild the panel with AR(1) returns whose rho switches at the midpoint.

    This is the C2-3 intervention from docs/RESEARCH.md: rho = +0.15 before the
    break (the planted-signal strength) and rho = -0.05 after it, so the momentum
    signal reverses mid-sample. OHLCV columns are reconstructed from the returns;
    only ``close`` carries the tested structure.
    """
    rng = np.random.default_rng(7)
    frames = []
    for asset, grp in panel.groupby("asset", sort=False):
        g = grp.sort_values("date")
        n = len(g)
        mid = n // 2
        eps = rng.normal(0.0, 0.01, n)
        r = np.zeros(n)
        for t in range(1, n):
            phi = 0.15 if t < mid else -0.05
            r[t] = phi * r[t - 1] + eps[t]
        close = 100.0 * np.exp(np.cumsum(r))
        open_ = np.concatenate([[close[0]], close[:-1]])
        frames.append(
            pd.DataFrame(
                {
                    "date": g["date"].to_numpy(),
                    "asset": asset,
                    "open": open_,
                    "high": np.maximum(open_, close) * 1.001,
                    "low": np.minimum(open_, close) * 0.999,
                    "close": close,
                    "volume": rng.lognormal(10.0, 0.5, n),
                }
            )
        )
    return pd.concat(frames, ignore_index=True).sort_values(["asset", "date"])


def experiment_c2_3() -> None:
    """HAC t-stat under a mid-sample structural break."""
    section("C2-3: structural break at T/2 (rho +0.15 -> -0.15)")
    sig = synthetic_ohlcv(plant_signal=True, **PANEL_ARGS)
    brk = _break_panel(sig)
    factor = REGISTRY["mom_20"]
    vals = factor.compute(brk)
    cut = sorted(brk["date"].unique())[len(brk["date"].unique()) // 2]

    m_full = evaluate_factor(vals, brk, [5], "mom_20")[0]
    pre_mask = vals.index.get_level_values("date") < cut
    m_pre = evaluate_factor(vals[pre_mask], brk[brk["date"] < cut], [5], "mom_20")[0]
    m_post = evaluate_factor(vals[~pre_mask], brk[brk["date"] >= cut], [5], "mom_20")[0]
    print(f"break date     : {pd.Timestamp(cut).date()}")
    print(f"pre-break  IC  : {m_pre.ic_pearson:+.4f}  hac_t={m_pre.ic_tstat:+.2f}")
    print(f"post-break IC  : {m_post.ic_pearson:+.4f}  hac_t={m_post.ic_tstat:+.2f}")
    print(f"full series IC : {m_full.ic_pearson:+.4f}  hac_t={m_full.ic_tstat:+.2f}")
    d = promote(factor, brk, PromotionConfig())
    oos = next(r for r in d.reasons if r.code == "oos_consistency")
    print(
        f"promote verdict: {d.verdict.upper()}  oos_consistency={oos.observed:.3f} "
        f"(threshold {oos.threshold})  failed={[r.code for r in d.reasons if not r.passed]}"
    )


def experiment_c2_4() -> None:
    """BH FDR on 13 near-identical noise factors; nominal m, no override."""
    section("C2-4: BH FDR family is nominal m with no m_eff override")
    print("benjamini_hochberg signature:", inspect.signature(benjamini_hochberg))
    print("promote signature           :", inspect.signature(promote))
    assert "m_eff" not in inspect.signature(benjamini_hochberg).parameters
    assert "m_eff" not in inspect.signature(promote).parameters
    print("no m_eff parameter exists on either public entry point -> nominal m by construction")

    nse = synthetic_ohlcv(plant_noise=True, **PANEL_ARGS)
    wide = nse.pivot(index="date", columns="asset", values="close")
    pvals = []
    for k in range(20, 33):  # mom_20 .. mom_32, pairwise IC corr ~1.0
        fv = wide.pct_change(k).stack(future_stack=True)
        fv.index.names = ["date", "asset"]
        m = evaluate_factor(fv, nse, [5], f"mom_{k}")[0]
        pvals.append(_t_to_p(m.ic_tstat, m.n_obs))
    print("13 near-duplicate p-values :", [round(p, 4) for p in pvals])
    rejected = benjamini_hochberg(pvals, q=0.15)
    print(f"BH at q=0.15, m={len(pvals)}: discoveries = {sum(rejected)} (expected 0 on noise)")

    # Show the threshold the pipeline actually applies at each rank.
    order = sorted(pvals)
    ranks = [(i, p, (i / len(pvals)) * 0.15) for i, p in enumerate(order, start=1)]
    print("rank thresholds (i/m)*q with m=13:", [(i, round(t, 4)) for i, _, t in ranks])
    any_pass = any(p <= t for _, p, t in ranks)
    print(f"any p_(i) <= (i/13)*q ? {any_pass} -> all 13 kept as nulls (conservative direction)")

    # Pipeline path: promote() families are built from the screened family only.
    cfg = PromotionConfig()
    d = promote(REGISTRY["noise_control"], nse, cfg, extra_factors_p_values=pvals)
    fdr = next(r for r in d.reasons if r.code == "survives_fdr")
    print(f"promote(noise_control, family=13): {fdr.note}  passed={fdr.passed}")


def experiment_calibration() -> None:
    """Permutation-null IC floor: the v0.2 calibrate procedure, run today."""
    section("CAL: permutation-null IC floor (closes RESEARCH.md 7.4)")
    sig = synthetic_ohlcv(plant_signal=True, **PANEL_ARGS)
    factor = REGISTRY["mom_20"]
    vals = factor.compute(sig)
    fwd = forward_returns(sig, [5])[5]
    observed = information_coefficient(vals, fwd, "pearson", 5)[0]

    f_wide = vals.unstack("asset")
    r_wide = fwd.pivot(index="date", columns="asset", values="fwd_ret")
    f_wide, r_wide = f_wide.align(r_wide, join="inner")
    A = f_wide.to_numpy(dtype=float)
    B = r_wide.to_numpy(dtype=float)

    def rowwise_ic(Am: np.ndarray, Bm: np.ndarray) -> np.ndarray:
        mask = ~np.isnan(Am) & ~np.isnan(Bm)
        Af = np.where(mask, Am, 0.0)
        Bf = np.where(mask, Bm, 0.0)
        na = mask.sum(axis=1)
        valid = na >= 3  # noqa: PLR2004
        ma = np.where(valid, Af.sum(axis=1) / np.maximum(na, 1), 0.0)
        mb = np.where(valid, Bf.sum(axis=1) / np.maximum(na, 1), 0.0)
        ac = Af - ma[:, None]
        bc = Bf - mb[:, None]
        ac = np.where(mask, ac, 0.0)
        bc = np.where(mask, bc, 0.0)
        num = (ac * bc).sum(axis=1)
        den = np.sqrt((ac**2).sum(axis=1) * (bc**2).sum(axis=1))
        out = np.full(Am.shape[0], np.nan)
        out[valid] = num[valid] / den[valid]
        return out

    sanity = float(np.nanmean(rowwise_ic(A, B)))
    rng = np.random.default_rng(0)
    n_boot = 500
    null_ics = np.empty(n_boot)
    for b in range(n_boot):
        idx = np.argsort(rng.random(B.shape), axis=1)
        Bp = np.take_along_axis(B, idx, axis=1)
        null_ics[b] = np.nanmean(rowwise_ic(A, Bp))
    floor = float(np.quantile(np.abs(null_ics), 0.95))
    print(
        f"mom_20 observed |mean IC| at H=5 : {abs(observed):.4f}  (rowwise check {abs(sanity):.4f})"
    )
    print(f"permutation null: {n_boot} cross-sectional shuffles, seed=0")
    print(f"null mean IC = {np.nanmean(null_ics):+.5f}, 95th pct of |null IC| = {floor:.4f}")
    print(
        f"default min_abs_ic = 0.0200  -> observed signal is "
        f"{'ABOVE' if abs(observed) > floor else 'BELOW'} the 95% noise floor"
    )
    print(
        "decision rule: set min_abs_ic to the 95th percentile of the permutation null "
        "on the researcher's own panel (floor above), not to a universal constant"
    )


def main() -> None:
    experiment_c2_1()
    experiment_c2_2()
    experiment_c2_3()
    experiment_c2_4()
    experiment_calibration()


if __name__ == "__main__":
    main()
