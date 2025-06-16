# RH2MAS Architecture

## Components

- **Hybrid Neural Core** – combines attention and state‑space models for
  efficient sequence processing.
- **Memory System** – layered storage with RadixAttention caching.
- **Agent Framework** – base classes for the Sentiment and Tech agents (active),
  with experimental Risk and Strategy agents under development.
- **Risk Analysis Engine** – utilities for parsing SEC filings and calculating
  exposure (prototype stage).
- **Agent Orchestrator** – routes messages among agents via a shared message bus
  and ensures each agent only sees the tools it requires.

## Design Principles

1. Efficient parallel processing
2. Layered memory management
3. Explainable decision-making
4. Dynamic risk adaptation
5. Clear separation of concerns between agents
