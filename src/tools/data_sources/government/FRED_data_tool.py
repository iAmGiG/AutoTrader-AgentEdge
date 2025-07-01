"""
FRED (Federal Reserve Economic Data) data tool for accessing economic data.

This tool provides access to FRED data via the fredapi library,
allowing retrieval of various economic indicators such as GDP, inflation rates,
unemployment figures, and more.
"""

from src.utils.date_utils import process_date_param, get_processed_date_range
import logging
from typing import Optional, Dict, Any, List
import pandas as pd
import logging
from typing import Optional, Dict, Any, List
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
            start_date: Start date in YYYY-MM-DD format or relative date like "-5y".
                        If None, fetches 5 years of data.
            end_date: End date in YYYY-MM-DD format or relative date like "today".
                      If None, uses current date.
            transform: Transformation to apply ('pct_change', 'diff', etc.)

        Returns:
            DataFrame with date index and value column
        """
        try:
            # Use the date_utils to properly handle date parameters
            processed_start, processed_end = get_processed_date_range(
                start_date=start_date,
                end_date=end_date,
                default_days_back=365*5  # Default to 5 years of data
            )

            # Fetch data from FRED
            series = self.fred.get_series(
                series_id, processed_start, processed_end, transform=transform)

            if series.empty:
                self.logger.warning(f"No data returned for series {series_id}")
                return pd.DataFrame()

            # Convert series to DataFrame
            df = pd.DataFrame(series)
            df.reset_index(inplace=True)

            # Rename columns to standard format
            df.columns = ['Date', 'Value']

            # Add metadata
            df['Series ID'] = series_id
            df['Source'] = 'FRED'

            # Get series information for additional context
            try:
                series_info = self.fred.get_series_info(series_id)
                if series_info is not None:
                    df['Title'] = series_info.get('title', series_id)
                    df['Units'] = series_info.get('units', '')
                    df['Frequency'] = series_info.get('frequency', '')
                else:
                    df['Title'] = series_id
                    df['Units'] = ''
                    df['Frequency'] = ''
            except Exception as e:
                self.logger.warning(
                    f"Could not fetch series info for {series_id}: {e}")
                df['Title'] = series_id
                df['Units'] = ''
                df['Frequency'] = ''

            return df

        except Exception as e:
            self.logger.error(f"Error fetching series {series_id}: {e}")
            return pd.DataFrame()

    def get_indicator(self, indicator: str,
                      start_date: Optional[str] = None,
                      end_date: Optional[str] = None,
                      transform: Optional[str] = None) -> pd.DataFrame:
        """
        Get an economic indicator by name using predefined series IDs.

        Args:
            indicator: Name of the indicator (e.g., 'gdp', 'unemployment')
            start_date: Start date in YYYY-MM-DD format or relative date like "-5y"
            end_date: End date in YYYY-MM-DD format or relative date like "today"
            transform: Transformation to apply

        Returns:
            DataFrame with the requested indicator
        """
        # Get the series ID for the indicator
        series_id = ECONOMIC_INDICATORS.get(indicator.lower())

        if not series_id:
            self.logger.error(f"Unknown indicator: {indicator}")
            self.logger.info(
                f"Available indicators: {', '.join(ECONOMIC_INDICATORS.keys())}")
            return pd.DataFrame()

        # Fetch the series
        return self.get_series(series_id, start_date, end_date, transform)

    def get_gdp(self, start_date: Optional[str] = None,
                end_date: Optional[str] = None,
                real: bool = True) -> pd.DataFrame:
        """
        Get Gross Domestic Product data.

        Args:
            start_date: Start date in YYYY-MM-DD format or relative date like "-5y"
            end_date: End date in YYYY-MM-DD format or relative date like "today"
            real: Whether to get real (inflation-adjusted) GDP

        Returns:
            DataFrame with GDP data
        """
        series_id = "GDPC1" if real else "GDP"
        return self.get_series(series_id, start_date, end_date)

    def get_inflation(self, start_date: Optional[str] = None,
                      end_date: Optional[str] = None,
                      year_over_year: bool = True) -> pd.DataFrame:
        """
        Get inflation data.

        Args:
            start_date: Start date in YYYY-MM-DD format or relative date like "-5y"
            end_date: End date in YYYY-MM-DD format or relative date like "today"
            year_over_year: Whether to compute year-over-year percentage change

        Returns:
            DataFrame with inflation data
        """
        if year_over_year:
            # Use Core CPI YoY series directly for YoY inflation
            return self.get_series("CORESTICKM159SFRBATL", start_date, end_date)
        else:
            # Get CPI index
            transform = None  # Don't apply transformation in the initial call
            df = self.get_series("CPIAUCSL", start_date, end_date, transform)

            if df.empty:
                return df

            return df

    def get_unemployment(self, start_date: Optional[str] = None,
                         end_date: Optional[str] = None) -> pd.DataFrame:
        """
        Get unemployment rate data.

        Args:
            start_date: Start date in YYYY-MM-DD format or relative date like "-5y"
            end_date: End date in YYYY-MM-DD format or relative date like "today"

        Returns:
            DataFrame with unemployment rate data
        """
        return self.get_series("UNRATE", start_date, end_date)

    def get_interest_rates(self, start_date: Optional[str] = None,
                           end_date: Optional[str] = None,
                           rate_type: str = "fed_funds") -> pd.DataFrame:
        """
        Get interest rate data.

        Args:
            start_date: Start date in YYYY-MM-DD format or relative date like "-5y"
            end_date: End date in YYYY-MM-DD format or relative date like "today"
            rate_type: Type of interest rate (fed_funds, treasury_10y, treasury_2y, treasury_3m)

        Returns:
            DataFrame with interest rate data
        """
        rate_mapping = {
            "fed_funds": "FEDFUNDS",
            "treasury_10y": "DGS10",
            "treasury_2y": "DGS2",
            "treasury_3m": "DGS3MO"
        }

        series_id = rate_mapping.get(rate_type, "FEDFUNDS")
        return self.get_series(series_id, start_date, end_date)

    def get_yield_curve(self, date: Optional[str] = None) -> pd.DataFrame:
        """
        Get the yield curve for a specific date.

        Args:
            date: Date in YYYY-MM-DD format or relative date like "today".
                 If None, uses most recent data.

        Returns:
            DataFrame with yield curve data
        """
        # Define Treasury maturities to include
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

        # Process the date parameter using date_utils
        processed_date = process_date_param(
            date) or process_date_param("today")

        # For end date, we use the next day to ensure we get data for the date we want
        # Using standard datetime to create a date one day after processed_date
        from datetime import datetime, timedelta
        date_obj = datetime.strptime(processed_date, '%Y-%m-%d')
        end_date = (date_obj + timedelta(days=1)).strftime('%Y-%m-%d')

        # Fetch data for each maturity
        yield_data = {}
        for maturity, series_id in maturities.items():
            try:
                # Get a single data point for the date
                series = self.fred.get_series(
                    series_id, processed_date, end_date)
                if not series.empty:
                    yield_data[maturity] = series.iloc[0]
                else:
                    yield_data[maturity] = None
            except Exception as e:
                self.logger.warning(
                    f"Could not fetch data for {maturity} ({series_id}): {e}")
                yield_data[maturity] = None

        # Create DataFrame
        df = pd.DataFrame([yield_data])
        df['Date'] = processed_date

        # Reorder columns to put Date first
        cols = df.columns.tolist()
        cols.remove('Date')
        df = df[['Date'] + cols]

        return df

    def get_multiple_series(self, series_ids: List[str],
                            start_date: Optional[str] = None,
                            end_date: Optional[str] = None) -> pd.DataFrame:
        """
        Get multiple series in a single DataFrame with proper alignment.

        Args:
            series_ids: List of FRED series IDs
            start_date: Start date in YYYY-MM-DD format or relative date like "-5y"
            end_date: End date in YYYY-MM-DD format or relative date like "today"

        Returns:
            DataFrame with multiple series aligned by date
        """
        # Use the date_utils to properly handle date parameters
        processed_start, processed_end = get_processed_date_range(
            start_date=start_date,
            end_date=end_date,
            default_days_back=365*5  # Default to 5 years of data
        )

        data = {}

        # Fetch each series
        for series_id in series_ids:
            try:
                series = self.fred.get_series(
                    series_id, processed_start, processed_end)
                if not series.empty:
                    data[series_id] = series
                else:
                    self.logger.warning(
                        f"No data returned for series {series_id}")
            except Exception as e:
                self.logger.error(f"Error fetching series {series_id}: {e}")

        # If no data was fetched, return empty DataFrame
        if not data:
            return pd.DataFrame()

        # Combine series into a single DataFrame
        df = pd.DataFrame(data)

        # Reset index to make date a column
        df.reset_index(inplace=True)
        df.rename(columns={'index': 'Date'}, inplace=True)

        return df

    def get_series_info(self, series_id: str) -> Dict[str, Any]:
        """
        Get metadata information about a specific series.

        Args:
            series_id: FRED series ID

        Returns:
            Dictionary with series metadata
        """
        try:
            info = self.fred.get_series_info(series_id)
            return info
        except Exception as e:
            self.logger.error(
                f"Error fetching series info for {series_id}: {e}")
            return {}

    def search_series(self, search_text: str, limit: int = 10) -> pd.DataFrame:
        """
        Search for FRED series matching the search text.

        Args:
            search_text: Text to search for
            limit: Maximum number of results to return

        Returns:
            DataFrame with search results
        """
        try:
            results = self.fred.search(search_text, limit=limit)

            if results.empty:
                self.logger.info(f"No series found matching '{search_text}'")
                return pd.DataFrame()

            # Rename the index to 'series_id' for clarity
            results.index.name = 'series_id'

            # Reset index to make series_id a column
            results.reset_index(inplace=True)

            return results
        except Exception as e:
            self.logger.error(f"Error searching for '{search_text}': {e}")
            return pd.DataFrame()

    def get_indicator_comparison(self,
                                 indicators: List[str],
                                 start_date: Optional[str] = None,
                                 end_date: Optional[str] = None) -> pd.DataFrame:
        """
        Get multiple indicators for comparison, normalized to the same scale.

        Args:
            indicators: List of indicator names (must be in ECONOMIC_INDICATORS)
            start_date: Start date in YYYY-MM-DD format or relative date like "-5y"
            end_date: End date in YYYY-MM-DD format or relative date like "today"

        Returns:
            DataFrame with multiple indicators normalized for comparison
        """
        # Validate indicators
        series_ids = []
        for indicator in indicators:
            series_id = ECONOMIC_INDICATORS.get(indicator.lower())
            if series_id:
                series_ids.append(series_id)
            else:
                self.logger.warning(
                    f"Unknown indicator: {indicator}, skipping")

        if not series_ids:
            return pd.DataFrame()

        # Get the data
        df = self.get_multiple_series(series_ids, start_date, end_date)

        if df.empty:
            return df

        # Add indicator names for clarity
        reverse_mapping = {v: k for k, v in ECONOMIC_INDICATORS.items()}
        rename_cols = {
            col: f"{reverse_mapping.get(col, col)}" for col in df.columns if col != 'Date'}
        df.rename(columns=rename_cols, inplace=True)

        return df

    def list_available_indicators(self) -> pd.DataFrame:
        """
        List all available predefined indicators.

        Returns:
            DataFrame with indicator names and series IDs
        """
        data = []
        for name, series_id in ECONOMIC_INDICATORS.items():
            try:
                info = self.fred.get_series_info(series_id)
                title = info.get('title', 'Unknown')
                units = info.get('units', 'Unknown')
                frequency = info.get('frequency', 'Unknown')

                data.append({
                    'Name': name,
                    'Series ID': series_id,
                    'Title': title,
                    'Units': units,
                    'Frequency': frequency
                })
            except Exception as e:
                self.logger.warning(
                    f"Could not fetch info for {name} ({series_id}): {e}")
                data.append({
                    'Name': name,
                    'Series ID': series_id,
                    'Title': 'Error retrieving info',
                    'Units': 'Unknown',
                    'Frequency': 'Unknown'
                })

        return pd.DataFrame(data)


# Example usage
if __name__ == "__main__":
    # Initialize the tool
    fred_tool = FREDDataTool(verbose=True)

    # Get GDP data using relative date format
    gdp_data = fred_tool.get_indicator('gdp', start_date="-5y")
    print("\nGDP Data:")
    print(gdp_data.head())

    # Get unemployment rate using relative date format
    unemployment_data = fred_tool.get_unemployment(start_date="-2y")
    print("\nUnemployment Rate:")
    print(unemployment_data.head())

    # Get yield curve for current date
    yield_curve = fred_tool.get_yield_curve("today")
    print("\nCurrent Yield Curve:")
    print(yield_curve)

    # Get multiple indicators for comparison
    comparison = fred_tool.get_indicator_comparison(['gdp_growth', 'unemployment', 'inflation_yoy'],
                                                    start_date="-3y")
    print("\nEconomic Indicator Comparison:")
    print(comparison.head())

    # Print the attribution notice required by FRED
    print("\nThis product uses the FRED® API but is not endorsed or certified by the Federal Reserve Bank of St. Louis.")
