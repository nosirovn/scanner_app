"""
Main Scanner Engine.
Orchestrates real-time scanning, filtering, and ranking of momentum stocks.
"""

import asyncio
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import pytz

from config import (
    SCANNER_FILTERS,
    ALERT_LEVELS,
    EMA_PERIODS,
    SCAN_INTERVAL,
    GLOBAL_PRICE_MIN,
    GLOBAL_PRICE_MAX,
    ALLOWED_EXCHANGES,
)
from data.market_data import MarketDataFetcher
from scanner.level_calculator import LevelCalculator
from scanner.obvious_stock import ObviousStockDetector
from scanner.momentum_radar import MomentumRadar
from utils.logger import logger, log_scanner_event, log_alert, log_error

class ScannerEngine:
    """Main scanning engine for momentum stock detection."""

    def __init__(self, market_data_fetcher: MarketDataFetcher):
        self.market_data = market_data_fetcher
        self.et = pytz.timezone('US/Eastern')
        self.current_session = None
        self.session_data = {
            "premarket": [],
            "market": [],
            "after_hours": []
        }
        self.previous_leaders = []
        self.obvious_stock = None

    async def scan_session(self, session_type: str = "market") -> List[Dict]:
        """
        Perform complete scan for a market session.

        Args:
            session_type: 'premarket', 'market', or 'after_hours'

        Returns:
            List of qualifying stocks with full analysis
        """
        try:
            logger.info(f"Starting {session_type} scan...")

            # Get top gainers
            movers_scan_limit = int(SCANNER_FILTERS.get("movers_scan_limit", 100))
            gainers = await self.market_data.get_movers("gainers", count=movers_scan_limit)
            if not gainers:
                logger.warning(f"No gainers retrieved for {session_type}")
                return []

            symbols_to_scan = gainers[:movers_scan_limit]

            # Pre-fetch all quotes in ONE batch call to avoid rate limits
            logger.info(f"Batch fetching quotes for {len(symbols_to_scan)} symbols...")
            bulk_quotes = await self.market_data.get_multiple_quotes(symbols_to_scan)
            if not bulk_quotes:
                logger.warning("No quotes returned from batch fetch; skipping this scan cycle")
                return []

            symbols_with_quotes = [s for s in symbols_to_scan if s in bulk_quotes]
            if not symbols_with_quotes:
                logger.warning("Batch fetch returned no matching symbols to analyze")
                return []

            # Fetch detailed data for top gainers (quotes now served from cache)
            scanned_stocks = await self._process_stocks(symbols_with_quotes, session_type)
            logger.info(f"Analysis complete: {len(scanned_stocks)}/{len(symbols_with_quotes)} stocks passed analysis")

            # Log top candidates before filtering for debugging
            by_change = sorted(scanned_stocks, key=lambda x: x["percent_change"], reverse=True)
            for s in by_change[:10]:
                logger.info(
                    f"  Pre-filter: {s['ticker']} price=${s['price']:.2f} chg={s['percent_change']:.1f}% "
                    f"vol={s['volume']:,} float={s['float']:,.0f} rvol={s['rvol']} "
                    f"avg_vol={s.get('average_volume',0):,.0f} ex={s.get('exchange','')}"
                )

            # Apply filters
            filtered_stocks = self._apply_filters(scanned_stocks, session_type)

            # Store session data
            self.session_data[session_type] = filtered_stocks

            logger.info(f"{session_type} scan complete: {len(filtered_stocks)} stocks qualified")
            return filtered_stocks

        except Exception as e:
            log_error("scanner_engine.scan_session", f"{session_type}: {str(e)}")
            return []

    async def _process_stocks(self, symbols: List[str],
                             session_type: str) -> List[Dict]:
        """Process multiple stocks in parallel."""
        tasks = [self._analyze_stock(sym, session_type) for sym in symbols]
        results = await asyncio.gather(*tasks)
        return [r for r in results if r is not None]

    async def _analyze_stock(self, symbol: str,
                            session_type: str) -> Optional[Dict]:
        """Analyze a single stock completely."""
        try:
            # Get quote
            quote = await self.market_data.get_quote(symbol)
            if not quote or quote["price"] is None:
                return None

            # Get company profile (non-fatal if missing)
            profile = await self.market_data.get_company_profile(symbol)

            # Get historical candles for EMA calculation
            candles = await self.market_data.get_candles(symbol, resolution="D", count=200)
            if not candles or len(candles) < 20:
                return None

            # Calculate EMAs
            prices = [c["close"] for c in candles]
            ema20 = LevelCalculator.calculate_ema(prices, 20)
            ema50 = LevelCalculator.calculate_ema(prices, 50)
            ema200 = LevelCalculator.calculate_ema(prices, 200)

            # Get latest news
            news = await self.market_data.get_news(symbol, limit=1)
            catalyst = self._detect_catalyst(news)

            # Extract data
            price = quote["price"]
            price_max = SCANNER_FILTERS.get("price_max", GLOBAL_PRICE_MAX)
            if price is None or price < GLOBAL_PRICE_MIN or price > price_max:
                return None

            change_percent = quote["percent"]
            volume = quote["volume"] or 0
            shares_out = (profile.get("shares_outstanding") or 0) if profile else 0
            float_shares = (profile.get("float") or shares_out * 0.3) if profile else shares_out * 0.3
            company_name = (profile.get("name") if profile else None) or symbol
            exchange = (profile.get("exchange") if profile else None) or ""
            avg_volume = (profile.get("average_volume") if profile else None) or 0

            # Calculate metrics
            rvol = self._calculate_rvol(volume, avg_volume)
            ema_alignment, _ = LevelCalculator.get_ema_alignment(price, ema20, ema50, ema200)

            # Calculate trading levels
            levels = LevelCalculator.calculate_levels(price, ema20, ema50, ema200)

            # Build stock record
            stock_data = {
                "ticker": symbol,
                "company_name": company_name,
                "price": price,
                "change": quote["change"],
                "percent_change": change_percent,
                "volume": volume,
                "rvol": rvol,
                "float": float_shares,
                "exchange": exchange,
                "average_volume": avg_volume,
                "ema20": ema20,
                "ema50": ema50,
                "ema200": ema200,
                "ema_alignment": ema_alignment,
                "entry": levels["entry"],
                "tp": levels["tp"],
                "sl": levels["sl"],
                "risk_reward": levels["risk_reward_ratio"],
                "catalyst": catalyst,
                "news_headline": news[0].get("headline") if news else None,
                "news_summary": (news[0].get("summary") if news else None) or (news[0].get("headline") if news else None),
                "news_url": news[0].get("url") if news else None,
                "session": session_type,
                "scan_time": datetime.now(self.et),
                "alert_level": None,
                "momentum_score": 0,
                "obvious_score": 0
            }

            # Detect alerts
            stock_data["alert_level"] = self._check_alert_level(stock_data)

            # Calculate momentum
            stock_data["momentum_score"] = MomentumRadar.calculate_momentum_score(
                change_percent, rvol
            )

            # Calculate obvious stock score
            stock_data["obvious_score"] = ObviousStockDetector.score_stock(
                symbol, price, change_percent, rvol, float_shares, volume,
                catalyst, ema_alignment
            )

            return stock_data

        except Exception as e:
            log_error("scanner_engine._analyze_stock", f"{symbol}: {str(e)}")
            return None

    def _apply_filters(self, stocks: List[Dict], session_type: str) -> List[Dict]:
        """Apply filter rules to stocks."""
        filters = SCANNER_FILTERS

        filtered = []
        reject_reasons = {}
        for stock in stocks:
            ticker = stock["ticker"]

            # User-configurable price filter.
            if not (filters["price_min"] <= stock["price"] <= filters["price_max"]):
                reject_reasons[ticker] = f"price {stock['price']} outside [{filters['price_min']},{filters['price_max']}]"
                continue

            # Base universe constraints.
            stock_exchange = (stock.get("exchange") or "").upper()
            if stock_exchange and stock_exchange not in ALLOWED_EXCHANGES:
                reject_reasons[ticker] = f"exchange '{stock_exchange}' not in allowed"
                continue
            avg_vol = stock.get("average_volume") or 0
            if avg_vol > 0 and avg_vol < 500_000:
                reject_reasons[ticker] = f"avg_volume {avg_vol} < 500K"
                continue

            # Float filter
            if stock["float"] > filters["float_max"]:
                reject_reasons[ticker] = f"float {stock['float']:,.0f} > {filters['float_max']:,.0f}"
                continue

            # Volume filters
            if stock["rvol"] < filters["relative_volume_min"]:
                reject_reasons[ticker] = f"rvol {stock['rvol']} < {filters['relative_volume_min']}"
                continue

            if stock["volume"] < filters["volume_min"]:
                reject_reasons[ticker] = f"volume {stock['volume']} < {filters['volume_min']}"
                continue

            # Change filter
            if stock["percent_change"] < filters["change_min"]:
                reject_reasons[ticker] = f"change {stock['percent_change']:.1f}% < {filters['change_min']}%"
                continue

            # EMA criteria filter
            ema_alignment = stock.get("ema_alignment") or ""
            ema_arrows = ema_alignment.count("\u2191")
            ema_min_arrows = int(filters.get("ema_min_arrows", 0))
            if ema_min_arrows > 0 and ema_arrows < ema_min_arrows:
                reject_reasons[ticker] = f"ema_arrows {ema_arrows} < {ema_min_arrows}"
                continue

            # News criteria filter
            news_mode = filters.get("news_mode", "all")
            has_news = bool(stock.get("news_headline") or stock.get("catalyst"))
            if news_mode == "with_news" and not has_news:
                reject_reasons[ticker] = "no news (news_mode=with_news)"
                continue
            if news_mode == "hot_news" and not (stock.get("alert_level") == "hot" and has_news):
                reject_reasons[ticker] = "not hot news"
                continue

            filtered.append(stock)

        # Log rejection summary for debugging
        if reject_reasons:
            from collections import Counter
            reason_counts = Counter()
            for reason in reject_reasons.values():
                # Group by reason category (first word before the value)
                category = reason.split()[0]
                reason_counts[category] += 1
            logger.info(f"Filter rejections ({len(reject_reasons)} stocks): {dict(reason_counts)}")
            # Log first 5 specific rejections for detail
            for ticker, reason in list(reject_reasons.items())[:5]:
                logger.info(f"  Rejected {ticker}: {reason}")

        return sorted(filtered, key=lambda x: x["percent_change"], reverse=True)

    def _calculate_rvol(self, volume: float, avg_volume: float = 0) -> float:
        """Calculate relative volume against actual average or estimate."""
        baseline = avg_volume if avg_volume > 0 else 100_000
        if baseline <= 0:
            return 0.0
        return round(volume / baseline, 1)

    def _detect_catalyst(self, news: Optional[List[Dict]]) -> Optional[str]:
        """Detect catalyst from news."""
        if not news:
            return None

        headline = news[0]["headline"].lower()

        if "earnings" in headline:
            return "earnings"
        elif "deal" in headline or "partner" in headline:
            return "partnership"
        elif "filing" in headline or "sec" in headline:
            return "sec_filing"
        else:
            return "news"

    def _check_alert_level(self, stock: Dict) -> Optional[str]:
        """Determine momentum alert level for stock (single alert mode)."""
        momentum_change_min = float(SCANNER_FILTERS.get("momentum_change_min", ALERT_LEVELS["momentum"]["change_min"]))
        momentum_rvol_min = float(SCANNER_FILTERS.get("momentum_rvol_min", ALERT_LEVELS["momentum"]["rvol_min"]))
        momentum_float_min = float(
            SCANNER_FILTERS.get(
                "momentum_float_min",
                SCANNER_FILTERS.get("momentum_float_max", ALERT_LEVELS["momentum"]["float_max"])
            )
        )

        change = stock["percent_change"]
        rvol = stock["rvol"]
        float_shares = stock["float"]

        # Momentum-only alert mode.
        if (
            change >= momentum_change_min and
            rvol >= momentum_rvol_min and
            float_shares <= momentum_float_min
        ):
            return "momentum"

        return None

    async def get_session_stats(self, session_type: str) -> Dict:
        """Get statistics for a session."""
        stocks = self.session_data.get(session_type, [])

        if not stocks:
            return {
                "session": session_type,
                "total_scanned": 0,
                "qualified": 0,
                "avg_change": 0,
                "top_ticker": None,
                "hot_alerts": 0,
                "momentum_alerts": 0
            }

        hot_count = sum(1 for s in stocks if s["alert_level"] == "hot")
        momentum_count = sum(1 for s in stocks if s["alert_level"] == "momentum")

        return {
            "session": session_type,
            "total_scanned": 50,
            "qualified": len(stocks),
            "avg_change": round(sum(s["percent_change"] for s in stocks) / len(stocks), 2),
            "top_ticker": stocks[0]["ticker"] if stocks else None,
            "hot_alerts": hot_count,
            "momentum_alerts": momentum_count
        }
