"""Configuration loader for model/runtime tuning."""

import json

CONFIG_FILE = "model_config.json"


def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as file_obj:
        return json.load(file_obj)
