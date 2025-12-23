"""
Voter Agent CLI Tools - FunctionTool wrappers for MACD+RSI voting strategy.

Issue #488: /voter command group for visibility and configuration.

This module wraps VoterAgent functionality as FunctionTool instances
for integration with the AutoGen agent architecture.

Original Implementation: src/autogen_agents/agents/voter_agent.py
Pattern: Pure function wrappers → FunctionTool → Registry
"""

from typing import Any, Dict

from autogen_core.tools import FunctionTool

from config_defaults.trading_config import TradingConfig

from src.utils.safe_print import get_symbol

# ============================================================================
# Pure Function Wrappers
# ============================================================================


def show_voter_config() -> str:
    """
    Display current VoterAgent configuration.

    Shows all MACD and RSI parameters used by the voting strategy,
    along with voting thresholds and validated performance metrics.

    Returns:
        Formatted string with configuration details

    Example:
        >>> show_voter_config()
        'Voter Configuration
        MACD: 13/34/8 (Fibonacci)
        RSI: 14 [30/70]
        Validated Sharpe: 0.856'
    """
    config = TradingConfig()
    macd = config.get_macd_config()
    rsi = config.get_rsi_config()

    output = f"{get_symbol('INFO')} VoterAgent Configuration\n"
    output += "=" * 50 + "\n"

    # MACD settings
    output += "MACD Parameters (Fibonacci)\n"
    output += f"  Fast Period:   {macd.fast}\n"
    output += f"  Slow Period:   {macd.slow}\n"
    output += f"  Signal Period: {macd.signal}\n"
    output += "-" * 50 + "\n"

    # RSI settings
    output += "RSI Parameters\n"
    output += f"  Period:     {rsi.period}\n"
    output += f"  Oversold:   {rsi.oversold}\n"
    output += f"  Overbought: {rsi.overbought}\n"
    output += "-" * 50 + "\n"

    # Voting thresholds (hardcoded validated values)
    output += "Voting Thresholds\n"
    output += "  MACD Threshold:    0.1\n"
    output += "  Consensus Boost:   0.15\n"
    output += "  Weak Signal Boost: 0.10\n"
    output += "  Min Data Points:   42\n"
    output += "-" * 50 + "\n"

    # Validated performance
    output += "Validated Performance (2024-2025)\n"
    output += "  Sharpe Ratio:  0.856\n"
    output += "  Total Return:  36.6%\n"
    output += "  Win Rate:      51.4%\n"
    output += "  Max Drawdown:  -10.10%\n"

    return output


def explain_voting_logic() -> str:
    """
    Explain how the MACD+RSI voting strategy works.

    Describes the consensus logic, signal types, and position sizing
    based on the voting outcome.

    Returns:
        Formatted explanation of the voting system

    Example:
        >>> explain_voting_logic()
        'Voting Logic
        STRONG: Both agree → Full position (1.0)
        WEAK: One signals → Half position (0.5)
        HOLD: Conflict/Neutral → No position'
    """
    output = "🗳️ MACD+RSI Voting Logic\n"
    output += "=" * 50 + "\n\n"

    output += "How It Works:\n"
    output += "-" * 50 + "\n"
    output += "1. MACD generates BUY/SELL/HOLD based on histogram\n"
    output += "2. RSI generates BUY/SELL/HOLD based on oversold/overbought\n"
    output += "3. Votes are combined for consensus decision\n\n"

    output += "Signal Types:\n"
    output += "-" * 50 + "\n"
    output += "STRONG (Full Position 1.0x)\n"
    output += "  Both MACD and RSI agree on direction\n"
    output += "  Confidence: 0.75-0.85\n\n"

    output += "WEAK (Half Position 0.5x)\n"
    output += "  One indicator signals, other is neutral\n"
    output += "  Confidence: 0.60-0.70\n\n"

    output += "CONFLICT (No Position)\n"
    output += "  MACD and RSI disagree\n"
    output += "  Action: HOLD\n\n"

    output += "NEUTRAL (No Position)\n"
    output += "  Both indicators are neutral\n"
    output += "  Action: HOLD\n"

    return output


def explain_macd_params() -> str:
    """
    Explain the MACD parameters and why Fibonacci values are used.

    Provides detailed explanation of each MACD parameter and the
    reasoning behind the 13/34/8 Fibonacci configuration.

    Returns:
        Formatted explanation of MACD parameters

    Example:
        >>> explain_macd_params()
        'MACD Parameters
        Fast (13): Short-term EMA
        Slow (34): Long-term EMA
        Signal (8): Signal line smoothing'
    """
    output = f"{get_symbol('CHART')} MACD Parameters Explained\n"
    output += "=" * 50 + "\n\n"

    output += "Current: 13/34/8 (Fibonacci Sequence)\n"
    output += "-" * 50 + "\n\n"

    output += "Fast Period (13)\n"
    output += "  Short-term exponential moving average\n"
    output += "  Reacts quickly to price changes\n"
    output += "  Fibonacci: 13 is in the sequence (1,1,2,3,5,8,13,21,34...)\n\n"

    output += "Slow Period (34)\n"
    output += "  Long-term exponential moving average\n"
    output += "  Provides trend context\n"
    output += "  Fibonacci: 34 is in the sequence\n\n"

    output += "Signal Period (8)\n"
    output += "  Smoothing for the MACD line\n"
    output += "  Crossovers generate signals\n"
    output += "  Fibonacci: 8 is in the sequence\n\n"

    output += "Why Fibonacci?\n"
    output += "-" * 50 + "\n"
    output += "  Validated across 7 tech stocks (2024-2025)\n"
    output += "  Outperformed traditional 12/26/9\n"
    output += "  Better alignment with market cycles\n"

    return output


def explain_rsi_params() -> str:
    """
    Explain the RSI parameters and threshold meanings.

    Provides detailed explanation of RSI calculation and
    the significance of oversold/overbought thresholds.

    Returns:
        Formatted explanation of RSI parameters

    Example:
        >>> explain_rsi_params()
        'RSI Parameters
        Period (14): Lookback window
        Oversold (30): Buy signal threshold
        Overbought (70): Sell signal threshold'
    """
    output = "📉 RSI Parameters Explained\n"
    output += "=" * 50 + "\n\n"

    output += "Current: 14 period, 30/70 thresholds\n"
    output += "-" * 50 + "\n\n"

    output += "Period (14)\n"
    output += "  Number of bars for RSI calculation\n"
    output += "  Industry standard, well-tested\n"
    output += "  Balances sensitivity and noise\n\n"

    output += "Oversold Threshold (30)\n"
    output += "  RSI below 30 = oversold condition\n"
    output += "  Generates BUY signal\n"
    output += "  Indicates potential price reversal up\n\n"

    output += "Overbought Threshold (70)\n"
    output += "  RSI above 70 = overbought condition\n"
    output += "  Generates SELL signal\n"
    output += "  Indicates potential price reversal down\n\n"

    output += "RSI Ranges:\n"
    output += "-" * 50 + "\n"
    output += "  0-30:  Oversold → BUY signal\n"
    output += "  30-70: Neutral → HOLD\n"
    output += "  70-100: Overbought → SELL signal\n"

    return output


def get_voter_parameters() -> Dict[str, Any]:
    """
    Get voter parameters as structured data for agents.

    Provides voting configuration in a structured format suitable
    for programmatic consumption by other agents.

    Returns:
        Dictionary with all voter parameters

    Example:
        >>> get_voter_parameters()
        {'macd': {'fast': 13, 'slow': 34, 'signal': 8}, ...}
    """
    config = TradingConfig()
    macd = config.get_macd_config()
    rsi = config.get_rsi_config()

    return {
        "macd": {
            "fast": macd.fast,
            "slow": macd.slow,
            "signal": macd.signal,
        },
        "rsi": {
            "period": rsi.period,
            "oversold": rsi.oversold,
            "overbought": rsi.overbought,
        },
        "thresholds": {
            "macd_threshold": 0.1,
            "consensus_boost": 0.15,
            "weak_signal_boost": 0.10,
            "min_data_points": 42,
        },
        "performance": {
            "sharpe_ratio": 0.856,
            "total_return": 0.366,
            "win_rate": 0.514,
            "max_drawdown": -0.101,
            "validation_period": "2024-2025",
        },
    }


def compare_with_traditional() -> str:
    """
    Compare Fibonacci MACD (13/34/8) with traditional (12/26/9).

    Shows side-by-side comparison of parameter sets and their
    performance characteristics.

    Returns:
        Formatted comparison table

    Example:
        >>> compare_with_traditional()
        'MACD Parameter Comparison
        | Param    | Fibonacci | Traditional |
        | Fast     |    13     |     12      |'
    """
    output = f"{get_symbol('INFO')} MACD Parameter Comparison\n"
    output += "=" * 50 + "\n\n"

    output += f"{'Parameter':<15} {'Fibonacci':>12} {'Traditional':>12}\n"
    output += "-" * 50 + "\n"
    output += f"{'Fast Period':<15} {'13':>12} {'12':>12}\n"
    output += f"{'Slow Period':<15} {'34':>12} {'26':>12}\n"
    output += f"{'Signal Period':<15} {'8':>12} {'9':>12}\n"
    output += "-" * 50 + "\n\n"

    output += "Fibonacci Advantages:\n"
    output += "  Better trend detection in tech stocks\n"
    output += "  Fewer false signals in choppy markets\n"
    output += "  Validated 0.856 Sharpe (2024-2025)\n\n"

    output += "Traditional Use Cases:\n"
    output += "  Broader market indices\n"
    output += "  More responsive to short-term moves\n"
    output += "  Industry standard for backtesting\n"

    return output


def show_signal_interpretation(signal_type: str = "STRONG") -> str:
    """
    Show how to interpret a specific signal type.

    Provides guidance on position sizing, confidence levels,
    and risk management for each signal type.

    Args:
        signal_type: Signal to explain ('STRONG', 'WEAK', 'CONFLICT', 'NEUTRAL')

    Returns:
        Formatted explanation of the signal type

    Example:
        >>> show_signal_interpretation('STRONG')
        'STRONG Signal
        Position: Full (1.0x)
        Confidence: 0.75-0.85
        Action: Enter with standard risk'
    """
    signal_type = signal_type.upper()

    interpretations = {
        "STRONG": {
            "emoji": "💪",
            "position": "Full (1.0x)",
            "confidence": "0.75-0.85",
            "description": "Both MACD and RSI agree on direction",
            "action": "Enter with standard position size",
            "risk_note": "Use normal stop loss (per mode settings)",
        },
        "WEAK": {
            "emoji": "🤏",
            "position": "Half (0.5x)",
            "confidence": "0.60-0.70",
            "description": "One indicator signals, other is neutral",
            "action": "Enter with reduced position size",
            "risk_note": "Consider tighter stop or wait for confirmation",
        },
        "CONFLICT": {
            "emoji": "⚔️",
            "position": "None (0.0x)",
            "confidence": "0.20",
            "description": "MACD and RSI disagree on direction",
            "action": "Do not enter - signals conflict",
            "risk_note": "Wait for agreement before trading",
        },
        "NEUTRAL": {
            "emoji": "😐",
            "position": "None (0.0x)",
            "confidence": "0.20",
            "description": "Both indicators are neutral",
            "action": "Do not enter - no clear signal",
            "risk_note": "Market may be consolidating",
        },
    }

    if signal_type not in interpretations:
        return f"{get_symbol('ERROR')} Unknown signal type: {signal_type}. Valid: STRONG, WEAK, CONFLICT, NEUTRAL"

    info = interpretations[signal_type]

    output = f"{info['emoji']} {signal_type} Signal Interpretation\n"
    output += "=" * 50 + "\n"
    output += f"  Position Size: {info['position']}\n"
    output += f"  Confidence:    {info['confidence']}\n"
    output += "-" * 50 + "\n"
    output += f"  {info['description']}\n\n"
    output += f"  Action: {info['action']}\n"
    output += f"  Risk: {info['risk_note']}\n"

    return output


# ============================================================================
# FunctionTool Definitions
# ============================================================================

show_voter_config_tool = FunctionTool(
    show_voter_config,
    description=(
        "Display current VoterAgent configuration including MACD parameters, "
        "RSI settings, voting thresholds, and validated performance metrics."
    ),
)

explain_voting_logic_tool = FunctionTool(
    explain_voting_logic,
    description=(
        "Explain how the MACD+RSI voting strategy works, including signal types "
        "(STRONG, WEAK, CONFLICT, NEUTRAL) and position sizing rules."
    ),
)

explain_macd_params_tool = FunctionTool(
    explain_macd_params,
    description=(
        "Explain MACD parameters and why Fibonacci values (13/34/8) "
        "are used instead of traditional (12/26/9)."
    ),
)

explain_rsi_params_tool = FunctionTool(
    explain_rsi_params,
    description=(
        "Explain RSI parameters including period, oversold/overbought thresholds, "
        "and how they generate trading signals."
    ),
)

get_voter_parameters_tool = FunctionTool(
    get_voter_parameters,
    description=(
        "Get VoterAgent parameters as structured data for programmatic use "
        "by other agents. Returns dict with MACD, RSI, and threshold settings."
    ),
)

compare_with_traditional_tool = FunctionTool(
    compare_with_traditional,
    description=(
        "Compare Fibonacci MACD parameters (13/34/8) with traditional (12/26/9). "
        "Shows parameter differences and use case recommendations."
    ),
)

show_signal_interpretation_tool = FunctionTool(
    show_signal_interpretation,
    description=(
        "Show how to interpret a specific voter signal type (STRONG, WEAK, "
        "CONFLICT, NEUTRAL) with position sizing and risk guidance."
    ),
)


# ============================================================================
# Tool Collection for Registry
# ============================================================================

CLI_VOTER_TOOLS = [
    show_voter_config_tool,
    explain_voting_logic_tool,
    explain_macd_params_tool,
    explain_rsi_params_tool,
    get_voter_parameters_tool,
    compare_with_traditional_tool,
    show_signal_interpretation_tool,
]

__all__ = [
    # Functions
    "show_voter_config",
    "explain_voting_logic",
    "explain_macd_params",
    "explain_rsi_params",
    "get_voter_parameters",
    "compare_with_traditional",
    "show_signal_interpretation",
    # Tools
    "show_voter_config_tool",
    "explain_voting_logic_tool",
    "explain_macd_params_tool",
    "explain_rsi_params_tool",
    "get_voter_parameters_tool",
    "compare_with_traditional_tool",
    "show_signal_interpretation_tool",
    # Collection
    "CLI_VOTER_TOOLS",
]
