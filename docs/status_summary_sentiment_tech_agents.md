# Status Summary: Sentiment and Tech Agents

This document provides a brief overview of the two active agents in RH2MAS and their current development status. It is intended for project stakeholders evaluating the next experimental stage. Details are subject to change as the system evolves.

## 1. Executive Summary

- **Purpose** – Outline the present capabilities of the Sentiment and Tech agents.
- **Status** – Both agents are functional and routinely tested, while Risk and Strategy agents remain in prototype form.
- **Current Milestone** – Preparing for an initial evaluation of these agents' analytic output in a closed environment.

## 2. Current Version and Scope of Functionality

### Sentiment Agent

- Retrieves news articles by ticker and date range using an aggregated news service.
- Returns a short sentiment label for each article (positive, neutral, negative).

**Known limitations**

- Coverage depends on the external APIs included in the aggregator.
- Long date ranges may produce incomplete results.

### Tech Agent

- Fetches historical price data and computes standard indicators such as EMA, MACD, RSI and ATR.
- Designed for analytical insights only; does not place trades or manage portfolios.

**Known limitations**

- Intraday data is not always available for every ticker.
- Multi-ticker comparisons are not yet supported.

### Technical Notes

- Both agents run as part of a multi-agent orchestrator executed from the command line.
- Interaction is via text prompts; results are returned in JSON or table form.

These notes capture the current state of development. Capabilities and interfaces may change as the project progresses.
