"""
Risk Calculation - Pure Functions

Portfolio-level risk metrics and position sizing.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class RiskMetrics:
    """Portfolio risk metrics."""

    total_portfolio_value: float
    position_value: float
    cash_value: float
    position_exposure_pct: float
    largest_position_pct: float
    total_unrealized_pnl: float
    total_unrealized_pnl_pct: float
    max_daily_loss_risk: float  # Max loss if all positions hit stop loss
    portfolio_beta: Optional[float] = None
    var_95: Optional[float] = None  # 95% Value at Risk


def calculate_portfolio_risk(
    positions: List[Dict], cash: float, portfolio_history: Optional[pd.DataFrame] = None
) -> RiskMetrics:
    """
    Calculate comprehensive portfolio risk metrics.

    Args:
        positions: List of position dictionaries
        cash: Available cash
        portfolio_history: Historical portfolio values for advanced metrics

    Returns:
        RiskMetrics object
    """
    # Basic portfolio metrics
    total_position_value = sum(p["position_value"] for p in positions)
    total_portfolio_value = total_position_value + cash

    # Position exposure
    position_exposure_pct = (
        (total_position_value / total_portfolio_value) * 100 if total_portfolio_value > 0 else 0
    )

    # Largest position risk
    if positions:
        largest_position_value = max(p["position_value"] for p in positions)
        largest_position_pct = (largest_position_value / total_portfolio_value) * 100
    else:
        largest_position_pct = 0

    # P&L metrics
    total_unrealized_pnl = sum(p["unrealized_pnl"] for p in positions)
    total_unrealized_pnl_pct = (
        (total_unrealized_pnl / total_portfolio_value) * 100 if total_portfolio_value > 0 else 0
    )

    # Maximum daily loss risk (all positions hit stop loss)
    max_daily_loss = 0
    for position in positions:
        # Use actual stop loss if available, otherwise default to 5%
        pos_value = position.get("position_value", 0)
        entry_price = position.get("entry_price", 0)
        stop_price = position.get("stop_loss_price") or position.get("stop_price")
        side = position.get("side", "long").lower()  # Default to long if not specified

        if stop_price and entry_price > 0:
            # Calculate risk based on position side
            if side == "short":
                # For shorts: stop is above entry, so risk is (stop - entry)
                risk_pct = max(0, (stop_price - entry_price) / entry_price)
            else:
                # For longs: stop is below entry, so risk is (entry - stop)
                risk_pct = max(0, (entry_price - stop_price) / entry_price)
            max_daily_loss += pos_value * risk_pct
        else:
            # No stop loss - assume 5% risk
            symbol = position.get("symbol", "UNKNOWN")
            logger.debug(
                f"Position {symbol}: no stop loss defined, assuming 5% risk "
                f"(stop_price={stop_price}, entry_price={entry_price})"
            )
            max_daily_loss += pos_value * 0.05

    # Advanced metrics if portfolio history available
    portfolio_beta = None
    var_95 = None

    if portfolio_history is not None and len(portfolio_history) > 30:
        # Calculate daily returns
        returns = portfolio_history["portfolio_value"].pct_change().dropna()

        if len(returns) > 10:
            # 95% Value at Risk (5th percentile of daily returns)
            var_95 = np.percentile(returns, 5) * total_portfolio_value

            # Simple beta calculation (vs market if SPY data available)
            # This would need market data to calculate properly
            portfolio_beta = 1.0  # Placeholder

    return RiskMetrics(
        total_portfolio_value=total_portfolio_value,
        position_value=total_position_value,
        cash_value=cash,
        position_exposure_pct=position_exposure_pct,
        largest_position_pct=largest_position_pct,
        total_unrealized_pnl=total_unrealized_pnl,
        total_unrealized_pnl_pct=total_unrealized_pnl_pct,
        max_daily_loss_risk=max_daily_loss,
        portfolio_beta=portfolio_beta,
        var_95=var_95,
    )


def calculate_position_size(
    portfolio_value: float,
    risk_per_trade: float = 0.02,
    entry_price: float = 0,
    stop_loss_price: float = 0,
) -> Dict[str, float]:
    """
    Calculate position size based on risk management.

    Args:
        portfolio_value: Total portfolio value
        risk_per_trade: Risk per trade as percentage (default 2%)
        entry_price: Planned entry price
        stop_loss_price: Planned stop loss price

    Returns:
        Dictionary with position sizing recommendations
    """
    risk_amount = portfolio_value * risk_per_trade

    if entry_price > 0 and stop_loss_price > 0:
        # Calculate shares based on stop loss distance
        price_risk_per_share = abs(entry_price - stop_loss_price)
        if price_risk_per_share > 0:
            shares = int(risk_amount / price_risk_per_share)
            position_value = shares * entry_price

            return {
                "recommended_shares": shares,
                "position_value": position_value,
                "risk_amount": risk_amount,
                "position_size_pct": (position_value / portfolio_value) * 100,
            }

    # Fallback: equal weight approach
    logger.warning(
        f"Position sizing fallback: entry_price={entry_price}, "
        f"stop_loss={stop_loss_price} - using equal weight (10% max) instead of risk-based"
    )
    max_position_pct = 0.10  # Max 10% per position
    max_position_value = portfolio_value * max_position_pct

    if entry_price > 0:
        shares = int(max_position_value / entry_price)
        position_value = shares * entry_price
        logger.info(
            f"Equal weight sizing: {shares} shares @ ${entry_price:.2f} "
            f"= ${position_value:.2f} ({max_position_pct * 100}% of portfolio)"
        )

        return {
            "recommended_shares": shares,
            "position_value": position_value,
            "risk_amount": position_value * 0.05,  # Assume 5% stop loss
            "position_size_pct": (position_value / portfolio_value) * 100,
        }

    # Cannot size position without entry price
    logger.error(
        f"Cannot calculate position size: entry_price={entry_price} is invalid. "
        f"Returning zero position."
    )
    return {
        "recommended_shares": 0,
        "position_value": 0,
        "risk_amount": risk_amount,
        "position_size_pct": 0,
    }


def check_portfolio_limits(
    current_positions: int,
    position_exposure_pct: float,
    largest_position_pct: float,
    limits_config: Optional[Dict[str, float]] = None,
) -> Dict[str, bool]:
    """
    Check portfolio risk limits.

    Args:
        current_positions: Number of current positions
        position_exposure_pct: Percentage of portfolio in positions
        largest_position_pct: Largest single position percentage
        limits_config: Optional dictionary of limits (max_positions, max_exposure_pct, max_single_position_pct)

    Returns:
        Dictionary of limit checks
    """
    cfg = limits_config or {}
    max_pos = cfg.get("max_positions", 10)
    max_exp = cfg.get("max_exposure_pct", 80.0)
    max_single = cfg.get("max_single_position_pct", 15.0)

    limits = {
        "max_positions": current_positions <= max_pos,
        "max_exposure": position_exposure_pct <= max_exp,
        "max_single_position": largest_position_pct <= max_single,
        # If only 1 position, allow up to 25%
        "diversification_ok": current_positions <= 1 or largest_position_pct <= 25,
    }

    limits["all_limits_ok"] = all(limits.values())

    return limits


def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.02) -> float:
    """
    Calculate Sharpe ratio from returns.

    Args:
        returns: Series of daily returns
        risk_free_rate: Annual risk-free rate (default 2%)

    Returns:
        Sharpe ratio
    """
    if len(returns) < 2:
        return 0.0

    excess_returns = returns - (risk_free_rate / 252)  # Daily risk-free rate

    if excess_returns.std() == 0:
        return 0.0

    sharpe = np.sqrt(252) * excess_returns.mean() / excess_returns.std()
    return float(sharpe)


def calculate_max_drawdown(portfolio_values: pd.Series) -> Dict[str, float]:
    """
    Calculate maximum drawdown.

    Args:
        portfolio_values: Series of portfolio values

    Returns:
        Dictionary with drawdown metrics
    """
    if len(portfolio_values) < 2:
        return {"max_drawdown_pct": 0.0, "current_drawdown_pct": 0.0}

    # Calculate running maximum
    running_max = portfolio_values.expanding().max()

    # Calculate drawdown
    drawdown = (portfolio_values - running_max) / running_max

    max_drawdown = drawdown.min()
    current_drawdown = drawdown.iloc[-1]

    return {"max_drawdown_pct": max_drawdown * 100, "current_drawdown_pct": current_drawdown * 100}
