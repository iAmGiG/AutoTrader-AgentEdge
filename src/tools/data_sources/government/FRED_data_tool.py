"""
FRED (Federal Reserve Economic Data) data tool for accessing economic data.

This tool provides access to FRED data via the fredapi library,
allowing retrieval of various economic indicators such as GDP, inflation rates,
unemployment figures, and more.
"""

from src.utils.date_utils import process_date_param, get_processed_date_range
import logging
from typing import Optional, List
import pandas as pd
from fredapi import Fred
import os
from config.config_loader import ConfigLoader

config_loader = ConfigLoader()


# Define standard economic indicator series IDs for easy access
ECONOMIC_INDICATORS = {
    "gdp": "GDP",                    # Gross Domestic Product
    "real_gdp": "GDPC1",             # Real Gross Domestic Product
    "gdp_growth": "A191RL1Q225SBEA",  # Real GDP Growth Rate
    "unemployment": "UNRATE",        # Unemployment Rate
    "inflation": "CPIAUCSL",         # Consumer Price Index for All Urban Consumers
    "inflation_yoy": "CORESTICKM159SFRBATL",  # Core CPI YoY
    "interest_rate": "FEDFUNDS",     # Federal Funds Effective Rate
    "treasury_10y": "DGS10",         # 10-Year Treasury Constant Maturity Rate
    "treasury_2y": "DGS2",           # 2-Year Treasury Constant Maturity Rate
    "treasury_3m": "DGS3MO",         # 3-Month Treasury Constant Maturity Rate
    "retail_sales": "RSAFS",         # Retail Sales
    "industrial_production": "INDPRO",  # Industrial Production Index
    "housing_starts": "HOUST",       # Housing Starts
    "consumer_sentiment": "UMCSENT",  # University of Michigan Consumer Sentiment
    "business_confidence": "BSCICP03USM665S",  # Business Confidence Indicator
    "m2_money_supply": "M2",         # M2 Money Stock
    "excess_reserves": "EXCSRESNS",  # Excess Reserves of Depository Institutions
    "pce": "PCE",                    # Personal Consumption Expenditures
    "personal_income": "PI",         # Personal Income
    "personal_saving_rate": "PSAVERT"  # Personal Saving Rate
}


class FREDDataTool:
    """
    A tool for accessing economic data from FRED (Federal Reserve Economic Data).

    This tool provides methods to access various economic indicators directly from
    the Federal Reserve Economic Data API. It normalizes the data into pandas
    DataFrames and offers both high-level indicator methods and direct series access.
    """

    def __init__(self, api_key: Optional[str] = None, verbose: bool = False):
        """
        Initialize the FRED data tool.

        Args:
            api_key: Optional API key for FRED. If not provided, will load from config.
            verbose: Whether to enable verbose logging.
        """
        # Set up logger
        self.logger = logging.getLogger(self.__class__.__name__)
        if verbose:
            logging.basicConfig(level=logging.INFO)

        # Load API key from environment if not provided
        if api_key is None:
            api_key = os.getenv("FREDAPI", config_loader.get("FREDAPI"))

            if not api_key:
                self.logger.error("No FRED API key provided in environment")
                raise ValueError(
                    "FRED API key is required. Set the FREDAPI environment variable."
                )
        # Initialize FRED API client
        try:
            self.fred = Fred(api_key=api_key)
            self.logger.info("FRED API client initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize FRED API client: {e}")
            raise

        # Store the indicators dictionary for reference
        self.indicators = ECONOMIC_INDICATORS

    def get_series(self, series_id: str,
                   start_date: Optional[str] = None,
                   end_date: Optional[str] = None,
                   transform: Optional[str] = None) -> pd.DataFrame:
        """
        Get data for a specific FRED series ID.

        Args:
            series_id: FRED series ID (e.g., 'GDP', 'UNRATE')
            start_date: Start date (YYYY-MM-DD format or relative like '-1y')
            end_date: End date (YYYY-MM-DD format or 'today')
            transform: Optional data transformation ('chg', 'ch1', 'pch', 'pc1', 'pca', 'cch', 'cca', 'log')

        Returns:
            DataFrame with the requested economic data
        """
        try:
            # Process date parameters
            start_date, end_date = get_processed_date_range(
                start_date, end_date)

            self.logger.info(
                f"Fetching FRED series {series_id} from {start_date} to {end_date}")

            # Fetch data using fredapi
            # Note: fredapi expects observation_start/observation_end parameters
            data = self.fred.get_series(
                series_id,
                observation_start=start_date,
                observation_end=end_date
            )

            if data is None or data.empty:
                self.logger.warning(f"No data returned for series {series_id}")
                return pd.DataFrame()

            # Convert to DataFrame with proper column names
            df = pd.DataFrame(data, columns=['value'])
            df.index.name = 'date'
            df = df.reset_index()

            # Add metadata
            df['series_id'] = series_id
            df['series_name'] = self._get_series_name(series_id)

            # Apply transformation if requested
            if transform:
                df = self._apply_transformation(df, transform)

            self.logger.info(
                f"Successfully fetched {len(df)} observations for {series_id}")
            return df

        except Exception as e:
            self.logger.error(f"Error fetching FRED series {series_id}: {e}")
            return pd.DataFrame()

    def get_economic_indicator(self, indicator: str,
                               start_date: Optional[str] = None,
                               end_date: Optional[str] = None) -> pd.DataFrame:
        """
        Get data for a common economic indicator using friendly names.

        Args:
            indicator: Indicator name (e.g., 'unemployment', 'gdp', 'inflation')
            start_date: Start date (YYYY-MM-DD format or relative like '-1y')
            end_date: End date (YYYY-MM-DD format or 'today')

        Returns:
            DataFrame with the requested economic indicator data
        """
        # Check if indicator is recognized
        if indicator.lower() not in self.indicators:
            self.logger.error(
                f"Unknown indicator: {indicator}. Available indicators: {list(self.indicators.keys())}")
            return pd.DataFrame()

        # Get the FRED series ID for this indicator
        series_id = self.indicators[indicator.lower()]

        # Fetch using the series ID
        df = self.get_series(series_id, start_date, end_date)

        # Add friendly indicator name
        if not df.empty:
            df['indicator'] = indicator.lower()

        return df

    def get_multiple_series(self, series_ids: List[str],
                            start_date: Optional[str] = None,
                            end_date: Optional[str] = None) -> pd.DataFrame:
        """
        Get data for multiple FRED series in a single call.

        Args:
            series_ids: List of FRED series IDs
            start_date: Start date (YYYY-MM-DD format or relative like '-1y')
            end_date: End date (YYYY-MM-DD format or 'today')

        Returns:
            DataFrame with data for all requested series
        """
        all_data = []

        for series_id in series_ids:
            df = self.get_series(series_id, start_date, end_date)
            if not df.empty:
                all_data.append(df)

        if all_data:
            # Combine all dataframes
            combined_df = pd.concat(all_data, ignore_index=True)
            return combined_df
        else:
            return pd.DataFrame()

    def search_series(self, search_text: str, limit: int = 10) -> pd.DataFrame:
        """
        Search for FRED series that match the given text.

        Args:
            search_text: Text to search for in series names/descriptions
            limit: Maximum number of results to return

        Returns:
            DataFrame with matching series information
        """
        try:
            self.logger.info(f"Searching FRED for: {search_text}")

            # Use fredapi search function
            results = self.fred.search(search_text, limit=limit)

            if results is None or results.empty:
                self.logger.warning(f"No series found matching: {search_text}")
                return pd.DataFrame()

            # Convert results to a more usable format
            df = pd.DataFrame({
                'series_id': results.index,
                'title': results['title'],
                'units': results['units'],
                'frequency': results['frequency'],
                'last_updated': results['last_updated']
            })

            self.logger.info(f"Found {len(df)} series matching: {search_text}")
            return df

        except Exception as e:
            self.logger.error(f"Error searching FRED series: {e}")
            return pd.DataFrame()

    def get_yield_curve(self, date: Optional[str] = None) -> pd.DataFrame:
        """
        Get U.S. Treasury yield curve data for a specific date.

        Args:
            date: Date for yield curve (defaults to most recent data)

        Returns:
            DataFrame with yield curve data
        """
        # Treasury maturity series
        maturities = {
            "1M": "DGS1MO",
            "3M": "DGS3MO",
            "6M": "DGS6MO",
            "1Y": "DGS1",
            "2Y": "DGS2",
            "3Y": "DGS3",
            "5Y": "DGS5",
            "7Y": "DGS7",
            "10Y": "DGS10",
            "20Y": "DGS20",
            "30Y": "DGS30"
        }

        if date is None:
            # Get most recent data
            date = pd.Timestamp.now().strftime('%Y-%m-%d')

        # Process the date
        processed_date = process_date_param(date)

        yield_data = []
        for maturity, series_id in maturities.items():
            df = self.get_series(series_id, processed_date, processed_date)
            if not df.empty:
                yield_data.append({
                    'maturity': maturity,
                    'series_id': series_id,
                    'yield': df['value'].iloc[0],
                    'date': df['date'].iloc[0]
                })

        if yield_data:
            return pd.DataFrame(yield_data)
        else:
            self.logger.warning(f"No yield curve data found for date: {date}")
            return pd.DataFrame()

    def _get_series_name(self, series_id: str) -> str:
        """
        Get the friendly name for a series ID if available.

        Args:
            series_id: FRED series ID

        Returns:
            Friendly name or the series ID itself
        """
        # Reverse lookup in our indicators dictionary
        for name, sid in self.indicators.items():
            if sid == series_id:
                return name.replace('_', ' ').title()
        return series_id

    def _apply_transformation(self, df: pd.DataFrame, transform: str) -> pd.DataFrame:
        """
        Apply a transformation to the data.

        Args:
            df: DataFrame with 'value' column
            transform: Transformation to apply

        Returns:
            DataFrame with transformed values
        """
        if transform == 'chg':  # Change
            df['value'] = df['value'].diff()
        elif transform == 'ch1':  # Change from year ago
            df['value'] = df['value'].diff(12)  # Assuming monthly data
        elif transform == 'pch':  # Percent change
            df['value'] = df['value'].pct_change() * 100
        elif transform == 'pc1':  # Percent change from year ago
            df['value'] = df['value'].pct_change(12) * 100
        elif transform == 'log':  # Natural log
            df['value'] = df['value'].apply(lambda x: pd.np.log(x) if x > 0 else None)

        # Add transformation info
        df['transform'] = transform

        return df

    def test_connection(self) -> bool:
        """
        Test the FRED API connection.

        Returns:
            True if connection is successful, False otherwise
        """
        try:
            # Try to fetch a small amount of GDP data
            df = self.get_series("GDP", "-1m", "today")
            return not df.empty
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False


if __name__ == "__main__":
    # Example usage
    tool = FREDDataTool()

    # Test connection
    print("Testing FRED connection...")
    if tool.test_connection():
        print("✓ Connection successful!")
    else:
        print("✗ Connection failed!")

    # Get unemployment rate
    print("\nFetching unemployment rate...")
    unemployment = tool.get_economic_indicator("unemployment", "-1y", "today")
    if not unemployment.empty:
        print(unemployment.tail())

    # Get multiple indicators
    print("\nFetching multiple indicators...")
    indicators = tool.get_multiple_series(
        ["UNRATE", "GDP", "CPIAUCSL"], "-6m", "today")
    if not indicators.empty:
        print(indicators.groupby('series_name').tail(2))

    # Search for series
    print("\nSearching for inflation series...")
    search_results = tool.search_series("inflation", limit=5)
    if not search_results.empty:
        print(search_results[['series_id', 'title']])

    # Get yield curve
    print("\nFetching current yield curve...")
    yield_curve = tool.get_yield_curve()
    if not yield_curve.empty:
        print(yield_curve)

    # Print available indicators
    print("\nAvailable economic indicators:")
    for key, series_id in tool.indicators.items():
        print(f"  - {key}: {series_id}")
