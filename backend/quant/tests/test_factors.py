from quant.factors.momentum import (
    score_return_1m,
    score_return_12m_skip1m,
)
from quant.factors.technical import score_rsi, score_week52_position
from quant.factors.value import score_pe_ratio


def test_pe_ratio_returns_none_for_missing():
    assert score_pe_ratio({"pe_ratio": None}) is None


def test_pe_ratio_returns_float_for_valid(sample_fundamentals_full):
    value = score_pe_ratio(sample_fundamentals_full)
    assert isinstance(value, float)
    assert value == 28.0


def test_rsi_score_returns_none_when_missing():
    assert score_rsi({"rsi": None}) is None


def test_week52_position_returns_none_when_high_equals_low():
    assert score_week52_position({"price": 150, "52week_low": 100, "52week_high": 100}) is None


def test_week52_position_valid_range():
    result = score_week52_position({"price": 150, "52week_low": 100, "52week_high": 200})
    assert result is not None
    assert 0.0 <= result <= 1.0


def test_week52_position_correct_calculation():
    assert score_week52_position({"price": 150, "52week_low": 100, "52week_high": 200}) == 0.5


def test_return_1m_correct_calculation():
    prices = [100.0] + [110.0] * 21
    expected = (110.0 / 100.0) - 1
    assert score_return_1m(prices) == expected


def test_return_12m_skip1m_excludes_last_month():
    prices = [100.0] * 230 + [200.0] + [300.0] * 21
    result = score_return_12m_skip1m(prices)
    assert result is not None
    assert result == 1.0


def test_momentum_returns_none_for_insufficient_history():
    assert score_return_1m([100.0] * 20) is None
