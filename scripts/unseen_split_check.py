"""unseen_split_check.py — decision on split k, realised outcome on split k+1.

Walk-forward across the full date range of the real panel.  For each purged
split: run the full promotion gate on the TRAIN window only, then measure what
the selected/refused factors actually did on the NEXT (never-seen) window.

Outcome classification per (factor, split):
  GOOD_PROMOTION   — promoted, and test IC keeps the train sign with |IC| >= 0.02
  FALSE_PROMOTION  — promoted, and the test window contradicts that claim
  MISSED_SIGNAL    — refused, but the test window shows sign-consistent |IC| >= 0.02
  CORRECT_REFUSAL  — refused, and the test window does not vindicate it
  N/A_STRUCTURAL   — rejected before any statistics (lookahead/degenerate)

Outputs: reports/unseen-split.json + stdout tables.

Usage:
    python scripts/unseen_split_check.py [--db PATH] [--n-splits 5]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

import prove_on_real_data as pur  # noqa: E402
from factorlab.cv import PurgedWalkForward  # noqa: E402
from factorlab.evaluate import evaluate_factor  # noqa: E402
from factorlab.factors import REGISTRY, get_factor  # noqa: E402
from factorlab.promote import PromotionConfig, promote  # noqa: E402

MIN_ABS_IC = 0.02  # same floor as PromotionConfig.min_abs_ic


def _realised_ic(factor, df, test_dates, horizon: int) -> tuple[float, int]:
    """Mean cross-sectional IC on the test window at a fixed horizon."""
    vals = factor.compute(df)
    test_vals = vals[vals.index.get_level_values("date").isin(test_dates)]
    if test_vals.empty:
        return float("nan"), 0
    metrics = evaluate_factor(test_vals, df[df["date"].isin(test_dates)], [horizon], factor.name)
    if not metrics:
        return float("nan"), 0
    return float(metrics[0].ic_pearson), int(metrics[0].n_obs)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Unseen-split outcome check on real data.")
    parser.add_argument("--db", default="prices.sqlite")
    parser.add_argument("--n-splits", type=int, default=5)
    args = parser.parse_args(argv)

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"SKIP: {db_path} not found")
        return 0

    df = pur.load_real_data(db_path)
    summary = pur.dataset_summary(df, db_path)
    print(
        f"Dataset: {summary['n_coins']} coins, {summary['n_bars_total']:,} bars, {summary['date_range']}"
    )

    cv = PurgedWalkForward(
        n_splits=args.n_splits,
        embargo_days=20,
        label_horizon=20,
    )
    splits = list(cv.split(df))
    cfg = PromotionConfig()

    rows: list[dict] = []
    boundaries: list[dict] = []
    t0 = time.time()

    for spl in splits:
        train_last = spl.train_dates[1]
        test_first, test_last = spl.test_dates
        train_df = df[df["date"] <= train_last]
        test_dates = set(
            df.loc[(df["date"] >= test_first) & (df["date"] <= test_last), "date"].unique()
        )
        n_train_dates = int(train_df["date"].nunique())
        n_test_dates = len(test_dates)
        boundaries.append(
            {
                "split": spl.split_id,
                "train": f"{train_df['date'].min().date()}..{train_last.date()}",
                "train_dates": n_train_dates,
                "test": f"{test_first.date()}..{test_last.date()}",
                "test_dates": n_test_dates,
                "n_purged": spl.n_purged,
                "n_embargoed": spl.n_embargoed,
            }
        )

        for name in REGISTRY:
            factor = get_factor(name)
            dec = promote(factor, train_df, cfg)

            if dec.best_horizon <= 0:  # structural / degenerate rejection
                rows.append(
                    {
                        "split": spl.split_id,
                        "factor": name,
                        "train_verdict": dec.verdict,
                        "outcome": "N/A_STRUCTURAL",
                    }
                )
                continue

            ic_test, n_test_obs = _realised_ic(factor, df, test_dates, dec.best_horizon)
            ic_train = dec.best_ic
            sign_match = (
                (not math.isnan(ic_test)) and ic_train != 0 and (ic_test > 0) == (ic_train > 0)
            )
            vindicated = sign_match and abs(ic_test) >= MIN_ABS_IC

            if dec.verdict == "promote":
                outcome = "GOOD_PROMOTION" if vindicated else "FALSE_PROMOTION"
            else:
                outcome = "MISSED_SIGNAL" if vindicated else "CORRECT_REFUSAL"

            rows.append(
                {
                    "split": spl.split_id,
                    "factor": name,
                    "train_verdict": dec.verdict,
                    "horizon": dec.best_horizon,
                    "ic_train": round(ic_train, 4),
                    "ic_test": None if math.isnan(ic_test) else round(ic_test, 4),
                    "n_train": dec.n_obs,
                    "n_test_obs": n_test_obs,
                    "outcome": outcome,
                }
            )

    # ------------------------------------------------------------------
    # Print raw tables
    # ------------------------------------------------------------------
    print("\n=== SPLIT BOUNDARIES (purged walk-forward, embargo=20d, horizon=20d) ===")
    print(
        f"{'k':>2} {'train window':<26} {'n':>5} {'test window':<26} {'n':>4} {'purged':>6} {'embo':>4}"
    )
    for b in boundaries:
        print(
            f"{b['split']:>2} {b['train']:<26} {b['train_dates']:>5} {b['test']:<26} "
            f"{b['test_dates']:>4} {b['n_purged']:>6} {b['n_embargoed']:>4}"
        )

    print("\n=== PER-SPLIT OUTCOMES ===")
    print(
        f"{'k':>2} {'factor':<18} {'train':<8} {'h':>2} {'IC_tr':>7} {'IC_te':>7} {'n_te':>5} outcome"
    )
    for r in rows:
        if r["outcome"] == "N/A_STRUCTURAL":
            print(
                f"{r['split']:>2} {r['factor']:<18} {r['train_verdict']:<8} {'-':>2} {'-':>7} {'-':>7} {'-':>5} {r['outcome']}"
            )
        else:
            print(
                f"{r['split']:>2} {r['factor']:<18} {r['train_verdict']:<8} {r['horizon']:>2} "
                f"{r['ic_train']:>7.4f} {r['ic_test']:>7.4f} {r['n_test_obs']:>5} {r['outcome']}"
            )

    counts: dict[str, int] = {}
    for r in rows:
        counts[r["outcome"]] = counts.get(r["outcome"], 0) + 1
    n_promoted = sum(1 for r in rows if r["train_verdict"] == "promote")
    n_decided = sum(1 for r in rows if r["outcome"] != "N/A_STRUCTURAL")
    print("\n=== COUNTS ===")
    print(
        f"splits: {len(splits)} | factors: {len(REGISTRY)} | decisions: {n_decided} "
        f"(+{counts.get('N/A_STRUCTURAL', 0)} structural)"
    )
    for k in (
        "GOOD_PROMOTION",
        "FALSE_PROMOTION",
        "MISSED_SIGNAL",
        "CORRECT_REFUSAL",
        "N/A_STRUCTURAL",
    ):
        if k in counts:
            print(f"{k}: {counts[k]}")
    print(f"promoted decisions: {n_promoted}")

    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "command": f"python scripts/unseen_split_check.py --db <prices.sqlite> --n-splits {args.n_splits}",
        "dataset": {
            "n_coins": summary["n_coins"],
            "n_bars_total": summary["n_bars_total"],
            "date_range": summary["date_range"],
        },
        "boundaries": boundaries,
        "counts": counts,
        "n_promoted": n_promoted,
        "n_decided": n_decided,
        "rows": rows,
        "elapsed_s": round(time.time() - t0, 1),
    }
    out = _REPO_ROOT / "reports" / "unseen-split.json"
    out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote {out.relative_to(_REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
