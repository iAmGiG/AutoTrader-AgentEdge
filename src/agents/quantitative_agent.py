# Std libs
import logging
from typing import Any, Dict, List, Optional

# 3rd-party libs
import pandas as pd
import numpy as np

# project imports
from src.agents.base_agent import BaseAgent
from src.tools.tools import QUANTITATIVE_AGENT, get_tools_for_agent

QUANT_LLM_CONFIG = {
    "temperature": 0.15,      # deterministic outputs
    "max_tokens": 4096,
    "top_p": 0.9,
    # You can set frequency_penalty / presence_penalty if hallucinations crop up
}


class QuantitativeAgent(BaseAgent):
    """
    Agent that answers quantitative / technical-analysis questions.

    Responsibilities
    ----------------
    • Retrieve market & macro data via registered tools.
    • Compute indicators locally.
    • Generate concise, data-driven explanations for the user.
    """

    def __init__(self, name: str = "QuantitativeAgent", memory_system=None):
        # Select only the quantitative-tagged tools
        tools = get_tools_for_agent(QUANTITATIVE_AGENT)

        super().__init__(
            name=name,
            tools=tools,
            memory_system=memory_system,
            llm_config=QUANT_LLM_CONFIG,
        )

        # Optional: attach a logger
        self.logger = logging.getLogger(self.__class__.__name__)

    def preprocess_message(self, message: str) -> Dict[str, Any]:
        """
        Very light parsing: pull out tickers, date windows, indicator names.

        Return a dict like:
        {
            "ticker": "AAPL",
            "indicators": ["sma(50)", "rsi(14)"],
            "start_date": "-90d",
            "end_date": "today"
        }
        """
        # TODO: plug in your QueryParser or quick regex heuristics
        parsed: Dict[str, Any] = {}
        return parsed

    def format_supplementary_context(self, query: Dict[str, Any]) -> str:
        """
        Build a short system prompt snippet that guides the LLM toward
        tool use + indicator computation.
        """
        snippets: List[str] = []

        if query.get("ticker"):
            snippets.append(f"Focus ticker: {query['ticker']}")

        if query.get("indicators"):
            snippets.append(
                "Requested indicators: " + ", ".join(query["indicators"])
            )

        snippets.append(
            "Available quantitative tools: fetch_market_data, fetch_yahoo_data, "
            "fetch_economic_indicator, fetch_interest_rates, fetch_yield_curve"
        )

        return "\n".join(snippets)

    def process_tool_result(
        self,
        tool_name: str,
        result: Any,
        tool_args: Dict[str, Any]
    ) -> Any:
        """
        Convert raw DataFrames into lightweight dict summaries, and/or
        compute requested indicators.
        """
        if isinstance(result, pd.DataFrame) and not result.empty:
            if tool_name in {"fetch_market_data", "fetch_yahoo_data"}:
                # Example: compute SMA / RSI if asked
                df = result.copy()
                if "sma(50)" in tool_args.get("indicators", []):
                    df["SMA50"] = sma(df["Close"], 50)
                if "rsi(14)" in tool_args.get("indicators", []):
                    df["RSI14"] = rsi(df["Close"], 14)
                # Return only the last row as JSON to keep token usage low
                return {
                    "latest_row": df.tail(1).to_dict(orient="records")[0],
                    "columns": list(df.columns),
                }
        # default passthrough
        return result

    def generate_reply(self, messages, context=None):
        """
        Primary entry-point required by AutoGen-assistant agents.
        """
        # --------------- Extract last user message -------------------------
        last_msg = messages[-1]["content"] if messages else ""
        query = self.preprocess_message(last_msg)

        # --------------- Compose system prompt ----------------------------
        sys_prompt = (
            "You are a quantitative research assistant. "
            "When useful, call tools to fetch data, then compute indicators "
            "locally before you answer.\n"
            "\nSupplementary context:\n"
            + self.format_supplementary_context(query)
            + "\n\nIMPORTANT: Use multiple tools if it improves the answer."
        )

        # --------------- Forward to BaseAgent’s tool-aware pipeline -------
        return self.process_with_tools(last_msg, sys_prompt)
