"""Simple bid/ask imbalance detection."""

from __future__ import annotations


def calculate_imbalance(bid: float, ask: float) -> float:
    b = float(bid or 0.0)
    a = float(ask or 0.0)
    if b <= 0 or a <= 0:
        return 0.0
    mid = (a + b) / 2.0
    spread = a - b
    return max(-1.0, min(1.0, 1.0 - (spread / max(0.01, mid))))
