from quant.factors.momentum import score_return_1m, score_return_12m_skip1m
from quant.factors.technical import score_rsi, score_week52_position
from quant.factors.value import score_dividend_yield, score_pb_ratio, score_pe_ratio


# Value factors

def test_pe_ratio_returns_none_for_missing():
    assert score_pe_ratio({"pe_ratio": None}) is None


def test_pe_ratio_returns_float_for_valid():
    value = score_pe_ratio({"pe_ratio": 12.5})
    assert isinstance(value, float)
    assert value == 12.5


def test_pb_ratio_returns_none_for_missing():
    assert score_pb_ratio({"price_to_book": None}) is None


def test_dividend_yield_returns_none_for_missing():
    assert score_dividend_yield({"dividend_yield": None}) is None


# Technical factors

def test_rsi_score_returns_none_when_missing():
    assert score_rsi({"rsi": None}) is None


def test_week52_position_returns_none_when_high_equals_low():
    assert score_week52_position({"price": 150, "52week_low": 100, "52week_high": 100}) is None


def test_week52_position_valid_range():
    """Result must be in [0.0, 1.0] for valid inputs."""
    value = score_week52_position({"price": 150, "52week_low": 100, "52week_high": 200})
    assert value is not None
    assert 0.0 <= value <= 1.0


def test_week52_position_correct_calculation():
    """Given price=150, low=100, high=200 -> expect 0.5."""
    assert score_week52_position({"price": 150, "52week_low": 100, "52week_high": 200}) == 0.5


# Momentum factors

def test_return_1m_correct_calculation():
    """Given prices with known 1m return -> verify exact value."""
    prices = [100.0] + [110.0] * 21
    expected = (110.0 / 100.0) - 1
    assert score_return_1m(prices) == expected


def test_return_12m_skip1m_excludes_last_month():
    """Verify 12-month return does not include the most recent 21 trading days."""
    prices = [100.0] * 230 + [200.0] + [300.0] * 21
    result = score_return_12m_skip1m(prices)
    assert result is not None
    assert result == 1.0


def test_momentum_returns_none_for_insufficient_history():
    """Less than 21 days of history -> 1m return = None."""
    assert score_return_1m([100.0] * 20) is None
