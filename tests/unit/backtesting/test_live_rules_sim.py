"""Live-rules simulator (#574 baseline): timing, brackets, sizing and limits."""

import numpy as np
import pandas as pd
import pytest

from src.backtesting.live_rules_sim import (
    LiveRules,
    compute_signals,
    performance,
    sharpe_ci,
    simulate,
)

DAYS = pd.bdate_range("2024-01-01", periods=6)


def _bars(opens, highs=None, lows=None, closes=None):
    opens = list(opens)
    return pd.DataFrame(
        {
            "open": opens,
            "high": highs or [o * 1.01 for o in opens],
            "low": lows or [o * 0.99 for o in opens],
            "close": closes or opens,
        },
        index=DAYS[: len(opens)],
    )


def _signals(day_actions):
    """``day_actions``: {(day_index, symbol): action}; every other day/symbol HOLDs."""
    rows = []
    for i, day in enumerate(DAYS):
        for symbol in ("AAA", "BBB"):
            act = day_actions.get((i, symbol), "HOLD")
            rows.append((day, symbol, act, 1.0 if act != "HOLD" else 0.0))
    return pd.DataFrame(rows, columns=["date", "symbol", "action", "position_size"]).set_index(
        ["date", "symbol"]
    )


def _run(prices, actions, **rules):
    prices = {s: prices.get(s, _bars([100.0] * 6)) for s in ("AAA", "BBB")}
    return simulate(prices, _signals(actions), LiveRules(**rules))


def test_signal_uses_only_prior_bars_at_the_prior_raw_scale():
    seen = {}

    def spy_fn(symbol, window):
        seen[window.index[-1]] = window["Close"].iloc[-1]
        return {"action": "HOLD", "position_size": 0.0}

    closes = pd.Series([10.0, 11.0, 12.0, 13.0], index=DAYS[:4])
    raw = closes * 4  # e.g. a later 4-for-1 split: raw prices were 4x the adjusted ones
    compute_signals({"AAA": closes}, {"AAA": raw}, spy_fn, str(DAYS[1].date()), str(DAYS[3].date()))

    # decision on day i sees closes through day i-1, scaled to that day's raw level
    assert seen == {DAYS[0]: 40.0, DAYS[1]: 44.0, DAYS[2]: 48.0}


def test_buy_fills_at_open_and_sell_signal_exits_at_next_open():
    aaa = _bars([100.0, 101.0, 102.0, 103.0, 104.0, 105.0])
    equity, trades = _run({"AAA": aaa}, {(1, "AAA"): "BUY", (3, "AAA"): "SELL"})

    trade = trades.iloc[0]
    assert (trade.entry_date, trade.entry_price) == (DAYS[1], 101.0)
    assert (trade.exit_date, trade.exit_price, trade.reason) == (DAYS[3], 103.0, "signal")
    assert trade.qty == int(0.02 * 100_000 / 100.0)  # sized on the previous close


def test_stop_and_target_fill_at_their_levels():
    stop_day = _bars([100.0, 100.0, 100.0], lows=[99.0, 99.0, 94.0])
    _, trades = _run({"AAA": stop_day}, {(1, "AAA"): "BUY"})
    assert (trades.iloc[0].exit_price, trades.iloc[0].reason) == (95.0, "stop")

    target_day = _bars([100.0, 100.0, 100.0], highs=[101.0, 101.0, 109.0])
    _, trades = _run({"AAA": target_day}, {(1, "AAA"): "BUY"})
    assert (trades.iloc[0].exit_price, trades.iloc[0].reason) == (108.0, "target")


def test_gap_through_the_stop_fills_at_the_open_and_both_touched_is_a_stop():
    gap = _bars([100.0, 100.0, 90.0])
    _, trades = _run({"AAA": gap}, {(1, "AAA"): "BUY"})
    assert (trades.iloc[0].exit_price, trades.iloc[0].reason) == (90.0, "stop_gap")

    both = _bars([100.0, 100.0, 100.0], highs=[101.0, 101.0, 109.0], lows=[99.0, 99.0, 94.0])
    _, trades = _run({"AAA": both}, {(1, "AAA"): "BUY"})
    assert trades.iloc[0].reason == "stop"


def test_costs_apply_on_both_sides():
    aaa = _bars([100.0, 100.0, 100.0, 100.0])
    _, trades = _run({"AAA": aaa}, {(1, "AAA"): "BUY", (2, "AAA"): "SELL"}, cost_bps=10)

    trade = trades.iloc[0]
    assert trade.entry_price == pytest.approx(100.1)
    assert trade.exit_price == pytest.approx(99.9)


def test_position_limit_blocks_extra_entries():
    _, trades = _run({}, {(1, "AAA"): "BUY", (1, "BBB"): "BUY"}, max_positions=1)

    assert list(trades["symbol"]) == ["AAA"]  # strongest first, then by symbol


def test_a_position_stopped_out_today_is_not_bought_again_at_todays_open():
    stop_day = _bars([100.0, 100.0, 100.0, 100.0], lows=[99.0, 99.0, 94.0, 99.0])
    _, trades = _run({"AAA": stop_day}, {(1, "AAA"): "BUY", (2, "AAA"): "BUY", (3, "AAA"): "BUY"})

    # the stop hits on day 2, after the pre-market decision saw AAA still held
    assert list(trades["entry_date"]) == [DAYS[1], DAYS[3]]


def test_position_limit_counts_positions_that_exit_later_that_day():
    aaa = _bars([100.0, 100.0, 100.0, 100.0], lows=[99.0, 99.0, 94.0, 99.0])
    _, trades = _run({"AAA": aaa}, {(1, "AAA"): "BUY", (2, "BBB"): "BUY"}, max_positions=1)

    assert list(trades["symbol"]) == ["AAA"]


def test_whole_shares_are_counted_at_the_raw_price():
    aaa = _bars([100.0, 101.0, 102.0, 103.0])
    signals = _signals({(1, "AAA"): "BUY", (1, "BBB"): "BUY"})
    prices = {"AAA": aaa, "BBB": _bars([100.0] * 4)}
    # AAA traded at 30x its adjusted price then (a later 30-for-1 split): $2,000 < 1 share
    raw = {"AAA": aaa["close"] * 30, "BBB": prices["BBB"]["close"] * 4}
    _, trades = simulate(prices, signals, LiveRules(), raw_closes=raw)

    assert list(trades["symbol"]) == ["BBB"]
    assert trades.iloc[0].qty == 5 * 4  # 5 raw shares at $400 = 20 adjusted shares
    assert trades.attrs["blocked"]["under_one_share"] == 1


def test_exposure_cap_blocks_an_entry():
    _, trades = _run({}, {(1, "AAA"): "BUY"}, position_pct=0.5, max_exposure_pct=0.4)

    assert trades.empty


def test_performance_and_bootstrap_interval():
    rng = np.random.default_rng(1)
    returns = pd.Series(rng.normal(0.0005, 0.01, 2000))
    equity = (1 + returns).cumprod() * 100
    equity.index = pd.bdate_range("2010-01-01", periods=len(equity))

    stats = performance(equity)
    low, high = sharpe_ci(equity.pct_change(), reps=300)

    assert low < stats["sharpe"] < high
    assert stats["max_drawdown_pct"] < 0
