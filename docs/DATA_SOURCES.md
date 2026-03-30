# ISMF Portfolio Engine Data Sources

## Data Source Agreement

| Data Type | Source | Library | Update Frequency | Field Names |
|-----------|--------|---------|------------------|-------------|
| Live prices | Finnhub WebSocket | `websockets` | Real-time (tick) | `price`, `change`, `change_percent` |
| Fundamentals | Yahoo Finance | `yfinance` | Every 60 min | Full field set from snapshot: symbol, name, price, change, change_percent, sector, market_cap, pe_ratio, price_to_book, peg_ratio, dividend_yield, roe, roa, debt_to_equity, current_ratio, quick_ratio, gross_margin, operating_margin, profit_margin, revenue_growth, earnings_growth, volume, avg_volume, beta, 52week_high, 52week_low, rsi |
| Price history | Yahoo Finance | `yfinance` | On demand / daily | OHLCV DataFrame |
| FX rates | ECB historical CSV | Manual download + `ecb_daily.pkl` | Daily | EUR base rates |
| News | Yahoo Finance | `yfinance` | On demand | `title`, `summary`, `link`, `date` |
| Universe | `universe.json` (static) | `json` | Manual update | `ticker`, `name`, `sector` |

## Universe Update Policy

The existing `backend/prices/universe.json` contains the original EuroPitch competition universe. ISMF extends this universe with actual ISMF holdings while preserving existing JSON shape and compatibility.

Do not change the format:

```json
{
  "sectors": {
    "sector_key": {
      "name": "Display Name",
      "stocks": [
        { "ticker": "SYM", "name": "Company" }
      ]
    }
  }
}
```

## Planned Additions for Quant

- Momentum lookbacks (1m, 3m, 6m, 12m returns) from `yfinance` history
- Earnings revision data placeholder (to be specified with Quant desk)
