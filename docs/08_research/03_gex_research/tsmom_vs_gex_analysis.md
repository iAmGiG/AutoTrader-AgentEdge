# TSMOM vs GEX Comparative Analysis

## Executive Summary

**Key Findings:**

- Signal overlap days: 4,484
- Signal divergence days: 1,508
- Avg TSMOM Sharpe (Positive GEX): 1.282
- Avg TSMOM Sharpe (Negative GEX): nan
- Sharpe improvement in positive gamma: nan%

## Results by Symbol

| Symbol | Days | Overlap | Divergence | Sharpe (Pos GEX) | Sharpe (Neg GEX) | Win Rate (Pos) | Win Rate (Neg) |
|--------|------|---------|------------|------------------|------------------|----------------|----------------|
| SOXL | 1497 | 409 | 152 | 0.518 | 0.485 | 18.6% | 11.0% |
| TQQQ | 1497 | 344 | 134 | 1.225 | -0.590 | 16.4% | 10.5% |
| SQQQ | 1495 | 377 | 145 | 0.419 | 1.016 | 12.2% | 12.6% |
| SOXS | 1494 | 415 | 213 | 0.764 | -0.889 | 17.0% | 12.3% |
| UVXY | 1494 | 218 | 307 | 0.918 | 0.533 | 15.5% | 9.1% |
| QQQ | 1490 | 388 | 39 | 1.074 | -1.634 | 14.7% | 5.7% |
| IWM | 1478 | 438 | 65 | 0.705 | 0.185 | 15.4% | 8.1% |
| SPY | 1010 | 270 | 34 | 0.582 | -0.167 | 14.5% | 7.1% |
| FAS | 352 | 104 | 31 | 3.475 | 0.007 | 27.5% | 7.2% |
| TECL | 343 | 119 | 42 | 1.265 | 2.955 | 24.6% | 26.5% |
| FAZ | 341 | 81 | 48 | 1.088 | -4.028 | 18.9% | 11.3% |
| LABU | 341 | 95 | 19 | 3.084 | -4.966 | 23.6% | 3.1% |
| DUST | 337 | 111 | 3 | 0.576 | -2.972 | 20.4% | 0.0% |
| NUGT | 337 | 67 | 53 | 2.857 | -3.045 | 19.3% | 9.7% |
| LABD | 336 | 125 | 18 | 0.297 | -4.019 | 20.9% | 8.0% |
| TECS | 335 | 101 | 3 | 0.242 | -4.403 | 17.5% | 0.0% |
| GLD | 228 | 40 | 18 | 0.634 | -1.152 | 14.7% | 9.5% |
| TSLA | 228 | 59 | 2 | 2.338 | nan | 14.6% | 0.0% |
| DIA | 218 | 74 | 8 | 2.855 | -0.581 | 18.0% | 8.9% |
| IYR | 218 | 62 | 17 | 1.925 | 0.066 | 16.6% | 13.0% |
| AAPL | 213 | 63 | 2 | 2.028 | 3.240 | 16.0% | 4.2% |
| LQD | 212 | 62 | 2 | 0.608 | nan | 13.4% | 0.0% |
| MSFT | 211 | 78 | 2 | 1.687 | 2.851 | 21.8% | 3.2% |
| SLV | 207 | 16 | 38 | 0.544 | -1.694 | 6.7% | 13.7% |
| VXX | 207 | 30 | 23 | 0.168 | -1.987 | 10.4% | 5.0% |
| IEF | 206 | 64 | 4 | 1.412 | 2.573 | 18.4% | 6.5% |
| TLT | 203 | 67 | 1 | 1.550 | -4.255 | 18.8% | 0.0% |
| VTI | 203 | 58 | 9 | 1.602 | 4.302 | 18.6% | 20.0% |
| SPXS | 107 | 27 | 6 | -0.543 | 2.011 | 12.7% | 8.6% |
| UPRO | 106 | 32 | 13 | 0.764 | 4.389 | 23.0% | 25.8% |
| TZA | 104 | 15 | 23 | 2.674 | -3.603 | 12.7% | 16.7% |
| SPXL | 102 | 24 | 15 | 0.112 | 5.125 | 16.1% | 22.2% |
| SPXU | 101 | 28 | 2 | 0.349 | -3.370 | 12.3% | 3.7% |
| TNA | 98 | 23 | 17 | 3.784 | -0.691 | 24.0% | 19.1% |

## Interpretation

**TSMOM performs similarly or better during negative gamma regimes.**

This suggests:

1. Momentum captures large moves in volatile (negative gamma) periods
2. GEX may not add value as a directional filter
3. Consider GEX for position sizing rather than signal filtering
