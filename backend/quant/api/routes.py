from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel

from quant.scoring.config import STRATEGY_CONFIGS
from quant.scoring.engine import (
    FACTOR_REGISTRY,
    RankingResult,
    ranking_result_to_csv,
    run_scoring_engine,
)

quant_router = APIRouter()

_PRICE_SERVICE: Any | None = None


class IDeskDataProvider(ABC):
    """
    Every desk plugs into the crossover layer by implementing this interface.
    The crossover exposure dashboard, trade idea aggregator, and weekly insight
    generator call these methods to collect unified data.
    """

    @abstractmethod
    def get_positions(self) -> list[dict]:
        """
        Returns list of current positions.
        Each dict must have: symbol, name, quantity, market_value, desk, asset_type
        """
        ...

    @abstractmethod
    def get_trade_ideas(self) -> list[dict]:
        """
        Returns list of current trade ideas.
        Each dict must have: asset, direction, horizon, conviction_score, desk, tags
        """
        ...

    @abstractmethod
    def get_weekly_insights(self) -> list[dict]:
        """
        Returns top insights for the weekly newsletter.
        Each dict must have: title, summary, desk, conviction, links
        """
        ...


class IFactorDataProvider(ABC):
    """
    Implemented by the price_service / data pipeline.
    The quant factor engine calls this to get raw data per symbol.
    """

    @abstractmethod
    def get_fundamentals(self, symbol: str) -> dict:
        """
        Returns the fundamental data dict for one symbol.
        Must include: pe_ratio, pb_ratio, peg_ratio, roe, roa, debt_to_equity,
                      current_ratio, gross_margin, operating_margin, profit_margin,
                      revenue_growth, earnings_growth, dividend_yield, market_cap,
                      beta, rsi, 52week_high, 52week_low, price
        """
        ...

    @abstractmethod
    def get_price_history(self, symbol: str, period: str) -> list[float]:
        """
        Returns list of daily close prices for `period` (e.g. "1y", "6mo", "1mo").
        """
        ...


class RefreshRequest(BaseModel):
    strategy: str | None = None


def set_price_service(service: Any) -> None:
    global _PRICE_SERVICE
    _PRICE_SERVICE = service


def _require_service() -> Any:
    if _PRICE_SERVICE is None:
        raise HTTPException(status_code=503, detail="Price service not initialized")
    return _PRICE_SERVICE


def _validate_strategy(strategy: str) -> None:
    if strategy not in STRATEGY_CONFIGS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown strategy '{strategy}'. Available: {list(STRATEGY_CONFIGS.keys())}",
        )


def _compute_result(service: Any, strategy: str) -> RankingResult:
    if hasattr(service, "quant_results") and strategy in getattr(service, "quant_results"):
        return service.quant_results[strategy]

    symbols = list(getattr(service, "symbols", []))
    snapshot = service.get_snapshot(symbols)
    universe_data = list(snapshot.values())

    price_histories = {}
    for symbol in symbols:
        if hasattr(service, "get_price_history"):
            price_histories[symbol] = service.get_price_history(symbol, period="1y")
        else:
            price_histories[symbol] = []

    result = run_scoring_engine(
        universe_data=universe_data,
        price_histories=price_histories,
        weights=STRATEGY_CONFIGS[strategy],
        strategy_name=strategy,
    )

    if hasattr(service, "quant_results"):
        service.quant_results[strategy] = result
    return result


def _filter_and_rank(result: RankingResult, sector: str | None, top_n: int) -> list[dict[str, Any]]:
    sector_norm = sector.lower().strip() if sector else None

    filtered = []
    for stock in result.ranked_stocks:
        if sector_norm and stock.sector.lower() != sector_norm:
            continue
        filtered.append(stock)

    filtered = filtered[:top_n]

    payload = []
    for idx, stock in enumerate(filtered, start=1):
        payload.append(
            {
                "rank": idx,
                "symbol": stock.symbol,
                "name": stock.name,
                "sector": stock.sector,
                "composite_score": stock.composite_score,
                "price": stock.price,
                "market_cap": stock.market_cap,
                "missing_factor_count": stock.missing_factor_count,
                "factor_scores": stock.factor_scores,
                "factor_zscores": stock.factor_zscores,
            }
        )
    return payload


@quant_router.get("/rankings")
def get_rankings(
    strategy: str = Query(default="default"),
    sector: str | None = Query(default=None),
    top_n: int = Query(default=20, ge=1),
) -> dict[str, Any]:
    _validate_strategy(strategy)
    service = _require_service()

    if hasattr(service, "refresh_quant_rankings") and strategy not in service.quant_results:
        service.refresh_quant_rankings(strategy=strategy)

    result = _compute_result(service, strategy)
    rankings = _filter_and_rank(result, sector=sector, top_n=top_n)

    return {
        "strategy": strategy,
        "run_timestamp": result.run_timestamp.isoformat(),
        "universe_size": result.universe_size,
        "returned": len(rankings),
        "factor_coverage": result.factor_coverage,
        "rankings": rankings,
    }


@quant_router.get("/rankings/export")
def export_rankings(
    strategy: str = Query(default="default"),
    sector: str | None = Query(default=None),
) -> Response:
    _validate_strategy(strategy)
    service = _require_service()

    if hasattr(service, "refresh_quant_rankings") and strategy not in service.quant_results:
        service.refresh_quant_rankings(strategy=strategy)

    result = _compute_result(service, strategy)

    filtered_stocks = []
    sector_norm = sector.lower().strip() if sector else None
    for stock in result.ranked_stocks:
        if sector_norm and stock.sector.lower() != sector_norm:
            continue
        filtered_stocks.append(stock)

    for idx, stock in enumerate(filtered_stocks, start=1):
        stock.rank = idx

    export_result = RankingResult(
        ranked_stocks=filtered_stocks,
        run_timestamp=result.run_timestamp,
        strategy_name=result.strategy_name,
        universe_size=len(filtered_stocks),
        factor_coverage=result.factor_coverage,
    )

    csv_content = ranking_result_to_csv(export_result)
    filename_date = datetime.now(timezone.utc).date().isoformat()

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="ismf-top-opportunities-{filename_date}.csv"'
        },
    )


@quant_router.get("/strategies")
def get_strategies() -> dict[str, list[str]]:
    return {"strategies": list(STRATEGY_CONFIGS.keys())}


@quant_router.get("/factors")
def get_factors() -> dict[str, list[dict[str, str]]]:
    factors = []
    for factor in FACTOR_REGISTRY.values():
        factors.append(
            {
                "name": factor.name,
                "direction": factor.direction,
                "group": factor.group,
                "description": factor.description,
            }
        )
    return {"factors": factors}


@quant_router.post("/refresh")
def refresh_rankings(payload: RefreshRequest | None = None) -> dict[str, Any]:
    service = _require_service()

    strategy = payload.strategy if payload else None
    if strategy:
        _validate_strategy(strategy)

    if hasattr(service, "refresh_quant_rankings"):
        service.refresh_quant_rankings(strategy=strategy)
    else:
        if strategy:
            _compute_result(service, strategy)
        else:
            for strategy_name in STRATEGY_CONFIGS:
                _compute_result(service, strategy_name)

    timestamps = []
    for strategy_name, result in getattr(service, "quant_results", {}).items():
        if strategy and strategy_name != strategy:
            continue
        timestamps.append(result.run_timestamp)

    run_timestamp = max(timestamps).isoformat() if timestamps else datetime.now(timezone.utc).isoformat()

    return {"status": "ok", "run_timestamp": run_timestamp}
