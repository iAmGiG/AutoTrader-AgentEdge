"""
Parallel GEX Calculator - Big Data Approach

Uses:
- Pandas vectorized operations (not row-by-row loops)
- Multiprocessing Pool for parallel symbol processing
- Bulk inserts with executemany + chunking
- SQLite WAL mode for concurrent writes
- Memory-mapped buffers for large datasets

Expected performance: 50M records in ~10-15 minutes vs hours with naive approach.
"""

import multiprocessing as mp
import sqlite3
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pandas as pd

DB_PATH = Path(".cache/gex_research.db")
CHUNK_SIZE = 100_000  # Records per chunk for memory efficiency
BATCH_INSERT_SIZE = 1000  # Rows per INSERT batch

# Asset class mapping
ASSET_CLASS_MAP = {
    "SPY": "equity",
    "QQQ": "equity",
    "IWM": "equity",
    "DIA": "equity",
    "VTI": "equity",
    "AAPL": "equity",
    "MSFT": "equity",
    "TSLA": "equity",
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
    "UVXY": "volatility",
    "VXX": "volatility",
    "GLD": "commodity",
    "SLV": "commodity",
    "TLT": "bond",
    "IEF": "bond",
    "LQD": "bond",
    "IYR": "real_estate",
}


def setup_database():
    """Configure SQLite for optimal write performance."""
    conn = sqlite3.connect(DB_PATH, timeout=60)

    # WAL mode for concurrent reads/writes
    conn.execute("PRAGMA journal_mode=WAL")
    # Larger page cache (100MB)
    conn.execute("PRAGMA cache_size=-102400")
    # Synchronous OFF for bulk inserts (faster, slightly less safe)
    conn.execute("PRAGMA synchronous=OFF")
    # Memory-mapped I/O (1GB)
    conn.execute("PRAGMA mmap_size=1073741824")
    # Temp store in memory
    conn.execute("PRAGMA temp_store=MEMORY")

    conn.close()


def calculate_gex_vectorized(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate GEX metrics using vectorized pandas operations.

    This processes an entire symbol's data at once, grouped by trading_date.
    Much faster than row-by-row iteration.
    """
    if df.empty:
        return pd.DataFrame()

    # Fill NaN values
    df["gamma"] = df["gamma"].fillna(0)
    df["delta"] = df["delta"].fillna(0)
    df["open_interest"] = df["open_interest"].fillna(1)

    # Calculate weighted gamma per row
    df["weighted_gamma"] = df["gamma"] * df["open_interest"]
    df["abs_weighted_gamma"] = df["weighted_gamma"].abs()

    # Flag for call/put
    df["is_call"] = df["option_type"] == "call"
    df["is_put"] = df["option_type"] == "put"

    # Flag for near-delta-neutral (for zero gamma calculation)
    df["near_neutral"] = (df["delta"].abs() >= 0.4) & (df["delta"].abs() <= 0.6)

    # Group by trading_date and aggregate
    agg = (
        df.groupby("trading_date")
        .agg(
            {
                "symbol": "first",
                "underlying_price": "first",
                "abs_weighted_gamma": "sum",
                "open_interest": "sum",
                "strike": "count",  # contract count
                "expiration": "nunique",  # unique expirations
            }
        )
        .rename(
            columns={
                "abs_weighted_gamma": "total_weighted_gamma",
                "open_interest": "total_oi",
                "strike": "contracts_count",
                "expiration": "expirations_count",
            }
        )
    )

    # Call aggregations
    call_df = (
        df[df["is_call"]]
        .groupby("trading_date")
        .agg(
            {
                "weighted_gamma": "sum",
                "open_interest": "sum",
            }
        )
        .rename(
            columns={
                "weighted_gamma": "call_weighted_gamma",
                "open_interest": "call_oi",
            }
        )
    )

    # Put aggregations
    put_df = (
        df[df["is_put"]]
        .groupby("trading_date")
        .agg(
            {
                "weighted_gamma": lambda x: x.abs().sum(),
                "open_interest": "sum",
            }
        )
        .rename(
            columns={
                "weighted_gamma": "put_weighted_gamma",
                "open_interest": "put_oi",
            }
        )
    )

    # Zero gamma strike calculation (weighted average of near-neutral strikes)
    neutral_df = (
        df[df["near_neutral"]]
        .groupby("trading_date")
        .apply(
            lambda x: (
                np.average(x["strike"], weights=x["open_interest"])
                if len(x) > 0 and x["open_interest"].sum() > 0
                else np.nan
            )
        )
        .rename("zero_gamma_level")
    )

    # Max gamma strike
    max_gamma_df = (
        df.loc[df.groupby("trading_date")["abs_weighted_gamma"].idxmax()][
            ["trading_date", "strike"]
        ]
        .set_index("trading_date")
        .rename(columns={"strike": "max_gamma_strike"})
    )

    # Merge all aggregations
    result = agg.join(call_df, how="left").join(put_df, how="left")
    result = result.join(neutral_df, how="left").join(max_gamma_df, how="left")

    # Fill NaN for missing call/put data
    result["call_weighted_gamma"] = result["call_weighted_gamma"].fillna(0)
    result["put_weighted_gamma"] = result["put_weighted_gamma"].fillna(0)
    result["call_oi"] = result["call_oi"].fillna(0)
    result["put_oi"] = result["put_oi"].fillna(0)

    # Calculate normalized metrics
    result["total_gex"] = result["total_weighted_gamma"] / result["total_oi"]
    result["net_call_gex"] = result["call_weighted_gamma"] / result["call_oi"].replace(0, 1)
    result["net_put_gex"] = result["put_weighted_gamma"] / result["put_oi"].replace(0, 1)
    result["net_gamma"] = result["net_call_gex"] - result["net_put_gex"]

    # OI concentration
    result["call_oi_concentration"] = result["call_oi"] / result["total_oi"]
    result["put_oi_concentration"] = result["put_oi"] / result["total_oi"]

    # Regime classification (vectorized)
    result["regime"] = np.where(
        result["contracts_count"] < 100,
        "NEUTRAL",
        np.where(
            result["net_gamma"] > 0,
            "POSITIVE_GAMMA",
            np.where(result["net_gamma"] < 0, "NEGATIVE_GAMMA", "NEUTRAL"),
        ),
    )

    # Data quality score (vectorized)
    quality = np.ones(len(result))
    quality = np.where(
        result["contracts_count"] < 100,
        quality * 0.5,
        np.where(result["contracts_count"] < 500, quality * 0.75, quality),
    )
    quality = np.where(
        result["total_oi"] < 1000,
        quality * 0.7,
        np.where(result["total_oi"] < 5000, quality * 0.85, quality),
    )
    result["data_quality_score"] = quality

    # Metadata
    result["calculation_method"] = "vectorized_pandas"
    result["calculation_timestamp"] = datetime.now().isoformat()
    result["asset_class"] = ASSET_CLASS_MAP.get(result["symbol"].iloc[0], "equity")

    # Reset index to get trading_date as column
    result = result.reset_index()

    # Select and round final columns
    output_cols = [
        "symbol",
        "trading_date",
        "underlying_price",
        "total_gex",
        "net_call_gex",
        "net_put_gex",
        "zero_gamma_level",
        "max_gamma_strike",
        "regime",
        "call_oi_concentration",
        "put_oi_concentration",
        "contracts_count",
        "expirations_count",
        "data_quality_score",
        "calculation_method",
        "calculation_timestamp",
        "asset_class",
    ]

    result = result[output_cols]

    # Round numeric columns
    for col in [
        "total_gex",
        "net_call_gex",
        "net_put_gex",
        "call_oi_concentration",
        "put_oi_concentration",
        "data_quality_score",
    ]:
        result[col] = result[col].round(8)

    return result


def process_symbol(symbol: str, db_path: Path) -> Tuple[str, int, int]:
    """
    Process a single symbol - designed to run in parallel.

    Returns: (symbol, new_records, skipped_records)
    """
    conn = sqlite3.connect(db_path, timeout=120)

    try:
        # Get already processed dates
        processed_dates = set(
            pd.read_sql_query(
                "SELECT trading_date FROM options_daily_summary WHERE symbol = ?",
                conn,
                params=(symbol,),
            )["trading_date"].tolist()
        )

        # Read symbol data in chunks for memory efficiency
        query = """
            SELECT symbol, trading_date, strike, option_type, expiration,
                   gamma, delta, underlying_price, open_interest
            FROM options_chains
            WHERE symbol = ?
            ORDER BY trading_date, strike
        """

        # Use chunked reading for large symbols
        chunks = pd.read_sql_query(query, conn, params=(symbol,), chunksize=CHUNK_SIZE)

        all_results = []
        for chunk in chunks:
            if chunk.empty:
                continue

            # Filter out already processed dates
            chunk = chunk[~chunk["trading_date"].isin(processed_dates)]
            if chunk.empty:
                continue

            # Calculate GEX metrics vectorized
            result = calculate_gex_vectorized(chunk)
            if not result.empty:
                all_results.append(result)

        if not all_results:
            return symbol, 0, len(processed_dates)

        # Combine all results
        final_df = pd.concat(all_results, ignore_index=True)

        # Bulk insert using pandas to_sql with 'replace' for upsert behavior
        # Use executemany for better control
        insert_sql = """
            INSERT OR REPLACE INTO options_daily_summary (
                symbol, trading_date, underlying_price, total_gex, net_call_gex,
                net_put_gex, zero_gamma_level, max_gamma_strike, regime,
                call_oi_concentration, put_oi_concentration, contracts_count,
                expirations_count, data_quality_score, calculation_method,
                calculation_timestamp, asset_class
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        # Convert to list of tuples for executemany
        records = final_df.values.tolist()

        # Batch insert
        cursor = conn.cursor()
        for i in range(0, len(records), BATCH_INSERT_SIZE):
            batch = records[i : i + BATCH_INSERT_SIZE]
            cursor.executemany(insert_sql, batch)

        conn.commit()

        return symbol, len(final_df), len(processed_dates)

    except Exception as e:
        print(f"Error processing {symbol}: {e}")
        return symbol, 0, 0
    finally:
        conn.close()


def get_symbols_to_process(db_path: Path) -> List[Tuple[str, int]]:
    """Get list of symbols with their expected date counts."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT symbol, COUNT(DISTINCT trading_date) as days
        FROM options_chains
        GROUP BY symbol
        ORDER BY days DESC
    """
    )

    symbols = cursor.fetchall()
    conn.close()

    return symbols


def main():
    """Main entry point with parallel processing."""
    print("=" * 70)
    print("PARALLEL GEX CALCULATOR - Big Data Approach")
    print("=" * 70)

    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        return

    # Setup database for optimal performance
    print("Configuring database for bulk operations...")
    setup_database()

    # Get symbols to process
    symbols_info = get_symbols_to_process(DB_PATH)
    print(f"Symbols to process: {len(symbols_info)}")

    total_expected_days = sum(days for _, days in symbols_info)
    print(f"Total expected trading days: {total_expected_days:,}")

    # Determine worker count (leave 1 CPU free)
    num_workers = max(1, mp.cpu_count() - 1)
    print(f"Using {num_workers} parallel workers")
    print("=" * 70)

    # Process symbols in parallel
    symbols = [s for s, _ in symbols_info]

    # Use partial to bind db_path
    process_func = partial(process_symbol, db_path=DB_PATH)

    start_time = datetime.now()
    results = []

    with mp.Pool(num_workers) as pool:
        for i, result in enumerate(pool.imap_unordered(process_func, symbols), 1):
            symbol, new_count, skip_count = result
            results.append(result)

            status = f"[{i}/{len(symbols)}] {symbol}: "
            if new_count > 0:
                status += f"{new_count} new"
            else:
                status += f"skipped ({skip_count} existing)"
            print(status, flush=True)

    elapsed = datetime.now() - start_time

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    total_new = sum(r[1] for r in results)
    total_skipped = sum(r[2] for r in results)

    print(f"New records calculated: {total_new:,}")
    print(f"Existing records skipped: {total_skipped:,}")
    print(f"Time elapsed: {elapsed}")
    print(f"Records per second: {total_new / elapsed.total_seconds():.1f}")

    # Verify final state
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT asset_class, COUNT(*) as days,
            SUM(CASE WHEN regime = 'POSITIVE_GAMMA' THEN 1 ELSE 0 END) as pos,
            SUM(CASE WHEN regime = 'NEGATIVE_GAMMA' THEN 1 ELSE 0 END) as neg
        FROM options_daily_summary
        GROUP BY asset_class
    """
    )

    print("\nRegime Distribution by Asset Class:")
    print(f"{'Asset Class':<15} {'Days':>8} {'Positive':>10} {'Negative':>10}")
    print("-" * 45)
    for row in cursor.fetchall():
        print(f"{row[0] or 'unknown':<15} {row[1]:>8} {row[2]:>10} {row[3]:>10}")

    conn.close()

    print("\n[DONE] Parallel GEX calculation complete!")


if __name__ == "__main__":
    # Required for Windows multiprocessing
    mp.freeze_support()
    main()
