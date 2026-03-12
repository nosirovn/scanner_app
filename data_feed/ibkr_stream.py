"""IBKR streaming adapter using ib_insync on localhost.

Supports TWS/Gateway paper/live ports and exposes real-time snapshots that
include trades, bid/ask, and 5-second bars.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

try:
    from ib_insync import IB, Stock
except Exception:  # pragma: no cover - optional dependency at runtime
    IB = None
    Stock = None


@dataclass
class MarketSnapshot:
    ticker: str
    price: float
    bid: float = 0.0
    ask: float = 0.0
    volume: float = 0.0
    average_volume: float = 0.0
    percent_change: float = 0.0
    gap_percent: float = 0.0
    premarket_volume: float = 0.0
    exchange: str = ""
    float_shares: float = 0.0
    high: float = 0.0
    low: float = 0.0
    open_price: float = 0.0
    vwap: float = 0.0
    bars_5s: List[Dict] = field(default_factory=list)
    updated_at: datetime = field(default_factory=datetime.utcnow)


class IBKRStream:
    """Thin async wrapper around ib_insync for laptop-local streaming."""

    def __init__(self, host: str = "127.0.0.1", port: int = 7497, client_id: int = 17):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.ib = IB() if IB else None
        self._connected = False
        self._tickers: Dict[str, object] = {}
        self._bar_streams: Dict[str, object] = {}
        self._contracts: Dict[str, object] = {}

    @property
    def connected(self) -> bool:
        return bool(self._connected and self.ib and self.ib.isConnected())

    async def connect(self) -> bool:
        if not self.ib:
            return False
        if self.connected:
            return True

        try:
            await self.ib.connectAsync(
                self.host,
                self.port,
                clientId=self.client_id,
                readonly=True,
                timeout=10,
            )
        except Exception as e:
            import logging
            logging.getLogger("ibkr_stream").warning(
                f"IBKR connectAsync failed: {type(e).__name__}: {e} "
                f"(host={self.host}, port={self.port}, clientId={self.client_id})"
            )
            self._connected = False
            return False

        self._connected = self.ib.isConnected()
        if self._connected:
            self.ib.errorEvent += self._on_error
        return self._connected

    def _on_error(self, reqId, errorCode, errorString, contract):
        """Silently handle non-fatal IBKR error callbacks."""
        pass

    async def disconnect(self) -> None:
        if not self.ib:
            return

        if self.ib.isConnected():
            self.ib.disconnect()
        self._connected = False

    async def subscribe(self, symbols: List[str]) -> None:
        """Subscribe to trade + bid/ask streaming for a list of symbols."""
        if not self.connected:
            ok = await self.connect()
            if not ok:
                return

        symbols = [s.strip().upper() for s in symbols if s and s.strip()]

        for sym in symbols:
            if sym in self._contracts:
                continue
            try:
                contract = Stock(sym, "SMART", "USD")
                qualified = await self.ib.qualifyContractsAsync(contract)
                if not qualified or not contract.conId:
                    continue
                ticker = self.ib.reqMktData(contract, genericTickList="233", snapshot=False)
                self._contracts[sym] = contract
                self._tickers[sym] = ticker
            except Exception:
                continue

    async def unsubscribe(self, symbols: List[str]) -> None:
        if not self.connected:
            return

        for sym in symbols:
            ticker = self._tickers.pop(sym, None)
            contract = self._contracts.pop(sym, None)
            if ticker is not None and contract is not None:
                self.ib.cancelMktData(contract)

    def get_snapshot(self, symbol: str) -> Optional[MarketSnapshot]:
        """Return latest in-memory snapshot for one symbol."""
        sym = symbol.upper()
        ticker = self._tickers.get(sym)
        if ticker is None:
            return None

        import math

        def _safe_float(val, default=0.0):
            v = float(val or default)
            return default if math.isnan(v) or math.isinf(v) else v

        last = _safe_float(ticker.last or ticker.close)
        bid = _safe_float(ticker.bid)
        ask = _safe_float(ticker.ask)
        open_price = _safe_float(ticker.open)
        high = _safe_float(ticker.high, last)
        low = _safe_float(ticker.low, last)
        volume = _safe_float(ticker.volume)
        avg_volume = _safe_float(getattr(ticker, "avVolume", 0.0))

        pct_change = 0.0
        if open_price > 0:
            pct_change = ((last - open_price) / open_price) * 100.0

        return MarketSnapshot(
            ticker=sym,
            price=last,
            bid=bid,
            ask=ask,
            volume=volume,
            average_volume=avg_volume,
            percent_change=pct_change,
            gap_percent=pct_change,
            premarket_volume=volume,
            exchange="SMART",
            float_shares=0.0,
            high=high,
            low=low,
            open_price=open_price,
            updated_at=datetime.utcnow(),
        )

    def get_snapshots(self) -> List[MarketSnapshot]:
        snapshots: List[MarketSnapshot] = []
        for sym in list(self._tickers.keys()):
            snap = self.get_snapshot(sym)
            if snap is not None:
                snapshots.append(snap)
        return snapshots
