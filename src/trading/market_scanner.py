#!/usr/bin/env python3
"""
Cost-Efficient Scanner - Minimal API calls for opportunity detection

Core Principle: Download data once, run calculations locally, generate opportunities for human review.
- Single API call to fetch 5-min bars for all watchlist symbols
- Run MACD+RSI calculations locally (no API cost)
- Generate ranked opportunities for human review
- No automatic execution - human approval required
"""

import json
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime  # TODO date utils
from typing import Any, Dict, List, Tuple

import pandas as pd

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from config_defaults.trading_config import TradingConfig

from src.data_sources.sources.market.alpaca_market_data import AlpacaMarketData
from src.trading_tools.indicators import calculate_macd, calculate_rsi

logger = logging.getLogger(__name__)


@dataclass
class OpportunitySignal:
    """Represents a trading opportunity with signal details"""

    symbol: str
    current_price: float
    signal_type: str  # BUY, SELL, HOLD
    confidence: float
    strength: float
    vote_score: float
    entry_recommendation: str
    stop_price: float
    target_price: float
    position_size_percent: float
    reasoning: str
    macd_details: Dict[str, Any]
    rsi_details: Dict[str, Any]
    timestamp: str


@dataclass
class ScanResult:
    """Results from a complete market scan"""

    timestamp: str
    symbols_scanned: int
    opportunities: List[OpportunitySignal]
    market_conditions: Dict[str, Any]
    api_calls_used: int
    scan_duration: float


class CostEfficientScanner:
    """
    Scanner optimized for minimal API costs.

    Strategy:
    - Download all market data in single batch
    - Run all calculations locally
    - Cache results for re-analysis
    - Generate human-readable opportunity reports
    """

    def __init__(self, cache_dir: str = ".cache/scanner_data"):
        self.cache_dir = cache_dir
        self.market_data = AlpacaMarketData()
        self.config = TradingConfig()

        # Default watchlist (can be customized)
        self.default_watchlist = [
            # Core ETFs
            "SPY",
            "QQQ",
            "IWM",
            "VTI",
            # Leverage ETFs
            "TQQQ",
            "SQQQ",
            "UPRO",
            "SPXL",
            # Tech giants
            "AAPL",
            "MSFT",
            "NVDA",
            "TSLA",
            "META",
            "GOOGL",
            "AMZN",
            # Other interesting stocks
            "PLTR",
            "COIN",
            "AMD",
            "CRM",
            "NFLX",
        ]

        os.makedirs(cache_dir, exist_ok=True)
        logger.info("CostEfficientScanner initialized")

    def fetch_market_data_batch(self, symbols: List[str], days: int = 3) -> Dict[str, pd.DataFrame]:
        """
        Fetch market data for all symbols in a single batch.
        This is the main API cost - minimize by caching and reusing.
        """
        start_time = datetime.now()
        market_data = {}
        api_calls = 0

        for symbol in symbols:
            try:
                # Try to get recent data (this counts as 1 API call per symbol)
                # Use get_bars method from AlpacaMarketData
                from datetime import timedelta

                end_date = datetime.now()
                start_date = end_date - timedelta(days=days)

                data = self.market_data.get_bars(
                    symbols=[symbol],
                    start=start_date.strftime("%Y-%m-%d"),
                    end=end_date.strftime("%Y-%m-%d"),
                    timeframe="1Day",
                )

                # get_bars returns data for all symbols, extract the one we want
                if isinstance(data, dict) and len(data) > 0:
                    data = data[symbol] if symbol in data else None
                api_calls += 1

                if data is not None and len(data) >= 20:
                    market_data[symbol] = data
                    logger.debug(f"Fetched {len(data)} bars for {symbol}")
                else:
                    logger.warning(f"Insufficient data for {symbol}")

            except Exception as e:
                logger.error(f"Error fetching data for {symbol}: {e}")

        duration = (datetime.now() - start_time).total_seconds()
        logger.info(
            f"Batch fetched data for {len(market_data)}/{len(symbols)} symbols "
            f"in {duration:.1f}s using {api_calls} API calls"
        )

        return market_data, api_calls, duration

    def calculate_signals_locally(self, symbol: str, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate MACD+RSI signals locally (no API cost).
        Uses the validated voting logic from the orchestrator.
        """
        try:
            if len(data) < 42:  # Need enough data for indicators
                return {
                    "symbol": symbol,
                    "error": "Insufficient data for indicators",
                    "vote_score": 0.0,
                    "signal_type": "HOLD",
                }

            # MACD calculation (validated parameters)
            macd_config = self.config.get_macd_config()
            macd_data = calculate_macd(
                data["Close"] if "Close" in data.columns else data["close"],
                fast=macd_config.fast,  # 13
                slow=macd_config.slow,  # 34
                signal=macd_config.signal,  # 8
            )

            # RSI calculation (validated parameters)
            rsi_config = self.config.get_rsi_config()
            rsi_data = calculate_rsi(
                data["Close"] if "Close" in data.columns else data["close"],
                period=rsi_config.period,
                oversold=rsi_config.oversold,
                overbought=rsi_config.overbought,
            )

            # Get latest values
            latest_histogram = macd_data["histogram"].iloc[-1]
            current_rsi = rsi_data["rsi"].iloc[-1]
            current_price = (
                data["Close"].iloc[-1] if "Close" in data.columns else data["close"].iloc[-1]
            )

            # MACD signal logic (from validated system)
            if latest_histogram > 0.1:  # Positive histogram above threshold
                macd_action = "BUY"
                macd_strength = min(50.0, abs(latest_histogram) * 10)
                macd_confidence = 0.6
            elif latest_histogram < -0.1:  # Negative histogram below threshold
                macd_action = "SELL"
                macd_strength = -min(50.0, abs(latest_histogram) * 10)
                macd_confidence = 0.6
            else:
                macd_action = "HOLD"
                macd_strength = 0.0
                macd_confidence = 0.3

            # RSI signal logic (from validated system)
            if current_rsi < rsi_config.oversold:  # < 30
                rsi_action = "BUY"
                rsi_strength = (rsi_config.oversold - current_rsi) * 3.33
                rsi_confidence = 0.6
            elif current_rsi > rsi_config.overbought:  # > 70
                rsi_action = "SELL"
                rsi_strength = (current_rsi - rsi_config.overbought) * 3.33
                rsi_confidence = 0.6
            else:
                rsi_action = "HOLD"
                rsi_strength = 0.0
                rsi_confidence = 0.3

            # VALIDATED VOTING LOGIC (0.856 Sharpe ratio)
            if macd_action == rsi_action and macd_action != "HOLD":
                # Both agree - strong signal
                final_action = macd_action
                final_confidence = min(0.85, (macd_confidence + rsi_confidence) / 2 + 0.15)
                position_size = 1.0
                vote_score = 0.8  # High consensus
                reasoning = f"Strong consensus: Both MACD and RSI signal {macd_action}"

            elif (macd_action != "HOLD" and rsi_action == "HOLD") or (
                rsi_action != "HOLD" and macd_action == "HOLD"
            ):
                # One signals, one neutral - weak signal
                final_action = macd_action if macd_action != "HOLD" else rsi_action
                active_conf = macd_confidence if macd_action != "HOLD" else rsi_confidence
                final_confidence = min(0.65, active_conf + 0.1)
                position_size = 0.5
                vote_score = 0.6  # Moderate signal
                reasoning = f"Weak signal: Only {'MACD' if macd_action != 'HOLD' else 'RSI'} signals {final_action}"

            else:
                # Conflicting or both neutral
                final_action = "HOLD"
                final_confidence = 0.2
                position_size = 0.0
                vote_score = 0.0
                if macd_action != rsi_action and macd_action != "HOLD" and rsi_action != "HOLD":
                    reasoning = f"Conflicting signals: MACD={macd_action}, RSI={rsi_action}"
                else:
                    reasoning = "Both indicators neutral"

            return {
                "symbol": symbol,
                "signal_type": final_action,
                "confidence": final_confidence,
                "strength": macd_strength + rsi_strength,
                "vote_score": vote_score,
                "position_size_percent": position_size * 20,  # Max 20% position
                "reasoning": reasoning,
                "current_price": current_price,
                "macd_details": {
                    "action": macd_action,
                    "histogram": latest_histogram,
                    "macd_line": macd_data["macd"].iloc[-1],
                    "signal_line": macd_data["signal"].iloc[-1],
                    "strength": macd_strength,
                    "confidence": macd_confidence,
                },
                "rsi_details": {
                    "action": rsi_action,
                    "rsi": current_rsi,
                    "oversold_threshold": rsi_config.oversold,
                    "overbought_threshold": rsi_config.overbought,
                    "strength": rsi_strength,
                    "confidence": rsi_confidence,
                },
            }

        except Exception as e:
            logger.error(f"Error calculating signals for {symbol}: {e}")
            return {"symbol": symbol, "error": str(e), "vote_score": 0.0, "signal_type": "HOLD"}

    def calculate_stop_and_target(
        self, symbol: str, current_price: float, signal_type: str, confidence: float
    ) -> Tuple[float, float]:
        """
        Calculate stop loss and target prices based on signal strength.
        Conservative approach with fixed percentages.
        """
        if signal_type == "BUY":
            # Conservative stops: 5% stop loss, 8% target
            stop_price = current_price * 0.95
            target_price = current_price * 1.08

        elif signal_type == "SELL":
            # Short positions: 5% stop loss (price goes up), 8% target (price goes down)
            stop_price = current_price * 1.05
            target_price = current_price * 0.92

        else:
            stop_price = current_price
            target_price = current_price

        return stop_price, target_price

    def scan_opportunities(
        self, symbols: List[str] = None, min_vote_score: float = 0.6
    ) -> ScanResult:
        """
        Scan for trading opportunities with minimal API costs.

        Args:
            symbols: List of symbols to scan (default: self.default_watchlist)
            min_vote_score: Minimum vote score to include in results
        """
        if symbols is None:
            symbols = self.default_watchlist

        scan_start = datetime.now()
        logger.info(f"Starting scan of {len(symbols)} symbols...")

        # Step 1: Fetch all market data (main API cost)
        market_data, api_calls, fetch_duration = self.fetch_market_data_batch(symbols)

        # Step 2: Run all calculations locally (no API cost)
        opportunities = []

        for symbol, data in market_data.items():
            signal_data = self.calculate_signals_locally(symbol, data)

            # Skip if error or below threshold
            if "error" in signal_data or signal_data["vote_score"] < min_vote_score:
                continue

            # Calculate stop and target
            stop_price, target_price = self.calculate_stop_and_target(
                symbol,
                signal_data["current_price"],
                signal_data["signal_type"],
                signal_data["confidence"],
            )

            # Create opportunity signal
            opportunity = OpportunitySignal(
                symbol=symbol,
                current_price=signal_data["current_price"],
                signal_type=signal_data["signal_type"],
                confidence=signal_data["confidence"],
                strength=signal_data["strength"],
                vote_score=signal_data["vote_score"],
                entry_recommendation=f"{signal_data['signal_type']} {signal_data['position_size_percent']:.0f}% position",
                stop_price=stop_price,
                target_price=target_price,
                position_size_percent=signal_data["position_size_percent"],
                reasoning=signal_data["reasoning"],
                macd_details=signal_data["macd_details"],
                rsi_details=signal_data["rsi_details"],
                timestamp=datetime.now().isoformat(),
            )

            opportunities.append(opportunity)

        # Sort by vote score (best opportunities first)
        opportunities.sort(key=lambda x: x.vote_score, reverse=True)

        # Market conditions assessment (simple)
        market_conditions = {
            "symbols_with_data": len(market_data),
            "buy_signals": len([o for o in opportunities if o.signal_type == "BUY"]),
            "sell_signals": len([o for o in opportunities if o.signal_type == "SELL"]),
            "avg_confidence": sum(o.confidence for o in opportunities) / max(len(opportunities), 1),
            "market_bias": (
                "BULLISH"
                if len([o for o in opportunities if o.signal_type == "BUY"])
                > len([o for o in opportunities if o.signal_type == "SELL"])
                else "BEARISH"
            ),
        }

        scan_duration = (datetime.now() - scan_start).total_seconds()

        result = ScanResult(
            timestamp=datetime.now().isoformat(),
            symbols_scanned=len(symbols),
            opportunities=opportunities,
            market_conditions=market_conditions,
            api_calls_used=api_calls,
            scan_duration=scan_duration,
        )

        logger.info(
            f"Scan complete: {len(opportunities)} opportunities found "
            f"in {scan_duration:.1f}s using {api_calls} API calls"
        )

        return result

    def generate_scan_report(self, scan_result: ScanResult) -> str:
        """Generate human-readable scan report for opportunities"""

        report_lines = [
            f"# Market Scan Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            f"**Scan Duration:** {scan_result.scan_duration:.1f}s",
            f"**API Calls Used:** {scan_result.api_calls_used}",
            f"**Symbols Scanned:** {scan_result.symbols_scanned}",
            f"**Opportunities Found:** {len(scan_result.opportunities)}",
            "",
        ]

        # Market conditions
        conditions = scan_result.market_conditions
        report_lines.extend(
            [
                "## Market Conditions",
                f"**Market Bias:** {conditions['market_bias']}",
                f"**Buy Signals:** {conditions['buy_signals']}",
                f"**Sell Signals:** {conditions['sell_signals']}",
                f"**Average Confidence:** {conditions['avg_confidence']:.1%}",
                f"**Data Coverage:** {conditions['symbols_with_data']}/{scan_result.symbols_scanned} symbols",
                "",
            ]
        )

        # Top opportunities
        if scan_result.opportunities:
            report_lines.extend(
                [
                    "## Top Opportunities (Ranked by Vote Score)",
                    "",
                    "| Rank | Symbol | Signal | Price | Confidence | Vote Score | Stop | Target | Size | Reasoning |",
                    "|------|--------|--------|-------|------------|------------|------|--------|------|-----------|",
                ]
            )

            for i, opp in enumerate(scan_result.opportunities[:10], 1):  # Top 10
                report_lines.append(
                    f"| {i} | **{opp.symbol}** | {opp.signal_type} | ${opp.current_price:.2f} | "
                    f"{opp.confidence:.1%} | {opp.vote_score:.2f} | ${opp.stop_price:.2f} | "
                    f"${opp.target_price:.2f} | {opp.position_size_percent:.0f}% | {opp.reasoning[:50]}... |"
                )

            report_lines.extend(["", "## Detailed Analysis"])

            # Detailed breakdown for top 3
            for i, opp in enumerate(scan_result.opportunities[:3], 1):
                report_lines.extend(
                    [
                        f"### {i}. {opp.symbol} - {opp.signal_type} Signal",
                        f"**Current Price:** ${opp.current_price:.2f}",
                        f"**Vote Score:** {opp.vote_score:.2f} (Confidence: {opp.confidence:.1%})",
                        f"**Entry Recommendation:** {opp.entry_recommendation}",
                        f"**Stop Loss:** ${opp.stop_price:.2f} ({((opp.stop_price/opp.current_price-1)*100):+.1f}%)",
                        f"**Target:** ${opp.target_price:.2f} ({((opp.target_price/opp.current_price-1)*100):+.1f}%)",
                        f"**Reasoning:** {opp.reasoning}",
                        "",
                        "**Technical Details:**",
                        f"- MACD: {opp.macd_details['action']} (Histogram: {opp.macd_details['histogram']:.4f})",
                        f"- RSI: {opp.rsi_details['action']} (RSI: {opp.rsi_details['rsi']:.1f})",
                        "",
                    ]
                )
        else:
            report_lines.extend(
                [
                    "## No Opportunities Found",
                    "No signals met the minimum vote score threshold.",
                    "Consider lowering the threshold or expanding the watchlist.",
                    "",
                ]
            )

        # Footer
        report_lines.extend(
            [
                "---",
                "⚠️ **HUMAN REVIEW REQUIRED** - No automatic execution",
                "📊 **Next Steps:**",
                "1. Review top opportunities for manual entry",
                "2. Verify signals with additional analysis",
                "3. Check position sizing against portfolio limits",
                "4. Consider market conditions and news events",
                "",
                f"*Generated by CostEfficientScanner at {scan_result.timestamp}*",
            ]
        )

        return "\n".join(report_lines)

    def save_scan_results(self, scan_result: ScanResult, report: str):
        """Save scan results and report to files with better naming"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")  # Remove seconds for cleaner names

        # Save to dedicated scans folder with clear names
        results_file = f"reports/scans/{timestamp}_opportunities.json"
        os.makedirs(os.path.dirname(results_file), exist_ok=True)

        # Convert dataclasses to dict for JSON serialization
        scan_dict = {
            "timestamp": scan_result.timestamp,
            "symbols_scanned": scan_result.symbols_scanned,
            "api_calls_used": scan_result.api_calls_used,
            "scan_duration": scan_result.scan_duration,
            "market_conditions": scan_result.market_conditions,
            "opportunities": [
                {
                    "symbol": opp.symbol,
                    "signal_type": opp.signal_type,
                    "current_price": opp.current_price,
                    "confidence": opp.confidence,
                    "vote_score": opp.vote_score,
                    "stop_price": opp.stop_price,
                    "target_price": opp.target_price,
                    "position_size_percent": opp.position_size_percent,
                    "reasoning": opp.reasoning,
                    "macd_details": opp.macd_details,
                    "rsi_details": opp.rsi_details,
                }
                for opp in scan_result.opportunities
            ],
        }

        with open(results_file, "w") as f:
            json.dump(scan_dict, f, indent=2)

        # Save human-readable report
        report_file = f"reports/scans/{timestamp}_opportunities.md"
        with open(report_file, "w") as f:
            f.write(report)

        logger.info(f"Scan results saved to {results_file} and {report_file}")

        return results_file, report_file


def main():
    """Demo the cost-efficient scanner"""
    print("=== Cost-Efficient Scanner Demo ===")

    try:
        scanner = CostEfficientScanner()

        # Use a smaller watchlist for demo
        demo_symbols = ["TQQQ", "SPY", "NVDA", "AAPL", "TSLA"]

        print(f"\nScanning {len(demo_symbols)} symbols: {demo_symbols}")

        # Run scan
        scan_result = scanner.scan_opportunities(demo_symbols, min_vote_score=0.5)

        # Generate report
        report = scanner.generate_scan_report(scan_result)

        # Save results
        scanner.save_scan_results(scan_result, report)

        # Print summary
        print("\n📊 SCAN COMPLETE")
        print(f"Duration: {scan_result.scan_duration:.1f}s")
        print(f"API Calls: {scan_result.api_calls_used}")
        print(f"Opportunities: {len(scan_result.opportunities)}")

        if scan_result.opportunities:
            print(
                f"\nTop opportunity: {scan_result.opportunities[0].symbol} "
                f"({scan_result.opportunities[0].signal_type}, "
                f"score: {scan_result.opportunities[0].vote_score:.2f})"
            )

        print("\nReports saved to reports/")

    except Exception as e:
        print(f"Scanner demo failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
