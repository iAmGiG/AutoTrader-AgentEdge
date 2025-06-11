# Std libs
import logging
from typing import Any, Dict, List
import re
from datetime import datetime

# 3rd-party libs
import pandas as pd

# TODO numpy usage coming
import numpy as np

# project imports
from src.agents.base_agent import BaseAgent
from src.tools.tools import QUANTITATIVE_AGENT, get_tools_for_agent
from src.tools.processors.indicator_library import (
    sma,
    ema,
    rsi,
    atr,
    supertrend,
    avwap,
    macd,
    bollinger_bands,
    adx,
    ichimoku,
    stochrsi,
    cci,
)
from src.tools.processors.data_normalizer import standardize_indicator_columns
from src.tools.date_utils import (
    process_date_param,
    get_processed_date_range,
    get_default_date_range,
)
from src.tools.agent_utils import QueryParser

QUANT_LLM_CONFIG = {
    "temperature": 0.15,  # deterministic outputs
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
        Parse financial queries to extract tickers, indicators, timeframes, and other parameters.

        Args:
            message: User input message

        Returns:
            Dict containing parsed components:
            {
                "ticker": "AAPL",
                "indicators": ["sma(20)", "rsi(14)", "atr(14)"],
                "interval": "1h",
                "start_date": "2025-03-05",
                "end_date": "2025-06-03",
                "needs_macro": False,
                "lookback": "90d",
                "chart_type": "candlestick",
                "analysis_types": ["basic"],
                "comparison_tickers": []
            }
        """
        # Preserve original case for ticker patterns; use lowercase for keywords
        original_text = message
        lower_text = message.lower()

        parsed: Dict[str, Any] = {}

        # 1. Extract ticker symbols (2-5 uppercase letters)
        ticker_patterns = [
            r"\$([A-Z]{2,5})\b",  # With $ prefix
            r"\bticker[:\s]+([A-Z]{2,5})\b",  # "ticker: AAPL"
            r"\b([A-Z]{2,5})\b",  # Standard ticker format
        ]

        ticker = None
        for pattern in ticker_patterns:
            match = re.search(pattern, original_text)
            if match:
                potential_ticker = match.group(1)
                false_positives = {
                    "USD",
                    "GMT",
                    "EST",
                    "PST",
                    "API",
                    "HTTP",
                    "JSON",
                    "XML",
                }
                if potential_ticker not in false_positives:
                    ticker = potential_ticker
                    break

        parsed["ticker"] = ticker or "SPY"  # Default to SPY

        # 2. Extract indicators with parameters (only supported: sma, ema, rsi, atr)
        indicators: List[str] = []
        indicator_patterns = {
            "sma": r"sma\s*\(?(\d+)\)?|simple\s+moving\s+average\s*\(?(\d+)\)?|(\d+)[\s-]*day\s+sma",
            "ema": r"ema\s*\(?(\d+)\)?|exponential\s+moving\s+average\s*\(?(\d+)\)?|(\d+)[\s-]*day\s+ema",
            "rsi": r"rsi\s*\(?(\d+)\)?|relative\s+strength\s+index\s*\(?(\d+)\)?",
            "atr": r"atr\s*\(?(\d+)\)?|average\s+true\s+range\s*\(?(\d+)\)?",
            "macd": r"macd",
            "bollinger": r"bollinger\s*bands?|\bbb",
            "adx": r"adx|average\s+directional",
            "ichimoku": r"ichimoku",
            "stochrsi": r"stoch(?:astic)?\s*rsi",
            "cci": r"cci|commodity\s+channel\s+index",
        }
        default_periods = {
            "sma": 20,
            "ema": 20,
            "rsi": 14,
            "atr": 14,
            "adx": 14,
            "cci": 20,
        }

        for indicator, pattern in indicator_patterns.items():
            for match in re.finditer(pattern, lower_text):
                period = None
                for group in match.groups():
                    if group and group.isdigit():
                        period = int(group)
                        break
                if period is None:
                    period = default_periods.get(indicator)
                if period:
                    indicators.append(f"{indicator}({period})")
                else:
                    indicators.append(indicator)

        # If none of those were found, add basic defaults
        if not indicators:
            if any(
                word in lower_text
                for word in ["chart", "technical", "analysis", "trend"]
            ):
                indicators = ["sma(20)", "rsi(14)", "atr(14)"]
            elif any(word in lower_text for word in ["momentum", "oscillator"]):
                indicators = ["rsi(14)", "ema(20)"]
            else:
                indicators = ["sma(20)", "rsi(14)"]

        parsed["indicators"] = indicators

        # 3. Extract timeframe/interval
        interval_patterns = {
            "1m": r"\b1\s*(?:min|minute|m)\b",
            "5m": r"\b5\s*(?:min|minute|m)\b",
            "15m": r"\b15\s*(?:min|minute|m)\b",
            "30m": r"\b30\s*(?:min|minute|m)\b",
            "1h": r"\b1\s*(?:hour|hr|h)\b",
            "4h": r"\b4\s*(?:hour|hr|h)\b",
            "1d": r"\b(?:1\s*)?(?:day|daily|d)\b",
            "1w": r"\b(?:1\s*)?(?:week|weekly|w)\b",
            "1M": r"\b(?:1\s*)?(?:month|monthly|m)\b",
        }

        interval = "1h"  # Default
        for tf, pattern in interval_patterns.items():
            if re.search(pattern, lower_text):
                interval = tf
                break

        parsed["interval"] = interval

        # 4. Extract raw date strings (we’ll normalize next)
        start_date = None
        end_date = None
        lookback_days = None

        # 4a. Look for relative phrases (run on lower_text)
        time_patterns = {
            "days": r"(?:last|past)\s+(\d+)\s+days?|(\d+)\s+days?\s+ago",
            "weeks": r"(?:last|past)\s+(\d+)\s+weeks?|(\d+)\s+weeks?\s+ago",
            "months": r"(?:last|past)\s+(\d+)\s+months?|(\d+)\s+months?\s+ago",
            "years": r"(?:last|past)\s+(\d+)\s+years?|(\d+)\s+years?\s+ago",
            "ytd": r"\bytd\b|year\s+to\s+date",
        }

        for period_type, pattern in time_patterns.items():
            match = re.search(pattern, lower_text)
            if match:
                if period_type == "ytd":
                    start_date = "ytd"
                    end_date = "today"
                    break
                else:
                    number = match.group(1) or match.group(2)
                    if number:
                        number = int(number)
                        if period_type == "days":
                            start_date = f"-{number}d"
                            lookback_days = number
                        elif period_type == "weeks":
                            start_date = f"-{number}w"
                            lookback_days = number * 7
                        elif period_type == "months":
                            start_date = f"-{number}m"
                            lookback_days = number * 30  # Approximate
                        elif period_type == "years":
                            start_date = f"-{number}y"
                            lookback_days = number * 365  # Approximate
                        end_date = "today"
                        break

        # 4b. Look for absolute‐date patterns (run on original_text)
        absolute_date_patterns = [
            r"from\s+(\d{4}-\d{1,2}-\d{1,2})\s+to\s+(\d{4}-\d{1,2}-\d{1,2})",
            r"between\s+(\d{4}-\d{1,2}-\d{1,2})\s+and\s+(\d{4}-\d{1,2}-\d{1,2})",
            r"since\s+(\d{4}-\d{1,2}-\d{1,2})",
            r"after\s+(\d{4}-\d{1,2}-\d{1,2})",
            r"(\d{1,2})/(\d{1,2})/(\d{4})",  # MM/DD/YYYY
        ]
        if not (start_date and end_date):
            for pattern in absolute_date_patterns:
                match = re.search(pattern, original_text)
                if not match:
                    continue

                if pattern.startswith(r"from"):
                    start_date = match.group(1)
                    end_date = match.group(2)

                elif pattern.startswith(r"between"):
                    start_date = match.group(1)
                    end_date = match.group(2)

                elif pattern.startswith(r"since"):
                    start_date = match.group(1)
                    end_date = "today"

                elif pattern.startswith(r"after"):
                    start_date = match.group(1)
                    end_date = "today"

                else:  # MM/DD/YYYY
                    month, day, year = match.groups()
                    start_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                    end_date = "today"

                break  # stop on the first absolute-date match

        # 4c. If still no explicit start/end, set defaults based on interval
        if not start_date and not end_date:
            default_lookbacks = {
                "1m": 1,
                "5m": 3,
                "15m": 7,
                "30m": 14,
                "1h": 30,
                "4h": 90,
                "1d": 200,
                "1w": 365,
                "1M": 1825,
            }
            lookback_days = default_lookbacks.get(interval, 90)
            start_date = f"-{lookback_days}d"
            end_date = "today"

        # 4d. Now normalize via get_processed_date_range(...)
        #     (internally calls process_date_param(...) or get_default_date_range)
        processed_start, processed_end = get_processed_date_range(
            start_date=start_date,
            end_date=end_date,
            default_days_back=lookback_days or 90,
        )
        parsed["start_date"] = processed_start
        parsed["end_date"] = processed_end

        # 4e. Compute lookback string if not already set
        if lookback_days:
            parsed["lookback"] = f"{lookback_days}d"
        else:
            try:
                from datetime import datetime as _dt

                s = _dt.strptime(processed_start, "%Y-%m-%d")
                e = _dt.strptime(processed_end, "%Y-%m-%d")
                days_diff = (e - s).days
                parsed["lookback"] = f"{days_diff}d"
            except Exception:
                parsed["lookback"] = "90d"

        # Validate interval/lookback combo against API constraints
        QueryParser.validate_interval_lookback(
            parsed["interval"], parsed.get("lookback", "0d")
        )

        # 5. Detect macro/economic data needs (phrase-level)
        macro_phrases = [
            "yield curve",
            "spread",
            "recession",
            "inflation",
            "gdp",
            "unemployment",
            "fed",
            "interest rates",
            "treasury",
            "bonds",
            "economic",
            "cpi",
            "ppi",
            "fomc",
            "federal reserve",
        ]
        needs_macro = any(phrase in lower_text for phrase in macro_phrases)
        parsed["needs_macro"] = needs_macro

        # 6. Extract chart_type for LLM to describe (no actual rendering done)
        if any(word in lower_text for word in ["candlestick", "candle", "ohlc"]):
            chart_type = "candlestick"
        elif any(word in lower_text for word in ["line", "linear"]):
            chart_type = "line"
        else:
            chart_type = "candlestick"
        parsed["chart_type"] = chart_type

        # 7. Extract analysis_types for LLM to frame its narrative
        analysis_keywords = {
            "support_resistance": ["support", "resistance", "levels"],
            "trend_analysis": ["trend", "direction", "momentum"],
            "volatility": ["volatility", "vol", "variance"],
            "correlation": ["correlation", "corr", "relationship"],
            "comparison": ["compare", "vs", "versus", "against"],
        }
        analysis_types: List[str] = []
        for a_type, keywords in analysis_keywords.items():
            if any(keyword in lower_text for keyword in keywords):
                analysis_types.append(a_type)
        parsed["analysis_types"] = analysis_types or ["basic"]

        # 8. Extract comparison_tickers (case-insensitive)
        comparison_tickers: List[str] = []
        vs_patterns = [
            r"vs\s+([A-Za-z]{2,5})",
            r"versus\s+([A-Za-z]{2,5})",
            r"against\s+([A-Za-z]{2,5})",
            r"compare.*?([A-Za-z]{2,5})",
        ]
        for pattern in vs_patterns:
            for match in re.finditer(pattern, original_text, flags=re.IGNORECASE):
                comp_ticker = match.group(1).upper()
                if (
                    comp_ticker != parsed["ticker"]
                    and comp_ticker not in comparison_tickers
                ):
                    comparison_tickers.append(comp_ticker)
        parsed["comparison_tickers"] = comparison_tickers

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
            snippets.append("Requested indicators: " + ", ".join(query["indicators"]))

        snippets.append(
            "Available quantitative tools: fetch_market_data, fetch_yahoo_data, "
            "fetch_economic_indicator, fetch_interest_rates, fetch_yield_curve"
        )

        return "\n".join(snippets)

    def process_tool_result(
        self, tool_name: str, result: Any, tool_args: Dict[str, Any]
    ) -> Any:
        """
        Convert raw DataFrames into lightweight dict summaries and/or
        compute requested indicators.
        """
        if isinstance(result, pd.DataFrame) and not result.empty:
            if tool_name in {"fetch_market_data", "fetch_yahoo_data"}:
                df = result.copy()

                # ------- normalize column names --------------------------------
                standard_cols = {
                    "open": "Open",
                    "high": "High",
                    "low": "Low",
                    "close": "Close",
                    "volume": "Volume",
                }
                rename_map = {
                    col: standard_cols[col.lower()]
                    for col in df.columns
                    if col.lower() in standard_cols
                }
                if rename_map:
                    df = df.rename(columns=rename_map)

                # ------- core indicators (always computed) -------------------
                df["EMA50"] = ema(df["Close"], 50)
                df["RSI14"] = rsi(df["Close"], 14)
                df["ATR14"] = atr(df["High"], df["Low"], df["Close"], 14)
                df["ST"] = supertrend(
                    df["High"], df["Low"], df["Close"], period=10, mult=3
                )

                req = [ind.split("(")[0] for ind in tool_args.get("indicators", [])]

                if "macd" in req:
                    df = pd.concat([df, macd(df["Close"])], axis=1)
                if "bollinger" in req:
                    df = pd.concat([df, bollinger_bands(df["Close"])], axis=1)
                if "adx" in req:
                    df = pd.concat(
                        [df, adx(df["High"], df["Low"], df["Close"])], axis=1
                    )
                if "ichimoku" in req:
                    df = pd.concat(
                        [df, ichimoku(df["High"], df["Low"], df["Close"])], axis=1
                    )
                if "stochrsi" in req:
                    df = pd.concat([df, stochrsi(df["Close"])], axis=1)
                if "cci" in req:
                    df["CCI"] = cci(df["High"], df["Low"], df["Close"])

                # ------- optional AVWAP (needs volume + explicit ask) --------
                if "Volume" in df.columns and "avwap" in tool_args.get(
                    "indicators", []
                ):
                    df["AVWAP"] = avwap(df["Close"], df["Volume"])

                df = standardize_indicator_columns(df)

                # ------- Go/NoGo one-liner -----------------------------------
                go_flag = (
                    (df["Close"].iloc[-1] > df["EMA_50"].iloc[-1])
                    and (df["RSI_14"].iloc[-1] > 55)
                    and (df["Close"].iloc[-1] > df["ST"].iloc[-1])
                )

                return {
                    "latest_row": df.tail(1).to_dict(orient="records")[0],
                    "columns": list(df.columns),
                    "go_flag": "Go" if go_flag else "NoGo",
                }

        # ---------------------------------------------------------------
        # default passthrough (macro tools etc.)
        return result

    def generate_reply(self, messages, context=None):
        """
        Primary entry-point required by AutoGen-assistant agents.
        NOTE: once we bolt in the memory system, BaseAgent.process_with_tools()
            can merge context (e.g. prior trades, user preferences) into the system prompt.
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
