# Documentation Structure

This directory contains all technical documentation for the RH2MAS project.

## Current Structure

- **architecture/** - System design and technical architecture
  - Components, data flow, orchestration patterns
  - UML diagrams and system design documents
  
- **implementation/** - Implementation details and guides
  - **agents/** - Agent-specific documentation
    - `sentiment_agent.md` - Sentiment analysis with VXX fallback
    - `technical_agent.md` - Technical indicators and MACD
    - `strategy_agent.md` - Trading strategy implementation
    - `coordinator_agent.md` - Multi-agent orchestration
  - **tools/** - Tool and indicator documentation
  - **strategies/** - Trading strategy documentation
  
- **autogen_core_reference/** - AutoGen 0.6.x reference docs
  - Core components, best practices, examples
  
- **research/** - Research notes and explorations
  - Framework comparisons, tool evaluations

## Recent Updates (2025-07-11)

- Fixed MACD calculation in technical agent
- Added news caching to sentiment agent
- Consolidated agent documentation
- Updated for enhanced strategy (sentiment >= 0)

## Quick Links

- [System Architecture](architecture/README.md)
- [Technical Agent Guide](implementation/agents/technical_agent.md)
- [Sentiment Agent Guide](implementation/agents/sentiment_agent.md)
- [Strategy Documentation](implementation/strategies/strategy_v2_documentation.md)
