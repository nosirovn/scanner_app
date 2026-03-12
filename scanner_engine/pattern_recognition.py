"""Heuristic pattern recognition for intraday momentum setups."""

from __future__ import annotations

from typing import Dict, List


def _slope(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    return values[-1] - values[0]


def detect_pattern(stock: Dict) -> Dict:
    bars = stock.get("bars_5s", []) or []
    closes = [float(b.get("close", 0.0) or 0.0) for b in bars if b.get("close") is not None]
    highs = [float(b.get("high", 0.0) or 0.0) for b in bars if b.get("high") is not None]
    lows = [float(b.get("low", 0.0) or 0.0) for b in bars if b.get("low") is not None]

    if len(closes) < 6:
        return {"name": "None", "confidence": 0.0}

    up_slope = _slope(closes[-6:])
    high_band = max(highs[-6:]) - min(highs[-6:]) if highs[-6:] else 0.0
    low_slope = _slope(lows[-6:]) if lows[-6:] else 0.0

    vwap = float(stock.get("vwap", 0.0) or 0.0)
    price = float(stock.get("price", closes[-1]) or closes[-1])
    prev_price = float(stock.get("prev_price", price) or price)

    if prev_price < vwap <= price and vwap > 0:
        return {"name": "VWAP Reclaim", "confidence": 0.78}

    if high_band > 0 and high_band / max(0.01, closes[-1]) < 0.004 and up_slope > 0:
        return {"name": "Flat Top Breakout", "confidence": 0.74}

    if low_slope > 0 and up_slope > 0:
        return {"name": "Ascending Triangle", "confidence": 0.72}

    if up_slope > 0 and min(closes[-4:]) > min(closes[-8:-4] or closes[-4:]):
        return {"name": "Bull Flag", "confidence": 0.69}

    opening_range_high = float(stock.get("opening_range_high", 0.0) or 0.0)
    if opening_range_high > 0 and price > opening_range_high:
        return {"name": "Opening Range Breakout", "confidence": 0.7}

    return {"name": "None", "confidence": 0.0}
