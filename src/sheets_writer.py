"""
Google Sheets integration — writes monthly P&L totals into the summary sheet.

Sheet layout (per property tab):
  Row 4: Headers — CATEGORY | Jan | Feb | ... | Dec | ANNUAL
  Column A: Category labels (Income rows, then Expense rows)

The pipeline aggregates all transactions for a given property/month/category
and writes the totals into the correct cells (overwrite, not append).
Running twice for the same month produces the same result (idempotent).
"""

import logging
import time
from datetime import date
from typing import Dict, List, Optional, Tuple

import gspread

from .models import Transaction

logger = logging.getLogger(__name__)

MONTH_SHORT = {
    1: "jan", 2: "feb", 3: "mar", 4: "apr", 5: "may", 6: "jun",
    7: "jul", 8: "aug", 9: "sep", 10: "oct", 11: "nov", 12: "dec",
}


def _get_client(service_account_path: str = "service_account.json") -> gspread.Client:
    return gspread.service_account(filename=service_account_path)


def _retry(fn, max_attempts: int = 3, base_delay: float = 2.0):
    """Call fn() up to max_attempts times with exponential backoff."""
    last_exc = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except gspread.exceptions.APIError as e:
            last_exc = e
            delay = base_delay * (2 ** attempt)
            logger.warning(
                f"Sheets API error (attempt {attempt + 1}/{max_attempts}): {e}. "
                f"Retrying in {delay:.1f}s…"
            )
            time.sleep(delay)
    raise last_exc


def _find_header_row(all_values: List[List]) -> Optional[int]:
    """Return 0-based index of the row containing month column headers (Jan, Feb, …)."""
    for i, row in enumerate(all_values):
        row_lower = [c.strip().lower() for c in row]
        if "jan" in row_lower and "feb" in row_lower:
            return i
    return None


def _find_col(header_row: List, month_num: int) -> Optional[int]:
    """Return 0-based column index for a given month number."""
    target = MONTH_SHORT[month_num]
    for j, cell in enumerate(header_row):
        if cell.strip().lower() == target:
            return j
    return None


def _find_row(all_values: List[List], category: str) -> Optional[int]:
    """
    Return 0-based row index for a category label in column A.
    Tries exact match first, then partial match (case-insensitive).
    """
    cat_lower = category.strip().lower()
    # Exact match
    for i, row in enumerate(all_values):
        if row and row[0].strip().lower() == cat_lower:
            return i
    # Partial match — category is substring of label, or label is substring of category
    for i, row in enumerate(all_values):
        if row:
            label = row[0].strip().lower()
            if label and (cat_lower in label or label in cat_lower):
                return i
    return None


def _parse_cell_value(cell: str) -> float:
    """Parse a sheet cell value to float; treat dash/blank as 0."""
    s = str(cell).strip().replace(",", "")
    if not s or s in ("-", "—"):
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def get_sheet_names(
    spreadsheet_id: str,
    service_account_path: str = "service_account.json",
) -> List[str]:
    """Return the list of worksheet tab names."""
    client = _get_client(service_account_path)
    spreadsheet = _retry(lambda: client.open_by_key(spreadsheet_id))
    return [ws.title for ws in spreadsheet.worksheets()]


def get_last_written_month(
    spreadsheet_id: str,
    sheet_name: str,
    service_account_path: str = "service_account.json",
) -> Optional[date]:
    """
    With the P&L grid layout, there are no date rows — each column IS a month.
    This function is kept for interface compatibility but always returns None.
    Use --month to control which month is processed.
    """
    return None


def write_monthly_totals(
    transactions: List[Transaction],
    spreadsheet_id: str,
    service_account_path: str = "service_account.json",
) -> Dict[str, int]:
    """
    Aggregate transactions by (property, category, month) and write totals
    into the correct cells of the P&L summary sheet.

    Cell values are OVERWRITTEN (not added) so running twice for the same
    month is idempotent — the total reflects exactly the transactions provided.

    Returns {sheet_name: number_of_transactions_written}.
    """
    if not transactions:
        return {}

    client = _get_client(service_account_path)
    spreadsheet = _retry(lambda: client.open_by_key(spreadsheet_id))

    # Group by property
    by_property: Dict[str, List[Transaction]] = {}
    for txn in transactions:
        if not txn.property:
            logger.warning(f"Skipping transaction with no property: {txn.description!r}")
            continue
        by_property.setdefault(txn.property, []).append(txn)

    written: Dict[str, int] = {}

    for prop_name, txns in by_property.items():
        try:
            ws = spreadsheet.worksheet(prop_name)
        except gspread.exceptions.WorksheetNotFound:
            logger.error(f"Worksheet {prop_name!r} not found — skipping.")
            continue

        all_values = _retry(lambda: ws.get_all_values())

        header_row_idx = _find_header_row(all_values)
        if header_row_idx is None:
            logger.error(f"Could not find month header row in {prop_name!r} — skipping.")
            continue

        header_row = all_values[header_row_idx]

        # Collect individual amounts per cell: (row_idx, col_idx) -> [amount, ...]
        cell_amounts: Dict[Tuple[int, int], List[float]] = {}
        skipped = 0

        for txn in txns:
            category = txn.category or "Other Expenses"
            row_idx = _find_row(all_values, category)
            col_idx = _find_col(header_row, txn.date.month)

            if row_idx is None:
                logger.warning(
                    f"No row found for category {category!r} in {prop_name!r} "
                    f"— skipping {txn.description!r}"
                )
                skipped += 1
                continue

            if col_idx is None:
                logger.warning(f"No column found for month {txn.date.month} in {prop_name!r}")
                skipped += 1
                continue

            key = (row_idx, col_idx)
            cell_amounts.setdefault(key, []).append(round(abs(txn.amount), 2))

        # Write cells as SUM formulas so individual amounts remain visible
        cells_updated = 0
        for (row_idx, col_idx), amounts in cell_amounts.items():
            if len(amounts) == 1:
                formula = amounts[0]  # plain number for single transactions
            else:
                parts = ",".join(str(a) for a in amounts)
                formula = f"=SUM({parts})"
            _retry(lambda r=row_idx + 1, c=col_idx + 1, v=formula: ws.update_cell(r, c, v))
            cells_updated += 1
            category_label = all_values[row_idx][0] if all_values[row_idx] else "?"
            month_label = header_row[col_idx] if col_idx < len(header_row) else "?"
            logger.info(f"  {prop_name} / {category_label} / {month_label} = {formula}")

        written[prop_name] = len(txns) - skipped
        logger.info(
            f"{prop_name!r}: {cells_updated} cells updated, "
            f"{skipped} transactions skipped (unmatched category/month)"
        )

    return written


# Keep old name as alias so any external callers aren't broken
def append_transactions(
    transactions: List[Transaction],
    spreadsheet_id: str,
    service_account_path: str = "service_account.json",
) -> Dict[str, int]:
    return write_monthly_totals(transactions, spreadsheet_id, service_account_path)
