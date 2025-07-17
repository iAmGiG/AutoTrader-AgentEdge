# Analysis Tools Overview

This directory contains three analysis scripts that serve different purposes:

## 1. `analyze_cache.py`
**Purpose**: Analyzes cached MARKET DATA files  
**Scope**: `.cache/market_data/*.json`  
**What it does**:
- Shows which symbols have cached price data
- Reports date ranges covered for each symbol
- Identifies data sources (Alpha Vantage, Yahoo, FMP)
- Helps understand data gaps before running scans

**When to use**: Before running scans/backtests to check data availability

## 2. `analyze_scan_performance.py`
**Purpose**: Analyzes SCAN RESULTS from mechanical strategy  
**Scope**: `.cache/daily_scans/scan_*.csv`  
**What it does**:
- Evaluates mechanical strategy performance (TA + Market Heat)
- Shows approval rates at different heat levels
- Identifies most active symbols
- Tracks daily signal distribution

**When to use**: After running daily scans to evaluate strategy effectiveness

## 3. `aggregate_results.py`
**Purpose**: Analyzes BACKTEST RESULTS from full MAS runs  
**Scope**: `.cache/backtests/*/trades.csv, metrics.csv, equity.csv`  
**What it does**:
- Aggregates results from multiple backtest runs
- Calculates performance metrics (Sharpe, drawdown, etc.)
- Compares strategy vs buy-and-hold
- Identifies best/worst performing periods

**When to use**: After running backtests to evaluate overall strategy performance

## Summary

Each tool analyzes different stages of the trading pipeline:
1. **Cache** → `analyze_cache.py` (data availability)
2. **Scans** → `analyze_scan_performance.py` (signal generation)
3. **Backtests** → `aggregate_results.py` (trading performance)

All three serve distinct purposes and should be kept.