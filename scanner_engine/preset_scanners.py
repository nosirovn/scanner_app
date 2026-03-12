"""Preset scanner rules with strict low-price enforcement."""

from __future__ import annotations

from typing import Dict, List

GLOBAL_PRICE_MIN = 0.0
GLOBAL_PRICE_MAX = 500.0
ALLOWED_EXCHANGES = {"NASDAQ", "NYSE", "AMEX", "NMS", "NYQ", "ASE", "SMART"}
MIN_AVG_VOLUME = 500_000

PRESETS: Dict[str, Dict] = {
    "gap_go": {
        "price_max": 20,
        "gap_percent_min": 4,
        "premarket_volume_min": 100_000,
        "relative_volume_min": 2,
        "float_max": 100_000_000,
    },
    "momentum": {
        "price_max": 20,
        "change_min": 7,
        "relative_volume_min": 3,
        "requires_above_vwap": True,
    },
    "high_of_day_break": {
        "price_max": 20,
        "near_hod_pct_max": 1,
        "relative_volume_min": 2,
        "volume_spike_min": 1.2,
    },
    "low_float_runner": {
        "price_max": 20,
        "float_max": 20_000_000,
        "change_min": 10,
        "volume_spike_min": 1.3,
    },
    "vwap_reclaim": {
        "price_max": 20,
        "crossed_above_vwap": True,
        "relative_volume_min": 2,
        "change_min": 3,
    },
}


def passes_global_price_rule(stock: Dict) -> bool:
    price = float(stock.get("price", 0.0) or 0.0)
    return GLOBAL_PRICE_MIN <= price <= GLOBAL_PRICE_MAX


def passes_base_universe(stock: Dict) -> bool:
    if not passes_global_price_rule(stock):
        return False
    exchange = str(stock.get("exchange", "")).upper()
    if exchange and exchange not in ALLOWED_EXCHANGES:
        return False
    avg_volume = float(stock.get("average_volume", 0.0) or 0.0)
    if avg_volume < MIN_AVG_VOLUME:
        return False
    return True


def _is_near_hod(stock: Dict, pct_max: float) -> bool:
    price = float(stock.get("price", 0.0) or 0.0)
    hod = float(stock.get("high", 0.0) or 0.0)
    if price <= 0 or hod <= 0:
        return False
    return ((hod - price) / hod) * 100.0 <= pct_max


def _above_vwap(stock: Dict) -> bool:
    vwap = float(stock.get("vwap", 0.0) or 0.0)
    price = float(stock.get("price", 0.0) or 0.0)
    return price > 0 and vwap > 0 and price >= vwap


def _crossed_above_vwap(stock: Dict) -> bool:
    price = float(stock.get("price", 0.0) or 0.0)
    vwap = float(stock.get("vwap", 0.0) or 0.0)
    prev_price = float(stock.get("prev_price", price) or price)
    if vwap <= 0:
        return False
    return prev_price < vwap <= price


def matches_preset(stock: Dict, preset_name: str) -> bool:
    if not passes_base_universe(stock):
        return False

    preset = PRESETS.get(preset_name)
    if not preset:
        return False

    if float(stock.get("price", 0.0) or 0.0) > float(preset.get("price_max", GLOBAL_PRICE_MAX)):
        return False
    if float(stock.get("gap_percent", 0.0) or 0.0) < float(preset.get("gap_percent_min", 0.0)):
        return False
    if float(stock.get("premarket_volume", 0.0) or 0.0) < float(preset.get("premarket_volume_min", 0.0)):
        return False
    if float(stock.get("relative_volume", 0.0) or 0.0) < float(preset.get("relative_volume_min", 0.0)):
        return False
    if float(stock.get("float_shares", 0.0) or 0.0) > float(preset.get("float_max", 1e18)):
        return False
    if float(stock.get("percent_change", 0.0) or 0.0) < float(preset.get("change_min", -1e9)):
        return False
    if float(stock.get("volume_spike", 0.0) or 0.0) < float(preset.get("volume_spike_min", 0.0)):
        return False

    near_hod = preset.get("near_hod_pct_max")
    if near_hod is not None and not _is_near_hod(stock, float(near_hod)):
        return False

    if preset.get("requires_above_vwap") and not _above_vwap(stock):
        return False
    if preset.get("crossed_above_vwap") and not _crossed_above_vwap(stock):
        return False

    return True


def matching_presets(stock: Dict) -> List[str]:
    return [name for name in PRESETS if matches_preset(stock, name)]
