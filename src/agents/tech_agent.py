# Std libs
import logging
from typing import Any, Dict, List
import re
import json

# 3rd-party libs
import pandas as pd

# TODO numpy usage coming
import numpy as np

# project imports
from src.agents.base_agent import BaseAgent
from src.tools.tools import TECH_AGENT, get_tools_for_agent
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
try:
    from sparklines import sparklines as _sparklines
except ImportError:
    _sparklines = None
from src.utils.date_utils import (
    get_processed_date_range,
    resolve_anchor,
)
from src.utils.agent_utils import QueryParser

TECH_LLM_CONFIG = {
    "temperature": 0.15,  # deterministic outputs
    "max_tokens": 4096,
    "top_p": 0.9,
    # You can set frequency_penalty / presence_penalty if hallucinations crop up
}


class TechAgent(BaseAgent):
    """
    Agent that answers technical-analysis questions.

    Responsibilities
    ----------------
    • Retrieve market & macro data via registered tools.
    • Compute indicators locally.
    • Generate concise, data-driven explanations for the user.
    """

    def __init__(self, name: str = "TechAgent", memory_system=None):
        # Select only the tech-agent-tagged tools
        tools = get_tools_for_agent(TECH_AGENT)

        super().__init__(
            name=name,
            tools=tools,
            memory_system=memory_system,
            llm_config=TECH_LLM_CONFIG,
        )

        # Limit tool recursion
        # Temporarily increased for debugging
        self.max_tool_rounds = 2

        # Optional: attach a logger
        self.logger = logging.getLogger(self.__class__.__name__)
        self.last_query: Dict[str, Any] = {}

    @staticmethod
    def _get_max_indicator_window(indicators: List[str]) -> int:
        """Return the maximum lookback window required by the indicators."""
        defaults = {
            "sma": 20,
            "ema": 20,
            "rsi": 14,
            "atr": 14,
            "macd": 26,
            "bollinger": 20,
            "adx": 14,
            "ichimoku": 52,
            "stochrsi": 14,
            "cci": 20,
            "supertrend": 10,
        }
        max_win = 0
        for ind in indicators:
            base = ind.split("(")[0].lower()
            m = re.search(r"(\d+)", ind)
            if m:
                win = int(m.group(1))
            else:
                win = defaults.get(base, 0)
            if win > max_win:
                max_win = win
        return max_win

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
        anchor = None

        anchor_match = re.search(
            r"(?:from|since)\s+(\d{4}-\d{2}-\d{2}|earnings|fomc|year[_ ]?open)",
            lower_text,
        )
        if anchor_match:
            anchor = anchor_match.group(1).replace(" ", "_")

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

        # Extend lookback if indicators need more history
        max_period = self._get_max_indicator_window(indicators)
        if max_period:
            try:
                s_dt = pd.to_datetime(parsed["start_date"])
                e_dt = pd.to_datetime(parsed["end_date"])
                current_days = (e_dt - s_dt).days
                if current_days < max_period:
                    extra = int(max_period * 1.5)
                    new_start = e_dt - pd.Timedelta(days=extra)
                    parsed["start_date"] = new_start.strftime("%Y-%m-%d")
                    lookback_days = (e_dt - new_start).days
                    parsed["lookback"] = f"{lookback_days}d"
            except Exception:
                pass

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

        parsed["anchor"] = anchor

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
            snippets.append("Requested indicators: " +
                            ", ".join(query["indicators"]))

        snippets.append(
            "Available technical tools: fetch_market_data, fetch_yahoo_data, "
            "fetch_economic_indicator, fetch_interest_rates, fetch_yield_curve"
        )

        return "\n".join(snippets)

    def process_tool_result(
        self, tool_name: str, result: Any, tool_args: Dict[str, Any]
    ) -> Any:
        """Process and enrich raw tool results.

        Returns a dictionary with:
            - ``latest_row``: OHLCV + indicators for the most recent row
            - ``go_flag``: ``bool`` bullish/bearish signal
            - ``go_rationale``: list of bullet point reasons for ``go_flag``
            - ``risk``: dict with ``sharpe`` and ``drawdown`` (if calculable)
            - ``events``: e.g. upcoming earnings date
            - ``spark``: miniature sparkline of recent closes
            - ``timestamp``: ISO timestamp with timezone
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

                req = [ind.split("(")[0]
                       for ind in tool_args.get("indicators", [])]

                # Always compute MACD so downstream logic can rely on it
                macd_df = macd(df["Close"])
                # Use MACD histogram for strategy signals as requested by advisor
                # MACD histogram = MACD line - Signal line
                macd_df["MACD"] = macd_df["MACD_hist"]
                df = pd.concat([df, macd_df], axis=1)
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

                anchor_ts = None
                anchor_warning = None

                # ------- optional AVWAP (needs volume + explicit ask) --------
                if "Volume" in df.columns and "avwap" in tool_args.get(
                    "indicators", []
                ):
                    anchor_token = self.last_query.get(
                        "anchor") if hasattr(self, "last_query") else None
                    anchor_ts = None
                    anchor_warning = None
                    if anchor_token:
                        anchor_ts, anchor_warning = resolve_anchor(
                            df, anchor_token)
                    df["AVWAP"] = avwap(
                        df["Close"], df["Volume"], anchor_ts=anchor_ts)

                df = standardize_indicator_columns(df)

                # ------- MACD CROSS helpers ----------------------------------
                if "MACD" in df.columns:
                    df["MACD_prev"] = df["MACD"].shift(1)

                # ------- Go/NoGo one-liner -----------------------------------
                go_flag = (
                    (df["Close"].iloc[-1] > df["EMA_50"].iloc[-1])
                    and (df["RSI_14"].iloc[-1] > 55)
                    and (df["Close"].iloc[-1] > df["ST"].iloc[-1])
                )

                go_rationale = [
                    "Close above EMA_50"
                    if df["Close"].iloc[-1] > df["EMA_50"].iloc[-1]
                    else "Close below EMA_50",
                    "RSI above 55"
                    if df["RSI_14"].iloc[-1] > 55
                    else "RSI at or below 55",
                    "Close above Supertrend"
                    if df["Close"].iloc[-1] > df["ST"].iloc[-1]
                    else "Close below Supertrend",
                ]

                # ------- Risk metrics ---------------------------------------
                risk = {"sharpe": None, "drawdown": None}
                if len(df["Close"]) > 1:
                    returns = df["Close"].pct_change().dropna()
                    if not returns.empty and returns.std() != 0:
                        sharpe = (returns.mean() / returns.std()) * \
                            np.sqrt(252)
                    else:
                        sharpe = np.nan
                    roll_max = df["Close"].cummax()
                    drawdown = (df["Close"] / roll_max - 1.0).min()
                    risk = {
                        "sharpe": float(sharpe) if pd.notna(sharpe) else None,
                        "drawdown": float(drawdown) if pd.notna(drawdown) else None,
                    }

                # ------- Events ---------------------------------------------
                events: Dict[str, Any] = {}
                if "Earnings_Date" in df.columns and not df["Earnings_Date"].dropna().empty:
                    last_event = df["Earnings_Date"].dropna().iloc[-1]
                    events["earnings_date"] = pd.to_datetime(
                        last_event).isoformat()

                n = min(len(df), 20)
                if _sparklines is not None:
                    spark = _sparklines(df["Close"].tail(n).tolist())[0]
                else:
                    spark = "Sparklines not available"

                timestamp = pd.Timestamp.utcnow().isoformat()

                return {
                    "latest_row": df.tail(1).to_dict(orient="records")[0],
                    "go_flag": bool(go_flag),
                    "go_rationale": go_rationale,
                    "risk": risk,
                    "events": events,
                    "spark": spark,
                    "timestamp": timestamp,
                    "macd_today": float(df["MACD"].iloc[-1]) if "MACD" in df.columns else None,
                    "macd_yest": float(df["MACD_prev"].iloc[-1]) if "MACD_prev" in df.columns else None,
                    "anchor_ts": anchor_ts.isoformat() if anchor_ts is not None else None,
                    "anchor_warning": anchor_warning,
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
        self.last_query = query

        # --------------- Compose system prompt ----------------------------
        # Example system prompt instructing the LLM about returned fields
        sys_prompt = (
            "You are a technical research assistant. "
            "When useful, call tools to fetch data, then compute indicators "
            "locally before you answer.\n"
            "\nSupplementary context:\n"
            + self.format_supplementary_context(query)
            + "\n\nIMPORTANT: Use multiple tools if it improves the answer."
            + "\nTool outputs include: latest_row, go_flag, go_rationale, risk, events, spark, timestamp."
        )
        sys_prompt += (
            "\n\nAfter you have executed ONE tool call and received its result, "
            "STOP CALLING TOOLS and give your final answer."
        )

        # Add JSON format requirement for MACD responses
        sys_prompt += (
            "\n\nIMPORTANT: Your final response MUST be in valid JSON format with exactly these fields:"
            "\n{\"macd_today\": <float or null>, \"macd_yest\": <float or null>}"
            "\n\nExample response: {\"macd_today\": 1.23, \"macd_yest\": 0.98}"
            "\nIf MACD values cannot be calculated, use: {\"macd_today\": null, \"macd_yest\": null}"
            "\n\nDo NOT include any text before or after the JSON. Return ONLY the JSON object."
        )

        # --------------- Forward to BaseAgent’s tool-aware pipeline -------
        raw_response = self.process_with_tools(last_msg, sys_prompt)

        # Extract and validate MACD JSON response
        try:
            # If it's already a dict, check for MACD values
            if isinstance(raw_response, dict):
                if 'macd_today' in raw_response and 'macd_yest' in raw_response:
                    return json.dumps(raw_response)
                else:
                    # Try to extract MACD from tool results
                    macd_today = raw_response.get('macd_today')
                    macd_yest = raw_response.get('macd_yest')
                    result = {
                        "macd_today": float(macd_today) if macd_today is not None else None,
                        "macd_yest": float(macd_yest) if macd_yest is not None else None
                    }
                    print(f"\nTechnical Analysis Result:")
                    print(f"  MACD Today: {result['macd_today']:.4f}" if result['macd_today']
                          is not None else "  MACD Today: Not available")
                    print(f"  MACD Yesterday: {result['macd_yest']:.4f}" if result['macd_yest']
                          is not None else "  MACD Yesterday: Not available")
                    return json.dumps(result)

            # Try to parse as JSON string
            response_str = str(raw_response).strip()

            # Remove any text before the first '{' and after the last '}'
            start_idx = response_str.find('{')
            end_idx = response_str.rfind('}')

            if start_idx != -1 and end_idx != -1:
                json_str = response_str[start_idx:end_idx + 1]
                parsed = json.loads(json_str)

                # Validate required fields
                if 'macd_today' in parsed and 'macd_yest' in parsed:
                    # Ensure proper types
                    result = {
                        "macd_today": float(parsed['macd_today']) if parsed['macd_today'] is not None else None,
                        "macd_yest": float(parsed['macd_yest']) if parsed['macd_yest'] is not None else None
                    }

                    print(f"\nTechnical Analysis Result:")
                    print(f"  MACD Today: {result['macd_today']:.4f}" if result['macd_today']
                          is not None else "  MACD Today: Not available")
                    print(f"  MACD Yesterday: {result['macd_yest']:.4f}" if result['macd_yest']
                          is not None else "  MACD Yesterday: Not available")

                    return json.dumps(result)

            # If parsing fails, return default
            print(
                f"Warning: Failed to parse MACD values from response, returning null values")
            default_response = {"macd_today": None, "macd_yest": None}
            print(f"\nDefault Technical Result:")
            print(f"  MACD Today: Not available")
            print(f"  MACD Yesterday: Not available")
            return json.dumps(default_response)

        except Exception as e:
            print(f"Error processing response: {str(e)}")
            default_response = {"macd_today": None, "macd_yest": None}
            print(f"\nDefault Technical Result (due to error):")
            print(f"  MACD Today: Not available")
            print(f"  MACD Yesterday: Not available")
            return json.dumps(default_response)
