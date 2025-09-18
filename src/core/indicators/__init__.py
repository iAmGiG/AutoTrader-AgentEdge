"""
Technical Indicators for RH2MAS Trading System

This module contains technical analysis indicators used as voting members
in the multi-indicator ensemble trading system.

Current Indicators:
- MACD: Existing implementation via TechAgent
- RSI: Relative Strength Index (Issue #277) - PENDING
- Bollinger Bands: Volatility bands (Issue #278) - PENDING  
- Volume: Volume-based confirmation (Issue #279) - PENDING

Each indicator provides:
- Signal generation (-100 to +100 strength)
- Confidence scoring (0-1 scale)
- Integration with unified cache system

Target: Combine 4 technical + 5 sentiment (V0-V4) = 9 voting members
Goal: 90% accuracy through ensemble democracy
"""

# Current indicators
from .base_indicator import BaseIndicator, IndicatorSignal
from .simple_rsi import SimpleRSI

# Future indicators (pending)
# from .bollinger_bands import BollingerBandsIndicator  # Issue #278
# from .volume_indicator import VolumeIndicator  # Issue #279

__all__ = [
    'BaseIndicator',
    'IndicatorSignal', 
    'SimpleRSI'
]

__version__ = "0.1.0"
__issue_tracking__ = {
    "277": "PENDING - RSI Implementation",
    "278": "PENDING - Bollinger Bands", 
    "279": "PENDING - Volume Confirmation",
}