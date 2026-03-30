# ISMF Portfolio Engine Architecture

## Overview

ISMF Portfolio Engine is a full-stack platform with:

- Backend services in Python/FastAPI under `backend/`
- Frontend application in React + TypeScript + Vite under `frontend/`
- Supabase as the primary database and authentication provider
- Real-time pricing via Finnhub WebSocket
- Fundamentals, history, and news via Yahoo Finance (`yfinance`)

The Quant layer extends the upstream pricing and data pipeline with a multi-factor ranking engine and `/quant/*` API routes.

## System Components

### Backend

- `backend/prices/main.py`: FastAPI app entrypoint, REST endpoints, WebSocket endpoint
- `backend/prices/price_service.py`: live price ingestion, fundamentals refresh, caches
- `backend/prices/data_retrieval.py`: portfolio analytics and currency conversion
- `backend/news/news_service.py`: news retrieval
- `backend/quant/`: factor models, scoring, APIs, tests, and Phase 2 stubs

### Frontend

- React 19 + TypeScript application
- Auth via Supabase
- Protected routes for authenticated pages
- Quant UI at `/quant` using backend ranking endpoints

### Data Stores and Caching

- Supabase tables for profiles, trades, watchlist, snapshots, fundamentals
- New quant tables:
  - `quant_rankings` for persisted ranking snapshots
  - `quant_factor_config` for future weight overrides
- Local pickle cache (`fundamentals_cache.pkl`) for fundamentals in the running backend container

## Runtime Flows

### Live Data

1. Backend connects to Finnhub WebSocket.
2. Subscribed symbols stream trade updates.
3. Latest prices are broadcast to connected frontend clients through `/ws`.

### Fundamentals Refresh

1. Background loop fetches fundamentals and history through `yfinance`.
2. Results are sanitized and stored in `fundamental_cache`.
3. Cache is periodically written to `fundamentals_cache.pkl`.

### Quant Scoring Refresh

1. Quant loop runs after fundamentals are available.
2. For each strategy in `STRATEGY_CONFIGS`, scoring engine computes factor z-scores and composites.
3. Results are stored in in-memory `quant_results` and persisted to `quant_rankings`.
4. API routes serve rankings, metadata, exports, and manual refresh operations.

## Known Issues and Constraints

1. **Finnhub WebSocket rate limits**
   - `price_service.py` already implements exponential backoff and HTTP 429 handling.
   - Quant engine must not create additional Finnhub subscriptions.
   - Quant engine reads from `PriceService.fundamental_cache` only.

2. **yfinance instability**
   - Yahoo can return HTTP 429 and can change field names.
   - Existing `_safe_float()` and `_safe_int()` patterns must remain in use.
   - Factor modules must handle `None` gracefully.

3. **EuroPitch competition scoring legacy code**
   - Upstream dashboard includes `calculateCompetitionScore()` and writes to `profiles.competition_score`.
   - ISMF removes competition score writes and keeps risk metrics logic.

4. **CORS**
   - Upstream uses broad `allow_origins=["*"]`.
   - Production should use environment-driven allow-list:

```python
allow_origins=[os.getenv("ALLOWED_ORIGINS", "*").split(",")]
```

5. **Pickle caching is ephemeral in hosted environments**
   - `fundamentals_cache.pkl` is lost on container restarts.
   - Acceptable for now due to hourly refresh cadence.
   - Future improvement: Redis or Supabase-backed cache.

6. **Multi-currency handling boundary**
   - `data_retrieval.py` converts portfolio value to GBP using ECB FX rates.
   - Quant scoring remains on raw USD-denominated fundamentals/prices.
   - No FX conversion should be applied in the quant scoring engine.
