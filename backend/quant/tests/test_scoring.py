from quant.scoring.config import STRATEGY_CONFIGS
from quant.scoring.engine import run_scoring_engine


def _build_histories(universe, sample_price_history):
    return {stock["symbol"]: list(sample_price_history) for stock in universe}


def test_composite_score_is_float(sample_universe, sample_price_history):
    result = run_scoring_engine(sample_universe, _build_histories(sample_universe, sample_price_history))
    assert result.ranked_stocks
    assert isinstance(result.ranked_stocks[0].composite_score, float)


def test_ranking_order_is_descending(sample_universe, sample_price_history):
    result = run_scoring_engine(sample_universe, _build_histories(sample_universe, sample_price_history))
    scores = [s.composite_score for s in result.ranked_stocks]
    assert scores == sorted(scores, reverse=True)


def test_missing_data_gets_neutral_score(sample_universe, sample_price_history):
    empty = {
        "symbol": "NULLS",
        "name": "Null Corp",
        "sector": "Industrials",
        "price": 10.0,
        "market_cap": 1_000_000,
    }
    universe = sample_universe + [empty]
    histories = _build_histories(universe, sample_price_history)
    result = run_scoring_engine(universe, histories, STRATEGY_CONFIGS["default"], "default")
    null_stock = next(s for s in result.ranked_stocks if s.symbol == "NULLS")
    assert abs(null_stock.composite_score) <= 1.0


def test_rsi_special_scoring(sample_price_history):
    base = {
        "name": "Base",
        "sector": "Technology",
        "price": 100.0,
        "pe_ratio": 20.0,
        "price_to_book": 5.0,
        "peg_ratio": 1.5,
        "dividend_yield": 0.01,
        "roe": 0.2,
        "roa": 0.1,
        "debt_to_equity": 30.0,
        "current_ratio": 1.2,
        "gross_margin": 0.3,
        "operating_margin": 0.2,
        "revenue_growth": 0.1,
        "earnings_growth": 0.1,
        "52week_high": 120.0,
        "52week_low": 80.0,
        "market_cap": 1_000_000_000,
    }
    universe = [
        {**base, "symbol": "RSI50", "rsi": 50.0},
        {**base, "symbol": "RSI90", "rsi": 90.0},
        {**base, "symbol": "RSI30", "rsi": 30.0},
    ]
    histories = _build_histories(universe, sample_price_history)
    result = run_scoring_engine(universe, histories, STRATEGY_CONFIGS["default"], "default")
    by_symbol = {s.symbol: s for s in result.ranked_stocks}
    assert by_symbol["RSI50"].factor_zscores["rsi"] > by_symbol["RSI90"].factor_zscores["rsi"]
    assert by_symbol["RSI50"].factor_zscores["rsi"] > by_symbol["RSI30"].factor_zscores["rsi"]
