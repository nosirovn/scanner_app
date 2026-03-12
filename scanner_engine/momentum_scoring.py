"""Momentum score engine (0-100)."""

from __future__ import annotations


def _clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _norm(value: float, scale: float) -> float:
    if scale <= 0:
        return 0.0
    return _clip(float(value or 0.0) / scale)


def calculate_momentum_score(
    volume_spike: float,
    relative_volume: float,
    price_change_percent: float,
    float_factor: float,
    pattern_confidence: float,
) -> float:
    """Weighted score based on momentum drivers.

    Formula mapped from requested weighting into a normalized 0-100 composite.
    """
    score = (
        _norm(volume_spike, 3.0) * 30
        + _norm(relative_volume, 6.0) * 25
        + _norm(price_change_percent, 20.0) * 20
        + _norm(float_factor, 1.0) * 15
        + _clip(pattern_confidence) * 10
    )
    return round(max(0.0, min(100.0, score)), 2)
