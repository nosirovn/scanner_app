"""Momentum ignition signal detection."""

from __future__ import annotations

from typing import Dict, List


def detect_ignition(stock: Dict) -> Dict:
    bars: List[Dict] = stock.get("bars_5s", []) or []
    if len(bars) < 4:
        return {"detected": False, "confidence": 0.0}

    closes = [float(b.get("close", 0.0) or 0.0) for b in bars[-4:]]
    volumes = [float(b.get("volume", 0.0) or 0.0) for b in bars[-4:]]

    strong_candles = sum(1 for i in range(1, len(closes)) if closes[i] > closes[i - 1])
    volume_acc = (volumes[-1] / max(1.0, volumes[0])) if volumes[0] > 0 else 0.0
    price_slope = (closes[-1] - closes[0]) / max(0.01, closes[0])

    detected = strong_candles >= 3 and volume_acc >= 1.4 and price_slope >= 0.01
    confidence = min(1.0, (strong_candles / 4.0) * 0.4 + min(1.0, volume_acc / 2.0) * 0.4 + min(1.0, price_slope / 0.03) * 0.2)

    return {"detected": detected, "confidence": round(confidence, 2)}
