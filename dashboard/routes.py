"""
FastAPI routes for the scanner dashboard.
Includes WebSocket support for real-time updates.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from typing import List, Dict, Optional
from datetime import datetime
import json
import asyncio
import pytz

from database.db import get_db
from database.models import Stock, Alert, ScanSession, WatchlistItem
from scanner.scanner_engine import ScannerEngine
from scanner.momentum_radar import MomentumRadar
from scanner.obvious_stock import ObviousStockDetector
from alerts.telegram_alert import TelegramAlertSystem
from data.market_data import MarketDataFetcher
from config import SCAN_INTERVAL, SCANNER_FILTERS, GLOBAL_PRICE_MAX, GLOBAL_PRICE_MIN
from utils.logger import logger

router = APIRouter()

# Global instances
market_data_fetcher = None
scanner_engine = None
telegram_alerts = None


def _passes_extra_filters(stock: Stock) -> bool:
    """Apply EMA/news criteria stored in SCANNER_FILTERS."""
    ema_min_arrows = int(SCANNER_FILTERS.get("ema_min_arrows", 0))
    ema_alignment = stock.ema_alignment or ""
    ema_arrows = ema_alignment.count("↑")

    if ema_min_arrows == -1 and ema_alignment != "↓":
        return False
    if ema_min_arrows > 0 and ema_arrows < ema_min_arrows:
        return False

    news_mode = SCANNER_FILTERS.get("news_mode", "all")
    has_news = bool(stock.news_summary or stock.news_headline or stock.catalyst)
    if news_mode == "with_news" and not has_news:
        return False

    return True

async def init_services(shared_market_data_fetcher, shared_scanner_engine, shared_telegram_alerts):
    """Attach app-owned service instances for route handlers/websockets."""
    global market_data_fetcher, scanner_engine, telegram_alerts
    market_data_fetcher = shared_market_data_fetcher
    scanner_engine = shared_scanner_engine
    telegram_alerts = shared_telegram_alerts

# ============ API Endpoints ============

@router.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

@router.get("/api/session/current")
async def get_current_session(db: Session = Depends(get_db)):
    """Get current market session info."""
    session_type, seconds_until_next = market_data_fetcher.get_current_session()
    now_et = datetime.now(pytz.timezone("US/Eastern"))
    now_gmt5 = now_et.astimezone(pytz.FixedOffset(300))

    # Convert seconds to HH:MM:SS
    hours, remainder = divmod(int(seconds_until_next), 3600)
    minutes, seconds = divmod(remainder, 60)
    countdown = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    return {
        "current_session": session_type,
        "countdown_to_next": countdown,
        "seconds_until_next": seconds_until_next,
        "clock": {
            "et": now_et.strftime("%Y-%m-%d %H:%M:%S"),
            "gmt_plus_5": now_gmt5.strftime("%Y-%m-%d %H:%M:%S"),
        }
    }

@router.get("/api/scanner/status")
async def scanner_status(db: Session = Depends(get_db)):
    """Get scanner status and statistics."""
    # Get latest scan session
    latest_session = db.query(ScanSession).order_by(
        ScanSession.started_at.desc()
    ).first()

    return {
        "running": True,
        "last_scan": latest_session.started_at if latest_session else None,
        "stats": {
            "qualified": latest_session.qualified_stocks if latest_session else 0,
            "hot_alerts": latest_session.hot_alerts if latest_session else 0,
            "momentum_alerts": latest_session.momentum_alerts if latest_session else 0
        }
    }

@router.get("/api/stocks/top")
async def get_top_stocks(
    session: str = Query("market"),
    limit: int = Query(10),
    db: Session = Depends(get_db)
):
    """Get top stocks for a session."""
    candidates = db.query(Stock).filter(
        Stock.session == session,
        Stock.price >= max(SCANNER_FILTERS["price_min"], GLOBAL_PRICE_MIN),
        Stock.price <= min(SCANNER_FILTERS["price_max"], GLOBAL_PRICE_MAX),
        Stock.float_shares <= SCANNER_FILTERS["float_max"],
        Stock.rvol >= SCANNER_FILTERS["relative_volume_min"],
        Stock.volume >= SCANNER_FILTERS["volume_min"],
        Stock.percent_change >= SCANNER_FILTERS["change_min"]
    ).order_by(
        Stock.percent_change.desc()
    ).all()
    stocks = [s for s in candidates if _passes_extra_filters(s)][:limit]

    return [
        {
            "ticker": s.ticker,
            "company_name": s.company_name,
            "price": s.price,
            "percent_change": s.percent_change,
            "rvol": s.rvol,
            "volume": s.volume,
            "float": s.float_shares,
            "ema_alignment": s.ema_alignment,
            "entry": s.entry,
            "tp": s.tp,
            "sl": s.sl,
            "catalyst": s.catalyst,
            "news_headline": s.news_headline,
            "news_summary": s.news_summary,
            "news_url": s.news_url,
            "alert_level": s.alert_level
        }
        for s in stocks
    ]

@router.get("/api/stocks/momentum")
async def get_momentum_stocks(
    limit: int = Query(10),
    session: str = Query("auto"),
    db: Session = Depends(get_db)
):
    """Get top momentum stocks."""
    effective_session = session
    if effective_session == "auto":
        detected_session = "market"
        if market_data_fetcher:
            detected_session, _ = market_data_fetcher.get_current_session()
        effective_session = detected_session if detected_session != "closed" else "market"

    candidates = db.query(Stock).filter(
        Stock.session == effective_session,
        Stock.price >= max(SCANNER_FILTERS["price_min"], GLOBAL_PRICE_MIN),
        Stock.price <= min(SCANNER_FILTERS["price_max"], GLOBAL_PRICE_MAX),
        Stock.float_shares <= SCANNER_FILTERS["float_max"],
        Stock.rvol >= SCANNER_FILTERS["relative_volume_min"],
        Stock.volume >= SCANNER_FILTERS["volume_min"],
        Stock.percent_change >= SCANNER_FILTERS["change_min"]
    ).order_by(
        Stock.momentum_score.desc()
    ).all()
    stocks = [s for s in candidates if _passes_extra_filters(s)][:limit]

    return [
        {
            "ticker": s.ticker,
            "company_name": s.company_name,
            "price": s.price,
            "percent_change": s.percent_change,
            "rvol": s.rvol,
            "volume": s.volume,
            "float": s.float_shares,
            "entry": s.entry,
            "tp": s.tp,
            "sl": s.sl,
            "catalyst": s.catalyst,
            "news_headline": s.news_headline,
            "news_summary": s.news_summary,
            "news_url": s.news_url,
            "alert_level": s.alert_level,
            "momentum_score": s.momentum_score
        }
        for s in stocks
    ]

@router.get("/api/stocks/obvious")
async def get_obvious_stock(
    session: str = Query("auto"),
    db: Session = Depends(get_db)
):
    """Get obvious stock of the day."""
    effective_session = session
    if effective_session == "auto":
        detected_session = "market"
        if market_data_fetcher:
            detected_session, _ = market_data_fetcher.get_current_session()
        effective_session = detected_session if detected_session != "closed" else "market"

    candidates = db.query(Stock).filter(
        Stock.session == effective_session,
        Stock.price >= max(SCANNER_FILTERS["price_min"], GLOBAL_PRICE_MIN),
        Stock.price <= min(SCANNER_FILTERS["price_max"], GLOBAL_PRICE_MAX),
        Stock.float_shares <= SCANNER_FILTERS["float_max"],
        Stock.rvol >= SCANNER_FILTERS["relative_volume_min"],
        Stock.volume >= SCANNER_FILTERS["volume_min"],
        Stock.percent_change >= SCANNER_FILTERS["change_min"]
    ).order_by(
        Stock.obvious_score.desc()
    ).all()

    stock = next((s for s in candidates if _passes_extra_filters(s)), None)

    if not stock:
        return None

    return {
        "ticker": stock.ticker,
        "price": stock.price,
        "percent_change": stock.percent_change,
        "rvol": stock.rvol,
        "float": stock.float_shares,
        "obvious_score": stock.obvious_score,
        "catalyst": stock.catalyst
    }

@router.get("/api/alerts/recent")
async def get_recent_alerts(limit: int = Query(10), db: Session = Depends(get_db)):
    """Get recent alerts."""
    alerts = db.query(Alert).order_by(
        Alert.triggered_at.desc()
    ).limit(limit).all()

    return [
        {
            "id": a.id,
            "ticker": a.ticker,
            "alert_level": a.alert_level,
            "price": a.price_at_alert,
            "percent_change": a.percent_change_at_alert,
            "rvol": a.rvol_at_alert,
            "triggered_at": a.triggered_at.isoformat()
        }
        for a in alerts
    ]

@router.post("/api/watchlist/add/{ticker}")
async def add_to_watchlist(ticker: str, db: Session = Depends(get_db)):
    """Add stock to watchlist."""
    normalized_ticker = ticker.strip().upper()
    quote = await market_data_fetcher.get_quote(normalized_ticker) if market_data_fetcher else None
    if quote and (quote.get("price") is None or quote.get("price") > GLOBAL_PRICE_MAX):
        return {"status": "rejected", "reason": f"price must be <= ${GLOBAL_PRICE_MAX}"}

    existing = db.query(WatchlistItem).filter(
        WatchlistItem.ticker == normalized_ticker
    ).first()

    if existing:
        return {"status": "already_exists"}

    item = WatchlistItem(ticker=normalized_ticker)
    db.add(item)
    db.commit()

    return {"status": "added"}

@router.get("/api/watchlist")
async def get_watchlist(db: Session = Depends(get_db)):
    """Get watchlist."""
    items = db.query(WatchlistItem).filter(
        WatchlistItem.is_active == True
    ).all()

    return [{"ticker": i.ticker, "added_at": i.added_at.isoformat()} for i in items]

@router.post("/api/settings/{key}")
async def update_setting(key: str, value: str, db: Session = Depends(get_db)):
    """Update application setting."""
    from database.models import Settings

    setting = db.query(Settings).filter(Settings.key == key).first()

    if setting:
        setting.value = value
    else:
        setting = Settings(key=key, value=value)
        db.add(setting)

    db.commit()
    return {"status": "updated"}

# ============ WebSocket Endpoints ============

@router.websocket("/ws/scanner")
async def websocket_scanner(websocket: WebSocket, db: Session = Depends(get_db)):
    """WebSocket for real-time scanner updates."""
    await websocket.accept()
    logger.info("WebSocket scanner connected")

    try:
        while True:
            # Wait for scan interval
            await asyncio.sleep(SCAN_INTERVAL)

            # Publish latest snapshot from DB. Scanning is owned by app.background_scanner.
            session_type, _ = market_data_fetcher.get_current_session()

            if session_type != "closed":
                candidates = db.query(Stock).filter(
                    Stock.session == session_type,
                    Stock.price >= max(SCANNER_FILTERS["price_min"], GLOBAL_PRICE_MIN),
                    Stock.price <= min(SCANNER_FILTERS["price_max"], GLOBAL_PRICE_MAX),
                    Stock.float_shares <= SCANNER_FILTERS["float_max"],
                    Stock.rvol >= SCANNER_FILTERS["relative_volume_min"],
                    Stock.volume >= SCANNER_FILTERS["volume_min"],
                    Stock.percent_change >= SCANNER_FILTERS["change_min"],
                ).order_by(Stock.percent_change.desc()).all()
                stocks = [s for s in candidates if _passes_extra_filters(s)][:20]

                payload_stocks = [
                    {
                        "ticker": s.ticker,
                        "company_name": s.company_name,
                        "price": s.price,
                        "percent_change": s.percent_change,
                        "rvol": s.rvol,
                    }
                    for s in stocks
                ]

                # Get momentum stocks
                momentum_stocks = MomentumRadar.get_top_momentum_stocks(payload_stocks, 10)

                # Get obvious stock
                obvious_stock = ObviousStockDetector.detect_obvious_stock(payload_stocks)

                # Send update
                update = {
                    "type": "scanner_update",
                    "session": session_type,
                    "total_stocks": len(payload_stocks),
                    "momentum_stocks": [
                        {
                            "ticker": s.get("ticker"),
                            "price": s.get("price"),
                            "percent_change": s.get("percent_change"),
                            "rvol": s.get("rvol")
                        }
                        for s in momentum_stocks
                    ],
                    "obvious_stock": {
                        "ticker": obvious_stock.get("ticker"),
                        "price": obvious_stock.get("price"),
                        "percent_change": obvious_stock.get("percent_change"),
                        "rvol": obvious_stock.get("rvol")
                    } if obvious_stock else None,
                    "timestamp": datetime.now().isoformat()
                }

                await websocket.send_json(update)

    except (WebSocketDisconnect, Exception) as e:
        if not isinstance(e, WebSocketDisconnect):
            logger.error(f"WebSocket error: {e}")
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
        logger.info("WebSocket scanner disconnected")

@router.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    """WebSocket for real-time alert updates."""
    await websocket.accept()
    logger.info("WebSocket alerts connected")

    try:
        while True:
            # Wait for alerts (would come from scanner in production)
            await asyncio.sleep(5)
            # Placeholder for alert streaming
            pass

    except (WebSocketDisconnect, Exception) as e:
        if not isinstance(e, WebSocketDisconnect):
            logger.error(f"WebSocket alerts error: {e}")
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
        logger.info("WebSocket alerts disconnected")
