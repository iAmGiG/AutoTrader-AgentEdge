import json
import os

try:
    import yaml
except ImportError:
    yaml = None


class ConfigLoader:
    def __init__(self, config_path=None):
        # Determine the config file path relative to this file
        if config_path is None:
            # Assuming config folder is in the project root
            # This file is at src/utils/config_loader.py, so go up 3 levels to project root
            base_dir = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            # Try YAML first, fallback to JSON
            yaml_path = os.path.join(base_dir, "config", "config.yaml")
            json_path = os.path.join(base_dir, "config", "config.json")

            if os.path.exists(yaml_path):
                config_path = yaml_path
            elif os.path.exists(json_path):
                config_path = json_path
            else:
                # Default to JSON for backward compatibility
                config_path = json_path

        self.config_path = config_path
        self.config = self.load_config()

    def load_config(self):
        try:
            with open(self.config_path, "r") as file:
                if self.config_path.endswith('.yaml') or self.config_path.endswith('.yml'):
                    if yaml is None:
                        raise ImportError("PyYAML not installed. Install with: pip install pyyaml")
                    config = yaml.safe_load(file)
                else:
                    config = json.load(file)
            return config
        except Exception as e:
            raise Exception(f"Error loading config file: {e}")

    def get(self, key, default=None):
        return self.config.get(key, default)

