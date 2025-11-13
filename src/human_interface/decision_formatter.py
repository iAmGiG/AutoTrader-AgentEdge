#!/usr/bin/env python3
"""
Decision Formatter - Formats trading decisions for human review
Part of RH2MAS AutoGen trading system
"""

from typing import Dict, List, Any
from datetime import datetime  # TODO date utils


class DecisionFormatter:
    """
    Formats trading analysis results into human-readable decision prompts.
    Provides clear, actionable information for trading decisions.
    """

    def format_trading_decision(self, validated_trades: Dict[str, Any],
                                account_status: Dict[str, Any]) -> str:
        """
        Format validated trades into a human decision prompt.

        Args:
            validated_trades: Dictionary of validated trading opportunities
            account_status: Current account status

        Returns:
            Formatted decision prompt string
        """
        if not validated_trades:
            return "No trading opportunities available at current risk levels."

        prompt_parts = []

        # Header
        prompt_parts.extend([
            "🤖 TRADING DECISION REQUIRED",
            "=" * 50,
            f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Available Capital: ${account_status.get('available_cash', 0):,.2f}",
            f"Total Portfolio: ${account_status.get('total_value', 0):,.2f}",
            ""
        ])

        # Individual trade opportunities
        approved_count = 0
        total_capital_required = 0

        for symbol, trade_info in validated_trades.items():
            if not trade_info.get('recommended_for_human', False):
                continue

            approved_count += 1
            trading_signal = trade_info['trading_signal']
            risk_validation = trade_info['risk_validation']
            trade_summary = risk_validation['trade_summary']

            total_capital_required += trade_summary['position_value']

            # Trade details
            prompt_parts.extend([
                f"{'='*40}",
                f"📊 OPPORTUNITY #{approved_count}: {symbol}",
                f"{'='*40}",
                ""
            ])

            # Signal analysis
            confidence = trading_signal.get('confidence', 0)
            signal_strength = trading_signal.get('signal_strength', 0)

            prompt_parts.extend([
                "🎯 SIGNAL ANALYSIS:",
                f"   Decision: {trading_signal.get('decision', 'Unknown')}",
                f"   Confidence: {confidence:.1%}",
                f"   Signal Strength: {signal_strength:.2f}",
                f"   Reason: {trading_signal.get('reason', 'No reason provided')}",
                ""
            ])

            # Technical indicators
            if 'macd_bullish' in trading_signal and 'rsi_bullish' in trading_signal:
                macd_status = "✅ Bullish" if trading_signal['macd_bullish'] else "❌ Bearish"
                rsi_status = "✅ Bullish" if trading_signal['rsi_bullish'] else "❌ Bearish"

                prompt_parts.extend([
                    "📈 TECHNICAL INDICATORS:",
                    f"   MACD(13/34/8): {macd_status}",
                    f"   RSI(14): {rsi_status}",
                    f"   Current Price: ${trading_signal.get('current_price', 0):.2f}",
                    ""
                ])

            # Position sizing and risk
            prompt_parts.extend([
                "💰 POSITION SIZING:",
                f"   Recommended Shares: {trade_summary['recommended_shares']:,}",
                f"   Position Value: ${trade_summary['position_value']:,.2f}",
                f"   Entry Price: ${trade_summary['entry_price']:.2f}",
                f"   Stop Loss: ${trade_summary['stop_loss_price']:.2f}",
                f"   Risk Amount: ${trade_summary['risk_amount']:,.2f}",
                ""
            ])

            # Risk assessment
            risk_assessment = risk_validation['risk_assessment']
            risk_level = risk_assessment.get('risk_level', 'Unknown')
            risk_flags = risk_assessment.get('risk_flags', [])

            risk_emoji = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴"}.get(risk_level, "⚪")

            prompt_parts.extend([
                "🛡️  RISK ASSESSMENT:",
                f"   Risk Level: {risk_emoji} {risk_level}",
                f"   Portfolio Impact: {trade_summary['risk_amount'] / account_status.get('total_value', 1):.1%}",
            ])

            if risk_flags:
                prompt_parts.append(f"   Risk Flags: {', '.join(risk_flags)}")

            prompt_parts.append("")

            # Expected outcomes
            # Using config to get exit percentages for calculation
            take_profit_pct = 0.08  # 8% from balanced config
            stop_loss_pct = 0.05    # 5% from balanced config

            profit_target = trade_summary['position_value'] * take_profit_pct
            loss_target = trade_summary['position_value'] * stop_loss_pct

            prompt_parts.extend([
                "🎲 EXPECTED OUTCOMES:",
                f"   Profit Target (+8%): ${profit_target:+,.2f}",
                f"   Stop Loss (-5%): ${-loss_target:,.2f}",
                f"   Expected Value: +1.5% at 50% win rate",
                ""
            ])

        # Summary
        if approved_count > 0:
            portfolio_impact = total_capital_required / account_status.get('total_value', 1)

            prompt_parts.extend([
                "=" * 50,
                "📊 DECISION SUMMARY:",
                "-" * 20,
                f"Total Opportunities: {approved_count}",
                f"Total Capital Required: ${total_capital_required:,.2f}",
                f"Portfolio Impact: {portfolio_impact:.1%}",
                f"Available Capital: ${account_status.get('available_cash', 0):,.2f}",
                ""
            ])

            if total_capital_required <= account_status.get('available_cash', 0):
                prompt_parts.append("✅ Sufficient capital available for all trades")
            else:
                shortfall = total_capital_required - account_status.get('available_cash', 0)
                prompt_parts.append(f"⚠️  Capital shortfall: ${shortfall:,.2f}")

            prompt_parts.extend([
                "",
                "🤔 DECISION REQUIRED:",
                "   Review each opportunity above",
                "   Consider your risk tolerance",
                "   Execute approved trades manually",
                ""
            ])

        return "\n".join(prompt_parts)

    def format_position_summary(self, positions: List[Dict[str, Any]],
                                account_status: Dict[str, Any]) -> str:
        """
        Format current positions into a readable summary.

        Args:
            positions: List of current positions
            account_status: Account status information

        Returns:
            Formatted position summary
        """
        if not positions:
            return "No active positions."

        summary_parts = [
            "📊 CURRENT POSITIONS",
            "=" * 40,
            f"Portfolio Value: ${account_status.get('total_value', 0):,.2f}",
            f"Unrealized P&L: ${account_status.get('unrealized_pnl', 0):+,.2f}",
            ""
        ]

        total_position_value = 0

        for i, position in enumerate(positions, 1):
            symbol = position.get('symbol', 'Unknown')
            shares = position.get('shares', 0)
            entry_price = position.get('entry_price', 0)
            position_value = shares * entry_price
            total_position_value += position_value

            summary_parts.extend([
                f"Position #{i}: {symbol}",
                f"   Shares: {shares:,}",
                f"   Entry: ${entry_price:.2f}",
                f"   Value: ${position_value:,.2f}",
                f"   Stop Loss: ${position.get('stop_loss_price', 0):.2f}",
                f"   Take Profit: ${position.get('take_profit_price', 0):.2f}",
                ""
            ])

        # Portfolio allocation
        if account_status.get('total_value', 0) > 0:
            allocation_pct = total_position_value / account_status['total_value']
            summary_parts.extend([
                "-" * 40,
                f"Total Position Value: ${total_position_value:,.2f}",
                f"Portfolio Allocation: {allocation_pct:.1%}",
                f"Cash Available: ${account_status.get('available_cash', 0):,.2f}"
            ])

        return "\n".join(summary_parts)

    def format_exit_recommendation(self, symbol: str, exit_analysis: Dict[str, Any]) -> str:
        """
        Format exit signal analysis into a recommendation.

        Args:
            symbol: Stock symbol
            exit_analysis: Exit analysis results

        Returns:
            Formatted exit recommendation
        """
        decision = exit_analysis.get('decision', 'UNKNOWN')
        reason = exit_analysis.get('reason', 'No reason provided')

        # Decision emoji
        decision_emoji = {
            'EXIT_PROFIT': '🎯',
            'EXIT_LOSS': '🛑',
            'HOLD': '⏳',
            'ERROR': '❌'
        }.get(decision, '❓')

        recommendation_parts = [
            f"{decision_emoji} EXIT ANALYSIS: {symbol}",
            "=" * 30,
            f"Decision: {decision}",
            f"Reason: {reason}",
            ""
        ]

        # Position details if available
        if 'entry_price' in exit_analysis and 'current_price' in exit_analysis:
            entry_price = exit_analysis['entry_price']
            current_price = exit_analysis['current_price']
            pnl_pct = exit_analysis.get('unrealized_pnl_pct', 0)

            recommendation_parts.extend([
                "Position Details:",
                f"   Entry Price: ${entry_price:.2f}",
                f"   Current Price: ${current_price:.2f}",
                f"   Unrealized P&L: {pnl_pct:+.2%}",
                ""
            ])

        # Exit configuration if available
        if 'exit_config' in exit_analysis:
            exit_config = exit_analysis['exit_config']
            recommendation_parts.extend([
                "Exit Targets:",
                f"   Take Profit: +{exit_config.get('take_profit_pct', 0):.1%}",
                f"   Stop Loss: -{exit_config.get('stop_loss_pct', 0):.1%}",
            ])

        return "\n".join(recommendation_parts)

    def format_execution_result(self, execution_results: List[Dict[str, Any]]) -> str:
        """
        Format trade execution results.

        Args:
            execution_results: List of execution results

        Returns:
            Formatted execution summary
        """
        if not execution_results:
            return "No trades executed."

        summary_parts = [
            "🔄 EXECUTION RESULTS",
            "=" * 30,
            ""
        ]

        successful_count = 0
        failed_count = 0
        total_value = 0

        for result in execution_results:
            symbol = result.get('symbol', 'Unknown')
            exec_result = result.get('execution_result', {})
            status = exec_result.get('status', 'Unknown')

            if status == 'FILLED':
                successful_count += 1
                execution_price = exec_result.get('execution_price', 0)
                shares = exec_result.get('shares', 0)
                order_value = exec_result.get('order_value', 0)
                total_value += order_value

                summary_parts.extend([
                    f"✅ {symbol}: FILLED",
                    f"   Shares: {shares:,}",
                    f"   Price: ${execution_price:.2f}",
                    f"   Value: ${order_value:,.2f}",
                    ""
                ])
            else:
                failed_count += 1
                reason = exec_result.get('reason', 'Unknown error')
                summary_parts.extend([
                    f"❌ {symbol}: FAILED",
                    f"   Reason: {reason}",
                    ""
                ])

        # Summary stats
        summary_parts.extend([
            "-" * 30,
            f"Successful: {successful_count}",
            f"Failed: {failed_count}",
            f"Total Value: ${total_value:,.2f}"
        ])

        return "\n".join(summary_parts)
