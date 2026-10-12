"""Gate a factor with factorproof, then tear-sheet it with alphalens-reloaded.

Concrete integration against a real external tool (alphalens-reloaded).
Offline: uses the bundled synthetic planted-signal panel, no network calls.

Usage:
    .venv/bin/python examples/integrate_alphalens.py

If alphalens is not installed the script prints SKIP and exits 0, so a fresh
clone without the optional integration dependency stays green.
"""

from __future__ import annotations

import sys


def main() -> int:
    try:
        import alphalens
    except ImportError:
        print("SKIP: alphalens-reloaded is not installed (pip install alphalens-reloaded).")
        return 0

    from factorlab.data import synthetic_ohlcv
    from factorlab.factors import get_factor
    from factorlab.promote import PromotionConfig, promote

    df = synthetic_ohlcv(n_days=1500, n_assets=12, seed=7, plant_signal=True)
    factor = get_factor("mom_20")
    decision = promote(factor, df, PromotionConfig())
    print(f"factorproof verdict for mom_20: {decision.verdict}")
    if decision.verdict != "promote":
        print("Rejected by the gate — not worth tear-sheeting.")
        for r in decision.reasons:
            if not r.passed:
                print(f"  FAIL {r.code}: observed={r.observed} threshold={r.threshold}")
        return 1

    factor_values = factor.compute(df)
    prices = df.pivot(index="date", columns="asset", values="close")
    factor_data = alphalens.utils.get_clean_factor_and_forward_returns(
        factor_values,
        prices,
        quantiles=5,
        periods=(1, 5, 20),
    )
    print(f"alphalens {alphalens.__version__}: factor_data shape {factor_data.shape}")
    ic = alphalens.performance.mean_information_coefficient(factor_data)
    print("alphalens mean IC:")
    print(ic.to_string())
    print("INTEGRATION_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
