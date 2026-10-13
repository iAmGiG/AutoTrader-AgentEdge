# GEX Research Re-validation (October 2026)

**Issue**: #576 (re-validation), #548 (expanded data)
**Supersedes**: the headline findings of #531, #543, #544, #545 and #546, and the batch-1/2 statuses in [gex_strategy_research_index.yaml](gex_strategy_research_index.yaml)
**Data**: `gex_options` PostgreSQL, 2008-01-02 to 2026-10-09
**Status**: 🛑 STOP for GEX trading overlays. One descriptive volatility finding stands (below).

---

## Summary

The February 2026 GEX results came from two methodology errors:

1. **Same-day regime look-ahead.** `options_daily_summary.regime` is computed from end-of-day options data, but the runners used it to classify the same day's returns.
2. **Backtester bugs in `run_daily_signal_strategy`.** It ignored position size, booked the same P&L for long and short trades, and the dispersion and delta-neutral signals booked the move that triggered each trade.

With both fixed, and 227 tests corrected for multiple testing:

- **No GEX trading overlay survives.** This covers MACD+RSI regime filtering, dispersion, delta neutral and pairs.
- **No intraday effect.** GEX sign does not switch intraday momentum and reversal (Barbon-Buraschi design, 2026 snapshots).
- **One finding survives, and it is descriptive.** Across 40 symbols, negative dealer gamma on the previous day goes with about 8% higher next-day variance, after controlling for trailing variance and the leverage effect. The effect is concentrated in stressed markets (VIX above its 2008-2019 median of 16.6) and is about zero in calm markets. It is stable across 2008-2019 and 2020-2026, but it does **not** improve out-of-sample variance forecasts beyond HAR, leverage and VIX.

---

## What changed in the code

| Change | File | Commit |
|---|---|---|
| Regime lagged one observation by default (`lag_days=1`); `lag_days=0` kept only as a labelled look-ahead comparison | `src/backtesting/gex_overlay.py` | d7d5d8a |
| Read-only DB session; prices clamped at 2026-10-09 (vendor break) | `src/backtesting/research_backtester.py` | d7d5d8a |
| Window, lag and output options; Newey-West tests | `src/backtesting/research_cli.py`, all GEX runners | 8a2dbdc |
| `run_daily_signal_strategy`: P&L = direction × size × day's change, exits before booking; dispersion and delta-neutral signals decide on the previous close | `src/backtesting/research_backtester.py`, `src/backtesting/signals/` | 8469709 |
| Pairs positions marked to market daily | `src/backtesting/research_backtester.py` | 4139e39 |

**Backtester convention** (`run_daily_signal_strategy`): the signal for row *i* uses information through day *i − 1*; `daily_pnl_pct` is the long-side change of the traded quantity on day *i*. MACD+RSI already followed this and is unchanged (SPY Sharpe 0.561 before and after).

Unit tests: `tests/unit/backtesting/test_gex_overlay_lag.py`, `tests/unit/backtesting/test_daily_signal_backtest.py`.

---

## Data notes

- **Vendor break.** Alpha Vantage supplied options through 2026-10-09 and Cboe delayed quotes from 2026-10-12, with a GEX level break. All runs stop at 2026-10-09.
- **Regime labels are almost SPY-only.** `regime` is a fixed $1B threshold on `total_gex` (neutral = \|GEX\| < $1B). SPY has real variety; QQQ only after 2020; most other symbols are labelled almost 100% neutral. XLK and XLF have essentially no bullish or bearish days. The 40-symbol panel therefore uses scale-free measures (sign and 252-day percentile of `total_gex`).
- **0DTE omitted.** Stored equity GEX omits same-day-expiry contracts (gex-database-infrastructure Issue #74).
- **Toy P&L.** Dispersion books correlation change × 1.0, and delta neutral books IV−RV spread change × 0.25. These test the signal, not tradable option P&L.

---

## Results by study (regime lag 1)

### #531 MACD+RSI by regime, 2009 to 2026-10-09

| Symbol | Lag 0 (look-ahead): bull vs bear Sharpe | Lag 1 | Newey-West p, lag 1 |
|---|---|---|---|
| SPY | 10.7 vs −4.4 | 0.81 vs 0.81 | 0.25 |
| QQQ | 15.2 vs −6.4 | 2.00 vs 0.63 | 0.57 |
| IWM | 12.4 vs −5.3 | −1.56 vs 0.38 | 0.26 |

Lags 2 and 5 give two scattered p < 0.05 results with the wrong sign, which is consistent with chance. **No regime effect.** The earlier "Sharpe 7.73 vs −4.52, strongly confirmed" result was the look-ahead.

### #544, #545, #546 strategy overlays (fit 2008-2010, test 2011 to 2026-10-09)

| Overlay | Old reported gain | Fixed gain | Paired NW t, p |
|---|---|---|---|
| Dispersion (#545) | +0.108 | +0.085 | 1.63, 0.10 |
| Delta neutral (#544) | +0.012 | −0.037 | −1.00, 0.32 |
| Pairs SPY/IWM (#546) | −0.100 | −0.018 | −0.16, 0.87 |
| Pairs QQQ/SPY (#546) | −0.016 | +0.016 | 0.38, 0.70 |

None is significant, and none survives correction. The original 2020-2023 windows (6 to 20 trades) are also null.

**Transaction costs (#541):** pairs breaks even at 7.5 bps (was 5.9 bps before daily mark-to-market). Dispersion never breaks even. Delta neutral is positive at all cost levels, but on only 8 trades.

### #543 risk metrics, SPY / QQQ, 2008 to 2026-10-09

- **VaR ratio.** Bearish-to-bullish VaR is 2.1× / 1.9× (lag 0 gave 6.8× / 12.2×).
- **Variance beyond HAR.** In a log-HAR on Parkinson variance, a bearish regime scales next-day variance by about 1.5× over bullish (t = 13.7 / 8.6). This holds in both halves.
- **Out of sample** (fit 2008-2019, forecast 2020+). QLIKE improves for QQQ (p = 0.017) and SPY (p = 0.085). MSE shows no significant change.
- **VaR backtest.** Both models are well calibrated at 95%. The regime improves 95% tick loss for QQQ only (p = 0.03). At 99% the regime model breaches too often: 1.53% vs 1%, Kupiec p = 0.04.

### 40-symbol volatility panel (`gex_vol_panel.py`)

The model is a log-HAR on Parkinson variance with leverage controls: the lagged negative return, its 5- and 22-day means, and the trailing 22-day return. The pooled version uses symbol fixed effects, with errors clustered by date and symbol.

| Pooled, negative-GEX dummy | Coefficient (log variance) | t |
|---|---|---|
| HAR | +0.101 | 5.8 |
| + leverage | +0.077 | 5.0 |
| + leverage + VIX: calm markets | +0.016 | 1.0 |
| extra when VIX > 16.6 | +0.073 | 5.5 |
| + leverage, 2008-2019 only | +0.066 | 4.1 |
| + leverage, 2020-2026 only | +0.117 | 5.5 |

The 252-day GEX percentile gives the same picture with the opposite sign (higher GEX, lower variance): −0.117 (t = −4.6) with leverage controls.

**Per symbol, with leverage controls:** 80% of symbols have the expected sign. 17 of 40 are significant with the expected sign and 2 with the wrong sign.

**Out of sample:** there is no gain. Per symbol, QLIKE improves for 40% of symbols; without leverage controls it was 70%, so the per-symbol gain was mostly the leverage effect. Pooled (fit 2008-2019, forecast 2020+, all 40 symbols): QLIKE goes from 1.53989 to 1.53984 (DM t = 0.14, p = 0.89).

### #530 intraday momentum and reversal by GEX sign (`intraday_gamma_momentum.py`)

The test regresses the 15:30→16:00 return on the previous-close→15:30 return, interacted with a negative-GEX dummy (Baltussen et al. 2021; Barbon-Buraschi). The data are 166 days and 67 symbols (10,176 symbol-days), 2026-01-14 to 2026-10-09. Official closes are the endpoints. The 16:00 snapshot price differs from the official close by more than 10 bps on about 25% of symbol-days, which would bias the design toward reversal.

| GEX measured at | Sample | Interaction (expected > 0) | p |
|---|---|---|---|
| Prior close | All symbols | −0.012 | 0.067 |
| Prior close | Ex leveraged ETFs | −0.008 | 0.18 |
| Prior close | SPY | +0.052 | 0.047 |
| 15:30 snapshot | All symbols | −0.007 | 0.36 |

There is no intraday momentum in either gamma state across the panel. A timing strategy (follow the early move when GEX < 0, fade it otherwise) earns −0.5 bps/day gross (t = −0.8). SPY alone shows the predicted pattern, but it does not survive correction. **Null.**

---

## Multiple-testing audit

`scripts/research/multiple_testing_audit.py` treats every lag-1 test of a GEX effect as one family. It excludes lag-0 runs, VaR calibration tests and cointegration tests. Holm stays valid under the overlap between full-sample and half-sample tests; BH is approximate.

| Group | Tests | Holm | BH |
|---|---|---|---|
| MACD+RSI regime gap | 3 | 0 | 0 |
| Strategy overlays (all windows) | 8 | 0 | 0 |
| HAR regime term, SPY/QQQ/IWM, in-sample | 24 | 14 | 20 |
| HAR out-of-sample forecasts | 12 | 0 | 3 |
| VaR tick-loss comparison | 4 | 0 | 0 |
| Panel per symbol, in-sample | 80 | 17 | 34 |
| Panel per symbol, out-of-sample | 80 | 1 | 10 |
| Panel pooled, in-sample | 4 | 3 | 3 |
| Panel pooled, out-of-sample | 2 | 0 | 0 |
| Intraday momentum × GEX, timing strategy | 10 | 0 | 0 |
| **Total** | **227** | **35** | **70** |

---

## What this means for the project

- **Trading.** Do not use the GEX regime as a filter or sizing overlay for VoterAgent, dispersion, delta-neutral or pairs strategies.
- **Risk.** A RiskAgent could treat negative GEX in a high-VIX market as a descriptive warning flag (about 8% more next-day variance). It is not a forecasting input, since it adds nothing out of sample beyond trailing variance, recent returns and VIX. Do not use it to tighten VaR on positive-GEX days: that made 99% VaR breach too often.
- **Still untested.** Expiry-day pinning, a regime × liquidity split, and real option P&L for dispersion and delta neutral. See [literature_and_methods.md](literature_and_methods.md).

---

## Reproduce

```bash
PY=~/miniconda3/envs/AutoGex/bin/python
W="--fit-start 2008-01-02 --fit-end 2010-12-31 --test-start 2011-01-03 --test-end 2026-10-09"

$PY scripts/research/macd_rsi_regime_analysis.py --symbols SPY QQQ IWM \
    --start 2009-01-02 --end 2026-10-09 --warmup-start 2008-01-02 \
    --regime-lags 0 1 2 5 --output macd_rsi_regime_expanded.yaml
$PY scripts/research/dispersion_gex.py $W --regime-lag 1 --output dispersion_expanded_lag1.yaml
$PY scripts/research/delta_neutral_gex.py $W --regime-lag 1 --output delta_neutral_expanded_lag1.yaml
$PY scripts/research/pairs_trading_gex.py $W --regime-lag 1 --output pairs_trading_expanded_lag1.yaml
$PY scripts/research/var_vol_baseline.py --regime-lag 1 --output var_vol_baseline_lag1.yaml
$PY scripts/research/gex_vol_panel.py
$PY scripts/research/intraday_gamma_momentum.py
$PY scripts/research/multiple_testing_audit.py
```

Results are written to [results/](results/). The `*_lag0.yaml` files are look-ahead comparisons only.
