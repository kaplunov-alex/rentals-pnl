"""
Categorizer: assigns property + expense category to each Transaction.

Step 1 — Split rules: check split_rules in config (vendor key + optional amount).
Step 2 — Rule-based: check vendor_mappings in config (partial match).
Step 3 — Claude API (Haiku): suggest a categorization.
Step 4 — Interactive: show suggestion, ask to confirm/override/split,
          then save the chosen mapping or split rule back to config.yaml.
Step 5 — Flag as REVIEW if user skips or Claude can't suggest.
"""

import copy
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

import anthropic

from .models import Transaction

logger = logging.getLogger(__name__)

_client: Optional[anthropic.Anthropic] = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def categorize_transactions(
    transactions: List[Transaction],
    config: Dict[str, Any],
    interactive: bool = True,
    config_path: str = "config.yaml",
) -> List[Transaction]:
    """Categorize transactions and return the (possibly expanded) result list.

    Split transactions produce multiple Transaction objects in the output.
    """
    vendor_mappings: Dict[str, Dict] = config.get("vendor_mappings") or {}
    split_rules: Dict[str, List] = config.get("split_rules") or {}
    properties: List[str] = config.get("properties", [])
    categories: List[str] = config.get("categories", [])
    income_categories: List[str] = config.get("income_categories", [])
    all_categories: List[str] = income_categories + categories

    result: List[Transaction] = []
    for txn in transactions:
        # Step 1: split rules
        splits = _split_rule_match(txn, split_rules)
        if splits:
            result.extend(splits)
            continue

        # Step 2: simple vendor mapping
        mapping = _rule_based_match(txn.description, vendor_mappings)
        if mapping:
            txn.property = mapping["property"]
            txn.category = mapping["category"]
            txn.needs_review = False
            result.append(txn)
            continue

        # Step 3/4: interactive or non-interactive Claude fallback
        if interactive:
            expanded = _interactive_categorize(
                txn, properties, all_categories, vendor_mappings, split_rules, config_path
            )
            result.extend(expanded)
        else:
            _claude_categorize(txn, properties, all_categories)
            result.append(txn)

    # Infer txn_type from amount sign: positive = Income, negative = Expense
    income_cat_set = {c.lower() for c in income_categories}
    for txn in result:
        if txn.amount > 0 or (txn.category and txn.category.lower() in income_cat_set):
            txn.txn_type = "Income"
        else:
            txn.txn_type = "Expense"

    return result


# ---------------------------------------------------------------------------
# Split rule matching
# ---------------------------------------------------------------------------

def _split_rule_match(
    txn: Transaction, split_rules: Dict[str, List]
) -> Optional[List[Transaction]]:
    """Return a list of split Transactions if a split rule matches, else None."""
    desc_upper = txn.description.upper()
    for vendor_key, rules in split_rules.items():
        if vendor_key.upper() not in desc_upper:
            continue
        # Found a matching vendor key — now find the right rule
        default_rule = None
        for rule in rules:
            if "amount" in rule:
                if abs(rule["amount"] - txn.amount) < 0.01:
                    return _apply_split(txn, rule["parts"])
            elif "default" in rule:
                default_rule = rule["default"]
        # No amount-specific match — use default if present
        if default_rule:
            txn.property = default_rule["property"]
            txn.category = default_rule["category"]
            txn.needs_review = False
            return [txn]
    return None


def _apply_split(txn: Transaction, parts: List[Dict]) -> List[Transaction]:
    """Create one Transaction per split part, cloning from the original."""
    result = []
    for part in parts:
        t = copy.copy(txn)
        t.property = part["property"]
        t.category = part["category"]
        t.amount = part["amount"]
        t.needs_review = False
        result.append(t)
    return result


# ---------------------------------------------------------------------------
# Simple vendor rule matching
# ---------------------------------------------------------------------------

def _rule_based_match(
    description: str, vendor_mappings: Dict[str, Dict]
) -> Optional[Dict]:
    desc_upper = description.upper()
    for vendor, mapping in vendor_mappings.items():
        if vendor.upper() in desc_upper:
            return mapping
    return None


# ---------------------------------------------------------------------------
# Claude suggestion
# ---------------------------------------------------------------------------

def _claude_suggest(
    txn: Transaction,
    properties: List[str],
    categories: List[str],
) -> Tuple[Optional[str], Optional[str]]:
    """Return (property, category) suggestion from Claude, or (None, None)."""
    prompt = f"""You are a rental property bookkeeper. Classify the following bank transaction.

Transaction description: {txn.description}
Amount: {txn.amount}
Bank source: {txn.source}

Valid properties: {json.dumps(properties)}
Valid categories: {json.dumps(categories)}

Note: positive amounts are typically income (e.g. rent received); negative amounts are expenses.

Respond with ONLY a JSON object (no markdown, no explanation) with exactly these two keys:
- "property": one of the valid properties above, or null if you cannot determine it
- "category": one of the valid categories above, or null if you cannot determine it

If not confident (e.g. unrelated to rental properties), set both to null.

Example: {{"property": "154 Santa Clara", "category": "Rental Income"}}"""

    try:
        response = _get_client().messages.create(
            model="claude-haiku-4-5",
            max_tokens=128,
            messages=[{"role": "user", "content": prompt}],
        )
        data = json.loads(response.content[0].text.strip())
        prop = data.get("property")
        cat = data.get("category")
        if prop in properties and cat in categories:
            return prop, cat
    except Exception as e:
        logger.debug(f"Claude suggestion failed for {txn.description!r}: {e}")
    return None, None


# ---------------------------------------------------------------------------
# Interactive prompt
# ---------------------------------------------------------------------------

def _interactive_categorize(
    txn: Transaction,
    properties: List[str],
    categories: List[str],
    vendor_mappings: Dict[str, Dict],
    split_rules: Dict[str, List],
    config_path: str,
) -> List[Transaction]:
    """Prompt the user; returns a list of 1+ transactions."""
    from .config_updater import save_split_rule, save_vendor_mapping

    suggested_prop, suggested_cat = _claude_suggest(txn, properties, categories)

    print()
    print("-" * 60)
    print(f"  Unknown transaction")
    print(f"  Description : {txn.description}")
    print(f"  Amount      : {txn.amount:+.2f}")
    print(f"  Source      : {txn.source}  |  Date: {txn.date}")
    if suggested_prop and suggested_cat:
        print(f"  Claude suggests -> {suggested_prop} / {suggested_cat}")
    print("-" * 60)

    prop = _prompt_choice(
        prompt="Property",
        options=properties,
        default=suggested_prop,
        extra_options={"t": "Split across multiple properties"},
    )

    if prop == "t":
        # --- Split flow ---
        parts = _prompt_split(txn, properties, categories)
        if not parts:
            txn.needs_review = True
            txn.category = "REVIEW"
            return [txn]

        split_txns = _apply_split(txn, parts)

        # Ask to save
        default_key = _default_vendor_key(txn.description)
        raw = input(f"\n  Save split rule? Vendor key [{default_key}] ('-' to skip): ").strip()
        if raw != "-":
            key = raw if raw else default_key
            # Ask for default (non-split) behaviour
            print(f"\n  Default rule when amount is NOT {txn.amount:+.2f}?")
            def_prop = _prompt_choice("Default property", properties, suggested_prop)
            def_cat = None
            if def_prop:
                def_cat = _prompt_choice("Default category", categories, suggested_cat)
            save_split_rule(
                vendor_key=key,
                amount=txn.amount,
                parts=parts,
                default_property=def_prop,
                default_category=def_cat,
                config_path=config_path,
            )
            split_rules[key] = []  # in-memory update (simplified; reloaded next run)
            print(f"  Saved split rule for {key!r}.")

        return split_txns

    # --- Single-property flow ---
    if prop is None:
        txn.needs_review = True
        txn.category = "REVIEW"
        print("  Flagged for manual review.\n")
        return [txn]

    cat = _prompt_choice("Category", categories, suggested_cat)
    if cat is None:
        txn.needs_review = True
        txn.category = "REVIEW"
        print("  Flagged for manual review.\n")
        return [txn]

    txn.property = prop
    txn.category = cat
    txn.needs_review = False

    default_key = _default_vendor_key(txn.description)
    raw = input(f"\n  Save vendor rule? Key [{default_key}] ('-' to skip): ").strip()
    if raw != "-":
        key = raw if raw else default_key
        save_vendor_mapping(key, prop, cat, config_path)
        vendor_mappings[key] = {"property": prop, "category": cat}
        print(f"  Saved: {key!r} -> {prop} / {cat}")

    print()
    return [txn]


def _prompt_split(
    txn: Transaction,
    properties: List[str],
    categories: List[str],
) -> Optional[List[Dict]]:
    """Interactively collect split parts. Returns list of part dicts, or None on cancel."""
    try:
        n_raw = input(f"\n  Split into how many parts? [2]: ").strip()
        n = int(n_raw) if n_raw else 2
        if n < 2:
            print("  Need at least 2 parts.")
            return None
    except ValueError:
        return None

    parts = []
    remaining = txn.amount
    for i in range(n):
        print(f"\n  -- Part {i + 1} of {n} (remaining: {remaining:+.2f}) --")
        prop = _prompt_choice(f"Property", properties, None)
        if prop is None:
            return None
        cat = _prompt_choice(f"Category", categories, None)
        if cat is None:
            return None

        if i == n - 1:
            # Last part: auto-fill the remainder
            amount = remaining
            print(f"  Amount: {amount:+.2f}  (remainder)")
        else:
            amt_raw = input(f"  Amount [{remaining:+.2f}]: ").strip()
            try:
                amount = float(amt_raw) if amt_raw else remaining
            except ValueError:
                print("  Invalid amount.")
                return None
            remaining = round(remaining - amount, 2)

        parts.append({"property": prop, "category": cat, "amount": amount})

    return parts


def _prompt_choice(
    prompt: str,
    options: List[str],
    default: Optional[str],
    extra_options: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    """Show a numbered menu; returns chosen option, extra key string, or None to skip."""
    print(f"\n  {prompt}:")
    for i, opt in enumerate(options, 1):
        marker = " <--" if opt == default else ""
        print(f"    {i}. {opt}{marker}")
    if extra_options:
        for key, label in extra_options.items():
            print(f"    {key}. {label}")
    print(f"    s. Skip (flag for review)")

    default_num = (options.index(default) + 1) if default in options else None
    hint = f"[{default_num}]" if default_num else ""

    while True:
        raw = input(f"  Choice {hint}: ").strip().lower()
        if raw == "s":
            return None
        if extra_options and raw in extra_options:
            return raw
        if raw == "" and default_num:
            return default
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        valid = f"1-{len(options)}, s" + (f", {', '.join(extra_options)}" if extra_options else "")
        print(f"  Enter {valid}.")


def _default_vendor_key(description: str) -> str:
    words = description.upper().split()
    meaningful = [w for w in words if len(w) >= 3 and not w.isdigit()]
    return " ".join(meaningful[:3]) if meaningful else description[:20].upper()


def _claude_categorize(
    txn: Transaction,
    properties: List[str],
    categories: List[str],
) -> None:
    """Non-interactive fallback: use Claude and flag if not confident."""
    prop, cat = _claude_suggest(txn, properties, categories)
    if prop and cat:
        txn.property = prop
        txn.category = cat
        txn.needs_review = False
    else:
        txn.needs_review = True
        txn.category = "REVIEW"
        logger.info(f"Flagged for review: {txn.description!r}")
