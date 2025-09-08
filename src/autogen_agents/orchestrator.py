#!/usr/bin/env python3
"""
Orchestrator - Coordinates multi-agent trading conversations
Part of RH2MAS AutoGen trading system
"""

import autogen
from typing import Dict, List, Any, Optional
import asyncio
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.autogen_agents.scanner_agent import create_scanner_agent
from src.autogen_agents.voter_agent import create_voter_agent
from src.autogen_agents.risk_agent import create_risk_agent
from src.autogen_agents.executor_agent import create_executor_agent
from src.human_interface.decision_formatter import DecisionFormatter
from config.trading_config import TradingConfig

class TradingOrchestrator:
    """
    Main orchestrator that coordinates multi-agent trading conversations.
    Manages the flow from market scanning to trade execution with human oversight.
    """
    
    def __init__(self, initial_capital: float = 100000):
        self.config = TradingConfig()
        self.initial_capital = initial_capital
        
        # Initialize agents
        self.scanner_agent = create_scanner_agent()
        self.voter_agent = create_voter_agent()
        self.risk_agent = create_risk_agent()
        self.executor_agent = create_executor_agent(initial_capital)
        
        # Human interface
        self.decision_formatter = DecisionFormatter()
        
        # Conversation state
        self.active_conversations = {}
        self.trading_enabled = True
        
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
        current_positions = self.executor_agent.get_positions()['active_positions']
        
        validated_trades = {}
        
        for symbol, recommendation in trading_recommendations.items():
            if recommendation.get('decision', '').startswith('ENTER'):
                # Create trade proposal
                trade_proposal = {
                    'symbol': symbol,
                    'entry_price': recommendation.get('current_price', 0),
                    'action': 'BUY'
                }
                
                # Risk validation
                risk_validation = self.risk_agent.validate_trade(
                    trade_proposal,
                    account_status['total_value'],
                    current_positions
                )
                
                validated_trades[symbol] = {
                    'trading_signal': recommendation,
                    'risk_validation': risk_validation,
                    'recommended_for_human': risk_validation['final_recommendation'] == 'APPROVE'
                }
        
        return {
            'scan_results': scan_results,
            'trading_recommendations': trading_recommendations,
            'validated_trades': validated_trades,
            'account_status': account_status,
            'timestamp': datetime.now().isoformat()
        }
    
    def execute_approved_trade(self, symbol: str, validation_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a human-approved trade.
        
        Args:
            symbol: Stock symbol
            validation_result: Risk validation result
            
        Returns:
            Execution result
        """
        try:
            trade_summary = validation_result['trade_summary']
            
            trade_order = {
                'symbol': symbol,
                'action': 'BUY',
                'shares': trade_summary['recommended_shares'],
                'price': trade_summary['entry_price']
            }
            
            execution_result = self.executor_agent.execute_trade(trade_order)
            
            return {
                'symbol': symbol,
                'execution_result': execution_result,
                'trade_summary': trade_summary,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'symbol': symbol,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def monitor_positions(self, current_prices: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
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
        active_positions = positions_info['active_positions']
        
        if not active_positions:
            return {
                'message': 'No active positions to monitor',
                'account_status': self.executor_agent.get_account_status()
            }
        
        # Fetch current prices if not provided
        if current_prices is None:
            current_prices = {}
            for position in active_positions:
                symbol = position['symbol']
                market_data = self.scanner_agent.get_market_data(symbol, days=1)
                if market_data and 'current_price' in market_data:
                    current_prices[symbol] = market_data['current_price']
        
        # Update positions and check for exits
        update_result = self.executor_agent.update_positions(current_prices)
        
        # Analyze exit signals for remaining positions
        exit_recommendations = {}
        remaining_positions = [pos for pos in active_positions 
                             if pos['symbol'] not in [exit['symbol'] for exit in update_result.get('triggered_exits', [])]]
        
        for position in remaining_positions:
            symbol = position['symbol']
            current_price = current_prices.get(symbol, position['entry_price'])
            
            exit_evaluation = self.voter_agent.evaluate_exit_signal(
                symbol,
                position['entry_price'],
                current_price,
                'long'
            )
            
            exit_recommendations[symbol] = exit_evaluation
        
        return {
            'automatic_exits': update_result.get('triggered_exits', []),
            'exit_recommendations': exit_recommendations,
            'position_updates': update_result,
            'account_status': update_result.get('account_status', {}),
            'timestamp': datetime.now().isoformat()
        }
    
    def generate_trading_report(self) -> str:
        """Generate comprehensive trading status report."""
        report_parts = [
            "🤖 RH2MAS TRADING SYSTEM REPORT",
            "=" * 60,
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            ""
        ]
        
        # Account status
        account_status = self.executor_agent.get_account_status()
        report_parts.extend([
            "💰 ACCOUNT STATUS:",
            "-" * 20,
            f"Total Value: ${account_status.get('total_value', 0):,.2f}",
            f"Available Cash: ${account_status.get('available_cash', 0):,.2f}",
            f"Total Return: {account_status.get('total_return_pct', 0):.2%}",
            f"Unrealized P&L: ${account_status.get('unrealized_pnl', 0):,.2f}",
            f"Realized P&L: ${account_status.get('realized_pnl', 0):,.2f}",
            ""
        ])
        
        # Position summary
        positions_info = self.executor_agent.get_positions()
        active_count = positions_info.get('total_positions', 0)
        
        report_parts.extend([
            f"📊 POSITIONS ({active_count} active):",
            "-" * 20
        ])
        
        if active_count > 0:
            for pos in positions_info['active_positions']:
                report_parts.append(
                    f"  {pos['symbol']}: {pos['shares']} shares @ ${pos['entry_price']:.2f}"
                )
        else:
            report_parts.append("  No active positions")
        
        report_parts.append("")
        
        # System status
        report_parts.extend([
            "⚙️  SYSTEM STATUS:",
            "-" * 20,
            f"Trading Enabled: {'Yes' if self.trading_enabled else 'No'}",
            f"Paper Trading: Yes",
            f"Active Conversations: {len(self.active_conversations)}",
            ""
        ])
        
        # Configuration summary
        macd_config = self.config.get_macd_config()
        exit_config = self.config.get_exit_config()
        
        report_parts.extend([
            "🔧 CONFIGURATION:",
            "-" * 20,
            f"MACD: {macd_config.fast_period}/{macd_config.slow_period}/{macd_config.signal_period}",
            f"RSI: {self.config.get_rsi_config().period} period",
            f"Exit Strategy: +{exit_config.take_profit_pct:.1%} TP / -{exit_config.stop_loss_pct:.1%} SL",
            ""
        ])
        
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
            analysis_results['validated_trades'],
            analysis_results['account_status']
        )
    
    def shutdown(self):
        """Gracefully shutdown the orchestrator."""
        print("🔄 Shutting down trading orchestrator...")
        self.trading_enabled = False
        self.active_conversations.clear()
        print("✅ Orchestrator shutdown complete")

def create_trading_orchestrator(initial_capital: float = 100000) -> TradingOrchestrator:
    """Factory function to create a fully configured trading orchestrator."""
    return TradingOrchestrator(initial_capital=initial_capital)

# Example usage functions for testing
def run_market_scan_example():
    """Example of running a complete market scan."""
    orchestrator = create_trading_orchestrator()
    
    print("Starting RH2MAS Trading System Example...")
    print("-" * 50)
    
    # Run scan and analysis
    results = orchestrator.scan_and_analyze(['AAPL', 'MSFT', 'NVDA'])
    
    # Display results
    print("\n" + orchestrator.generate_trading_report())
    
    # Show human decision prompt
    if results['validated_trades']:
        print("\n" + "="*60)
        print("HUMAN DECISION REQUIRED:")
        print("="*60)
        decision_prompt = orchestrator.create_human_decision_prompt(results)
        print(decision_prompt)
    
    return results

if __name__ == "__main__":
    # Run example
    results = run_market_scan_example()