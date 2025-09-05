# Reports Organization

This directory contains all experimental results and analysis reports for RH2MAS.

## Directory Structure

### `/active/` - Current Development Results
Results from ongoing Fibonacci regime detection development.

#### `/active/voting_strategy/`
**Core validated voting system results**
- `experiment_293_validation/` - MACD vs Voting comparison (✅ VOTING VALIDATED)
- `macd_optimization/` - Parameter optimization across tech stocks (13/34/8 optimal)
- `extended_period_analysis/` - 2024-2025 bull vs volatile market performance
- `indicator_comparisons/` - Ichimoku vs other indicators

#### `/active/fibonacci_regime/`
**Fibonacci regime detection development** (Issues #297-#301)
- `phase_1_results/` - Core Fibonacci Module (34 EMA filtering)
- `phase_2_results/` - CCI Filter Integration  
- `phase_3_results/` - Symmetry Break Detection
- `phase_4_results/` - Full Integration Testing

### `/archived/` - Historical and Deprecated Results
Results from completed or deprecated research.

#### `/archived/v0_v4_deprecated/`
**Legacy V0-V4 sentiment framework** (moved from active development)
- Original sentiment-based trading research
- Complexity vs ROI analysis
- Migration path documentation

## File Naming Convention

### Experiment Results:
`{experiment_id}_{description}_{date}.json`
- `293_voting_validation_2024_09_05.json`
- `macd_optimization_tech_stocks_2024_09_05.json`

### Analysis Reports:  
`{experiment_id}_{description}_report.md`
- `293_voting_validation_report.md`
- `extended_period_analysis_report.md`

### Summary Files:
`{category}_summary_{period}.md`
- `voting_strategy_summary_2024.md`
- `fibonacci_regime_progress_2024.md`

## Key Results Quick Reference

### ✅ Validated Systems:
1. **Voting Strategy**: 0.856 Sharpe, better risk management than single indicators
2. **Fibonacci MACD**: 13/34/8 parameters optimal across tech stocks  
3. **Market Regime Insight**: Better performance in volatile (-14.6% gap) vs bull (-25.8% gap)

### 🔄 In Development:
1. **Fibonacci Regime Detection**: 4-phase implementation (Issues #298-#301)
2. **Modular Architecture**: Component-based enhancement system

### ❌ Deprecated:
1. **V0-V4 Sentiment**: Complex system moved to archived (unproven ROI)
2. **Ichimoku Integration**: Confirmed better as visual aid only

## Usage Notes

- **Keep active results**: All files in `/active/` are current development
- **Archive old experiments**: Move completed research to `/archived/`
- **Use clear naming**: Follow convention for easy identification
- **Include metadata**: Each result file should have experiment context

---
*Last Updated: September 5, 2025 - Post-reorganization*