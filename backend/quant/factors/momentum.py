"""
Momentum factor calculations.
Requires price history from yfinance. Uses PriceService.get_price_history().
"""

TRADING_DAYS_1M = 21
TRADING_DAYS_3M = 63
TRADING_DAYS_6M = 126
TRADING_DAYS_12M = 252


def _return_from_lookback(prices: list[float], lookback_days: int) -> float | None:
    if len(prices) < lookback_days + 1:
        return None

    latest = prices[-1]
    lookback = prices[-(lookback_days + 1)]

    if lookback in (None, 0):
        return None

    return (latest / lookback) - 1


def score_return_1m(prices: list[float]) -> float | None:
    """1-month price return. Higher is better."""
    return _return_from_lookback(prices, TRADING_DAYS_1M)


def score_return_3m(prices: list[float]) -> float | None:
    """3-month price return. Higher is better."""
    return _return_from_lookback(prices, TRADING_DAYS_3M)


def score_return_6m(prices: list[float]) -> float | None:
    """6-month price return. Higher is better."""
    return _return_from_lookback(prices, TRADING_DAYS_6M)


def score_return_12m_skip1m(prices: list[float]) -> float | None:
    """12-month return excluding most recent month (classic momentum skip-period). Higher is better."""
    if len(prices) < TRADING_DAYS_12M:
        return None

    end_index = -(TRADING_DAYS_1M + 1)
    start_index = -TRADING_DAYS_12M

    start_price = prices[start_index]
    end_price = prices[end_index]

    if start_price in (None, 0):
        return None

    return (end_price / start_price) - 1
