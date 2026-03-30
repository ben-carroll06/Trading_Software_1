"""
Value factor calculations.
All functions accept fundamentals: dict (from PriceService.get_snapshot() output)
and return float | None.
"""


def score_pe_ratio(fundamentals: dict) -> float | None:
    """Returns raw P/E. Lower is better. Returns None if unavailable."""
    return fundamentals.get("pe_ratio")


def score_pb_ratio(fundamentals: dict) -> float | None:
    """Returns raw P/B. Lower is better. Returns None if unavailable."""
    return fundamentals.get("price_to_book")


def score_peg_ratio(fundamentals: dict) -> float | None:
    """Returns raw PEG. Lower is better. Returns None if unavailable."""
    return fundamentals.get("peg_ratio")


def score_dividend_yield(fundamentals: dict) -> float | None:
    """Returns dividend yield. Higher is better. Returns None if unavailable."""
    return fundamentals.get("dividend_yield")
