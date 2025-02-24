from base_agent import BaseAgent
import pandas as pd


class StrategyAgent(BaseAgent):
    def preprocess_data(self, data: pd.DataFrame) -> dict:
        # e.g. calculate moving averages, implied vol spreads, etc.
        signals = ...
        return signals

# Load data example
# base_agent.load_tool("market_data", market_data_tool)
# fetch data example
# df = self.use_tool("market_data").fetch_options_data(
#     symbol="AAPL",
#     start_date="2021-01-01",
#     end_date="2021-01-31",
#     filters={"option_type": "call"}
# )
