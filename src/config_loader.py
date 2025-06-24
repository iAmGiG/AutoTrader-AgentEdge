import json
import os


class ConfigLoader:
    def __init__(self, config_path=None):
        # Determine the config file path relative to this file
        if config_path is None:
            # Assuming config folder is in the project root
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, "config", "config.json")
        self.config_path = config_path
        self.config = self.load_config()

    def load_config(self):
        try:
            with open(self.config_path, "r") as file:
                config = json.load(file)
            return config
        except Exception as e:
            # If the config file is missing, fall back to an empty dict
            # to avoid import errors across environments.
            print(f"Warning: could not load config file: {e}")
            return {}

    def get(self, key, default=None):
        return self.config.get(key, default)
