"""
agent_orchestrator.py
"""

from typing import List, Dict, Any
from agents.base_agent import BaseAgent
from tools.memory.memory_system import MemorySystem
from core.decision_engine import DecisionEngine


class AgentOrchestrator:
    """
    A minimal orchestrator that initializes, manages, and coordinates 
    multiple specialized agents. It routes incoming messages, gathers 
    responses, and applies a simple decision or aggregation step.
    """

    def __init__(self,
                 agent_configs: List[Dict[str, Any]],
                 memory_system: MemorySystem,
                 decision_engine_config: Dict[str, Any]):
        """
        :param agent_configs: List of config dictionaries, each specifying 
                              'class' (the agent class), 'name', and other 
                              config keys needed to instantiate the agent.
        :param memory_system: Shared MemorySystem instance.
        """
        self.memory_system = memory_system
        self.agents = self._initialize_agents(agent_configs)
        self.decision_engine = DecisionEngine(
            decision_engine_config, memory_system)

    def _initialize_agents(self, agent_configs: List[Dict[str, Any]]) -> List[BaseAgent]:
        agents = []
        for cfg in agent_configs:
            # Dynamically load the agent class (passed in via config).
            agent_class = cfg["class"]
            name = cfg["name"]
            config_dict = cfg.get("config", {})
            agent = agent_class(name=name, config=config_dict,
                                memory_system=self.memory_system)
            agents.append(agent)
        return agents

    def process_message(self, message: str) -> str:
        """
        Main entry point for orchestrating agent interactions.
        1. Pass the message to each agent.
        2. Collect responses.
        3. Apply a decision function to produce the final output.
        """
        # 1. Collect each agent's response
        responses = {}
        for agent in self.agents:
            try:
                agent_response = agent.handle_message(message)
                responses[agent.name] = agent_response
            except Exception as e:
                responses[agent.name] = f"[ERROR: {str(e)}]"

        # 2. Use the DecisionEngine to produce a final outcome
        final_decision = self.decision_engine.decide(responses)

        return final_decision

    def _simple_decision_function(self, agent_responses: List[tuple]) -> str:
        """
        Placeholder logic to combine agent outputs. 
        Right now it just merges them. In a real system, 
        you might apply risk weighting, majority voting, etc.
        """
        combined = "\n".join(
            [f"{name} => {resp}" for (name, resp) in agent_responses]
        )
        return f"Collected Responses:\n{combined}"

    def store_decision(self, key: str, decision_data: Any):
        """
        Optionally store the final decision or aggregated result 
        in the memory system for future reference.
        """
        self.memory_system.store_data(key, decision_data, layer="context")

    def retrieve_decision(self, key: str) -> Any:
        """
        Retrieve a past decision from the memory system.
        """
        return self.memory_system.retrieve_data(key, layer="context")
