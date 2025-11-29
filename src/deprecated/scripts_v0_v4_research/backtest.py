#!/usr/bin/env python3
"""
Simple Continuous Backtesting with Checkpoint/Resume

Simplified approach for year-long continuous V0-V4 backtesting with:
- Checkpoint/resume functionality
- Version-specific folders and status tracking
- Multi-year support (2024 → 2025 → ...)
- Clean, focused implementation
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import argparse
import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from src.agents.tech_agent import TechAgent  # Add tech agent for market data

# Import deprecated sentiment agents - preserved for backtesting comparison
from src.deprecated.v0_v4_agents.sentiment_v0 import V0SentimentAgent
from src.deprecated.v0_v4_agents.sentiment_v1 import SentimentV1Agent
from src.deprecated.v0_v4_agents.sentiment_v2 import SentimentV2Agent
from src.deprecated.v0_v4_agents.sentiment_v3 import SentimentV3Agent
from src.deprecated.v0_v4_agents.sentiment_v4 import SentimentV4Agent

# Import tools
from src.tools.cache.unified_cache import UnifiedCacheManager

# Import advanced metrics capture
try:
    from src.analysis.metrics_capture import MetricsCapture

    METRICS_CAPTURE_AVAILABLE = True
except ImportError:
    METRICS_CAPTURE_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class BacktestCheckpoint:
    """Checkpoint state for resuming backtests."""

    version: str
    symbol: str
    year: int
    last_date: str
    cash: float
    position: int
    entry_price: float
    entry_date: Optional[str]
    trades: List[Dict]
    daily_values: List[Dict]
    sentiment_scores: List[float]
    completed: bool = False

    # Enhanced position tracking
    position_avg_cost: float = 0.0
    total_cost_basis: float = 0.0


class SimpleContinuousBacktest:
    """
    Simplified continuous backtesting with checkpoint/resume functionality.

    Key Features:
    - One version at a time for clarity
    - Checkpoint every trading day
    - Resume from any point
    - Version-specific folders
    - Multi-year support
    """

    def __init__(self, output_dir: str = "reports/continuous_backtests"):
        self.output_dir = Path(output_dir)
        self.cache_manager = UnifiedCacheManager()

        # MACD parameters
        self.fast_period = 12
        self.slow_period = 26
        self.signal_period = 9

        # Initialize sentiment agents - using optimized versions where available
        self.agents = {
            "V0": V0SentimentAgent(),
            "V1": SentimentV1Agent(),
            "V2": SentimentV2Agent(),
            "V3": SentimentV3Agent(),
            "V4": SentimentV4Agent(enable_date_sanitization=True),
        }

        # Initialize tech agent for fetching market data
        self.tech_agent = TechAgent()

        logger.info("✅ Simple Continuous Backtest initialized")

    def update_position_tracking(
        self, action: str, shares: int, price: float, current_avg_cost: float, cost_basis: float
    ) -> tuple:
        """Update position average cost and cost basis tracking."""

        if action == "BUY":
            if current_avg_cost > 0:
                # Adding to existing position - weighted average
                new_cost_basis = cost_basis + (shares * price)
                current_shares = cost_basis / current_avg_cost
                total_shares = current_shares + shares
                new_avg_cost = new_cost_basis / total_shares
                return new_avg_cost, new_cost_basis
            else:
                # Starting new position
                return price, shares * price

        elif action == "SELL":
            if current_avg_cost > 0 and cost_basis > 0:
                # Calculate current total shares from cost basis
                current_shares = cost_basis / current_avg_cost
                if shares >= current_shares:
                    # Closing entire position
                    return 0.0, 0.0
                else:
                    # Partial sale - reduce basis proportionally
                    sold_ratio = shares / current_shares
                    new_cost_basis = cost_basis * (1 - sold_ratio)
                    return current_avg_cost, new_cost_basis
            else:
                return 0.0, 0.0

        return current_avg_cost, cost_basis

    def get_version_dir(self, version: str) -> Path:
        """Get version-specific directory."""
        version_dir = self.output_dir / version
        version_dir.mkdir(parents=True, exist_ok=True)
        return version_dir

    def get_checkpoint_path(self, version: str, symbol: str, year: int) -> Path:
        """Get checkpoint file path."""
        version_dir = self.get_version_dir(version)
        return version_dir / f"{symbol}_{year}_checkpoint.json"

    def get_results_path(self, version: str, symbol: str, year: int) -> Path:
        """Get final results file path."""
        version_dir = self.get_version_dir(version)
        return version_dir / f"{symbol}_{year}_results.json"

    def load_checkpoint(self, version: str, symbol: str, year: int) -> Optional[BacktestCheckpoint]:
        """Load existing checkpoint if available."""
        checkpoint_path = self.get_checkpoint_path(version, symbol, year)

        if checkpoint_path.exists():
            try:
                with open(checkpoint_path, "r") as f:
                    data = json.load(f)
                    checkpoint = BacktestCheckpoint(**data)
                    logger.info(
                        f"📂 Loaded checkpoint: {version} {symbol} {year} (last: {checkpoint.last_date})"
                    )
                    return checkpoint
            except Exception as e:
                logger.warning(f"⚠️ Could not load checkpoint: {e}")

        return None

    def save_checkpoint(self, checkpoint: BacktestCheckpoint):
        """Save checkpoint to disk."""
        checkpoint_path = self.get_checkpoint_path(
            checkpoint.version, checkpoint.symbol, checkpoint.year
        )

        try:
            with open(checkpoint_path, "w") as f:
                json.dump(checkpoint.__dict__, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"❌ Could not save checkpoint: {e}")

    def calculate_macd(self, prices: pd.Series) -> Dict[str, pd.Series]:
        """Calculate MACD indicator."""
        ema_fast = prices.ewm(span=self.fast_period).mean()
        ema_slow = prices.ewm(span=self.slow_period).mean()

        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=self.signal_period).mean()

        return {"macd": macd_line, "signal": signal_line, "histogram": macd_line - signal_line}

    def generate_macd_signals(self, macd_data: Dict[str, pd.Series]) -> pd.Series:
        """Generate MACD crossover signals."""
        macd = macd_data["macd"]
        signal = macd_data["signal"]

        bullish_cross = (macd > signal) & (macd.shift(1) <= signal.shift(1))
        bearish_cross = (macd < signal) & (macd.shift(1) >= signal.shift(1))

        signals = pd.Series(0, index=macd.index)
        signals[bullish_cross] = 1
        signals[bearish_cross] = -1

        return signals

    async def get_sentiment(self, agent, symbol: str, date_str: str) -> float:
        """Get sentiment score from agent."""
        try:
            query = f"{symbol} on {date_str}"
            response = agent.generate_reply(query)

            if asyncio.iscoroutine(response):
                response = await response

            if isinstance(response, str):
                data = json.loads(response)
            else:
                data = response

            sentiment = data.get("sentiment", 0.0) or data.get("score", 0.0)

            if isinstance(sentiment, str):
                sentiment = float(sentiment)

            return sentiment

        except Exception as e:
            logger.warning(f"⚠️ Sentiment error for {symbol} on {date_str}: {e}")
            return 0.0  # Neutral fallback

    async def run_continuous_backtest(
        self, version: str, symbol: str, year: int, initial_cash: float = 100000.0
    ) -> Dict[str, Any]:
        """
        Run continuous backtest for one version/symbol/year with checkpoints.

        Args:
            version: V0, V1, V2, V3, or V4
            symbol: Stock symbol (e.g., 'AAPL')
            year: Year to backtest (e.g., 2024)
            initial_cash: Starting cash amount
        """

        logger.info(f"🚀 Starting continuous backtest: {version} {symbol} {year}")

        # Initialize advanced metrics capture if available
        metrics_capture = None
        if METRICS_CAPTURE_AVAILABLE:
            metrics_capture = MetricsCapture(symbol, initial_cash)
            logger.info(f"📊 Advanced metrics capture enabled for {version} {symbol}")

        # Check if already completed
        results_path = self.get_results_path(version, symbol, year)
        if results_path.exists():
            logger.info(f"✅ {version} {symbol} {year} already completed")
            with open(results_path, "r") as f:
                return json.load(f)

        # Load checkpoint or start fresh
        checkpoint = self.load_checkpoint(version, symbol, year)

        if checkpoint and checkpoint.completed:
            logger.info(f"✅ {version} {symbol} {year} completed from checkpoint")
            return self._load_final_results(version, symbol, year)

        # Get market data for the year or month
        if hasattr(self, "month_override") and self.month_override:
            start_date = f"{year}-{self.month_override:02d}-01"
            # Calculate last day of month
            import calendar

            last_day = calendar.monthrange(year, self.month_override)[1]
            end_date = f"{year}-{self.month_override:02d}-{last_day}"
        else:
            start_date = f"{year}-01-01"
            end_date = f"{year}-12-31"

        # Try cache first
        market_data = self.cache_manager.get_market_data(symbol, start_date, end_date, "polygon")
        if market_data is None or market_data.empty:
            market_data = self.cache_manager.get_market_data(
                symbol, start_date, end_date, "alpha_vantage"
            )

        # If no cached data, use tech agent to fetch it
        if market_data is None or market_data.empty:
            logger.info(f"📡 No cached data for {symbol} {year}, fetching via tech agent...")
            try:
                # Run tech agent in a new thread to avoid event loop conflicts
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        self.tech_agent.generate_reply,
                        f"fetch historical market data for {symbol} from {start_date} to {end_date}",
                    )
                    response = future.result(timeout=60)  # 60 second timeout

                # Parse response and get data from cache (tech agent should have cached it)
                market_data = self.cache_manager.get_market_data(
                    symbol, start_date, end_date, "polygon"
                )
                if market_data is None or market_data.empty:
                    market_data = self.cache_manager.get_market_data(
                        symbol, start_date, end_date, "alpha_vantage"
                    )

            except Exception as e:
                logger.error(f"❌ Tech agent failed to fetch data: {e}")

        if market_data is None or market_data.empty:
            raise ValueError(f"No market data available for {symbol} {year}")

        # Calculate MACD signals
        macd_data = self.calculate_macd(market_data["close"])
        macd_signals = self.generate_macd_signals(macd_data)

        logger.info(f"📊 Market data: {len(market_data)} trading days")
        logger.info(
            f"📈 MACD signals: {(macd_signals == 1).sum()} buy, {(macd_signals == -1).sum()} sell"
        )

        # Initialize or resume state
        if checkpoint:
            # Resume from checkpoint
            cash = checkpoint.cash
            position = checkpoint.position
            entry_price = checkpoint.entry_price
            entry_date = checkpoint.entry_date
            trades = checkpoint.trades
            daily_values = checkpoint.daily_values
            sentiment_scores = checkpoint.sentiment_scores

            # Enhanced position tracking
            position_avg_cost = getattr(checkpoint, "position_avg_cost", 0.0)
            total_cost_basis = getattr(checkpoint, "total_cost_basis", 0.0)

            # Find resume point
            if checkpoint.last_date == "batch_preparation_complete":
                # V4 batch preparation was completed, resume from start of daily trading
                resume_data = market_data
                logger.info(
                    f"🔄 V4: Resuming from completed batch preparation ({len(resume_data)} days to trade)"
                )
            else:
                # Normal resume from specific date
                last_date = pd.to_datetime(checkpoint.last_date)
                resume_data = market_data[market_data.index > last_date]
                logger.info(
                    f"🔄 Resuming from {checkpoint.last_date} ({len(resume_data)} days remaining)"
                )

        else:
            # Start fresh
            cash = initial_cash
            position = 0
            entry_price = 0
            entry_date = None
            trades = []
            daily_values = []
            sentiment_scores = []
            resume_data = market_data

            # Enhanced position tracking
            position_avg_cost = 0.0
            total_cost_basis = 0.0

            logger.info("🆕 Starting fresh backtest")

        # Get agent
        agent = self.agents[version]
        total_days = len(resume_data)
        processed_days = 0

        # V4-specific weekly batch preparation for efficient LLM processing
        if version == "V4" and (
            not checkpoint or checkpoint.last_date != "batch_preparation_complete"
        ):
            logger.info("🤖 V4: Preparing weekly batch sentiment analysis...")
            try:
                # Use market data date range for weekly batch preparation
                first_date = resume_data.index[0].strftime("%Y-%m-%d")
                last_date = resume_data.index[-1].strftime("%Y-%m-%d")

                success = await asyncio.to_thread(
                    agent.prepare_period_data, symbol, first_date, last_date
                )

                if success:
                    logger.info(
                        f"✅ V4: Weekly batch preparation completed for {len(resume_data)} days"
                    )

                    # Save checkpoint after successful batch preparation
                    # This ensures V4 progress is saved before entering daily loop
                    batch_prep_checkpoint = BacktestCheckpoint(
                        version=version,
                        symbol=symbol,
                        year=year,
                        last_date="batch_preparation_complete",  # Special marker
                        cash=cash,
                        position=position,
                        entry_price=entry_price,
                        entry_date=entry_date,
                        trades=trades,
                        daily_values=daily_values,
                        sentiment_scores=sentiment_scores,
                        completed=False,
                    )
                    self.save_checkpoint(batch_prep_checkpoint)
                    logger.info("💾 V4: Batch preparation checkpoint saved")

                else:
                    logger.warning(
                        "⚠️ V4: Weekly batch preparation failed, falling back to daily mode"
                    )

            except Exception as e:
                logger.error(f"❌ V4: Weekly batch preparation error: {e}")
                logger.info("🔄 V4: Continuing with daily sentiment analysis")

        # Daily trading loop
        for date, row in resume_data.iterrows():
            current_price = row["close"]
            date_str = date.strftime("%Y-%m-%d")

            # Get signals
            macd_signal = macd_signals.get(date, 0)

            # Use V4 batch sentiment data when available to avoid redundant API calls
            if (
                version == "V4"
                and hasattr(agent, "prepared_sentiments")
                and date_str in agent.prepared_sentiments
            ):
                sentiment_score = agent.prepared_sentiments[date_str]
                logger.debug(f"🤖 V4: Using batch sentiment for {date_str}: {sentiment_score:.3f}")
            else:
                sentiment_score = await self.get_sentiment(agent, symbol, date_str)

            sentiment_scores.append(sentiment_score)

            # Trading logic: MACD + Sentiment
            # Use consistent threshold for all versions to enable proper comparison
            sentiment_threshold = 0.0
            if position == 0 and macd_signal == 1 and sentiment_score >= sentiment_threshold:
                # Enter long position with sentiment-based position sizing
                # SENTIMENT POSITION SIZING (Issue #222)
                # Normalize sentiment to 0-1 range (handles different sentiment ranges)
                # V0: fixed 1.0, V1: -1 to +1, V2: ~0.3-0.8, V3: ~0.2-0.8, V4: -1 to +1
                normalized_sentiment = max(0, min(1, (sentiment_score + 1) / 2))  # Clamp to [0,1]

                # Calculate position multiplier based on sentiment confidence
                MIN_POSITION = 0.3  # Never go below 30% position
                MAX_POSITION = 1.0  # Maximum 100% position
                position_multiplier = (
                    MIN_POSITION + (MAX_POSITION - MIN_POSITION) * normalized_sentiment
                )

                # Capital-aware position sizing - calculate affordable shares first
                max_affordable_shares = int(cash * 0.95 / current_price)  # Keep 5% cash buffer
                target_shares = max(1, int(max_affordable_shares * position_multiplier))
                shares = min(target_shares, max_affordable_shares)

                # Ensure we have enough cash for this position
                required_cash = shares * current_price
                if shares > 0 and required_cash <= cash:
                    position = shares
                    cash = round(cash - (shares * current_price), 2)  # Round to cents
                    entry_price = current_price
                    entry_date = date_str

                    # Update position tracking
                    position_avg_cost, total_cost_basis = self.update_position_tracking(
                        "BUY", shares, current_price, position_avg_cost, total_cost_basis
                    )

                    trades.append(
                        {
                            "date": date_str,
                            "action": "BUY",
                            "price": current_price,
                            "shares": shares,
                            "sentiment": sentiment_score,
                            "macd_signal": macd_signal,
                            "position_avg_cost": position_avg_cost,  # Enhanced tracking
                        }
                    )

                    # Record trade in advanced metrics capture
                    if metrics_capture:
                        metrics_capture.record_trade(
                            date=date_str,
                            action="BUY",
                            price=current_price,
                            shares=shares,
                            sentiment=sentiment_score,
                            macd_signal=str(macd_signal),
                            portfolio_value=cash + (position * current_price),
                        )

                    logger.info(
                        f"📈 BUY: {shares} shares at ${current_price:.2f} (avg: ${position_avg_cost:.2f}, sentiment: {sentiment_score:.3f}, multiplier: {position_multiplier:.2f})"
                    )

            elif position > 0 and (macd_signal == -1 or sentiment_score < -0.5):
                # Exit position
                cash = round(cash + (position * current_price), 2)  # Round to cents
                exit_return = (current_price - entry_price) / entry_price * 100
                avg_cost_return = (
                    (current_price - position_avg_cost) / position_avg_cost * 100
                    if position_avg_cost > 0
                    else 0
                )

                trades.append(
                    {
                        "date": date_str,
                        "action": "SELL",
                        "price": current_price,
                        "shares": position,
                        "sentiment": sentiment_score,
                        "macd_signal": macd_signal,
                        "return_pct": exit_return,
                        "avg_cost_return_pct": avg_cost_return,  # Enhanced tracking
                        "entry_date": entry_date,
                        "entry_avg_cost": position_avg_cost,
                    }
                )

                # Record trade in advanced metrics capture
                if metrics_capture:
                    metrics_capture.record_trade(
                        date=date_str,
                        action="SELL",
                        price=current_price,
                        shares=position,
                        sentiment=sentiment_score,
                        macd_signal=str(macd_signal),
                        portfolio_value=cash,  # Cash after selling
                    )

                logger.info(
                    f"📉 SELL: {position} shares at ${current_price:.2f} (avg cost return: {avg_cost_return:+.2f}%)"
                )

                # Update position tracking before resetting (pass shares sold, not position count)
                position_avg_cost, total_cost_basis = self.update_position_tracking(
                    "SELL", position, current_price, position_avg_cost, total_cost_basis
                )

                # Reset position tracking
                position = 0
                entry_price = 0
                entry_date = None

            # Record enhanced daily portfolio value
            portfolio_value = cash + (position * current_price)
            position_value = position * current_price

            # Calculate enhanced metrics
            if position > 0 and position_avg_cost > 0:
                unrealized_pnl = (current_price - position_avg_cost) * position
                unrealized_pnl_pct = ((current_price - position_avg_cost) / position_avg_cost) * 100
            else:
                unrealized_pnl = 0.0
                unrealized_pnl_pct = 0.0

            # Allocation percentages
            cash_allocation_pct = (cash / portfolio_value) * 100 if portfolio_value > 0 else 0
            position_allocation_pct = (
                (position_value / portfolio_value) * 100 if portfolio_value > 0 else 0
            )

            daily_values.append(
                {
                    "date": date_str,
                    "portfolio_value": round(portfolio_value, 2),
                    "cash": round(cash, 2),  # Round to cents for realism
                    "position": position,
                    "stock_price": round(current_price, 2),
                    "sentiment": round(sentiment_score, 4),
                    # Enhanced position tracking metrics
                    "position_avg_cost": round(position_avg_cost, 2) if position > 0 else 0.0,
                    "position_value": round(position_value, 2),
                    "cost_basis": round(total_cost_basis, 2),
                    "unrealized_pnl": round(unrealized_pnl, 2),
                    "unrealized_pnl_pct": round(unrealized_pnl_pct, 2),
                    "cash_allocation_pct": round(cash_allocation_pct, 1),
                    "position_allocation_pct": round(position_allocation_pct, 1),
                    "is_averaging_up": position_avg_cost > 0 and current_price > position_avg_cost,
                    "is_averaging_down": position_avg_cost > 0
                    and current_price < position_avg_cost,
                }
            )

            # Update advanced metrics capture with daily data
            if metrics_capture:
                # Note: Volume not available in current data, will be None
                metrics_capture.update_daily_data(
                    date=date_str,
                    portfolio_value=round(portfolio_value, 2),
                    cash=round(cash, 2),
                    position=position,
                    stock_price=round(current_price, 2),
                    sentiment=round(sentiment_score, 4),
                    volume=None,  # Not available in current market data
                    macd_histogram=None,  # Could add MACD histogram if needed
                )

            processed_days += 1

            # Save checkpoint every 3 days (more frequent for testing)
            if processed_days % 3 == 0:
                checkpoint = BacktestCheckpoint(
                    version=version,
                    symbol=symbol,
                    year=year,
                    last_date=date_str,
                    cash=cash,
                    position=position,
                    entry_price=entry_price,
                    entry_date=entry_date,
                    trades=trades,
                    daily_values=daily_values,
                    sentiment_scores=sentiment_scores,
                )
                self.save_checkpoint(checkpoint)

                progress = (processed_days / total_days) * 100
                logger.info(
                    f"💾 Checkpoint saved: {processed_days}/{total_days} days ({progress:.1f}%)"
                )

        # Verify position sizing differentiation worked
        if trades:
            buy_trades = [t for t in trades if t["action"] == "BUY"]
            if buy_trades:
                share_counts = [t["shares"] for t in buy_trades]
                unique_shares = set(share_counts)
                avg_sentiment = np.mean([t["sentiment"] for t in buy_trades])

                logger.info("📊 Position sizing verification:")
                logger.info(f"   - Unique share counts: {sorted(unique_shares)}")
                logger.info(f"   - Share count range: {min(share_counts)} to {max(share_counts)}")
                logger.info(f"   - Average sentiment: {avg_sentiment:.3f}")
                logger.info(f"   - Total buy trades: {len(buy_trades)}")

                # Warn if all trades have identical shares (position sizing not working)
                if len(unique_shares) == 1:
                    logger.warning(
                        "⚠️ All trades have identical share count - position sizing may not be working!"
                    )
                else:
                    logger.info("✅ Position sizing working - different share counts detected")

        # Calculate final metrics
        metrics = self._calculate_metrics(daily_values, trades, market_data)

        # Create final results
        results = {
            "metadata": {
                "version": version,
                "symbol": symbol,
                "year": year,
                "start_date": start_date,
                "end_date": end_date,
                "initial_cash": initial_cash,
                "execution_time": datetime.now().isoformat(),
                "framework": "SimpleContinuousBacktest_v1.0",
            },
            "performance": metrics,
            "trades": trades,
            # All daily values
            "daily_values": daily_values,
            "sentiment_stats": {
                "mean": np.mean(sentiment_scores),
                "std": np.std(sentiment_scores),
                "min": np.min(sentiment_scores),
                "max": np.max(sentiment_scores),
            },
        }

        # Add enhanced metrics if MetricsCapture was used
        if metrics_capture:
            enhanced_data = metrics_capture.export_enhanced_results()
            results["enhanced_metrics"] = enhanced_data["enhanced_daily_data"]
            results["enhanced_trades"] = enhanced_data["enhanced_trade_data"]
            results["sentiment_effectiveness"] = enhanced_data["sentiment_effectiveness"]
            results["market_regime_analysis"] = enhanced_data["market_regime_summary"]
            results["real_time_metrics"] = enhanced_data["real_time_metrics"]

            # Mark as having enhanced metrics
            results["metadata"]["enhanced_capture"] = True
            results["metadata"]["capture_framework"] = "MetricsCapture_v1.0"

            logger.info("📊 Enhanced metrics added to results")

        # Save final results
        with open(results_path, "w") as f:
            json.dump(results, f, indent=2, default=str)

        # Mark checkpoint as completed
        final_checkpoint = BacktestCheckpoint(
            version=version,
            symbol=symbol,
            year=year,
            last_date=end_date,
            cash=cash,
            position=position,
            entry_price=entry_price,
            entry_date=entry_date,
            trades=trades,
            daily_values=daily_values,
            sentiment_scores=sentiment_scores,
            completed=True,
        )
        self.save_checkpoint(final_checkpoint)

        logger.info(
            f"🎉 {version} {symbol} {year} completed: {metrics['total_return']:+.2f}% return"
        )

        return results

    def _calculate_metrics(
        self, daily_values: List[Dict], trades: List[Dict], market_data: pd.DataFrame
    ) -> Dict[str, Any]:
        """Calculate performance metrics."""

        if not daily_values:
            return {"error": "No daily values"}

        initial_value = daily_values[0]["portfolio_value"]
        final_value = daily_values[-1]["portfolio_value"]
        total_return = ((final_value - initial_value) / initial_value) * 100

        # Buy and hold comparison
        initial_price = market_data.iloc[0]["close"]
        final_price = market_data.iloc[-1]["close"]
        buy_hold_return = ((final_price - initial_price) / initial_price) * 100

        # Trade analysis
        profitable_trades = [t for t in trades if t.get("return_pct", 0) > 0]
        losing_trades = [t for t in trades if t.get("return_pct", 0) < 0]

        return {
            "total_return": round(total_return, 3),
            "total_return_pct": round(total_return, 3),
            "buy_hold_return": round(buy_hold_return, 2),
            "outperformance": round(total_return - buy_hold_return, 3),
            "final_portfolio_value": round(final_value, 2),
            "num_trades": len(trades),
            "profitable_trades": len(profitable_trades),
            "losing_trades": len(losing_trades),
            "win_rate": round(len(profitable_trades) / len(trades) * 100, 1) if trades else 0,
            "avg_trade_return": (
                round(np.mean([t.get("return_pct", 0) for t in trades if "return_pct" in t]), 2)
                if trades
                else 0
            ),
        }

    def _load_final_results(self, version: str, symbol: str, year: int) -> Dict[str, Any]:
        """Load final results from file."""
        results_path = self.get_results_path(version, symbol, year)
        with open(results_path, "r") as f:
            return json.load(f)

    def get_status_summary(self) -> Dict[str, Any]:
        """Get status summary of all backtests."""
        summary = {}

        for version in ["V0", "V1", "V2", "V3", "V4"]:
            version_dir = self.get_version_dir(version)
            version_status = {"completed": [], "in_progress": [], "not_started": []}

            # Check for checkpoint and result files
            for file_path in version_dir.glob("*_checkpoint.json"):
                try:
                    with open(file_path, "r") as f:
                        checkpoint = json.load(f)

                    test_id = f"{checkpoint['symbol']}_{checkpoint['year']}"

                    if checkpoint.get("completed", False):
                        version_status["completed"].append(test_id)
                    else:
                        version_status["in_progress"].append(
                            {"test_id": test_id, "last_date": checkpoint["last_date"]}
                        )

                except Exception as e:
                    logger.warning(f"Could not read checkpoint {file_path}: {e}")

            summary[version] = version_status

        return summary


async def main():
    """Main execution with CLI arguments."""

    parser = argparse.ArgumentParser(description="Simple Continuous Backtesting")
    parser.add_argument("--version", choices=["V0", "V1", "V2", "V3", "V4"], help="Version to test")
    parser.add_argument("--symbol", default="AAPL", help="Symbol to test")
    parser.add_argument("--year", type=int, default=2024, help="Year to test")
    parser.add_argument("--month", type=int, help="Month to test (1-12, optional for single month)")
    parser.add_argument("--cash", type=float, default=100000.0, help="Initial cash")
    parser.add_argument("--status", action="store_true", help="Show status summary")
    parser.add_argument("--all-versions", action="store_true", help="Run all V0-V4 versions")

    args = parser.parse_args()

    backtest = SimpleContinuousBacktest()

    if args.status:
        # Show status summary
        summary = backtest.get_status_summary()
        print("\n📊 BACKTEST STATUS SUMMARY")
        print("=" * 50)

        for version, status in summary.items():
            print(f"\n{version}:")
            if status["completed"]:
                print(f"  ✅ Completed: {', '.join(status['completed'])}")
            if status["in_progress"]:
                for ip in status["in_progress"]:
                    print(f"  🔄 In Progress: {ip['test_id']} (last: {ip['last_date']})")
            if not status["completed"] and not status["in_progress"]:
                print("  ⏳ Not started")

        return

    if args.all_versions:
        # Run all versions sequentially
        versions = ["V0", "V1", "V2", "V3", "V4"]
        results = {}

        # Set month override if specified
        if args.month:
            backtest.month_override = args.month
            period_desc = f"{args.symbol} {args.year}-{args.month:02d}"
        else:
            period_desc = f"{args.symbol} {args.year}"

        print(f"\n🚀 Running all versions: {period_desc}")
        print("=" * 60)

        for version in versions:
            try:
                print(f"\n📈 Starting {version}...")
                result = await backtest.run_continuous_backtest(
                    version, args.symbol, args.year, args.cash
                )
                results[version] = result["performance"]

                total_return = result["performance"]["total_return"]
                num_trades = result["performance"]["num_trades"]
                print(f"✅ {version}: {total_return:+.2f}% return, {num_trades} trades")

            except Exception as e:
                print(f"❌ {version} failed: {e}")
                results[version] = {"error": str(e)}

        # Print comparison
        print(f"\n📊 FINAL COMPARISON: {args.symbol} {args.year}")
        print("-" * 50)
        for version in versions:
            if "error" not in results[version]:
                ret = results[version]["total_return"]
                trades = results[version]["num_trades"]
                print(f"{version}: {ret:+6.2f}% | {trades:2d} trades")
            else:
                print(f"{version}: ERROR")

    elif args.version:
        # Run single version
        if args.month:
            backtest.month_override = args.month
        try:
            result = await backtest.run_continuous_backtest(
                args.version, args.symbol, args.year, args.cash
            )

            print(f"\n🎉 {args.version} {args.symbol} {args.year} completed!")
            print(f"Return: {result['performance']['total_return']:+.2f}%")
            print(f"Trades: {result['performance']['num_trades']}")
            print(
                f"Results saved to: {backtest.get_results_path(args.version, args.symbol, args.year)}"
            )

        except Exception as e:
            print(f"❌ {args.version} failed: {e}")

    else:
        print("Please specify --version, --all-versions, or --status")


if __name__ == "__main__":
    asyncio.run(main())
