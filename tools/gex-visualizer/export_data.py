#!/usr/bin/env python3
"""
Export GEX research data from SQLite to JSON for the visualizer.

Usage:
    python export_data.py              # Export all symbols
    python export_data.py SPY QQQ      # Export specific symbols
"""

import json
import sqlite3
import sys
from pathlib import Path

# Database path (relative to project root)
DB_PATH = Path(__file__).parent.parent.parent / ".cache" / "gex_research.db"
OUTPUT_DIR = Path(__file__).parent / "data"


def get_symbols(conn, filter_symbols=None):
    """Get list of symbols to export."""
    cursor = conn.cursor()
    if filter_symbols:
        placeholders = ",".join("?" * len(filter_symbols))
        cursor.execute(
            f"SELECT DISTINCT symbol, asset_class FROM options_daily_summary WHERE symbol IN ({placeholders}) ORDER BY symbol",
            filter_symbols,
        )
    else:
        cursor.execute(
            "SELECT DISTINCT symbol, asset_class FROM options_daily_summary ORDER BY asset_class, symbol"
        )
    return cursor.fetchall()


def export_symbol(conn, symbol):
    """Export data for a single symbol."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            trading_date,
            underlying_price,
            total_gex,
            net_call_gex,
            net_put_gex,
            zero_gamma_level,
            max_gamma_strike,
            regime,
            call_oi_concentration,
            put_oi_concentration,
            contracts_count,
            data_quality_score,
            asset_class
        FROM options_daily_summary
        WHERE symbol = ? AND underlying_price IS NOT NULL
        ORDER BY trading_date ASC
    """,
        (symbol,),
    )

    rows = cursor.fetchall()
    if not rows:
        return None

    data = {
        "symbol": symbol,
        "asset_class": rows[0][12],
        "date_range": {"start": rows[0][0], "end": rows[-1][0]},
        "count": len(rows),
        "timeline": [],
    }

    for row in rows:
        data["timeline"].append(
            {
                "date": row[0],
                "price": round(row[1], 2) if row[1] else None,
                "gex": round(row[2] * 1000, 2) if row[2] else None,  # Convert to millions
                "call_gex": round(row[3] * 1000, 2) if row[3] else None,
                "put_gex": round(row[4] * 1000, 2) if row[4] else None,
                "zero_gamma": round(row[5], 2) if row[5] else None,
                "max_gamma": round(row[6], 2) if row[6] else None,
                "regime": row[7],
                "call_oi": round(row[8], 4) if row[8] else None,
                "put_oi": round(row[9], 4) if row[9] else None,
                "contracts": row[10],
                "quality": round(row[11], 2) if row[11] else None,
            }
        )

    return data


def export_index(symbols_data):
    """Create index file listing all available symbols."""
    index = {"symbols": [], "asset_classes": {}}

    for symbol, asset_class, count, date_range in symbols_data:
        index["symbols"].append(
            {
                "symbol": symbol,
                "asset_class": asset_class,
                "count": count,
                "date_range": date_range,
            }
        )

        if asset_class not in index["asset_classes"]:
            index["asset_classes"][asset_class] = []
        index["asset_classes"][asset_class].append(symbol)

    return index


def main():
    # Parse command line args
    filter_symbols = sys.argv[1:] if len(sys.argv) > 1 else None

    # Check database exists
    if not DB_PATH.exists():
        print(f"Error: Database not found at {DB_PATH}")
        sys.exit(1)

    # Create output directory
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Connect to database
    conn = sqlite3.connect(str(DB_PATH))
    symbols = get_symbols(conn, filter_symbols)

    print(f"Exporting {len(symbols)} symbols to {OUTPUT_DIR}/")

    symbols_data = []
    for symbol, asset_class in symbols:
        data = export_symbol(conn, symbol)
        if data:
            # Write symbol file
            output_file = OUTPUT_DIR / f"{symbol.lower()}.json"
            with open(output_file, "w") as f:
                json.dump(data, f, indent=2)
            print(f"  {symbol}: {data['count']} days -> {output_file.name}")
            symbols_data.append((symbol, asset_class, data["count"], data["date_range"]))
        else:
            print(f"  {symbol}: No data (skipped)")

    # Write index file
    index = export_index(symbols_data)
    index_file = OUTPUT_DIR / "index.json"
    with open(index_file, "w") as f:
        json.dump(index, f, indent=2)
    print(f"\nIndex: {len(index['symbols'])} symbols -> {index_file.name}")

    conn.close()
    print("\nDone!")


if __name__ == "__main__":
    main()
