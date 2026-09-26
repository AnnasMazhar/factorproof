"""
factorlab.factors.base — abstract Factor interface.

All factors must subclass Factor and implement compute().
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class Factor(ABC):
    """Abstract base for all factors.

    Subclasses must set class attributes:
        name (str)       — stable registry key
        category (str)   — e.g. "momentum", "volatility"
        description (str)— one-line human description
        params (dict)    — hyper-parameters used in compute()

    The compute() contract:
        Input:  tidy long-format OHLCV panel with columns
                date, asset, open, high, low, close, volume.
        Output: pd.Series with a MultiIndex (date, asset),
                representing the factor value at time t.
                NaN is acceptable where the lookback window
                is insufficient; the downstream machinery
                handles coverage penalties.
    """

    name: str = ""
    category: str = ""
    description: str = ""
    params: dict = {}

    @abstractmethod
    def compute(self, df: pd.DataFrame) -> pd.Series:
        """Compute factor values from OHLCV panel.

        Parameters
        ----------
        df:
            Tidy long-format OHLCV panel.

        Returns
        -------
        pd.Series
            Factor values with MultiIndex (date, asset).
        """
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"
