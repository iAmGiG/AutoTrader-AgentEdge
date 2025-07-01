import logging
from typing import Optional
import os
import pandas as pd
import nasdaqdatalink
from src.utils.date_utils import get_processed_date_range, localize_df, get_default_timezone


class NasdaqDataLinkTool:
    """Tool for fetching stock data from Nasdaq Data Link (Quandl)."""

    def __init__(self, api_key: Optional[str] = None, verbose: bool = False):
        self.logger = logging.getLogger(self.__class__.__name__)
        if verbose:
            logging.basicConfig(level=logging.INFO)

        if api_key is None:
            api_key = os.getenv("NASDAQ_DATA_LINK_KEY")
        if api_key:
            nasdaqdatalink.ApiConfig.api_key = api_key
        else:
            self.logger.warning("Nasdaq Data Link API key not provided")

        self.default_dataset = "EOD"

    def fetch_stock_data(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        dataset: Optional[str] = None,
    ) -> pd.DataFrame:
        """Fetch OHLCV data for a symbol."""
        if dataset is None:
            dataset = self.default_dataset
        try:
            start_date, end_date = get_processed_date_range(start_date, end_date)
            code = f"{dataset}/{symbol.upper()}"
            df = nasdaqdatalink.get(
                code, start_date=start_date, end_date=end_date
            )
            if df is None or df.empty:
                self.logger.warning(f"No Nasdaq Data Link data for {symbol}")
                return pd.DataFrame()

            column_map = {
                "Adj. Open": "Open",
                "Adj. High": "High",
                "Adj. Low": "Low",
                "Adj. Close": "Close",
                "Adj. Volume": "Volume",
            }
            df = df.rename(columns={k: v for k, v in column_map.items() if k in df.columns})
            ohlcv_cols = ["Open", "High", "Low", "Close", "Volume"]
            df = df[[col for col in ohlcv_cols if col in df.columns]]
            df = localize_df(df, get_default_timezone())
            return df
        except Exception as e:
            self.logger.error(f"Error fetching Nasdaq Data Link data: {e}")
            return pd.DataFrame()
