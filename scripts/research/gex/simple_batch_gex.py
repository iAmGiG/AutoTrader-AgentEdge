"""Simple batch GEX calculator - processes one symbol at a time."""

import sqlite3
from datetime import datetime
from pathlib import Path

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


def process_date(cursor, symbol, trading_date):
    """Process a single date."""
    cursor.execute(
        """
        SELECT option_type, strike, gamma, delta, underlying_price, open_interest, expiration
        FROM options_chains
        WHERE symbol = ? AND trading_date = ?
    """,
        (symbol, trading_date),
    )

    rows = cursor.fetchall()
    if not rows:
        return None

    total_gamma = call_gamma = put_gamma = 0.0
    total_oi = call_oi = put_oi = 0
    call_count = put_count = 0
    max_gamma = max_gamma_strike = 0
    zero_gamma_weight = weighted_zero_gamma_strike = 0.0
    expirations = set()
    underlying_price = None

    for row in rows:
        opt_type, strike, gamma, delta, u_price, oi, exp = row

        if underlying_price is None and u_price:
            underlying_price = u_price
        if exp:
            expirations.add(exp)

        oi = oi or 1
        gamma = gamma or 0
        delta = delta or 0

        weighted_gamma = gamma * oi
        total_gamma += abs(weighted_gamma)
        total_oi += oi

        if opt_type == "call":
            call_gamma += weighted_gamma
            call_oi += oi
            call_count += 1
        elif opt_type == "put":
            put_gamma += abs(weighted_gamma)
            put_oi += oi
            put_count += 1

        if abs(weighted_gamma) > max_gamma:
            max_gamma = abs(weighted_gamma)
            max_gamma_strike = strike

        if 0.4 <= abs(delta) <= 0.6:
            zero_gamma_weight += oi
            weighted_zero_gamma_strike += strike * oi

    if total_oi == 0:
        return None

    avg_total = total_gamma / total_oi
    avg_call = call_gamma / call_oi if call_oi > 0 else 0
    avg_put = put_gamma / put_oi if put_oi > 0 else 0
    net_gamma = avg_call - avg_put

    regime = (
        "POSITIVE_GAMMA" if net_gamma > 0 else ("NEGATIVE_GAMMA" if net_gamma < 0 else "NEUTRAL")
    )
    if len(rows) < 100:
        regime = "NEUTRAL"

    quality = 1.0
    if len(rows) < 100:
        quality *= 0.5
    elif len(rows) < 500:
        quality *= 0.75
    if total_oi < 1000:
        quality *= 0.7
    elif total_oi < 5000:
        quality *= 0.85

    zero_level = weighted_zero_gamma_strike / zero_gamma_weight if zero_gamma_weight > 0 else None

    return {
        "symbol": symbol,
        "trading_date": trading_date,
        "underlying_price": underlying_price,
        "total_gex": round(avg_total, 8),
        "net_call_gex": round(avg_call, 8),
        "net_put_gex": round(avg_put, 8),
        "zero_gamma_level": zero_level,
        "max_gamma_strike": max_gamma_strike,
        "regime": regime,
        "call_oi_concentration": round(call_oi / total_oi, 4),
        "put_oi_concentration": round(put_oi / total_oi, 4),
        "contracts_count": len(rows),
        "expirations_count": len(expirations),
        "data_quality_score": round(quality, 3),
        "calculation_method": "weighted_oi",
        "calculation_timestamp": datetime.now().isoformat(),
        "asset_class": ASSET_CLASS_MAP.get(symbol, "equity"),
    }


def main():
    conn = sqlite3.connect(DB_PATH, timeout=60)
    cursor = conn.cursor()

    # Get symbols
    cursor.execute("SELECT DISTINCT symbol FROM options_chains ORDER BY symbol")
    symbols = [r[0] for r in cursor.fetchall()]
    print(f"Processing {len(symbols)} symbols...")

    for i, symbol in enumerate(symbols, 1):
        # Get dates for symbol
        cursor.execute(
            "SELECT DISTINCT trading_date FROM options_chains WHERE symbol = ? ORDER BY trading_date",
            (symbol,),
        )
        all_dates = [r[0] for r in cursor.fetchall()]

        # Get processed dates
        cursor.execute("SELECT trading_date FROM options_daily_summary WHERE symbol = ?", (symbol,))
        processed = {r[0] for r in cursor.fetchall()}

        to_process = [d for d in all_dates if d not in processed]

        if not to_process:
            print(f"[{i}/{len(symbols)}] {symbol}: already complete ({len(processed)} days)")
            continue

        print(f"[{i}/{len(symbols)}] {symbol}: processing {len(to_process)} dates...", flush=True)

        for j, date in enumerate(to_process, 1):
            metrics = process_date(cursor, symbol, date)
            if metrics:
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

            if j % 50 == 0:
                conn.commit()
                print(f"    {symbol}: {j}/{len(to_process)}", flush=True)

        conn.commit()
        print(f"  [OK] {symbol}: {len(to_process)} new days")

    # Summary
    cursor.execute(
        """
        SELECT asset_class, COUNT(*) as days,
            SUM(CASE WHEN regime = 'POSITIVE_GAMMA' THEN 1 ELSE 0 END) as pos,
            SUM(CASE WHEN regime = 'NEGATIVE_GAMMA' THEN 1 ELSE 0 END) as neg
        FROM options_daily_summary GROUP BY asset_class
    """
    )

    print("\n=== SUMMARY ===")
    for row in cursor.fetchall():
        print(f"{row[0]}: {row[1]} days (Pos: {row[2]}, Neg: {row[3]})")

    conn.close()
    print("\n[DONE] Batch complete!")


if __name__ == "__main__":
    main()
