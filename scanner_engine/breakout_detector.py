"""Breakout detectors for PM high, HOD, VWAP, and consolidation."""

from __future__ import annotations

from typing import Dict, List


def detect_breakouts(stock: Dict) -> List[Dict]:
    price = float(stock.get("price", 0.0) or 0.0)
    volume_spike = float(stock.get("volume_spike", 0.0) or 0.0)
    out: List[Dict] = []

    pm_high = float(stock.get("premarket_high", 0.0) or 0.0)
    if pm_high > 0 and price > pm_high and volume_spike >= 1.1:
        out.append({"type": "Premarket High", "confidence": min(1.0, 0.6 + (volume_spike - 1.0) * 0.2)})

    hod = float(stock.get("high", 0.0) or 0.0)
    if hod > 0 and price >= hod and volume_spike >= 1.1:
        out.append({"type": "High of Day", "confidence": min(1.0, 0.55 + (volume_spike - 1.0) * 0.25)})

    vwap = float(stock.get("vwap", 0.0) or 0.0)
    prev_price = float(stock.get("prev_price", price) or price)
    if vwap > 0 and prev_price < vwap <= price and volume_spike >= 1.0:
        out.append({"type": "VWAP Reclaim", "confidence": min(1.0, 0.5 + (volume_spike - 1.0) * 0.2)})

    range_high = float(stock.get("consolidation_high", 0.0) or 0.0)
    if range_high > 0 and price > range_high and volume_spike >= 1.2:
        out.append({"type": "Consolidation Range", "confidence": min(1.0, 0.6 + (volume_spike - 1.0) * 0.2)})

    return out
