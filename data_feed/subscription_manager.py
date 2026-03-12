"""Subscription orchestration for IBKR market data streams."""

from __future__ import annotations

from typing import List, Set

from data_feed.ibkr_stream import IBKRStream


class SubscriptionManager:
    def __init__(self, stream: IBKRStream, max_symbols: int = 300):
        self.stream = stream
        self.max_symbols = max_symbols
        self.active_symbols: Set[str] = set()

    async def set_symbols(self, symbols: List[str]) -> List[str]:
        normalized = [s.strip().upper() for s in symbols if s and s.strip()]
        target = set(normalized[: self.max_symbols])

        to_add = sorted(list(target - self.active_symbols))
        to_remove = sorted(list(self.active_symbols - target))

        if to_remove:
            await self.stream.unsubscribe(to_remove)
        if to_add:
            await self.stream.subscribe(to_add)

        self.active_symbols = target
        return sorted(list(self.active_symbols))
