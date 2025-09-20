# Reports Organization

This directory contains system reports and analysis results for the unified RH2MAS trading platform.

## Directory Structure

### `/scans/` - Market Analysis Reports

Real-time market scanning and technical analysis results from the unified system.

**Current Scan Types:**

- **Market Scanner**: Opportunity detection across watchlist symbols
- **Technical Scanner**: MACD+RSI analysis with actionable insights
- **Position Scanner**: Current position analysis and exit recommendations

**Report Format**: `YYYYMMDD_HHMM_scan_type.md`

### `/daily/` - Daily Trading Reports  

Automated daily reports from the trading cycle system.

**Report Types:**

- **Morning Routine**: Position reconciliation, stop adjustments, account status
- **Evening Review**: EOD position analysis, P&L summary, next day preparation
- **Risk Assessment**: Portfolio exposure, concentration limits, stop loss coverage

**Report Format**: `YYYYMMDD_HHMM_routine_type.md`

### `/performance/` - Trading Performance Analysis

Backtesting results and live trading performance tracking.

**Analysis Types:**

- **Monthly Performance**: P&L analysis, Sharpe ratio, win rate statistics
- **Strategy Validation**: Signal accuracy, entry/exit timing analysis  
- **Risk Metrics**: Drawdown analysis, position sizing effectiveness

### `/active/` - Current Development Results

Historical results from strategy development and validation.

#### `/active/voting_strategy/`

**Core validated voting system results** (Archive - system now implemented)

- `experiment_293_validation/` - ✅ MACD vs Voting comparison (0.856 Sharpe validated)
- `macd_optimization/` - Parameter optimization (13/34/8 proven optimal)
- `extended_period_analysis/` - 2024-2025 performance validation

### `/archived/` - Historical Development

Preserved results from previous system iterations and experiments.

### `/legacy/` - Pre-Unified System Reports  

Reports from the old fragmented system architecture (pre-September 10, 2025).

**Contains:**

- Old crash recovery reports (obsolete - PositionManager handles this automatically)
- Failed scan reports with date parsing errors (fixed in unified system)
- Manual state reconstruction attempts (unified state management eliminates need)

## Current Reporting System

### Automated Report Generation

The unified system automatically generates reports through:

**Market Scanner** (`src/trading/market_scanner.py`):

```bash
python -c "from src.trading.market_scanner import MarketScanner; MarketScanner().scan_watchlist()"
```

**Technical Scanner** (`src/trading/technical_scanner.py`):

```bash  
python -c "from src.trading.technical_scanner import TechnicalScanner; TechnicalScanner().analyze_opportunities()"
```

**Trading Cycle** (`src/trading/trading_cycle.py`):

```bash
python -c "from src.trading.trading_cycle import TradingCycle; TradingCycle().morning_routine()"
```

### Report Quality

- **Data Accuracy**: All reports use unified data sources with proper error handling
- **Consistent Format**: Standardized markdown format with clear sections
- **Actionable Insights**: Focus on specific next actions rather than just data dumps
- **Error-Free**: Proper date handling and market hours management

## Benefits Over Legacy System

### 1. **Reliable Data Sources**

- **Old**: Scattered data fetching with parsing errors
- **New**: Unified price fetcher with consistent error handling

### 2. **Automatic State Management**  

- **Old**: Manual crash recovery and state reconstruction
- **New**: PositionManager automatically syncs with broker

### 3. **Professional Format**

- **Old**: Cryptic filenames and unclear content
- **New**: Clear naming conventions and structured content

### 4. **Actionable Content**

- **Old**: Raw data dumps with no clear next steps
- **New**: Specific recommendations and threshold-based insights

---

*Reports reflect the unified trading system architecture with reliable data sources and professional formatting standards.*

*Last Updated: September 10, 2025 - Post Unified System Implementation*
