"""Shared FastAPI dependencies."""

from typing import Any, Dict

import yaml

CONFIG_PATH = "config.yaml"
_config_cache: Dict[str, Any] | None = None


def get_config() -> Dict[str, Any]:
    """Load config.yaml. Cached until reload_config() is called."""
    global _config_cache
    if _config_cache is None:
        with open(CONFIG_PATH, "r") as f:
            _config_cache = yaml.safe_load(f)
    return _config_cache


def reload_config() -> Dict[str, Any]:
    """Clear the cache and reload config.yaml from disk."""
    global _config_cache
    _config_cache = None
    return get_config()
