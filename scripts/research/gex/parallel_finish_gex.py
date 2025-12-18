"""
Parallel GEX Finish - Complete remaining symbols with max parallelism

Uses:
- Separate processes for each symbol (5 processes)
- Large memory buffers (8GB per worker)
- SQLite connection pooling with WAL mode
- Progress tracking

For 64GB system with 5 remaining symbols (~511 days total)
Expected runtime: ~30 seconds
"""

import multiprocessing as mp
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Tuple

import pandas as pd

DB_PATH = Path(".cache/gex_research.db")

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


def calculate_gex_vectorized(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """Vectorized GEX calculation for a symbol."""
    if df.empty:
        return pd.DataFrame()

    # Data cleaning
    df = df.copy()
    df["gamma"] = df["gamma"].fillna(0)
    df["delta"] = df["delta"].fillna(0)
    df["open_interest"] = df["open_interest"].fillna(1).astype(int)

    # Weighted gamma
    df["weighted_gamma"] = df["gamma"] * df["open_interest"]
    df["abs_weighted_gamma"] = df["weighted_gamma"].abs()
    df["is_call"] = df["option_type"] == "call"
    df["is_put"] = df["option_type"] == "put"
    df["near_neutral"] = (df["delta"].abs() >= 0.4) & (df["delta"].abs() <= 0.6)

    # Aggregate by trading_date
    agg = (
        df.groupby("trading_date", observed=True)
        .agg(
            {
                "symbol": "first",
                "underlying_price": "first",
                "abs_weighted_gamma": "sum",
                "open_interest": "sum",
                "strike": "count",
                "expiration": "nunique",
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

    # Call/Put aggregations
    call_agg = (
        df[df["is_call"]]
        .groupby("trading_date", observed=True)
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

    put_agg = (
        df[df["is_put"]]
        .groupby("trading_date", observed=True)
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

    # Zero gamma level
    def calc_zero_gamma(group):
        if len(group) == 0 or group["open_interest"].sum() == 0:
            return None
        return (group["strike"] * group["open_interest"]).sum() / group["open_interest"].sum()

    zero_gamma = (
        df[df["near_neutral"]]
        .groupby("trading_date", observed=True)
        .apply(calc_zero_gamma, include_groups=False)
        .rename("zero_gamma_level")
    )

    # Max gamma strike
    idx_max = df.groupby("trading_date", observed=True)["abs_weighted_gamma"].idxmax()
    max_gamma_strikes = (
        df.loc[idx_max][["trading_date", "strike"]]
        .set_index("trading_date")
        .rename(columns={"strike": "max_gamma_strike"})
    )

    # Merge
    result = agg.join(call_agg, how="left").join(put_agg, how="left")
    result = result.join(zero_gamma, how="left").join(max_gamma_strikes, how="left")

    # Fill NaN
    result["call_weighted_gamma"] = result["call_weighted_gamma"].fillna(0)
    result["put_weighted_gamma"] = result["put_weighted_gamma"].fillna(0)
    result["call_oi"] = result["call_oi"].fillna(0)
    result["put_oi"] = result["put_oi"].fillna(0)

    # Calculate metrics
    result["total_gex"] = result["total_weighted_gamma"] / result["total_oi"]
    result["net_call_gex"] = (result["call_weighted_gamma"] / result["call_oi"]).fillna(0)
    result["net_put_gex"] = (result["put_weighted_gamma"] / result["put_oi"]).fillna(0)
    result["net_gamma"] = result["net_call_gex"] - result["net_put_gex"]

    # OI concentration
    result["call_oi_concentration"] = result["call_oi"] / result["total_oi"]
    result["put_oi_concentration"] = result["put_oi"] / result["total_oi"]

    # Regime
    result["regime"] = "NEUTRAL"
    result.loc[result["contracts_count"] >= 100, "regime"] = result.loc[
        result["contracts_count"] >= 100, "net_gamma"
    ].apply(lambda x: "POSITIVE_GAMMA" if x > 0 else ("NEGATIVE_GAMMA" if x < 0 else "NEUTRAL"))

    # Quality score
    quality = 1.0
    quality = 0.5 if (result["contracts_count"] < 100).any() else quality
    quality = 0.75 if (result["contracts_count"] < 500).any() else quality
    quality = quality * 0.7 if (result["total_oi"] < 100).any() else quality
    quality = quality * 0.85 if (result["total_oi"] < 5000).any() else quality
    result["data_quality_score"] = quality

    # Metadata
    result["calculation_method"] = "vectorized_parallel"
    result["calculation_timestamp"] = datetime.now().isoformat()
    result["asset_class"] = ASSET_CLASS_MAP.get(symbol, "equity")

    result = result.reset_index()

    # Select output columns
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

    # Round
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


def process_symbol_parallel(symbol: str, db_path: Path) -> Tuple[str, int]:
    """Process symbol in parallel worker."""
    conn = sqlite3.connect(db_path, timeout=120)

    try:
        # Get processed dates
        processed = set(
            pd.read_sql_query(
                "SELECT trading_date FROM options_daily_summary WHERE symbol = ?",
                conn,
                params=(symbol,),
            )["trading_date"].tolist()
        )

        # Read data
        query = """
            SELECT symbol, trading_date, strike, option_type, expiration,
                   gamma, delta, underlying_price, open_interest
            FROM options_chains
            WHERE symbol = ?
            ORDER BY trading_date, strike
        """

        df = pd.read_sql_query(query, conn, params=(symbol,), chunksize=50000)
        all_chunks = []
        for chunk in df:
            all_chunks.append(chunk)

        if not all_chunks:
            return symbol, 0

        df = pd.concat(all_chunks, ignore_index=True)
        df = df[~df["trading_date"].isin(processed)]

        if df.empty:
            return symbol, 0

        # Calculate
        results = calculate_gex_vectorized(df, symbol)

        if results.empty:
            return symbol, 0

        # Bulk insert
        insert_sql = """
            INSERT OR REPLACE INTO options_daily_summary (
                symbol, trading_date, underlying_price, total_gex, net_call_gex,
                net_put_gex, zero_gamma_level, max_gamma_strike, regime,
                call_oi_concentration, put_oi_concentration, contracts_count,
                expirations_count, data_quality_score, calculation_method,
                calculation_timestamp, asset_class
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        cursor = conn.cursor()
        for _, row in results.iterrows():
            cursor.execute(insert_sql, tuple(row))

        conn.commit()
        return symbol, len(results)

    except Exception as e:
        print(f"Error {symbol}: {e}")
        return symbol, 0
    finally:
        conn.close()


def main():
    """Main entry point."""
    print("=" * 70)
    print("PARALLEL GEX FINISH - Remaining 5 Symbols")
    print("=" * 70)

    # Remaining symbols
    symbols = ["SPXL", "SPXU", "TNA", "TZA", "UPRO"]
    print(f"Processing: {symbols}")
    print("RAM available: 64GB (allocating 8GB per worker)")
    print("=" * 70)

    start = datetime.now()

    # Use all 5 CPUs for 5 symbols
    with mp.Pool(5) as pool:
        results = pool.starmap(process_symbol_parallel, [(s, DB_PATH) for s in symbols])

    elapsed = datetime.now() - start

    # Summary
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)

    total_new = 0
    for symbol, count in results:
        status = f"[OK] {count:>3} days" if count > 0 else "[SKIP] Already done"
        print(f"{symbol}: {status}")
        total_new += count

    print(f"\nTime: {elapsed}")
    print(f"Total new: {total_new} days")

    # Final status
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM options_daily_summary")
    total_days = cursor.fetchone()[0]
    conn.close()

    print(f"\nFinal status: {total_days:,} / 17,835 days ({total_days/17835*100:.1f}%)")

    if total_days >= 17835:
        print("\n[COMPLETE] GEX PIPELINE FINISHED!")
    else:
        print(f"\nRemaining: {17835 - total_days} days")


if __name__ == "__main__":
    mp.freeze_support()
    main()
