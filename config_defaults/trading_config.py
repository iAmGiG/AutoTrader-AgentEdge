"""
Trading Configuration Management
Centralized configuration for all trading parameters.
"""

import json
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass

try:
    import yaml
except ImportError:
    yaml = None


@dataclass
class MACDConfig:
    """MACD indicator configuration."""
    fast: int = 13
    slow: int = 34
    signal: int = 8


@dataclass
class RSIConfig:
    """RSI indicator configuration."""
    period: int = 14
    oversold: int = 30
    overbought: int = 70


@dataclass
class ExitConfig:
    """Exit strategy configuration."""
    take_profit: float
    stop_loss: float
    description: str
    expected_value_50wr: float
    breakeven_win_rate: float


class TradingConfig:
    """
    Trading configuration manager.

    Benefits of configuration system:
    1. Easy parameter tuning without code changes
    2. A/B testing different configurations
    3. Environment-specific settings (dev/test/prod)
    4. Audit trail of parameter changes
    5. Consistent configuration across all components
    """

    def __init__(self, config_file: str = None):
        """Load configuration from file or use defaults."""
        if config_file is None:
            config_path = os.path.dirname(__file__)
            # Try YAML first, fallback to JSON
            yaml_file = os.path.join(config_path, 'trading_config.yaml')
            json_file = os.path.join(config_path, 'trading_config.json')

            if os.path.exists(yaml_file):
                config_file = yaml_file
            elif os.path.exists(json_file):
                config_file = json_file
            else:
                config_file = yaml_file  # Default to YAML for new installs

        self.config_file = config_file
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        """Load configuration from YAML or JSON file."""
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r', encoding='utf-8') as f:
                if self.config_file.endswith('.yaml') or self.config_file.endswith('.yml'):
                    if yaml is None:
                        raise ImportError("PyYAML not installed. Install with: pip install pyyaml")
                    return yaml.safe_load(f)
                else:
                    return json.load(f)
        else:
            # Return default configuration
            return self._get_default_config()

    def _get_default_config(self) -> Dict:
        """Get default configuration."""
        return {
            "strategy_parameters": {
                "macd": {"fast": 13, "slow": 34, "signal": 8},
                "rsi": {"period": 14, "oversold": 30, "overbought": 70},
                "exits": {
                    "balanced": {
                        "take_profit": 0.08,
                        "stop_loss": 0.05,
                        "expected_value_50wr": 0.015,
                        "breakeven_win_rate": 0.385
                    },
                    "default": "balanced"
                }
            }
        }

    def get_macd_config(self) -> MACDConfig:
        """Get MACD configuration."""
        params = self.config['strategy_parameters']['macd']
        return MACDConfig(
            fast=params['fast'],
            slow=params['slow'],
            signal=params['signal']
        )

    def get_rsi_config(self) -> RSIConfig:
        """Get RSI configuration."""
        params = self.config['strategy_parameters']['rsi']
        return RSIConfig(
            period=params['period'],
            oversold=params['oversold'],
            overbought=params['overbought']
        )

    def get_exit_config(self, strategy: str = None) -> ExitConfig:
        """Get exit strategy configuration."""
        exits = self.config['strategy_parameters']['exits']

        if strategy is None:
            strategy = exits.get('default', 'balanced')

        if strategy not in exits:
            strategy = 'balanced'  # Fallback to balanced

        params = exits[strategy]
        return ExitConfig(
            take_profit=params['take_profit'],
            stop_loss=params['stop_loss'],
            description=params.get('description', ''),
            expected_value_50wr=params.get('expected_value_50wr', 0),
            breakeven_win_rate=params.get('breakeven_win_rate', 0.5)
        )

    def update_config(self, section: str, key: str, value: Any):
        """Update configuration value."""
        if section in self.config:
            self.config[section][key] = value
            self._save_config()

    def _save_config(self):
        """Save configuration to file."""
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)

    def get_all_exit_strategies(self) -> Dict[str, ExitConfig]:
        """Get all available exit strategies."""
        exits = self.config['strategy_parameters']['exits']
        strategies = {}

        for name, params in exits.items():
            if name != 'default' and isinstance(params, dict):
                strategies[name] = ExitConfig(
                    take_profit=params['take_profit'],
                    stop_loss=params['stop_loss'],
                    description=params.get('description', ''),
                    expected_value_50wr=params.get('expected_value_50wr', 0),
                    breakeven_win_rate=params.get('breakeven_win_rate', 0.5)
                )

        return strategies

    def validate_config(self) -> bool:
        """Validate configuration parameters."""
        try:
            macd = self.get_macd_config()
            assert macd.fast > 0 and macd.slow > macd.fast
            assert macd.signal > 0

            rsi = self.get_rsi_config()
            assert 0 < rsi.oversold < rsi.overbought < 100
            assert rsi.period > 0

            exits = self.get_all_exit_strategies()
            for name, exit_cfg in exits.items():
                assert 0 < exit_cfg.stop_loss < 1
                assert 0 < exit_cfg.take_profit < 1
                assert 0 <= exit_cfg.breakeven_win_rate <= 1

            return True
        except (KeyError, AssertionError) as e:
            print(f"Configuration validation failed: {e}")
            return False


# Global instance for easy access
_config_instance = None


def get_config() -> TradingConfig:
    """Get global configuration instance."""
    global _config_instance
    if _config_instance is None:
        _config_instance = TradingConfig()
    return _config_instance


def reload_config(config_file: str = None):
    """Reload configuration from file."""
    global _config_instance
    _config_instance = TradingConfig(config_file)
    return _config_instance
