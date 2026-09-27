"""leakage_experiment.py — ablation arms over the real price panel.

Runs the SAME promote() gate four times, changing exactly one control per arm:

  correct           — as-shipped pipeline (purge+embargo, HAC t-stats, real labels)
  no_purge_embargo  — splitter replaced with one that performs NO purge and NO
                      embargo (constructor validation deliberately bypassed)
  shuffled_labels   — forward returns scrambled in time per asset; factor values
                      frozen from the real panel so only labels change
  naive_t           — Newey-West HAC SE replaced by the i.i.d. SE, removing the
                      overlapping-label correction from the significance path

The proof claim this script tests: at least one ablated arm promotes a factor
that the correct pipeline refuses (or, if none does, that is reported as-is).

Outputs: reports/leakage-experiment.json + stdout verdict table.

Usage:
    python scripts/leakage_experiment.py [--db PATH] [--arms all|a,b,c]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

import factorlab.evaluate as _evaluate_mod  # noqa: E402
import factorlab.promote as _promote_mod  # noqa: E402
import prove_on_real_data as pur  # noqa: E402  (shared real-data loader)
from factorlab.cv import PurgedWalkForward, WalkForwardSplit  # noqa: E402
from factorlab.factors import REGISTRY, get_factor  # noqa: E402
from factorlab.promote import PromotionConfig, promote  # noqa: E402

_ARMS = ("correct", "no_purge_embargo", "shuffled_labels", "naive_t")


# ---------------------------------------------------------------------------
# Ablation components (live only in this script — src/ is never weakened)
# ---------------------------------------------------------------------------


class _NoPurgeWalkForward(PurgedWalkForward):
    """Walk-forward splitter with purge and embargo REMOVED (ablation arm a).

    Train = every date strictly before the test window.  Test windows are
    identical to the correct splitter (same chunk boundaries).
    """

    def __init__(self, n_splits: int = 5, embargo_days: int = 0, label_horizon: int = 1) -> None:
        # Deliberately bypass parent validation: the parent refuses
        # embargo_days < label_horizon, which is exactly what we remove here.
        self.n_splits = n_splits
        self.embargo_days = 0
        self.label_horizon = 0

    def split(self, df: pd.DataFrame):  # noqa: ANN201 — mirrors parent generator
        dates = pd.DatetimeIndex(sorted(df["date"].unique()))
        n_dates = len(dates)
        chunk_size = n_dates // (self.n_splits + 1)
        for fold in range(self.n_splits):
            test_start = (fold + 1) * chunk_size
            test_end = test_start + chunk_size if fold < self.n_splits - 1 else n_dates
            test_dates = dates[test_start:test_end]
            train_dates = dates[:test_start]  # no purge, no embargo
            if len(train_dates) == 0 or len(test_dates) == 0:
                continue
            train_idx = np.where(df["date"].isin(train_dates).values)[0]
            test_idx = np.where(df["date"].isin(test_dates).values)[0]
            yield WalkForwardSplit(
                split_id=fold,
                train_idx=train_idx,
                test_idx=test_idx,
                train_dates=(train_dates[0], train_dates[-1]),
                test_dates=(test_dates[0], test_dates[-1]),
                n_purged=0,
                n_embargoed=0,
            )


def _naive_se(ic_arr: np.ndarray, max_lags: int) -> float:
    """i.i.d. standard error — the HAC lag structure deliberately ignored."""
    del max_lags
    t = len(ic_arr)
    if t < 2:  # noqa: PLR2004
        return float("nan")
    xc = ic_arr - ic_arr.mean()
    gamma0 = float(np.dot(xc, xc) / t)
    return math.sqrt(gamma0 / t) if gamma0 >= 0 else float("nan")


def _shuffle_labels(df: pd.DataFrame, seed: int = 12345) -> pd.DataFrame:
    """Scramble close prices through time within each asset (labels only)."""
    rng = np.random.default_rng(seed)
    out = df.copy()
    out["close"] = out.groupby("asset")["close"].transform(
        lambda s: pd.Series(rng.permutation(s.to_numpy()), index=s.index)
    )
    return out


class _FrozenFactor:
    """Wraps a factor so compute() returns values precomputed on the real panel.

    The pipeline then evaluates those frozen values against whatever panel it
    is handed — in the shuffled arm, scrambled forward returns.
    """

    def __init__(self, base, vals: pd.Series) -> None:
        self.base = base
        self._vals = vals
        self.name = base.name
        self.category = getattr(base, "category", "ablation")
        self.description = getattr(base, "description", "")
        self.params = getattr(base, "params", {})
        self.uses_future_data = bool(getattr(base, "uses_future_data", False))

    def compute(self, data: pd.DataFrame) -> pd.Series:
        del data
        return self._vals


# ---------------------------------------------------------------------------
# Decision capture
# ---------------------------------------------------------------------------


def _decide(factor, df, cfg: PromotionConfig) -> dict:
    dec = promote(factor, df, cfg)
    fails = []
    for r in dec.reasons:
        if not r.passed:
            obs = round(r.observed, 4) if isinstance(r.observed, float) else r.observed
            fails.append(f"{r.code}={obs} (thr {r.threshold})")
    return {
        "verdict": dec.verdict,
        "best_horizon": dec.best_horizon,
        "n_obs": dec.n_obs,
        "oos_consistency": round(dec.oos_consistency, 4)
        if not math.isnan(dec.oos_consistency)
        else None,
        "fails": fails,
    }


def run_arm(arm: str, df_real, cfg: PromotionConfig) -> dict[str, dict]:
    """Run every registry factor through promote() under one arm's controls."""
    results: dict[str, dict] = {}

    orig_splitter = _promote_mod.PurgedWalkForward
    orig_se = _evaluate_mod._newey_west_se

    try:
        if arm == "no_purge_embargo":
            _promote_mod.PurgedWalkForward = _NoPurgeWalkForward
        elif arm == "naive_t":
            _evaluate_mod._newey_west_se = _naive_se
        elif arm not in ("correct", "shuffled_labels"):
            raise ValueError(f"unknown arm: {arm}")

        if arm == "shuffled_labels":
            # Factor values frozen from the REAL panel; only labels are scrambled.
            eval_df = _shuffle_labels(df_real)
            frozen = {
                name: _FrozenFactor(get_factor(name), get_factor(name).compute(df_real))
                for name in REGISTRY
            }
        else:
            eval_df = df_real
            frozen = {}

        for name in REGISTRY:
            factor = frozen.get(name, get_factor(name))
            try:
                results[name] = _decide(factor, eval_df, cfg)
            except Exception as exc:  # pragma: no cover — recorded, not hidden
                results[name] = {"verdict": f"ERROR: {exc}", "fails": []}
    finally:
        _promote_mod.PurgedWalkForward = orig_splitter
        _evaluate_mod._newey_west_se = orig_se

    return results


_DB_PATH = Path("prices.sqlite")


def main(argv: list[str] | None = None) -> int:
    global _DB_PATH
    parser = argparse.ArgumentParser(description="Leakage experiment arms on real data.")
    parser.add_argument("--db", default="prices.sqlite", help="Path to prices.sqlite")
    parser.add_argument("--arms", default="all", help="Comma list or 'all'")
    args = parser.parse_args(argv)

    _DB_PATH = Path(args.db)
    if not _DB_PATH.exists():
        print(f"SKIP: {_DB_PATH} not found")
        return 0

    arms = list(_ARMS) if args.arms == "all" else [a.strip() for a in args.arms.split(",")]
    df = pur.load_real_data(_DB_PATH)
    summary = pur.dataset_summary(df, _DB_PATH)
    print(
        f"Dataset: {summary['n_coins']} coins, {summary['n_bars_total']:,} bars, "
        f"{summary['date_range']}"
    )

    cfg = PromotionConfig()
    all_arms: dict[str, dict[str, dict]] = {}
    t0 = time.time()
    for arm in arms:
        print(f"\n=== ARM: {arm} ===")
        res = run_arm(arm, df, cfg)
        all_arms[arm] = res
        for name, r in res.items():
            fails = "; ".join(r["fails"]) if r["fails"] else "-"
            print(f"{name:<18} {r['verdict']:<8} {fails}")

    correct = all_arms.get("correct", {})
    flips: dict[str, list[str]] = {}
    for arm, res in all_arms.items():
        if arm == "correct":
            continue
        flips[arm] = sorted(
            n
            for n, r in res.items()
            if r["verdict"] == "promote" and correct.get(n, {}).get("verdict") != "promote"
        )

    print("\n=== VERDICT MATRIX ===")
    col = f"{'factor':<18}" + "".join(f"{a:>18}" for a in all_arms)
    print(col)
    for name in REGISTRY:
        row = f"{name:<18}"
        for a in all_arms:
            v = all_arms[a][name]["verdict"]
            row += f"{('PROMOTE' if v == 'promote' else v):>18}"
        print(row)

    print("\n=== FLIPS (promoted under ablation, refused by correct pipeline) ===")
    any_flip = False
    for arm, names in flips.items():
        if names:
            any_flip = True
            print(f"{arm}: {', '.join(names)}")
        else:
            print(f"{arm}: none")
    print(f"flip_present: {any_flip}")

    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "command": "python scripts/leakage_experiment.py --db <prices.sqlite> --arms "
        + ",".join(arms),
        "dataset": {
            "n_coins": summary["n_coins"],
            "n_bars_total": summary["n_bars_total"],
            "date_range": summary["date_range"],
        },
        "arms": all_arms,
        "flips": flips,
        "elapsed_s": round(time.time() - t0, 1),
    }
    out = _REPO_ROOT / "reports" / "leakage-experiment.json"
    out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote {out.relative_to(_REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
