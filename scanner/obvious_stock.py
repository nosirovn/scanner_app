"""
Obvious Stock detector.
Identifies the single most obvious trading opportunity of the day.
"""

from typing import Optional, Dict
from datetime import datetime

class ObviousStockDetector:
    """Detects the most obvious momentum stock of the day."""

    @staticmethod
    def score_stock(ticker: str, price: float, percent_change: float,
                   rvol: float, float_shares: float, volume: int,
                   catalyst: Optional[str] = None,
                   ema_alignment: str = "↓") -> float:
        """
        Score a stock based on multiple factors.

        Args:
            ticker: Stock symbol
            price: Current price
            percent_change: Percent change
            rvol: Relative volume
            float_shares: Float (shares outstanding)
            volume: Total volume
            catalyst: Type of catalyst (news, earnings, etc.)
            ema_alignment: EMA alignment indicator

        Returns:
            Score (0-100) indicating how "obvious" the stock is
        """
        score = 0

        # Price change (30 points max)
        if percent_change >= 30:
            score += 30
        elif percent_change >= 20:
            score += 25
        elif percent_change >= 15:
            score += 20
        elif percent_change >= 10:
            score += 15
        else:
            score += percent_change * 1.5

        # Relative Volume (25 points max)
        if rvol >= 10:
            score += 25
        elif rvol >= 8:
            score += 22
        elif rvol >= 6:
            score += 18
        elif rvol >= 4:
            score += 12
        else:
            score += rvol * 2

        # Float (20 points max)
        if float_shares < 5_000_000:
            score += 20
        elif float_shares < 10_000_000:
            score += 15
        elif float_shares < 15_000_000:
            score += 10
        else:
            score += 5

        # Volume Acceleration (15 points max)
        if volume >= 500_000:
            score += 15
        elif volume >= 300_000:
            score += 12
        elif volume >= 150_000:
            score += 8
        elif volume >= 50_000:
            score += 4

        # EMA Alignment (10 points max)
        if ema_alignment == "↑↑↑":
            score += 10
        elif ema_alignment == "↑↑":
            score += 7
        elif ema_alignment == "↑":
            score += 4

        # Catalyst bonus (5 points max)
        if catalyst and catalyst in ["news", "earnings", "partnership"]:
            score += 5

        return min(100, score)

    @staticmethod
    def detect_obvious_stock(stocks_data: list) -> Optional[Dict]:
        """
        Find the most obvious stock from a list of candidate stocks.

        Args:
            stocks_data: List of stock data dicts with scoring data

        Returns:
            Most obvious stock data dict, or None
        """
        if not stocks_data:
            return None

        # Score each stock
        scored_stocks = []
        for stock in stocks_data:
            score = ObviousStockDetector.score_stock(
                ticker=stock.get("ticker"),
                price=stock.get("price", 0),
                percent_change=stock.get("percent_change", 0),
                rvol=stock.get("rvol", 0),
                float_shares=stock.get("float", 0),
                volume=stock.get("volume", 0),
                catalyst=stock.get("catalyst"),
                ema_alignment=stock.get("ema_alignment", "↓")
            )
            scored_stocks.append({
                **stock,
                "obvious_score": score
            })

        # Sort by score and return the best
        obvious = max(scored_stocks, key=lambda x: x.get("obvious_score", 0))

        # Only return if score is significant (> 50)
        if obvious.get("obvious_score", 0) >= 50:
            return obvious

        return None

    @staticmethod
    def get_catalyst_icon(catalyst: Optional[str]) -> str:
        """Map catalyst type to emoji icon."""
        catalyst_icons = {
            "news": "📰",
            "earnings": "💰",
            "sec_filing": "📝",
            "unusual_volume": "📈",
            "partnership": "🤝",
            "acquisition": "💼",
            "revenue": "📊"
        }
        return catalyst_icons.get(catalyst, "")

    @staticmethod
    def get_catalyst_summary(catalyst: Optional[str], headline: str = "") -> str:
        """Get 2-sentence summary of catalyst."""
        if catalyst == "news":
            return f"{headline[:80]}... Recent news is driving volume and momentum."
        elif catalyst == "earnings":
            return "Company reported earnings. Strong results driving bullish momentum."
        elif catalyst == "partnership":
            return "New partnership announced. Catalyzing institutional interest and volume surge."
        elif catalyst == "unusual_volume":
            return "Unusual trading volume detected. Smart money accumulating position."
        elif catalyst == "sec_filing":
            return "SEC filing released. Market reacting to regulatory news."
        else:
            return "Significant catalyst detected. Monitor for further developments."
