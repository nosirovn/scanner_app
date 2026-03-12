"""
Configuration module for the Small-Cap Momentum Scanner.
Handles all app settings, API keys, and environment variables.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load only scanner_app/.env to avoid picking up unrelated parent workspace .env.
load_dotenv(dotenv_path=Path(__file__).with_name(".env"), override=True)

# API Keys
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Market Sessions (ET - Eastern Time)
MARKET_SESSIONS = {
    "premarket": {"start": "04:00", "end": "09:30", "color": "🟣"},
    "market": {"start": "09:30", "end": "16:00", "color": "🟢"},
    "after_hours": {"start": "16:00", "end": "20:00", "color": "🔵"}
}

# Scanner Filters (Default)
GLOBAL_PRICE_MIN = 0
GLOBAL_PRICE_MAX = 500
ALLOWED_EXCHANGES = {"NMS", "NYQ", "ASE", "NGM", "NCM", "PCX", "BTS", "NASDAQ", "NYSE", "AMEX"}

SCANNER_FILTERS = {
    "price_min": GLOBAL_PRICE_MIN,
    "price_max": GLOBAL_PRICE_MAX,
    "float_max": 100_000_000,
    "relative_volume_min": 1,
    "volume_min": 500_000,
    "change_min": 1,  # percentage
    "ema_min_arrows": 0,  # 0=all, 1..3 bullish strength
    "news_mode": "all",  # all, with_news, hot_news
    "movers_scan_limit": 100,
    "momentum_change_min": 12,
    "momentum_rvol_min": 5,
    "momentum_float_min": 10_000_000,
    # Backward compatibility for older clients posting the previous name.
    "momentum_float_max": 10_000_000,
}

# Alert Thresholds
ALERT_LEVELS = {
    "watch": {
        "change_min": 8,
        "rvol_min": 3
    },
    "momentum": {
        "change_min": 12,
        "rvol_min": 5,
        "float_max": 10_000_000
    },
    "hot": {
        "change_min": 20,
        "rvol_min": 7,
        "volume_min": 100_000,
        "float_max": 10_000_000,
        "catalyst_required": True
    }
}

# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./scanner.db")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Scanner Settings
SCAN_INTERVAL = 60  # seconds (yfinance rate limit friendly)
MAX_STOCKS_SCAN = 20  # top 20 gainers
MIN_STOCKS_SCAN = 10

# UI Settings
TOP_OBVIOUS_STOCKS = 1
TOP_MOMENTUM_STOCKS = 5
MOMENTUM_UPDATE_INTERVAL = 5  # seconds

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "logs/scanner.log")

# Server
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))

# Data Sources
FINNHUB_BASE_URL = "https://finnhub.io/api/v1"

# IBKR Connectivity
IBKR_HOST = os.getenv("IBKR_HOST", "127.0.0.1")
IBKR_MODE = os.getenv("IBKR_MODE", "paper").lower()  # paper or live
IBKR_PAPER_PORT = int(os.getenv("IBKR_PAPER_PORT", 7497))
IBKR_LIVE_PORT = int(os.getenv("IBKR_LIVE_PORT", 7496))
import random as _random
IBKR_CLIENT_ID = int(os.getenv("IBKR_CLIENT_ID", 0)) or _random.randint(100, 999)

# EMA Periods
EMA_PERIODS = [20, 50, 200]

# Price Levels Configuration
ENTRY_OFFSET = 0.02  # 2% pullback below current price
TP_OFFSET = 0.12  # 12% above entry
SL_OFFSET = -0.03  # -3% below entry

print("✅ Configuration loaded successfully")
