"""
factorlab.cli — command-line interface.

Entry point: factor-lab

Commands:
    screen  -- screen all registered factors on OHLCV data
    promote -- run the promotion gate on a single named factor
    report  -- render a report from screening results
    list    -- list all registered factors
    explain -- describe one factor
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _get_data(data_arg: str, seed: int = 7, plant_signal: bool = False):
    """Load OHLCV data from a path or generate synthetic data.

    Parameters
    ----------
    data_arg:
        'synthetic', 'signal', 'noise', or a file path.
    seed:
        RNG seed for synthetic data.
    plant_signal:
        If True and data_arg='synthetic', plant a momentum signal.
    """
    from .data import load_ohlcv_csv, synthetic_ohlcv

    if data_arg == "synthetic":
        return synthetic_ohlcv(n_days=1500, n_assets=12, seed=seed, plant_signal=plant_signal)
    if data_arg == "signal":
        return synthetic_ohlcv(n_days=1500, n_assets=12, seed=seed, plant_signal=True)
    if data_arg == "noise":
        return synthetic_ohlcv(n_days=1500, n_assets=12, seed=seed, plant_noise=True)
    try:
        return load_ohlcv_csv(data_arg)
    except FileNotFoundError:
        print(
            f"Error: data file not found: {data_arg!r}.\n"
            "Use --data synthetic, --data signal, --data noise, or a valid CSV path.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    except ValueError as exc:
        print(f"Error reading CSV: {exc}", file=sys.stderr)
        raise SystemExit(1)


# ---------------------------------------------------------------------------
# Sub-commands
# ---------------------------------------------------------------------------


def cmd_list(args) -> int:
    """List all registered factors."""
    from .factors import list_factors

    factors = list_factors()
    header = f"{'Name':<22} {'Category':<18} {'Description'}"
    print(header)
    print("-" * len(header))
    for f in factors:
        print(f"{f['name']:<22} {f['category']:<18} {f['description']}")
    return 0


def cmd_explain(args) -> int:
    """Print detailed description of a named factor."""
    from .factors import get_factor

    try:
        factor = get_factor(args.factor)
    except KeyError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    print(f"Name:        {factor.name}")
    print(f"Category:    {factor.category}")
    print(f"Description: {factor.description}")
    print(f"Params:      {factor.params}")
    print(f"Class:       {factor.__class__.__name__}")
    return 0


def cmd_screen(args) -> int:
    """Screen all registered factors on OHLCV data."""
    import math

    from .evaluate import evaluate_factor
    from .factors import REGISTRY
    from .promote import PromotionConfig, promote
    from .report import plot_ic_decay, plot_quantile_returns, to_markdown

    horizons = [int(h) for h in args.horizons.split(",")]
    df = _get_data(args.data, seed=args.seed)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    cfg = PromotionConfig(horizons=horizons)

    all_metrics = []
    all_decisions = []
    all_p_values = []

    # First pass: compute metrics and collect p-values
    factor_metrics_map = {}
    for name, factor in REGISTRY.items():
        factor_vals = factor.compute(df)
        metrics_list = evaluate_factor(
            factor_vals=factor_vals,
            df=df,
            horizons=horizons,
            factor_name=name,
        )
        factor_metrics_map[name] = metrics_list
        all_metrics.extend(metrics_list)

        # Collect HAC IC t-stat p-value for FDR correction (best horizon by |t_hac|)
        best = max(
            metrics_list, key=lambda m: abs(m.ic_tstat) if not math.isnan(m.ic_tstat) else 0.0
        )
        from .significance import _norm_cdf

        def _tstat_to_pval(t: float, n: int) -> float:
            if math.isnan(t) or n < 2:  # noqa: PLR2004
                return 1.0
            return 2.0 * (1.0 - _norm_cdf(abs(t)))

        p = _tstat_to_pval(best.ic_tstat, best.n_obs)
        all_p_values.append(p)

    # Second pass: promote with shared p-value family
    factor_names = list(REGISTRY.keys())
    for i, name in enumerate(factor_names):
        factor = REGISTRY[name]
        other_pvals = [all_p_values[j] for j in range(len(all_p_values)) if j != i]
        decision = promote(
            factor=factor,
            df=df,
            cfg=cfg,
            extra_factors_p_values=other_pvals,
        )
        all_decisions.append(decision)

    # Markdown table
    md = to_markdown(all_metrics, all_decisions)
    print(md)

    table_path = out_dir / "factor_table.md"
    table_path.write_text(md)

    # Plots
    ic_decay_path = out_dir / "ic_decay.png"
    qret_path = out_dir / "quantile_returns.png"
    plot_ic_decay(all_metrics, ic_decay_path)
    plot_quantile_returns(all_metrics, qret_path, horizon=horizons[0])

    # HTML
    from .report import to_html

    html = to_html(all_metrics, all_decisions, ic_decay_path, qret_path)
    (out_dir / "report.html").write_text(html)

    # Summary
    promoted = [d.factor_name for d in all_decisions if d.verdict == "promote"]
    rejected = [d.factor_name for d in all_decisions if d.verdict == "reject"]
    print(f"\nPromoted ({len(promoted)}): {', '.join(promoted) or 'none'}")
    print(f"Rejected ({len(rejected)}): {', '.join(rejected) or 'none'}")
    print(f"\nResults written to: {out_dir}/")
    return 0


def cmd_promote(args) -> int:
    """Run the promotion gate on a single named factor."""
    from .factors import get_factor
    from .promote import PromotionConfig, promote

    try:
        factor = get_factor(args.factor)
    except KeyError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    df = _get_data(args.data, seed=args.seed, plant_signal=args.plant_signal)
    cfg = PromotionConfig()
    decision = promote(factor=factor, df=df, cfg=cfg)
    print(decision)

    if decision.verdict == "promote":
        print("\nResult: PROMOTE")
        return 0
    else:
        print("\nResult: REJECT")
        return 1


def cmd_report(args) -> int:
    """Render a report from results directory."""
    results_dir = Path(args.from_dir)
    table_path = results_dir / "factor_table.md"

    if not table_path.exists():
        print(f"Error: {table_path} not found. Run 'factor-lab screen' first.", file=sys.stderr)
        return 1

    content = table_path.read_text()
    if args.format == "md":
        print(content)
    else:
        print(content)
        print(f"\n(HTML report: {results_dir / 'report.html'})")
    return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="factor-lab",
        description="Evidence-gated factor research engine for financial time series.",
    )
    sub = parser.add_subparsers(dest="command")

    # list
    sub.add_parser("list", help="List all registered factors.")

    # explain
    p_explain = sub.add_parser("explain", help="Describe a factor.")
    p_explain.add_argument("factor", help="Factor name.")

    # screen
    p_screen = sub.add_parser("screen", help="Screen all factors.")
    p_screen.add_argument(
        "--data",
        default="synthetic",
        help="'synthetic', 'signal', 'noise', or path to CSV.",
    )
    p_screen.add_argument("--horizons", default="1,5,20", help="Comma-separated horizons.")
    p_screen.add_argument("--out", default="results/", help="Output directory.")
    p_screen.add_argument("--seed", type=int, default=7, help="RNG seed for synthetic data.")

    # promote
    p_promote = sub.add_parser("promote", help="Promote a single factor.")
    p_promote.add_argument("factor", help="Factor name.")
    p_promote.add_argument(
        "--data",
        default="synthetic",
        help="'synthetic', 'signal', 'noise', or path to CSV.",
    )
    p_promote.add_argument("--seed", type=int, default=7, help="RNG seed for synthetic data.")
    p_promote.add_argument(
        "--plant-signal",
        action="store_true",
        help="Plant a known predictive signal in synthetic data.",
    )

    # report
    p_report = sub.add_parser("report", help="Render a report.")
    p_report.add_argument("--from", dest="from_dir", default="results/", help="Results directory.")
    p_report.add_argument("--format", choices=["md", "html"], default="md")

    return parser


def main() -> None:
    """Entry point for the factor-lab CLI."""
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "list":
        sys.exit(cmd_list(args))
    elif args.command == "explain":
        sys.exit(cmd_explain(args))
    elif args.command == "screen":
        sys.exit(cmd_screen(args))
    elif args.command == "promote":
        sys.exit(cmd_promote(args))
    elif args.command == "report":
        sys.exit(cmd_report(args))
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
