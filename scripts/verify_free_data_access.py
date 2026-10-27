"""
Verify Free Tier Historical Options Data Access

Tests what historical options data is available via free API tiers:
- Alpha Vantage (free tier)
- Alpaca (paper account)

Usage:
    python scripts/verify_free_data_access.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.config_loader import ConfigLoader

# Initialize config - explicitly use JSON file with real keys
project_root = Path(__file__).parent.parent
config_json_path = project_root / "config" / "config.json"
config_loader = ConfigLoader(str(config_json_path))


def get_config():
    """Get config instance."""
    return config_loader


def test_alpha_vantage_options_data():
    """Test Alpha Vantage free tier for options data."""
    print("\n" + "=" * 60)
    print("ALPHA VANTAGE FREE TIER TEST")
    print("=" * 60)

    config = get_config()
    api_key = config.get("ALPHA_VANTAGE_KEY")

    if not api_key:
        print("[X] No Alpha Vantage API key found")
        return False

    print(f"[OK] API Key Found: {api_key[:10]}...")

    try:
        import requests

        # Alpha Vantage doesn't have robust options endpoints
        # They have HISTORICAL_OPTIONS but it's very limited
        url = "https://www.alphavantage.co/query"
        params = {"function": "HISTORICAL_OPTIONS", "symbol": "SPY", "apikey": api_key}

        print("\nTesting: Historical Options endpoint")
        response = requests.get(url, params=params, timeout=10)

        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()

            if "Error Message" in data:
                print(f"[X] API Error: {data['Error Message']}")
                return False
            elif "Note" in data:
                print(rf"[\!] Rate Limited: {data['Note']}")
                print("Free tier: 25 API calls/day (very restrictive)")
                return False
            elif "data" in data:
                print("[OK] Some data available")
                print(f"Records: {len(data.get('data', []))}")
                return True
            else:
                print(rf"[\!] Unexpected format: {list(data.keys())}")
                return False
        else:
            print(f"[X] Request failed: {response.text[:200]}")
            return False

    except Exception as e:
        print(f"[X] Error testing Alpha Vantage: {e}")
        return False


def test_alpaca_options_data():
    """Test Alpaca paper account for options data."""
    print("\n" + "=" * 60)
    print("ALPACA PAPER ACCOUNT TEST")
    print("=" * 60)

    config = get_config()
    api_key = config.get("ALPACA_PAPER_API_KEY")
    secret = config.get("ALPACA_PAPER_SECRET")

    if not api_key or not secret:
        print("[X] No Alpaca credentials found")
        return False

    print(f"[OK] API Key Found: {api_key[:10]}...")

    try:
        import requests

        base_url = "https://paper-api.alpaca.markets"
        headers = {"APCA-API-KEY-ID": api_key, "APCA-API-SECRET-KEY": secret}

        # Test 1: Check account status
        account_url = f"{base_url}/v2/account"
        print("\nTesting: Account access")

        account_resp = requests.get(account_url, headers=headers, timeout=10)
        print(f"Account Status: {account_resp.status_code}")

        if account_resp.status_code != 200:
            print(f"[X] Account access failed: {account_resp.text[:200]}")
            return False

        account_data = account_resp.json()
        print(f"[OK] Account active: {account_data.get('account_number', 'N/A')}")

        # Test 2: Options chain endpoint
        # Note: Alpaca options API is different from stock API
        options_url = f"{base_url}/v2/options/contracts"
        params = {"underlying_symbols": "SPY", "status": "active", "limit": 10}

        print("\nTesting: Options contracts endpoint")
        options_resp = requests.get(options_url, headers=headers, params=params, timeout=10)

        print(f"Options Status: {options_resp.status_code}")

        if options_resp.status_code == 200:
            options_data = options_resp.json()

            if "option_contracts" in options_data:
                contracts = options_data["option_contracts"]
                print(f"[OK] Options data available! {len(contracts)} contracts")

                if contracts:
                    sample = contracts[0]
                    print(f"Sample: {sample.get('symbol', 'N/A')}")
                    print(f"Strike: {sample.get('strike_price', 'N/A')}")
                    print(f"Type: {sample.get('type', 'N/A')}")

                # Test 3: Historical options bars
                if contracts:
                    contract_symbol = contracts[0]["symbol"]
                    bars_url = f"{base_url}/v1beta1/options/bars"
                    bars_params = {
                        "symbols": contract_symbol,
                        "timeframe": "1Day",
                        "start": "2024-01-01",
                        "end": "2024-12-31",
                        "limit": 1000,
                    }

                    print(f"\nTesting: Historical bars for {contract_symbol}")
                    bars_resp = requests.get(
                        bars_url, headers=headers, params=bars_params, timeout=10
                    )

                    print(f"Bars Status: {bars_resp.status_code}")

                    if bars_resp.status_code == 200:
                        bars_data = bars_resp.json()
                        bars = bars_data.get("bars", {}).get(contract_symbol, [])
                        print(f"[OK] Historical bars available! {len(bars)} bars")
                        return True
                    else:
                        print(rf"[\!] Historical bars issue: {bars_resp.text[:200]}")
                        return False

                return True
            else:
                print(rf"[\!] Unexpected format: {list(options_data.keys())}")
                return False

        elif options_resp.status_code == 404:
            print("[X] Options endpoint not found (may not be supported on paper)")
            return False
        else:
            print(rf"[\!] Options request failed: {options_resp.text[:200]}")
            return False

    except Exception as e:
        print(f"[X] Error testing Alpaca: {e}")
        return False


def main():
    """Run all data access verification tests."""
    print("\n" + "=" * 60)
    print("FREE TIER OPTIONS DATA VERIFICATION")
    print("=" * 60)
    print("\nChecking what historical options data is available...")
    print("This will help determine if paid subscriptions are needed.")

    results = {
        "alpha_vantage": test_alpha_vantage_options_data(),
        "alpaca": test_alpaca_options_data(),
    }

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    for provider, success in results.items():
        status = "[OK] Available" if success else "[X] Limited/Unavailable"
        print(f"{provider.upper()}: {status}")

    # Recommendations
    print("\n" + "=" * 60)
    print("RECOMMENDATIONS")
    print("=" * 60)

    if any(results.values()):
        print("\n[OK] Some free tier data is available!")
        print("Next steps:")
        print("1. Test data quality and coverage")
        print("2. Determine if sufficient for backtesting needs")
        print("3. Consider paid tier only if free is insufficient")
    else:
        print("\n[X] Free tier appears very limited for options data")
        print("Options:")
        print("1. Use limited free data for proof-of-concept")
        print("2. Read options data from the gex DB (read-only, #572)")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
