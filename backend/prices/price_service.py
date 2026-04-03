import asyncio
import json
import logging
import os
import threading
import time
import pickle
import requests
import yfinance as yf
import pandas as pd
import websockets
from fastapi import WebSocket
from datetime import datetime, timedelta, timezone
from typing import Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PriceService")

CACHE_FILE = "fundamentals_cache.pkl"

class ConnectionManager:
    """Manages the websocket connections to your frontend clients (React)."""
    
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"New client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"Client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Broadcasts a JSON message to all connected clients. Removes dead connections automatically."""
        json_msg = json.dumps(message)
        for connection in list(self.active_connections):  # Iterate over a copy
            try:
                await connection.send_text(json_msg)
            except Exception as e:
                logger.error(f"Failed to send to client: {e}")
                self.disconnect(connection)


class PriceService:
    def __init__(self, universe_file="universe.json"):
        self.api_key = os.getenv("FINNHUB_KEY")
        if not self.api_key:
            logger.warning("Oi! You forgot the FINNHUB_KEY. We're flying blind here mate.")
        
        self.universe_file = universe_file
        self.ticker_metadata = self._load_ticker_metadata()
        self.symbols = list(self.ticker_metadata.keys())
        
        self.fundamental_cache = self._load_cache()
        self.live_prices = {}  # {symbol: price}
        self.quant_results: dict[str, Any] = {}
        self.quant_refresh_minutes = int(os.getenv("QUANT_FACTOR_REFRESH_MINUTES", "60"))
        self.quant_lock = threading.Lock()
        
        self.manager = ConnectionManager()
        self.running = False
        
        # ============================================
        # NEW: WebSocket Reconnection Management
        # ============================================
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        self.base_delay = 5
        self.max_delay = 300  # 5 minutes max
        self.last_429_time = None
        self.consecutive_failures = 0
        self.ws_connected = False

    def _universe_path(self) -> str:
        return os.path.join(os.path.dirname(__file__), self.universe_file)

    def _load_ticker_metadata(self) -> dict[str, dict[str, str]]:
        try:
            path = self._universe_path()
            if not os.path.exists(path):
                return {}

            with open(path, "r") as f:
                data = json.load(f)

            metadata: dict[str, dict[str, str]] = {}
            for sector in data.get("sectors", {}).values():
                sector_name = sector.get("name", "Unknown")
                for stock in sector.get("stocks", []):
                    ticker = stock.get("ticker")
                    if not ticker:
                        continue
                    metadata[ticker] = {
                        "name": stock.get("name", ticker),
                        "sector": sector_name,
                    }
            return metadata
        except Exception as e:
            logger.error(f"Failed to load ticker metadata: {e}")
            return {}

    def _load_symbols(self):
        try:
            path = self._universe_path()
            if not os.path.exists(path):
                return []
            
            with open(path, "r") as f:
                data = json.load(f)
            
            tickers = []
            for sector in data["sectors"].values():
                for stock in sector["stocks"]:
                    tickers.append(stock["ticker"])
            return list(set(tickers))
        except Exception as e:
            logger.error(f"Failed to load universe: {e}")
            return []

    def _load_cache(self):
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "rb") as f:
                    logger.info("Loaded cached fundamentals from disk.")
                    return pickle.load(f)
            except Exception:
                pass
        return {}

    def _save_cache(self):
        try:
            with open(CACHE_FILE, "wb") as f:
                pickle.dump(self.fundamental_cache, f)
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")

    async def start(self):
        """Starts the async loop for Finnhub and the threaded loop for Yahoo."""
        self.running = True
        
        # Start fundamentals in a background thread
        t_fund = threading.Thread(target=self._fundamental_loop, daemon=True)
        t_fund.start()

        # Start quant scoring in a background thread
        t_quant = threading.Thread(target=self._quant_scoring_loop, daemon=True)
        t_quant.start()
        
        # Start the async websocket consumer
        asyncio.create_task(self._upstream_websocket_loop())

    async def _upstream_websocket_loop(self):
        """Connects to Finnhub with exponential backoff and rate limit handling."""
        uri = f"wss://ws.finnhub.io?token={self.api_key}"
        
        while self.running:
            try:
                # ============================================
                # RATE LIMIT CHECK: If we got 429, wait longer
                # ============================================
                if self.last_429_time:
                    time_since_429 = (datetime.now() - self.last_429_time).total_seconds()
                    if time_since_429 < 120:  # Wait at least 2 minutes after 429
                        wait_time = 120 - time_since_429
                        logger.warning(f"⚠️ Rate limited! Waiting {wait_time:.0f}s before retry...")
                        await asyncio.sleep(wait_time)
                        self.last_429_time = None  # Reset after waiting
                
                # ============================================
                # EXPONENTIAL BACKOFF: Calculate delay
                # ============================================
                if self.reconnect_attempts > 0:
                    delay = min(self.base_delay * (2 ** self.reconnect_attempts), self.max_delay)
                    logger.info(f"Reconnecting in {delay}s (attempt {self.reconnect_attempts}/{self.max_reconnect_attempts})...")
                    await asyncio.sleep(delay)
                
                logger.info("Connecting to Finnhub WS...")
                
                async with websockets.connect(uri) as ws:
                    logger.info("✅ Connected to Finnhub.")
                    self.ws_connected = True
                    self.reconnect_attempts = 0  # Reset on successful connection
                    self.consecutive_failures = 0
                    
                    # Subscribe to all symbols
                    for sym in self.symbols:
                        await ws.send(json.dumps({"type": "subscribe", "symbol": sym}))
                        await asyncio.sleep(0.05)  # Small delay between subscriptions
                    
                    # Listen for messages
                    async for message in ws:
                        try:
                            data = json.loads(message)
                            
                            if data["type"] == "trade":
                                update_batch = {}
                                
                                for trade in data["data"]:
                                    sym = trade["s"]
                                    price = trade["p"]
                                    
                                    self.live_prices[sym] = price
                                    
                                    prev_close = self._get_prev_close(sym)
                                    change = 0.0
                                    change_p = 0.0
                                    
                                    if prev_close and prev_close > 0:
                                        change = price - prev_close
                                        change_p = (change / prev_close) * 100
                                    
                                    update_batch[sym] = {
                                        "price": price,
                                        "change": round(change, 2),
                                        "change_percent": round(change_p, 2),
                                    }
                                
                                if update_batch:
                                    await self.manager.broadcast({
                                        "type": "price_update",
                                        "data": update_batch
                                    })
                        
                        except Exception as e:
                            logger.error(f"Error processing message: {e}")
            
            except Exception as e:
                self.ws_connected = False
                self.consecutive_failures += 1
                
                error_msg = str(e)
                
                # ============================================
                # HANDLE 429 (Rate Limit) SPECIFICALLY
                # ============================================
                if "429" in error_msg or "HTTP 429" in error_msg:
                    logger.error(f"🚨 Finnhub rate limit hit (HTTP 429). Backing off significantly...")
                    self.last_429_time = datetime.now()
                    self.reconnect_attempts = min(self.reconnect_attempts + 5, self.max_reconnect_attempts)
                
                # ============================================
                # HANDLE OTHER ERRORS
                # ============================================
                else:
                    logger.error(f"Finnhub connection dropped: {e}")
                    self.reconnect_attempts = min(self.reconnect_attempts + 1, self.max_reconnect_attempts)
                
                # ============================================
                # STOP TRYING AFTER TOO MANY FAILURES
                # ============================================
                if self.consecutive_failures >= self.max_reconnect_attempts:
                    logger.error(f"❌ Failed to connect {self.max_reconnect_attempts} times. Giving up on WebSocket.")
                    logger.info("💡 Falling back to HTTP-only mode. Live prices disabled.")
                    break

    def _get_prev_close(self, symbol):
        """Helper to get previous close from cache."""
        cache = self.fundamental_cache.get(symbol, {})
        history = cache.get("history", pd.DataFrame())
        
        if not history.empty and "Close" in history:
            return history["Close"].iloc[-1]
        return None

    def _fundamental_loop(self):
        """Runs in a separate thread. Fetches Yahoo Finance data every 1 hour."""
        while self.running:
            logger.info("Fetching atomic fundamentals (Yahoo)...")
            
            if not self.symbols:
                time.sleep(10)
                continue
            
            try:
                # Fetch history for RSI calculation
                history_data = yf.download(
                    self.symbols,
                    period="1y",
                    interval="1d",
                    group_by="ticker",
                    threads=False,
                    progress=False,
                    auto_adjust=True
                )
                
                for sym in self.symbols:
                    try:
                        # Extract history
                        if len(self.symbols) > 1:
                            sym_hist = history_data[sym] if sym in history_data else pd.DataFrame()
                        else:
                            sym_hist = history_data
                        
                        # Get ticker object
                        ticker = yf.Ticker(sym)
                        
                        try:
                            # Get all metrics
                            fast_info = ticker.fast_info
                            market_cap = fast_info.market_cap if hasattr(fast_info, "market_cap") else None
                            prev_close = fast_info.previous_close if hasattr(fast_info, "previous_close") else None
                            
                            info = ticker.info
                            
                            pe_ratio = info.get("trailingPE")
                            pb_ratio = info.get("priceToBook")
                            peg_ratio = info.get("pegRatio")
                            dividend_yield = info.get("dividendYield")
                            
                            roe = info.get("returnOnEquity")
                            roa = info.get("returnOnAssets")
                            
                            debt_to_equity = info.get("debtToEquity")
                            current_ratio = info.get("currentRatio")
                            quick_ratio = info.get("quickRatio")
                            
                            gross_margin = info.get("grossMargins")
                            operating_margin = info.get("operatingMargins")
                            profit_margin = info.get("profitMargins")
                            
                            revenue_growth = info.get("revenueGrowth")
                            earnings_growth = info.get("earningsGrowth")
                            
                            volume = info.get("volume")
                            avg_volume = info.get("averageVolume")
                            beta = info.get("beta")
                            
                            week52_high = info.get("fiftyTwoWeekHigh")
                            week52_low = info.get("fiftyTwoWeekLow")
                        
                        except Exception as e:
                            logger.warning(f"Failed to get metrics for {sym}: {e}")
                            market_cap = prev_close = pe_ratio = pb_ratio = peg_ratio = None
                            dividend_yield = roe = roa = debt_to_equity = current_ratio = None
                            quick_ratio = gross_margin = operating_margin = profit_margin = None
                            revenue_growth = earnings_growth = volume = avg_volume = beta = None
                            week52_high = week52_low = None
                        
                        # Calculate RSI
                        rsi_val = self._calculate_rsi(sym_hist, prev_close)
                        
                        # Store in cache (sanitize all numeric values for JSON safety)
                        metadata = self.ticker_metadata.get(sym, {})
                        self.fundamental_cache[sym] = {
                            "history": sym_hist,
                            "constants": {
                                "market_cap": self._safe_float(market_cap),
                                "prev_close": self._safe_float(prev_close),
                                "sector": metadata.get("sector", "Unknown"),
                                "pe_ratio": self._safe_float(pe_ratio),
                                "pb_ratio": self._safe_float(pb_ratio),
                                "peg_ratio": self._safe_float(peg_ratio),
                                "dividend_yield": self._safe_float(dividend_yield),
                                "roe": self._safe_float(roe),
                                "roa": self._safe_float(roa),
                                "debt_to_equity": self._safe_float(debt_to_equity),
                                "current_ratio": self._safe_float(current_ratio),
                                "quick_ratio": self._safe_float(quick_ratio),
                                "gross_margin": self._safe_float(gross_margin),
                                "operating_margin": self._safe_float(operating_margin),
                                "profit_margin": self._safe_float(profit_margin),
                                "revenue_growth": self._safe_float(revenue_growth),
                                "earnings_growth": self._safe_float(earnings_growth),
                                "volume": self._safe_int(volume),
                                "avg_volume": self._safe_int(avg_volume),
                                "beta": self._safe_float(beta),
                                "52week_high": self._safe_float(week52_high),
                                "52week_low": self._safe_float(week52_low),
                                "rsi": round(self._safe_float(rsi_val), 2) if self._safe_float(rsi_val) is not None else None,
                            }
                        }
                        
                        time.sleep(0.5)  # Rate limiting
                    
                    except Exception as e:
                        logger.error(f"Failed to process {sym}: {e}")
                
                self._save_cache()
                logger.info("Fundamentals updated successfully.")
                time.sleep(3600)  # Sleep for 1 hour
            
            except Exception as e:
                logger.error(f"Global fetch failed: {e}")
                time.sleep(60)

    def _calculate_rsi(self, history, current_price):
        """Calculates 14-day RSI."""
        if history.empty or "Close" not in history:
            return None
        
        try:
            closes = history["Close"].tolist()
            if current_price:
                closes.append(current_price)
            
            series = pd.Series(closes)
            delta = series.diff()
            
            gain = delta.where(delta > 0, 0).rolling(window=14).mean()
            loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
            
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            return rsi.iloc[-1]
        except:
            return None

    def _safe_float(self, val):
        """Convert numpy/pandas types to JSON-safe Python floats. Returns None for NaN/inf."""
        if val is None:
            return None
        try:
            f = float(val)
            if f != f or f == float('inf') or f == float('-inf'):  # NaN or inf
                return None
            return f
        except (TypeError, ValueError):
            return None

    def _safe_int(self, val):
        """Convert numpy/pandas types to JSON-safe Python ints. Returns None on failure."""
        if val is None:
            return None
        try:
            f = float(val)
            if f != f or f == float('inf') or f == float('-inf'):
                return None
            return int(f)
        except (TypeError, ValueError):
            return None

    def get_snapshot(self, requested_symbols):
        """Returns the full state for the initial REST load."""
        response = {}
        
        for sym in requested_symbols:
            cache = self.fundamental_cache.get(sym, {})
            constants = cache.get("constants", {})
            
            price = self.live_prices.get(sym)
            if not price:
                price = constants.get("prev_close", 0.0)
            
            price = self._safe_float(price) or 0.0
            prev_close = self._safe_float(constants.get("prev_close", 0.0)) or 0.0
            change = 0.0
            change_p = 0.0
            
            if prev_close and price:
                change = price - prev_close
                change_p = (change / prev_close) * 100

            metadata = self.ticker_metadata.get(sym, {})
            
            response[sym] = {
                "symbol": sym,
                "name": metadata.get("name", sym),
                "price": price,
                "change": round(change, 2),
                "change_percent": round(change_p, 2),
                "sector": constants.get("sector") or metadata.get("sector", "Unknown"),
                "market_cap": self._safe_float(constants.get("market_cap")),
                "pe_ratio": self._safe_float(constants.get("pe_ratio")),
                "price_to_book": self._safe_float(constants.get("pb_ratio")),
                "peg_ratio": self._safe_float(constants.get("peg_ratio")),
                "dividend_yield": self._safe_float(constants.get("dividend_yield")),
                "roe": self._safe_float(constants.get("roe")),
                "roa": self._safe_float(constants.get("roa")),
                "debt_to_equity": self._safe_float(constants.get("debt_to_equity")),
                "current_ratio": self._safe_float(constants.get("current_ratio")),
                "quick_ratio": self._safe_float(constants.get("quick_ratio")),
                "gross_margin": self._safe_float(constants.get("gross_margin")),
                "operating_margin": self._safe_float(constants.get("operating_margin")),
                "profit_margin": self._safe_float(constants.get("profit_margin")),
                "revenue_growth": self._safe_float(constants.get("revenue_growth")),
                "earnings_growth": self._safe_float(constants.get("earnings_growth")),
                "volume": self._safe_int(constants.get("volume")),
                "avg_volume": self._safe_int(constants.get("avg_volume")),
                "beta": self._safe_float(constants.get("beta")),
                "52week_high": self._safe_float(constants.get("52week_high")),
                "52week_low": self._safe_float(constants.get("52week_low")),
                "rsi": self._safe_float(constants.get("rsi")),
            }
        
        return response

    def get_fundamentals(self, symbol: str) -> dict:
        return self.get_snapshot([symbol]).get(symbol, {})

    def get_price_history(self, symbol: str, period: str = "1y") -> list[float]:
        lookbacks = {
            "1mo": 21,
            "3mo": 63,
            "6mo": 126,
            "1y": 252,
        }

        history = self.fundamental_cache.get(symbol, {}).get("history", pd.DataFrame())
        closes: list[float] = []

        if isinstance(history, pd.DataFrame) and not history.empty and "Close" in history:
            closes = [self._safe_float(v) for v in history["Close"].tolist()]
            closes = [v for v in closes if v is not None]

        if not closes:
            try:
                downloaded = yf.download(
                    symbol,
                    period=period,
                    interval="1d",
                    progress=False,
                    auto_adjust=True,
                )
                if isinstance(downloaded, pd.DataFrame) and not downloaded.empty and "Close" in downloaded:
                    closes = [self._safe_float(v) for v in downloaded["Close"].tolist()]
                    closes = [v for v in closes if v is not None]
            except Exception as e:
                logger.warning(f"Failed to fetch price history for {symbol}: {e}")

        days = lookbacks.get(period)
        if days and len(closes) > days:
            return closes[-days:]
        return closes

    def _persist_quant_result(self, strategy_name: str, result: Any) -> None:
        supabase_url = os.getenv("SUPABASE_URL")
        service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if not supabase_url or not service_key:
            return

        try:
            from supabase import create_client
            from quant.scoring.engine import ranking_result_to_dict

            supabase = create_client(supabase_url, service_key)
            payload = {
                "run_date": datetime.now(timezone.utc).date().isoformat(),
                "strategy": strategy_name,
                "rankings_json": ranking_result_to_dict(result),
            }
            supabase.table("quant_rankings").insert(payload).execute()
        except Exception as e:
            logger.warning(f"Unable to persist quant rankings for {strategy_name}: {e}")

    def _build_quant_inputs(self) -> tuple[list[dict], dict[str, list[float]]]:
        symbols = list(self.symbols)
        snapshot = self.get_snapshot(symbols)
        universe_data = list(snapshot.values())
        price_histories = {symbol: self.get_price_history(symbol, period="1y") for symbol in symbols}
        return universe_data, price_histories

    def refresh_quant_rankings(self, strategy: str | None = None) -> None:
        from quant.scoring.config import STRATEGY_CONFIGS
        from quant.scoring.engine import run_scoring_engine

        universe_data, price_histories = self._build_quant_inputs()
        strategy_names = [strategy] if strategy else list(STRATEGY_CONFIGS.keys())

        for strategy_name in strategy_names:
            if strategy_name not in STRATEGY_CONFIGS:
                logger.warning(f"Skipping unknown quant strategy: {strategy_name}")
                continue

            logger.info(f"Running quant scoring for strategy={strategy_name}")
            result = run_scoring_engine(
                universe_data=universe_data,
                price_histories=price_histories,
                weights=STRATEGY_CONFIGS[strategy_name],
                strategy_name=strategy_name,
            )

            with self.quant_lock:
                self.quant_results[strategy_name] = result

            self._persist_quant_result(strategy_name, result)
            logger.info(
                f"Quant scoring complete for strategy={strategy_name}; "
                f"stocks_scored={len(result.ranked_stocks)}"
            )

    def _quant_scoring_loop(self) -> None:
        """Runs quant scoring periodically using the same background-thread pattern as fundamentals."""
        refresh_seconds = max(1, self.quant_refresh_minutes) * 60

        while self.running:
            try:
                if not self.fundamental_cache:
                    logger.info("Quant loop waiting for fundamentals cache to populate...")
                    time.sleep(10)
                    continue

                logger.info("Starting scheduled quant scoring refresh...")
                self.refresh_quant_rankings()
                logger.info("Scheduled quant scoring refresh complete.")
            except Exception as e:
                logger.error(f"Quant scoring loop failed: {e}")

            time.sleep(refresh_seconds)