# Exit Strategy Analysis Experiments

**Research Question**: Which exit strategy provides the best expected value for MACD+RSI voting system?

## Critical Discovery

**Conservative exits (6% TP / 8% SL) have NEGATIVE expected value at realistic win rates!**

## Methodology

- **Entry System**: Validated MACD(13/34/8) + RSI voting
- **Test Scenarios**: Bull market, bear market, volatile sideways
- **Analysis**: Expected value calculation, actual backtesting, mathematical verification

## Scripts

### `performance_clarification.py`

- **Purpose**: Clarify per-trade vs annual returns
- **Key Insight**: 6%/8% are per-trade targets, not annual returns
- **Findings**: Actual annual returns depend on trade frequency and compounding

### `expected_value_analysis.py`

- **Purpose**: Mathematical expected value verification
- **Critical Finding**: Conservative strategy has -0.08% EV at 56.6% win rate
- **Formula**: EV = (Win Rate × Take Profit) - (Loss Rate × Stop Loss)

## Exit Strategy Comparison

### 🏆 Balanced Strategy (8% TP / 5% SL) - RECOMMENDED

- **Expected Value**: +1.50% per trade at 50% win rate
- **Breakeven Win Rate**: 38.5% (very achievable)
- **Actual Performance**: 27.48% annual return, 1.288 Sharpe ratio
- **Status**: ✅ OPTIMAL CHOICE

### ❌ Conservative Strategy (6% TP / 8% SL) - AVOID

- **Expected Value**: -0.08% per trade at 56.6% win rate
- **Breakeven Win Rate**: 57.1% (requires high accuracy)
- **Actual Performance**: 10.42% annual return, 0.578 Sharpe
- **Status**: ❌ NEGATIVE EXPECTED VALUE

### ⚡ Aggressive Strategy (10% TP / 3% SL)

- **Expected Value**: +1.33% per trade at 33.3% win rate
- **Breakeven Win Rate**: 23.1% (very low threshold)
- **Actual Performance**: 7.67% annual return, 0.488 Sharpe
- **Status**: 🤔 MATHEMATICALLY GOOD, PRACTICALLY MODERATE

## Key Mathematical Insights

### Expected Value Formula

```text
EV per trade = (Win Rate × Take Profit %) - (Loss Rate × Stop Loss %)
```

### Breakeven Win Rate Formula

```text
Breakeven WR = Stop Loss % / (Take Profit % + Stop Loss %)
```

### Examples:

- **Balanced (8%/5%)**: 5% / (8% + 5%) = 38.5% breakeven
- **Conservative (6%/8%)**: 8% / (6% + 8%) = 57.1% breakeven
- **Aggressive (10%/3%)**: 3% / (10% + 3%) = 23.1% breakeven

## Critical Lesson

**The original "0.373 Sharpe" claim for conservative exits was misleading!** The actual win rate achieved (66.7%) was much higher than the claimed 56.6%, masking the negative expected value.

## Recommendation

✅ **Use Balanced Strategy (8% TP / 5% SL)**

- Best expected value at realistic win rates
- Robust to win rate variations
- Proven 27.48% annual returns in testing

## Research Gaps & Future Work

### Important Context

While the "Balanced" strategy is mathematically superior to "Conservative" for fixed targets, a robust trading system—especially one using TSMOM—requires more adaptive exit logic. The current analysis makes sense for static, fixed-percentage exits but reveals significant gaps regarding dynamic market conditions and momentum-specific mechanics.

### 1. Volatility Normalization (ATR)

**Gap**: Fixed percentages (e.g., 5% SL) are rigid. In high volatility (high VIX), a 5% move might just be noise, triggering premature stops. In low volatility, an 8% target might never be reached.

**Why It Matters**: Professional systems typically use Average True Range (ATR) multiples (e.g., 2xATR) to adapt to market "noise."

**Future Work**: Test exits based on ATR multiples (e.g., SL = 2 × ATR, TP = 3 × ATR), allowing the system to breathe during volatile periods while tightening during calm markets.
**Tracked in**: Issue #538

### 2. Trailing Stops vs. Fixed Targets

**Gap**: Momentum strategies (like TSMOM) rely on "letting winners run." A fixed 8% Take Profit caps your upside on a stock that might run 50%.

**Why It Matters**: Trailing stops are essential to capture the "fat tails" of momentum distributions. Fixed targets truncate the right tail of returns, reducing overall expectancy.

**Future Work**: Investigate trailing stops (e.g., Chandelier Exit, parabolic SAR, ATR-trailing) to compare against fixed TP. Measure impact on Sharpe ratio and maximum favorable excursion.
**Tracked in**: Issue #539

### 3. Time-Based Exits

**Gap**: The current analysis ignores time. TSMOM often uses a fixed holding period (e.g., 1 month) rather than price targets. The interaction between price stops and time stops is missing.

**Why It Matters**: Academic TSMOM (Moskowitz et al.) uses holding periods, not price targets. A strategy might exit after 21 days regardless of P&L, then re-evaluate the signal.

**Future Work**: Compare fixed TP/SL against time-based exits (e.g., 5-day, 21-day holding periods). Test hybrid approaches: "exit at TP/SL OR after N days, whichever comes first."
**Tracked in**: Issue #540

### 4. Signal-Based Exits

**Gap**: The analysis assumes the trade must hit TP or SL. It doesn't account for exiting early if the signal reverses (e.g., MACD crosses down) before hitting either target.

**Why It Matters**: Signal invalidation often precedes adverse price moves. Exiting on signal reversal may reduce drawdowns without waiting for stop-loss.

**Future Work**: Test "exit on signal reversal" strategy. Compare: (A) fixed TP/SL only, (B) signal reversal only, (C) hybrid (whichever triggers first).

### 5. Dynamic Exit Selection (Regime-Aware)

**Gap**: One size (Balanced) fits all regimes. Market conditions vary—strong trends, mean-reversion, high/low volatility.

**Why It Matters**: Aggressive exits (wide stops, trailing TP) may excel in trending markets but fail in choppy conditions. Conservative exits may work better in range-bound markets.

**Future Work**: Link exit strategy selection to Market Regime Classifier or VIX levels (e.g., use Aggressive/Trailing in Bull, Conservative in Sideways, ATR-based in High-Vol).

## Tool Limitations

### `performance_clarification.py` Constraints

While this script validates the mathematical Expected Value, it has specific limitations:

1. **Synthetic Data**: Uses normally distributed random data. Real markets have "fat tails" (extreme events) that occur more frequently than this model predicts. (See #542)
2. **Data Granularity**: Operates on daily closing prices. It cannot simulate intraday stop-loss hits or "gap openings" where price jumps past the stop level.
3. **Compounding Aggressiveness**: The script bets 100% of equity on every trade. This maximizes growth rate (CAGR) but also maximizes drawdown depth compared to fixed-fractional sizing (e.g., 2% risk).
4. **Transaction Costs**: Now includes a default 0.1% cost, but does not model variable slippage based on liquidity or volatility. (See #541)

### `expected_value_analysis.py` Constraints

1. **Binary Outcome Simplification**: Assumes every trade hits exactly TP or SL. Ignores time-based exits, signal reversals, or trailing stops which create a continuous distribution of returns.
2. **Zero-Cost Assumption**: Does not factor in spread/commissions which reduce the effective TP and increase the effective SL.
3. **Single-Bet Isolation**: Calculates EV for a single independent trial. Does not account for serial correlation (streaks) common in momentum strategies.
4. **Missing Time Dimension**: Does not calculate "EV per Day". A lower EV strategy might be superior if it recycles capital faster.

## Related Issues

- Issue #293 - Updated with these findings
- Issue #303 - Configuration system to make exit strategies adjustable
- Issue #538 - ATR-Based Exit Strategy Comparison
- Issue #539 - Trailing Stop vs Fixed Take Profit Analysis
- Issue #540 - Time-Based Exit Testing
- Issue #541 - Transaction Cost Sensitivity Analysis
- Issue #542 - Real Market Fat Tails Validation

## Usage

```bash
# Clarify performance metrics
python performance_clarification.py

# Verify expected value math
python expected_value_analysis.py
```
