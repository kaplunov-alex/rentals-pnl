"""
CSV parsers for Wells Fargo checking and Chase credit card exports.

Wells Fargo format: Date, Amount, *, *, Description (no header row)
Chase format:      Transaction Date, Post Date, Description, Category, Type, Amount (with header)
"""

import logging
from datetime import date
from pathlib import Path
from typing import List

import pandas as pd

from .models import Transaction

logger = logging.getLogger(__name__)


def parse_wells_fargo(filepath: str | Path) -> List[Transaction]:
    """Parse a Wells Fargo checking CSV into a list of Transactions.

    WF CSVs have no header. Columns: Date, Amount, *, *, Description
    """
    transactions = []
    try:
        df = pd.read_csv(
            filepath,
            header=None,
            names=["date", "amount", "col2", "col3", "description"],
            dtype=str,
        )
        for _, row in df.iterrows():
            try:
                txn_date = _parse_date(str(row["date"]).strip())
                amount = float(str(row["amount"]).replace(",", "").strip())
                description = str(row["description"]).strip()
                transactions.append(
                    Transaction(
                        date=txn_date,
                        description=description,
                        amount=amount,
                        source="Wells Fargo",
                        raw_file=str(filepath),
                    )
                )
            except Exception as e:
                logger.warning(f"Skipping WF row {_}: {e} | row={row.to_dict()}")
    except Exception as e:
        logger.error(f"Failed to parse Wells Fargo file {filepath}: {e}")
    return transactions


def parse_chase(filepath: str | Path) -> List[Transaction]:
    """Parse a Chase credit card CSV into a list of Transactions.

    Chase CSVs have a header row:
    Transaction Date, Post Date, Description, Category, Type, Amount
    """
    transactions = []
    try:
        df = pd.read_csv(filepath, dtype=str)
        # Normalize column names
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
        for _, row in df.iterrows():
            try:
                # Skip card payments (Type == "Payment") — not a property expense
                txn_type = str(row.get("type", "")).strip().lower()
                if txn_type == "payment":
                    logger.debug(f"Skipping Chase payment row: {row.get('description', '')}")
                    continue
                txn_date = _parse_date(str(row["transaction_date"]).strip())
                amount = float(str(row["amount"]).replace(",", "").strip())
                description = str(row["description"]).strip()
                transactions.append(
                    Transaction(
                        date=txn_date,
                        description=description,
                        amount=amount,
                        source="Chase",
                        raw_file=str(filepath),
                    )
                )
            except Exception as e:
                logger.warning(f"Skipping Chase row {_}: {e} | row={row.to_dict()}")
    except Exception as e:
        logger.error(f"Failed to parse Chase file {filepath}: {e}")
    return transactions


def _parse_date(date_str: str) -> date:
    """Try common date formats."""
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y", "%m/%d/%y"):
        try:
            from datetime import datetime
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {date_str!r}")


def detect_and_parse(filepath: str | Path) -> List[Transaction]:
    """Auto-detect CSV type by filename or structure and parse it."""
    path = Path(filepath)
    name = path.name.lower()
    if "chase" in name:
        return parse_chase(filepath)
    if "wells" in name or "wf" in name or "checking" in name:
        return parse_wells_fargo(filepath)

    # Fallback: peek at the header row
    try:
        with open(filepath, "r") as f:
            first_line = f.readline().lower()
        if "transaction date" in first_line or "post date" in first_line:
            return parse_chase(filepath)
        else:
            return parse_wells_fargo(filepath)
    except Exception:
        logger.warning(f"Could not detect format for {filepath}, trying Wells Fargo")
        return parse_wells_fargo(filepath)
