"""
Strategy configuration registry.

Quants can add new strategies here without touching engine.py.
Each strategy is a named dict of {factor_name: weight}.
Factors not listed in a strategy dict receive weight = 0 (excluded).

To add a new strategy:
    1. Add entry to STRATEGY_CONFIGS
    2. Verify factors map to known factor names in FACTOR_REGISTRY (in engine.py)
    3. Restart the quant service or call /quant/refresh
"""

DEFAULT_WEIGHTS: dict[str, float] = {
    "pe_ratio": 0.08,
    "pb_ratio": 0.07,
    "peg_ratio": 0.05,
    "dividend_yield": 0.05,
    "return_1m": 0.05,
    "return_3m": 0.07,
    "return_6m": 0.08,
    "return_12m_skip1": 0.05,
    "roe": 0.07,
    "roa": 0.05,
    "debt_to_equity": 0.05,
    "current_ratio": 0.04,
    "gross_margin": 0.04,
    "operating_margin": 0.05,
    "revenue_growth": 0.03,
    "earnings_growth": 0.02,
    "rsi": 0.08,
    "week52_position": 0.07,
}

STRATEGY_CONFIGS: dict[str, dict[str, float]] = {
    "default": DEFAULT_WEIGHTS,
    "value_tilt": {
        "pe_ratio": 0.20,
        "pb_ratio": 0.20,
        "peg_ratio": 0.15,
        "dividend_yield": 0.15,
        "roe": 0.10,
        "debt_to_equity": 0.10,
        "rsi": 0.10,
    },
    "momentum_tilt": {
        "return_1m": 0.10,
        "return_3m": 0.20,
        "return_6m": 0.25,
        "return_12m_skip1": 0.15,
        "rsi": 0.15,
        "week52_position": 0.15,
    },
    "quality_tilt": {
        "roe": 0.20,
        "roa": 0.15,
        "gross_margin": 0.15,
        "operating_margin": 0.15,
        "revenue_growth": 0.15,
        "earnings_growth": 0.10,
        "debt_to_equity": 0.10,
    },
}
