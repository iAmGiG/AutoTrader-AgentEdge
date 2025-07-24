"""Buy and Hold Strategy - Baseline for comparison.

This strategy simply buys at the start and holds throughout the period.
No trading decisions are made after initial purchase.
"""

import logging
from typing import Dict, List, Optional
import numpy as np
from datetime import datetime

logger = logging.getLogger(__name__)


class BuyHoldStrategy:
    """Buy and hold baseline strategy.
    
    Implements the same interface as StrategyAgent for fair comparison.
    Buys equal weight portfolio at start and holds entire period.
    """
    
    def __init__(self, name: str = "BuyHoldStrategy", initial_capital: float = 10000):
        self.name = name
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions = {}  # symbol -> shares
        self.entry_prices = {}  # symbol -> entry price
        self.trade_log = []
        self.equity_curve = []
        self.initialized = False
        
        # For single stock compatibility
        self.position = 0  # 0 = flat, 1 = long
        self.entry_price = None
        self.entry_date = None
        
    def initialize_portfolio(self, symbols: List[str], prices: Dict[str, float], 
                           date: str) -> Dict:
        """Initialize equal weight portfolio at start.
        
        :param symbols: List of symbols to buy
        :param prices: Current prices for each symbol
        :param date: Date of initialization
        :return: Initialization summary
        """
        if self.initialized:
            return {"error": "Portfolio already initialized"}
        
        # Equal weight allocation
        allocation_per_symbol = self.initial_capital / len(symbols)
        
        for symbol in symbols:
            price = prices.get(symbol, 0)
            if price > 0:
                shares = allocation_per_symbol / price
                self.positions[symbol] = shares
                self.entry_prices[symbol] = price
                self.cash -= shares * price
                
                # Log the "trade"
                self.trade_log.append({
                    "date": date,
                    "action": "BUY",
                    "symbol": symbol,
                    "price": price,
                    "shares": shares,
                    "value": shares * price,
                    "reason": "Initial buy-and-hold purchase"
                })
        
        self.initialized = True
        self.entry_date = date
        
        logger.info(f"Buy & Hold initialized with {len(self.positions)} positions on {date}")
        logger.info(f"Remaining cash: ${self.cash:.2f}")
        
        return {
            "positions": dict(self.positions),
            "cash_remaining": self.cash,
            "total_invested": self.initial_capital - self.cash
        }
    
    def decide_trade(self, aggregated: Dict, price: float, trade_date: str) -> Dict:
        """Buy & Hold makes no trading decisions after initialization.
        
        For single-stock backtesting compatibility.
        """
        # Handle single stock initialization if not done
        if not self.initialized and self.position == 0:
            # Buy with all capital on first call
            shares = self.initial_capital / price
            self.position = 1
            self.entry_price = price
            self.entry_date = trade_date
            self.positions[aggregated.get("symbol", "UNKNOWN")] = shares
            self.cash = 0
            self.initialized = True
            
            self.trade_log.append({
                "date": trade_date,
                "action": "BUY",
                "price": price,
                "shares": shares,
                "reason": "Buy and hold - initial purchase"
            })
            
            return {
                "action": "BUY",
                "qty": 100,  # For compatibility
                "reasoning": {
                    "strategy": "Buy and Hold",
                    "rationale": "Initial purchase - will hold entire period"
                }
            }
        
        # After initialization, always HOLD
        return {
            "action": "HOLD",
            "qty": 0,
            "reasoning": {
                "strategy": "Buy and Hold", 
                "rationale": "Strategy holds entire period after initial purchase"
            }
        }
    
    def update_equity(self, date: str, prices: Dict[str, float]):
        """Update equity curve with current portfolio value.
        
        :param date: Current date
        :param prices: Current prices for all symbols
        """
        portfolio_value = self.cash
        
        for symbol, shares in self.positions.items():
            current_price = prices.get(symbol, self.entry_prices.get(symbol, 0))
            portfolio_value += shares * current_price
        
        self.equity_curve.append({
            "date": date,
            "equity": portfolio_value,
            "cash": self.cash,
            "positions_value": portfolio_value - self.cash
        })
    
    def get_portfolio_value(self, prices: Dict[str, float]) -> float:
        """Calculate current portfolio value.
        
        :param prices: Current prices for all symbols
        :return: Total portfolio value
        """
        value = self.cash
        for symbol, shares in self.positions.items():
            price = prices.get(symbol, self.entry_prices.get(symbol, 0))
            value += shares * price
        return value
    
    def get_metrics(self, initial_capital: float = None, risk_free_rate: float = 0.02) -> Dict:
        """Calculate performance metrics matching StrategyAgent interface.
        
        Buy & Hold specific metrics:
        - No trades after initialization
        - Lower volatility typically
        - No trading costs
        """
        if initial_capital is None:
            initial_capital = self.initial_capital
        
        # For single stock, calculate based on position
        if len(self.positions) <= 1 and self.position == 1 and self.entry_price:
            # Simple return calculation
            final_value = initial_capital  # Assumes still holding
            if self.equity_curve:
                final_value = self.equity_curve[-1]["equity"]
            
            total_return = (final_value - initial_capital) / initial_capital
            
            # Calculate daily returns from equity curve
            returns = []
            if len(self.equity_curve) > 1:
                for i in range(1, len(self.equity_curve)):
                    prev_equity = self.equity_curve[i-1]["equity"]
                    curr_equity = self.equity_curve[i]["equity"]
                    daily_return = (curr_equity - prev_equity) / prev_equity
                    returns.append(daily_return)
            
            # Sharpe ratio
            sharpe_ratio = 0
            if returns:
                avg_return = np.mean(returns)
                std_return = np.std(returns)
                if std_return > 0:
                    daily_risk_free = risk_free_rate / 252
                    sharpe_ratio = np.sqrt(252) * (avg_return - daily_risk_free) / std_return
            
            # Max drawdown
            max_drawdown = 0
            if self.equity_curve:
                peak = self.equity_curve[0]["equity"]
                for point in self.equity_curve:
                    if point["equity"] > peak:
                        peak = point["equity"]
                    drawdown = (peak - point["equity"]) / peak
                    max_drawdown = max(max_drawdown, drawdown)
            
            return {
                "total_return": total_return,
                "total_return_pct": total_return * 100,
                "win_rate": 100.0 if total_return > 0 else 0.0,  # One "trade"
                "avg_win": total_return if total_return > 0 else 0,
                "avg_loss": abs(total_return) if total_return < 0 else 0,
                "profit_factor": float('inf') if total_return > 0 else 0,
                "sharpe_ratio": sharpe_ratio,
                "max_drawdown": max_drawdown,
                "num_trades": 1,  # Initial buy only
                "expectancy": total_return,
                "winning_trades": 1 if total_return > 0 else 0,
                "losing_trades": 1 if total_return < 0 else 0,
                "strategy_type": "Buy and Hold"
            }
        
        # Multi-stock portfolio metrics
        if not self.equity_curve:
            return self._empty_metrics()
        
        # Calculate returns
        initial_equity = self.equity_curve[0]["equity"] if self.equity_curve else initial_capital
        final_equity = self.equity_curve[-1]["equity"] if self.equity_curve else initial_capital
        total_return = (final_equity - initial_equity) / initial_equity
        
        # Daily returns for Sharpe
        returns = []
        for i in range(1, len(self.equity_curve)):
            prev = self.equity_curve[i-1]["equity"]
            curr = self.equity_curve[i]["equity"]
            returns.append((curr - prev) / prev)
        
        # Calculate Sharpe
        sharpe_ratio = 0
        if returns:
            avg_return = np.mean(returns)
            std_return = np.std(returns)
            if std_return > 0:
                daily_rf = risk_free_rate / 252
                sharpe_ratio = np.sqrt(252) * (avg_return - daily_rf) / std_return
        
        # Max drawdown
        peak = initial_equity
        max_dd = 0
        for point in self.equity_curve:
            if point["equity"] > peak:
                peak = point["equity"]
            dd = (peak - point["equity"]) / peak
            max_dd = max(max_dd, dd)
        
        return {
            "total_return": total_return,
            "total_return_pct": total_return * 100,
            "win_rate": 100.0 if total_return > 0 else 0.0,
            "avg_win": total_return if total_return > 0 else 0,
            "avg_loss": abs(total_return) if total_return < 0 else 0,
            "profit_factor": float('inf') if total_return > 0 else 0,
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": max_dd,
            "num_trades": len(self.positions),  # Initial buys only
            "expectancy": total_return,
            "winning_trades": len(self.positions) if total_return > 0 else 0,
            "losing_trades": len(self.positions) if total_return < 0 else 0,
            "strategy_type": "Buy and Hold"
        }
    
    def _empty_metrics(self) -> Dict:
        """Return empty metrics structure."""
        return {
            "total_return": 0.0,
            "total_return_pct": 0.0,
            "win_rate": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "profit_factor": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "num_trades": 0,
            "expectancy": 0.0,
            "winning_trades": 0,
            "losing_trades": 0,
            "strategy_type": "Buy and Hold"
        }
    
    def reset(self):
        """Reset strategy to initial state."""
        self.cash = self.initial_capital
        self.positions = {}
        self.entry_prices = {}
        self.trade_log = []
        self.equity_curve = []
        self.initialized = False
        self.position = 0
        self.entry_price = None
        self.entry_date = None