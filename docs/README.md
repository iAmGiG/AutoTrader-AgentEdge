# Core Components

This folder contains the main documentation for the research prototype. The
project is built around a **multi‑agent system** with shared memory and a set of
data–retrieval tools. Below is a quick overview of what is implemented today.

## Hybrid‑Head

Neural architecture combining attention and state space models. The current code
uses this design indirectly through pre‑trained models to keep memory usage low.

## Memory System

Layered memory implementation with a RadixAttention cache. Agents can store and
retrieve conversation context or intermediate results from this system.

## Agent Framework

The framework defines four specialized agents.  At this stage the Sentiment and
Tech agents are operational, while the Risk and Strategy agents are still
experimental.

1. **Sentiment Agent** – fetches financial news and analyses sentiment using LLM
   function calling.  Supports date‑range and ticker queries through a unified
   tool.
2. **Tech Agent** – performs technical analysis with indicators such as EMA,
   MACD and ATR on market data retrieved from common APIs.
3. **Risk Agent** – prototype utilities for scanning SEC filings.
4. **Strategy Agent** – early orchestrator that combines other agents’ output.

Agents communicate via a lightweight orchestrator and a message bus. Each agent
only sees the tools it needs, reducing prompt noise and API usage.

## Reference Documentation

- [AutoGen Core Reference](autogen_core_reference/README.md) – Reference
  documentation for AutoGen Core 0.6.x components used in RH2MAS
- [Status Summary: Sentiment and Tech Agents](status_summary_sentiment_tech_agents.md) – High-level overview of the active agents and their limitations

