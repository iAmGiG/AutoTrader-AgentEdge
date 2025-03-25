# Assume we have SentimentAgent, StrategyAgent, etc.
from src.agents.sentiment_agent import SentimentAgent
from src.agents.strategy_agent import StrategyAgent
from src.core.agent_orchestrator import AgentOrchestrator
from src.core.memory.memory_system import MemorySystem
# from sentiment_agent import SentimentAgent
# from strategy_agent import StrategyAgent
# Example usage (in some main.py):
if __name__ == "__main__":

    memory_sys = MemorySystem(ephemeral_ttl=10)
    agent_config_list = [
        {
            "class": SentimentAgent,
            "name": "SentimentAgent",
            "config": {
                "sentiment_threshold": 0.5
            }
        },
        {
            "class": StrategyAgent,
            "name": "StrategyAgent",
            "config": {
                "strategy_type": "long_short"
            }
        }
    ]

    orchestrator = AgentOrchestrator(agent_config_list, memory_sys)
    user_message = "What is the market outlook for next week?"
    final_result = orchestrator.process_message(user_message)

    print("=== Final Aggregated Response ===")
    print(final_result)

    # Optionally store the decision in memory
    orchestrator.store_decision("last_decision", final_result)
