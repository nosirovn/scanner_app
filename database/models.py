"""
Database models for scanner application.
Uses SQLAlchemy ORM.
"""

from sqlalchemy import Column, Integer, Float, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import pytz

Base = declarative_base()
et = pytz.timezone('US/Eastern')


def _now_et():
    """Return timezone-aware current Eastern time for SQLAlchemy defaults."""
    return datetime.now(et)

class Stock(Base):
    """Stock scan record."""
    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(10), index=True, unique=False)
    company_name = Column(String(200), nullable=True)
    price = Column(Float)
    change = Column(Float)
    percent_change = Column(Float)
    volume = Column(Integer)
    rvol = Column(Float)
    float_shares = Column(Float)
    ema20 = Column(Float)
    ema50 = Column(Float)
    ema200 = Column(Float)
    ema_alignment = Column(String(5))
    entry = Column(Float)
    tp = Column(Float)
    sl = Column(Float)
    risk_reward = Column(Float)
    catalyst = Column(String(50), nullable=True)
    news_headline = Column(Text, nullable=True)
    news_summary = Column(Text, nullable=True)
    news_url = Column(Text, nullable=True)
    session = Column(String(20))
    alert_level = Column(String(20), nullable=True)
    momentum_score = Column(Float)
    obvious_score = Column(Float)
    scan_time = Column(DateTime, default=_now_et)
    created_at = Column(DateTime, default=_now_et)

    class Config:
        from_attributes = True


class Alert(Base):
    """Alert record."""
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(10), index=True)
    alert_level = Column(String(20))  # watch, momentum, hot
    price_at_alert = Column(Float)
    percent_change_at_alert = Column(Float)
    rvol_at_alert = Column(Float)
    entry = Column(Float)
    tp = Column(Float)
    sl = Column(Float)
    message = Column(Text)
    sent_to_telegram = Column(Boolean, default=False)
    triggered_at = Column(DateTime, default=_now_et)
    created_at = Column(DateTime, default=_now_et)

    class Config:
        from_attributes = True


class ScanSession(Base):
    """Scan session record."""
    __tablename__ = "scan_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_type = Column(String(20))  # premarket, market, after_hours
    total_scanned = Column(Integer)
    qualified_stocks = Column(Integer)
    hot_alerts = Column(Integer)
    momentum_alerts = Column(Integer)
    watch_alerts = Column(Integer)
    avg_change = Column(Float)
    top_ticker = Column(String(10), nullable=True)
    started_at = Column(DateTime, default=_now_et)
    ended_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_now_et)

    class Config:
        from_attributes = True


class WatchlistItem(Base):
    """Watchlist entry."""
    __tablename__ = "watchlist"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(10), index=True, unique=True)
    added_at = Column(DateTime, default=_now_et)
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_now_et)

    class Config:
        from_attributes = True


class Trade(Base):
    """Trade record."""
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(10), index=True)
    entry_price = Column(Float)
    entry_time = Column(DateTime)
    exit_price = Column(Float, nullable=True)
    exit_time = Column(DateTime, nullable=True)
    quantity = Column(Integer)
    profit_loss = Column(Float, nullable=True)
    percent_profit_loss = Column(Float, nullable=True)
    status = Column(String(20))  # open, closed, cancelled
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_now_et)

    class Config:
        from_attributes = True


class Settings(Base):
    """Application settings."""
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, index=True)
    value = Column(Text)
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=_now_et, onupdate=_now_et)

    class Config:
        from_attributes = True
