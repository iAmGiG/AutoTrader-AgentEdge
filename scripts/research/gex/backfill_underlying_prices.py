"""
Backfill underlying prices for GEX database.

This script fetches historical daily prices for symbols in the options_chains table
and updates the underlying_price column. Uses Alpha Vantage or Finnhub APIs.
"""

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import Dict, List

import requests

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.date_utils import get_datetime_from_timestamp, parse_date_string

# Rate limiting
ALPHA_VANTAGE_RATE_LIMIT = 75  # requests per minute (freemium)
FINNHUB_RATE_LIMIT = 60  # requests per minute (free)


class PriceBackfiller:
    """Backfill underlying prices using Alpha Vantage or Finnhub."""

    def __init__(self, db_path: Path, api_key: str, provider: str = "alpha_vantage"):
        """Initialize backfiller."""
        self.db_path = db_path
        self.api_key = api_key
        self.provider = provider
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self.request_count = 0
        self.last_request_time = time.time()

    def _rate_limit(self):
        """Enforce rate limiting."""
        rate_limit = (
            ALPHA_VANTAGE_RATE_LIMIT if self.provider == "alpha_vantage" else FINNHUB_RATE_LIMIT
        )

        self.request_count += 1
        elapsed = time.time() - self.last_request_time

        if elapsed < 60:  # Within 1 minute window
            if self.request_count >= rate_limit:
                sleep_time = 60 - elapsed + 1
                print(
                    f"  Rate limit reached ({self.request_count} requests). "
                    f"Sleeping {sleep_time:.1f}s..."
                )
                time.sleep(sleep_time)
                self.request_count = 0
                self.last_request_time = time.time()
        else:
            # Reset window
            self.request_count = 1
            self.last_request_time = time.time()

    def fetch_prices_alpha_vantage(
        self, symbol: str, start_date: str, end_date: str
    ) -> Dict[str, float]:
        """Fetch daily prices from Alpha Vantage TIME_SERIES_DAILY."""
        self._rate_limit()

        url = "https://www.alphavantage.co/query"  # Using adjusted prices is critical
        params = {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": symbol,
            "outputsize": "full",
            "apikey": self.api_key,
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            if "Time Series (Daily)" not in data:
                print(f"  ERROR: No time series data for {symbol}")
                if "Note" in data:
                    print(f"  API message: {data['Note']}")
                return {}

            prices = {}
            for date_str, daily_data in data["Time Series (Daily)"].items():
                if start_date <= date_str <= end_date:
                    prices[date_str] = float(daily_data["5. adjusted close"])

            return prices

        except Exception as e:
            print(f"  ERROR fetching {symbol}: {e}")
            return {}

    def fetch_prices_finnhub(self, symbol: str, start_date: str, end_date: str) -> Dict[str, float]:
        """Fetch daily prices from Finnhub stock candles."""
        self._rate_limit()

        # Convert dates to timestamps
        start_ts = int(parse_date_string(start_date).timestamp())
        end_ts = int(parse_date_string(end_date).timestamp())

        url = "https://finnhub.io/api/v1/stock/candle"
        params = {
            "symbol": symbol,
            "resolution": "D",  # Daily
            "from": start_ts,
            "to": end_ts,
            "token": self.api_key,
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            if data.get("s") != "ok":
                print(f"  ERROR: No data for {symbol}")
                return {}

            prices = {}
            for i, timestamp in enumerate(data["t"]):
                date_str = get_datetime_from_timestamp(timestamp).strftime("%Y-%m-%d")
                prices[date_str] = float(data["c"][i])  # close price

            return prices

        except Exception as e:
            print(f"  ERROR fetching {symbol}: {e}")
            return {}

    def get_symbols_needing_prices(self) -> List[str]:
        """Get list of symbols with NULL underlying_price."""
        self.cursor.execute(
            """
            SELECT DISTINCT symbol
            FROM options_chains
            WHERE underlying_price IS NULL
        """
        )
        return [row[0] for row in self.cursor.fetchall()]

    def get_date_range(self, symbol: str) -> tuple[str, str]:
        """Get min/max trading dates for a symbol."""
        self.cursor.execute(
            """
            SELECT MIN(trading_date), MAX(trading_date)
            FROM options_chains
            WHERE symbol = ?
        """,
            (symbol,),
        )
        return self.cursor.fetchone()

    def update_prices(self, symbol: str, prices: Dict[str, float]) -> int:
        """Update underlying_price in database."""
        updated = 0
        for date_str, price in prices.items():
            self.cursor.execute(
                """
                UPDATE options_chains
                SET underlying_price = ?
                WHERE symbol = ? AND trading_date = ? AND underlying_price IS NULL
            """,
                (price, symbol, date_str),
            )
            updated += self.cursor.rowcount

        self.conn.commit()
        return updated

    def backfill_all(self):
        """Backfill prices for all symbols."""
        symbols = self.get_symbols_needing_prices()

        if not symbols:
            print("No symbols need price backfill")
            return

        print(f"Found {len(symbols)} symbol(s) needing price backfill")
        print(f"Using provider: {self.provider}")

        for i, symbol in enumerate(symbols, 1):
            print(f"\n[{i}/{len(symbols)}] Processing {symbol}...")

            min_date, max_date = self.get_date_range(symbol)
            if not min_date or not max_date:
                print(f"  No date range found for {symbol}")
                continue

            print(f"  Date range: {min_date} to {max_date}")

            # Fetch prices
            if self.provider == "alpha_vantage":
                prices = self.fetch_prices_alpha_vantage(symbol, min_date, max_date)
            else:
                prices = self.fetch_prices_finnhub(symbol, min_date, max_date)

            if not prices:
                print(f"  No prices fetched for {symbol}")
                continue

            print(f"  Fetched {len(prices)} price records")

            # Update database
            updated = self.update_prices(symbol, prices)
            print(f"  Updated {updated} records")

    def close(self):
        """Close database connection."""
        self.conn.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Backfill underlying prices in GEX database")

    parser.add_argument(
        "--db",
        type=Path,
        default=Path(".cache/gex_research.db"),
        help="Database path",
    )
    parser.add_argument(
        "--provider",
        choices=["alpha_vantage", "finnhub"],
        default="alpha_vantage",
        help="Price data provider",
    )
    parser.add_argument("--api-key", type=str, help="API key (from config if omitted)")

    args = parser.parse_args()

    # Load API key from config if not provided
    if not args.api_key:
        config_path = Path("config/config.json")
        if config_path.exists():
            with open(config_path) as f:
                config = json.load(f)
                if args.provider == "alpha_vantage":
                    args.api_key = config.get("ALPHA_VANTAGE_KEY")
                else:
                    args.api_key = config.get("FINNHUB_KEY")

    if not args.api_key:
        print(f"ERROR: No API key found for {args.provider}")
        sys.exit(1)

    # Verify database exists
    if not args.db.exists():
        print(f"ERROR: Database not found: {args.db}")
        sys.exit(1)

    # Run backfill
    backfiller = PriceBackfiller(args.db, args.api_key, args.provider)
    try:
        backfiller.backfill_all()
        print("\nBackfill complete!")
    finally:
        backfiller.close()


if __name__ == "__main__":
    main()
