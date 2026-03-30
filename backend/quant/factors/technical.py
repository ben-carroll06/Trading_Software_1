"""Technical factor calculations."""


def score_rsi(fundamentals: dict) -> float | None:
    """
    RSI is already computed by price_service._calculate_rsi().
    The raw RSI value is available in fundamentals['rsi'].
    This function returns the raw RSI value.
    Scoring direction handled by engine.py (special case: peak at 50).
    """
    return fundamentals.get("rsi")


def score_week52_position(fundamentals: dict) -> float | None:
    """
    (price - 52w_low) / (52w_high - 52w_low).
    Mid-high values preferred. Range: 0.0 to 1.0.
    Returns None if 52w_high == 52w_low (avoid divide by zero).
    """
    price = fundamentals.get("price")
    low = fundamentals.get("52week_low")
    high = fundamentals.get("52week_high")
    if None in (price, low, high) or high == low:
        return None
    return (price - low) / (high - low)
