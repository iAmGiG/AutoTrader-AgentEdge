"""
Signal Generators for Backtesting

Collection of trading signal generators compatible with BacktestEngine.
"""

from .delta_neutral_signal import DeltaNeutralSignal
from .dispersion_signal import DispersionSignal
from .macd_rsi_signal import MACDRSISignal
from .pairs_trading_signal import PairsTradingSignal
from .tsmom_signal import TSMOMSignalGenerator

__all__ = [
    "TSMOMSignalGenerator",
    "PairsTradingSignal",
    "DeltaNeutralSignal",
    "DispersionSignal",
    "MACDRSISignal",
]
