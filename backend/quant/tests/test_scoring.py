from copy import deepcopy

from quant.scoring.config import STRATEGY_CONFIGS
from quant.scoring.engine import ranking_result_to_csv, run_scoring_engine


def _histories_for(universe, sample_price_history):
    return {stock["symbol"]: list(sample_price_history) for stock in universe}


def test_composite_score_is_float(sample_universe, sample_price_history):
    result = run_scoring_engine(sample_universe, _histories_for(sample_universe, sample_price_history))
    assert isinstance(result.ranked_stocks[0].composite_score, float)


def test_ranking_order_is_descending(sample_universe, sample_price_history):
    """composite_score[rank=1] >= composite_score[rank=2] >= ..."""
    result = run_scoring_engine(sample_universe, _histories_for(sample_universe, sample_price_history))
    scores = [s.composite_score for s in result.ranked_stocks]
    assert scores == sorted(scores, reverse=True)


def test_missing_data_gets_neutral_score(sample_universe, sample_price_history):
    """Stock with all-null fundamentals should get composite score near 0."""
    all_null = {
        "symbol": "NULLS",
        "name": "Null Corp",
        "sector": "Utilities",
        "price": 10.0,
        "pe_ratio": None,
        "price_to_book": None,
        "peg_ratio": None,
        "dividend_yield": None,
        "roe": None,
        "roa": None,
        "debt_to_equity": None,
        "current_ratio": None,
        "gross_margin": None,
        "operating_margin": None,
        "revenue_growth": None,
        "earnings_growth": None,
        "rsi": None,
        "52week_high": None,
        "52week_low": None,
        "market_cap": None,
    }
    universe = sample_universe + [all_null]
    histories = _histories_for(universe, sample_price_history)
    result = run_scoring_engine(universe, histories, STRATEGY_CONFIGS["default"], "default")
    null_stock = next(s for s in result.ranked_stocks if s.symbol == "NULLS")
    assert abs(null_stock.composite_score) <= 1.0


def test_missing_factor_count_correct(sample_universe, sample_price_history):
    """sample_fundamentals_sparse has many nulls - missing_factor_count should reflect that."""
    result = run_scoring_engine(sample_universe, _histories_for(sample_universe, sample_price_history))
    sparse = next(s for s in result.ranked_stocks if s.symbol == "SMALL")
    assert sparse.missing_factor_count >= 8


def test_winsorisation_applied(sample_universe, sample_price_history):
    """Inject a stock with extreme pe_ratio (e.g. 10000). Its z-score must be capped at 3."""
    universe = deepcopy(sample_universe)
    extreme = deepcopy(universe[0])
    extreme["symbol"] = "EXTREME"
    extreme["pe_ratio"] = 10000.0
    universe.append(extreme)

    histories = _histories_for(universe, sample_price_history)
    result = run_scoring_engine(universe, histories, STRATEGY_CONFIGS["default"], "default")
    stock = next(s for s in result.ranked_stocks if s.symbol == "EXTREME")
    assert abs(stock.factor_zscores["pe_ratio"]) <= 3.0


def test_weights_normalise(sample_universe, sample_price_history):
    """Even if weights don't sum to 1, composite score must be within [-3, 3] range."""
    custom_weights = {"pe_ratio": 10.0, "roe": 5.0, "rsi": 3.0}
    result = run_scoring_engine(sample_universe, _histories_for(sample_universe, sample_price_history), custom_weights, "custom")
    assert all(-3.0 <= s.composite_score <= 3.0 for s in result.ranked_stocks)


def test_strategy_value_tilt_ranks_low_pe_higher(sample_price_history):
    """With value_tilt strategy, a stock with pe=10 should outrank one with pe=50, all else equal."""
    base = {
        "name": "Base",
        "sector": "Technology",
        "price": 100.0,
        "price_to_book": 2.0,
        "peg_ratio": 1.0,
        "dividend_yield": 0.02,
        "roe": 0.2,
        "roa": 0.1,
        "debt_to_equity": 50.0,
        "current_ratio": 1.5,
        "gross_margin": 0.4,
        "operating_margin": 0.2,
        "revenue_growth": 0.1,
        "earnings_growth": 0.1,
        "rsi": 50.0,
        "52week_high": 120.0,
        "52week_low": 80.0,
        "market_cap": 1_000_000_000,
    }
    universe = [
        {**base, "symbol": "LOWPE", "pe_ratio": 10.0},
        {**base, "symbol": "HIGHPE", "pe_ratio": 50.0},
        {**base, "symbol": "MIDPE", "pe_ratio": 30.0},
    ]
    result = run_scoring_engine(universe, _histories_for(universe, sample_price_history), STRATEGY_CONFIGS["value_tilt"], "value_tilt")
    by_rank = [s.symbol for s in result.ranked_stocks]
    assert by_rank.index("LOWPE") < by_rank.index("HIGHPE")


def test_strategy_momentum_tilt_ranks_strong_momentum_higher():
    """With momentum_tilt strategy, strongest 6m return stock should rank highest, all else equal."""
    universe = [
        {
            "symbol": "M1",
            "name": "Momentum 1",
            "sector": "Tech",
            "price": 100,
            "pe_ratio": 20,
            "price_to_book": 4,
            "peg_ratio": 1.2,
            "dividend_yield": 0.01,
            "roe": 0.2,
            "roa": 0.1,
            "debt_to_equity": 30,
            "current_ratio": 1.5,
            "gross_margin": 0.4,
            "operating_margin": 0.2,
            "revenue_growth": 0.1,
            "earnings_growth": 0.1,
            "rsi": 50,
            "52week_high": 120,
            "52week_low": 80,
            "market_cap": 1_000_000,
        },
        {
            "symbol": "M2",
            "name": "Momentum 2",
            "sector": "Tech",
            "price": 100,
            "pe_ratio": 20,
            "price_to_book": 4,
            "peg_ratio": 1.2,
            "dividend_yield": 0.01,
            "roe": 0.2,
            "roa": 0.1,
            "debt_to_equity": 30,
            "current_ratio": 1.5,
            "gross_margin": 0.4,
            "operating_margin": 0.2,
            "revenue_growth": 0.1,
            "earnings_growth": 0.1,
            "rsi": 50,
            "52week_high": 120,
            "52week_low": 80,
            "market_cap": 1_000_000,
        },
        {
            "symbol": "M3",
            "name": "Momentum 3",
            "sector": "Tech",
            "price": 100,
            "pe_ratio": 20,
            "price_to_book": 4,
            "peg_ratio": 1.2,
            "dividend_yield": 0.01,
            "roe": 0.2,
            "roa": 0.1,
            "debt_to_equity": 30,
            "current_ratio": 1.5,
            "gross_margin": 0.4,
            "operating_margin": 0.2,
            "revenue_growth": 0.1,
            "earnings_growth": 0.1,
            "rsi": 50,
            "52week_high": 120,
            "52week_low": 80,
            "market_cap": 1_000_000,
        },
    ]
    histories = {
        "M1": [100.0] * 252,
        "M2": [100.0] * 126 + [130.0] * 126,
        "M3": [100.0] * 126 + [160.0] * 126,
    }

    result = run_scoring_engine(universe, histories, STRATEGY_CONFIGS["momentum_tilt"], "momentum_tilt")
    assert result.ranked_stocks[0].symbol == "M3"


def test_universe_size_in_result_matches_input(sample_universe, sample_price_history):
    """RankingResult.universe_size == len(sample_universe)."""
    result = run_scoring_engine(sample_universe, _histories_for(sample_universe, sample_price_history))
    assert result.universe_size == len(sample_universe)


def test_factor_coverage_between_0_and_1(sample_universe, sample_price_history):
    """All factor_coverage values must be in [0.0, 1.0]."""
    result = run_scoring_engine(sample_universe, _histories_for(sample_universe, sample_price_history))
    assert all(0.0 <= value <= 1.0 for value in result.factor_coverage.values())


def test_csv_export_contains_all_ranked_stocks(sample_universe, sample_price_history):
    """CSV output row count (excluding header) == len(rankings)."""
    result = run_scoring_engine(sample_universe, _histories_for(sample_universe, sample_price_history))
    csv_content = ranking_result_to_csv(result)
    row_count = len([line for line in csv_content.splitlines() if line.strip()]) - 1
    assert row_count == len(result.ranked_stocks)


def test_rsi_special_scoring(sample_price_history):
    """
    Two stocks: rsi=50 and rsi=90.
    With default weights, rsi=50 stock should have higher rsi z-score than rsi=90.
    """
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
    result = run_scoring_engine(universe, _histories_for(universe, sample_price_history), STRATEGY_CONFIGS["default"], "default")
    by_symbol = {s.symbol: s for s in result.ranked_stocks}
    assert by_symbol["RSI50"].factor_zscores["rsi"] > by_symbol["RSI90"].factor_zscores["rsi"]
    assert by_symbol["RSI50"].factor_zscores["rsi"] > by_symbol["RSI30"].factor_zscores["rsi"]
