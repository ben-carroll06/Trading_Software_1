"""
Factor Scoring Engine.

Inputs:
    universe_data: list[dict]   - list of fundamentals dicts, one per symbol.
                                  Each dict is the output of PriceService.get_snapshot() for one symbol.
    price_histories: dict[str, list[float]]  - {symbol: [close_price_t-N, ..., close_price_today]}
    weights: dict[str, float]   - factor weights, must be positive, need not sum to 1.
    strategy_name: str          - name of the strategy (for logging/export labeling).

Output:
    RankingResult - dataclass containing:
        ranked_stocks: list[StockScore]   - sorted descending by composite_score
        run_timestamp: datetime
        strategy_name: str
        universe_size: int
        factor_coverage: dict[str, float] - {factor: % of stocks with non-null data}
"""

from __future__ import annotations

import csv
import io
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Callable

from quant.factors.momentum import (
    score_return_1m,
    score_return_3m,
    score_return_6m,
    score_return_12m_skip1m,
)
from quant.factors.quality import (
    score_current_ratio,
    score_debt_to_equity,
    score_earnings_growth,
    score_gross_margin,
    score_operating_margin,
    score_revenue_growth,
    score_roa,
    score_roe,
)
from quant.factors.technical import score_rsi, score_week52_position
from quant.factors.value import (
    score_dividend_yield,
    score_pb_ratio,
    score_pe_ratio,
    score_peg_ratio,
)
from quant.scoring.config import DEFAULT_WEIGHTS


@dataclass
class FactorDefinition:
    name: str
    group: str
    direction: str
    description: str
    special_scoring: str | None
    calculator: Callable[[dict, list[float]], float | None]


@dataclass
class StockScore:
    symbol: str
    name: str
    sector: str
    composite_score: float
    rank: int
    factor_scores: dict[str, float | None]
    factor_zscores: dict[str, float | None]
    missing_factor_count: int
    price: float
    market_cap: float | None


@dataclass
class RankingResult:
    ranked_stocks: list[StockScore]
    run_timestamp: datetime
    strategy_name: str
    universe_size: int
    factor_coverage: dict[str, float]


FACTOR_REGISTRY: dict[str, FactorDefinition] = {
    "pe_ratio": FactorDefinition(
        name="pe_ratio",
        group="value",
        direction="lower_is_better",
        description="P/E Ratio",
        special_scoring=None,
        calculator=lambda fundamentals, _prices: score_pe_ratio(fundamentals),
    ),
    "pb_ratio": FactorDefinition(
        name="pb_ratio",
        group="value",
        direction="lower_is_better",
        description="P/B Ratio",
        special_scoring=None,
        calculator=lambda fundamentals, _prices: score_pb_ratio(fundamentals),
    ),
    "peg_ratio": FactorDefinition(
        name="peg_ratio",
        group="value",
        direction="lower_is_better",
        description="PEG Ratio",
        special_scoring=None,
        calculator=lambda fundamentals, _prices: score_peg_ratio(fundamentals),
    ),
    "dividend_yield": FactorDefinition(
        name="dividend_yield",
        group="value",
        direction="higher_is_better",
        description="Dividend Yield",
        special_scoring=None,
        calculator=lambda fundamentals, _prices: score_dividend_yield(fundamentals),
    ),
    "return_1m": FactorDefinition(
        name="return_1m",
        group="momentum",
        direction="higher_is_better",
        description="1-month return",
        special_scoring=None,
        calculator=lambda _fundamentals, prices: score_return_1m(prices),
    ),
    "return_3m": FactorDefinition(
        name="return_3m",
        group="momentum",
        direction="higher_is_better",
        description="3-month return",
        special_scoring=None,
        calculator=lambda _fundamentals, prices: score_return_3m(prices),
    ),
    "return_6m": FactorDefinition(
        name="return_6m",
        group="momentum",
        direction="higher_is_better",
        description="6-month return",
        special_scoring=None,
        calculator=lambda _fundamentals, prices: score_return_6m(prices),
    ),
    "return_12m_skip1": FactorDefinition(
        name="return_12m_skip1",
        group="momentum",
        direction="higher_is_better",
        description="12-month return excluding most recent month",
        special_scoring=None,
        calculator=lambda _fundamentals, prices: score_return_12m_skip1m(prices),
    ),
    "roe": FactorDefinition(
        name="roe",
        group="quality",
        direction="higher_is_better",
        description="Return on Equity",
        special_scoring=None,
        calculator=lambda fundamentals, _prices: score_roe(fundamentals),
    ),
    "roa": FactorDefinition(
        name="roa",
        group="quality",
        direction="higher_is_better",
        description="Return on Assets",
        special_scoring=None,
        calculator=lambda fundamentals, _prices: score_roa(fundamentals),
    ),
    "debt_to_equity": FactorDefinition(
        name="debt_to_equity",
        group="quality",
        direction="lower_is_better",
        description="Debt to Equity",
        special_scoring=None,
        calculator=lambda fundamentals, _prices: score_debt_to_equity(fundamentals),
    ),
    "current_ratio": FactorDefinition(
        name="current_ratio",
        group="quality",
        direction="higher_is_better",
        description="Current Ratio",
        special_scoring=None,
        calculator=lambda fundamentals, _prices: score_current_ratio(fundamentals),
    ),
    "gross_margin": FactorDefinition(
        name="gross_margin",
        group="quality",
        direction="higher_is_better",
        description="Gross Margin",
        special_scoring=None,
        calculator=lambda fundamentals, _prices: score_gross_margin(fundamentals),
    ),
    "operating_margin": FactorDefinition(
        name="operating_margin",
        group="quality",
        direction="higher_is_better",
        description="Operating Margin",
        special_scoring=None,
        calculator=lambda fundamentals, _prices: score_operating_margin(fundamentals),
    ),
    "revenue_growth": FactorDefinition(
        name="revenue_growth",
        group="quality",
        direction="higher_is_better",
        description="Revenue Growth",
        special_scoring=None,
        calculator=lambda fundamentals, _prices: score_revenue_growth(fundamentals),
    ),
    "earnings_growth": FactorDefinition(
        name="earnings_growth",
        group="quality",
        direction="higher_is_better",
        description="Earnings Growth",
        special_scoring=None,
        calculator=lambda fundamentals, _prices: score_earnings_growth(fundamentals),
    ),
    "rsi": FactorDefinition(
        name="rsi",
        group="technical",
        direction="special",
        description="RSI (special midpoint scoring)",
        special_scoring="rsi_midpoint",
        calculator=lambda fundamentals, _prices: score_rsi(fundamentals),
    ),
    "week52_position": FactorDefinition(
        name="week52_position",
        group="technical",
        direction="higher_is_better",
        description="52-week position",
        special_scoring=None,
        calculator=lambda fundamentals, _prices: score_week52_position(fundamentals),
    ),
}

PE_RATIO_ANCHOR_WEIGHT = 0.12


def _is_valid_number(value: float | int | None) -> bool:
    if value is None:
        return False
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _winsorise(value: float, min_value: float = -3.0, max_value: float = 3.0) -> float:
    return max(min_value, min(max_value, value))


def _zscore(values: list[float]) -> list[float]:
    if not values:
        return []
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    std_dev = math.sqrt(variance)
    if std_dev == 0:
        return [0.0 for _ in values]
    return [(v - mean) / std_dev for v in values]


def _rsi_midpoint_score(rsi: float) -> float:
    return 1 - abs(rsi - 50) / 50


def get_factor_metadata() -> list[dict[str, str]]:
    return [
        {
            "name": factor.name,
            "direction": factor.direction,
            "group": factor.group,
            "description": factor.description,
        }
        for factor in FACTOR_REGISTRY.values()
    ]


def run_scoring_engine(
    universe_data: list[dict],
    price_histories: dict[str, list[float]],
    weights: dict[str, float] | None = None,
    strategy_name: str = "default",
) -> RankingResult:
    if weights is None:
        weights = DEFAULT_WEIGHTS

    active_weights = {
        factor: weight
        for factor, weight in weights.items()
        if factor in FACTOR_REGISTRY and weight > 0
    }

    stock_rows: list[dict] = []
    factor_raw_matrix: dict[str, list[float | None]] = {name: [] for name in FACTOR_REGISTRY}

    for fundamentals in universe_data:
        symbol = str(fundamentals.get("symbol", ""))
        prices = price_histories.get(symbol, [])

        factor_scores: dict[str, float | None] = {}
        for factor_name, definition in FACTOR_REGISTRY.items():
            raw_value = definition.calculator(fundamentals, prices)
            if not _is_valid_number(raw_value):
                raw_value = None
            else:
                raw_value = float(raw_value)
            factor_scores[factor_name] = raw_value
            factor_raw_matrix[factor_name].append(raw_value)

        stock_rows.append(
            {
                "symbol": symbol,
                "name": str(fundamentals.get("name", symbol)),
                "sector": str(fundamentals.get("sector", "Unknown")),
                "price": float(fundamentals.get("price", 0.0) or 0.0),
                "market_cap": fundamentals.get("market_cap"),
                "factor_scores": factor_scores,
            }
        )

    universe_size = len(stock_rows)

    factor_coverage: dict[str, float] = {}
    for factor_name, values in factor_raw_matrix.items():
        if universe_size == 0:
            factor_coverage[factor_name] = 0.0
        else:
            non_null_count = sum(1 for v in values if v is not None)
            factor_coverage[factor_name] = non_null_count / universe_size

    zscore_maps: dict[str, list[float | None]] = {name: [None] * universe_size for name in FACTOR_REGISTRY}

    for factor_name, definition in FACTOR_REGISTRY.items():
        raw_values = factor_raw_matrix[factor_name]

        transformed_values: list[float] = []
        transformed_indices: list[int] = []

        for idx, raw_value in enumerate(raw_values):
            if raw_value is None:
                continue
            transformed = (
                _rsi_midpoint_score(raw_value)
                if definition.special_scoring == "rsi_midpoint"
                else raw_value
            )
            transformed_values.append(transformed)
            transformed_indices.append(idx)

        transformed_zscores = _zscore(transformed_values)

        for idx, z in zip(transformed_indices, transformed_zscores):
            if definition.direction == "lower_is_better":
                z = -z
            zscore_maps[factor_name][idx] = _winsorise(z)

    ranked: list[StockScore] = []
    total_weight = sum(active_weights.values())

    for idx, row in enumerate(stock_rows):
        factor_scores = row["factor_scores"]
        factor_zscores: dict[str, float | None] = {}

        missing_factor_count = 0
        for factor_name in FACTOR_REGISTRY:
            raw_val = factor_scores[factor_name]
            if raw_val is None:
                missing_factor_count += 1
                factor_zscores[factor_name] = 0.0
            else:
                factor_zscores[factor_name] = zscore_maps[factor_name][idx] if zscore_maps[factor_name][idx] is not None else 0.0

        if total_weight > 0:
            weighted_sum = sum(
                active_weights[factor] * float(factor_zscores.get(factor, 0.0) or 0.0)
                for factor in active_weights
            )

            pe_anchor = 0.0
            if "pe_ratio" in active_weights:
                pe_anchor = PE_RATIO_ANCHOR_WEIGHT * float(factor_zscores.get("pe_ratio", 0.0) or 0.0)

            composite_score = (weighted_sum + pe_anchor) / (total_weight + PE_RATIO_ANCHOR_WEIGHT)
        else:
            composite_score = 0.0

        ranked.append(
            StockScore(
                symbol=row["symbol"],
                name=row["name"],
                sector=row["sector"],
                composite_score=float(composite_score),
                rank=0,
                factor_scores=factor_scores,
                factor_zscores=factor_zscores,
                missing_factor_count=missing_factor_count,
                price=float(row["price"]),
                market_cap=float(row["market_cap"]) if _is_valid_number(row["market_cap"]) else None,
            )
        )

    ranked.sort(key=lambda stock: stock.composite_score, reverse=True)
    for rank, stock in enumerate(ranked, start=1):
        stock.rank = rank

    return RankingResult(
        ranked_stocks=ranked,
        run_timestamp=datetime.now(timezone.utc),
        strategy_name=strategy_name,
        universe_size=universe_size,
        factor_coverage=factor_coverage,
    )


def ranking_result_to_dict(result: RankingResult) -> dict:
    return {
        "ranked_stocks": [asdict(stock) for stock in result.ranked_stocks],
        "run_timestamp": result.run_timestamp.isoformat(),
        "strategy_name": result.strategy_name,
        "universe_size": result.universe_size,
        "factor_coverage": result.factor_coverage,
    }


def ranking_result_to_csv(result: RankingResult) -> str:
    output = io.StringIO()
    writer = csv.writer(output)

    factor_columns = list(FACTOR_REGISTRY.keys())
    writer.writerow(
        [
            "rank",
            "symbol",
            "name",
            "sector",
            "composite_score",
            "price",
            "market_cap",
            *factor_columns,
        ]
    )

    for stock in result.ranked_stocks:
        writer.writerow(
            [
                stock.rank,
                stock.symbol,
                stock.name,
                stock.sector,
                stock.composite_score,
                stock.price,
                stock.market_cap,
                *[stock.factor_zscores.get(col) for col in factor_columns],
            ]
        )

    return output.getvalue()
