"""Agent Factory Pattern for AutoGen-Trader.

Centralized agent creation with typed enums, configuration dataclasses,
and registry tracking. Ported from gex-llm-patterns and adapted for
trading system agents.

Issue #390: Agent Factory & Event Bus Infrastructure

Benefits:
- Centralized agent creation and configuration
- Easy to add new agent types without modifying base classes
- Better testability through dependency injection
- Integration with TradingConfig for parameter management
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from config_defaults.trading_config import TradingConfig

logger = logging.getLogger(__name__)


class AgentType(Enum):
    """Available agent types in the AutoGen-Trader system."""

    SCANNER = "scanner"
    VOTER = "voter"
    RISK = "risk"
    EXECUTOR = "executor"
    PORTFOLIO = "portfolio"  # Future: Issue #333
    ORCHESTRATOR = "orchestrator"


@dataclass
class AgentConfig:
    """Configuration for agent creation.

    Attributes:
        agent_type: Type of agent to create
        name: Unique agent identifier
        description: Human-readable agent description
        model_name: OpenAI model to use
        temperature: LLM temperature for consistency
        max_tokens: Maximum tokens for responses
        timeout: Request timeout in seconds
        tools: List of tool names available to agent
        extra_config: Additional agent-specific configuration
    """

    agent_type: AgentType
    name: str
    description: str = ""
    model_name: str = "gpt-4o-mini"
    temperature: float = 0.2
    max_tokens: int = 4096
    timeout: int = 120
    tools: List[str] = field(default_factory=list)
    extra_config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentInstance:
    """Wrapper for created agent instances with metadata.

    Tracks agent lifecycle and provides access to both the agent
    and its configuration for debugging and monitoring.
    """

    agent: Any
    config: AgentConfig
    agent_type: AgentType
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            from src.utils.date_utils import now_iso

            self.created_at = now_iso()


class AgentFactory:
    """Factory for creating AutoGen-Trader agents.

    Singleton pattern ensures consistent agent creation across the system.
    Integrates with TradingConfig for parameter management.

    Example usage:
        factory = get_agent_factory()
        voter = factory.create(AgentType.VOTER)
        scanner = factory.create(AgentType.SCANNER, config_override={"timeout": 60})
    """

    _instance: Optional["AgentFactory"] = None
    _creators: Dict[AgentType, Callable] = {}

    def __new__(cls):
        """Singleton pattern for factory."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the factory with default creators."""
        if self._initialized:
            return

        self._trading_config = TradingConfig()
        self._agent_configs: Dict[AgentType, AgentConfig] = {}
        self._created_agents: List[AgentInstance] = []

        # Register default creators
        self._register_default_creators()
        self._load_config_defaults()
        self._initialized = True

        logger.info("AgentFactory initialized")

    def _register_default_creators(self):
        """Register default agent creator functions."""
        self._creators = {
            AgentType.SCANNER: self._create_scanner_agent,
            AgentType.VOTER: self._create_voter_agent,
            AgentType.RISK: self._create_risk_agent,
            AgentType.EXECUTOR: self._create_executor_agent,
            AgentType.PORTFOLIO: self._create_portfolio_agent,
            AgentType.ORCHESTRATOR: self._create_orchestrator,
        }

    def _load_config_defaults(self):
        """Load default configurations for each agent type."""
        # Get MACD/RSI config for voter
        macd_config = self._trading_config.get_macd_config()
        rsi_config = self._trading_config.get_rsi_config()

        self._agent_configs = {
            AgentType.SCANNER: AgentConfig(
                agent_type=AgentType.SCANNER,
                name="scanner_agent",
                description="Multi-ticker market scanning with technical analysis",
                model_name="gpt-4o-mini",
                temperature=0.2,
            ),
            AgentType.VOTER: AgentConfig(
                agent_type=AgentType.VOTER,
                name="voter_agent",
                description="MACD+RSI voting decision agent (0.856 Sharpe validated)",
                model_name="gpt-4o-mini",
                temperature=0.2,
                extra_config={
                    "macd_params": {
                        "fast": macd_config.fast,
                        "slow": macd_config.slow,
                        "signal": macd_config.signal,
                    },
                    "rsi_params": {
                        "period": rsi_config.period,
                        "oversold": rsi_config.oversold,
                        "overbought": rsi_config.overbought,
                    },
                },
            ),
            AgentType.RISK: AgentConfig(
                agent_type=AgentType.RISK,
                name="risk_agent",
                description="Portfolio risk management and position sizing",
                model_name="gpt-4o-mini",
                temperature=0.1,  # Lower for more consistent risk decisions
            ),
            AgentType.EXECUTOR: AgentConfig(
                agent_type=AgentType.EXECUTOR,
                name="executor_agent",
                description="Trade execution coordination with Alpaca",
                model_name="gpt-4o-mini",
                temperature=0.1,
            ),
            AgentType.PORTFOLIO: AgentConfig(
                agent_type=AgentType.PORTFOLIO,
                name="portfolio_agent",
                description="Portfolio management and rebalancing (Issue #333)",
                model_name="gpt-4o-mini",
                temperature=0.2,
            ),
            AgentType.ORCHESTRATOR: AgentConfig(
                agent_type=AgentType.ORCHESTRATOR,
                name="trading_orchestrator",
                description="Multi-agent coordination and workflow management",
                model_name="gpt-4o-mini",
                temperature=0.2,
            ),
        }

        logger.info(f"Loaded config defaults for {len(self._agent_configs)} agent types")

    def register_creator(
        self, agent_type: AgentType, creator: Callable[[AgentConfig], Any]
    ) -> None:
        """Register a custom creator function for an agent type.

        Args:
            agent_type: The type of agent
            creator: Function that takes AgentConfig and returns an agent instance
        """
        self._creators[agent_type] = creator
        logger.info(f"Registered custom creator for {agent_type.value}")

    def create(
        self,
        agent_type: AgentType,
        config_override: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> AgentInstance:
        """Create an agent of the specified type.

        Args:
            agent_type: Type of agent to create
            config_override: Optional config values to override defaults
            **kwargs: Additional arguments passed to agent constructor

        Returns:
            AgentInstance wrapping the created agent

        Raises:
            ValueError: If no creator registered for agent type
        """
        if agent_type not in self._creators:
            raise ValueError(f"No creator registered for agent type: {agent_type}")

        # Get base config
        base_config = self._agent_configs.get(
            agent_type, AgentConfig(agent_type=agent_type, name=agent_type.value)
        )

        # Apply overrides
        if config_override:
            config = self._merge_config(base_config, config_override)
        else:
            config = base_config

        # Merge kwargs into extra_config
        if kwargs:
            config.extra_config.update(kwargs)

        # Create the agent
        try:
            creator = self._creators[agent_type]
            agent = creator(config)

            instance = AgentInstance(agent=agent, config=config, agent_type=agent_type)
            self._created_agents.append(instance)

            logger.info(f"Created {agent_type.value} agent: {config.name}")
            return instance

        except Exception as e:
            logger.error(f"Failed to create {agent_type.value} agent: {e}")
            raise

    def _merge_config(self, base: AgentConfig, overrides: Dict[str, Any]) -> AgentConfig:
        """Merge override values into base config."""
        return AgentConfig(
            agent_type=base.agent_type,
            name=overrides.get("name", base.name),
            description=overrides.get("description", base.description),
            model_name=overrides.get("model_name", base.model_name),
            temperature=overrides.get("temperature", base.temperature),
            max_tokens=overrides.get("max_tokens", base.max_tokens),
            timeout=overrides.get("timeout", base.timeout),
            tools=overrides.get("tools", base.tools),
            extra_config={**base.extra_config, **overrides.get("extra_config", {})},
        )

    # --- Agent Creator Methods ---

    def _create_scanner_agent(self, config: AgentConfig) -> Any:
        """Create a ScannerAgent."""
        from src.autogen_agents.scanner_agent import create_scanner_agent

        return create_scanner_agent(name=config.name)

    def _create_voter_agent(self, config: AgentConfig) -> Any:
        """Create a VoterAgent with MACD+RSI parameters."""
        from src.autogen_agents.voter_agent import create_voter_agent

        return create_voter_agent(
            name=config.name,
            macd_params=config.extra_config.get("macd_params"),
            rsi_params=config.extra_config.get("rsi_params"),
        )

    def _create_risk_agent(self, config: AgentConfig) -> Any:
        """Create a RiskAgent."""
        from src.autogen_agents.risk_agent import create_risk_agent

        return create_risk_agent(name=config.name)

    def _create_executor_agent(self, config: AgentConfig) -> Any:
        """Create an ExecutorAgent."""
        from src.autogen_agents.executor_agent import create_executor_agent

        initial_capital = config.extra_config.get("initial_capital", 100000)
        return create_executor_agent(initial_capital=initial_capital)

    def _create_portfolio_agent(self, config: AgentConfig) -> Any:
        """Create a PortfolioAgent (placeholder for Issue #333)."""
        # TODO: Implement when Issue #333 is completed
        logger.warning("PortfolioAgent not yet implemented (Issue #333)")
        return None

    def _create_orchestrator(self, config: AgentConfig) -> Any:
        """Create a TradingOrchestrator."""
        from src.autogen_agents.trading_orchestrator import create_trading_orchestrator

        initial_capital = config.extra_config.get("initial_capital", 100000)
        return create_trading_orchestrator(initial_capital=initial_capital)

    # --- Utility Methods ---

    def get_config(self, agent_type: AgentType) -> AgentConfig:
        """Get the current configuration for an agent type."""
        return self._agent_configs.get(
            agent_type, AgentConfig(agent_type=agent_type, name=agent_type.value)
        )

    def set_config(self, agent_type: AgentType, config: AgentConfig) -> None:
        """Set configuration for an agent type."""
        self._agent_configs[agent_type] = config
        logger.info(f"Updated config for {agent_type.value}")

    def get_created_agents(self) -> List[AgentInstance]:
        """Get list of all agents created by this factory."""
        return self._created_agents.copy()

    def get_agent_types(self) -> List[AgentType]:
        """Get list of available agent types."""
        return list(self._creators.keys())

    def clear_created_agents(self) -> None:
        """Clear the list of created agents (for testing)."""
        self._created_agents.clear()
        logger.info("Cleared created agents list")

    def get_factory_stats(self) -> Dict[str, Any]:
        """Get statistics about the factory."""
        type_counts: Dict[str, int] = {}
        for instance in self._created_agents:
            type_name = instance.agent_type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1

        return {
            "total_agents_created": len(self._created_agents),
            "registered_types": [t.value for t in self._creators.keys()],
            "agents_by_type": type_counts,
        }

    def reset(self) -> None:
        """Reset factory state (for testing)."""
        self._created_agents.clear()
        self._load_config_defaults()
        logger.info("AgentFactory reset")


# Module-level convenience functions
_factory: Optional[AgentFactory] = None


def get_agent_factory() -> AgentFactory:
    """Get the singleton AgentFactory instance."""
    global _factory
    if _factory is None:
        _factory = AgentFactory()
    return _factory


def create_agent(
    agent_type: AgentType,
    config_override: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> AgentInstance:
    """Convenience function to create an agent.

    Args:
        agent_type: Type of agent to create
        config_override: Optional config overrides
        **kwargs: Additional arguments

    Returns:
        AgentInstance wrapping the created agent
    """
    return get_agent_factory().create(agent_type, config_override, **kwargs)


# Convenience functions for common agent types
def create_voter(
    macd_params: Optional[Dict[str, int]] = None,
    rsi_params: Optional[Dict[str, int]] = None,
) -> AgentInstance:
    """Create a VoterAgent with optional parameter overrides.

    Args:
        macd_params: MACD parameters {"fast": 13, "slow": 34, "signal": 8}
        rsi_params: RSI parameters {"period": 14, "oversold": 30, "overbought": 70}

    Returns:
        AgentInstance wrapping the VoterAgent
    """
    extra_config = {}
    if macd_params:
        extra_config["macd_params"] = macd_params
    if rsi_params:
        extra_config["rsi_params"] = rsi_params

    return create_agent(
        AgentType.VOTER,
        config_override={"extra_config": extra_config} if extra_config else None,
    )


def create_scanner() -> AgentInstance:
    """Create a ScannerAgent with default configuration."""
    return create_agent(AgentType.SCANNER)


def create_risk() -> AgentInstance:
    """Create a RiskAgent with default configuration."""
    return create_agent(AgentType.RISK)


def create_executor(initial_capital: float = 100000) -> AgentInstance:
    """Create an ExecutorAgent with specified initial capital.

    Args:
        initial_capital: Starting capital for paper trading

    Returns:
        AgentInstance wrapping the ExecutorAgent
    """
    return create_agent(
        AgentType.EXECUTOR,
        config_override={"extra_config": {"initial_capital": initial_capital}},
    )


def create_orchestrator(initial_capital: float = 100000) -> AgentInstance:
    """Create a TradingOrchestrator with specified initial capital.

    Args:
        initial_capital: Starting capital for paper trading

    Returns:
        AgentInstance wrapping the TradingOrchestrator
    """
    return create_agent(
        AgentType.ORCHESTRATOR,
        config_override={"extra_config": {"initial_capital": initial_capital}},
    )
