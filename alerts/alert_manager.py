"""Alert manager for desktop, Telegram, and sound notifications."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Dict, List, Optional

from alerts.telegram_alert import TelegramAlertSystem


class AlertManager:
    def __init__(self, telegram: Optional[TelegramAlertSystem] = None):
        self.telegram = telegram
        self.history: List[Dict] = []

    async def emit(self, alert_type: str, stock: Dict) -> None:
        payload = {
            "type": alert_type,
            "ticker": stock.get("ticker"),
            "price": stock.get("price"),
            "runner_score": stock.get("runner_score"),
            "momentum_score": stock.get("momentum_score"),
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.history.append(payload)
        self.history = self.history[-200:]

        if self.telegram and stock.get("price", 0) <= 20:
            await self.telegram.send_momentum_update([stock])

    def recent(self, limit: int = 50) -> List[Dict]:
        return list(reversed(self.history[-limit:]))
