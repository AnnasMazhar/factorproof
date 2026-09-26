"""
factorlab.factors — factor library.

Each factor implements Factor.compute(df) -> pd.Series.
Factor names are stable keys used across the CLI and registry.
"""

from __future__ import annotations

from .base import Factor
from .library import (
    Amihud20,
    Atr14Norm,
    Autocorr5,
    DeflatedMom,
    LookaheadControl,
    Mom20,
    Mom60,
    NoiseControl,
    Rev5,
    Rsi14,
    Skew60,
    Vol20,
    VolumeZ20,
)

REGISTRY: dict[str, Factor] = {
    "mom_20": Mom20(),
    "mom_60": Mom60(),
    "rev_5": Rev5(),
    "vol_20": Vol20(),
    "atr_norm_14": Atr14Norm(),
    "rsi_14": Rsi14(),
    "volume_z_20": VolumeZ20(),
    "amihud_illiq_20": Amihud20(),
    "skew_60": Skew60(),
    "autocorr_5": Autocorr5(),
    "deflated_mom": DeflatedMom(),
    "noise_control": NoiseControl(),
    "lookahead_control": LookaheadControl(),
}


def get_factor(name: str) -> Factor:
    """Return a factor instance by name.

    Raises KeyError if the name is not in the registry.
    """
    if name not in REGISTRY:
        raise KeyError(f"Unknown factor: '{name}'. Available: {list(REGISTRY)}")
    return REGISTRY[name]


def list_factors() -> list[dict[str, str]]:
    """Return metadata rows for all registered factors (for CLI display)."""
    return [
        {
            "name": f.name,
            "category": f.category,
            "description": f.description,
        }
        for f in REGISTRY.values()
    ]


__all__ = [
    "Factor",
    "REGISTRY",
    "get_factor",
    "list_factors",
]
