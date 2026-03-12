"""
Telegram Alert System.
Sends real-time trading alerts via Telegram Bot.
"""

import aiohttp
import asyncio
from html import escape
from typing import Dict, Optional
from datetime import datetime
import pytz
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from config import GLOBAL_PRICE_MAX
from utils.logger import logger, log_error

class TelegramAlertSystem:
    """Handle Telegram bot messaging for trading alerts."""

    BASE_URL = "https://api.telegram.org"

    def __init__(self):
        self.bot_token = TELEGRAM_BOT_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID
        self.session = None

    async def init(self):
        """Initialize async session."""
        self.session = aiohttp.ClientSession()

    async def close(self):
        """Close async session."""
        if self.session:
            await self.session.close()

    async def send_alert(self, stock: Dict) -> bool:
        """Send hot alert for a stock."""
        try:
            if float(stock.get("price") or 0) > GLOBAL_PRICE_MAX:
                return False

            alert_level = stock.get("alert_level", "").upper()
            if alert_level not in ["HOT", "MOMENTUM"]:
                return False

            # Format message
            message = self._format_alert_message(stock, alert_level)

            # Send via Telegram
            return await self._send_telegram_message(message)

        except Exception as e:
            log_error("telegram_alert.send_alert", str(e))
            return False

    async def send_obvious_stock_alert(self, stock: Dict) -> bool:
        """Send obvious stock notification."""
        try:
            message = self._format_obvious_stock_message(stock)
            return await self._send_telegram_message(message)
        except Exception as e:
            log_error("telegram_alert.send_obvious_stock_alert", str(e))
            return False

    async def send_momentum_update(self, top_stocks: list) -> bool:
        """Send momentum radar update."""
        try:
            eligible = [s for s in (top_stocks or []) if float(s.get("price") or 0) <= GLOBAL_PRICE_MAX]
            message = self._format_momentum_message(eligible)
            return await self._send_telegram_message(message)
        except Exception as e:
            log_error("telegram_alert.send_momentum_update", str(e))
            return False

    async def _send_telegram_message(self, message: str) -> bool:
        """Send message via Telegram API."""
        if not self.session:
            await self.init()

        try:
            url = f"{self.BASE_URL}/bot{self.bot_token}/sendMessage"
            data = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            }

            async with self.session.post(url, json=data) as resp:
                if resp.status == 200:
                    logger.info(f"Telegram alert sent successfully")
                    return True
                else:
                    log_error("telegram_alert._send_telegram_message",
                             f"Status {resp.status}")
                    return False

        except Exception as e:
            log_error("telegram_alert._send_telegram_message", str(e))
            return False

    def _format_alert_message(self, stock: Dict, alert_level: str) -> str:
        """Format stock alert for Telegram."""
        ticker = stock["ticker"]
        company = stock.get("company_name") or ""
        price = stock["price"]
        change = stock["percent_change"]
        volume = stock.get("volume", 0)
        rvol = stock["rvol"]
        float_shares = stock["float"]
        entry = stock["entry"]
        tp = stock["tp"]
        sl = stock["sl"]
        news_headline = stock.get("news_summary") or stock.get("news_headline") or stock.get("catalyst") or ""
        news_url = stock.get("news_url")

        # Format float
        float_str = f"{float_shares/1_000_000:.1f}M" if float_shares >= 1_000_000 else f"{float_shares/1000:.0f}K"

        return self._format_requested_message(ticker, company, price, change, volume, rvol, float_str, news_headline, news_url, entry, tp, sl)

    def _format_requested_message(
        self,
        ticker: str,
        company: str,
        price: float,
        change: float,
        volume: float,
        rvol: float,
        float_str: str,
        news_text: str,
        news_url: Optional[str],
        entry: float,
        tp: float,
        sl: float,
    ) -> str:
        """Format alert message using Telegram HTML styling."""
        volume_m = (float(volume or 0) / 1_000_000) if volume else 0
        summary = (news_text or "").strip()
        if len(summary) > 280:
            summary = f"{summary[:277]}..."

        arrow = "▲" if change >= 0 else "▼"
        company_part = f" ({escape(company)})" if company else ""
        chart_url = f"https://finance.yahoo.com/chart/{escape(ticker)}#eyJpbnRlcnZhbCI6NSwicGVyaW9kaWNpdHkiOjEsInRpbWVVbml0IjoibWludXRlIiwiY2FuZGxlV2lkdGgiOjgsImZsaXBwZWQiOmZhbHNlLCJ2b2x1bWVVbmRlcmxheSI6dHJ1ZX0-"

        line1 = f'🔥 <b><a href="{chart_url}">{escape(ticker)}</a></b>{company_part}'
        line2 = f"<b>${price:.2f}</b>  {arrow} <b>{change:+.1f}%</b>"
        line3 = f"VOL: <b>{volume_m:.1f} M</b>"
        line4 = f"RVOL: <b>{rvol:.1f}x</b>"
        line5 = f"Float: <b>{escape(float_str)}</b>"
        line6 = f"EN: <b><i>${entry:.2f}</i></b>"
        line7 = f"TP: <b><i>${tp:.2f}</i></b>"
        line8 = f"SL: <b><i>${sl:.2f}</i></b>"

        if summary and news_url:
            safe_url = escape(news_url, quote=True)
            news_line = f'News: <a href="{safe_url}">{escape(summary)}</a>'
        elif summary:
            news_line = f'News: {escape(summary)}'
        elif news_url:
            safe_url = escape(news_url, quote=True)
            news_line = f'News: <a href="{safe_url}">Read more</a>'
        else:
            news_line = ''

        parts = [line1, line2, "", line3, line4, line5, "", line6, line7, line8]
        if news_line:
            parts.extend(["", news_line])
        return "\n".join(parts)

    def _format_obvious_stock_message(self, stock: Dict) -> str:
        """Format obvious stock notification."""
        ticker = stock["ticker"]
        company = stock.get("company_name") or ""
        price = stock["price"]
        change = stock["percent_change"]
        volume = stock.get("volume", 0)
        rvol = stock["rvol"]
        float_shares = stock["float"]
        entry = stock.get("entry", price)
        tp = stock.get("tp", price)
        sl = stock.get("sl", price)
        news_headline = stock.get("news_summary") or stock.get("news_headline") or stock.get("catalyst") or ""
        news_url = stock.get("news_url")

        float_str = f"{float_shares/1_000_000:.1f}M" if float_shares >= 1_000_000 else f"{float_shares/1000:.0f}K"
        return self._format_requested_message(ticker, company, price, change, volume, rvol, float_str, news_headline, news_url, entry, tp, sl)

    def _format_momentum_message(self, stocks: list) -> str:
        """Format momentum radar update."""
        if not stocks:
            return "No momentum stocks"

        blocks = []
        for stock in stocks[:10]:
            ticker = stock["ticker"]
            company = stock.get("company_name") or ""
            price = stock["price"]
            change = stock["percent_change"]
            volume = stock.get("volume", 0)
            rvol = stock["rvol"]
            float_shares = stock.get("float", 0)
            entry = stock.get("entry", price)
            tp = stock.get("tp", price)
            sl = stock.get("sl", price)
            news_headline = stock.get("news_summary") or stock.get("news_headline") or stock.get("catalyst") or ""
            news_url = stock.get("news_url")
            float_str = (
                f"{float_shares/1_000_000:.1f}M"
                if float_shares >= 1_000_000
                else f"{float_shares/1000:.0f}K"
            )
            blocks.append(
                self._format_requested_message(ticker, company, price, change, volume, rvol, float_str, news_headline, news_url, entry, tp, sl)
            )

        return "\n\n".join(blocks)

    def _get_catalyst_icon(self, catalyst: Optional[str]) -> str:
        """Get emoji for catalyst type."""
        icons = {
            "news": "📰",
            "earnings": "💰",
            "sec_filing": "📝",
            "unusual_volume": "📈",
            "partnership": "🤝"
        }
        return icons.get(catalyst, "")
