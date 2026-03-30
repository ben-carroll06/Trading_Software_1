"""Size factor calculations."""


def score_market_cap(fundamentals: dict) -> float | None:
    """Returns market cap. Used primarily for filtering rather than ranking."""
    return fundamentals.get("market_cap")
