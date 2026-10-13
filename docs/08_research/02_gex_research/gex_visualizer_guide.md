# GEX Regime Trace Comparator - User Guide

Interactive visualization tool for exploring Gamma Exposure (GEX) methodology differences across market regimes from 2020-2025.

**Location**: `tools/gex-visualizer/index.html`

## Overview

This visualizer demonstrates a key research finding: how the S² (spot price squared) scaling factor in absolute GEX calculations causes regime over-detection as market prices inflate over time.

### Dual View Comparison

| Left Panel: Practitioner View | Right Panel: Paper 2 View |
|------------------------------|---------------------------|
| Normalized ratio (price-independent) | Absolute GEX (S² scaled) |
| Fixed 1.0x scaling | Dynamic scaling based on price |
| Stable across price levels | Inflates with price increases |

## Features

### Media Controls

Full playback controls for stepping through historical market regimes:

| Control | Action | Keyboard |
|---------|--------|----------|
| Play/Pause | Start/stop simulation | Space |
| Step Forward | Next snapshot | Arrow Right |
| Step Back | Previous snapshot | Arrow Left |
| Next Year | Jump to next year | Arrow Up |
| Prev Year | Jump to previous year | Arrow Down |
| Start | Jump to beginning | Home |
| End | Jump to end | End |

**Speed Control**: 0.5x, 1x, 2x playback speeds

**Timeline Scrubber**: Click or drag to jump to any point in the timeline.

### Historical Timeline

21 end-of-day (EOD) regime snapshots from March 2020 to December 2025:

| Period | Key Events |
|--------|------------|
| 2020 | COVID crash (SPY $222) → V-shape recovery → Tech bubble |
| 2021 | Meme stocks → Inflation fears → 0DTE growth → ATH |
| 2022 | Fed pivot fears → Bear market ($358) → Choppy year end |
| 2023 | AI rally → Summer melt-up → Rate spike selloff → Santa rally |
| 2024 | Q1 breakout → Summer ATH → Election rally ($600) |
| 2025 | Current regime ($605) |

### Price History Sparkline

- **Yellow line**: Historical SPY price trajectory
- **Cyan marker**: Current timeline position (only shown when on historical data)
- **Manual mode**: When using sliders, marker hides to indicate hypothetical scenario

### Volatility Warning Banner

Automatically appears when dealer positioning enters extreme gamma territory (|tilt| > 0.25):

**Negative Gamma Regime** (tilt < -0.25, red/orange gradient):

- **Vol Amp**: Volatility amplification multiplier (baseline 3.81x)
- **Extreme Prob**: Likelihood of >2% daily moves (baseline 10.1x higher)

**Positive Gamma Regime** (tilt > 0.25, cyan/green gradient):

- **Vol Damp**: Volatility dampening factor (dealers stabilize)
- **Stability**: Market stability percentage indicator

### Zero Gamma Level

The "gamma flip point" where dealer exposure inverts:

- **Below 0γ**: Dealers are long gamma (dampens volatility)
- **Above 0γ**: Dealers are short gamma (amplifies volatility)

### Regime Persistence Meter

Visual indicator showing:

- Current regime duration (Day 1-8)
- Average persistence (~8 days equity, ~5 days volatility)
- Color coding: Cyan = long gamma, Red = short gamma

### UVXY Lead-Lag Signal

Displays the research-validated 1-day lead relationship:

- UVXY movements predict SPY direction
- 0.456 correlation coefficient

## Parameters

### Manual Controls

| Slider | Range | Description |
|--------|-------|-------------|
| Spot Price | $280-$620 | Current SPY price level |
| Open Interest | 3-12M | Total outstanding contracts |
| Dealer Positioning | -0.5 to +0.5 | Net dealer tilt (negative = short gamma) |

**Note**: Using sliders enters "Manual Mode" - you're exploring hypothetical scenarios, not historical data.

### Chart Controls (TradingView-style)

| Control | Action |
| ------- | ------ |
| Scroll on Chart | Adjust spot price (Shift = faster) |
| Drag on Chart | Drag up/down to adjust spot price |
| Y-Axis Drag/Scroll | Zoom price range (0.5x to 2.0x) |
| X-Axis Drag/Scroll | Zoom magnitude scale (0.3x to 3.0x) |
| Double-click Axis | Reset zoom to 1.0x |
| Click Sparkline | Jump to that historical date |

**Invert Scroll Toggle**: Found in the Chart Controls `?` popup (bottom-right). Disabled by default - uses visual mapping (drag/scroll up = price up). Toggle on for natural scrolling (drag/scroll down = price up, like mobile touchscreens).

### Help Buttons

Two separate `?` buttons provide context-specific help:

- **Sidebar `?`**: Simulation controls (play/pause, keyboard shortcuts)
- **Bottom-right `?`**: Chart controls (scroll zoom, axis drag, invert toggle)

## Terminology Glossary

| Term | Definition |
|------|------------|
| **GEX** | Gamma Exposure - net gamma dealers hold from hedging options |
| **S²** | Spot price squared - scaling factor in absolute GEX (Price × Price) |
| **γ (Gamma)** | Rate of delta change; hedge adjustment required per $1 price move |
| **0γ** | Zero gamma level - price where dealer exposure flips sign |
| **OI** | Open Interest - total outstanding option contracts |
| **Tilt** | Dealer positioning bias; negative = dealers short gamma (amplifies moves) |
| **UVXY** | ProShares Ultra VIX ETF - volatility proxy that leads SPY by ~1 day |

## Research Insight

The key demonstration:

1. **At 2020 prices ($300)**: Both methodologies produce similar regime signals
2. **At 2024-2025 prices ($600)**: S² factor = 4.0x (600²/300² = 360,000/90,000)
3. **Result**: Absolute GEX shows "regime detected" when normalized view shows neutral

This explains why practitioners using normalized ratios may see different signals than academic papers using absolute dollar GEX.

## Technical Details

### GEX Calculation

```text
Normalized GEX = Gamma × Dealer_Tilt × 50

Absolute GEX = Normalized_GEX × (Current_S² / Baseline_S²) × (Current_OI / Baseline_OI)

Where:
  Baseline_S² = 300² = 90,000
  Baseline_OI = 5M contracts
```

### Status Indicators

**Practitioner View**:

- NEUTRAL: |tilt| ≤ 0.2
- DIRECTIONAL: 0.2 < |tilt| ≤ 0.35
- STRONG SIGNAL: |tilt| > 0.35

**Absolute View**:

- NO REGIME: Total GEX ≤ 12B
- ELEVATED: 12B < Total GEX ≤ 20B
- REGIME DETECTED: Total GEX > 20B

## Data Modes

### Demo Mode (Default)

Built-in simulated SPY timeline (2020-2025) with 21 representative snapshots. Works out of the box for research demonstrations and public sharing.

### Real Data Mode (Local Only)

Loads actual historical GEX data from exported JSON files. Supports 34 symbols across 5 asset classes.

**Setup Requirements**:

1. Access to `.cache/gex_research.db` (premium API data - not included in repo)
2. Run `python tools/gex-visualizer/export_data.py` to generate JSON files
3. **Serve via HTTP** (browsers block fetch on file:// URLs):

   ```bash
   cd tools/gex-visualizer
   python -m http.server 8080
   # Open http://localhost:8080
   ```

4. Click "Real Data" button in the visualizer

**Multi-Asset Support**:

| Asset Class  | Symbols                         |
| ------------ | ------------------------------- |
| Equity       | SPY, QQQ, IWM, DIA, TQQQ, SQQQ  |
| Volatility   | UVXY, VXX, VIXY                 |
| Bonds        | TLT, HYG, LQD                   |
| Commodities  | GLD, SLV, USO                   |
| Sectors      | XLF, XLE, XLK, XLV              |

**Dynamic Chart Scaling**: When loading symbols with different price ranges (e.g., IWM ~$200 vs SPY ~$600), the chart automatically adjusts:

- Strike range calculated from min/max prices with 20% padding
- Strike step size adapts to price range (2, 5, 10, or 20 points)
- Y-axis zoom expanded to 0.2x-3.0x for full overview

> ⚠️ **Note**: The `data/` folder is gitignored. Real data exports contain proprietary historical options data and must remain LOCAL ONLY.

## File Structure

```text
tools/gex-visualizer/
├── index.html       # HTML structure (~380 lines)
├── styles.css       # All CSS styles (~1300 lines)
├── main.js          # JavaScript logic (~1450 lines)
├── data-loader.js   # Real data loading module
├── export_data.py   # SQLite → JSON export script
├── data/            # (gitignored) Exported JSON files
└── README.md        # Quick reference
```

**Note**: The visualizer is modular but still standalone - open `index.html` directly in a browser (no build step required). For Real Data mode, serve via HTTP.

## Related Research

- **Issue #394**: Forward testing validation (3.81x volatility in negative gamma)
- **Issue #501**: Big data pipeline (50.88M options records → 17,835 daily metrics)
- **Issue #496**: Cross-asset correlation (UVXY leads SPY)
- **Issue #421**: TSMOM vs GEX analysis

## Use Cases

1. **LinkedIn Posts**: Demonstrate GEX methodology differences visually
2. **Education**: Teach options market structure and dealer hedging
3. **Research Validation**: Verify findings from academic GEX papers
4. **Strategy Development**: Understand regime detection implications
