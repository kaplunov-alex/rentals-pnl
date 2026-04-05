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


def get_overview_cells(
    spreadsheet_id: str,
    service_account_path: str = "service_account.json",
    sheet_name: str = "Portfolio Summary",
    cell_range: str = "E4:E6",
) -> dict:
    """
    Read the three overview cells from the Portfolio Summary tab.
    Default range E4:E6 maps to Total Income, Total Expenses, Net Cash Flow.
    Returns {"total_income": float, "total_expenses": float, "net_cash_flow": float}
    """
    client = _get_client(service_account_path)
    spreadsheet = _retry(lambda: client.open_by_key(spreadsheet_id))
    ws = spreadsheet.worksheet(sheet_name)
    values = _retry(lambda: ws.get(cell_range, value_render_option="UNFORMATTED_VALUE"))

    def safe_get(idx: int) -> float:
        try:
            raw = values[idx][0]
            return float(raw) if raw != "" else 0.0
        except (IndexError, TypeError, ValueError):
            return 0.0

    return {
        "total_income": safe_get(0),
        "total_expenses": safe_get(1),
        "net_cash_flow": safe_get(2),
    }


def get_portfolio_summary(
    spreadsheet_id: str,
    service_account_path: str = "service_account.json",
    sheet_name: str = "Portfolio Summary",
) -> dict:
    """
    Read a P&L grid tab (Portfolio Summary or a property tab) and return
    rows with monthly values keyed by 3-letter month abbreviation.

    Returns: {"months": [...], "rows": [{"label": str, "values": {"jan": float, ...}}]}
    """
    client = _get_client(service_account_path)
    spreadsheet = _retry(lambda: client.open_by_key(spreadsheet_id))
    ws = spreadsheet.worksheet(sheet_name)
    all_values = _retry(lambda: ws.get_all_values())

    header_row_idx = _find_header_row(all_values)
    if header_row_idx is None:
        return {"months": [], "rows": []}

    header_row = all_values[header_row_idx]
    months: List[str] = []
    month_cols: List[int] = []
    valid_months = set(MONTH_SHORT.values())
    for j, cell in enumerate(header_row):
        val = cell.strip().lower()
        if val in valid_months:
            months.append(val)
            month_cols.append(j)

    rows = []
    for i in range(header_row_idx + 1, len(all_values)):
        row = all_values[i]
        if not row or not row[0].strip():
            continue
        label = row[0].strip()
        values: dict = {}
        for col_j, month in zip(month_cols, months):
            values[month] = _parse_cell_value(row[col_j]) if col_j < len(row) else 0.0
        rows.append({"label": label, "values": values})

    return {"months": months, "rows": rows}


_PROPERTY_SHEET_HEADERS = ["Date", "Vendor", "Amount", "Bank/Card", "Category", "Comments"]


def write_property_transaction_sheets(
    transactions: List[Transaction],
    config: dict,
    service_account_path: str = "service_account.json",
) -> Dict[str, int]:
    """
    Append transactions to per-property transaction sheets.

    Each property has its own Google Sheet (IDs in config['property_sheets']).
    Tabs are named by year (e.g. "2026"); created automatically if missing.
    Columns: Date | Vendor | Amount | Bank/Card | Category | Comments

    Deduplication: if a month (YYYY-MM) already has any rows in the target tab,
    all transactions for that month are skipped entirely.

    Returns {property_name: rows_appended}.  Raises on first unrecoverable error.
    """
    property_sheets_cfg = config.get("property_sheets", {})
    if not property_sheets_cfg:
        logger.warning("No property_sheets configured — skipping per-property sheet write.")
        return {}

    client = _get_client(service_account_path)

    # Group transactions by property
    by_property: Dict[str, List[Transaction]] = {}
    for txn in transactions:
        if not txn.property:
            continue
        by_property.setdefault(txn.property, []).append(txn)

    logger.info(
        f"write_property_transaction_sheets: {len(transactions)} txns, "
        f"{len(by_property)} properties: {list(by_property.keys())}"
    )

    written: Dict[str, int] = {}
    errors: Dict[str, str] = {}

    for prop_name, txns in by_property.items():
        try:
            # Case-insensitive lookup for property sheet config
            sheet_cfg = next(
                (v for k, v in property_sheets_cfg.items() if k.lower() == prop_name.lower()),
                None,
            )
            if not sheet_cfg:
                msg = f"No property_sheets entry for {prop_name!r} (config keys: {list(property_sheets_cfg.keys())})"
                logger.warning(msg)
                errors[prop_name] = msg
                continue

            sheet_id = sheet_cfg.get("spreadsheet_id")
            if not sheet_id:
                msg = f"Missing spreadsheet_id for {prop_name!r}"
                logger.warning(msg)
                errors[prop_name] = msg
                continue

            logger.info(f"Opening property sheet for {prop_name!r} (id={sheet_id})")
            spreadsheet = _retry(lambda sid=sheet_id: client.open_by_key(sid))

            # Group by year
            by_year: Dict[int, List[Transaction]] = {}
            for txn in txns:
                by_year.setdefault(txn.date.year, []).append(txn)

            prop_written = 0

            for year, year_txns in by_year.items():
                tab_name = str(year)

                # Get or create year tab
                try:
                    ws = spreadsheet.worksheet(tab_name)
                    logger.info(f"Found existing tab {tab_name!r} in {prop_name!r}")
                except gspread.exceptions.WorksheetNotFound:
                    ws = _retry(lambda s=spreadsheet, t=tab_name: s.add_worksheet(title=t, rows=1000, cols=10))
                    _retry(lambda w=ws: w.append_row(_PROPERTY_SHEET_HEADERS, value_input_option="USER_ENTERED"))
                    logger.info(f"Created tab {tab_name!r} in {prop_name!r} transaction sheet.")

                # Read existing rows to find already-written months (skip header row)
                all_values = _retry(lambda w=ws: w.get_all_values())
                logger.info(f"{prop_name!r} / {tab_name}: {len(all_values)} rows already in sheet")
                written_months: set = set()
                for row in all_values[1:]:
                    if row and row[0].strip():
                        # Date is YYYY-MM-DD; extract YYYY-MM
                        written_months.add(row[0].strip()[:7])

                # Build rows to append, skipping any month already present
                rows_to_append = []
                skipped_months: set = set()
                for txn in year_txns:
                    txn_month = txn.date.strftime("%Y-%m")
                    if txn_month in written_months:
                        skipped_months.add(txn_month)
                        continue
                    rows_to_append.append([
                        txn.date.strftime("%Y-%m-%d"),
                        txn.description,
                        txn.amount,
                        txn.source,
                        txn.category or "",
                        txn.comments or "",
                    ])
                    written_months.add(txn_month)  # mark month as written for intra-batch consistency

                if skipped_months:
                    logger.info(f"{prop_name!r} / {tab_name}: skipped months already present: {sorted(skipped_months)}")

                logger.info(f"{prop_name!r} / {tab_name}: {len(rows_to_append)} new rows to append (of {len(year_txns)} txns)")
                if rows_to_append:
                    _retry(lambda w=ws, r=rows_to_append: w.append_rows(r, value_input_option="USER_ENTERED"))
                    prop_written += len(rows_to_append)
                    logger.info(f"{prop_name!r} / {tab_name}: appended {len(rows_to_append)} rows.")

            written[prop_name] = prop_written

        except Exception as e:
            logger.error(f"Failed to write property sheet for {prop_name!r}: {e}", exc_info=True)
            errors[prop_name] = str(e)

    if errors:
        error_summary = "; ".join(f"{p}: {e}" for p, e in errors.items())
        raise RuntimeError(f"Property sheet write errors: {error_summary}")

    return written


def _parse_row_date(date_str: str) -> Optional[str]:
    """Parse a date string in any common format and return YYYY-MM-DD, or None if unparseable."""
    from datetime import datetime
    date_str = date_str.strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y", "%-m/%-d/%Y"):
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def read_property_sheet_transactions(
    config: dict,
    month: str,
    property_name: Optional[str] = None,
    service_account_path: str = "service_account.json",
) -> List[dict]:
    """
    Read transactions from per-property Google Sheets for a given month (YYYY-MM).
    If property_name is None or 'all', reads from all configured property sheets.
    Returns a list of dicts: {date, vendor, amount, source, category, comments, property}.
    """
    property_sheets_cfg = config.get("property_sheets", {})
    if not property_sheets_cfg:
        return []

    client = _get_client(service_account_path)

    if property_name and property_name.lower() != "all":
        sheet_items = [
            (k, v) for k, v in property_sheets_cfg.items()
            if k.lower() == property_name.lower()
        ]
    else:
        sheet_items = list(property_sheets_cfg.items())

    try:
        year = int(month[:4])
    except (ValueError, IndexError):
        return []

    results: List[dict] = []

    for prop_name, sheet_cfg in sheet_items:
        sheet_id = sheet_cfg.get("spreadsheet_id")
        if not sheet_id:
            continue
        try:
            spreadsheet = _retry(lambda sid=sheet_id: client.open_by_key(sid))
            # Try year-named tab first, then fall back to the first worksheet
            try:
                ws = spreadsheet.worksheet(str(year))
            except gspread.exceptions.WorksheetNotFound:
                worksheets = spreadsheet.worksheets()
                if not worksheets:
                    continue
                ws = worksheets[0]

            all_values = _retry(lambda w=ws: w.get_all_values())
            for row in all_values[1:]:  # skip header row
                if not row or not row[0].strip():
                    continue
                parsed_date = _parse_row_date(row[0])
                if not parsed_date:
                    continue  # skip format/example rows
                if not parsed_date.startswith(month):
                    continue
                amount_str = row[2].strip().replace("$", "").replace(",", "") if len(row) > 2 else ""
                try:
                    amount = float(amount_str) if amount_str else 0.0
                except ValueError:
                    amount = 0.0
                results.append({
                    "date": parsed_date,
                    "vendor": row[1].strip() if len(row) > 1 else "",
                    "amount": amount,
                    "source": row[3].strip() if len(row) > 3 else "",
                    "category": row[4].strip() if len(row) > 4 else "",
                    "comments": row[5].strip() if len(row) > 5 else "",
                    "property": prop_name,
                })
        except Exception as e:
            logger.warning(f"Could not read sheet for {prop_name!r}: {e}")
            continue

    results.sort(key=lambda r: r["date"])
    return results


# Keep old name as alias so any external callers aren't broken
def append_transactions(
    transactions: List[Transaction],
    spreadsheet_id: str,
    service_account_path: str = "service_account.json",
) -> Dict[str, int]:
    return write_monthly_totals(transactions, spreadsheet_id, service_account_path)
