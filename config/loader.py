import yaml
from pathlib import Path

_config_cache = None

def load_config(path="config/config.yaml"):
    global _config_cache

    if _config_cache is None:
        config_path = Path(path)
        with open(config_path, "r", encoding="utf-8") as f:
            _config_cache = yaml.safe_load(f)

    return _config_cache


def get(key=None, default=None):
    """
    Config-аас утга авах helper
    жишээ:
    get("city")
    get("simulation.speed")
    """
    config = load_config()

    if key is None:
        return config

    keys = key.split(".")
    value = config

    for k in keys:
        value = value.get(k)
        if value is None:
            return default

    return value