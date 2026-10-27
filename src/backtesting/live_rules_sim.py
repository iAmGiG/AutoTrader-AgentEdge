"""
Simulation of the live CLI trading rules, for the #574 paper-validation baseline.

The live path (RealVoterStrategy -> SimpleRiskManager -> AlpacaExecutionManager) is
reproduced as closely as daily bars allow:

- Signal: the live ``VoterAgent.evaluate_ranked_voting`` (computed by ``VotingSignal``) (MACD 13/34/8 histogram beyond
  +/-0.1, RSI 14 at 30/70) on a 90-calendar-day window, as RealVoterStrategy fetches.
- Timing: the signal for day *d* uses bars through *d - 1*, as a pre-market routine
  would; trades fill at day *d*'s open. The window is rescaled to the split level of
  day *d*, because the MACD threshold is in dollars and live bars are split-adjusted
  only up to the fetch (on a split day, they are already at the new level).
- Entries: a BUY with no position opens one at the open. Size is a share of the
  previous close's equity (the mode's risk_per_trade) in whole shares at the previous
  close, rounded at the raw price of the day as live orders are (so a slot smaller than
  one share is skipped). Blocked beyond 10 positions, 80% exposure or the cash held at
  the start of the day (SimpleRiskManager defaults). The decision is made before the
  open, so the position count, exposure and cash include positions that exit later
  that day, and a symbol held at the start of the day is not bought again until the
  next day.
- Exits: a SELL signal closes the position at the open. Otherwise the market bracket
  (stop -5%, target +8% from the fill, AlpacaExecutionManager defaults) is checked on
  the day's range. A gap through either level fills at the open, and a day that
  touches both counts as the stop (the conservative reading).
- Costs: ``cost_bps`` per side on every fill.

Prices are split-adjusted (ResearchBacktester); dividends are not included.
"""

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

SignalFn = Callable[[str, pd.DataFrame], dict]


@dataclass
class LiveRules:
    """Sizing, limits, brackets and costs of the live path."""

    position_pct: float = 0.02  # notional per position, share of equity (risk_per_trade)
    max_positions: int = 10  # SimpleRiskManager risk.max_positions default
    max_exposure_pct: float = 0.80  # SimpleRiskManager risk.max_exposure_pct default
    stop_pct: float = 0.05  # market-bracket stop below the fill
    target_pct: float = 0.08  # market-bracket target above the fill
    cost_bps: float = 0.0  # per side, every fill
    lookback_days: int = 90  # RealVoterStrategy lookback (calendar days)
    initial_capital: float = 100_000.0


def compute_signals(
    closes: Dict[str, pd.Series],
    raw_closes: Dict[str, pd.Series],
    signal_fn: SignalFn,
    start: str,
    end: str,
    lookback_days: int = 90,
) -> pd.DataFrame:
    """
    Signal for each symbol on each of its trading days in [start, end].

    The window holds the closes strictly before the day, within ``lookback_days``
    calendar days, rescaled to that day's split level (its raw / adjusted ratio, which
    depends only on the split calendar).

    Returns:
        DataFrame indexed by (date, symbol) with ``action`` and ``position_size``
    """
    rows = []
    for symbol, series in closes.items():
        dates = series.index
        ratio = (raw_closes[symbol].reindex(dates) / series).ffill().fillna(1.0)
        days = dates[(dates >= pd.Timestamp(start)) & (dates <= pd.Timestamp(end))]
        for day in days:
            end_i = dates.searchsorted(day)  # first index at or after `day`
            if end_i == 0:
                continue
            start_i = dates.searchsorted(day - pd.Timedelta(days=lookback_days))
            window = series.iloc[start_i:end_i]
            scale = ratio.iloc[end_i]
            result = signal_fn(symbol, pd.DataFrame({"Close": window * scale}))
            rows.append(
                (day, symbol, result.get("action", "HOLD"), result.get("position_size", 0.0))
            )
    signals = pd.DataFrame(rows, columns=["date", "symbol", "action", "position_size"])
    return signals.set_index(["date", "symbol"]).sort_index()


def _bracket_exit(bar, stop: float, target: float, gap: bool) -> Tuple[Optional[float], str]:
    """Exit price and reason if the bracket triggers on this bar (gap: check the open)."""
    if gap and bar.open <= stop:
        return bar.open, "stop_gap"
    if gap and bar.open >= target:
        return bar.open, "target_gap"
    hit_stop, hit_target = bar.low <= stop, bar.high >= target
    if hit_stop:
        return stop, "stop"  # also when both are touched: the conservative reading
    if hit_target:
        return target, "target"
    return None, ""


def simulate(  # noqa: C901
    prices: Dict[str, pd.DataFrame],
    signals: pd.DataFrame,
    rules: LiveRules,
    raw_closes: Optional[Dict[str, pd.Series]] = None,
) -> Tuple[pd.Series, pd.DataFrame]:
    """
    Run the live rules over the signal days.

    Args:
        prices: Per symbol, split-adjusted daily bars (open/high/low/close), date index
        signals: From compute_signals()
        rules: Sizing, limits, brackets and costs
        raw_closes: Per symbol, unadjusted closes; whole shares are counted at this
            price level. Without them, at the adjusted level.

    Returns:
        (equity at each close, trades with entry/exit dates, prices, reason and return).
        ``trades.attrs["blocked"]`` counts BUY signals not taken, by reason.
    """
    cost = rules.cost_bps / 1e4
    action = signals["action"].to_dict()
    size = signals["position_size"].to_dict()
    calendar = sorted(signals.index.get_level_values("date").unique())
    # Prior closes from before the first signal day (the warm-up), for first-day sizing
    last_close: Dict[str, float] = {}
    for symbol, frame in prices.items():
        before = frame["close"][frame.index < calendar[0]] if calendar else frame["close"][:0]
        if len(before):
            last_close[symbol] = float(before.iloc[-1])
    cash = rules.initial_capital
    equity_prev = cash
    positions: Dict[str, dict] = {}
    trades: List[dict] = []
    equity = {}
    blocked = {
        "in_position": 0,
        "max_positions": 0,
        "no_prior_close": 0,
        "under_one_share": 0,
        "exposure": 0,
        "cash": 0,
    }
    # raw shares per adjusted share on each day (the later splits' combined factor)
    share_scale = {
        s: (raw_closes[s].reindex(prices[s].index) / prices[s]["close"])
        .ffill()
        .fillna(1.0)
        .to_dict()
        for s in (raw_closes or {})
        if s in prices
    }

    def bar_on(symbol, day):
        frame = prices[symbol]
        return frame.loc[day] if day in frame.index else None

    def close_position(symbol, day, price, reason):
        nonlocal cash
        pos = positions.pop(symbol)
        fill = price * (1 - cost)
        cash += pos["qty"] * fill
        trades.append(
            {
                "symbol": symbol,
                "entry_date": pos["entry_date"],
                "entry_price": pos["entry_price"],
                "exit_date": day,
                "exit_price": fill,
                "reason": reason,
                "qty": pos["qty"],
                "return": fill / pos["entry_price"] - 1,
            }
        )

    for day in calendar:
        bars = {sym: bar_on(sym, day) for sym in prices}
        # Book as the pre-market decision sees it: exits at or after the open come later
        book = {s: p["qty"] * last_close.get(s, p["entry_price"]) for s, p in positions.items()}
        buying_power = cash

        # Exits at the open on SELL signals, then bracket triggers through the day
        for symbol in list(positions):
            bar = bars[symbol]
            if bar is None:
                continue
            if action.get((day, symbol)) == "SELL":
                close_position(symbol, day, bar.open, "signal")
                continue
            pos = positions[symbol]
            price, reason = _bracket_exit(bar, pos["stop"], pos["target"], gap=True)
            if price is not None:
                close_position(symbol, day, price, reason)

        # Entries at the open: strong signals first, then by symbol
        held_value = sum(book.values())
        n_held = len(book)
        buys = [s for s in prices if bars[s] is not None and action.get((day, s)) == "BUY"]
        candidates = [s for s in buys if s not in book]
        blocked["in_position"] += len(buys) - len(candidates)
        candidates.sort(key=lambda s: (-size.get((day, s), 0.0), s))
        for i, symbol in enumerate(candidates):
            if n_held >= rules.max_positions:
                blocked["max_positions"] += len(candidates) - i
                break
            prev_close = last_close.get(symbol)
            if not prev_close:
                blocked["no_prior_close"] += 1
                continue
            scale = share_scale.get(symbol, {}).get(day, 1.0)  # the day's split level
            qty = int(rules.position_pct * equity_prev / (prev_close * scale)) * scale
            if qty <= 0:
                blocked["under_one_share"] += 1
                continue
            if (held_value + qty * prev_close) / equity_prev > rules.max_exposure_pct:
                blocked["exposure"] += 1
                continue
            bar = bars[symbol]
            fill = bar.open * (1 + cost)
            if qty * fill > buying_power:
                blocked["cash"] += 1
                continue
            buying_power -= qty * fill
            cash -= qty * fill
            held_value += qty * prev_close
            n_held += 1
            positions[symbol] = {
                "qty": qty,
                "entry_price": fill,
                "entry_date": day,
                "stop": bar.open * (1 - rules.stop_pct),
                "target": bar.open * (1 + rules.target_pct),
            }
            price, reason = _bracket_exit(
                bar, positions[symbol]["stop"], positions[symbol]["target"], gap=False
            )
            if price is not None:
                close_position(symbol, day, price, reason)

        for symbol, bar in bars.items():
            if bar is not None:
                last_close[symbol] = float(bar.close)
        equity_prev = cash + sum(p["qty"] * last_close[s] for s, p in positions.items())
        equity[day] = equity_prev

    for symbol, pos in positions.items():  # still open at the end: marked, not closed
        trades.append(
            {
                "symbol": symbol,
                "entry_date": pos["entry_date"],
                "entry_price": pos["entry_price"],
                "exit_date": None,
                "exit_price": last_close[symbol],
                "reason": "open",
                "qty": pos["qty"],
                "return": last_close[symbol] / pos["entry_price"] - 1,
            }
        )
    trades_frame = pd.DataFrame(trades)
    trades_frame.attrs["blocked"] = blocked
    return pd.Series(equity, name="equity"), trades_frame


def performance(equity: pd.Series) -> dict:
    """Annualized Sharpe (rf 0), CAGR, volatility and max drawdown of an equity curve."""
    returns = equity.pct_change().dropna()
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    drawdown = equity / equity.cummax() - 1
    std = returns.std()
    return {
        "sharpe": float(np.sqrt(252) * returns.mean() / std) if std > 0 else 0.0,
        "cagr_pct": (
            float(((equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1) * 100)
            if years > 0
            else 0.0
        ),
        "vol_pct": float(std * np.sqrt(252) * 100),
        "max_drawdown_pct": float(drawdown.min() * 100),
        "n_days": int(len(returns)),
    }


def sharpe_ci(
    returns: pd.Series, block: int = 20, reps: int = 2000, seed: int = 0
) -> Tuple[float, float]:
    """95% circular block-bootstrap interval for the annualized Sharpe ratio."""
    r = returns.dropna().to_numpy()
    n = len(r)
    if n < 2 * block:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, n, size=(reps, int(np.ceil(n / block))))
    offsets = np.arange(block)
    samples = r[((starts[:, :, None] + offsets) % n).reshape(reps, -1)[:, :n]]
    sharpes = np.sqrt(252) * samples.mean(axis=1) / samples.std(axis=1, ddof=1)
    low, high = np.percentile(sharpes, [2.5, 97.5])
    return float(low), float(high)
