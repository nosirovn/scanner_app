"""Standalone local AI momentum screener server for IBKR data.

Run with:
python -m uvicorn dashboard.screener_server:app --host 127.0.0.1 --port 5000
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Dict, List, Optional

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse

from alerts.alert_manager import AlertManager
from alerts.telegram_alert import TelegramAlertSystem
from analysis.float_rotation_tracker import calculate_float_rotation
from analysis.relative_volume_calculator import calculate_relative_volume
from analysis.vwap_calculator import calculate_vwap
from data.market_data import MarketDataFetcher
from data_feed.ibkr_stream import IBKRStream, MarketSnapshot
from data_feed.subscription_manager import SubscriptionManager
from dashboard.top_runners_dashboard import render_dashboard
from scanner_engine.breakout_detector import detect_breakouts
from scanner_engine.ignition_detector import detect_ignition
from scanner_engine.momentum_scoring import calculate_momentum_score
from scanner_engine.pattern_recognition import detect_pattern
from scanner_engine.preset_scanners import matching_presets, passes_base_universe, passes_global_price_rule
from scanner_engine.runner_predictor import calculate_runner_score, classify_runner
from scanner_engine.trade_setup_engine import generate_trade_setup
from config import IBKR_HOST, IBKR_MODE, IBKR_PAPER_PORT, IBKR_LIVE_PORT, IBKR_CLIENT_ID

HOST = IBKR_HOST
MODE = (IBKR_MODE or "paper").lower().strip()
active_ibkr_port: Optional[int] = None

def _port_order() -> List[int]:
    if MODE == "live":
        return [IBKR_LIVE_PORT, IBKR_PAPER_PORT]
    return [IBKR_PAPER_PORT, IBKR_LIVE_PORT]

state: Dict = {
    "rows": [],
    "watchlist": [],
    "alerts": [],
}

ib_stream: Optional[IBKRStream] = None
subscription_manager: Optional[SubscriptionManager] = None
alert_manager: Optional[AlertManager] = None
market_data_fallback: Optional[MarketDataFetcher] = None
scanner_task: Optional[asyncio.Task] = None


async def _build_rows(snapshots: List[MarketSnapshot]) -> List[Dict]:
    rows: List[Dict] = []
    for snap in snapshots:
        stock = {
            "ticker": snap.ticker,
            "price": snap.price,
            "bid": snap.bid,
            "ask": snap.ask,
            "volume": snap.volume,
            "average_volume": snap.average_volume,
            "percent_change": snap.percent_change,
            "gap_percent": snap.gap_percent,
            "premarket_volume": snap.premarket_volume,
            "exchange": snap.exchange,
            "float_shares": snap.float_shares,
            "high": snap.high,
            "low": snap.low,
            "bars_5s": snap.bars_5s,
            "prev_price": snap.open_price,
            "vwap": calculate_vwap(snap.bars_5s),
        }
        stock["relative_volume"] = calculate_relative_volume(stock["volume"], stock["average_volume"])
        stock["float_rotation"] = calculate_float_rotation(stock["volume"], stock["float_shares"])
        stock["volume_spike"] = stock["relative_volume"]

        if not passes_global_price_rule(stock):
            continue
        if not passes_base_universe(stock):
            continue

        pattern = detect_pattern(stock)
        stock["pattern"] = pattern["name"]
        stock["pattern_confidence"] = pattern["confidence"]

        breakouts = detect_breakouts(stock)
        stock["breakouts"] = breakouts

        momentum = calculate_momentum_score(
            volume_spike=stock["volume_spike"],
            relative_volume=stock["relative_volume"],
            price_change_percent=stock["percent_change"],
            float_factor=max(0.0, min(1.0, 1.0 - (stock["float_shares"] / 100_000_000 if stock["float_shares"] else 1.0))),
            pattern_confidence=stock["pattern_confidence"],
        )
        stock["momentum_score"] = momentum

        volatility_compression = 0.0
        if stock["high"] > 0:
            volatility_compression = max(0.0, min(1.0, 1.0 - ((stock["high"] - stock["low"]) / stock["high"])))

        runner_score = calculate_runner_score(
            volume_acceleration=stock["volume_spike"],
            float_rotation=stock["float_rotation"],
            relative_volume=stock["relative_volume"],
            volatility_compression=volatility_compression,
            pattern_confidence=stock["pattern_confidence"],
        )
        stock["runner_score"] = runner_score
        stock["runner_label"] = classify_runner(runner_score)

        ignition = detect_ignition(stock)
        stock["ignition"] = ignition

        breakout_type = breakouts[0]["type"] if breakouts else None
        stock["trade_setup"] = generate_trade_setup(stock, breakout_type, stock["pattern"])
        stock["matching_presets"] = matching_presets(stock)

        if (
            breakouts
            or stock["runner_score"] > 80
            or ignition.get("detected")
            or stock["trade_setup"] is not None
        ):
            if alert_manager is not None:
                await alert_manager.emit("signal", stock)

        rows.append(stock)

    rows.sort(key=lambda x: (x.get("runner_score", 0.0), x.get("momentum_score", 0.0)), reverse=True)
    return rows[:10]


async def _scanner_loop() -> None:
    while True:
        try:
            snaps: List[MarketSnapshot] = []
            if ib_stream and ib_stream.connected:
                snaps = ib_stream.get_snapshots()
            state["rows"] = await _build_rows(snaps) if snaps else []
            state["alerts"] = alert_manager.recent(50) if alert_manager else []
        except Exception:
            pass

        await asyncio.sleep(3)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global ib_stream, subscription_manager, alert_manager, market_data_fallback, scanner_task

    market_data_fallback = MarketDataFetcher()
    await market_data_fallback.init()

    telegram = TelegramAlertSystem()
    await telegram.init()
    alert_manager = AlertManager(telegram=telegram)

    ib_stream = None
    global active_ibkr_port
    active_ibkr_port = None
    for idx, port in enumerate(_port_order()):
        candidate = IBKRStream(host=HOST, port=port, client_id=IBKR_CLIENT_ID + idx)
        if await candidate.connect():
            ib_stream = candidate
            active_ibkr_port = port
            break

    if ib_stream is None:
        ib_stream = IBKRStream(host=HOST, port=_port_order()[0], client_id=IBKR_CLIENT_ID)

    subscription_manager = SubscriptionManager(ib_stream, max_symbols=250)

    # Seed universe from existing mover source, then stream those symbols.
    seed = await market_data_fallback.get_movers("gainers", count=250)
    state["watchlist"] = [s.upper() for s in (seed or [])]
    if subscription_manager:
        await subscription_manager.set_symbols(state["watchlist"])

    scanner_task = asyncio.create_task(_scanner_loop())

    try:
        yield
    finally:
        if scanner_task and not scanner_task.done():
            scanner_task.cancel()
            try:
                await scanner_task
            except asyncio.CancelledError:
                pass
        if ib_stream:
            await ib_stream.disconnect()
        if market_data_fallback:
            await market_data_fallback.close()
        if telegram:
            await telegram.close()


app = FastAPI(title="IBKR Momentum Screener", version="1.0.0", lifespan=lifespan)


@app.get("/health")
async def health() -> Dict:
    return {
        "status": "ok",
        "connected_to_ibkr": bool(ib_stream and ib_stream.connected),
        "ibkr_mode": MODE,
        "ibkr_host": HOST,
        "ibkr_port": active_ibkr_port,
        "watchlist_size": len(state.get("watchlist", [])),
        "rows": len(state.get("rows", [])),
        "global_price_rule": "$0-$20",
    }


@app.get("/api/runners/top")
async def top_runners(limit: int = Query(10, ge=1, le=25)) -> List[Dict]:
    return state.get("rows", [])[:limit]


@app.get("/api/trade-setups")
async def trade_setups(limit: int = Query(10, ge=1, le=25)) -> List[Dict]:
    setups = [r for r in state.get("rows", []) if r.get("trade_setup")]
    return setups[:limit]


@app.get("/api/alerts/recent")
async def recent_alerts(limit: int = Query(50, ge=1, le=200)) -> List[Dict]:
    return state.get("alerts", [])[:limit]


@app.get("/api/watchlist")
async def get_watchlist() -> List[str]:
    return state.get("watchlist", [])


@app.post("/api/watchlist/add/{ticker}")
async def add_watchlist_ticker(ticker: str) -> Dict:
    symbol = ticker.strip().upper()
    if not symbol:
        return {"status": "invalid"}

    # Enforce global price rule directly at watchlist add time.
    if market_data_fallback:
        q = await market_data_fallback.get_quote(symbol)
        if q and float(q.get("price") or 0.0) > 20:
            return {"status": "rejected", "reason": "price must be <= $20"}

    if symbol not in state["watchlist"]:
        state["watchlist"].append(symbol)
        if subscription_manager:
            await subscription_manager.set_symbols(state["watchlist"])
    return {"status": "added", "ticker": symbol}


@app.get("/", response_class=HTMLResponse)
async def dashboard_page() -> str:
    return render_dashboard(state.get("rows", []))
