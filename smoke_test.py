import sys
sys.path.insert(0, "backend/prices")
sys.path.insert(0, "backend")

from quant.scoring.engine import run_scoring_engine
from quant.scoring.config import STRATEGY_CONFIGS

fake_universe = [
    {"symbol": "AAPL", "name": "Apple", "sector": "Technology", "price": 180.0, "pe_ratio": 28.0, "price_to_book": 45.0, "peg_ratio": 2.1, "dividend_yield": 0.006, "roe": 1.47, "roa": 0.28, "debt_to_equity": 172.0, "current_ratio": 0.99, "gross_margin": 0.46, "operating_margin": 0.30, "profit_margin": 0.26, "revenue_growth": 0.08, "earnings_growth": 0.14, "beta": 1.2, "rsi": 58.0, "52week_high": 200.0, "52week_low": 140.0, "market_cap": 2_800_000_000_000},
    {"symbol": "JPM", "name": "JPMorgan", "sector": "Financials", "price": 200.0, "pe_ratio": 12.0, "price_to_book": 1.8, "peg_ratio": 1.2, "dividend_yield": 0.025, "roe": 0.15, "roa": 0.01, "debt_to_equity": 120.0, "current_ratio": None, "gross_margin": None, "operating_margin": 0.35, "profit_margin": 0.28, "revenue_growth": 0.05, "earnings_growth": 0.08, "beta": 1.1, "rsi": 45.0, "52week_high": 220.0, "52week_low": 150.0, "market_cap": 580_000_000_000},
    {"symbol": "XOM", "name": "ExxonMobil", "sector": "Energy", "price": 110.0, "pe_ratio": 14.0, "price_to_book": 2.1, "peg_ratio": None, "dividend_yield": 0.034, "roe": 0.18, "roa": 0.10, "debt_to_equity": 20.0, "current_ratio": 1.3, "gross_margin": 0.40, "operating_margin": 0.15, "profit_margin": 0.10, "revenue_growth": 0.02, "earnings_growth": None, "beta": 0.9, "rsi": 52.0, "52week_high": 125.0, "52week_low": 90.0, "market_cap": 450_000_000_000},
    {"symbol": "NVDA", "name": "Nvidia", "sector": "Technology", "price": 900.0, "pe_ratio": 65.0, "price_to_book": 40.0, "peg_ratio": 1.8, "dividend_yield": 0.001, "roe": 0.55, "roa": 0.25, "debt_to_equity": 40.0, "current_ratio": 4.2, "gross_margin": 0.72, "operating_margin": 0.52, "profit_margin": 0.48, "revenue_growth": 1.22, "earnings_growth": 1.68, "beta": 1.6, "rsi": 70.0, "52week_high": 950.0, "52week_low": 400.0, "market_cap": 2_200_000_000_000},
    {"symbol": "PFE", "name": "Pfizer", "sector": "Healthcare", "price": 28.0, "pe_ratio": 8.0, "price_to_book": 1.2, "peg_ratio": 0.9, "dividend_yield": 0.058, "roe": 0.12, "roa": 0.05, "debt_to_equity": 60.0, "current_ratio": 1.1, "gross_margin": 0.52, "operating_margin": 0.08, "profit_margin": 0.06, "revenue_growth": -0.12, "earnings_growth": -0.45, "beta": 0.6, "rsi": 30.0, "52week_high": 50.0, "52week_low": 25.0, "market_cap": 160_000_000_000},
]

import random
def fake_prices(n=252):
    p = 100.0
    prices = []
    for _ in range(n):
        p *= (1 + random.gauss(0.0003, 0.015))
        prices.append(p)
    return prices

fake_histories = {s["symbol"]: fake_prices() for s in fake_universe}

result = run_scoring_engine(
    universe_data=fake_universe,
    price_histories=fake_histories,
    weights=STRATEGY_CONFIGS["default"],
    strategy_name="default"
)

print(f"\n{'='*60}")
print(f"Strategy: {result.strategy_name}")
print(f"Universe size: {result.universe_size}")
print(f"Run timestamp: {result.run_timestamp}")
print(f"\nRankings:")
print(f"{'Rank':<6} {'Symbol':<8} {'Score':>8}  {'Missing':>8}")
print("-" * 40)
for s in result.ranked_stocks:
    print(f"{s.rank:<6} {s.symbol:<8} {s.composite_score:>8.3f}  {s.missing_factor_count:>8}")

print(f"\nFactor coverage:")
for factor, coverage in result.factor_coverage.items():
    bar = "█" * int(coverage * 20)
    print(f"  {factor:<25} {coverage:>5.0%}  {bar}")
