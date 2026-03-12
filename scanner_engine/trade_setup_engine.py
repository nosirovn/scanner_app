"""Trade setup generation with risk/reward validation."""

from __future__ import annotations

from typing import Dict, Optional


def _rr(entry: float, stop: float, target: float) -> float:
    risk = entry - stop
    reward = target - entry
    if risk <= 0:
        return 0.0
    return reward / risk


def generate_trade_setup(stock: Dict, breakout_type: Optional[str], pattern_name: str) -> Optional[Dict]:
    price = float(stock.get("price", 0.0) or 0.0)
    if price <= 0:
        return None

    setup_name = None
    if breakout_type:
        setup_name = "Breakout"
    elif pattern_name == "VWAP Reclaim":
        setup_name = "VWAP Reclaim"
    elif pattern_name == "Bull Flag":
        setup_name = "Bull Flag"
    else:
        return None

    entry = price
    stop = round(entry * 0.97, 4)
    target = round(entry * 1.06, 4)
    rr = _rr(entry, stop, target)
    if rr < 2:
        target = round(entry + (entry - stop) * 2.2, 4)
        rr = _rr(entry, stop, target)

    if rr < 2:
        return None

    return {
        "setup": setup_name,
        "entry": round(entry, 4),
        "stop_loss": stop,
        "target": target,
        "risk_reward": round(rr, 2),
    }
