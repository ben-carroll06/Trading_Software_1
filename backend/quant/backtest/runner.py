"""
Backtesting framework for factor strategies.

Phase 2 deliverable. Stubs defined here to establish interface.
"""

from dataclasses import dataclass
from datetime import date


@dataclass
class BacktestConfig:
    strategy_name: str
    start_date: date
    end_date: date
    rebalance_frequency: str   # "daily" | "weekly" | "monthly"
    universe_snapshot: str     # path to historical universe file, or "current"
    top_n: int                 # number of stocks to hold (equal-weight)
    transaction_cost_bps: float = 10.0  # basis points per trade


@dataclass
class BacktestResult:
    config: BacktestConfig
    total_return: float
    annualised_return: float
    sharpe_ratio: float
    max_drawdown: float
    volatility: float
    turnover: float
    equity_curve: list[tuple[date, float]]


def run_backtest(config: BacktestConfig) -> BacktestResult:
    """
    Phase 2 implementation.
    Raises NotImplementedError until Phase 2 is built.
    """
    raise NotImplementedError("Backtesting engine is Phase 2.")
