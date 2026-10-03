"""adversarial_attacks.py — attack the promotion gate on real data.

Three attacks, each an attempt to force a wrong answer out of the pipeline:

  A1 seed_scan        — promote() 100 seeded known-noise factors (persistent
                        AR(1) noise, low turnover so only the statistical gates
                        can stop them).  A promotion here is a false positive.
  A2 fdr_family       — make the FDR step pass a factor the family rejects:
                        (i) default single-test mode, (ii) the real 13-factor
                        family, (iii) a fabricated family of tiny p-values.
  A3 config_relax     — relax every threshold and confirm noise promotes,
                        showing gate integrity depends on the shipped config.

Output is raw stdout (pasted into docs/ADVERSARIAL_REVIEW.md) plus
reports/adversarial-attacks.json.

Usage:
    python scripts/adversarial_attacks.py [--db PATH] [--seeds 100]
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

import prove_on_real_data as pur  # noqa: E402
from factorlab.factors import REGISTRY, get_factor  # noqa: E402
from factorlab.factors.base import Factor  # noqa: E402
from factorlab.promote import PromotionConfig, promote  # noqa: E402
from factorlab.significance import _norm_cdf  # noqa: E402

# ---------------------------------------------------------------------------
# A1: known-noise factor factory
# ---------------------------------------------------------------------------


class PersistentNoise(Factor):
    """Pure noise with an AR(1) persistence of 0.95 — deliberately low turnover,
    so the turnover gate cannot stop it and only the statistics can."""

    name = "persistent_noise"
    category = "attack"
    description = "AR(1) noise, phi=0.95, seeded per instance"
    params: dict = {}
    uses_future_data = False

    def __init__(self, seed: int) -> None:
        self.seed = seed

    def compute(self, df: pd.DataFrame) -> pd.Series:
        rng = np.random.default_rng(self.seed)
        idx = pd.MultiIndex.from_frame(df[["date", "asset"]])
        n_assets = df["asset"].nunique()
        n_dates = df["date"].nunique()
        phi = 0.95
        # One AR(1) chain per asset, evaluated in date order.
        chains = np.zeros((n_dates, n_assets))
        for a in range(n_assets):
            x = 0.0
            eps = rng.standard_normal(n_dates)
            for t in range(n_dates):
                x = phi * x + math.sqrt(1 - phi * phi) * eps[t]
                chains[t, a] = x
        asset_order = list(pd.unique(df["asset"]))
        wide = pd.DataFrame(chains, columns=asset_order)
        wide.index = sorted(pd.unique(df["date"]))
        vals = wide.stack()
        vals.index.names = ["date", "asset"]
        return vals.reindex(idx)


def _t_to_p(t: float, n: int) -> float:
    if math.isnan(t) or n < 2:
        return 1.0
    return 2.0 * (1.0 - _norm_cdf(abs(t)))


def attack_seed_scan(df, cfg: PromotionConfig, n_seeds: int) -> dict:
    promoted: list[dict] = []
    fail_histogram: dict[str, int] = {}
    closest: list[tuple[int, str, list[str]]] = []
    per_seed: list[dict] = []
    for seed in range(n_seeds):
        factor = PersistentNoise(seed)
        dec = promote(factor, df, cfg)
        fails = [r.code for r in dec.reasons if not r.passed]
        p_self = next(
            (float(r.observed) for r in dec.reasons if r.code == "survives_fdr"), float("nan")
        )
        for code in fails:
            fail_histogram[code] = fail_histogram.get(code, 0) + 1
        closest.append((len(fails), f"seed={seed}", fails))
        per_seed.append({"seed": seed, "p": p_self, "verdict": dec.verdict})
        if dec.verdict == "promote":
            promoted.append(
                {
                    "seed": seed,
                    "ic": round(dec.best_ic, 4),
                    "ic_ir": round(dec.best_ic_ir, 4),
                    "p": p_self,
                }
            )
    closest.sort(key=lambda x: x[0])

    # Post-hoc multiplicity control: what the FDR step should have done if the
    # 100 attempts were treated as one family of tests (q=0.15).
    from factorlab.significance import benjamini_hochberg

    pvals = [rec["p"] for rec in per_seed]
    bh_mask = benjamini_hochberg(pvals, q=0.15)
    bh_survivors = [per_seed[i] for i, keep in enumerate(bh_mask) if keep]

    return {
        "n_seeds": n_seeds,
        "n_promoted": len(promoted),
        "promoted": promoted,
        "fail_histogram": fail_histogram,
        "closest": [{"n_fails": n, "id": i, "fails": f} for n, i, f in closest[:5]],
        "per_seed": per_seed,
        "bh_over_100_attempts": {
            "q": 0.15,
            "m": n_seeds,
            "n_survivors": len(bh_survivors),
            "survivors": bh_survivors,
            "promoted_that_survive_bh": [
                p["seed"] for p in promoted if p["seed"] in {s["seed"] for s in bh_survivors}
            ],
        },
    }


# ---------------------------------------------------------------------------
# A2: FDR step manipulation
# ---------------------------------------------------------------------------


def _family_p_values(df) -> list[float]:
    """HAC p-value per registry factor at its best horizon (CLI-style family)."""
    from factorlab.evaluate import evaluate_factor

    pvals = []
    for name in REGISTRY:
        vals = get_factor(name).compute(df)
        metrics = evaluate_factor(vals, df, [1, 5, 20], name)
        best = max(metrics, key=lambda m: abs(m.ic_tstat) if not math.isnan(m.ic_tstat) else 0.0)
        pvals.append(_t_to_p(best.ic_tstat, int(best.n_obs)))
    return pvals


def attack_fdr_family(df, cfg: PromotionConfig, target: str = "amihud_illiq_20") -> dict:
    factor = get_factor(target)
    family = _family_p_values(df)

    def _fdr_reason(dec) -> dict:
        for r in dec.reasons:
            if r.code == "survives_fdr":
                return {"passed": r.passed, "observed": r.observed, "note": r.note}
        return {"passed": None}

    out: dict = {"target": target, "family_p_values": [round(p, 5) for p in family]}

    dec_default = promote(factor, df, cfg)
    out["m1_default"] = {**_fdr_reason(dec_default), "verdict": dec_default.verdict}

    target_idx = list(REGISTRY).index(target)
    real_family = [p for i, p in enumerate(family) if i != target_idx]
    dec_real = promote(factor, df, cfg, extra_factors_p_values=real_family)
    out["real_family_m13"] = {**_fdr_reason(dec_real), "verdict": dec_real.verdict}

    fabricated = [1e-8] * 12
    dec_fake = promote(factor, df, cfg, extra_factors_p_values=fabricated)
    out["fabricated_family"] = {**_fdr_reason(dec_fake), "verdict": dec_fake.verdict}
    return out


# ---------------------------------------------------------------------------
# A3: relax every shipped threshold
# ---------------------------------------------------------------------------


def attack_config_relax(df) -> dict:
    loose = PromotionConfig(
        min_observations=1,
        min_ic_ir=0.0,
        min_abs_ic=0.0,
        hit_rate_wilson_lb=0.0,
        max_turnover=99.0,
        oos_consistency_min=0.0,
        fdr_q=1.0,
        coverage_min=0.0,
    )
    dec = promote(get_factor("noise_control"), df, loose)
    return {
        "factor": "noise_control",
        "verdict": dec.verdict,
        "failing_gates": [r.code for r in dec.reasons if not r.passed],
        "config": "all thresholds relaxed",
    }


# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Adversarial attacks on the gate (real data).")
    parser.add_argument("--db", default="prices.sqlite")
    parser.add_argument("--seeds", type=int, default=100)
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
    cfg = PromotionConfig()
    results: dict = {}

    print(f"\n=== A1: seed scan — {args.seeds} known-noise factors through promote() ===")
    t0 = time.time()
    results["A1_seed_scan"] = attack_seed_scan(df, cfg, args.seeds)
    a1 = results["A1_seed_scan"]
    print(f"seeds run: {a1['n_seeds']} | promoted: {a1['n_promoted']}")
    if a1["promoted"]:
        print(f"PROMOTED (false positives): {a1['promoted']}")
    print("gate-failure histogram (how noise is stopped):")
    for code, n in sorted(a1["fail_histogram"].items(), key=lambda kv: -kv[1]):
        print(f"  {code}: {n}/{a1['n_seeds']}")
    print("closest calls (fewest failing gates):")
    for c in a1["closest"]:
        print(f"  {c['id']}: {c['n_fails']} fails -> {', '.join(c['fails'])}")
    bh = a1["bh_over_100_attempts"]
    print(
        f"post-hoc BH across all {bh['m']} attempts (q={bh['q']}): "
        f"{bh['n_survivors']} survive, promoted that survive: {bh['promoted_that_survive_bh']}"
    )

    print("\n=== A2: FDR step — can it pass a factor the family rejects? ===")
    results["A2_fdr_family"] = attack_fdr_family(df, cfg)
    a2 = results["A2_fdr_family"]
    print(f"target: {a2['target']}")
    print(f"family p-values (m=13): {a2['family_p_values']}")
    for key in ("m1_default", "real_family_m13", "fabricated_family"):
        r = a2[key]
        print(f"  {key:<20} survives_fdr={r['passed']} (p={r['observed']}) | {r['note']}")

    print("\n=== A3: relax every shipped threshold, then promote pure noise ===")
    results["A3_config_relax"] = attack_config_relax(df)
    a3 = results["A3_config_relax"]
    print(
        f"{a3['factor']} with {a3['config']}: {a3['verdict']} (failing: {a3['failing_gates'] or 'none'})"
    )

    print(f"\nelapsed: {time.time() - t0:.1f}s")
    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "command": f"python scripts/adversarial_attacks.py --db <prices.sqlite> --seeds {args.seeds}",
        "dataset": {
            "n_coins": summary["n_coins"],
            "n_bars_total": summary["n_bars_total"],
            "date_range": summary["date_range"],
        },
        "attacks": results,
    }
    out = _REPO_ROOT / "reports" / "adversarial-attacks.json"
    out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {out.relative_to(_REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
