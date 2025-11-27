#!/usr/bin/env python3
"""
Orchestrator - Coordinates multi-agent trading conversations
Part of RH2MAS AutoGen trading system

Refactored to use AgentFactory and AgentBus (Issue #390).
"""

import os
import sys
from typing import Any, Dict, List, Optional

from src.utils.date_utils import get_datetime_now, now_iso

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from config_defaults.trading_config import TradingConfig

from src.autogen_agents.agent_bus import EventType, get_agent_bus

# Agent Infrastructure (Issue #390)
from src.autogen_agents.agent_factory import AgentType, get_agent_factory

# Lazy import to avoid circular dependency with cli_interface
DecisionFormatter = None


def _get_decision_formatter():
    global DecisionFormatter
    if DecisionFormatter is None:
        from src.human_interface.decision_formatter import DecisionFormatter as DF

        DecisionFormatter = DF
    return DecisionFormatter


class TradingOrchestrator:
    """
    Main orchestrator that coordinates multi-agent trading conversations.
    Manages the flow from market scanning to trade execution with human oversight.

    Uses AgentFactory for agent creation and AgentBus for event-driven coordination.
    """

    def __init__(self, initial_capital: float = 100000):
        self.config = TradingConfig()
        self.initial_capital = initial_capital

        # Get factory and bus singletons
        self._factory = get_agent_factory()
        self._bus = get_agent_bus()

        # Initialize agents via factory
        self._scanner_instance = self._factory.create(AgentType.SCANNER)
        self._voter_instance = self._factory.create(AgentType.VOTER)
        self._risk_instance = self._factory.create(AgentType.RISK)
        self._executor_instance = self._factory.create(
            AgentType.EXECUTOR,
            config_override={"extra_config": {"initial_capital": initial_capital}},
        )

        # Extract agent objects for backward compatibility
        self.scanner_agent = self._scanner_instance.agent
        self.voter_agent = self._voter_instance.agent
        self.risk_agent = self._risk_instance.agent
        self.executor_agent = self._executor_instance.agent

        # Human interface (lazy loaded to avoid circular import)
        self.decision_formatter = _get_decision_formatter()()

        # Conversation state
        self.active_conversations = {}
        self.trading_enabled = True

        # Subscribe to key events for logging/monitoring
        self._setup_event_subscriptions()

    def scan_and_analyze(self, symbols: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Complete scan and analysis workflow.

        Args:
            symbols: Symbols to scan, uses default watchlist if None

        Returns:
            Analysis results with trading recommendations
        """
        print("🔍 Starting market scan and analysis...")

        # Step 1: Scanner identifies opportunities
        print("   📊 Scanning markets for signals...")
        scan_results = self.scanner_agent.scan_for_signals(symbols)

        # Step 2: Voter evaluates each signal
        print("   🎯 Evaluating trading signals...")
        trading_recommendations = {}

        for symbol, signal_data in scan_results.items():
            if "error" in signal_data:
                trading_recommendations[symbol] = {"error": signal_data["error"]}
                continue

            # Get market data for voter analysis
            market_data = self.scanner_agent.get_market_data(symbol, days=60)
            if not market_data or "error" in market_data:
                trading_recommendations[symbol] = {"error": "Failed to get market data"}
                continue

            # Voter evaluation
            evaluation = self.voter_agent.evaluate_entry_signal(symbol, market_data)
            trading_recommendations[symbol] = evaluation

        # Step 3: Risk analysis for actionable signals
        print("   🛡️  Performing risk analysis...")
        account_status = self.executor_agent.get_account_status()
        current_positions = self.executor_agent.get_positions()["active_positions"]

        validated_trades = {}

        for symbol, recommendation in trading_recommendations.items():
            if recommendation.get("decision", "").startswith("ENTER"):
                # Create trade proposal
                trade_proposal = {
                    "symbol": symbol,
                    "entry_price": recommendation.get("current_price", 0),
                    "action": "BUY",
                }

                # Risk validation
                risk_validation = self.risk_agent.validate_trade(
                    trade_proposal, account_status["total_value"], current_positions
                )

                validated_trades[symbol] = {
                    "trading_signal": recommendation,
                    "risk_validation": risk_validation,
                    "recommended_for_human": risk_validation["final_recommendation"] == "APPROVE",
                }

        return {
            "scan_results": scan_results,
            "trading_recommendations": trading_recommendations,
            "validated_trades": validated_trades,
            "account_status": account_status,
            "timestamp": now_iso(),
        }

    def execute_approved_trade(
        self, symbol: str, validation_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a human-approved trade.

        Args:
            symbol: Stock symbol
            validation_result: Risk validation result

        Returns:
            Execution result
        """
        try:
            trade_summary = validation_result["trade_summary"]

            trade_order = {
                "symbol": symbol,
                "action": "BUY",
                "shares": trade_summary["recommended_shares"],
                "price": trade_summary["entry_price"],
            }

            execution_result = self.executor_agent.execute_trade(trade_order)

            return {
                "symbol": symbol,
                "execution_result": execution_result,
                "trade_summary": trade_summary,
                "timestamp": now_iso(),
            }

        except Exception as e:
            return {"symbol": symbol, "error": str(e), "timestamp": now_iso()}

    def monitor_positions(
        self, current_prices: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Monitor existing positions for exit signals.

        Args:
            current_prices: Current market prices, fetched if None

        Returns:
            Position monitoring results
        """
        print("📈 Monitoring existing positions...")

        # Get current positions
        positions_info = self.executor_agent.get_positions()
        active_positions = positions_info["active_positions"]

        if not active_positions:
            return {
                "message": "No active positions to monitor",
                "account_status": self.executor_agent.get_account_status(),
            }

        # Fetch current prices if not provided
        if current_prices is None:
            current_prices = {}
            for position in active_positions:
                symbol = position["symbol"]
                market_data = self.scanner_agent.get_market_data(symbol, days=1)
                if market_data and "current_price" in market_data:
                    current_prices[symbol] = market_data["current_price"]

        # Update positions and check for exits
        update_result = self.executor_agent.update_positions(current_prices)

        # Analyze exit signals for remaining positions
        exit_recommendations = {}
        remaining_positions = [
            pos
            for pos in active_positions
            if pos["symbol"]
            not in [exit["symbol"] for exit in update_result.get("triggered_exits", [])]
        ]

        for position in remaining_positions:
            symbol = position["symbol"]
            current_price = current_prices.get(symbol, position["entry_price"])

            exit_evaluation = self.voter_agent.evaluate_exit_signal(
                symbol, position["entry_price"], current_price, "long"
            )

            exit_recommendations[symbol] = exit_evaluation

        return {
            "automatic_exits": update_result.get("triggered_exits", []),
            "exit_recommendations": exit_recommendations,
            "position_updates": update_result,
            "account_status": update_result.get("account_status", {}),
            "timestamp": now_iso(),
        }

    def generate_trading_report(self) -> str:
        """Generate comprehensive trading status report."""
        report_parts = [
            "🤖 RH2MAS TRADING SYSTEM REPORT",
            "=" * 60,
            f"Generated: {get_datetime_now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]

        # Account status
        account_status = self.executor_agent.get_account_status()
        report_parts.extend(
            [
                "💰 ACCOUNT STATUS:",
                "-" * 20,
                f"Total Value: ${account_status.get('total_value', 0):,.2f}",
                f"Available Cash: ${account_status.get('available_cash', 0):,.2f}",
                f"Total Return: {account_status.get('total_return_pct', 0):.2%}",
                f"Unrealized P&L: ${account_status.get('unrealized_pnl', 0):,.2f}",
                f"Realized P&L: ${account_status.get('realized_pnl', 0):,.2f}",
                "",
            ]
        )

        # Position summary
        positions_info = self.executor_agent.get_positions()
        active_count = positions_info.get("total_positions", 0)

        report_parts.extend([f"📊 POSITIONS ({active_count} active):", "-" * 20])

        if active_count > 0:
            for pos in positions_info["active_positions"]:
                report_parts.append(
                    f"  {pos['symbol']}: {pos['shares']} shares @ ${pos['entry_price']:.2f}"
                )
        else:
            report_parts.append("  No active positions")

        report_parts.append("")

        # System status
        report_parts.extend(
            [
                "⚙️  SYSTEM STATUS:",
                "-" * 20,
                f"Trading Enabled: {'Yes' if self.trading_enabled else 'No'}",
                "Paper Trading: Yes",
                f"Active Conversations: {len(self.active_conversations)}",
                "",
            ]
        )

        # Configuration summary
        macd_config = self.config.get_macd_config()
        exit_config = self.config.get_exit_config()

        report_parts.extend(
            [
                "🔧 CONFIGURATION:",
                "-" * 20,
                f"MACD: {macd_config.fast}/{macd_config.slow}/{macd_config.signal}",
                f"RSI: {self.config.get_rsi_config().period} period",
                f"Exit Strategy: +{exit_config.take_profit_pct:.1%} TP / -{exit_config.stop_loss_pct:.1%} SL",
                "",
            ]
        )

        return "\n".join(report_parts)

    def create_human_decision_prompt(self, analysis_results: Dict[str, Any]) -> str:
        """
        Create formatted prompt for human trading decisions.

        Args:
            analysis_results: Results from scan_and_analyze

        Returns:
            Formatted decision prompt
        """
        return self.decision_formatter.format_trading_decision(
            analysis_results["validated_trades"], analysis_results["account_status"]
        )

    def _setup_event_subscriptions(self):
        """Subscribe to key events for monitoring and logging."""

        # Log all trade executions
        def log_trade(msg):
            symbol = msg.symbol or "UNKNOWN"
            order_id = msg.payload.get("order_id", "N/A")
            print(f"[Orchestrator] Trade executed: {symbol} - Order {order_id}")

        # Log position updates
        def log_position(msg):
            symbol = msg.symbol or "UNKNOWN"
            print(f"[Orchestrator] Position updated: {symbol}")

        self._bus.subscribe("orchestrator", EventType.TRADE_EXECUTED, log_trade)
        self._bus.subscribe("orchestrator", EventType.POSITION_UPDATED, log_position)

    def get_factory_stats(self) -> dict:
        """Get agent factory statistics."""
        return self._factory.get_factory_stats()

    def get_bus_stats(self) -> dict:
        """Get agent bus statistics."""
        return self._bus.get_stats()

    def shutdown(self):
        """Gracefully shutdown the orchestrator."""
        print("🔄 Shutting down trading orchestrator...")
        self.trading_enabled = False
        self.active_conversations.clear()

        # Unsubscribe from events
        self._bus.unsubscribe("orchestrator", EventType.TRADE_EXECUTED)
        self._bus.unsubscribe("orchestrator", EventType.POSITION_UPDATED)

        print("✅ Orchestrator shutdown complete")


def create_trading_orchestrator(initial_capital: float = 100000) -> TradingOrchestrator:
    """Factory function to create a fully configured trading orchestrator."""
    return TradingOrchestrator(initial_capital=initial_capital)
