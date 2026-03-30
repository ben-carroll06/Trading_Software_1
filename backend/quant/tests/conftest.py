import random

import pytest


@pytest.fixture
def sample_fundamentals_full():
    return {
        "symbol": "AAPL",
        "name": "Apple",
        "sector": "Technology",
        "price": 180.0,
        "pe_ratio": 28.0,
        "price_to_book": 45.0,
        "peg_ratio": 2.1,
        "dividend_yield": 0.006,
        "roe": 1.47,
        "roa": 0.28,
        "debt_to_equity": 172.0,
        "current_ratio": 0.99,
        "gross_margin": 0.46,
        "operating_margin": 0.30,
        "profit_margin": 0.26,
        "revenue_growth": 0.08,
        "earnings_growth": 0.14,
        "beta": 1.2,
        "rsi": 58.0,
        "52week_high": 200.0,
        "52week_low": 140.0,
        "market_cap": 2_800_000_000_000,
    }


@pytest.fixture
def sample_fundamentals_sparse():
    return {
        "symbol": "SMALL",
        "name": "Small Corp",
        "sector": "Industrials",
        "price": 10.0,
        "pe_ratio": None,
        "price_to_book": None,
        "peg_ratio": None,
        "dividend_yield": None,
        "roe": None,
        "roa": None,
        "debt_to_equity": None,
        "current_ratio": 1.5,
        "gross_margin": 0.20,
        "operating_margin": 0.10,
        "profit_margin": 0.08,
        "revenue_growth": 0.03,
        "earnings_growth": None,
        "beta": 0.8,
        "rsi": 45.0,
        "52week_high": 15.0,
        "52week_low": 8.0,
        "market_cap": 50_000_000,
    }


@pytest.fixture
def sample_universe(sample_fundamentals_full, sample_fundamentals_sparse):
    stocks = [sample_fundamentals_full, sample_fundamentals_sparse]
    for i in range(3):
        stocks.append(
            {
                "symbol": f"MOCK{i}",
                "name": f"Mock Corp {i}",
                "sector": "Technology",
                "price": 50.0 + i * 10,
                "pe_ratio": 15.0 + i * 5,
                "price_to_book": 3.0 + i,
                "peg_ratio": 1.5 + i * 0.3,
                "dividend_yield": 0.02 + i * 0.005,
                "roe": 0.15 + i * 0.05,
                "roa": 0.08 + i * 0.02,
                "debt_to_equity": 50.0 - i * 10,
                "current_ratio": 1.5 + i * 0.2,
                "gross_margin": 0.35 + i * 0.05,
                "operating_margin": 0.15 + i * 0.03,
                "profit_margin": 0.12 + i * 0.02,
                "revenue_growth": 0.05 + i * 0.02,
                "earnings_growth": 0.08 + i * 0.03,
                "beta": 1.0 + i * 0.1,
                "rsi": 50.0 + i * 5,
                "52week_high": 70.0 + i * 10,
                "52week_low": 30.0 + i * 5,
                "market_cap": 100_000_000 * (i + 1),
            }
        )
    return stocks


@pytest.fixture
def sample_price_history():
    random.seed(42)
    p = 100.0
    prices = []
    for _ in range(252):
        p *= 1 + random.gauss(0.0003, 0.015)
        prices.append(p)
    return prices
