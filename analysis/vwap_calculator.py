"""VWAP utilities for intraday bars."""

from __future__ import annotations

from typing import Dict, List


def calculate_vwap(bars: List[Dict]) -> float:
    if not bars:
        return 0.0
    pv = 0.0
    vv = 0.0
    for bar in bars:
        high = float(bar.get("high", 0.0) or 0.0)
        low = float(bar.get("low", 0.0) or 0.0)
        close = float(bar.get("close", 0.0) or 0.0)
        volume = float(bar.get("volume", 0.0) or 0.0)
        typical = (high + low + close) / 3.0 if (high or low or close) else close
        pv += typical * volume
        vv += volume
    if vv <= 0:
        return 0.0
    return pv / vv
