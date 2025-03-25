# decision_engine.py

from typing import Dict, Any, Optional
import logging


class DecisionEngine:
    """
    A simple decision engine that aggregates agent responses and applies
    decision logic to produce a final outcome.
    """

    def __init__(self, config: Dict[str, Any], memory_system: Optional[Any] = None):
        """
        :param config: Dictionary for decision engine settings (weights, thresholds, etc.).
        :param memory_system: Optional memory system for storing/retrieving decision context.
        """
        self.config = config
        self.memory_system = memory_system
        self.logger = logging.getLogger(self.__class__.__name__)
        # Example: read weighting or thresholds from config
        self.agent_weights = config.get("agent_weights", {})
        self.decision_threshold = config.get("decision_threshold", 0.0)

    def decide(self, agent_responses: Dict[str, str]) -> str:
        """
        Combines agent responses and applies logic (voting, weighting, etc.)
        to arrive at a final decision or recommendation.

        :param agent_responses: Dict mapping agent_name -> response_text
        :return: A string representing the final decision or outcome.
        """
        # 1. Parse each agent’s response to extract signals or structured data.
        #    For now, let's keep it simple and just do a naive "majority" or "weighting" approach.

        scores = {}
        for agent_name, response_text in agent_responses.items():
            # In a more complex system, parse numeric signals from the response
            # e.g., sentiment = self._extract_sentiment(response_text)
            # or risk_score = self._extract_risk_score(response_text)
            # For this demo, just treat length of text as a "score."
            score = len(response_text)
            weight = self.agent_weights.get(agent_name, 1.0)
            weighted_score = score * weight
            scores[agent_name] = weighted_score

        # 2. Combine scores into a single metric.
        total_score = sum(scores.values())

        # 3. Compare total_score against some threshold or produce a structured result.
        if total_score >= self.decision_threshold:
            final_decision = f"Positive Decision (score={total_score:.2f})"
        else:
            final_decision = f"Negative Decision (score={total_score:.2f})"

        # 4. (Optional) Store the decision or intermediate signals in memory.
        if self.memory_system:
            self._store_decision_in_memory(agent_responses, final_decision)

        self.logger.info(f"DecisionEngine: Final decision => {final_decision}")
        return final_decision

    def _store_decision_in_memory(self, agent_responses: Dict[str, str], final_decision: str):
        """
        Store the final decision (and possibly agent responses) in the memory system
        for future retrieval or reflection.
        """
        # For example, store in context memory:
        data_to_store = {
            "agent_responses": agent_responses,
            "final_decision": final_decision
        }
        # Key naming is up to you; could be a timestamp or UUID
        key = "last_decision"
        self.memory_system.store_data(key, data_to_store, layer="context")
        self.logger.info(
            f"DecisionEngine: Stored decision in memory under key='{key}'.")

    # -- Optionally, you can add more helper methods to parse numeric signals, etc. --
    # def _extract_sentiment(self, response_text: str) -> float:
    #     # parse sentiment from text
    #     return some_sentiment_score
    #
    # def _extract_risk_score(self, response_text: str) -> float:
    #     # parse risk from text
    #     return some_risk_score
