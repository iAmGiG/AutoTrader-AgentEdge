#!/usr/bin/env python3
"""
ScannerAgent - Multi-Ticker Market Scanning with Technical Analysis

Scans configurable watchlist for trading opportunities using MACD+RSI indicators.
Produces ranked opportunity list for downstream processing by VoterAgent.

Issue #386: ScannerAgent - Multi-Ticker Market Scanning with Technical Analysis
"""

import datetime
import json
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import pandas as pd
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from config_defaults.trading_config import TradingConfig

from .base_agent import BaseAgent

# Agent Bus for event publishing (Issue #390)
from src.autogen_agents.agent_bus import EventType, create_message, get_agent_bus
from src.data_sources.sources.market.unified_market_tool import (
    fetch_unified_market_data,
)
from src.trading_tools.indicators import calculate_macd, calculate_rsi
from src.utils.date_utils import get_datetime_now, now_iso, subtract_days, today_str

logger = logging.getLogger(__name__)

# Config paths
CONFIG_DIR = Path(__file__).parent.parent.parent / "config_defaults"
SCANNER_CONFIG_PATH = CONFIG_DIR / "scanner_config.yaml"
TRADING_MODES_PATH = CONFIG_DIR / "trading_modes.yaml"
WATCHLISTS_DIR = CONFIG_DIR / "watchlists"


# Fallback watchlist when config unavailable
FALLBACK_WATCHLIST = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "TSLA"]


def _load_scanner_config() -> Dict[str, Any]:
    """Load scanner configuration from YAML."""
    try:
        with open(SCANNER_CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.warning(f"Could not load scanner config: {e}")
        return {}


def _load_trading_modes() -> Dict[str, Any]:
    """Load trading modes configuration from YAML."""
    try:
        with open(TRADING_MODES_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.warning(f"Could not load trading modes: {e}")
        return {}


def _load_strategy_watchlist(strategy_name: str) -> List[str]:
    """Load tickers from a strategy watchlist file."""
    try:
        watchlist_path = WATCHLISTS_DIR / f"{strategy_name}.yaml"
        if not watchlist_path.exists():
            logger.warning(f"Strategy watchlist not found: {strategy_name}")
            return []

        with open(watchlist_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        tickers = data.get("tickers", [])
        logger.debug(f"Loaded {len(tickers)} tickers from {strategy_name} watchlist")
        return tickers
    except Exception as e:
        logger.warning(f"Could not load strategy watchlist {strategy_name}: {e}")
        return []


def _load_discovery_tickers() -> List[str]:
    """Load discovery tickers from default_watchlist in scanner_config."""
    config = _load_scanner_config()
    default_watchlist = config.get("default_watchlist", {})

    tickers = []
    for category_tickers in default_watchlist.values():
        if isinstance(category_tickers, list):
            tickers.extend(category_tickers)

    return tickers if tickers else FALLBACK_WATCHLIST


@dataclass
class TierLimits:
    """Limits for each watchlist tier."""

    positions: int = 10
    pending_orders: int = 5
    strategy: int = 8
    discovery: int = 5


@dataclass
class TieredWatchlistConfig:
    """Configuration for tiered watchlist system (Issue #405)."""

    enabled: bool = True
    max_symbols_per_scan: int = 25
    tier_limits: TierLimits = field(default_factory=TierLimits)
    fallback_to_config: bool = True

    @classmethod
    def from_config(cls) -> "TieredWatchlistConfig":
        """Load tiered config from scanner_config.yaml."""
        config = _load_scanner_config()
        tiered = config.get("tiered_watchlist", {})

        limits_data = tiered.get("tier_limits", {})
        tier_limits = TierLimits(
            positions=limits_data.get("positions", 10),
            pending_orders=limits_data.get("pending_orders", 5),
            strategy=limits_data.get("strategy", 8),
            discovery=limits_data.get("discovery", 5),
        )

        return cls(
            enabled=tiered.get("enabled", True),
            max_symbols_per_scan=tiered.get("max_symbols_per_scan", 25),
            tier_limits=tier_limits,
            fallback_to_config=tiered.get("fallback_to_config", True),
        )


@dataclass
class ScanConfig:
    """Configuration for market scanning."""

    watchlist: List[str] = field(default_factory=lambda: FALLBACK_WATCHLIST.copy())
    lookback_days: int = 60  # Days of price data to fetch
    max_concurrent_requests: int = 5  # Rate limiting
    request_delay_seconds: float = 0.2  # Delay between requests
    min_data_points: int = 42  # Minimum points for reliable signals
    macd_params: Dict[str, int] = field(
        default_factory=lambda: {"fast": 13, "slow": 34, "signal": 8}
    )
    rsi_params: Dict[str, int] = field(
        default_factory=lambda: {"period": 14, "oversold": 30, "overbought": 70}
    )
    volume_threshold: float = 1.0  # Minimum volume ratio vs 20-day average
    min_confidence: float = 0.5  # Minimum confidence for inclusion

    # Tiered watchlist config (Issue #405)
    tiered_config: TieredWatchlistConfig = field(default_factory=TieredWatchlistConfig.from_config)


@dataclass
class ScanResult:
    """Result of scanning a single ticker."""

    symbol: str
    action: str  # BUY, SELL, HOLD
    confidence: float
    signal_type: str  # STRONG, WEAK, NEUTRAL, CONFLICT
    current_price: float
    macd_signal: str
    macd_histogram: float
    rsi_value: float
    rsi_signal: str
    volume_ratio: float
    ranking_score: float
    timestamp: str
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "symbol": self.symbol,
            "action": self.action,
            "confidence": self.confidence,
            "signal_type": self.signal_type,
            "current_price": self.current_price,
            "macd_signal": self.macd_signal,
            "macd_histogram": self.macd_histogram,
            "rsi_value": self.rsi_value,
            "rsi_signal": self.rsi_signal,
            "volume_ratio": self.volume_ratio,
            "ranking_score": self.ranking_score,
            "timestamp": self.timestamp,
            "error": self.error,
        }


class ScannerAgent(BaseAgent):
    """
    Multi-ticker market scanning agent.

    Responsibilities:
    - Scan configurable watchlist for trading opportunities
    - Calculate MACD and RSI signals for each ticker
    - Produce ranked opportunity list by signal strength
    - Integrate with VoterAgent for final decision
    - Publish scan events via AgentBus

    Supports parallel data fetching with configurable rate limiting.
    """

    def __init__(
        self,
        name: str = "scanner_agent",
        scan_config: Optional[ScanConfig] = None,
        watchlist: Optional[List[str]] = None,
        use_config_file: bool = True,
        **kwargs,
    ):
        """
        Initialize ScannerAgent.

        Args:
            name: Agent identifier
            scan_config: ScanConfig object (takes precedence)
            watchlist: Override watchlist (convenience param)
            use_config_file: Whether to load from config file
            **kwargs: Additional BaseAgent parameters
        """
        super().__init__(name=name, **kwargs)

        # Initialize configuration
        if scan_config:
            self.scan_config = scan_config
        else:
            self.scan_config = ScanConfig()
            # Override watchlist if provided
            if watchlist:
                self.scan_config.watchlist = watchlist

        # Load MACD/RSI params from config file if available
        if use_config_file:
            try:
                config = TradingConfig()
                macd_cfg = config.get_macd_config()
                rsi_cfg = config.get_rsi_config()
                self.scan_config.macd_params = {
                    "fast": macd_cfg.fast,
                    "slow": macd_cfg.slow,
                    "signal": macd_cfg.signal,
                }
                self.scan_config.rsi_params = {
                    "period": rsi_cfg.period,
                    "oversold": rsi_cfg.oversold,
                    "overbought": rsi_cfg.overbought,
                }
            except Exception as e:
                logger.warning(f"Could not load config file: {e}, using defaults")

        # Agent Bus for event publishing
        self._bus = get_agent_bus()
        self._publish_events = True

        # Scan state
        self._last_scan_results: List[ScanResult] = []
        self._last_scan_time: Optional[datetime.datetime] = None

        # Tiered watchlist support (Issue #405)
        self._position_fetcher: Optional[Callable[[], List[str]]] = None
        self._pending_order_fetcher: Optional[Callable[[], List[str]]] = None
        self._current_trading_mode: str = "moderate"  # Default mode

        logger.info(f"ScannerAgent '{name}' initialized:")
        logger.info(f"  Watchlist: {len(self.scan_config.watchlist)} symbols")
        logger.info(f"  Tiered Watchlist: {self.scan_config.tiered_config.enabled}")
        logger.info(
            f"  MACD({self.scan_config.macd_params['fast']}/"
            f"{self.scan_config.macd_params['slow']}/"
            f"{self.scan_config.macd_params['signal']})"
        )
        logger.info(
            f"  RSI({self.scan_config.rsi_params['period']}) "
            f"[{self.scan_config.rsi_params['oversold']}/{self.scan_config.rsi_params['overbought']}]"
        )

    # ==================== Tiered Watchlist Methods (Issue #405) ====================

    def set_position_fetcher(self, fetcher: Callable[[], List[str]]) -> None:
        """
        Set callback to fetch current position symbols from broker.

        Args:
            fetcher: Callable that returns list of symbols for open positions
        """
        self._position_fetcher = fetcher

    def set_pending_order_fetcher(self, fetcher: Callable[[], List[str]]) -> None:
        """
        Set callback to fetch pending order symbols from broker.

        Args:
            fetcher: Callable that returns list of symbols with pending orders
        """
        self._pending_order_fetcher = fetcher

    def set_trading_mode(self, mode: str) -> None:
        """
        Set current trading mode (affects strategy watchlist selection).

        Args:
            mode: Trading mode name (conservative, moderate, aggressive)
        """
        self._current_trading_mode = mode
        logger.info(f"Trading mode set to: {mode}")

    def build_scan_list(self) -> List[str]:
        """
        Build prioritized scan list using tiered watchlist system.

        Tier priority:
            0: Active positions (broker-sourced) - ALWAYS included
            1: Pending orders (broker-sourced)
            2: Strategy watchlist (based on trading mode)
            3: Discovery tickers (from scanner_config)

        Returns:
            List of symbols to scan, respecting tier limits
        """
        config = self.scan_config.tiered_config

        if not config.enabled:
            # Tiered system disabled - use static watchlist
            return self.scan_config.watchlist[: config.max_symbols_per_scan]

        symbols: List[str] = []
        limits = config.tier_limits

        # Tier 0: Active positions (broker-sourced)
        if self._position_fetcher:
            try:
                position_symbols = self._position_fetcher()
                for symbol in position_symbols[: limits.positions]:
                    if symbol not in symbols:
                        symbols.append(symbol)
                logger.debug(f"Tier 0: Added {len(position_symbols)} position symbols")
            except Exception as e:
                logger.warning(f"Failed to fetch positions: {e}")

        # Tier 1: Pending orders (broker-sourced)
        if self._pending_order_fetcher:
            try:
                pending_symbols = self._pending_order_fetcher()
                added = 0
                for symbol in pending_symbols:
                    if symbol not in symbols and added < limits.pending_orders:
                        symbols.append(symbol)
                        added += 1
                logger.debug(f"Tier 1: Added {added} pending order symbols")
            except Exception as e:
                logger.warning(f"Failed to fetch pending orders: {e}")

        # Tier 2: Strategy watchlist (based on trading mode)
        strategy_name = self._get_strategy_for_mode(self._current_trading_mode)
        if strategy_name:
            strategy_tickers = _load_strategy_watchlist(strategy_name)
            added = 0
            for ticker in strategy_tickers:
                if ticker not in symbols and added < limits.strategy:
                    symbols.append(ticker)
                    added += 1
            logger.debug(f"Tier 2: Added {added} strategy tickers from '{strategy_name}'")

        # Tier 3: Discovery tickers (from default_watchlist)
        discovery_tickers = _load_discovery_tickers()
        added = 0
        for ticker in discovery_tickers:
            if ticker not in symbols and added < limits.discovery:
                symbols.append(ticker)
                added += 1
        logger.debug(f"Tier 3: Added {added} discovery tickers")

        # Apply hard limit
        final_list = symbols[: config.max_symbols_per_scan]
        logger.info(f"Built scan list: {len(final_list)} symbols")
        return final_list

    def _get_strategy_for_mode(self, mode: str) -> Optional[str]:
        """Get the watchlist strategy name for a trading mode."""
        modes_config = _load_trading_modes()
        modes = modes_config.get("modes", {})
        mode_config = modes.get(mode, {})
        return mode_config.get("watchlist_strategy")

    # ==================== Core Scanning Methods ====================

    def scan_market(
        self,
        watchlist: Optional[List[str]] = None,
        parallel: bool = True,
    ) -> List[ScanResult]:
        """
        Scan market for trading opportunities.

        Args:
            watchlist: Override watchlist for this scan
            parallel: Use parallel fetching (default True)

        Returns:
            List of ScanResult sorted by ranking_score
        """
        # Use provided watchlist, build tiered list, or fall back to static config
        if watchlist:
            symbols = watchlist
        elif self.scan_config.tiered_config.enabled:
            symbols = self.build_scan_list()
        else:
            symbols = self.scan_config.watchlist

        logger.info(f"Starting market scan for {len(symbols)} symbols...")

        start_time = time.time()

        if parallel:
            results = self._scan_parallel(symbols)
        else:
            results = self._scan_sequential(symbols)

        # Filter out errors and low-confidence results
        valid_results = [
            r
            for r in results
            if r.error is None and r.confidence >= self.scan_config.min_confidence
        ]

        # Sort by ranking score (highest first)
        valid_results.sort(key=lambda x: x.ranking_score, reverse=True)

        # Store results
        self._last_scan_results = valid_results
        self._last_scan_time = get_datetime_now()

        elapsed = time.time() - start_time
        logger.info(
            f"Scan complete: {len(valid_results)} opportunities "
            f"from {len(symbols)} symbols in {elapsed:.2f}s"
        )

        # Publish scan complete event
        if self._publish_events and valid_results:
            self._publish_scan_complete(valid_results)

        return valid_results

    def _scan_sequential(self, symbols: List[str]) -> List[ScanResult]:
        """Scan symbols sequentially with rate limiting."""
        results = []
        for symbol in symbols:
            try:
                result = self._scan_symbol(symbol)
                results.append(result)
                # Rate limiting delay
                time.sleep(self.scan_config.request_delay_seconds)
            except Exception as e:
                logger.warning(f"Error scanning {symbol}: {e}")
                results.append(self._create_error_result(symbol, str(e)))
        return results

    def _scan_parallel(self, symbols: List[str]) -> List[ScanResult]:
        """Scan symbols in parallel with thread pool."""
        results = []
        max_workers = min(self.scan_config.max_concurrent_requests, len(symbols))

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self._scan_symbol_safe, s): s for s in symbols}

            for future in futures:
                symbol = futures[future]
                try:
                    result = future.result(timeout=30)
                    results.append(result)
                except Exception as e:
                    logger.warning(f"Parallel scan failed for {symbol}: {e}")
                    results.append(self._create_error_result(symbol, str(e)))

        return results

    def _scan_symbol_safe(self, symbol: str) -> ScanResult:
        """Safe wrapper for _scan_symbol that catches exceptions."""
        try:
            return self._scan_symbol(symbol)
        except Exception as e:
            logger.warning(f"Error in _scan_symbol for {symbol}: {e}")
            return self._create_error_result(symbol, str(e))

    def _scan_symbol(self, symbol: str) -> ScanResult:
        """
        Scan a single symbol for trading signals.

        Args:
            symbol: Ticker symbol

        Returns:
            ScanResult with signal analysis
        """
        timestamp = now_iso()

        # Calculate date range
        end_date = today_str()
        start_date = subtract_days(get_datetime_now(), self.scan_config.lookback_days).strftime(
            "%Y-%m-%d"
        )

        # Fetch market data
        try:
            data = fetch_unified_market_data(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                source="auto",
            )
        except Exception as e:
            logger.warning(f"Data fetch failed for {symbol}: {e}")
            return self._create_error_result(symbol, f"Data fetch error: {e}")

        if data is None or data.empty:
            return self._create_error_result(symbol, "No data available")

        if len(data) < self.scan_config.min_data_points:
            return self._create_error_result(
                symbol, f"Insufficient data ({len(data)} < {self.scan_config.min_data_points})"
            )

        # Extract price series (handle both cases: 'Close' and 'close')
        if "Close" in data.columns:
            prices = data["Close"]
        elif "close" in data.columns:
            prices = data["close"]
        else:
            return self._create_error_result(symbol, "No close price column")

        current_price = float(prices.iloc[-1])

        # Calculate volume ratio
        volume_ratio = self._calculate_volume_ratio(data)

        # Calculate MACD
        macd_data = calculate_macd(
            prices,
            fast=self.scan_config.macd_params["fast"],
            slow=self.scan_config.macd_params["slow"],
            signal=self.scan_config.macd_params["signal"],
        )

        # Calculate RSI
        rsi_data = calculate_rsi(
            prices,
            period=self.scan_config.rsi_params["period"],
            oversold=self.scan_config.rsi_params["oversold"],
            overbought=self.scan_config.rsi_params["overbought"],
        )

        # Analyze signals
        macd_signal, macd_conf = self._analyze_macd(macd_data)
        rsi_signal, rsi_conf = self._analyze_rsi(rsi_data)

        # Determine voting consensus
        action, confidence, signal_type = self._voting_consensus(
            macd_signal, macd_conf, rsi_signal, rsi_conf
        )

        # Calculate ranking score
        ranking_score = self._calculate_ranking_score(
            action, confidence, volume_ratio, macd_data, rsi_data
        )

        return ScanResult(
            symbol=symbol,
            action=action,
            confidence=confidence,
            signal_type=signal_type,
            current_price=current_price,
            macd_signal=macd_signal,
            macd_histogram=float(macd_data["histogram"].iloc[-1]),
            rsi_value=float(rsi_data["rsi"].iloc[-1]),
            rsi_signal=rsi_signal,
            volume_ratio=volume_ratio,
            ranking_score=ranking_score,
            timestamp=timestamp,
        )

    def _calculate_volume_ratio(self, data: pd.DataFrame) -> float:
        """Calculate current volume vs 20-day average."""
        if "Volume" in data.columns:
            volume = data["Volume"]
        elif "volume" in data.columns:
            volume = data["volume"]
        else:
            return 1.0  # Default if no volume data

        if len(volume) < 20:
            return 1.0

        avg_volume = volume.iloc[-20:].mean()
        current_volume = volume.iloc[-1]

        if avg_volume > 0:
            return current_volume / avg_volume
        return 1.0

    def _analyze_macd(self, macd_data: Dict) -> tuple:
        """Analyze MACD signal and confidence."""
        histogram = macd_data["histogram"].iloc[-1]
        macd_threshold = 0.1  # Minimum histogram for signal

        if histogram > macd_threshold:
            return "BUY", 0.6
        elif histogram < -macd_threshold:
            return "SELL", 0.6
        else:
            return "HOLD", 0.3

    def _analyze_rsi(self, rsi_data: Dict) -> tuple:
        """Analyze RSI signal and confidence."""
        rsi_value = rsi_data["rsi"].iloc[-1]
        oversold = self.scan_config.rsi_params["oversold"]
        overbought = self.scan_config.rsi_params["overbought"]

        if rsi_value < oversold:
            return "BUY", 0.6
        elif rsi_value > overbought:
            return "SELL", 0.6
        else:
            return "HOLD", 0.3

    def _voting_consensus(
        self, macd_signal: str, macd_conf: float, rsi_signal: str, rsi_conf: float
    ) -> tuple:
        """
        Determine voting consensus from MACD and RSI signals.

        Returns:
            (action, confidence, signal_type)
        """
        consensus_boost = 0.15
        weak_boost = 0.1

        if macd_signal == rsi_signal and macd_signal != "HOLD":
            # Strong consensus
            action = macd_signal
            confidence = min(0.85, (macd_conf + rsi_conf) / 2 + consensus_boost)
            signal_type = "STRONG"

        elif (macd_signal != "HOLD" and rsi_signal == "HOLD") or (
            rsi_signal != "HOLD" and macd_signal == "HOLD"
        ):
            # Weak signal - only one indicator active
            active_signal = macd_signal if macd_signal != "HOLD" else rsi_signal
            active_conf = macd_conf if macd_signal != "HOLD" else rsi_conf
            action = active_signal
            confidence = min(0.65, active_conf + weak_boost)
            signal_type = "WEAK"

        elif macd_signal != rsi_signal and macd_signal != "HOLD" and rsi_signal != "HOLD":
            # Conflicting signals
            action = "HOLD"
            confidence = 0.2
            signal_type = "CONFLICT"

        else:
            # Both neutral
            action = "HOLD"
            confidence = 0.2
            signal_type = "NEUTRAL"

        return action, confidence, signal_type

    def _calculate_ranking_score(
        self,
        action: str,
        confidence: float,
        volume_ratio: float,
        macd_data: Dict,
        rsi_data: Dict,
    ) -> float:
        """
        Calculate ranking score for sorting opportunities.

        Higher score = better opportunity.
        """
        if action == "HOLD":
            return 0.0

        # Base score from confidence
        score = confidence * 50

        # Bonus for high volume
        if volume_ratio > self.scan_config.volume_threshold:
            score += min(20, (volume_ratio - 1) * 10)

        # Bonus for strong MACD histogram
        histogram = abs(macd_data["histogram"].iloc[-1])
        score += min(15, histogram * 5)

        # Bonus for extreme RSI (oversold for BUY, overbought for SELL)
        rsi_value = rsi_data["rsi"].iloc[-1]
        if action == "BUY" and rsi_value < 40:
            score += (40 - rsi_value) * 0.5
        elif action == "SELL" and rsi_value > 60:
            score += (rsi_value - 60) * 0.5

        return round(score, 2)

    def _create_error_result(self, symbol: str, error: str) -> ScanResult:
        """Create a ScanResult for error cases."""
        return ScanResult(
            symbol=symbol,
            action="HOLD",
            confidence=0.0,
            signal_type="ERROR",
            current_price=0.0,
            macd_signal="HOLD",
            macd_histogram=0.0,
            rsi_value=50.0,
            rsi_signal="HOLD",
            volume_ratio=0.0,
            ranking_score=0.0,
            timestamp=get_datetime_now().isoformat(),
            error=error,
        )

    # ==================== Watchlist Management ====================

    def add_to_watchlist(self, symbols: List[str]) -> None:
        """Add symbols to watchlist."""
        for symbol in symbols:
            if symbol not in self.scan_config.watchlist:
                self.scan_config.watchlist.append(symbol)
        logger.info(f"Watchlist updated: {len(self.scan_config.watchlist)} symbols")

    def remove_from_watchlist(self, symbols: List[str]) -> None:
        """Remove symbols from watchlist."""
        self.scan_config.watchlist = [s for s in self.scan_config.watchlist if s not in symbols]
        logger.info(f"Watchlist updated: {len(self.scan_config.watchlist)} symbols")

    def set_watchlist(self, symbols: List[str]) -> None:
        """Replace entire watchlist."""
        self.scan_config.watchlist = symbols.copy()
        logger.info(f"Watchlist set: {len(self.scan_config.watchlist)} symbols")

    def get_watchlist(self) -> List[str]:
        """Get current watchlist."""
        return self.scan_config.watchlist.copy()

    # ==================== Results Access ====================

    def get_opportunities(
        self,
        action_filter: Optional[str] = None,
        min_confidence: Optional[float] = None,
        top_n: Optional[int] = None,
    ) -> List[ScanResult]:
        """
        Get filtered and ranked opportunities from last scan.

        Args:
            action_filter: Filter by action (BUY, SELL, or None for all)
            min_confidence: Minimum confidence threshold
            top_n: Return only top N results

        Returns:
            Filtered list of ScanResult
        """
        results = self._last_scan_results.copy()

        # Apply action filter
        if action_filter:
            results = [r for r in results if r.action == action_filter.upper()]

        # Apply confidence filter
        if min_confidence:
            results = [r for r in results if r.confidence >= min_confidence]

        # Apply top N
        if top_n:
            results = results[:top_n]

        return results

    def get_buy_opportunities(self, top_n: int = 5) -> List[ScanResult]:
        """Get top buy opportunities."""
        return self.get_opportunities(action_filter="BUY", top_n=top_n)

    def get_sell_opportunities(self, top_n: int = 5) -> List[ScanResult]:
        """Get top sell opportunities."""
        return self.get_opportunities(action_filter="SELL", top_n=top_n)

    def get_scan_summary(self) -> Dict[str, Any]:
        """Get summary of last scan."""
        if not self._last_scan_results:
            return {
                "status": "no_scan",
                "message": "No scan has been performed yet",
            }

        buy_signals = [r for r in self._last_scan_results if r.action == "BUY"]
        sell_signals = [r for r in self._last_scan_results if r.action == "SELL"]

        return {
            "status": "complete",
            "scan_time": self._last_scan_time.isoformat() if self._last_scan_time else None,
            "total_scanned": len(self.scan_config.watchlist),
            "total_opportunities": len(self._last_scan_results),
            "buy_signals": len(buy_signals),
            "sell_signals": len(sell_signals),
            "top_buy": buy_signals[0].to_dict() if buy_signals else None,
            "top_sell": sell_signals[0].to_dict() if sell_signals else None,
            "watchlist_size": len(self.scan_config.watchlist),
        }

    # ==================== Event Publishing ====================

    def _publish_scan_complete(self, results: List[ScanResult]) -> None:
        """Publish scan complete event to AgentBus."""
        try:
            # Publish individual opportunity events
            for result in results:
                if result.action != "HOLD":
                    msg = create_message(
                        source_agent=self.name,
                        event_type=EventType.MARKET_DATA_RECEIVED,
                        symbol=result.symbol,
                        payload={
                            "action": result.action,
                            "confidence": result.confidence,
                            "signal_type": result.signal_type,
                            "ranking_score": result.ranking_score,
                            "macd_histogram": result.macd_histogram,
                            "rsi_value": result.rsi_value,
                            "volume_ratio": result.volume_ratio,
                        },
                    )
                    self._bus.publish_sync(msg)

            logger.debug(f"Published {len(results)} scan results to AgentBus")
        except Exception as e:
            logger.warning(f"Failed to publish scan results: {e}")

    def set_publish_events(self, enabled: bool) -> None:
        """Enable or disable event publishing."""
        self._publish_events = enabled

    # ==================== AutoGen Interface ====================

    def generate_reply(self, messages, context=None) -> str:
        """
        AutoGen's required method for handling incoming messages.

        Expected message formats:
        - {"command": "scan"} - Full watchlist scan
        - {"command": "scan", "symbols": ["AAPL", "MSFT"]} - Specific symbols
        - {"command": "opportunities", "action": "BUY", "top_n": 5}
        - {"command": "summary"}
        - {"command": "watchlist"}
        - {"command": "add_watchlist", "symbols": ["AAPL"]}
        - {"command": "remove_watchlist", "symbols": ["AAPL"]}
        """
        if not messages:
            return json.dumps({"error": "No messages to process"})

        # Get the latest message
        latest_message = messages[-1]
        if hasattr(latest_message, "content"):
            content = latest_message.content
        else:
            content = str(latest_message)

        # Try to parse as JSON
        try:
            if isinstance(content, str):
                command_data = json.loads(content)
            else:
                command_data = content

            command = command_data.get("command", "scan")

            if command == "scan":
                symbols = command_data.get("symbols")
                parallel = command_data.get("parallel", True)
                results = self.scan_market(watchlist=symbols, parallel=parallel)
                return json.dumps(
                    {
                        "status": "complete",
                        "opportunities": len(results),
                        "results": [r.to_dict() for r in results],
                    },
                    indent=2,
                )

            elif command == "opportunities":
                action_filter = command_data.get("action")
                min_conf = command_data.get("min_confidence")
                top_n = command_data.get("top_n")
                results = self.get_opportunities(action_filter, min_conf, top_n)
                return json.dumps({"results": [r.to_dict() for r in results]}, indent=2)

            elif command == "summary":
                return json.dumps(self.get_scan_summary(), indent=2)

            elif command == "watchlist":
                return json.dumps({"watchlist": self.get_watchlist()}, indent=2)

            elif command == "add_watchlist":
                symbols = command_data.get("symbols", [])
                self.add_to_watchlist(symbols)
                return json.dumps({"status": "updated", "watchlist": self.get_watchlist()})

            elif command == "remove_watchlist":
                symbols = command_data.get("symbols", [])
                self.remove_from_watchlist(symbols)
                return json.dumps({"status": "updated", "watchlist": self.get_watchlist()})

            elif command == "set_watchlist":
                symbols = command_data.get("symbols", [])
                self.set_watchlist(symbols)
                return json.dumps({"status": "set", "watchlist": self.get_watchlist()})

            else:
                return json.dumps({"error": f"Unknown command: {command}"})

        except json.JSONDecodeError:
            # Natural language - use LLM processing
            system_prompt = (
                "You are a market scanning agent that identifies trading "
                "opportunities.\n\n"
                "You can:\n"
                "- Scan multiple tickers for MACD+RSI signals\n"
                "- Rank opportunities by signal strength\n"
                "- Filter by action type (BUY/SELL) and confidence\n\n"
                "Return structured responses in JSON format."
            )
            return self.process_with_tools(content, system_prompt)

    def get_current_configuration(self) -> Dict[str, Any]:
        """Return current scanner configuration."""
        return {
            "watchlist_size": len(self.scan_config.watchlist),
            "lookback_days": self.scan_config.lookback_days,
            "max_concurrent_requests": self.scan_config.max_concurrent_requests,
            "min_data_points": self.scan_config.min_data_points,
            "macd_params": self.scan_config.macd_params.copy(),
            "rsi_params": self.scan_config.rsi_params.copy(),
            "volume_threshold": self.scan_config.volume_threshold,
            "min_confidence": self.scan_config.min_confidence,
        }


def create_scanner_agent(
    name: str = "scanner_agent",
    watchlist: Optional[List[str]] = None,
    **kwargs,
) -> ScannerAgent:
    """Factory function to create a properly configured scanner agent."""
    return ScannerAgent(name=name, watchlist=watchlist, **kwargs)
