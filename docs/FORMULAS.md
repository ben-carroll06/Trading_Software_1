# ISMF Portfolio Engine Formulas

This document records formulas currently implemented in the codebase and inherited from upstream.

## 1. Position Value (from `data_retrieval.py`)

```text
position_value_GBP = total_shares × close_price_in_native_currency × (1 / EUR_rate[currency]) × EUR_rate[GBP]
```

Where:

- `EUR_rate[currency]` converts native currency to EUR
- `EUR_rate[GBP]` converts EUR to GBP
- Supported currencies: USD, GBP, EUR, CAD

## 2. Weekly Performance

```text
weekly_perf(stock) = (close[-1] - close[-6]) / close[-6] × 100
portfolio_weekly_perf = (sum_end_values - sum_start_values) / sum_start_values × 100
```

## 3. Overall Performance

```text
stock_perf = (close[today] - close[first_transaction_date]) / close[first_transaction_date] × 100
fund_perf  = (current_portfolio_value - 10000) / 10000 × 100
```

Notes:

- Upstream implementation uses hardcoded initial fund value of 10,000 GBP.
- ISMF target behavior uses `initial_capital` from `profiles`.

## 4. RSI (14-day, from `price_service.py`)

```text
delta = diff(close_series)
gain  = rolling_mean(max(delta, 0), window=14)
loss  = rolling_mean(max(-delta, 0), window=14)
RS    = gain / loss
RSI   = 100 - (100 / (1 + RS))
```

## 5. Portfolio Risk Metrics (from `Dashboard.tsx`, planned Python port)

```text
hourly_returns[i] = (equity[i] - equity[i-1]) / equity[i-1]
mean_return       = mean(hourly_returns)
std_dev           = sqrt(variance(hourly_returns))
trading_hours_pa  = 252 × 6.5 = 1638
risk_free_hourly  = 0.04 / 1638
sharpe            = ((mean_return - risk_free_hourly) / std_dev) × sqrt(1638)
volatility_ann    = std_dev × sqrt(1638) × 100
max_drawdown      = max((peak - equity) / peak) across all snapshots
var95             = equity × |5th_percentile(sorted_returns)|
```
