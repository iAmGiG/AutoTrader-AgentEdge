from base_agent import BaseAgent
import pandas as pd


class SentimentAgent(BaseAgent):
    def preprocess_data(self, data: pd.DataFrame) -> dict:
        # e.g. calculate moving averages, implied vol spreads, etc.
        signals = ...
        return signals