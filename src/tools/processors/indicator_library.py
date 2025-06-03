import pandas as pd
import numpy as np

__all__ = ["eam", "sma", "rsi", "atr", "supertrend", "avwap"]


# --- Trend ---
def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window).mean()


# --- momentum ---
def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=9)
    roll_up = gain.rolling(period).mean()
    roll_down = loss.rolling(period).mean()
    rs = roll_up / roll_down
    return (100 - (100/(1+rs)))


# --- Volatility ---
def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    tr = pd.concat([high - low, (high - close.shift()).abs(),
                   (low - close.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean()


# --- Composit trend/stop ---
def supertrend(high: pd.Series, low: pd.Series, close: pd.Series,
               period: int = 10, mult: float = 3.0) -> pd.Series:
    """
    Vectorised Supertrend implementation (no explicit Python loop).
    Returns a pd.Series aligned to `close.index`.
    """
    atr_vals = atr(high=high, low=low, close=close, period=period)
    hl2 = (high + low) / 2
    upper = hl2 + mult * atr_vals
    lower = hl2 - mult * atr_vals

    st = pd.Series(index=close.index, dtype=float)
    direction = pd.Series(True, index=close.index)  # when true = uptrend

    for i in range(len(close)):
        if i == 0:
            st.iat[i] = lower.iat[i]
            continue
        # In-trend "stickiness"
        if direction.iat[i-1]:
            st.iat[i] = max(lower.iat[i], st.iat[i-1])
        else:
            st.iat[i] = min(upper.iat[i], st.iat[i-1])

        # flip on close cross
        direction.iat[i] = close.iat[i] > st.iat[i]
    return st


# --- AVWAP ---
def avwap(close: pd.Series,
          volume: pd.Series,
          anchor_idx: int | str | pd.Timestamp = 0) -> pd.Series:
    """
    Anchored VWAP.  `anchor_idx` can be
      • int  - positional index (0 = first row in frame),
      • str  - e.g. "2025-05-20 09:30",
      • pd.Timestamp.
    """
    if isinstance(anchor_idx, (str, pd.Timestamp)):
        anchor_idx = close.index.get_loc(
            pd.Timestamp(anchor_idx), method="nearest")
    pv = (close * volume).cumsum()
    vol = volume.cumsum()
    if anchor_idx > 0:
        pv = pv - pv.iloc[anchor_idx - 1]
        vol = vol - vol.iloc[anchor_idx - 1]
    return pv/vol
