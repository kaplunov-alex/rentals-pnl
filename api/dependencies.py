"""Shared FastAPI dependencies."""

import os
from typing import Any, Dict

import yaml

CONFIG_PATH = "config.yaml"
_config_cache: Dict[str, Any] | None = None


def _service_account_path(config: dict) -> str:
    svc = (
        os.environ.get("SERVICE_ACCOUNT_PATH")
        or config.get("service_account_path")
        or "service_account.json"
    )
    if not os.path.exists(svc):
        svc = "service_account.json"
    return svc


def get_config() -> Dict[str, Any]:
    """
    Load config.yaml and overlay categories + vendor_mappings from Google Sheet.
    Cached until reload_config() is called.
    """
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    with open(CONFIG_PATH, "r") as f:
        config = yaml.safe_load(f)

    # Overlay categories and vendor_mappings from sheet (sheet is source of truth)
    spreadsheet_id = config.get("spreadsheet_id")
    sa_path = _service_account_path(config)
    if spreadsheet_id and os.path.exists(sa_path):
        try:
            from src.config_sheet import read_categories, read_vendor_mappings
            sheet_cats = read_categories(spreadsheet_id, sa_path)
            if sheet_cats:
                config.update(sheet_cats)
            sheet_mappings = read_vendor_mappings(spreadsheet_id, sa_path)
            if sheet_mappings is not None:
                config["vendor_mappings"] = sheet_mappings
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                f"Could not load config from sheet, using config.yaml values: {e}"
            )

    _config_cache = config
    return _config_cache


def reload_config() -> Dict[str, Any]:
    """Clear the cache and reload from config.yaml + sheet."""
    global _config_cache
    _config_cache = None
    return get_config()
