"""
Persists new vendor mappings and split rules back to config.yaml so they are
used as rule-based matches on future runs (eliminating API calls for known vendors).

Split rule format in config.yaml:
  split_rules:
    "BILL PAY Juan Santiago":
      - amount: -340.0          # amount-specific rule (optional)
        parts:
          - property: "154 Santa Clara"
            category: "Landscaping"
            amount: -140.0
          - property: "30 Bishop Oak"
            category: "Landscaping"
            amount: -200.0
      - default:                # fallback when no amount matches
          property: "30 Bishop Oak"
          category: "Landscaping"
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


def _load(config_path: str) -> Dict[str, Any]:
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def _save(config: Dict[str, Any], config_path: str) -> None:
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def save_vendor_mapping(
    vendor_key: str,
    property_name: str,
    category: str,
    config_path: str = "config.yaml",
) -> None:
    """Add or overwrite a simple (one property) vendor mapping."""
    config = _load(config_path)
    if not config.get("vendor_mappings"):
        config["vendor_mappings"] = {}
    config["vendor_mappings"][vendor_key] = {"property": property_name, "category": category}
    _save(config, config_path)
    logger.info(f"Saved vendor mapping: {vendor_key!r} -> {property_name} / {category}")


def save_split_rule(
    vendor_key: str,
    amount: Optional[float],
    parts: List[Dict[str, Any]],
    default_property: Optional[str],
    default_category: Optional[str],
    config_path: str = "config.yaml",
) -> None:
    """Add or update a split rule for a vendor.

    - If amount is given, saves an amount-specific split.
    - If default_property/category are given, saves a fallback single-property rule.
    """
    config = _load(config_path)
    if not config.get("split_rules"):
        config["split_rules"] = {}

    rules = config["split_rules"].get(vendor_key, [])
    # Remove any existing rule with the same amount (or default) to avoid duplicates
    rules = [r for r in rules if r.get("amount") != amount and not (amount is None and "default" in r)]

    if amount is not None:
        rules.append({"amount": amount, "parts": parts})

    if default_property and default_category:
        rules.append({"default": {"property": default_property, "category": default_category}})

    config["split_rules"][vendor_key] = rules
    _save(config, config_path)
    logger.info(f"Saved split rule: {vendor_key!r} amount={amount}")
