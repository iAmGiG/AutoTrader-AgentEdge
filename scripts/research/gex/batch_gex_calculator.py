"""
Batch GEX Calculator: Calculate GEX metrics for all symbols in the database.

Processes all unique symbols in options_chains table and populates options_daily_summary.
"""

import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

DB_PATH = Path(".cache/gex_research.db")

# Asset class mapping
ASSET_CLASS_MAP = {
    # Equity benchmarks
    "SPY": "equity",
    "QQQ": "equity",
    "IWM": "equity",
    "DIA": "equity",
    "VTI": "equity",
    # Individual stocks
    "AAPL": "equity",
    "MSFT": "equity",
    "TSLA": "equity",
    # Leveraged equity
    "TQQQ": "equity",
    "SQQQ": "equity",
    "UPRO": "equity",
    "SPXU": "equity",
    "SPXL": "equity",
    "SPXS": "equity",
    "SOXL": "equity",
    "SOXS": "equity",
    "TNA": "equity",
    "TZA": "equity",
    "TECL": "equity",
    "TECS": "equity",
    "FAS": "equity",
    "FAZ": "equity",
    "LABU": "equity",
    "LABD": "equity",
    "NUGT": "equity",
    "DUST": "equity",
    # Volatility
    "UVXY": "volatility",
    "VXX": "volatility",
    # Commodities
    "GLD": "commodity",
    "SLV": "commodity",
    # Bonds
    "TLT": "bond",
    "IEF": "bond",
    "LQD": "bond",
    # Real estate
    "IYR": "real_estate",
}


def get_symbols(conn: sqlite3.Connection) -> List[str]:
    """Get all unique symbols from options_chains."""
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT symbol FROM options_chains ORDER BY symbol")
    return [row[0] for row in cursor.fetchall()]


def get_trading_dates_for_symbol(conn: sqlite3.Connection, symbol: str) -> List[str]:
    """Get all trading dates for a specific symbol."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT DISTINCT trading_date FROM options_chains WHERE symbol = ? ORDER BY trading_date",
        (symbol,),
    )
    return [row[0] for row in cursor.fetchall()]


def get_processed_dates(conn: sqlite3.Connection, symbol: str) -> set:
    """Get dates already processed for a symbol."""
    cursor = conn.cursor()
    cursor.execute("SELECT trading_date FROM options_daily_summary WHERE symbol = ?", (symbol,))
    return {row[0] for row in cursor.fetchall()}


def calculate_daily_gex(conn: sqlite3.Connection, symbol: str, trading_date: str) -> Optional[Dict]:
    """Calculate GEX metrics for a single trading date."""
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            option_type,
            strike,
            gamma,
            delta,
            underlying_price,
            open_interest,
            volume,
            expiration
        FROM options_chains
        WHERE symbol = ? AND trading_date = ?
        ORDER BY strike
    """,
        (symbol, trading_date),
    )

    rows = cursor.fetchall()
    if not rows:
        return None

    # Aggregate metrics
    total_gamma = 0.0
    call_gamma = 0.0
    put_gamma = 0.0
    total_oi = 0
    call_oi = 0
    put_oi = 0
    call_count = 0
    put_count = 0

    # For zero-gamma strike calculation
    weighted_zero_gamma_strike = 0.0
    zero_gamma_weight = 0.0

    # For max gamma strike
    max_gamma = 0.0
    max_gamma_strike = None

    # Track expirations
    expirations = set()

    # Underlying price (take first non-null)
    underlying_price = None

    for row in rows:
        option_type, strike, gamma, delta, u_price, oi, volume, expiration = row

        if underlying_price is None and u_price:
            underlying_price = u_price

        if expiration:
            expirations.add(expiration)

        # Use OI as weight, default to 1 if missing
        oi = oi if oi else 1
        gamma = gamma if gamma else 0
        delta = delta if delta else 0

        # Weight gamma by open interest
        weighted_gamma = gamma * oi

        total_gamma += abs(weighted_gamma)
        total_oi += oi

        if option_type == "call":
            call_gamma += weighted_gamma
            call_oi += oi
            call_count += 1
        elif option_type == "put":
            put_gamma += abs(weighted_gamma)  # Put gamma is positive in our calc
            put_oi += oi
            put_count += 1

        # Track max gamma strike
        if abs(weighted_gamma) > max_gamma:
            max_gamma = abs(weighted_gamma)
            max_gamma_strike = strike

        # Find zero-gamma strike (near delta-neutral)
        if 0.4 <= abs(delta) <= 0.6:
            zero_gamma_weight += oi
            weighted_zero_gamma_strike += strike * oi

    # Normalize by OI
    if total_oi > 0:
        avg_total_gamma = total_gamma / total_oi
        avg_call_gamma = call_gamma / call_oi if call_oi > 0 else 0
        avg_put_gamma = put_gamma / put_oi if put_oi > 0 else 0
        net_gamma = avg_call_gamma - avg_put_gamma
    else:
        avg_total_gamma = 0
        avg_call_gamma = 0
        avg_put_gamma = 0
        net_gamma = 0

    # Zero-gamma level
    zero_gamma_level = None
    if zero_gamma_weight > 0:
        zero_gamma_level = weighted_zero_gamma_strike / zero_gamma_weight

    # Classify regime
    if len(rows) < 100:
        regime = "NEUTRAL"
    elif net_gamma > 0:
        regime = "POSITIVE_GAMMA"
    elif net_gamma < 0:
        regime = "NEGATIVE_GAMMA"
    else:
        regime = "NEUTRAL"

    # Data quality score
    quality_score = 1.0
    if len(rows) < 100:
        quality_score *= 0.5
    elif len(rows) < 500:
        quality_score *= 0.75
    if total_oi < 1000:
        quality_score *= 0.7
    elif total_oi < 5000:
        quality_score *= 0.85

    # OI concentration (top 10% of strikes)
    call_oi_concentration = call_oi / total_oi if total_oi > 0 else 0
    put_oi_concentration = put_oi / total_oi if total_oi > 0 else 0

    return {
        "symbol": symbol,
        "trading_date": trading_date,
        "underlying_price": underlying_price,
        "total_gex": round(avg_total_gamma, 8),
        "net_call_gex": round(avg_call_gamma, 8),
        "net_put_gex": round(avg_put_gamma, 8),
        "zero_gamma_level": zero_gamma_level,
        "max_gamma_strike": max_gamma_strike,
        "regime": regime,
        "call_oi_concentration": round(call_oi_concentration, 4),
        "put_oi_concentration": round(put_oi_concentration, 4),
        "contracts_count": len(rows),
        "expirations_count": len(expirations),
        "data_quality_score": round(quality_score, 3),
        "calculation_method": "weighted_oi",
        "calculation_timestamp": datetime.now().isoformat(),
        "asset_class": ASSET_CLASS_MAP.get(symbol, "equity"),
    }


def save_metrics(conn: sqlite3.Connection, metrics: Dict) -> bool:
    """Save metrics to options_daily_summary table."""
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT OR REPLACE INTO options_daily_summary (
                symbol, trading_date, underlying_price, total_gex, net_call_gex,
                net_put_gex, zero_gamma_level, max_gamma_strike, regime,
                call_oi_concentration, put_oi_concentration, contracts_count,
                expirations_count, data_quality_score, calculation_method,
                calculation_timestamp, asset_class
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                metrics["symbol"],
                metrics["trading_date"],
                metrics["underlying_price"],
                metrics["total_gex"],
                metrics["net_call_gex"],
                metrics["net_put_gex"],
                metrics["zero_gamma_level"],
                metrics["max_gamma_strike"],
                metrics["regime"],
                metrics["call_oi_concentration"],
                metrics["put_oi_concentration"],
                metrics["contracts_count"],
                metrics["expirations_count"],
                metrics["data_quality_score"],
                metrics["calculation_method"],
                metrics["calculation_timestamp"],
                metrics["asset_class"],
            ),
        )
        return True
    except Exception as e:
        print(f"  Error saving {metrics['symbol']} {metrics['trading_date']}: {e}")
        return False


def process_symbol(conn: sqlite3.Connection, symbol: str) -> Tuple[int, int]:
    """Process all dates for a symbol. Returns (success_count, skip_count)."""
    trading_dates = get_trading_dates_for_symbol(conn, symbol)
    processed_dates = get_processed_dates(conn, symbol)

    # Filter to unprocessed dates
    dates_to_process = [d for d in trading_dates if d not in processed_dates]

    if not dates_to_process:
        return 0, len(trading_dates)

    success_count = 0
    batch_data = []

    for i, trading_date in enumerate(dates_to_process, 1):
        metrics = calculate_daily_gex(conn, symbol, trading_date)
        if metrics:
            batch_data.append(metrics)
            success_count += 1

        # Batch insert every 50 records for efficiency
        if len(batch_data) >= 50:
            for m in batch_data:
                save_metrics(conn, m)
            conn.commit()
            batch_data = []
            print(f"    {symbol}: {i}/{len(dates_to_process)} dates processed", flush=True)

    # Save remaining
    for m in batch_data:
        save_metrics(conn, m)
    conn.commit()

    return success_count, len(processed_dates)


def main():
    """Main entry point."""
    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH, timeout=30)

    try:
        symbols = get_symbols(conn)
        print("=" * 70)
        print("BATCH GEX CALCULATION")
        print("=" * 70)
        print(f"Database: {DB_PATH}")
        print(f"Symbols to process: {len(symbols)}")
        print("=" * 70)

        total_new = 0
        total_skipped = 0

        for i, symbol in enumerate(symbols, 1):
            print(f"\n[{i}/{len(symbols)}] Processing {symbol}...")
            new_count, skip_count = process_symbol(conn, symbol)
            total_new += new_count
            total_skipped += skip_count

            if new_count > 0:
                print(f"  ✓ {symbol}: {new_count} new days calculated")
            else:
                print(f"  ○ {symbol}: Already up to date ({skip_count} days)")

        # Final summary
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"New calculations: {total_new:,}")
        print(f"Already processed: {total_skipped:,}")

        # Show regime distribution
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                asset_class,
                COUNT(*) as days,
                COUNT(CASE WHEN regime = 'POSITIVE_GAMMA' THEN 1 END) as positive,
                COUNT(CASE WHEN regime = 'NEGATIVE_GAMMA' THEN 1 END) as negative,
                COUNT(CASE WHEN regime = 'NEUTRAL' THEN 1 END) as neutral
            FROM options_daily_summary
            GROUP BY asset_class
        """
        )

        print("\nRegime Distribution by Asset Class:")
        print(f"{'Asset Class':<15} {'Days':>8} {'Positive':>10} {'Negative':>10} {'Neutral':>10}")
        print("-" * 55)
        for row in cursor.fetchall():
            asset_class, days, pos, neg, neu = row
            print(f"{asset_class or 'unknown':<15} {days:>8} {pos:>10} {neg:>10} {neu:>10}")

    finally:
        conn.close()

    print("\n✓ Batch GEX calculation complete!")


if __name__ == "__main__":
    main()
