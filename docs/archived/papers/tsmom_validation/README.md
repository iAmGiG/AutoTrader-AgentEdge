# TSMOM Validation Research Paper

**Working Title**: "Evaluating Time Series Momentum in Multi-Agent Trading Systems: A Comparative Study with Technical Indicators"

**Status**: Framework Ready - Awaiting Experimental Results

**Target Venue**: TBD (Computational Finance, Algorithmic Trading, or AI in Finance journal)

---

## Research Question

Can time series momentum (TSMOM) provide uncorrelated alpha when integrated with technical indicator-based voting strategies in automated trading systems?

**Hypothesis**: 12-month TSMOM signals will achieve Sharpe > 0.6 with correlation < 0.5 to existing MACD+RSI voting strategy.

---

## Repository Structure

### `latex/` - LaTeX Project Files

Complete paper structure ready for results population.

**Core Files**:

- `Main.tex` - Main document
- `00_Header.tex` - Preamble and packages
- `01_Introduction.tex` - Motivation and research gap
- `02_Related_work.tex` - TSMOM academic background (Moskowitz et al. 2012)
- `03_Methodology.tex` - Backtesting framework and signal generation
- `04_Experimental_setup.tex` - Data sources, parameters, validation approach
- `05_Results.tex` - Performance metrics and correlation analysis
- `06_Discussion.tex` - Interpretation and multi-agent implications
- `07_Conclusion.tex` - Contributions and future work
- `references.bib` - BibTeX bibliography

### `analysis/` - Research Artifacts

Experimental results and analysis.

**Planned Files**:

- `tsmom_backtest_results.md` - Full backtest results (2016-2024)
- `correlation_analysis.md` - TSMOM vs MACD+RSI correlation
- `regime_analysis.md` - Performance across bull/bear/crash regimes
- `walk_forward_validation.md` - Temporal stability analysis

### `figures/` - Visualizations

Generated figures for paper.

**Planned Figures**:

1. `figure1_system_architecture.png` - Multi-agent trading system with TSMOM
2. `figure2_tsmom_signals.png` - Example TSMOM signal generation
3. `figure3_performance_comparison.png` - TSMOM vs MACD+RSI vs Buy-Hold
4. `figure4_correlation_heatmap.png` - Strategy correlation matrix
5. `figure5_regime_performance.png` - Performance by market regime
6. `figure6_equity_curves.png` - Portfolio equity curves
7. `figure7_drawdown_comparison.png` - Drawdown analysis
8. `figure8_triple_voting.png` - Triple voting consensus example

---

## Research Design

### Phase 1: TSMOM Validation (Weeks 5-7)

**Objective**: Validate TSMOM as standalone strategy

**Metrics**:

- Sharpe Ratio: Target > 0.6 (academic baseline: 0.48-0.79)
- Max Drawdown: < -20%
- Correlation with MACD+RSI: < 0.5
- Win Rate: 45-55%

**Data**:

- Symbols: AAPL, GOOGL, MSFT, NVDA, AMZN, META
- Period: 2016-01-01 to 2024-12-31 (10 years)
- Source: Alpaca Markets API

**Parameters**:

- Lookback: 252 days (12 months)
- Threshold: 10% absolute return
- Position: Full (1.0) for strong signals

### Phase 2: Comparative Analysis (Week 8)

**Objective**: Compare TSMOM with existing strategies

**Comparisons**:

1. TSMOM vs MACD-only
2. TSMOM vs MACD+RSI voting
3. TSMOM vs Buy-and-Hold

**Analysis**:

- Risk-adjusted returns (Sharpe)
- Drawdown profiles
- Trade frequency and win rate
- Correlation matrix

### Phase 3: Multi-Agent Integration (Week 9-10)

**Objective**: Evaluate triple voting (MACD + RSI + TSMOM)

**Voting Logic**:

- 3 agree → Strong signal (1.0 position)
- 2 agree → Moderate signal (0.67 position)
- 1 signals → Weak signal (0.33 position)
- 0 or conflict → HOLD

**Expected Outcome**:

- Improved Sharpe vs dual voting
- Reduced drawdown
- Lower correlation with market beta

---

## Key Results (Pending Experiments)

### Expected Findings

**TSMOM Standalone**:

- Sharpe: 0.6-0.8 (based on Moskowitz et al. 2012)
- Correlation: < 0.5 with MACD+RSI
- Drawdown: -15% to -20%

**Triple Voting**:

- Sharpe: 0.9-1.1 (improved risk-adjusted returns)
- Drawdown: -10% to -15% (reduced risk)
- Win Rate: 50-55% (consensus filtering)

**Market Regime Analysis**:

- Bull: TSMOM underperforms (trend lags)
- Bear: TSMOM outperforms (captures reversals)
- Crash: TSMOM protects (exits early)

---

## Methodology Summary

### Backtesting Framework

**Engine**: Custom in-house framework (650 lines)

- Refactored from validated experiment_293
- Commission modeling: $0.005/share (Alpaca)
- Position sizing: Dynamic based on signal strength

**Validation**:

- Framework validated on AAPL 2024 (Sharpe 1.315)
- Walk-forward testing across 10 years
- Out-of-sample validation (2024 held out)

### Signal Generation

**TSMOM Formula**:

```python
momentum = (Price_t / Price_{t-252}) - 1

IF momentum > 0.10:  BUY
IF momentum < -0.10: SELL
ELSE:                HOLD
```

**Comparison Strategies**:

- MACD: Fibonacci parameters (13/34/8)
- RSI: 14-period, 30/70 thresholds
- Dual Voting: Consensus between MACD + RSI

---

## Compilation Instructions

### Local Compilation

```bash
cd latex/
pdflatex Main.tex
bibtex Main
pdflatex Main.tex
pdflatex Main.tex
```

### Overleaf

1. Zip the `latex/` directory
2. Upload to Overleaf as new project
3. Compiler: pdfLaTeX
4. Bibliography: BibTeX

---

## Data Sources

**Market Data**:

- Alpaca Markets API (primary)
- 10 years historical stock data (2016-2024)
- Daily OHLCV bars

**Baseline Validation**:

- Experiment #293: MACD+RSI voting (0.856 Sharpe on AAPL 2024)
- Extended validation: 36.6% return over 2024-2025

**Academic Benchmark**:

- Moskowitz et al. (2012): TSMOM Sharpe 0.48-0.79 across asset classes

---

## Citation (Provisional)

```bibtex
@article{autotrader2025tsmom,
  title={Evaluating Time Series Momentum in Multi-Agent Trading Systems: A Comparative Study with Technical Indicators},
  author={AutoGen-Trader Research Team},
  journal={TBD},
  year={2025},
  note={AutoGen-Trader Project}
}
```

---

## Experiment Tracking

### Issue Links

- **#425**: Backtesting Framework (✅ Complete)
- **#420**: TSMOM Validation Research (🔜 In Progress)
- **#422**: Hybrid Integration (⏸️ Blocked by #420)
- **#421**: Comparative Analysis (⏸️ Blocked by #420)

### Project Board

- **Phase**: Research (TSMOM Validation)
- **Priority**: High
- **Assignee**: Research Team (Chat B)
- **Labels**: `research`, `tsmom`, `validation`

---

## Success Criteria

### Validation Bar (Moderate)

**TSMOM Standalone**:

- ✅ Sharpe Ratio > 0.6
- ✅ Correlation < 0.5 with MACD+RSI
- ✅ Max Drawdown < -20%
- ✅ Works across 2016-2024 (multiple regimes)

**If Validated**:

- Add `TSMOMVoterAgent` to production
- Update `TradingOrchestrator` for triple voting
- Paper trading (4 weeks)
- Promote to live if successful

**If Failed**:

- Archive research findings
- Document why TSMOM didn't meet bar
- Continue with dual voting (MACD+RSI)

---

## Timeline

- **Week 1-4**: Backtesting framework (✅ Complete)
- **Week 5-7**: TSMOM validation experiments (🔜 Current)
- **Week 8**: Comparative analysis and paper writing
- **Week 9-10**: Triple voting integration (if validated)
- **Week 11+**: Paper finalization and submission

---

## Contact

**Project**: AutoGen-Trader
**Repository**: github.com/iAmGiG/AutoGen-Trader
**Branch**: feature/research-backtesting-425
**Status**: Framework Complete, Experiments Pending

---

**Last Updated**: 2025-12-02
**Status**: Ready for Experiments
