import yfinance as yf
import pandas as pd


class YahooFinanceTool:
    def fetch_stock_data(self, ticker, start_date="2023-01-01", end_date="2024-01-01"):
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(start=start_date, end=end_date)
            if df.empty:
                print(f"Warning: No data fetched for {ticker}")
            return df[['Open', 'High', 'Low', 'Close', 'Volume']]
        except Exception as e:
            print(f"Error fetching stock data: {e}")
            return pd.DataFrame()


if __name__ == "__main__":
    # Use 'api' for live fetching
    tool = YahooFinanceTool({"data_source": "api"})
    df = tool.fetch_stock_data("AAPL", "2023-01-01", "2024-01-01")
    print(df.head())  # Check if data is coming through
    print("Fetched DataFrame shape:", df.shape)
    print("DataFrame content:", df.head())
