# RH2MAS: Reflective Hybrid-Head Multi-Agent System

## Overview

RH2MAS is a research project developing an LLM-based investment research system that combines hybrid neural architectures with reflective learning mechanisms. The system integrates:

- Hybrid-Head Architecture (based on Hymba)
- Layered Memory System
- Dynamic Risk Analysis
- Verbal Reinforcement Learning

## Project Structure

- /docs           # Research notes
- -/architecture  # System design documentation
- -/research      # Research progress and findings
- -/indicator_library.md  # Technical indicator definitions
- /src
- -/agents
- -/core          # Core architecture components
- -/tools         # Common utilities and agent tools
- -/tests          # Test suites

## Project Status

This repository is under active research development. See our [Research Documentation](docs/research/README.md) for current progress.

## Documentation

- Architecture Documentation
- Research Progress
- API Documentation

## Configuration

Secrets such as API keys are no longer loaded from `config/config.json`. Instead
the project reads configuration values from environment variables. You can store
these secrets using the [Codex CLI](https://github.com/openai/codex) and set the
`envKey` field in `~/.codex/config.json` to match the lowercase variable names
used by the code (e.g. `open_ai_key`, `newsapi_key`).

## Research Goals

1. Efficient hybrid processing for financial data
2. Scalable multi-agent coordination
3. Adaptive risk profiling
4. Verifiable decision-making processes

## Research Papers

This project builds upon:

- SGLang (2024): Structured Language Model Programs
- Hymba (2024): Hybrid-head Architecture
- FinMem (2023): Layered Memory Systems
- FinCon (2024): Hierarchical Agent Systems with VRL
- [Additioanl papers from HF](https://huggingface.co/collections/m-ric/agents-65ba776fbd9e29f771c07d4e)

### License

This project is licensed under AGPL-3.0 - see the LICENSE file for details.
