"""Relative volume calculations for intraday screening."""

from __future__ import annotations


def calculate_relative_volume(current_volume: float, average_volume: float) -> float:
    avg = float(average_volume or 0.0)
    if avg <= 0:
        return 0.0
    return float(current_volume or 0.0) / avg
