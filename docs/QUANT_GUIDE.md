# Quant Guide

## Adjusting Factor Weights

Edit `backend/quant/scoring/config.py`. Add or modify entries in `STRATEGY_CONFIGS`. Each key is a factor name from the quant factor list. Values are positive floats and do not need to sum to 1. Factors not listed receive weight 0 and are excluded.

## Adding a New Strategy

1. Open `backend/quant/scoring/config.py`.
2. Add a new key to `STRATEGY_CONFIGS`, for example: `"esg_tilt": {"roe": 0.3, ...}`.
3. Deploy the backend.
4. The strategy appears in `GET /quant/strategies` and in the frontend strategy selector within 60 seconds.

## Changing the Universe

Edit `backend/prices/universe.json` using the existing structure:

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

Restart the backend. New tickers are scored in the next quant refresh cycle.

## Reading the Rankings

`composite_score` is a normalized weighted average of cross-sectional z-scores. A score of `+2.0` means the stock is two standard deviations above the universe average for the weighted factor combination.

- Positive score: above average
- Negative score: below average
- Missing data in the `Missing` column means those factors contributed neutral `0` and should be interpreted cautiously when the missing count is high.
