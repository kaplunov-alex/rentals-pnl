"""
Read and write categories and vendor mappings from the P&L Google Sheet.

Expected tab formats:
  "Categories"     — columns: Category | Type  (Type = "income" or "expense")
  "Vendor Mappings" — columns: Key | Property | Category
"""

import logging
from typing import Any, Dict, List

import gspread

logger = logging.getLogger(__name__)

CATEGORIES_TAB = "Categories"
VENDOR_MAPPINGS_TAB = "Vendor Mappings"


def _get_client(service_account_path: str):
    return gspread.service_account(filename=service_account_path)


def read_categories(spreadsheet_id: str, service_account_path: str) -> Dict[str, List[str]]:
    """
    Read the Categories tab and return:
      {'categories': [...], 'income_categories': [...]}
    Expects columns: Category | Type  (Type = 'income' or 'expense').
    Rows with no Category value are skipped.
    """
    client = _get_client(service_account_path)
    spreadsheet = client.open_by_key(spreadsheet_id)
    try:
        ws = spreadsheet.worksheet(CATEGORIES_TAB)
    except gspread.exceptions.WorksheetNotFound:
        logger.warning(f"'{CATEGORIES_TAB}' tab not found — falling back to config.yaml categories.")
        return {}

    rows = ws.get_all_values()
    if not rows:
        return {}

    # Find header row
    header = [c.strip().lower() for c in rows[0]]
    try:
        cat_col = header.index("category")
    except ValueError:
        # No header — assume single column of category names, all expense
        categories = [r[0].strip() for r in rows if r and r[0].strip()]
        return {"categories": categories, "income_categories": []}

    type_col = header.index("type") if "type" in header else None

    income, expense = [], []
    for row in rows[1:]:
        if not row or not row[cat_col].strip():
            continue
        name = row[cat_col].strip()
        if type_col is not None and type_col < len(row):
            t = row[type_col].strip().lower()
            if t == "income":
                income.append(name)
            else:
                expense.append(name)
        else:
            expense.append(name)

    return {"categories": expense, "income_categories": income}


def read_vendor_mappings(spreadsheet_id: str, service_account_path: str) -> Dict[str, Any]:
    """
    Read the Vendor Mappings tab and return a dict matching vendor_mappings in config.yaml:
      {key: {'property': ..., 'category': ...}}
    Expects columns: Key | Property | Category
    """
    client = _get_client(service_account_path)
    spreadsheet = client.open_by_key(spreadsheet_id)
    try:
        ws = spreadsheet.worksheet(VENDOR_MAPPINGS_TAB)
    except gspread.exceptions.WorksheetNotFound:
        logger.warning(f"'{VENDOR_MAPPINGS_TAB}' tab not found — falling back to config.yaml vendor_mappings.")
        return {}

    rows = ws.get_all_values()
    if not rows:
        return {}

    header = [c.strip().lower() for c in rows[0]]
    try:
        key_col = header.index("key")
        prop_col = header.index("property")
        cat_col = header.index("category")
    except ValueError:
        logger.warning(f"'{VENDOR_MAPPINGS_TAB}' tab missing expected headers (Key, Property, Category).")
        return {}

    mappings = {}
    for row in rows[1:]:
        if not row or not row[key_col].strip():
            continue
        key = row[key_col].strip()
        mappings[key] = {
            "property": row[prop_col].strip() if prop_col < len(row) else "",
            "category": row[cat_col].strip() if cat_col < len(row) else "",
        }
    return mappings


def write_vendor_mapping(
    key: str,
    property_name: str,
    category: str,
    spreadsheet_id: str,
    service_account_path: str,
) -> None:
    """Add or overwrite a vendor mapping row in the sheet."""
    client = _get_client(service_account_path)
    spreadsheet = client.open_by_key(spreadsheet_id)
    ws = spreadsheet.worksheet(VENDOR_MAPPINGS_TAB)

    rows = ws.get_all_values()
    header = [c.strip().lower() for c in rows[0]] if rows else []
    try:
        key_col = header.index("key")
        prop_col = header.index("property")
        cat_col = header.index("category")
    except ValueError:
        raise RuntimeError(f"'{VENDOR_MAPPINGS_TAB}' tab missing expected headers.")

    # Check if key already exists and update in place
    for i, row in enumerate(rows[1:], start=2):  # 1-based sheet rows
        if row and row[key_col].strip() == key:
            ws.update_cell(i, prop_col + 1, property_name)
            ws.update_cell(i, cat_col + 1, category)
            logger.info(f"Updated existing vendor mapping row for {key!r}")
            return

    # Append new row
    new_row = [""] * max(key_col + 1, prop_col + 1, cat_col + 1)
    new_row[key_col] = key
    new_row[prop_col] = property_name
    new_row[cat_col] = category
    ws.append_row(new_row, value_input_option="USER_ENTERED")
    logger.info(f"Appended new vendor mapping row for {key!r}")


def delete_vendor_mapping(
    key: str,
    spreadsheet_id: str,
    service_account_path: str,
) -> bool:
    """
    Remove the row with the given key from the Vendor Mappings tab.
    Returns True if found and deleted, False if not found.
    """
    client = _get_client(service_account_path)
    spreadsheet = client.open_by_key(spreadsheet_id)
    ws = spreadsheet.worksheet(VENDOR_MAPPINGS_TAB)

    rows = ws.get_all_values()
    header = [c.strip().lower() for c in rows[0]] if rows else []
    try:
        key_col = header.index("key")
    except ValueError:
        raise RuntimeError(f"'{VENDOR_MAPPINGS_TAB}' tab missing 'Key' header.")

    for i, row in enumerate(rows[1:], start=2):
        if row and row[key_col].strip() == key:
            ws.delete_rows(i)
            logger.info(f"Deleted vendor mapping row for {key!r}")
            return True

    return False
