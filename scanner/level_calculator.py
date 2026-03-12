"""
Trading level calculator.
Calculates Entry, Take Profit, and Stop Loss levels.
"""

from typing import Dict, Tuple
from config import ENTRY_OFFSET, TP_OFFSET, SL_OFFSET
import statistics

class LevelCalculator:
    """Calculate trading levels based on price and EMA alignment."""

    @staticmethod
    def calculate_levels(current_price: float, ema20: float,
                        ema50: float, ema200: float) -> Dict[str, float]:
        """
        Calculate Entry, TP, and SL based on current price and EMAs.

        Returns:
            {
                "entry": float,
                "tp": float,
                "sl": float
            }
        """
        # Pullback entry: target a retracement below current price.
        pullback_price = current_price * (1 - ENTRY_OFFSET)
        support_candidates = [pullback_price]

        # Prefer the nearest EMA support below current price when available.
        for ema in (ema20, ema50, ema200):
            if ema and ema > 0 and ema < current_price:
                support_candidates.append(ema)

        entry = max(support_candidates)

        # TP: higher target
        tp = current_price * (1 + TP_OFFSET)

        # SL: below current price
        sl = current_price * (1 + SL_OFFSET)

        # Adjust based on EMA alignment for better risk/reward
        ema_avg = statistics.mean([ema20, ema50, ema200])

        # If price is above all EMAs, more aggressive TP
        if current_price > ema200 and current_price > ema50 and current_price > ema20:
            tp = tp * 1.08  # 8% boost to TP

        # If price is below key EMA, adjust SL higher (tighter)
        if current_price < ema50:
            sl = current_price * (1 - 0.015)  # -1.5% instead of -3%

        return {
            "entry": round(entry, 2),
            "tp": round(tp, 2),
            "sl": round(sl, 2),
            "risk_reward_ratio": round((tp - entry) / (entry - sl), 2) if entry != sl else 0
        }

    @staticmethod
    def calculate_ema(prices: list, period: int) -> float:
        """
        Calculate Exponential Moving Average.

        Args:
            prices: List of closing prices (oldest first)
            period: EMA period (20, 50, 200, etc.)

        Returns:
            Current EMA value
        """
        if len(prices) < period:
            # Not enough data, return simple average
            return sum(prices) / len(prices) if prices else 0

        # Calculate multiplier
        multiplier = 2 / (period + 1)

        # Initialize SMA
        sma = sum(prices[:period]) / period

        # Calculate EMA
        ema = sma
        for price in prices[period:]:
            ema = price * multiplier + ema * (1 - multiplier)

        return ema

    @staticmethod
    def get_ema_alignment(price: float, ema20: float,
                         ema50: float, ema200: float) -> Tuple[str, str]:
        """
        Determine EMA alignment.

        Returns:
            (alignment_text, arrow_symbol)
            Examples:
            - ("↑↑↑", "price above all EMAs")
            - ("↑↑", "above EMA20 and EMA50")
            - ("↑", "above EMA20 only")
            - ("↓", "below EMAs")
        """
        above_ema20 = price > ema20
        above_ema50 = price > ema50
        above_ema200 = price > ema200

        count_above = sum([above_ema20, above_ema50, above_ema200])

        if count_above == 3:
            return "↑↑↑", "Bullish alignment (above all EMAs)"
        elif count_above == 2:
            return "↑↑", "Strong bullish (above 2 EMAs)"
        elif count_above == 1:
            return "↑", "Weak bullish (above 1 EMA)"
        else:
            return "↓", "Bearish (below EMAs)"

    @staticmethod
    def calculate_trend_strength(ema20: float, ema50: float,
                                 ema200: float) -> float:
        """
        Calculate trend strength score (0-100).
        Higher = stronger uptrend.
        """
        if ema200 == 0:
            return 0

        score = 0

        # EMA alignment points
        if ema50 > ema200:
            score += 25  # 50 above 200
        if ema20 > ema50:
            score += 25  # 20 above 50
        if ema20 > ema200:
            score += 25  # 20 above 200

        # Distance from EMA200
        distance_pct = (ema20 - ema200) / ema200 * 100
        if distance_pct > 0:
            score += min(25, distance_pct)  # Up to 25 points

        return min(100, score)
