# ISMF Desk and Factor Interfaces

This document defines required abstract interfaces for desk integration and quant factor data access.

## Desk Data Interface

```python
from abc import ABC, abstractmethod
from typing import Any


class IDeskDataProvider(ABC):
    """
    Every desk plugs into the crossover layer by implementing this interface.
    The crossover exposure dashboard, trade idea aggregator, and weekly insight
    generator call these methods to collect unified data.
    """

    @abstractmethod
    def get_positions(self) -> list[dict]:
        """
        Returns list of current positions.
        Each dict must have: symbol, name, quantity, market_value, desk, asset_type
        """
        ...

    @abstractmethod
    def get_trade_ideas(self) -> list[dict]:
        """
        Returns list of current trade ideas.
        Each dict must have: asset, direction, horizon, conviction_score, desk, tags
        """
        ...

    @abstractmethod
    def get_weekly_insights(self) -> list[dict]:
        """
        Returns top insights for the weekly newsletter.
        Each dict must have: title, summary, desk, conviction, links
        """
        ...
```

## Factor Data Interface

```python
from abc import ABC, abstractmethod


class IFactorDataProvider(ABC):
    """
    Implemented by the price_service / data pipeline.
    The quant factor engine calls this to get raw data per symbol.
    """

    @abstractmethod
    def get_fundamentals(self, symbol: str) -> dict:
        """
        Returns the fundamental data dict for one symbol.
        Must include: pe_ratio, pb_ratio, peg_ratio, roe, roa, debt_to_equity,
                      current_ratio, gross_margin, operating_margin, profit_margin,
                      revenue_growth, earnings_growth, dividend_yield, market_cap,
                      beta, rsi, 52week_high, 52week_low, price
        """
        ...

    @abstractmethod
    def get_price_history(self, symbol: str, period: str) -> list[float]:
        """
        Returns list of daily close prices for `period` (e.g. "1y", "6mo", "1mo").
        """
        ...
```
