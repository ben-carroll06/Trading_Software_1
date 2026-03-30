"""Quality factor calculations."""


def score_roe(fundamentals: dict) -> float | None:
    return fundamentals.get("roe")


def score_roa(fundamentals: dict) -> float | None:
    return fundamentals.get("roa")


def score_debt_to_equity(fundamentals: dict) -> float | None:
    return fundamentals.get("debt_to_equity")


def score_current_ratio(fundamentals: dict) -> float | None:
    value = fundamentals.get("current_ratio")
    if value is None:
        return None
    return min(value, 3.0)


def score_gross_margin(fundamentals: dict) -> float | None:
    return fundamentals.get("gross_margin")


def score_operating_margin(fundamentals: dict) -> float | None:
    return fundamentals.get("operating_margin")


def score_revenue_growth(fundamentals: dict) -> float | None:
    return fundamentals.get("revenue_growth")


def score_earnings_growth(fundamentals: dict) -> float | None:
    return fundamentals.get("earnings_growth")
