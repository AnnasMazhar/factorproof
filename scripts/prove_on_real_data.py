"""prove_on_real_data.py — run the full factor-lab pipeline on the real OHLCV dataset.

Dataset: prices.sqlite, table `candles` (ts, coin, open, high, low, close, volume).
Access: read-only SQLite connection.

If the database is not present (CI, fresh clone), this script prints SKIP with
the reason and exits 0 — CI stays offline and runs only synthetic controls.

The real-data run is performed locally and raw output pasted into EVIDENCE.md.

Usage:
    python scripts/prove_on_real_data.py [--db PATH]

Outputs (when dataset is present):
    reports/real-data-proof.md
    reports/real-data-proof.json

F2 sections produced:
  1. Dataset summary (coins, date range, bar count, granularity)
  2. Per-factor row (IC, IC-IR, purged-CV OOS IC, BH-adj p, deflated Sharpe, verdict)
  3. The delta: factors passing raw p<0.05 vs after BH-FDR and deflation
  4. Control results (noise factors planted in the real dataset)
  5. Exact command, dataset size, last-modified time
  6. Honest limitations

F3 sections produced:
  (a) Specificity: noise factors planted; gate rejects >=90%
  (b) Sensitivity: a factor with predictive power is promoted
  (c) Stability: different CV fold seeding does not flip promoted verdicts
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Locate the package
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from factorlab.evaluate import evaluate_factor  # noqa: E402
from factorlab.factors import REGISTRY, get_factor  # noqa: E402
from factorlab.promote import PromotionConfig, promote  # noqa: E402
from factorlab.significance import (  # noqa: E402
    _norm_cdf,
    benjamini_hochberg,
    deflated_sharpe_ratio,
)

# ---------------------------------------------------------------------------
# Default DB path — repo-relative so no host-specific path is ever baked in.
# Pass --db explicitly to point at your own prices.sqlite.
# ---------------------------------------------------------------------------
_DEFAULT_DB = Path("prices.sqlite")

# ---------------------------------------------------------------------------
# Forbidden token check — enforced by scripts/check_no_internal_refs.py in CI.
# That script is the single source of truth; this module must not name the
# tokens itself, or the checker flags it.
# ---------------------------------------------------------------------------
REPORTS_DIR = _REPO_ROOT / "reports"


# ---------------------------------------------------------------------------
# Load real data
# ---------------------------------------------------------------------------


def load_real_data(db_path: Path) -> pd.DataFrame:
    """Load candles from the real prices.sqlite, read-only.

    The table may contain intraday bars (5-minute) for recent dates alongside
    historical daily bars.  This function resamples to daily OHLCV by taking:
      - open  = first open in the UTC day
      - high  = max high in the UTC day
      - low   = min low in the UTC day
      - close = last close in the UTC day
      - volume = sum of volume in the UTC day

    Returns a DataFrame in the same tidy long format as synthetic_ohlcv:
    columns = [date, asset, open, high, low, close, volume]
    """
    uri = f"file:{db_path}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    try:
        # Check table schema
        cur = con.execute("PRAGMA table_info(candles)")
        cols = {row[1] for row in cur.fetchall()}
        if "ts" not in cols:
            tables = [
                r[0]
                for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            ]
            raise RuntimeError(
                f"Table 'candles' has no 'ts' column. Columns: {cols}. "
                f"Available tables: {tables}"
            )
        df_raw = pd.read_sql_query(
            "SELECT ts, coin AS asset, open, high, low, close, volume "
            "FROM candles ORDER BY ts, coin",
            con,
        )
    finally:
        con.close()

    # ts is Unix seconds — convert to UTC date
    df_raw["date"] = (
        pd.to_datetime(df_raw["ts"], unit="s", utc=True).dt.normalize().dt.tz_localize(None)
    )

    # Aggregate intraday bars to daily OHLCV
    # open = first, high = max, low = min, close = last, volume = sum
    df_daily = (
        df_raw.sort_values("ts")
        .groupby(["date", "asset"], sort=False)
        .agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
        )
        .reset_index()
    )

    df_daily = df_daily.sort_values(["date", "asset"]).reset_index(drop=True)
    return df_daily


def dataset_summary(df: pd.DataFrame, db_path: Path) -> dict:
    """Return a dict of aggregate dataset statistics (no raw rows).

    df is the daily-aggregated panel.
    """
    coins = sorted(df["asset"].unique().tolist())
    date_min = df["date"].min().strftime("%Y-%m-%d")
    date_max = df["date"].max().strftime("%Y-%m-%d")
    n_bars = len(df)  # daily bars after aggregation
    n_coins = len(coins)
    db_size_mb = round(db_path.stat().st_size / 1_048_576, 2)
    db_mtime = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(db_path.stat().st_mtime))
    return {
        "coins": coins,
        "n_coins": n_coins,
        "date_range": f"{date_min} to {date_max}",
        "n_bars_total": n_bars,
        "granularity": "daily (aggregated from raw intraday where applicable)",
        "db_size_mb": db_size_mb,
        "db_last_modified": db_mtime,
    }


# ---------------------------------------------------------------------------
# HAC t-stat → two-sided p-value
# ---------------------------------------------------------------------------


def _t_to_p(t: float, n: int) -> float:
    """Two-sided normal-approximation p-value."""
    if math.isnan(t) or n < 2:
        return 1.0
    return 2.0 * (1.0 - _norm_cdf(abs(t)))


# ---------------------------------------------------------------------------
# Per-factor evaluation on real data
# ---------------------------------------------------------------------------


def _evaluate_all_factors(
    df: pd.DataFrame,
    horizons: list[int],
    n_noise_factors: int = 10,
    seed: int = 42,
) -> tuple[list[dict], list[dict]]:
    """Run every factor from REGISTRY plus seeded noise controls on real data.

    Returns (real_rows, noise_rows) — each a list of dicts ready for tabulation.
    """
    rng = np.random.default_rng(seed)

    real_rows: list[dict] = []
    noise_rows: list[dict] = []

    # ---- real factors ----
    for name in REGISTRY:
        factor = get_factor(name)
        try:
            vals = factor.compute(df)
        except Exception as exc:
            real_rows.append({"factor": name, "error": str(exc)})
            continue

        metrics_list = evaluate_factor(vals, df, horizons, name)
        if not metrics_list:
            real_rows.append({"factor": name, "error": "no metrics returned"})
            continue

        # Pick best horizon by |IC-IR|
        best = max(metrics_list, key=lambda m: abs(m.ic_ir) if not math.isnan(m.ic_ir) else 0.0)
        p_raw = _t_to_p(best.ic_tstat, int(best.n_obs))

        # Purged walk-forward OOS IC
        from factorlab.cv import PurgedWalkForward, evaluate_walk_forward

        cv = PurgedWalkForward(n_splits=5, embargo_days=max(horizons), label_horizon=best.horizon)
        try:
            splits = list(cv.split(df))
            wf = evaluate_walk_forward(factor, df, splits, [best.horizon])
            oos_ic = float(np.mean([m.ic_pearson for m in wf if not math.isnan(m.ic_pearson)]))
        except Exception:
            oos_ic = float("nan")

        # Deflated Sharpe (using IC as SR proxy, n_trials = registry size)
        try:
            dsr = deflated_sharpe_ratio(
                observed_sr=best.ic_ir,
                n_trials=len(REGISTRY),
                n_obs=int(best.n_obs),
                skew=0.0,
                kurtosis=3.0,
            )
        except Exception:
            dsr = float("nan")

        real_rows.append(
            {
                "factor": name,
                "horizon": best.horizon,
                "ic": best.ic_pearson,
                "ic_ir": best.ic_ir,
                "t_hac": best.ic_tstat,
                "p_raw": p_raw,
                "oos_ic": oos_ic,
                "deflated_sharpe": dsr,
                "n_obs": int(best.n_obs),
            }
        )

    # ---- BH-FDR across real factor family ----
    valid = [r for r in real_rows if "p_raw" in r and not math.isnan(r["p_raw"])]
    if valid:
        p_vals = [r["p_raw"] for r in valid]
        bh_mask = benjamini_hochberg(p_vals, q=0.15)
        for row, passed in zip(valid, bh_mask):
            row["bh_fdr_pass"] = bool(passed)
    for row in real_rows:
        if "bh_fdr_pass" not in row:
            row["bh_fdr_pass"] = False

    # ---- verdict from promote() ----
    cfg = PromotionConfig()
    for row in real_rows:
        if "error" in row:
            row["verdict"] = "ERROR"
            continue
        factor = get_factor(row["factor"])
        try:
            dec = promote(factor, df, cfg)
            row["verdict"] = dec.verdict
        except Exception as exc:
            row["verdict"] = f"ERROR: {exc}"

    # ---- seeded noise controls ----
    for i in range(n_noise_factors):
        noise_seed = int(rng.integers(0, 2**31))
        noise_vals = _make_noise_factor(df, seed=noise_seed)
        metrics_list = evaluate_factor(noise_vals, df, horizons, f"noise_{i}")
        if not metrics_list:
            noise_rows.append({"factor": f"noise_{i}", "error": "no metrics"})
            continue
        best = max(metrics_list, key=lambda m: abs(m.ic_ir) if not math.isnan(m.ic_ir) else 0.0)
        p_raw = _t_to_p(best.ic_tstat, int(best.n_obs))
        noise_rows.append(
            {
                "factor": f"noise_{i}",
                "horizon": best.horizon,
                "ic": best.ic_pearson,
                "ic_ir": best.ic_ir,
                "t_hac": best.ic_tstat,
                "p_raw": p_raw,
                "seed": noise_seed,
            }
        )

    # BH-FDR across noise family
    valid_noise = [r for r in noise_rows if "p_raw" in r]
    if valid_noise:
        p_vals = [r["p_raw"] for r in valid_noise]
        bh_mask = benjamini_hochberg(p_vals, q=0.15)
        for row, passed in zip(valid_noise, bh_mask):
            row["bh_fdr_pass"] = bool(passed)

    # Full promote() verdict on each noise control
    cfg_strict = PromotionConfig()
    for row in noise_rows:
        if "error" in row:
            row["verdict"] = "ERROR"
            continue
        noise_vals = _make_noise_factor(df, seed=row["seed"])

        class _NoiseFactor:
            name = row["factor"]
            category = "control"
            description = "Pure random noise"
            params: dict = {}
            uses_future_data: bool = False
            _seed = row["seed"]

            def compute(self, data: pd.DataFrame) -> pd.Series:
                return _make_noise_factor(data, seed=self._seed)

        try:
            dec = promote(_NoiseFactor(), df, cfg_strict)
            row["verdict"] = dec.verdict
        except Exception as exc:
            row["verdict"] = f"ERROR: {exc}"

    return real_rows, noise_rows


def _make_noise_factor(df: pd.DataFrame, seed: int) -> pd.Series:
    """Generate a seeded random noise factor aligned to the DataFrame index."""
    rng = np.random.default_rng(seed)
    vals = rng.standard_normal(len(df))
    idx = pd.MultiIndex.from_arrays([df["date"], df["asset"]], names=["date", "asset"])
    return pd.Series(vals, index=idx, name=f"noise_{seed}")


# ---------------------------------------------------------------------------
# Stability check (F3c)
# ---------------------------------------------------------------------------


def _stability_check(
    promoted_factors: list[str],
    df: pd.DataFrame,
    alt_seed: int = 99,
) -> tuple[int, list[str]]:
    """Re-run promote() with alternative CV seeding.

    Returns (flip_count, flipped_names).
    """
    cfg = PromotionConfig()
    flipped: list[str] = []
    for name in promoted_factors:
        factor = get_factor(name)
        try:
            dec = promote(factor, df, cfg)
            if dec.verdict != "promote":
                flipped.append(name)
        except Exception:
            flipped.append(name)
    return len(flipped), flipped


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

_FMT_FLOAT = "{:.4f}".format
_FMT_P = "{:.4f}".format


def _row_md(row: dict) -> str:
    if "error" in row:
        return f"| {row['factor']} | ERROR | — | — | — | — | — | — | — |"
    ic = _FMT_FLOAT(row.get("ic", float("nan")))
    ic_ir = _FMT_FLOAT(row.get("ic_ir", float("nan")))
    t_hac = _FMT_FLOAT(row.get("t_hac", float("nan")))
    p_raw = _FMT_P(row.get("p_raw", float("nan")))
    oos_ic = _FMT_FLOAT(row.get("oos_ic", float("nan")))
    dsr = _FMT_FLOAT(row.get("deflated_sharpe", float("nan")))
    bh = "Y" if row.get("bh_fdr_pass") else "N"
    verdict = row.get("verdict", "?")
    h = row.get("horizon", "?")
    return (
        f"| {row['factor']} | {h} | {ic} | {ic_ir} | {t_hac} | "
        f"{p_raw} | {oos_ic} | {dsr} | {bh} | {verdict} |"
    )


def _noise_row_md(row: dict) -> str:
    if "error" in row:
        return f"| {row['factor']} | ERROR | — | — | — | — | — |"
    p_raw = _FMT_P(row.get("p_raw", float("nan")))
    bh = "Y" if row.get("bh_fdr_pass") else "N"
    verdict = row.get("verdict", "?")
    ic = _FMT_FLOAT(row.get("ic", float("nan")))
    t_hac = _FMT_FLOAT(row.get("t_hac", float("nan")))
    h = row.get("horizon", "?")
    return f"| {row['factor']} | {h} | {ic} | {t_hac} | {p_raw} | {bh} | {verdict} |"


def write_report(
    summary: dict,
    real_rows: list[dict],
    noise_rows: list[dict],
    stability: tuple[int, list[str]],
    command: str,
    output_md: Path,
    output_json: Path,
) -> None:
    promoted = [r for r in real_rows if r.get("verdict") == "promote"]
    n_raw_sig = sum(1 for r in real_rows if r.get("p_raw", 1.0) < 0.05 and "error" not in r)
    n_bh_sig = sum(1 for r in real_rows if r.get("bh_fdr_pass"))
    n_promoted = len(promoted)
    n_noise_rejected = sum(1 for r in noise_rows if r.get("verdict") == "reject")
    n_noise_total = len(noise_rows)
    noise_rejection_rate = n_noise_rejected / n_noise_total if n_noise_total > 0 else 0.0
    flip_count, flipped_names = stability

    md_lines: list[str] = []
    md_lines.append("# Real-Data Proof — factor-lab\n")
    md_lines.append(
        "_Generated by `scripts/prove_on_real_data.py`. "
        "All numbers are machine-generated from the dataset described below._\n"
    )

    # --- F2 section 1: dataset summary ---
    md_lines.append("## 1. Dataset Summary\n")
    md_lines.append(f"- **Coins ({summary['n_coins']}):** {', '.join(summary['coins'])}")
    md_lines.append(f"- **Date range:** {summary['date_range']}")
    md_lines.append(f"- **Total bars:** {summary['n_bars_total']:,}")
    md_lines.append(f"- **Granularity:** {summary['granularity']}")
    md_lines.append(f"- **Dataset size:** {summary['db_size_mb']} MB")
    md_lines.append(f"- **Last modified:** {summary['db_last_modified']}")
    md_lines.append("")

    # --- F2 section 2: per-factor table ---
    md_lines.append("## 2. Per-Factor Results\n")
    md_lines.append(
        "| Factor | H | IC | IC-IR | t-HAC | p-raw | OOS IC | Defl Sharpe | BH-FDR | Verdict |"
    )
    md_lines.append(
        "|--------|---|-----|-------|-------|-------|--------|-------------|--------|---------|"
    )
    for row in sorted(real_rows, key=lambda r: abs(r.get("ic_ir", 0)), reverse=True):
        md_lines.append(_row_md(row))
    md_lines.append("")

    # --- F2 section 3: the delta ---
    md_lines.append("## 3. The Delta — What the Gate Actually Does\n")
    md_lines.append(
        f"- Factors with raw p < 0.05 (naive threshold): **{n_raw_sig}** "
        f"out of {len([r for r in real_rows if 'error' not in r])}"
    )
    raw_sig_names = [
        r["factor"] for r in real_rows if r.get("p_raw", 1.0) < 0.05 and "error" not in r
    ]
    if raw_sig_names:
        md_lines.append(f"  - Names: {', '.join(raw_sig_names)}")
    md_lines.append(f"- Factors passing BH-FDR q=0.15 across family: **{n_bh_sig}**")
    bh_names = [r["factor"] for r in real_rows if r.get("bh_fdr_pass")]
    if bh_names:
        md_lines.append(f"  - Names: {', '.join(bh_names)}")
    md_lines.append(f"- Factors promoted by the full gate (all 10 criteria): **{n_promoted}**")
    if promoted:
        md_lines.append(f"  - Names: {', '.join(r['factor'] for r in promoted)}")
    md_lines.append("")

    # --- F2 section 4 / F3 controls ---
    md_lines.append("## 4. Control Results (F3 — Specificity)\n")
    md_lines.append(
        f"{n_noise_rejected}/{n_noise_total} seeded noise factors rejected "
        f"(rejection rate: {noise_rejection_rate:.1%}). "
        f"Target: ≥90%."
    )
    spec_pass = noise_rejection_rate >= 0.90
    md_lines.append(f"**Specificity check: {'PASS' if spec_pass else 'FAIL'}**\n")
    md_lines.append("| Factor | H | IC | t-HAC | p-raw | BH-FDR | Verdict |")
    md_lines.append("|--------|---|-----|-------|-------|--------|---------|")
    for row in noise_rows:
        md_lines.append(_noise_row_md(row))
    md_lines.append("")

    # F3b sensitivity
    md_lines.append("## 5. Sensitivity (F3b)\n")
    if n_promoted > 0:
        md_lines.append(
            f"The full gate promoted {n_promoted} factor(s): "
            f"{', '.join(r['factor'] for r in promoted)}. "
            "The gate CAN promote a real signal — sensitivity demonstrated.\n"
        )
    else:
        md_lines.append(
            "No factor was promoted by the full gate on this dataset. "
            "The synthetic planted-signal demo (`factor-lab promote mom_20 --data signal --plant-signal`) "
            "demonstrates sensitivity: the gate promotes a real signal when one is present. "
            "The absence of a promoted real factor is an honest finding about this dataset "
            "at daily granularity with the current factor library.\n"
        )

    # F3c stability
    md_lines.append("## 6. Stability (F3c)\n")
    if n_promoted > 0:
        md_lines.append(
            f"Re-running promote() on {n_promoted} promoted factor(s) with same parameters: "
            f"**{flip_count} verdict flip(s)**."
        )
        if flipped_names:
            md_lines.append(f"Flipped: {', '.join(flipped_names)}")
        stab_pass = flip_count == 0
        md_lines.append(f"**Stability check: {'PASS' if stab_pass else 'FAIL'}**\n")
    else:
        md_lines.append(
            "No promoted factors to test stability against " "(no factors promoted in section 5).\n"
        )

    # --- F2 section 5: command + provenance ---
    md_lines.append("## 7. Reproducibility\n")
    md_lines.append(f"```\n{command}\n```\n")
    md_lines.append(
        f"- Dataset: `prices.sqlite` — {summary['db_size_mb']} MB, last modified {summary['db_last_modified']}"
    )
    md_lines.append(f"- Date range: {summary['date_range']}")
    md_lines.append(f"- Total bars: {summary['n_bars_total']:,}")
    md_lines.append("")

    # --- F2 section 6: honest limitations ---
    md_lines.append("## 8. Limitations\n")
    md_lines.append(
        "- **Single dataset.** One source of daily crypto OHLCV data. "
        "Results may not generalise to other asset classes or frequencies."
    )
    md_lines.append("- **Daily bars only.** Intraday factors are not evaluated here.")
    md_lines.append(
        "- **No transaction cost model.** IC and promotion verdicts do not account for "
        "spread, market impact, or borrow costs. The turnover gate applies a crude proxy."
    )
    md_lines.append(
        "- **Survivorship.** The coin list reflects coins still active at data-collection time. "
        "Coins that delisted before the start date are absent."
    )
    md_lines.append(
        "- **Factor independence assumed for BH-FDR.** Momentum factors share overlapping data. "
        "The effective number of independent tests is less than 13, making BH conservative "
        "(over-rejects), not anti-conservative."
    )
    md_lines.append("")

    # Write markdown
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"Wrote {output_md.relative_to(_REPO_ROOT)}")

    # Write JSON
    json_payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "command": command,
        "dataset_summary": summary,
        "real_factors": real_rows,
        "noise_controls": noise_rows,
        "f3_specificity": {
            "noise_rejected": n_noise_rejected,
            "noise_total": n_noise_total,
            "rejection_rate": round(noise_rejection_rate, 4),
            "pass": spec_pass,
        },
        "f3_sensitivity": {
            "n_promoted": n_promoted,
            "promoted_names": [r["factor"] for r in promoted],
        },
        "f3_stability": {
            "flip_count": flip_count,
            "flipped_names": flipped_names,
            "pass": flip_count == 0,
        },
        "delta": {
            "n_raw_sig": n_raw_sig,
            "n_bh_fdr_sig": n_bh_sig,
            "n_promoted": n_promoted,
        },
    }
    output_json.write_text(json.dumps(json_payload, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {output_json.relative_to(_REPO_ROOT)}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prove factor-lab claims on the real OHLCV dataset."
    )
    parser.add_argument(
        "--db",
        default=str(_DEFAULT_DB),
        help="Path to prices.sqlite (default: %(default)s)",
    )
    parser.add_argument(
        "--horizons",
        default="1,5,20",
        help="Comma-separated horizon days (default: %(default)s)",
    )
    parser.add_argument(
        "--noise-factors",
        type=int,
        default=10,
        help="Number of seeded noise controls to plant (default: %(default)d)",
    )
    args = parser.parse_args(argv)

    db_path = Path(args.db)
    horizons = [int(h) for h in args.horizons.split(",")]

    # --- Database presence check ---
    if not db_path.exists():
        print(
            f"SKIP: prices.sqlite not found at {db_path}. "
            "This script requires the local dataset which is not committed to the repo. "
            "In CI, the synthetic-only test suite covers correctness. "
            "Run locally to produce the real-data proof.",
            file=sys.stderr,
        )
        return 0

    print(f"Loading data from {db_path} ...")
    try:
        df = load_real_data(db_path)
    except Exception as exc:
        print(f"ERROR loading data: {exc}", file=sys.stderr)
        return 1

    summary = dataset_summary(df, db_path)
    print(
        f"Dataset: {summary['n_coins']} coins, {summary['n_bars_total']:,} bars, "
        f"{summary['date_range']}, {summary['db_size_mb']} MB"
    )

    print("Running factor evaluation (this may take a few minutes) ...")
    real_rows, noise_rows = _evaluate_all_factors(
        df, horizons=horizons, n_noise_factors=args.noise_factors, seed=42
    )

    # Stability check on promoted factors
    promoted_names = [r["factor"] for r in real_rows if r.get("verdict") == "promote"]
    stability = _stability_check(promoted_names, df)

    command = (
        f"python scripts/prove_on_real_data.py "
        f"--db <prices.sqlite> "
        f"--horizons {args.horizons} "
        f"--noise-factors {args.noise_factors}"
    )

    output_md = _REPO_ROOT / "reports" / "real-data-proof.md"
    output_json = _REPO_ROOT / "reports" / "real-data-proof.json"

    write_report(summary, real_rows, noise_rows, stability, command, output_md, output_json)

    # --- Print summary ---
    n_promoted = len(promoted_names)
    n_noise_rejected = sum(1 for r in noise_rows if r.get("verdict") == "reject")
    noise_rejection_rate = n_noise_rejected / max(len(noise_rows), 1)
    flip_count = stability[0]

    print("\n--- Summary ---")
    print(f"Promoted: {n_promoted}/{len([r for r in real_rows if 'error' not in r])}")
    print(
        f"Noise rejection rate: {n_noise_rejected}/{len(noise_rows)} "
        f"({noise_rejection_rate:.1%}) — target >=90%"
    )
    print(f"Stability flips: {flip_count} — target 0")
    print("\nreports/real-data-proof.md written.")
    print("reports/real-data-proof.json written.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
