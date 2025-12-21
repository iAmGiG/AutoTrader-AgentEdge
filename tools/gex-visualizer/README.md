# GEX Regime Trace Comparator

Interactive visualization tool for exploring Gamma Exposure (GEX) methodology differences across market regimes.

## Quick Start

Open `index.html` in a browser - no server required.

## Features

- **Dual View Comparison**: Normalized (Practitioner) vs Absolute (S² Scaled) GEX
- **Historical Timeline**: 21 EOD regime snapshots from March 2020 to December 2025
- **Media Controls**: Play/pause, step through, timeline scrubbing, keyboard shortcuts
- **Price Sparkline**: Click to jump, hover for tooltips, historical trajectory
- **Axis Scaling**: TradingView-style zoom via scroll or drag on Y/X axes
- **Color-Coded Regimes**: Cyan for long gamma (stabilizing), red for short gamma (amplifying)
- **Research Metrics**: Volatility warnings, regime persistence, UVXY lead-lag signals
- **Help System**: Two `?` buttons - sim controls (sidebar) and chart controls (bottom-right)

## Controls

| Control | Action |
|---------|--------|
| Space | Play/Pause simulation |
| Arrow Left/Right | Step backward/forward |
| Arrow Up/Down | Jump to next/prev year |
| Home/End | Jump to start/end |
| Scroll on Chart | Adjust spot price (Shift = faster) |
| Drag on Chart | Drag up/down to adjust spot price |
| Y-Axis Drag/Scroll | Zoom price range |
| X-Axis Drag/Scroll | Zoom magnitude scale |
| Double-click Axis | Reset zoom |
| Click Sparkline | Jump to that point |
| R | Reset view (zoom) |
| F | Toggle fullscreen |

## Color Legend

| Color | Meaning |
|-------|---------|
| Cyan/Green | Long gamma - dealers stabilize volatility |
| Red/Orange | Short gamma - dealers amplify volatility |
| Yellow | Spot price line |
| Purple | Zero gamma (0γ) flip point |

## Terminology

| Symbol | Meaning |
|--------|---------|
| GEX | Gamma Exposure - net gamma dealers hold from hedging |
| S² | Spot price squared - scaling factor (Price × Price) |
| γ | Greek letter gamma - hedge adjustment per $1 move |
| 0γ | Zero gamma level - dealer exposure flip point |
| Tilt | Dealer positioning bias (negative = short gamma) |
| UVXY | ProShares Ultra VIX ETF - volatility proxy |

## File Structure

```text
├── index.html    # HTML structure
├── styles.css    # CSS styles
├── main.js       # JavaScript logic
└── README.md     # This file
```

No build step required - open `index.html` directly in browser.

## Research Background

Based on GEX research analyzing 50.88M+ options records (2020-2025). Demonstrates how the S² scaling factor in absolute GEX methodology causes regime over-detection as SPY price increases from ~$300 (2020) to ~$600 (2025).

See `docs/08_research/03_gex_research/` for full methodology documentation.
