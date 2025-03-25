# AgentOrchestrator

- multiple agents each get input from memory, produce an “analysis piece,” and then “debate” or combine results.

## Terminology: “Decision Engine” vs. “Agent Controller”

- are basically synonyms in this architecture. We might call it agent_orchestrator.py or decision_engine.py.

## Core responsibilities

- Initialize all specialized agents with their configs and memory references.
- Route messages to each agent in the correct sequence.
- Gather agent outputs (sentiment, strategy suggestions, etc.).
- Apply decision logic (majority vote, weighting scheme, risk scoring, etc.).
- Store outcome or final decision in memory.

## Example flow

- Input from user or environment → Orchestrator.
- Orchestrator calls SentimentAgent.handle_message(), StrategyAgent.handle_message(), etc.
- Orchestrator merges results with a weighting or rule-based approach.
- Orchestrator stores final decision → memory.
- Architecture Next Step: Write the minimal orchestration code so we can orchestrate a few simple test interactions among the agents and memory system.

### Agent Registration

1. Agents
    - We pass each agent’s class (e.g. SentimentAgent) via a config list so the orchestrator can instantiate them. This ensures it’s easy to add new agents.
2. Error Handling

    - A try/except around agent calls ensures no single agent crash can break the entire orchestrator.
3. Decision Logic Stub

    - Currently _simple_decision_function just merges the agents’ responses. In a real system, you might do more advanced weighting (like a sentiment-based threshold, risk weighting, or majority vote).
4. Memory Integration

    - We show how you can store or retrieve final outcomes from the memory system (layer="context").
