"""Float rotation metrics."""

from __future__ import annotations


def calculate_float_rotation(volume: float, float_shares: float) -> float:
    f = float(float_shares or 0.0)
    if f <= 0:
        return 0.0
    return float(volume or 0.0) / f
