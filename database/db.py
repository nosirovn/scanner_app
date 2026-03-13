"""
Database connection and session management.
"""

from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from config import DATABASE_URL
from database.models import Base
from utils.logger import logger


def _resolve_database_url(db_url: str) -> str:
    """Resolve SQLite relative paths against the scanner_app directory."""
    if not db_url.startswith("sqlite:///"):
        return db_url

    raw_path = db_url.replace("sqlite:///", "", 1)
    if raw_path.startswith("/"):
        return db_url

    base_dir = Path(__file__).resolve().parent.parent
    resolved = (base_dir / raw_path).resolve()
    return f"sqlite:///{resolved}"


RESOLVED_DATABASE_URL = _resolve_database_url(DATABASE_URL)

# Database engine
engine = create_engine(
    RESOLVED_DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in RESOLVED_DATABASE_URL else {},
    poolclass=StaticPool if "sqlite" in RESOLVED_DATABASE_URL else None,
    echo=False
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Initialize database tables."""
    try:
        Base.metadata.create_all(bind=engine)
        _ensure_sqlite_schema_compatibility()
        logger.info(f"Database URL resolved to: {RESOLVED_DATABASE_URL}")
        logger.info("✅ Database initialized successfully")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise


def _ensure_sqlite_schema_compatibility():
    """Backfill missing SQLite columns for legacy database files."""
    if not RESOLVED_DATABASE_URL.startswith("sqlite:///"):
        return

    required_stock_columns = {
        "ticker": "VARCHAR(10)",
        "company_name": "VARCHAR(200)",
        "price": "FLOAT",
        "change": "FLOAT",
        "percent_change": "FLOAT",
        "volume": "INTEGER",
        "rvol": "FLOAT",
        "float_shares": "FLOAT",
        "ema20": "FLOAT",
        "ema50": "FLOAT",
        "ema200": "FLOAT",
        "ema_alignment": "VARCHAR(5)",
        "entry": "FLOAT",
        "tp": "FLOAT",
        "sl": "FLOAT",
        "risk_reward": "FLOAT",
        "catalyst": "VARCHAR(50)",
        "news_headline": "TEXT",
        "news_summary": "TEXT",
        "news_url": "TEXT",
        "session": "VARCHAR(20)",
        "alert_level": "VARCHAR(20)",
        "momentum_score": "FLOAT DEFAULT 0",
        "obvious_score": "FLOAT DEFAULT 0",
        "scan_time": "DATETIME",
        "created_at": "DATETIME",
    }

    with engine.begin() as conn:
        table_exists = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='stocks'")
        ).fetchone()
        if not table_exists:
            return

        rows = conn.execute(text("PRAGMA table_info(stocks)")).fetchall()
        existing_columns = {row[1] for row in rows}

        for column_name, column_type in required_stock_columns.items():
            if column_name in existing_columns:
                continue
            conn.execute(text(f'ALTER TABLE stocks ADD COLUMN "{column_name}" {column_type}'))
            logger.info(f"Added missing SQLite column stocks.{column_name}")

        # Backfill legacy schemas that used different column names.
        if "percent_change" in {row[1] for row in conn.execute(text("PRAGMA table_info(stocks)")).fetchall()}:
            if "change_percent" in existing_columns:
                conn.execute(text(
                    "UPDATE stocks SET percent_change = COALESCE(percent_change, change_percent)"
                ))
            if "relative_volume" in existing_columns:
                conn.execute(text(
                    "UPDATE stocks SET rvol = COALESCE(rvol, relative_volume)"
                ))
            if "float_millions" in existing_columns:
                conn.execute(text(
                    "UPDATE stocks SET float_shares = COALESCE(float_shares, float_millions * 1000000)"
                ))
            if "ema_20" in existing_columns:
                conn.execute(text(
                    "UPDATE stocks SET ema20 = COALESCE(ema20, ema_20)"
                ))
            if "ema_50" in existing_columns:
                conn.execute(text(
                    "UPDATE stocks SET ema50 = COALESCE(ema50, ema_50)"
                ))
            if "ema_200" in existing_columns:
                conn.execute(text(
                    "UPDATE stocks SET ema200 = COALESCE(ema200, ema_200)"
                ))
            if "entry_price" in existing_columns:
                conn.execute(text(
                    "UPDATE stocks SET entry = COALESCE(entry, entry_price)"
                ))
            if "take_profit" in existing_columns:
                conn.execute(text(
                    "UPDATE stocks SET tp = COALESCE(tp, take_profit)"
                ))
            if "stop_loss" in existing_columns:
                conn.execute(text(
                    "UPDATE stocks SET sl = COALESCE(sl, stop_loss)"
                ))
            if "updated_at" in existing_columns:
                conn.execute(text(
                    "UPDATE stocks SET scan_time = COALESCE(scan_time, updated_at)"
                ))

def get_db() -> Session:
    """Get database session for dependency injection."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def close_db():
    """Close database connection."""
    engine.dispose()
    logger.info("Database connection closed")
