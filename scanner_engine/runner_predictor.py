"""Runner probability model and labels."""

from __future__ import annotations


def _clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _norm(value: float, scale: float) -> float:
    if scale <= 0:
        return 0.0
    return _clip(float(value or 0.0) / scale)


def calculate_runner_score(
    volume_acceleration: float,
    float_rotation: float,
    relative_volume: float,
    volatility_compression: float,
    pattern_confidence: float,
) -> float:
    score = (
        _norm(volume_acceleration, 2.0) * 30
        + _norm(float_rotation, 1.0) * 25
        + _norm(relative_volume, 6.0) * 20
        + _norm(volatility_compression, 1.0) * 15
        + _clip(pattern_confidence) * 10
    )
    return round(max(0.0, min(100.0, score)), 2)


def classify_runner(score: float) -> str:
    if score >= 85:
        return "EXTREME RUNNER"
    if score >= 70:
        return "HIGH RUNNER"
    if score >= 55:
        return "POTENTIAL RUNNER"
    return "WATCH"
