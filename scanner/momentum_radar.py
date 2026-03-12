"""
Momentum Radar module.
Identifies and tracks the top N strongest momentum stocks.
"""

from typing import List, Dict
from datetime import datetime

class MomentumRadar:
    """Real-time momentum tracker for top stocks."""

    @staticmethod
    def calculate_momentum_score(percent_change: float, rvol: float,
                                 volume_accel: float = 1.0) -> float:
        """
        Calculate momentum score for a stock.

        Args:
            percent_change: Percent change (%+)
            rvol: Relative volume
            volume_accel: Volume acceleration factor (1.0 = normal)

        Returns:
            Momentum score (0-100)
        """
        # Price momentum (50 points)
        price_score = min(50, percent_change * 1.5)

        # Volume momentum (30 points)
        volume_score = min(30, rvol * 4)

        # Acceleration (20 points)
        accel_score = min(20, (volume_accel - 1) * 100)

        return round(price_score + volume_score + accel_score, 2)

    @staticmethod
    def get_top_momentum_stocks(stocks_data: list, top_n: int = 5) -> List[Dict]:
        """
        Get top N stocks by momentum.

        Args:
            stocks_data: List of stock data
            top_n: Number of top stocks to return

        Returns:
            List of top momentum stocks sorted by score
        """
        # Score each stock
        scored_stocks = []
        for stock in stocks_data:
            score = MomentumRadar.calculate_momentum_score(
                percent_change=stock.get("percent_change", 0),
                rvol=stock.get("rvol", 0),
                volume_accel=stock.get("volume_accel", 1.0)
            )
            scored_stocks.append({
                **stock,
                "momentum_score": score
            })

        # Sort by score and return top N
        ranked = sorted(scored_stocks, key=lambda x: x["momentum_score"], reverse=True)
        return ranked[:top_n]

    @staticmethod
    def format_momentum_display(stock: Dict) -> str:
        """
        Format stock data for momentum radar display.

        Example:
        🔥 ABCD   +38%   RVOL 9.4
        """
        ticker = stock.get("ticker", "")
        percent = stock.get("percent_change", 0)
        rvol = stock.get("rvol", 0)

        # Get icon based on momentum intensity
        if percent >= 30:
            icon = "🔥"
        elif percent >= 20:
            icon = "⚡"
        else:
            icon = "📈"

        return f"{icon} {ticker:6} +{percent:.1f}%   RVOL {rvol:.1f}"

    @staticmethod
    def detect_momentum_shift(current_leaders: List[Dict],
                             previous_leaders: List[Dict]) -> Dict[str, List[str]]:
        """
        Detect changes in momentum leadership.

        Returns:
            {
                "new_leaders": [tickers],
                "lost_momentum": [tickers],
                "stable": [tickers]
            }
        """
        current_tickers = {s["ticker"] for s in current_leaders}
        previous_tickers = {s["ticker"] for s in previous_leaders}

        return {
            "new_leaders": list(current_tickers - previous_tickers),
            "lost_momentum": list(previous_tickers - current_tickers),
            "stable": list(current_tickers & previous_tickers)
        }

    @staticmethod
    def get_momentum_trend(current_momentum_score: float,
                          previous_momentum_score: float) -> str:
        """
        Determine if momentum is accelerating or decelerating.

        Returns: "📈" (up), "➡️" (stable), "📉" (down)
        """
        diff = current_momentum_score - previous_momentum_score

        if diff > 5:
            return "📈"
        elif diff < -5:
            return "📉"
        else:
            return "➡️"

    @staticmethod
    def update_momentum_queue(stocks_data: list, window_size: int = 10) -> List[Dict]:
        """
        Update momentum tracking queue with newest data.

        Returns:
            List of top N stocks with momentum trend data
        """
        # Sort by momentum
        sorted_stocks = sorted(
            stocks_data,
            key=lambda x: x.get("momentum_score", 0),
            reverse=True
        )

        # Add timestamp
        for stock in sorted_stocks:
            stock["last_updated"] = datetime.now()

        return sorted_stocks[:window_size]
