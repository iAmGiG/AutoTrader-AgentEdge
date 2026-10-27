"""Live-rules simulator exit modes (#539): trailing-stop tiers against the fixed bracket."""

import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import src.backtesting.live_rules_sim as sim
from src.backtesting.live_rules_sim import LiveRules, LiveTrailingStop, simulate

DAYS = pd.bdate_range("2024-01-01", periods=40)
FLAT = (100.0, 100.0, 100.0, 100.0)  # (open, high, low, close) of the warm-up day
REPO = Path(__file__).resolve().parents[3]


def _signals(n_days, buys=(1,), sells=()):
    rows = []
    for i in range(n_days):
        act = "BUY" if i in buys else "SELL" if i in sells else "HOLD"
        rows.append((DAYS[i], "AAA", act, 1.0 if act != "HOLD" else 0.0))
    return pd.DataFrame(rows, columns=["date", "symbol", "action", "position_size"]).set_index(
        ["date", "symbol"]
    )


def _run(rows, mode, buys=(1,), sells=(), **rules):
    """Trades of one symbol on (open, high, low, close) rows; day 0 is the warm-up."""
    frame = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=DAYS[: len(rows)])
    _, trades = simulate(
        {"AAA": frame}, _signals(len(rows), buys, sells), LiveRules(exit_mode=mode, **rules)
    )
    return trades


# ---------------------------------------------------------------------------
# The live tiers, entered at 100 with the 5% stop at 95
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "close, stop",
    [
        (102.0, 100.0),  # 2% is the first tier: breakeven
        (103.99, 100.0),
        (104.0, 101.0),  # 4%: lock 25% of the gain
        (105.0, 101.25),
        (105.99, 101.5),
        (106.0, 103.0),  # 6%: lock 50%
        (108.0, 104.0),
        (110.0, 107.5),  # 10%: lock 75%
        (112.0, 109.0),
        (120.0, 115.0),
    ],
)
def test_each_tier_sets_the_stop_the_next_session_trades_through(close, stop):
    rows = [
        FLAT,
        (100.0, close, 99.0, close),  # filled at 100 at the open, closes at `close`
        (close, close, stop - 0.5, close),  # the next session trades through the raised stop
    ]
    trade = _run(rows, "trailing").iloc[0]

    assert (trade.exit_date, trade.reason) == (DAYS[2], "trail")
    assert trade.exit_price == pytest.approx(stop)


def test_under_two_percent_leaves_the_initial_stop():
    rows = [
        FLAT,
        (100.0, 102.0, 99.0, 101.9),  # +1.9%: no raise
        (101.9, 102.0, 95.5, 98.0),  # a raise to breakeven would have stopped this out
        (98.0, 98.0, 94.0, 94.5),
    ]
    trade = _run(rows, "trailing").iloc[0]

    assert (trade.exit_date, trade.reason) == (DAYS[3], "stop")  # never raised
    assert trade.exit_price == pytest.approx(95.0)


def test_a_lower_tier_never_moves_the_stop_down():
    rows = [
        FLAT,
        (100.0, 108.0, 99.0, 108.0),  # +8%: the stop goes to 104
        (107.0, 108.0, 104.5, 105.0),  # +5% is the 25% tier, 101.25: the stop stays at 104
        (105.0, 105.0, 103.0, 103.5),
    ]
    trade = _run(rows, "trailing").iloc[0]

    assert (trade.exit_date, trade.reason) == (DAYS[3], "trail")
    assert trade.exit_price == pytest.approx(104.0)


def test_a_raise_applies_from_the_next_session_not_the_day_it_is_made():
    rows = [
        FLAT,
        (100.0, 108.0, 96.0, 108.0),  # closes +8%: stop to 104, above this day's low of 96
        (108.0, 109.0, 105.0, 107.0),
    ]
    assert list(_run(rows, "trailing")["reason"]) == ["open"]  # not stopped on its own day

    rows.append((107.0, 107.0, 103.0, 104.0))  # the next session after that trades through 104
    trade = _run(rows, "trailing").iloc[0]
    assert (trade.exit_date, trade.reason) == (DAYS[3], "trail")
    assert trade.exit_price == pytest.approx(104.0)


def test_a_gap_down_through_a_raised_stop_fills_at_the_open():
    rows = [FLAT, (100.0, 108.0, 99.0, 108.0), (101.0, 102.0, 100.0, 101.5)]
    trade = _run(rows, "trailing").iloc[0]

    assert (trade.exit_date, trade.reason) == (DAYS[2], "trail_gap")
    assert trade.exit_price == pytest.approx(101.0)  # the open, below the 104 stop


def test_a_gap_down_through_the_initial_stop_fills_at_the_open():
    rows = [FLAT, (100.0, 101.0, 99.0, 100.5), (90.0, 91.0, 89.0, 90.0)]
    trade = _run(rows, "trailing").iloc[0]

    assert (trade.exit_date, trade.reason) == (DAYS[2], "stop_gap")
    assert trade.exit_price == pytest.approx(90.0)


# ---------------------------------------------------------------------------
# The floor and the one-cent rule of the live reconciler
# ---------------------------------------------------------------------------


def test_the_stop_stays_one_percent_below_the_price(monkeypatch):
    from config_defaults.trading_config import TrailingStopConfig

    from src.trading.state.state_reconciler import MIN_STOP_GAP

    # The stock tiers never get closer than 1% (a 2% gain locks at most the entry), so the
    # floor only shows with the manager's simple rule, which trails 0.5% below the price
    simple = TrailingStopConfig(progressive_enabled=False)
    assert LiveTrailingStop(simple).raised_stop("AAA", 100.0, 95.0, 103.0) == pytest.approx(
        round(103.0 * (1 - MIN_STOP_GAP), 2)
    )

    monkeypatch.setattr(sim, "LiveTrailingStop", lambda: LiveTrailingStop(simple))
    rows = [FLAT, (100.0, 103.0, 99.0, 103.0), (103.0, 103.0, 101.0, 102.0)]
    trade = _run(rows, "trailing").iloc[0]

    assert trade.exit_price == pytest.approx(101.97)  # 1% below the 103 close, not 102.49
    assert trade.reason == "trail"


def test_the_stock_tiers_never_reach_the_one_percent_floor():
    live = LiveTrailingStop()

    for price in np.arange(101.0, 400.0, 0.5):
        level = live.raised_stop("AAA", 100.0, 95.0, float(price))
        assert level is None or level <= round(float(price) * 0.99, 2)


def test_a_raise_must_beat_the_stop_by_more_than_a_cent():
    live = LiveTrailingStop()

    assert live.raised_stop("AAA", 100.0, 99.995, 102.0) is None  # breakeven is half a cent up
    assert live.raised_stop("AAA", 100.0, 99.98, 102.0) == 100.0


def test_the_cent_is_rounded_at_the_raw_price_not_the_split_adjusted_one():
    live = LiveTrailingStop()
    # $10.00 entry and $10.45 close, on a stock that later split 40-for-1 (adjusted /40):
    # 25% of the gain is $10.1125, which the broker rounds to the cent: $10.11
    level = live.raised_stop("AAA", 10.0 / 40, 9.5 / 40, 10.45 / 40, scale=40.0)
    assert level == pytest.approx(10.11 / 40)
    # at the adjusted level a cent is 4% of the price and the same raise would round to 0.25
    assert live.raised_stop("AAA", 10.0 / 40, 9.5 / 40, 10.45 / 40) == 0.25


def test_numpy_prices_round_the_cent_as_the_live_python_floats_do():
    live = LiveTrailingStop()
    # 50% of the 16.78 to 18.33 gain is the double just under 17.555: Python rounds it down to
    # 17.55, numpy up to 17.56. The broker's prices are Python floats, but bars hold numpy ones
    for entry, price in ((16.78, 18.33), (np.float64(16.78), np.float64(18.33))):
        level = live.raised_stop("AAA", entry, 16.78, price)
        assert level == 17.55
        assert type(level) is float
    rows = [FLAT, (16.78, 18.4, 16.7, 18.33), (18.33, 18.4, 17.5, 18.0)]
    frame = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=DAYS[:3])
    frame.iloc[0] = (16.0, 16.0, 16.0, 16.0)
    _, trades = simulate({"AAA": frame}, _signals(3), LiveRules(exit_mode="trailing"))
    assert trades.iloc[0].exit_price == 17.55  # the same level through the simulator's bars


@pytest.mark.parametrize(
    "price, stop, expected",
    [
        (95.0, 95.0, None),  # under water
        (101.9, 95.0, None),  # under 2%
        (102.0, 95.0, 100.0),
        (104.0, 95.0, 101.0),
        (106.0, 95.0, 103.0),
        (110.0, 95.0, 107.5),
        (110.0, 107.5, None),  # already there
        (110.0, 109.0, None),  # never down
        (105.0, 101.25, None),  # the 25% tier lands on the stop it has
    ],
)
def test_live_tiers_pinned(price, stop, expected):
    # Pins the live manager's outputs: if the tiers change, the simulated exits change
    assert LiveTrailingStop().raised_stop("AAA", 100.0, stop, price) == expected


def test_live_tiers_are_the_stock_ones_and_the_extras_are_off():
    from config_defaults.trading_config import TradingConfig, TrailingStopConfig

    live = LiveTrailingStop()
    config = live.manager.trailing_config

    assert TradingConfig().get_trailing_stop_config() == TrailingStopConfig()  # no overrides
    assert config == TrailingStopConfig()
    assert (config.climb_rate, config.never_move_stop_down) == ("medium", True)
    assert (config.progressive_breakeven_pct, config.progressive_lock_25_pct) == (0.02, 0.04)
    assert config.progressive_trail_50_pct == 0.06
    assert live.manager.atr_fetcher is None and not config.volatility_aware


def test_routines_build_the_manager_as_the_simulation_does():
    cycle = (REPO / "src/trading/scheduling/trading_cycle.py").read_text(encoding="utf-8")
    calls = re.findall(r"TrailingStopManager\(\n(.*?)\n\s*\)", cycle, re.S)

    # no atr_fetcher, no trailing_config override: the live manager is the plain one
    assert len(calls) == 1 and cycle.count("TrailingStopManager(") == 1
    arguments = re.sub(r"#[^\n]*", "", calls[0])
    assert "".join(arguments.split()) == "order_manager=None,config=self.config,"


def test_voter_tightening_and_support_levels_are_never_set_on_the_live_path():
    hooks = (".update_voter_signal(", ".set_support_resistance(")
    for folder in ("scheduling", "state", "gtt", "orders", "broker", "positions"):
        for path in (REPO / "src/trading" / folder).rglob("*.py"):
            if path.name == "trailing_stop_manager.py":
                continue
            text = path.read_text(encoding="utf-8")
            for hook in hooks:
                assert hook not in text, f"{path.relative_to(REPO)} calls {hook}"


# ---------------------------------------------------------------------------
# Targets, modes and the unchanged bracket
# ---------------------------------------------------------------------------


def test_trailing_has_no_target_and_trailing_target_keeps_it():
    rows = [FLAT, (100.0, 109.0, 99.0, 100.5), (100.5, 101.0, 99.8, 100.5)]

    for mode in ("bracket", "trailing_target"):
        trade = _run(rows, mode).iloc[0]
        assert (trade.reason, trade.exit_price) == ("target", pytest.approx(108.0))
    assert list(_run(rows, "trailing")["reason"]) == ["open"]  # rode through +9%


def test_trailing_target_raises_the_stop_and_keeps_the_target():
    base = [FLAT, (100.0, 104.0, 99.0, 104.0)]  # +4%: stop to 101, target still 108
    both = _run(base + [(104.0, 108.5, 100.5, 105.0)], "trailing_target").iloc[0]
    target = _run(base + [(104.0, 108.5, 102.0, 108.0)], "trailing_target").iloc[0]
    gap = _run(base + [(109.0, 110.0, 108.0, 109.0)], "trailing_target").iloc[0]

    assert (both.reason, both.exit_price) == ("trail", pytest.approx(101.0))  # both: the stop
    assert (target.reason, target.exit_price) == ("target", pytest.approx(108.0))
    assert (gap.reason, gap.exit_price) == ("target_gap", pytest.approx(109.0))


def test_bracket_mode_keeps_the_initial_stop_whatever_the_gains():
    rows = [FLAT, (100.0, 104.0, 99.0, 104.0), (104.0, 104.0, 99.5, 100.0)]

    assert list(_run(rows, "bracket")["reason"]) == ["open"]  # the stop is still 95
    trade = _run(rows, "trailing").iloc[0]
    assert (trade.reason, trade.exit_price) == ("trail", pytest.approx(101.0))


def test_trailing_modes_cost_and_signal_exits_work_as_in_the_bracket():
    rows = [FLAT] + [(100.0, 101.0, 99.5, 100.0)] * 4
    for mode in ("bracket", "trailing", "trailing_target"):
        trade = _run(rows, mode, sells=(3,), cost_bps=10).iloc[0]
        assert (trade.exit_date, trade.reason) == (DAYS[3], "signal")
        assert trade.entry_price == pytest.approx(100.1)
        assert trade.exit_price == pytest.approx(99.9)


def test_signal_exit_can_be_switched_off():
    rows = [FLAT] + [(100.0, 101.0, 99.5, 100.0)] * 4

    assert _run(rows, "trailing", sells=(3,)).iloc[0].reason == "signal"
    assert list(_run(rows, "trailing", sells=(3,), signal_exit=False)["reason"]) == ["open"]


def test_an_unknown_exit_mode_is_refused():
    with pytest.raises(ValueError, match="exit_mode"):
        _run([FLAT, FLAT], "chandelier")


def test_the_default_mode_is_the_bracket():
    rules = LiveRules()

    assert (rules.exit_mode, rules.signal_exit) == ("bracket", True)
    assert (rules.stop_pct, rules.target_pct) == (0.05, 0.08)


def _random_market(seed=7, n_sym=4, n_days=320):
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2022-01-03", periods=n_days)
    prices, raw, rows = {}, {}, []
    for k in range(n_sym):
        close = 40 * np.exp(np.cumsum(rng.normal(0.0005, 0.025, n_days)))
        open_ = np.r_[close[0], close[:-1]] * (1 + rng.normal(0, 0.012, n_days))
        high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.006, n_days)))
        low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.006, n_days)))
        frame = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close}, index=days)
        prices[f"S{k}"] = frame
        raw[f"S{k}"] = frame["close"] * (2.0 if k % 2 else 1.0)  # S1, S3 traded at 2x then
    for d in days:
        for sym in prices:
            act = rng.choice(["BUY", "SELL", "HOLD"], p=[0.25, 0.08, 0.67])
            rows.append((d, sym, act, float(rng.uniform(0.2, 1.0)) if act != "HOLD" else 0.0))
    cols = ["date", "symbol", "action", "position_size"]
    return prices, raw, pd.DataFrame(rows, columns=cols).set_index(["date", "symbol"])


@pytest.mark.parametrize(
    "cost_bps, final, lowest, exits, returns",
    [
        (0.0, 100622.38096074964, 99232.00814685966, 6753.899569411258, 0.36107046110861774),
        (5.0, 100317.14533836427, 99063.7518975737, 6750.522619626552, 0.20978503336139886),
    ],
)
def test_bracket_mode_reproduces_the_numbers_of_the_pre_trailing_simulator(
    cost_bps, final, lowest, exits, returns
):
    # Golden values from the simulator as of the #574 baseline (before the exit modes)
    prices, raw, signals = _random_market()
    equity, trades = simulate(prices, signals, LiveRules(cost_bps=cost_bps), raw_closes=raw)
    closed = trades[trades["reason"] != "open"]

    assert equity.iloc[-1] == pytest.approx(final, rel=1e-12)
    assert equity.min() == pytest.approx(lowest, rel=1e-12)
    assert (len(trades), len(closed)) == (153, 151)
    assert closed["exit_price"].sum() == pytest.approx(exits, rel=1e-12)
    assert closed["return"].sum() == pytest.approx(returns, rel=1e-12)
    assert closed["reason"].value_counts().to_dict() == {
        "stop": 51,
        "signal": 48,
        "target": 37,
        "stop_gap": 12,
        "target_gap": 3,
    }


# ---------------------------------------------------------------------------
# A reference model, written from the rules, against the simulator on random paths
# ---------------------------------------------------------------------------


def _reference_exit(bars, mode):  # noqa: C901
    """Exit (day index, price, reason) of a position bought at day 1's open, or None."""
    entry = bars[1][0]
    stop = entry * (1 - 0.05)
    target = entry * (1 + 0.08) if mode != "trailing" else float("inf")
    raised = False
    for i in range(1, len(bars)):
        o, h, lo, c = bars[i]
        hit = None
        if i > 1 and o <= stop:
            hit = (o, "stop_gap")
        elif i > 1 and o >= target:
            hit = (o, "target_gap")
        elif lo <= stop:
            hit = (stop, "stop")
        elif h >= target:
            hit = (target, "target")
        if hit:
            price, reason = hit
            if raised and reason.startswith("stop"):
                reason = reason.replace("stop", "trail")
            return i, price, reason
        if mode == "bracket":
            continue
        profit = (c - entry) / entry
        if profit < 0.02:
            continue
        gain = c - entry
        if profit < 0.04:
            level = entry
        elif profit < 0.06:
            level = entry + gain * 0.25
        elif profit < 0.10:
            level = entry + gain * 0.50
        else:
            level = entry + gain * 0.75
        level = round(level, 2)
        if level <= stop:  # never down
            continue
        level = round(min(level, c * (1 - 0.01)), 2)
        if level > stop + 0.01:
            stop, raised = level, True
    return None


@pytest.mark.parametrize("mode", ["bracket", "trailing", "trailing_target"])
def test_simulator_matches_a_reference_model_on_random_paths(mode):
    checked = exits = 0
    for seed in range(60):
        rng = np.random.default_rng(seed)
        n = 25
        close = 100 * np.exp(np.cumsum(rng.normal(0.002, 0.02, n)))
        open_ = np.r_[100.0, close[:-1]] * (1 + rng.normal(0, 0.01, n))
        high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.008, n)))
        low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.008, n)))
        bars = list(zip(open_.round(2), high.round(2), low.round(2), close.round(2)))
        bars = [
            (float(o), float(max(h, o, c)), float(min(lo, o, c)), float(c)) for o, h, lo, c in bars
        ]
        trades = _run(bars, mode)

        expected = _reference_exit(bars, mode)
        trade = trades.iloc[0]
        checked += 1
        if expected is None:
            assert trade.reason == "open"
            continue
        exits += 1
        day, price, reason = expected
        assert (trade.exit_date, trade.reason) == (DAYS[day], reason), f"seed {seed}"
        assert trade.exit_price == pytest.approx(price), f"seed {seed}"
    assert checked == 60 and exits > 20  # the paths do exercise exits
