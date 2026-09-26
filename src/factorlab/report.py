"""
factorlab.report — output formatters.

Generates markdown tables, HTML reports, and PNG charts.
All charts use the Agg backend (no display required).
"""

from __future__ import annotations

import base64
from pathlib import Path

from .evaluate import FactorMetrics
from .promote import PromotionDecision

# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------


def to_markdown(
    metrics_list: list[FactorMetrics],
    decisions: list[PromotionDecision],
) -> str:
    """Render a ranked factor table in Markdown.

    Columns: factor, horizon, IC, IC-IR, t-stat, Q-spread, HR Wilson LB,
             turnover, coverage, FDR-pass, verdict.

    No timestamps — output is stable and diff-friendly.

    Parameters
    ----------
    metrics_list:
        Evaluated metrics (one per factor x horizon).
    decisions:
        Promotion decisions keyed by factor name.
    """
    decision_map: dict[str, PromotionDecision] = {d.factor_name: d for d in decisions}

    # Sort by |IC-IR| descending (best signal first)
    def _sort_key(m: FactorMetrics) -> float:
        return abs(m.ic_ir) if m.ic_ir == m.ic_ir else 0.0  # nan check

    best_per_factor: dict[str, FactorMetrics] = {}
    for m in metrics_list:
        if m.factor_name not in best_per_factor:
            best_per_factor[m.factor_name] = m
        else:
            prev = best_per_factor[m.factor_name]
            if _sort_key(m) > _sort_key(prev):
                best_per_factor[m.factor_name] = m

    rows = sorted(best_per_factor.values(), key=_sort_key, reverse=True)

    header = (
        "| Factor | H | IC | IC-IR | t-stat | Q-Spread | HR-WLB | Turnover | Coverage | FDR | Verdict |\n"
        "|--------|---|-----|-------|--------|----------|--------|----------|----------|-----|---------|"
    )
    lines = [header]
    for m in rows:
        d = decision_map.get(m.factor_name)
        verdict = d.verdict.upper() if d else "?"

        def _fmt(x, ndigits=4):
            if x != x:  # nan
                return "nan"
            return f"{x:.{ndigits}f}"

        # FDR pass from decision reasons
        fdr_pass = "?"
        if d:
            for r in d.reasons:
                if r.code == "survives_fdr":
                    fdr_pass = "Y" if r.passed else "N"

        line = (
            f"| {m.factor_name} | {m.horizon} | {_fmt(m.ic_pearson)} | {_fmt(m.ic_ir)} "
            f"| {_fmt(m.ic_tstat, 2)} | {_fmt(m.quantile_spread)} | {_fmt(m.hit_rate_wilson_lb)} "
            f"| {_fmt(m.turnover)} | {_fmt(m.coverage, 2)} | {fdr_pass} | {verdict} |"
        )
        lines.append(line)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------


def plot_ic_decay(
    metrics_list: list[FactorMetrics],
    path: str | Path,
) -> None:
    """Plot IC decay (IC vs horizon) for all factors.

    Saves as PNG to `path`. Uses the Agg backend; no display needed.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 5))

    # Group by factor name; pick the first metrics entry for decay dict
    seen: set[str] = set()
    for m in metrics_list:
        if m.factor_name in seen:
            continue
        seen.add(m.factor_name)
        decay = m.ic_decay
        if not decay:
            continue
        horizons = sorted(decay.keys())
        ics = [decay[h] for h in horizons]
        ax.plot(horizons, ics, marker="o", label=m.factor_name)

    ax.axhline(0, color="black", linewidth=0.8, linestyle="--")
    ax.set_xlabel("Horizon (days)")
    ax.set_ylabel("Mean IC")
    ax.set_title("IC Decay by Factor")
    if seen:  # only add legend if there are labelled artists
        ax.legend(fontsize=7, ncol=3)
    fig.tight_layout()
    fig.savefig(str(path), dpi=100)
    plt.close(fig)


def plot_quantile_returns(
    metrics_list: list[FactorMetrics],
    path: str | Path,
    horizon: int = 5,
) -> None:
    """Plot mean return per quantile bin for each factor at a given horizon.

    Saves as PNG to `path`.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    relevant = [m for m in metrics_list if m.horizon == horizon]
    if not relevant:
        relevant = metrics_list[:1]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.axhline(0, color="black", linewidth=0.8, linestyle="--")
    ax.set_xlabel("Quantile (1=bottom, 5=top)")
    ax.set_ylabel(f"Mean {horizon}d forward return")
    ax.set_title(f"Quantile Returns at horizon={horizon}d")
    ax.legend(fontsize=7, ncol=3)
    fig.tight_layout()
    fig.savefig(str(path), dpi=100)
    plt.close(fig)


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------


def to_html(
    metrics_list: list[FactorMetrics],
    decisions: list[PromotionDecision],
    ic_decay_png: str | Path | None = None,
    quantile_png: str | Path | None = None,
) -> str:
    """Render a self-contained HTML report with inline base64 images.

    No CDN, no external resources.

    Parameters
    ----------
    metrics_list:
        Evaluated metrics.
    decisions:
        Promotion decisions.
    ic_decay_png:
        Path to IC decay PNG (optional).
    quantile_png:
        Path to quantile returns PNG (optional).
    """
    md_table = to_markdown(metrics_list, decisions)
    table_html = _md_table_to_html(md_table)

    imgs = ""
    for png_path in [ic_decay_png, quantile_png]:
        if png_path and Path(png_path).exists():
            data = Path(png_path).read_bytes()
            b64 = base64.b64encode(data).decode("ascii")
            imgs += (
                f'<img src="data:image/png;base64,{b64}" style="max-width:100%;margin:1em 0;" />\n'
            )

    decision_rows = ""
    for d in sorted(decisions, key=lambda x: x.factor_name):
        color = "#c8f7c5" if d.verdict == "promote" else "#f7c5c5"
        decision_rows += f'<tr style="background:{color}"><td>{d.factor_name}</td><td>{d.verdict.upper()}</td></tr>\n'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<title>factor-lab report</title>
<style>
  body {{ font-family: monospace; margin: 2em; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #ccc; padding: 4px 8px; text-align: right; }}
  th {{ background: #f0f0f0; }}
  td:first-child {{ text-align: left; }}
</style>
</head>
<body>
<h1>factor-lab screening report</h1>
{imgs}
<h2>Ranked Factor Table</h2>
{table_html}
<h2>Promotion Verdicts</h2>
<table>
<tr><th>Factor</th><th>Verdict</th></tr>
{decision_rows}
</table>
</body>
</html>"""
    return html


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _md_table_to_html(md: str) -> str:
    """Convert a Markdown pipe-table to HTML. Simple, no deps."""
    lines = [row.strip() for row in md.strip().splitlines() if row.strip()]
    rows = []
    for i, line in enumerate(lines):
        if line.startswith("|---") or line.startswith("| ---"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        tag = "th" if i == 0 else "td"
        row_html = "".join(f"<{tag}>{c}</{tag}>" for c in cells)
        rows.append(f"<tr>{row_html}</tr>")
    return "<table>\n" + "\n".join(rows) + "\n</table>"
