# Technical Indicator Library

The `indicator_library` module provides common TA indicators used by the QuantitativeAgent.
All indicator output columns follow the pattern `INDICATOR_component`.

| Indicator | Columns Produced |
|-----------|-----------------|
| EMA(span) | `EMA_<span>` |
| SMA(window) | `SMA_<window>` |
| RSI(period) | `RSI_<period>` |
| ATR(period) | `ATR_<period>` |
| Supertrend | `ST` |
| Anchored VWAP | `AVWAP` |
| MACD | `MACD_line`, `MACD_signal`, `MACD_hist` |
| Bollinger Bands | `BB_upper`, `BB_middle`, `BB_lower` |
| ADX + DI± | `ADX`, `DI_pos`, `DI_neg` |
| Ichimoku Cloud | `Ichimoku_baseline`, `Ichimoku_span_a`, `Ichimoku_span_b` |
| Stochastic RSI | `StochRSI`, `StochRSI_K`, `StochRSI_D` |
| CCI | `CCI` |

These names are returned in the QuantitativeAgent's `latest_row` dictionary so downstream tools can rely on a consistent schema.

The `avwap` function accepts an optional `anchor_ts` parameter which can be an
ISO date or event token (e.g. `earnings`). When provided, the AVWAP calculation
starts from that timestamp.
