"""IBKR-first market data fetcher for the existing scanner runtime.

Uses localhost TWS/IB Gateway with automatic paper/live fallback.
Falls back to the base MarketDataFetcher behavior when IBKR is unavailable.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Dict, List, Optional

from config import IBKR_CLIENT_ID, IBKR_HOST, IBKR_LIVE_PORT, IBKR_MODE, IBKR_PAPER_PORT
from data.market_data import MarketDataFetcher, _DEFAULT_WATCHLIST
from data_feed.ibkr_stream import IBKRStream, MarketSnapshot
from data_feed.subscription_manager import SubscriptionManager
from utils.logger import logger, log_error


class IBKRMarketDataFetcher(MarketDataFetcher):
    def __init__(self):
        super().__init__()
        self.ibkr_mode = (IBKR_MODE or "paper").lower().strip()
        self.ibkr_stream: Optional[IBKRStream] = None
        self.subscription_manager: Optional[SubscriptionManager] = None
        self.ibkr_port: Optional[int] = None
        self.ibkr_connected = False

    def _port_order(self) -> List[int]:
        if self.ibkr_mode == "live":
            return [IBKR_LIVE_PORT, IBKR_PAPER_PORT]
        return [IBKR_PAPER_PORT, IBKR_LIVE_PORT]

    async def init(self):
        await super().init()
        ports = self._port_order()

        for idx, port in enumerate(ports):
            cid = IBKR_CLIENT_ID + idx
            try:
                logger.info(f"Attempting IBKR connection to {IBKR_HOST}:{port} clientId={cid}")
                stream = IBKRStream(host=IBKR_HOST, port=port, client_id=cid)
                if await stream.connect():
                    self.ibkr_stream = stream
                    self.ibkr_port = port
                    self.ibkr_connected = True
                    self.subscription_manager = SubscriptionManager(stream, max_symbols=100)
                    await self.subscription_manager.set_symbols(_DEFAULT_WATCHLIST[:50])
                    logger.info(f"IBKR connected on {IBKR_HOST}:{port} (mode={self.ibkr_mode}, clientId={cid})")
                    return
                else:
                    logger.warning(f"IBKR connect returned False for {IBKR_HOST}:{port} clientId={cid}")
            except Exception as e:
                log_error("ibkr_market_data.init", f"{IBKR_HOST}:{port} clientId={cid}: {str(e)}")

        self.ibkr_connected = False
        logger.warning("IBKR unavailable; using yfinance fallback")

    async def close(self):
        if self.ibkr_stream:
            await self.ibkr_stream.disconnect()
        self.ibkr_connected = False
        await super().close()

    def get_data_source_status(self) -> Dict:
        return {
            "ibkr_connected": bool(self.ibkr_connected and self.ibkr_stream and self.ibkr_stream.connected),
            "ibkr_host": IBKR_HOST,
            "ibkr_mode": self.ibkr_mode,
            "ibkr_port": self.ibkr_port,
            "fallback": "yfinance",
        }

    def _quote_from_snapshot(self, snap: Optional[MarketSnapshot]) -> Optional[Dict]:
        if not snap:
            return None
        if float(snap.price or 0.0) <= 0:
            return None
        return {
            "price": round(float(snap.price or 0.0), 4),
            "change": round(float(snap.price or 0.0) - float(snap.open_price or 0.0), 4),
            "percent": round(float(snap.percent_change or 0.0), 4),
            "high": float(snap.high or snap.price or 0.0),
            "low": float(snap.low or snap.price or 0.0),
            "open": float(snap.open_price or snap.price or 0.0),
            "volume": int(float(snap.volume or 0.0)),
            "timestamp": datetime.utcnow(),
            "exchange": snap.exchange or "SMART",
            "average_volume": float(snap.average_volume or 0.0),
        }

    async def get_quote(self, symbol: str) -> Optional[Dict]:
        sym = symbol.upper()

        if self.ibkr_connected and self.ibkr_stream and self.subscription_manager:
            try:
                active = sorted(list(self.subscription_manager.active_symbols))
                if sym not in self.subscription_manager.active_symbols:
                    await self.subscription_manager.set_symbols(active + [sym])
                    await asyncio.sleep(0.15)
                snap = self.ibkr_stream.get_snapshot(sym)
                quote = self._quote_from_snapshot(snap)
                if quote:
                    self._quote_cache[sym] = quote
                    self._cache_time = datetime.now()
                    return quote
            except Exception as e:
                log_error("ibkr_market_data.get_quote", f"{sym}: {str(e)}")

        return await super().get_quote(sym)

    async def get_multiple_quotes(self, symbols: List[str]) -> Dict[str, Dict]:
        if not symbols:
            return {}

        normalized_symbols = [s.upper() for s in symbols if s]
        results: Dict[str, Dict] = {}

        if self.ibkr_connected and self.ibkr_stream and self.subscription_manager:
            try:
                merged = sorted(list(set(self.subscription_manager.active_symbols).union(set(normalized_symbols))))
                await self.subscription_manager.set_symbols(merged)
                await asyncio.sleep(0.2)
                for sym in normalized_symbols:
                    quote = self._quote_from_snapshot(self.ibkr_stream.get_snapshot(sym))
                    if quote:
                        results[sym] = quote
                logger.info(f"IBKR quotes: {len(results)}/{len(normalized_symbols)} from IBKR")
            except Exception as e:
                log_error("ibkr_market_data.get_multiple_quotes", str(e))

        missing = [s for s in normalized_symbols if s not in results]
        if missing:
            logger.info(f"Fetching {len(missing)} quotes from yfinance fallback")
            fallback = await super().get_multiple_quotes(missing)
            results.update(fallback)
            logger.info(f"yfinance returned {len(fallback)} quotes")

        if results:
            self._quote_cache.update(results)
            self._cache_time = datetime.now()

        return results

    async def get_movers(self, market_type: str = "gainers", count: int = 20):
        # Always use yfinance screener for DISCOVERY of movers
        # (IBKR snapshots only cover previously subscribed symbols)
        screener_movers = await super().get_movers(market_type=market_type, count=count)
        logger.info(f"Screener discovered {len(screener_movers or [])} movers")

        if self.ibkr_connected and self.ibkr_stream and self.subscription_manager:
            # Subscribe discovered movers via IBKR for real-time data
            try:
                all_syms = list(set((screener_movers or []) + list(self.subscription_manager.active_symbols)))
                await self.subscription_manager.set_symbols(all_syms[:100])
            except Exception as e:
                log_error("ibkr_market_data.get_movers", f"subscribe: {str(e)}")

        return screener_movers
