#!/usr/bin/env python3
"""
Useful Scanner - Actually helpful market analysis

Instead of useless "no opportunities found" reports, this scanner provides:
- Raw technical data for every symbol
- Clear explanation of why signals were rejected
- Alternative thresholds and what they would find
- Actionable next steps with specific symbols to watch
"""

import sys
import os
from datetime import datetime  # TODO Date utils
from typing import Dict, Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.trading.unified_price_fetcher import get_current_price
from src.data_sources.sources.market.alpaca_market_data import AlpacaMarketData


class UsefulScanner:
    """Scanner that actually provides useful insights instead of empty reports."""

    def __init__(self):
        self.market_data = AlpacaMarketData()

        # Realistic watchlist with liquid ETFs
        self.watchlist = [
            # Core ETFs (most liquid)
            "SPY", "QQQ", "IWM", "VTI", "VEA", "VWO",
            # Leveraged ETFs (higher volatility)
            "TQQQ", "SQQQ", "UPRO", "SPXS", "SPXL", "TNA", "TZA",
            # Sector ETFs
            "XLF", "XLK", "XLE", "XLV", "XLP", "XLI", "XLB", "XLU", "XLY",
            # Popular stocks
            "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "TSLA", "META"
        ]

    def get_raw_technical_data(self, symbol: str) -> Dict[str, Any]:
        """
        Get actual technical data instead of hiding it.

        Returns raw MACD, RSI, price data so humans can make decisions.
        """
        try:
            current_price = get_current_price(symbol)

            # Get recent price data for calculations
            end_date = datetime.now()
            start_date = end_date.replace(day=end_date.day - 60)  # 60 days

            data = self.market_data.get_bars(
                symbols=[symbol],
                start=start_date.strftime('%Y-%m-%d'),
                end=end_date.strftime('%Y-%m-%d'),
                timeframe="1Day"
            )

            if data is None or symbol not in data:
                return {
                    'symbol': symbol,
                    'error': 'No market data available',
                    'current_price': current_price,
                    'status': 'NO_DATA'
                }

            df = data[symbol]
            if len(df) < 26:  # Need enough data for MACD(12,26,9)
                return {
                    'symbol': symbol,
                    'error': f'Insufficient data: {len(df)} bars',
                    'current_price': current_price,
                    'status': 'INSUFFICIENT_DATA'
                }

            # Calculate technical indicators manually
            close_prices = df['close']

            # Simple MACD calculation
            ema12 = close_prices.ewm(span=12).mean()
            ema26 = close_prices.ewm(span=26).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9).mean()
            histogram = macd_line - signal_line

            # Simple RSI calculation
            delta = close_prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))

            # Get latest values
            latest_macd = macd_line.iloc[-1]
            latest_signal = signal_line.iloc[-1]
            latest_histogram = histogram.iloc[-1]
            latest_rsi = rsi.iloc[-1]

            # Calculate price momentum
            price_change_1d = (current_price - close_prices.iloc[-2]) / close_prices.iloc[-2] * 100
            price_change_5d = (
                current_price - close_prices.iloc[-6]) / close_prices.iloc[-6] * 100 if len(close_prices) >= 6 else 0
            price_change_20d = (
                current_price - close_prices.iloc[-21]) / close_prices.iloc[-21] * 100 if len(close_prices) >= 21 else 0

            # Determine signal strength with transparent logic
            macd_signal = "BUY" if latest_histogram > 0 else "SELL" if latest_histogram < -0.05 else "NEUTRAL"
            rsi_signal = "OVERSOLD" if latest_rsi < 30 else "OVERBOUGHT" if latest_rsi > 70 else "NEUTRAL"

            # Vote scoring (transparent)
            vote_score = 0.5  # Start neutral

            if macd_signal == "BUY":
                vote_score += 0.2
            elif macd_signal == "SELL":
                vote_score -= 0.2

            if rsi_signal == "OVERSOLD":
                vote_score += 0.15
            elif rsi_signal == "OVERBOUGHT":
                vote_score -= 0.15

            # Momentum bonus/penalty
            if price_change_5d > 2:
                vote_score += 0.1
            elif price_change_5d < -2:
                vote_score -= 0.1

            vote_score = max(0, min(1, vote_score))  # Clamp to 0-1

            return {
                'symbol': symbol,
                'current_price': current_price,
                'status': 'ANALYZED',
                'macd': {
                    'line': latest_macd,
                    'signal': latest_signal,
                    'histogram': latest_histogram,
                    'signal_type': macd_signal
                },
                'rsi': {
                    'value': latest_rsi,
                    'signal_type': rsi_signal
                },
                'momentum': {
                    'change_1d': price_change_1d,
                    'change_5d': price_change_5d,
                    'change_20d': price_change_20d
                },
                'vote_score': vote_score,
                'recommendation': self._get_recommendation(vote_score, macd_signal, rsi_signal),
                'data_points': len(df)
            }

        except Exception as e:
            return {
                'symbol': symbol,
                'error': str(e),
                'current_price': get_current_price(symbol),
                'status': 'ERROR'
            }

    def _get_recommendation(self, vote_score: float, macd_signal: str, rsi_signal: str) -> str:
        """Get clear recommendation with reasoning."""
        if vote_score >= 0.7:
            return f"STRONG BUY - High confidence ({vote_score:.2f})"
        elif vote_score >= 0.6:
            return f"BUY - Good setup ({vote_score:.2f})"
        elif vote_score <= 0.3:
            return f"STRONG SELL - High confidence ({1-vote_score:.2f})"
        elif vote_score <= 0.4:
            return f"SELL - Weak setup ({vote_score:.2f})"
        else:
            return f"HOLD - Mixed signals ({vote_score:.2f})"

    def scan_market(self, min_score: float = 0.6) -> Dict[str, Any]:
        """
        Scan market and provide USEFUL analysis.

        Returns detailed breakdown of every symbol, not just empty lists.
        """
        scan_start = datetime.now()
        print(f"🔍 Scanning {len(self.watchlist)} symbols...")

        results = {
            'scan_time': scan_start.isoformat(),
            'symbols_analyzed': [],
            'opportunities': [],
            'watch_list': [],
            'rejects': [],
            'errors': [],
            'summary': {}
        }

        for symbol in self.watchlist:
            print(f"  Analyzing {symbol}...")
            data = self.get_raw_technical_data(symbol)
            results['symbols_analyzed'].append(data)

            if data['status'] == 'ANALYZED':
                vote_score = data['vote_score']

                if vote_score >= min_score:
                    results['opportunities'].append(data)
                elif vote_score >= (min_score - 0.1):  # Close misses
                    results['watch_list'].append(data)
                else:
                    results['rejects'].append(data)
            else:
                results['errors'].append(data)

        # Generate useful summary
        analyzed_count = len([d for d in results['symbols_analyzed'] if d['status'] == 'ANALYZED'])

        results['summary'] = {
            'total_symbols': len(self.watchlist),
            'successfully_analyzed': analyzed_count,
            'opportunities_found': len(results['opportunities']),
            'near_misses': len(results['watch_list']),
            'rejected': len(results['rejects']),
            'errors': len(results['errors']),
            'scan_duration': (datetime.now() - scan_start).total_seconds(),
            'success_rate': f"{analyzed_count/len(self.watchlist)*100:.1f}%"
        }

        return results

    def generate_useful_report(self, results: Dict[str, Any]) -> str:
        """Generate actually useful report instead of useless boilerplate."""

        lines = [
            f"# Useful Market Scan - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            f"**Scanned:** {results['summary']['total_symbols']} symbols",
            f"**Analyzed:** {results['summary']['successfully_analyzed']} ({results['summary']['success_rate']})",
            f"**Duration:** {results['summary']['scan_duration']:.1f}s",
            "",
        ]

        # Opportunities section
        if results['opportunities']:
            lines.extend([
                f"## 🎯 Strong Opportunities ({len(results['opportunities'])})",
                "",
                "| Symbol | Price | Vote | MACD | RSI | Momentum | Recommendation |",
                "|--------|-------|------|------|-----|----------|----------------|"
            ])

            for opp in sorted(results['opportunities'], key=lambda x: x['vote_score'], reverse=True):
                momentum_5d = opp['momentum']['change_5d']
                momentum_str = f"{momentum_5d:+.1f}%" if momentum_5d else "N/A"

                lines.append(
                    f"| **{opp['symbol']}** | ${opp['current_price']:.2f} | "
                    f"{opp['vote_score']:.2f} | {opp['macd']['signal_type']} | "
                    f"{opp['rsi']['value']:.0f} ({opp['rsi']['signal_type']}) | "
                    f"{momentum_str} | {opp['recommendation']} |"
                )
            lines.append("")

        # Watch list section
        if results['watch_list']:
            lines.extend([
                f"## 👀 Watch List - Close to Signals ({len(results['watch_list'])})",
                "",
                "These symbols are close to our threshold. Monitor for changes:",
                ""
            ])

            for watch in sorted(results['watch_list'], key=lambda x: x['vote_score'], reverse=True):
                lines.append(
                    f"- **{watch['symbol']}**: {watch['vote_score']:.2f} - {watch['recommendation']}")
            lines.append("")

        # Top rejects with reasons
        if results['rejects']:
            top_rejects = sorted(results['rejects'],
                                 key=lambda x: x['vote_score'], reverse=True)[:5]
            lines.extend([
                "## ❌ Top Rejects (Why They Failed)",
                "",
                "Understanding why signals were rejected:",
                ""
            ])

            for reject in top_rejects:
                macd_reason = f"MACD {reject['macd']['signal_type'].lower()}"
                rsi_reason = f"RSI {reject['rsi']['value']:.0f} ({reject['rsi']['signal_type'].lower()})"

                lines.append(
                    f"- **{reject['symbol']}** ({reject['vote_score']:.2f}): "
                    f"{macd_reason}, {rsi_reason}, "
                    f"5d momentum {reject['momentum']['change_5d']:+.1f}%"
                )
            lines.append("")

        # Errors section
        if results['errors']:
            lines.extend([
                f"## ⚠️ Data Issues ({len(results['errors'])})",
                "",
                "Symbols with data problems:",
                ""
            ])

            for error in results['errors']:
                lines.append(f"- **{error['symbol']}**: {error.get('error', 'Unknown error')}")
            lines.append("")

        # Actionable next steps
        lines.extend([
            "## 🎯 Next Actions",
            "",
        ])

        if results['opportunities']:
            top_opp = results['opportunities'][0]
            lines.append(
                f"1. **Consider {top_opp['symbol']}** - Highest score ({top_opp['vote_score']:.2f})")

        if results['watch_list']:
            lines.append("2. **Monitor watch list** - Check these again in 1-2 hours")

        if not results['opportunities'] and not results['watch_list']:
            lines.extend([
                "1. **Lower threshold** - Try 0.55 instead of 0.6",
                "2. **Check individual names** - Look at top rejects manually",
                "3. **Wait for market movement** - Scan again in 2-4 hours"
            ])

        lines.extend([
            "",
            "---",
            f"*Scan completed at {results['scan_time']}*"
        ])

        return "\n".join(lines)


def main():
    """Demo the useful scanner."""
    print("🔍 USEFUL MARKET SCANNER")
    print("=" * 50)
    print("Actually provides actionable insights instead of empty reports")
    print()

    scanner = UsefulScanner()

    # Scan with reasonable threshold
    results = scanner.scan_market(min_score=0.6)

    # Generate useful report
    report = scanner.generate_useful_report(results)

    # Save report with clear naming in dedicated folder
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')  # Remove seconds for cleaner names
    report_file = f"/mnt/bst/yxie2/cregan1/RH2MAS/reports/scans/{timestamp}_market_scan.md"

    os.makedirs(os.path.dirname(report_file), exist_ok=True)
    with open(report_file, 'w') as f:
        f.write(report)

    print(report)
    print(f"\n📁 Saved to: {report_file}")

    # Show the difference
    print("\n" + "=" * 50)
    print("🆚 OLD vs NEW SCANNER COMPARISON")
    print("=" * 50)
    print("❌ Old scanner:")
    print("   - 'No opportunities found'")
    print("   - Empty JSON files")
    print("   - No explanation why")
    print("   - Useless boilerplate")
    print()
    print("✅ New scanner:")
    print("   - Shows ALL technical data")
    print("   - Explains WHY signals were rejected")
    print("   - Provides watch list of near-misses")
    print("   - Gives specific next actions")
    print("   - Actually helps make decisions!")


if __name__ == "__main__":
    main()
