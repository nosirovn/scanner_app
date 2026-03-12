"""
Main FastAPI application for Small-Cap Momentum Scanner.
"""

from fastapi import FastAPI, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from pydantic import BaseModel
from datetime import datetime
import pytz

from config import HOST, PORT, SCAN_INTERVAL, SCANNER_FILTERS, GLOBAL_PRICE_MAX, GLOBAL_PRICE_MIN
from database.db import init_db, SessionLocal
from database.models import Stock
from dashboard.routes import router as dashboard_router, init_services
from data.ibkr_market_data import IBKRMarketDataFetcher
from scanner.scanner_engine import ScannerEngine
from scanner.momentum_radar import MomentumRadar
from alerts.telegram_alert import TelegramAlertSystem
from utils.logger import logger

# Global instances
market_data_fetcher = None
scanner_engine = None
telegram_alerts = None
scanner_restart_event = asyncio.Event()
scan_lock = asyncio.Lock()
active_scan_task = None
background_scanner_task = None
settings_version = 0

et_tz = pytz.timezone("US/Eastern")
gmt5_tz = pytz.FixedOffset(300)
scan_runtime = {
    "in_progress": False,
    "trigger": None,
    "detected_session": None,
    "effective_session": None,
    "forced": False,
    "started_at": None,
    "completed_at": None,
    "result_count": 0,
    "last_error": None,
    "settings_version": 0,
}


class ScannerSettings(BaseModel):
    price_min: float
    price_max: float
    float_max: float
    relative_volume_min: float
    volume_min: float
    change_min: float
    ema_min_arrows: int = 0
    news_mode: str = "all"
    movers_scan_limit: int = 100
    momentum_change_min: float = 12
    momentum_rvol_min: float = 5
    momentum_float_min: float = 10_000_000

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle with explicit startup and shutdown cleanup."""
    global market_data_fetcher, scanner_engine, telegram_alerts, background_scanner_task

    logger.info("🚀 Starting Small-Cap Momentum Scanner...")
    init_db()

    market_data_fetcher = IBKRMarketDataFetcher()
    await market_data_fetcher.init()

    scanner_engine = ScannerEngine(market_data_fetcher)
    telegram_alerts = TelegramAlertSystem()
    await telegram_alerts.init()

    await init_services(market_data_fetcher, scanner_engine, telegram_alerts)
    logger.info("✅ All services initialized")

    background_scanner_task = asyncio.create_task(background_scanner())

    try:
        yield
    finally:
        logger.info("🛑 Shutting down scanner...")

        if background_scanner_task and not background_scanner_task.done():
            background_scanner_task.cancel()
            try:
                await background_scanner_task
            except asyncio.CancelledError:
                pass

        if market_data_fetcher:
            await market_data_fetcher.close()

        if telegram_alerts:
            await telegram_alerts.close()

        logger.info("✅ Shutdown complete")


# Initialize FastAPI app
app = FastAPI(
    title="Small-Cap Momentum Scanner",
    description="Real-time stock momentum scanning and trading alerts",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ Background Tasks ============

def save_stocks_to_db(stocks, session_type):
    """Persist scanned stocks to the database (upsert by ticker+session)."""
    db = SessionLocal()
    try:
        # Keep the DB aligned with the current screener output for the session.
        # This prevents stale symbols from previous settings from appearing in the UI.
        current_tickers = {s["ticker"] for s in stocks}
        session_rows = db.query(Stock).filter(Stock.session == session_type).all()
        for row in session_rows:
            if row.ticker not in current_tickers:
                db.delete(row)

        for s in stocks:
            existing = db.query(Stock).filter(
                Stock.ticker == s["ticker"],
                Stock.session == session_type
            ).first()
            if existing:
                for k, v in [
                    ("company_name", s.get("company_name")),
                    ("price", s["price"]), ("change", s.get("change")),
                    ("percent_change", s["percent_change"]), ("volume", s.get("volume")),
                    ("rvol", s.get("rvol")), ("float_shares", s.get("float")),
                    ("ema20", s.get("ema20")), ("ema50", s.get("ema50")),
                    ("ema200", s.get("ema200")), ("ema_alignment", s.get("ema_alignment")),
                    ("entry", s.get("entry")), ("tp", s.get("tp")), ("sl", s.get("sl")),
                    ("catalyst", s.get("catalyst")),
                    ("news_headline", s.get("news_headline")),
                    ("news_summary", s.get("news_summary")),
                    ("news_url", s.get("news_url")),
                    ("alert_level", s.get("alert_level")),
                    ("momentum_score", s.get("momentum_score", 0)),
                    ("obvious_score", s.get("obvious_score", 0)),
                ]:
                    setattr(existing, k, v)
            else:
                db.add(Stock(
                    ticker=s["ticker"], company_name=s.get("company_name"),
                    price=s["price"], change=s.get("change"),
                    percent_change=s["percent_change"], volume=s.get("volume"),
                    rvol=s.get("rvol"), float_shares=s.get("float"),
                    ema20=s.get("ema20"), ema50=s.get("ema50"), ema200=s.get("ema200"),
                    ema_alignment=s.get("ema_alignment"), entry=s.get("entry"),
                    tp=s.get("tp"), sl=s.get("sl"), catalyst=s.get("catalyst"),
                    news_headline=s.get("news_headline"),
                    news_summary=s.get("news_summary"),
                    news_url=s.get("news_url"),
                    session=session_type,
                    alert_level=s.get("alert_level"),
                    momentum_score=s.get("momentum_score", 0),
                    obvious_score=s.get("obvious_score", 0),
                ))
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"DB save error: {e}")
    finally:
        db.close()

async def wait_for_next_scan():
    """Wait for either the next interval or a manual restart request."""
    try:
        await asyncio.wait_for(scanner_restart_event.wait(), timeout=SCAN_INTERVAL)
        logger.info("Scanner restart triggered by settings update")
        scanner_restart_event.clear()
    except asyncio.TimeoutError:
        pass


def _iso(dt):
    return dt.isoformat() if dt else None


def _public_scan_runtime():
    return {
        "in_progress": scan_runtime["in_progress"],
        "trigger": scan_runtime["trigger"],
        "detected_session": scan_runtime["detected_session"],
        "effective_session": scan_runtime["effective_session"],
        "forced": scan_runtime["forced"],
        "started_at": _iso(scan_runtime["started_at"]),
        "completed_at": _iso(scan_runtime["completed_at"]),
        "result_count": scan_runtime["result_count"],
        "last_error": scan_runtime["last_error"],
        "settings_version": scan_runtime["settings_version"],
    }


async def run_scan_now(trigger: str, allow_closed: bool = False):
    """Run one scan cycle and persist results.

    If the detected session is closed and allow_closed=True, force a market-style
    scan to immediately refresh results after settings changes.
    """
    global settings_version

    async with scan_lock:
        session_type, _ = market_data_fetcher.get_current_session()
        effective_session = session_type
        forced = False

        if session_type == "closed" and allow_closed:
            effective_session = "market"
            forced = True

        if effective_session == "closed":
            scan_runtime.update({
                "in_progress": False,
                "trigger": trigger,
                "detected_session": session_type,
                "effective_session": effective_session,
                "forced": False,
                "started_at": None,
                "completed_at": datetime.now(et_tz),
                "result_count": 0,
                "last_error": None,
                "settings_version": settings_version,
            })
            return []

        scan_runtime.update({
            "in_progress": True,
            "trigger": trigger,
            "detected_session": session_type,
            "effective_session": effective_session,
            "forced": forced,
            "started_at": datetime.now(et_tz),
            "last_error": None,
            "settings_version": settings_version,
        })

        try:
            logger.info(f"Running scan ({trigger}) for {effective_session}...")
            stocks = await scanner_engine.scan_session(effective_session)
            save_stocks_to_db(stocks, effective_session)
            await process_alerts(stocks)

            scan_runtime.update({
                "in_progress": False,
                "completed_at": datetime.now(et_tz),
                "result_count": len(stocks),
                "last_error": None,
            })
            return stocks

        except Exception as e:
            scan_runtime.update({
                "in_progress": False,
                "completed_at": datetime.now(et_tz),
                "result_count": 0,
                "last_error": str(e),
            })
            raise

async def background_scanner():
    """Background task that continuously scans for momentum stocks."""
    logger.info("Background scanner started")

    while True:
        try:
            stocks = await run_scan_now("interval", allow_closed=False)
            if stocks:
                logger.info(f"Scan complete: {len(stocks)} stocks qualified")

            await wait_for_next_scan()

        except Exception as e:
            logger.error(f"Background scanner error: {e}")
            await asyncio.sleep(30)

async def process_alerts(stocks):
    """Process stocks and send momentum radar updates."""
    try:
        alert_candidates = [
            s for s in (stocks or [])
            if str(s.get("alert_level") or "").lower() in {"hot", "momentum"}
        ]
        for stock in alert_candidates:
            sent = await telegram_alerts.send_alert(stock)
            if sent:
                logger.info(f"Telegram stock alert sent: {stock.get('ticker')} ({stock.get('alert_level')})")

        momentum_stocks = MomentumRadar.get_top_momentum_stocks(stocks, top_n=10)

        # Send dynamic momentum radar update from current top momentum stocks.
        if momentum_stocks:
            sent = await telegram_alerts.send_momentum_update(momentum_stocks)
            if sent:
                logger.info(f"Momentum update sent: {len(momentum_stocks)} stocks")
            else:
                logger.warning("Momentum update was not delivered to Telegram")

    except Exception as e:
        logger.error(f"Alert processing error: {e}")

# ============ API Routes ============

app.include_router(dashboard_router)

# ============ Static Files & Templates ============

# Mount static files
static_dir = Path(__file__).parent / "dashboard" / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Serve main dashboard
@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serve main dashboard HTML."""
    template_path = Path(__file__).parent / "dashboard" / "templates" / "index.html"
    if template_path.exists():
        return FileResponse(template_path)
    else:
        return HTMLResponse("<h1>Dashboard template not found</h1>", status_code=404)

# ============ Health Check ============

@app.get("/health")
async def health():
    """Health check endpoint."""
    data_source = market_data_fetcher.get_data_source_status() if market_data_fetcher and hasattr(market_data_fetcher, "get_data_source_status") else {"ibkr_connected": False}
    return {
        "status": "healthy",
        "service": "Small-Cap Momentum Scanner",
        "version": "1.0.0",
        "data_source": data_source,
    }

@app.get("/api/debug/ibkr")
async def debug_ibkr():
    """Debug endpoint: show IBKR snapshot data for subscribed symbols."""
    if not market_data_fetcher or not hasattr(market_data_fetcher, "ibkr_stream"):
        return {"error": "no ibkr_stream"}
    stream = market_data_fetcher.ibkr_stream
    if not stream or not stream.connected:
        return {"error": "ibkr not connected", "ibkr_connected": False}
    snaps = stream.get_snapshots()
    return {
        "ibkr_connected": True,
        "subscribed_symbols": len(stream._tickers),
        "snapshots_with_price": len([s for s in snaps if s.price > 0]),
        "snapshots": [
            {
                "ticker": s.ticker,
                "price": s.price,
                "open": s.open_price,
                "volume": s.volume,
                "pct_change": round(s.percent_change, 2),
            }
            for s in sorted(snaps, key=lambda x: x.percent_change, reverse=True)[:20]
        ],
    }

@app.get("/api/scanner/settings")
async def get_scanner_settings():
    """Return current scanner filter settings."""
    return SCANNER_FILTERS

@app.post("/api/scanner/settings")
async def update_scanner_settings(settings: ScannerSettings):
    """Update scanner filters and trigger an immediate re-scan."""
    global settings_version, active_scan_task

    normalized = settings.dict()

    # Backward compatibility: accept float in millions from UI (e.g., 20 => 20M) or absolute shares.
    float_max = normalized.get("float_max", 0)
    if 1 <= float_max <= 2_000:
        normalized["float_max"] = float(float_max) * 1_000_000
    momentum_float_min = normalized.get("momentum_float_min", normalized.get("momentum_float_max", 10_000_000))
    if 5 <= momentum_float_min <= 500 and int(momentum_float_min) % 5 == 0:
        normalized["momentum_float_min"] = int(momentum_float_min) * 1_000_000

    # Backward compatibility for volume units from older UI revisions.
    volume_min = normalized.get("volume_min", 0)
    if 10 <= volume_min <= 50 and int(volume_min) % 5 == 0:
        normalized["volume_min"] = int(volume_min) * 1_000
    elif 10_000_000 <= volume_min <= 100_000_000 and int(volume_min) % 5_000_000 == 0:
        normalized["volume_min"] = int(volume_min / 1_000)

    # Sanitize price bounds.
    normalized["price_min"] = max(GLOBAL_PRICE_MIN, float(normalized["price_min"]))
    normalized["price_max"] = min(GLOBAL_PRICE_MAX, float(normalized["price_max"]))

    if normalized["price_min"] < 0 or normalized["price_max"] <= 0:
        raise HTTPException(status_code=400, detail="price values must be positive and price_min >= 0")
    if normalized["price_min"] >= normalized["price_max"]:
        raise HTTPException(status_code=400, detail="price_min must be less than price_max")
    float_max_value = float(normalized["float_max"])
    if float_max_value < 1_000_000 or float_max_value > 2_000_000_000:
        raise HTTPException(status_code=400, detail="float_max must be between 1M and 2B")
    if normalized["change_min"] < 1 or normalized["change_min"] > 10:
        raise HTTPException(status_code=400, detail="change_min must be in range 1 to 10")
    if normalized["volume_min"] < 10_000 or normalized["volume_min"] > 2_000_000:
        raise HTTPException(status_code=400, detail="volume_min must be 10K to 2M")
    rvol_min = float(normalized["relative_volume_min"])
    if rvol_min <= 0 or rvol_min > 500:
        raise HTTPException(status_code=400, detail="relative_volume_min must be greater than 0 and <= 500")
    if normalized["ema_min_arrows"] not in {0, 1, 2, 3}:
        raise HTTPException(status_code=400, detail="ema_min_arrows must be one of 0,1,2,3")
    if normalized.get("news_mode") == "hot_news":
        normalized["news_mode"] = "with_news"
    if normalized["news_mode"] not in {"all", "with_news"}:
        raise HTTPException(status_code=400, detail="news_mode must be all or with_news")
    if normalized["movers_scan_limit"] < 20 or normalized["movers_scan_limit"] > 1000:
        raise HTTPException(status_code=400, detail="movers_scan_limit must be between 20 and 1000")
    if normalized["momentum_change_min"] < 0 or normalized["momentum_rvol_min"] < 0:
        raise HTTPException(status_code=400, detail="momentum thresholds must be non-negative")
    if normalized["momentum_float_min"] <= 0:
        raise HTTPException(status_code=400, detail="momentum_float_min must be positive")

    # Maintain legacy key for backward compatibility across routes/components.
    normalized["momentum_float_max"] = normalized["momentum_float_min"]

    SCANNER_FILTERS.update(normalized)
    settings_version += 1
    scan_runtime["settings_version"] = settings_version
    scanner_restart_event.set()
    logger.info(f"Scanner settings updated: {SCANNER_FILTERS}")

    if active_scan_task and not active_scan_task.done():
        await active_scan_task
    else:
        active_scan_task = asyncio.create_task(
            run_scan_now("settings_update", allow_closed=True)
        )
        await active_scan_task

    return {
        "status": "updated",
        "filters": SCANNER_FILTERS,
        "scan_status": _public_scan_runtime(),
    }


@app.get("/api/scanner/run-status")
async def get_scanner_run_status():
    """Expose latest scan run status for frontend sync after settings updates."""
    now_et = datetime.now(et_tz)
    now_gmt5 = now_et.astimezone(gmt5_tz)
    data_source = (
        market_data_fetcher.get_data_source_status()
        if market_data_fetcher and hasattr(market_data_fetcher, "get_data_source_status")
        else {"ibkr_connected": False}
    )
    return {
        "scan": _public_scan_runtime(),
        "data_source": data_source,
        "clock": {
            "et": now_et.strftime("%Y-%m-%d %H:%M:%S ET"),
            "gmt_plus_5": now_gmt5.strftime("%Y-%m-%d %H:%M:%S GMT+5"),
        }
    }

@app.post("/api/test-telegram")
async def test_telegram():
    """Send a test Telegram notification (live server)."""
    if not telegram_alerts or not telegram_alerts.bot_token or not telegram_alerts.chat_id:
        raise HTTPException(status_code=400, detail="Telegram not configured")
    sample = {
        "ticker": "CVI",
        "company_name": "CVR Energy Inc.",
        "price": 18.37,
        "percent_change": 10.3,
        "volume": 12_100_000,
        "rvol": 13.8,
        "float": 29_300_000,
        "entry": 28.94,
        "tp": 31.77,
        "sl": 27.52,
        "news_headline": "Calumet reports strategic update and balance sheet milestone with improved guidance. The company announced a major restructuring plan aimed at reducing costs.",
        "news_url": "https://finance.yahoo.com/",
    }
    ok = await telegram_alerts.send_momentum_update([sample])
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to send Telegram test")
    return {"ok": True, "message": "Test notification sent!"}

# ============ Run Application ============

if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting server on {HOST}:{PORT}")

    uvicorn.run(
        "app:app",
        host=HOST,
        port=PORT,
        reload=False,
        log_level="info"
    )
