"""
Government data sources package.

This package contains tools for retrieving data from government sources:
- SEC Edgar (company filings)
- FRED (Federal Reserve Economic Data)
"""

# Try to import FRED tool (requires fredapi)
try:
    from .FRED_data_tool import FREDDataTool
except ImportError:
    FREDDataTool = None

# Try to import SEC Edgar tool (requires beautifulsoup4)
try:
    from .sec_edgar_tool import SECEdgarTool
except ImportError:
    SECEdgarTool = None

# Build __all__ based on available tools
__all__ = []
if FREDDataTool is not None:
    __all__.append("FREDDataTool")
if SECEdgarTool is not None:
    __all__.append("SECEdgarTool")
