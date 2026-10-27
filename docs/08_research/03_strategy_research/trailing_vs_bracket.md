# Trailing-Stop Exits against the Fixed Bracket

**Issue**: #539
**Status**: Complete. No detectable difference between the live trailing exits and the fixed bracket. The morning raise, which is not measured directly, probably lowers the trailing modes by about 0.1 Sharpe.
**Date**: 2026-10-27
**Results**: [results/trailing_vs_bracket.json](results/trailing_vs_bracket.json) and [results/trailing_vs_bracket.md](results/trailing_vs_bracket.md) (every table: both sizings, 0/5/10 bps, both signal-exit variants)
**Code**: `src/backtesting/live_rules_sim.py`, `scripts/research/trailing_vs_bracket.py`

## Question

The [live-rules baseline](live_rules_baseline.md) (#574 stage A) used a fixed -5% stop and +8% target. The live positions do not: their take-profit legs lapsed at Alpaca's 90-day GTC limit, and the routines raise their stops with the trailing tiers. Does exiting by trailing stop help, hurt, or make no detectable difference, given the same entry signal?

## Summary

- **No detectable difference.** At 5 bps a side, moderate sizing, with SELL-signal exits off (the variant that matches live exits), the full-period Sharpe is 0.833 for the bracket, 0.808 for trailing and 0.791 for trailing_target. Every paired 95% interval includes zero. Read that as "not detected", not "no difference": the intervals run about ±0.2 Sharpe.
- **The point estimates lean slightly negative for trailing.** The evening-raise-only differences are -0.024 and -0.042 (no-signal-exit variant) and -0.043 and +0.004 (SELL-exit variant).
- **The omitted morning raise runs against trailing.** With the day's open as the 09:20 price, Sharpe falls from 0.808 to 0.720 (trailing) and from 0.791 to 0.681 (trailing_target). The Sharpe loss is 0.09 to 0.12 in 52 of 54 comparisons. The headline tables therefore flatter the trailing modes.
- **Neither mode has alpha over holding the same symbols.** Alpha is +0.34% a year (t = +0.55) for trailing and +0.20% (t = +0.38) for trailing_target, against +0.12% (t = +0.22) for the bracket. The entry signal has no out-of-sample edge (#574), so this compares exits conditional on that signal. None of the 54 paired tests survives correction (smallest raw p 0.058; none is rejected by Holm or BH).

## Method

Same signals, sizing, position limits, fills at the open and costs as the baseline. Only the exit rule changes. Bracket mode reproduces the committed baseline bit for bit.

| Mode | Protective orders | Stands for |
| ---- | ----------------- | ---------- |
| bracket | -5% stop and +8% target from the fill, fixed | the #574 baseline |
| trailing | -5% stop raised by the live tiers, no target | legacy positions (take-profit leg lapsed) |
| trailing_target | the same tiers plus the +8% target | new CLI entries (bracket order with an 8% leg until day 90) |

**Live rules, from the code at 7c3ed7a:**

- **Tiers:** `TrailingStopManager.calculate_new_stop` (`src/trading/orders/trailing_stop_manager.py:245`), climb rate medium. Profit under 2%: no change. 2-4%: breakeven. 4-6%: lock 25% of the gain. 6-10%: lock 50%. 10% and up: lock 75% (`entry + lock x (price - entry)`). The stop never moves down.
- **Floor and threshold:** the reconciler (`src/trading/state/state_reconciler.py`, `_trailing_level`, `MIN_STOP_GAP`) keeps the stop at least 1% below the price and raises only when the new level beats the current stop by more than $0.01.
- **Inert adjustments:** ATR (`volatility_aware`), voter tightening and support/resistance are off on the live path. `CostEfficientTradeCycle` builds the manager without an `atr_fetcher`, and nothing calls `update_voter_signal` or `set_support_resistance`. A guard test scans all of `src/` for such callers.
- **How the simulation uses them:** it builds the same manager and calls the live `_trailing_level`, so the tiers are not re-implemented. Bar values are converted to Python floats first, since numpy floats change the cent rounding.
- **Timing:** one raise per day from that day's close (the evening routine runs at 15:50 ET, ten minutes before it). The raised stop applies from the next session.
- **Fills:** a session low at or below the stop exits at min(open, stop), so a gap fills at the open. A day that touches both stop and target counts as the stop.

**Statistics:** circular block bootstrap (20-day blocks) for Sharpe intervals, and a paired bootstrap on the daily return differences (same blocks for both series) for the differences. Newey-West t-statistics for alpha and mean-return differences. In-sample is 2009-2019, out-of-sample 2020 on. The 54 paired tests (3 sizing/variant blocks x 3 costs x 3 periods x 2 modes) were added to `multiple_testing_audit.py` as an exit-rule family. Data stops at 2026-10-09, read-only, split-adjusted.

## Results

Moderate sizing (2% of equity), SELL-signal exits off, 5 bps a side, evening raise only. Alpha is against equal-weight buy-and-hold of the same symbols, with the Newey-West t in brackets.

| Mode | Period | Sharpe [95% CI] | CAGR | Max DD | Trades | Win rate | Mean hold (days) | Alpha (t) |
| ---- | ------ | --------------- | ---- | ------ | ------ | -------- | ---------------- | --------- |
| bracket | full | 0.833 [0.363, 1.300] | 2.62% | -9.1% | 3,376 | 44.9% | 14.1 | +0.12% (+0.22) |
| bracket | 2009-2019 | 0.885 [0.338, 1.490] | 2.51% | -6.1% | 1,766 | 45.6% | 16.8 | +0.02% (+0.04) |
| bracket | 2020 on | 0.771 [-0.014, 1.584] | 2.76% | -9.1% | 1,610 | 44.2% | 11.1 | +0.22% (+0.21) |
| trailing | full | 0.808 [0.334, 1.291] | 2.61% | -8.4% | 3,709 | 42.5% | 12.2 | +0.34% (+0.55) |
| trailing | 2009-2019 | 0.799 [0.244, 1.368] | 2.29% | -4.9% | 1,972 | 43.0% | 14.3 | +0.05% (+0.08) |
| trailing | 2020 on | 0.823 [0.047, 1.598] | 3.07% | -8.4% | 1,737 | 42.0% | 9.8 | +0.74% (+0.63) |
| trailing_target | full | 0.791 [0.312, 1.272] | 2.28% | -9.0% | 4,513 | 42.7% | 9.2 | +0.20% (+0.38) |
| trailing_target | 2009-2019 | 0.904 [0.379, 1.453] | 2.35% | -3.6% | 2,380 | 43.2% | 10.7 | +0.34% (+0.57) |
| trailing_target | 2020 on | 0.651 [-0.175, 1.502] | 2.13% | -9.0% | 2,133 | 42.2% | 7.4 | -0.02% (-0.02) |

Trailing exits more trades per year than the bracket (3,709 against 3,376 closed trades) and wins less often. Its edge, if any, comes from smaller losers and longer-held winners. Trailing has the better out-of-sample Sharpe and trailing_target the worse (0.823 and 0.651 against 0.771 for the bracket), but the intervals overlap heavily and the order reverses in-sample, so this is noise.

### Paired differences against the bracket

Full period, 5 bps, Sharpe difference with paired block-bootstrap 95% CI. Every interval includes zero.

| Variant | trailing - bracket | trailing_target - bracket |
| ------- | ------------------ | ------------------------- |
| SELL exits off (live exits), evening raise only | -0.024 [-0.244, +0.194] | -0.042 [-0.225, +0.139] |
| SELL exits kept (#574 convention), evening raise only | -0.043 [-0.247, +0.159] | +0.004 [-0.145, +0.153] |
| SELL exits off, with the morning-raise proxy | -0.112 [-0.328, +0.105] | -0.151 [-0.331, +0.037] |

The paired intervals (about 0.4 wide) are much tighter than the gap between two separate Sharpe intervals (about 0.94), because both series share the same entries and market days.

### SELL-signal exits kept

The #574 baseline sells on a SELL signal; the live system has no such exit. Moderate sizing, 5 bps, full period:

| Mode | Sharpe [95% CI] | CAGR | Max DD | Trades | Win rate | Mean hold (days) | Alpha (t) |
| ---- | --------------- | ---- | ------ | ------ | -------- | ---------------- | --------- |
| bracket | 0.687 [0.205, 1.148] | 1.98% | -6.9% | 4,111 | 44.2% | 8.8 | +0.11% (+0.19) |
| trailing | 0.644 [0.176, 1.112] | 1.95% | -7.8% | 4,357 | 41.5% | 8.4 | +0.07% (+0.12) |
| trailing_target | 0.691 [0.212, 1.165] | 1.88% | -7.6% | 5,002 | 42.1% | 6.8 | +0.15% (+0.27) |

### Costs, sizing and morning raise

- **Costs:** 0 and 10 bps give the same picture, and every paired interval includes zero. At 10 bps trailing's full-period alpha is -0.11% (t = -0.18) and trailing_target's is -0.24% (t = -0.44). At 0 bps trailing's is +0.73% (t = +1.19), which is still not significant.
- **Sizing:** conservative sizing (1% of equity) is in the results file and does not change the conclusion.
- **Morning-raise sensitivity** (`LiveRules.morning_raise`, default off): stops are raised from the day's open before the day's range is checked. The open is an upper bound on the 09:20 pre-market price (it assumes the gap is fully priced), so this is the largest plausible effect. Full period, 5 bps, SELL exits off: trailing 0.808 to 0.720 (paired change -0.088 [-0.211, +0.040]); trailing_target 0.791 to 0.681 (-0.110 [-0.196, -0.023], excludes zero). These comparisons repeat the same hypotheses under another assumption, so they are kept out of the paired tests and the multiple-testing audit.

## Conclusion

On this signal, the live trailing-stop exits neither help nor hurt by an amount this data can detect. Compared with the fixed bracket, the full-period Sharpe is 0.02 to 0.04 lower at the evening-raise level (one case +0.004), with intervals of about ±0.2. Trailing_target, which keeps the 8% leg that new entries carry until day 90, is no better than trailing alone. If the morning raise acts as the open-as-proxy suggests, the trailing modes lose about 0.1 Sharpe more, which would move the point estimates to the negative side, though those intervals still include zero (trailing_target alone reaches -0.151 [-0.331, +0.037]). Nothing here is a reason to change the exits, and nothing shows that the trailing tiers add value.

## Not Modelled

- **Morning raise:** the 09:20 ET routine raises from the broker's price, a pre-market or after-hours last trade, which on gap days differs from the 15:50 price. Daily bars have no pre-market price (none are in the database). The sensitivity above bounds it; the live size is not measured.
- **Raise deferral:** the reconciler skips a raise while the stop order is in a non-replaceable state (`accepted`, `pending_new`, `pending_replace`, `pending_cancel`) until a later run. The simulation lands every raise at once. Likely tiny.
- **Stale entry price across a split:** live local `entry_price` is not refreshed after a split, so live tiers on a position held through a split use the pre-split cost. The simulation uses the split-adjusted entry. Only 4-8 of about 3,700-5,000 simulated trades span a split, so the results are unaffected. A live-code issue to refresh it from the broker could be filed.
- **GTC renewal**, intraday decisions, IEX bars and dividends, as in the baseline.

## Caveats

- **Raise price:** the simulation raises from the 16:00 close, but the routine sees the 15:50 price. Replacing the close with a noisy 15:50 proxy moved the trailing Sharpe by about ±0.04 (no consistent sign). That timing noise is not in the bootstrap interval.
- **Stop slippage:** costs are a flat bps per side and in-bar stops fill exactly at the stop price. The trailing modes make more near-the-price stop exits (2,000 stop and trail exits for trailing against 1,447 stops for the bracket, SELL-exit variant), so extra stop-market slippage hurts them more. A check outside the committed results with +10 bps on non-gap stop fills moved trailing minus bracket from -0.043 to -0.090, and +25 bps to -0.160 (intervals still include zero). The 0/5/10 bps grid does not show this.
- **Conditional comparison:** the entry signal has no out-of-sample edge (#574). This compares exit rules given that signal, on a hindsight universe that favors long holds.
- **GOOGL split:** GOOGL's 2014-04-03 2-for-1 split is missing from `gex.corporate_events`, which leaves a phantom -49.7% day in the adjusted series. It is shared with the #574 baseline and immaterial here (Sharpe moves by about 0.004 when patched; no GOOGL position spans the date). It was not patched and can be reported to the gex repo.
- **Multiple tests:** 54 paired tests were run; none is significant even before correction.
- **Reproducibility:** the runner was re-run twice (different hash seed) and reproduced the committed JSON exactly; an independent re-derivation of the headline rows agreed.
