"""
Logging utility for the scanner application.
"""

import logging
import os
from pathlib import Path
from config import LOG_LEVEL, LOG_FILE

# Create logs directory if it doesn't exist
log_dir = Path(LOG_FILE).parent
log_dir.mkdir(parents=True, exist_ok=True)

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def log_scanner_event(event_type: str, ticker: str, data: dict):
    """Log scanner events with structured data."""
    logger.info(f"[{event_type}] {ticker}: {data}")

def log_alert(alert_level: str, ticker: str, details: str):
    """Log alert events."""
    logger.warning(f"[{alert_level.upper()}] {ticker}: {details}")

def log_error(component: str, error: str):
    """Log error events."""
    logger.error(f"[{component}] {error}")
