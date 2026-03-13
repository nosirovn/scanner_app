"""
Market data fetcher using yfinance (Yahoo Finance).
Retrieves real-time quotes, news, and fundamental data. No API key needed.
"""

import asyncio
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import pytz
import yfinance as yf
from utils.logger import logger, log_error

# Top small-cap watchlist used as fallback for "movers" since yfinance
# doesn't have a dedicated movers endpoint.
_DEFAULT_WATCHLIST = [
    "SOFI", "LCID", "RIVN", "NIO", "GRAB", "OPEN", "PLTR", "F", "CCL", "AAL",
    "GOLD", "KGC", "VALE", "PBR", "SIRI", "RKLB", "JOBY", "ACHR", "HOOD", "UBER",
    "LYFT", "SNAP", "PINS", "CHPT", "QS", "RUN", "SPWR", "ARRY", "RIOT", "CLSK",
    "HUT", "BITF", "MARA", "WULF", "IONQ", "ASTS", "DNA", "BBAI", "SOUN", "FUBO",
    "WBD", "PYPL", "AFRM", "UPST", "NOK", "BB", "TLRY", "CGC", "SNDL"
]

class MarketDataFetcher:
    def __init__(self):
        self.et = pytz.timezone('US/Eastern')
        # Batch quote cache: {symbol: quote_dict}, refreshed each bulk fetch
        self._quote_cache: Dict[str, Dict] = {}
        self._cache_time: Optional[datetime] = None
        self._cache_ttl_seconds = 60
        # Profile + candles cache (hourly refresh)
        self._profile_cache: Dict[str, Dict] = {}
        self._candles_cache: Dict[str, List] = {}
        self._slow_cache_time: Optional[datetime] = None
        self._slow_cache_ttl = 3600  # 1 hour
        # Semaphore: max 3 concurrent yfinance calls
        self._sem = asyncio.Semaphore(3)

    async def init(self):
        """No-op: yfinance doesn't need session init."""
        pass

    async def close(self):
        """No-op: yfinance doesn't need cleanup."""
        pass

    def _is_cache_valid(self) -> bool:
        if not self._cache_time:
            return False
        return (datetime.now() - self._cache_time).total_seconds() < self._cache_ttl_seconds

    def _is_slow_cache_valid(self) -> bool:
        if not self._slow_cache_time:
            return False
        return (datetime.now() - self._slow_cache_time).total_seconds() < self._slow_cache_ttl

    async def _run(self, fn):
        """Run a blocking function with the rate-limit semaphore."""
        async with self._sem:
            result = await asyncio.get_event_loop().run_in_executor(None, fn)
            await asyncio.sleep(0.5)  # small pause between calls
            return result

    async def _bulk_fetch_quotes(self, symbols: List[str]) -> Dict[str, Dict]:
        """Fetch all quotes in a single yfinance batch download."""
        def _fetch():
            results = {}

            def _extract_series(frame, field: str, symbol: str, chunk_size: int):
                if frame is None or frame.empty:
                    return None

                columns = getattr(frame, "columns", None)
                if columns is None:
                    return None

                # yfinance 1.x always returns multi-index columns: (field, symbol)
                if getattr(columns, "nlevels", 1) > 1:
                    if field not in frame.columns.get_level_values(0):
                        return None
                    field_df = frame[field]
                    if symbol not in field_df.columns:
                        return None
                    return field_df[symbol].dropna()

                # Flat columns fallback (legacy yfinance)
                if field in frame.columns:
                    return frame[field].dropna()

                return None

            chunks = [symbols[i:i + 10] for i in range(0, len(symbols), 10)]
            for chunk in chunks:
                try:
                    tickers = yf.download(
                        " ".join(chunk),
                        period="5d",
                        interval="1d",
                        progress=False,
                        threads=False,
                        auto_adjust=True,
                    )
                except Exception as e:
                    log_error("market_data._bulk_fetch_quotes", f"chunk={chunk}: {str(e)}")
                    continue

                if tickers is None or tickers.empty:
                    continue

                for sym in chunk:
                    try:
                        close_series = _extract_series(tickers, "Close", sym, len(chunk))
                        if close_series is None or len(close_series) < 2:
                            continue

                        price = float(close_series.iloc[-1])
                        prev = float(close_series.iloc[-2])
                        change = price - prev
                        pct = (change / prev * 100) if prev else 0

                        vol_series = _extract_series(tickers, "Volume", sym, len(chunk))
                        high_series = _extract_series(tickers, "High", sym, len(chunk))
                        low_series = _extract_series(tickers, "Low", sym, len(chunk))
                        open_series = _extract_series(tickers, "Open", sym, len(chunk))

                        vol = int(vol_series.iloc[-1]) if vol_series is not None and len(vol_series) else None
                        high = float(high_series.iloc[-1]) if high_series is not None and len(high_series) else None
                        low = float(low_series.iloc[-1]) if low_series is not None and len(low_series) else None
                        opn = float(open_series.iloc[-1]) if open_series is not None and len(open_series) else None

                        results[sym] = {
                            "price": round(price, 4),
                            "change": round(change, 4),
                            "percent": round(pct, 4),
                            "high": high,
                            "low": low,
                            "open": opn,
                            "volume": vol,
                            "timestamp": datetime.now(self.et),
                        }
                    except Exception as e:
                        log_error("market_data._bulk_fetch_quotes", f"{sym}: {str(e)}")

            return results
        return await asyncio.get_event_loop().run_in_executor(None, _fetch)

    async def get_quote(self, symbol: str) -> Optional[Dict]:
        """Get quote from cache if available, else single fetch."""
        if symbol in self._quote_cache and self._is_cache_valid():
            return self._quote_cache[symbol]
        try:
            def _fetch():
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="5d", interval="1d")
                if hist.empty or len(hist) < 2:
                    return None
                price = float(hist["Close"].iloc[-1])
                prev = float(hist["Close"].iloc[-2])
                change = price - prev
                pct = (change / prev * 100) if prev else 0
                vol = hist["Volume"].iloc[-1]
                return {
                    "price": round(price, 4),
                    "change": round(change, 4),
                    "percent": round(pct, 4),
                    "high": float(hist["High"].iloc[-1]),
                    "low": float(hist["Low"].iloc[-1]),
                    "open": float(hist["Open"].iloc[-1]),
                    "volume": int(vol) if vol == vol else 0,  # NaN guard
                    "timestamp": datetime.now(self.et)
                }
            result = await self._run(_fetch)
            if result:
                self._quote_cache[symbol] = result
            return result
        except Exception as e:
            log_error("market_data.get_quote", f"{symbol}: {str(e)}")
        return None

    async def get_candles(self, symbol: str, resolution: str = "D",
                         count: int = 200) -> Optional[List[Dict]]:
        """Get historical candles (OHLCV) via yfinance. Cached for 1 hour."""
        cache_key = f"{symbol}_{resolution}"
        if cache_key in self._candles_cache and self._is_slow_cache_valid():
            return self._candles_cache[cache_key]
        try:
            interval_map = {"1": "1m", "5": "5m", "15": "15m", "30": "30m",
                            "60": "60m", "D": "1d", "W": "1wk", "M": "1mo"}
            interval = interval_map.get(resolution, "1d")
            period = f"{count}d" if resolution == "D" else "60d"

            def _fetch():
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period=period, interval=interval)
                if hist.empty:
                    return None
                candles = []
                for ts, row in hist.iterrows():
                    vol = row["Volume"]
                    candles.append({
                        "timestamp": ts.to_pydatetime(),
                        "open": float(row["Open"]),
                        "high": float(row["High"]),
                        "low": float(row["Low"]),
                        "close": float(row["Close"]),
                        "volume": int(vol) if vol == vol else 0
                    })
                return candles
            result = await self._run(_fetch)
            if result:
                self._candles_cache[cache_key] = result
                self._slow_cache_time = datetime.now()
            return result
        except Exception as e:
            log_error("market_data.get_candles", f"{symbol}: {str(e)}")
        return None

    async def get_news(self, symbol: str, limit: int = 5) -> Optional[List[Dict]]:
        """Get latest news for a symbol via yfinance."""
        try:
            def _fetch():
                ticker = yf.Ticker(symbol)
                news = ticker.news or []
                results = []
                for item in news[:limit]:
                    content = item.get("content", {})
                    pub_date = content.get("pubDate", "")
                    try:
                        ts = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
                    except Exception:
                        ts = datetime.now()
                    results.append({
                        "headline": content.get("title", ""),
                        "summary": content.get("summary", ""),
                        "url": (content.get("canonicalUrl") or {}).get("url", ""),
                        "timestamp": ts,
                        "source": (content.get("provider") or {}).get("displayName", "Yahoo Finance")
                    })
                return results
            return await self._run(_fetch)
        except Exception as e:
            log_error("market_data.get_news", f"{symbol}: {str(e)}")
        return None

    async def get_company_profile(self, symbol: str) -> Optional[Dict]:
        """Get company profile and fundamental data via yfinance. Cached for 1 hour."""
        if symbol in self._profile_cache and self._is_slow_cache_valid():
            return self._profile_cache[symbol]
        try:
            def _fetch():
                info = yf.Ticker(symbol).info
                shares = info.get("sharesOutstanding")
                float_shares = info.get("floatShares") or (shares * 0.3 if shares else None)
                return {
                    "name": info.get("shortName") or info.get("longName"),
                    "exchange": info.get("exchange"),
                    "currency": info.get("currency"),
                    "ipo": info.get("ipoExpectedDate"),
                    "market_cap": info.get("marketCap"),
                    "average_volume": info.get("averageVolume") or info.get("averageDailyVolume10Day") or 0,
                    "shares_outstanding": shares,
                    "float": float_shares,
                }
            result = await self._run(_fetch)
            if result:
                self._profile_cache[symbol] = result
                self._slow_cache_time = datetime.now()
            return result
        except Exception as e:
            log_error("market_data.get_company_profile", f"{symbol}: {str(e)}")
        return None

    async def get_movers(self, market_type: str = "gainers", count: int = 20) -> Optional[List[str]]:
        """
        Get top movers. Uses yfinance screener, falls back to static watchlist.
        No bulk download in fallback to avoid rate limits.
        """
        try:
            def _fetch():
                symbols_set = set()
                # Try small_cap_gainers first (more relevant for momentum scanning)
                for screen_name in ["small_cap_gainers", "day_gainers"]:
                    try:
                        screener = yf.screen(screen_name, count=count)
                        quotes = screener.get("quotes", [])
                        for q in quotes:
                            sym = q.get("symbol")
                            if sym:
                                symbols_set.add(sym)
                    except Exception:
                        pass
                if symbols_set:
                    return list(symbols_set)[:count]
                # Fallback: return static watchlist (no bulk download)
                return _DEFAULT_WATCHLIST[:count]
            return await self._run(_fetch)
        except Exception as e:
            log_error("market_data.get_movers", f"{market_type}: {str(e)}")
        return _DEFAULT_WATCHLIST[:count]

    async def get_multiple_quotes(self, symbols: List[str]) -> Dict[str, Dict]:
        """Fetch all quotes in one batch call and populate cache."""
        results = await self._bulk_fetch_quotes(symbols)
        if results:
            self._quote_cache.update(results)
            self._cache_time = datetime.now()
        return results

    def get_current_session(self) -> Tuple[str, float]:
        """
        Determine current market session based on ET time.
        Returns: (session_name, seconds_until_next_session)
        """
        now = datetime.now(self.et)
        current_time = now.time()

        # Session times
        premarket_start = datetime.strptime("04:00", "%H:%M").time()
        market_start = datetime.strptime("09:30", "%H:%M").time()
        market_end = datetime.strptime("16:00", "%H:%M").time()
        after_hours_end = datetime.strptime("20:00", "%H:%M").time()

        # Determine current session
        if premarket_start <= current_time < market_start:
            session = "premarket"
            next_time = market_start
        elif market_start <= current_time < market_end:
            session = "market"
            next_time = market_end
        elif market_end <= current_time < after_hours_end:
            session = "after_hours"
            # Next session is premarket (next day)
            next_time = premarket_start
            next_dt = (now + timedelta(days=1)).replace(
                hour=premarket_start.hour,
                minute=premarket_start.minute,
                second=0,
                microsecond=0,
            )
        else:
            # Outside market hours
            session = "closed"
            next_time = premarket_start
            if current_time < premarket_start:
                next_dt = now.replace(
                    hour=premarket_start.hour,
                    minute=premarket_start.minute,
                    second=0,
                    microsecond=0,
                )
            else:
                next_dt = (now + timedelta(days=1)).replace(
                    hour=premarket_start.hour,
                    minute=premarket_start.minute,
                    second=0,
                    microsecond=0,
                )

        # Calculate seconds until next session
        if session == "premarket" or session == "market" or session == "after_hours":
            next_dt = now.replace(hour=next_time.hour, minute=next_time.minute, second=0, microsecond=0)
            if next_dt <= now:
                next_dt = next_dt + timedelta(days=1)

        seconds_until_next = (next_dt - now).total_seconds()

        return session, seconds_until_next
