from typing import Dict, Optional
import numpy as np
import logging
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class StrategyAgent(BaseAgent):
    """
    Implements a hard-coded MACD + sentiment trading strategy.

    Entry:
      - If flat AND yesterday’s MACD < 0 AND today’s MACD > yesterday’s MACD
        AND sentiment >= 0 → BUY  (V2: Changed from > to >= to allow neutral sentiment)

    Exit:
      - If long AND (yesterday’s MACD < 0 AND today’s MACD < yesterday’s MACD)
        OR (yesterday’s MACD > 0 AND today’s MACD < 0) → SELL

    Otherwise: HOLD
    """

    def __init__(self, name: str = "StrategyAgent", memory_system=None):
        super().__init__(name=name, tools=[], memory_system=memory_system)
        self.position = 0       # 0 = flat, 1 = long
        self.entry_price = None
        self.entry_date = None
        self.trade_log = []
        self.trades = []  # List of completed trades for metrics calculation
        self.equity_curve = []  # Track equity over time
        # Market heat threshold for trading (adjusted for current market conditions)
        self.market_heat_threshold = -0.2
        self.decision_log = []  # Log all filtering decisions

    def generate_reply(self, messages, context=None):
        """Stub required by BaseAgent; this agent does not support chat."""
        raise NotImplementedError(
            "StrategyAgent does not support chat-based interactions")

    def filter_trades(self, ta_signals: Dict, market_heat: float) -> Dict:
        """Filter trades based on TA signals AND market heat threshold.

        :param ta_signals: Technical analysis signals dictionary
        :param market_heat: Current market heat score (-1 to 1)
        :return: Filtered trade decision with approval status
        """
        # Extract TA signal if exists
        ta_action = ta_signals.get("action", "HOLD")
        has_ta_signal = ta_action in ["BUY", "SELL"]

        # Apply AND logic: both conditions must be true
        heat_above_threshold = market_heat > self.market_heat_threshold
        trade_approved = has_ta_signal and heat_above_threshold

        # Log the decision
        decision_entry = {
            "ta_signal": ta_action,
            "has_ta_signal": has_ta_signal,
            "market_heat": market_heat,
            "heat_threshold": self.market_heat_threshold,
            "heat_above_threshold": heat_above_threshold,
            "trade_approved": trade_approved,
            "reason": self._get_rejection_reason(has_ta_signal, heat_above_threshold)
        }
        self.decision_log.append(decision_entry)

        # Log to logger for real-time monitoring
        logger.info(f"Trade Filter Decision: TA={ta_action}, Heat={market_heat:.3f}, "
                    f"Approved={trade_approved}, Reason={decision_entry['reason']}")

        # Return filtered decision
        if trade_approved:
            return {
                "action": ta_action,
                "approved": True,
                "market_heat": market_heat,
                "reason": f"TA signal {ta_action} with market heat {market_heat:.3f} > {self.market_heat_threshold}"
            }
        else:
            return {
                "action": "HOLD",
                "approved": False,
                "market_heat": market_heat,
                "reason": decision_entry['reason']
            }

    def _get_rejection_reason(self, has_ta_signal: bool, heat_above_threshold: bool) -> str:
        """Get human-readable reason for trade rejection."""
        if not has_ta_signal and not heat_above_threshold:
            return "No TA signal AND market heat too low"
        elif not has_ta_signal:
            return "No TA signal"
        elif not heat_above_threshold:
            return f"Market heat below threshold ({self.market_heat_threshold})"
        else:
            return "Trade approved"

    def decide_trade(self, aggregated: Dict, price: float, trade_date: str) -> Dict:
        """Return a BUY/SELL/HOLD decision based on MACD crossovers, sentiment, and market heat."""
        macd_y = aggregated.get("technical", {}).get("macd_yest")
        macd_t = aggregated.get("technical", {}).get("macd_today")
        sentiment = aggregated.get("sentiment", {}).get("score", 0)
        
        # Extract market heat value from the market_heat dictionary
        market_heat_data = aggregated.get("market_heat", {})
        if isinstance(market_heat_data, dict):
            market_heat = market_heat_data.get("heat_level", 0.0)
        else:
            # Fallback for backward compatibility
            market_heat = float(market_heat_data) if market_heat_data else 0.0

        action = "HOLD"

        # Use small threshold for near-zero comparisons to handle precision issues
        # This helps catch crossings that might be missed due to floating-point precision
        ZERO_THRESHOLD = 0.01

        # First determine TA signal based on MACD and sentiment
        ta_signal = {"action": "HOLD"}

        # Entry rule (TA signal)
        if self.position == 0:
            if (
                macd_y is not None and macd_y < ZERO_THRESHOLD and
                macd_t is not None and macd_t > macd_y and
                sentiment >= 0
            ):
                ta_signal = {"action": "BUY"}

        # Exit rule (TA signal)
        elif self.position == 1:
            if (
                (macd_y is not None and macd_y < ZERO_THRESHOLD and macd_t < macd_y) or
                (macd_y is not None and macd_y > -ZERO_THRESHOLD and macd_t < -ZERO_THRESHOLD)
            ):
                ta_signal = {"action": "SELL"}

        # Apply market heat filter
        filtered_decision = self.filter_trades(ta_signal, market_heat)
        action = filtered_decision["action"]

        # Execute the trade if approved
        if action == "BUY" and self.position == 0:
            self.position = 1
            self.entry_price = price
            self.entry_date = trade_date
        elif action == "SELL" and self.position == 1:
            self.position = 0
            # Record completed trade
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

        # Log trade decision with market heat data
        self.trade_log.append({
            "date": trade_date,
            "action": action,
            "price": price,
            "macd_today": macd_t,
            "macd_yest": macd_y,
            "sentiment": sentiment,
            "market_heat": market_heat,
            "ta_signal": ta_signal["action"],
            "filtered": ta_signal["action"] != action,
            "filter_reason": filtered_decision.get("reason", "")
        })

        return {
            "action": action,
            "qty": 100 if action == "BUY" else 0,
            "reason": filtered_decision.get("reason", "macd_sent_heat_rule"),
            "market_heat": market_heat,
            "ta_signal": ta_signal["action"],
            "approved": filtered_decision.get("approved", False)
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

    def get_decision_summary(self) -> Dict:
        """Get summary of all filtering decisions made."""
        if not self.decision_log:
            return {
                "total_decisions": 0,
                "approved_trades": 0,
                "rejected_trades": 0,
                "rejection_reasons": {}
            }

        total = len(self.decision_log)
        approved = sum(1 for d in self.decision_log if d["trade_approved"])
        rejected = total - approved

        # Count rejection reasons
        rejection_reasons = {}
        for decision in self.decision_log:
            if not decision["trade_approved"]:
                reason = decision["reason"]
                rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1

        return {
            "total_decisions": total,
            "approved_trades": approved,
            "rejected_trades": rejected,
            "approval_rate": approved / total if total > 0 else 0,
            "rejection_reasons": rejection_reasons,
            "avg_market_heat": np.mean([d["market_heat"] for d in self.decision_log]) if self.decision_log else 0
        }

    def print_decision_summary(self) -> None:
        """Print a formatted summary of trade filtering decisions."""
        summary = self.get_decision_summary()

        print("\n" + "=" * 60)
        print("TRADE FILTERING SUMMARY")
        print("=" * 60)

        print(f"\nDecision Statistics:")
        print(f"  Total Decisions: {summary['total_decisions']}")
        print(f"  Approved Trades: {summary['approved_trades']}")
        print(f"  Rejected Trades: {summary['rejected_trades']}")
        if summary['total_decisions'] > 0:
            print(f"  Approval Rate: {summary['approval_rate']*100:.1f}%")
            if 'avg_market_heat' in summary:
                print(f"  Avg Market Heat: {summary['avg_market_heat']:.3f}")

        if summary['rejection_reasons'] and summary['rejected_trades'] > 0:
            print(f"\nRejection Reasons:")
            for reason, count in sorted(summary['rejection_reasons'].items(), key=lambda x: x[1], reverse=True):
                print(f"  {reason}: {count} ({count/summary['rejected_trades']*100:.1f}%)")

        print("=" * 60)
    
    def get_metrics(self, initial_capital: float = 100000.0) -> Dict:
        """Wrapper method for calculate_metrics for compatibility."""
        return self.calculate_metrics(initial_capital)
