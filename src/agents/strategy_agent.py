"""
StrategyAgent as Orchestrator - Issue #188
Manages TechAgent and SentimentAgent internally for simplified architecture
"""

from typing import Dict, Optional
import numpy as np
import logging
import json
from .base_agent import BaseAgent
from .tech_agent import TechAgent
from .sentiment_v0 import V0SentimentAgent
from .sentiment_v1 import SentimentV1Agent

logger = logging.getLogger(__name__)


class StrategyAgent(BaseAgent):
    """
    Orchestrator StrategyAgent that manages TechAgent and SentimentAgent internally.
    
    Implements MACD + sentiment trading strategy by coordinating:
    - TechAgent: Fetches market data and calculates MACD
    - SentimentAgent: Provides sentiment scores (V0-V4)
    
    Entry: MACD improving AND sentiment >= 0 → BUY
    Exit: MACD deteriorating OR sentiment < -0.5 → SELL
    """

    def __init__(self, name: str = "StrategyAgent", sentiment_version: str = "V0", memory_system=None):
        super().__init__(name=name, tools=[], memory_system=memory_system)
        
        # Trading state
        self.position = 0       # 0 = flat, 1 = long
        self.entry_price = None
        self.entry_date = None
        self.trade_log = []
        self.trades = []  # List of completed trades for metrics calculation
        self.equity_curve = []  # Track equity over time
        
        # Internal agents
        self.tech_agent = TechAgent()
        self.sentiment_agent = self._create_sentiment_agent(sentiment_version)
        self.sentiment_version = sentiment_version
        
        logger.info(f"StrategyAgent initialized with {sentiment_version} sentiment agent")

    def _create_sentiment_agent(self, version: str):
        """Create the appropriate sentiment agent based on version."""
        if version == "V0":
            return V0SentimentAgent()
        elif version == "V1":
            return SentimentV1Agent()
        # TODO: Add V2-V4 when implemented
        # elif version == "V2":
        #     return V2SentimentAgent()
        # elif version == "V3":
        #     return V3SentimentAgent()
        # elif version == "V4":
        #     return V4SentimentAgent()
        else:
            logger.warning(f"Unknown sentiment version {version}, defaulting to V0")
            return V0SentimentAgent()

    def generate_reply(self, messages, context=None):
        """Stub required by BaseAgent; this agent does not support chat."""
        raise NotImplementedError(
            "StrategyAgent does not support chat-based interactions")

    def decide_trade(self, symbol: str, date: str, price: float) -> Dict:
        """
        Main orchestration method: get data from agents and make trading decision.
        
        Args:
            symbol: Stock ticker symbol
            date: Trading date (YYYY-MM-DD)
            price: Current stock price
            
        Returns:
            Dict with trading decision and reasoning
        """
        # Get technical data from TechAgent
        tech_message = f"Get MACD data for {symbol} on {date}"
        tech_response = self.tech_agent.generate_reply(tech_message)
        
        try:
            tech_data = json.loads(tech_response)
            macd_y = tech_data.get("macd_yest")
            macd_t = tech_data.get("macd_today")
        except (json.JSONDecodeError, AttributeError) as e:
            logger.error(f"Failed to parse tech agent response: {e}")
            macd_y = None
            macd_t = None
        
        # Get sentiment data from SentimentAgent
        sentiment_message = f"Get sentiment for {symbol} on {date}"
        sentiment_response = self.sentiment_agent.generate_reply(sentiment_message)
        
        try:
            sentiment_data = json.loads(sentiment_response)
            # V0 uses "score", V1+ use "sentiment"
            sentiment = sentiment_data.get("score") or sentiment_data.get("sentiment", 0)
        except (json.JSONDecodeError, AttributeError) as e:
            logger.error(f"Failed to parse sentiment agent response: {e}")
            sentiment = 0
        
        # Make trading decision based on aggregated data
        return self._make_trading_decision(macd_y, macd_t, sentiment, price, date)

    def _make_trading_decision(self, macd_y: float, macd_t: float, sentiment: float, price: float, trade_date: str) -> Dict:
        """Make the actual trading decision based on MACD and sentiment data."""
        action = "HOLD"
        reason = "no_signal"

        # Entry rule: MACD improving AND sentiment non-negative
        if self.position == 0:
            if (
                macd_y is not None and macd_y < 0 and
                macd_t is not None and macd_t > macd_y and
                sentiment >= 0
            ):
                action = "BUY"
                reason = f"MACD improving (y:{macd_y:.4f} t:{macd_t:.4f}) with sentiment {sentiment:.2f}"
                self.position = 1
                self.entry_price = price
                self.entry_date = trade_date

        # Exit rule: MACD deteriorating OR crossing below zero OR extreme negative sentiment
        elif self.position == 1:
            if macd_y is not None and macd_t is not None:
                # MACD-based exit
                if (macd_y < 0 and macd_t < macd_y) or (macd_y > 0 and macd_t < 0):
                    action = "SELL"
                    reason = f"MACD exit signal (y:{macd_y:.4f} t:{macd_t:.4f})"
                # Sentiment-based exit (extreme bearish sentiment)
                elif sentiment < -0.5:
                    action = "SELL"
                    reason = f"Extreme negative sentiment ({sentiment:.2f})"
                
                # Record completed trade for any SELL action
                if action == "SELL":
                    self.position = 0
                    if self.entry_price is not None:
                        self.trades.append({
                            "entry_date": self.entry_date or trade_date,
                            "exit_date": trade_date,
                            "entry_price": self.entry_price,
                            "exit_price": price,
                            "return": (price - self.entry_price) / self.entry_price,
                            "profit": price - self.entry_price
                        })
                        self.entry_price = None
                        self.entry_date = None

        # Log trade decision
        self.trade_log.append({
            "date": trade_date,
            "action": action,
            "price": price,
            "macd_today": macd_t,
            "macd_yest": macd_y,
            "sentiment": sentiment,
            "reason": reason,
            "version": self.sentiment_version
        })

        return {
            "action": action,
            "qty": 100 if action == "BUY" else 0,
            "reason": reason,
            "macd_today": macd_t,
            "macd_yest": macd_y,
            "sentiment": sentiment,
            "version": self.sentiment_version
        }

    def calculate_metrics(self, initial_capital: float = 100000.0, risk_free_rate: float = 0.02) -> Dict:
        """
        Calculate comprehensive performance metrics for the strategy.

        :param initial_capital: Starting capital amount
        :param risk_free_rate: Annual risk-free rate for Sharpe ratio calculation
        :return: Dictionary of performance metrics
        """
        if not self.trades and not self.equity_curve:
            return {
                "total_return": 0.0,
                "total_return_pct": 0.0,
                "win_rate": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "max_drawdown": 0.0,
                "max_drawdown_pct": 0.0,
                "sharpe_ratio": 0.0,
                "num_trades": 0,
                "avg_holding_days": 0.0,
                "profit_factor": 0.0,
                "expectancy": 0.0,
                "winning_trades": 0,
                "losing_trades": 0
            }

        # Calculate basic metrics from trades
        if self.trades:
            profits = [t["profit"] for t in self.trades]

            winning_trades = [t for t in self.trades if t["profit"] > 0]
            losing_trades = [t for t in self.trades if t["profit"] <= 0]

            win_rate = len(winning_trades) / \
                len(self.trades) if self.trades else 0
            avg_win = np.mean([t["profit"]
                              for t in winning_trades]) if winning_trades else 0
            avg_loss = np.mean([abs(t["profit"])
                               for t in losing_trades]) if losing_trades else 0

            # Calculate profit factor
            gross_profit = sum([t["profit"]
                               for t in winning_trades]) if winning_trades else 0
            gross_loss = sum([abs(t["profit"])
                             for t in losing_trades]) if losing_trades else 0
            profit_factor = gross_profit / \
                gross_loss if gross_loss > 0 else float('inf')

            # Calculate expectancy
            expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)

            # Calculate average holding period
            holding_days = []
            for trade in self.trades:
                try:
                    from datetime import datetime
                    entry = datetime.fromisoformat(trade["entry_date"])
                    exit = datetime.fromisoformat(trade["exit_date"])
                    days = (exit - entry).days
                    holding_days.append(days)
                except:
                    pass
            avg_holding_days = np.mean(holding_days) if holding_days else 0

            # Total return calculation
            total_return = sum(profits) / \
                initial_capital if initial_capital > 0 else 0
        else:
            win_rate = avg_win = avg_loss = profit_factor = expectancy = avg_holding_days = total_return = 0

        # Calculate metrics from equity curve if available
        if self.equity_curve and len(self.equity_curve) > 1:
            equity_values = [e["equity"]
                             for e in self.equity_curve if "equity" in e]

            if equity_values:
                # Max drawdown calculation
                peak = equity_values[0]
                max_drawdown = 0
                for value in equity_values:
                    if value > peak:
                        peak = value
                    drawdown = (peak - value) / peak if peak > 0 else 0
                    max_drawdown = max(max_drawdown, drawdown)

                # Daily returns for Sharpe ratio
                daily_returns = []
                for i in range(1, len(equity_values)):
                    daily_return = (
                        equity_values[i] - equity_values[i - 1]) / equity_values[i - 1]
                    daily_returns.append(daily_return)

                if daily_returns:
                    # Annualized Sharpe ratio (assuming 252 trading days)
                    avg_daily_return = np.mean(daily_returns)
                    std_daily_return = np.std(daily_returns)

                    if std_daily_return > 0:
                        daily_risk_free = risk_free_rate / 252
                        sharpe_ratio = np.sqrt(
                            252) * (avg_daily_return - daily_risk_free) / std_daily_return
                    else:
                        sharpe_ratio = 0
                else:
                    sharpe_ratio = 0

                # Update total return from equity curve
                if not self.trades:  # Only use equity curve if no trades recorded
                    total_return = (
                        equity_values[-1] - initial_capital) / initial_capital
            else:
                max_drawdown = sharpe_ratio = 0
        else:
            max_drawdown = sharpe_ratio = 0

        metrics = {
            "total_return": total_return,
            "total_return_pct": total_return * 100,
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "max_drawdown": max_drawdown,
            "max_drawdown_pct": max_drawdown * 100,
            "sharpe_ratio": sharpe_ratio,
            "num_trades": len(self.trades),
            "avg_holding_days": avg_holding_days,
            "profit_factor": profit_factor,
            "expectancy": expectancy,
            "winning_trades": len([t for t in self.trades if t["profit"] > 0]),
            "losing_trades": len([t for t in self.trades if t["profit"] <= 0])
        }

        return metrics

    def update_equity_curve(self, date: str, equity: float, price: float):
        """Update the equity curve for drawdown and Sharpe calculations."""
        self.equity_curve.append({
            "date": date,
            "equity": equity,
            "price": price
        })

    def print_metrics_summary(self, metrics: Dict) -> None:
        """Print a formatted summary of performance metrics."""
        print("\n" + "=" * 60)
        print("STRATEGY PERFORMANCE METRICS")
        print("=" * 60)

        print(f"\nReturns:")
        print(f"  Total Return: {metrics['total_return_pct']:+.2f}%")
        print(f"  Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
        print(f"  Max Drawdown: {metrics['max_drawdown_pct']:.2f}%")

        print(f"\nTrade Statistics:")
        print(f"  Total Trades: {metrics['num_trades']}")
        print(f"  Win Rate: {metrics['win_rate']*100:.1f}%")
        print(f"  Winning Trades: {metrics['winning_trades']}")
        print(f"  Losing Trades: {metrics['losing_trades']}")

        if metrics['num_trades'] > 0:
            print(f"\nProfitability:")
            print(f"  Average Win: ${metrics['avg_win']:,.2f}")
            print(f"  Average Loss: ${metrics['avg_loss']:,.2f}")
            print(f"  Profit Factor: {metrics['profit_factor']:.2f}")
            print(f"  Expectancy: ${metrics['expectancy']:,.2f}")
            print(f"  Avg Holding Days: {metrics['avg_holding_days']:.1f}")

        print("=" * 60)

    def get_metrics(self, initial_capital: float = 100000.0) -> Dict:
        """Wrapper method for calculate_metrics for compatibility."""
        return self.calculate_metrics(initial_capital)