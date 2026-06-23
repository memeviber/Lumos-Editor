import json
import os
from pathlib import Path


class ConfigManager:
    def __init__(self, config_file=Path.home() / ".lumos_editor" / "config.json"):
        self.config_file = config_file
        if not self.config_file.parent.exists():
            self.config_file.parent.mkdir(parents=True)
        self.settings = self._load_settings()

    def _load_settings(self):
        defaults = {
            "last_session": {},
            "last_session_id": None,
            "AI_sessions": [],
            "plugins_enabled": True,
            "individual_plugins": {},
            "recent_files": [],
            "wrap_mode": False,
            "theme": "default",
        }
        if not os.path.exists(self.config_file):
            return defaults
        try:
            with open(self.config_file, "r") as f:
                settings = json.load(f)
                for key, value in defaults.items():
                    settings.setdefault(key, value)
                return settings
        except (json.JSONDecodeError, IOError):
            return defaults

    def get(self, key, default=None):
        return self.settings.get(key, default)

    def set(self, key, value):
        self.settings[key] = value
        self._save_settings()

    def _save_settings(self):
        try:
            with open(self.config_file, "w") as f:
                json.dump(self.settings, f, indent=4, sort_keys=True)
        except IOError as e:
            print(f"Error saving config file: {e}")

    def is_plugin_enabled(self, plugin_filename):
        return self.settings["individual_plugins"].get(plugin_filename, True)

    def set_plugin_enabled(self, plugin_filename, is_enabled):
        self.settings["individual_plugins"][plugin_filename] = is_enabled
        self._save_settings()
