"""
main.py — Orchestrates the rental P&L automation pipeline.

Steps:
1. Load config.yaml
2. Find CSV files in downloads/
3. Parse each CSV (detect WF vs Chase)
4. Filter out transactions already in the sheet (by date)
5. Categorize transactions (rule-based → Claude Haiku fallback)
6. Write to Google Sheets
7. Log results to CSV audit trail
8. Print summary
"""

import csv
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import yaml
from dotenv import load_dotenv

# Allow running as `python src/main.py` from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.categorizer import categorize_transactions
from src.csv_parser import detect_and_parse
from src.models import Transaction
from src.sheets_writer import append_transactions

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def find_csv_files(downloads_dir: str) -> List[Path]:
    d = Path(downloads_dir)
    if not d.exists():
        logger.warning(f"Downloads directory not found: {downloads_dir}")
        return []
    return sorted(d.glob("*.csv"))


def write_audit_log(transactions: List[Transaction], logs_dir: str = "logs") -> None:
    Path(logs_dir).mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = Path(logs_dir) / f"audit_{timestamp}.csv"
    with open(log_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["date", "description", "amount", "source", "property", "category",
             "type", "needs_review", "raw_file"]
        )
        for txn in transactions:
            writer.writerow([
                txn.date, txn.description, txn.amount, txn.source,
                txn.property, txn.category, txn.txn_type, txn.needs_review, txn.raw_file,
            ])
    logger.info(f"Audit log written: {log_path}")


def run(config_path: str = "config.yaml", interactive: bool = True, only_file: str = None, month: str = None) -> None:
    config = load_config(config_path)
    spreadsheet_id: str = config["spreadsheet_id"]
    downloads_dir: str = config.get("downloads_dir", "./downloads")
    service_account_path: str = config.get("service_account_path", "service_account.json")

    # Parse CSV files (all, or a single specified file)
    if only_file:
        p = Path(only_file)
        if not p.exists():
            # Try relative to downloads dir
            p = Path(downloads_dir) / only_file
        csv_files = [p] if p.exists() else []
        if not csv_files:
            logger.error(f"File not found: {only_file}")
            return
    else:
        csv_files = find_csv_files(downloads_dir)

    if not csv_files:
        logger.info("No CSV files found in downloads/ — nothing to do.")
        return

    all_transactions: List[Transaction] = []
    for csv_file in csv_files:
        logger.info(f"Parsing {csv_file.name}…")
        try:
            txns = detect_and_parse(csv_file)
            logger.info(f"  → {len(txns)} transactions")
            all_transactions.extend(txns)
        except Exception as e:
            logger.error(f"Failed to parse {csv_file.name}: {e} — skipping")

    if not all_transactions:
        logger.info("No transactions parsed.")
        return

    # Skip transactions matching any pattern in skip_descriptions (case-insensitive)
    skip_patterns = [s.lower() for s in config.get("skip_descriptions", [])]
    if skip_patterns:
        before = len(all_transactions)
        all_transactions = [
            t for t in all_transactions
            if not any(p in t.description.lower() for p in skip_patterns)
        ]
        skipped = before - len(all_transactions)
        if skipped:
            logger.info(f"Skipped {skipped} transactions matching skip_descriptions.")

    # Filter by month if specified
    if month:
        try:
            filter_year, filter_month = int(month[:4]), int(month[5:7])
        except (ValueError, IndexError):
            logger.error(f"Invalid --month format {month!r}. Use YYYY-MM (e.g. 2026-01).")
            return
        before = len(all_transactions)
        all_transactions = [
            t for t in all_transactions
            if t.date.year == filter_year and t.date.month == filter_month
        ]
        logger.info(f"Month filter {month}: kept {len(all_transactions)} of {before} transactions.")
        if not all_transactions:
            logger.info("No transactions for the specified month.")
            return

    # Categorize (may expand list due to splits)
    logger.info(f"Categorizing {len(all_transactions)} transactions…")
    all_transactions = categorize_transactions(all_transactions, config, interactive=interactive, config_path=config_path)

    # Write to Sheets (overwrites cell totals — idempotent per month)
    logger.info(f"Writing {len(all_transactions)} transactions to Google Sheets…")
    written = append_transactions(all_transactions, spreadsheet_id, service_account_path)

    # Audit log
    write_audit_log(all_transactions)

    # Summary
    total = len(all_transactions)
    auto_categorized = sum(1 for t in all_transactions if not t.needs_review and t.category)
    flagged = sum(1 for t in all_transactions if t.needs_review)

    print("\n" + "=" * 50)
    print("  Rental P&L Automation — Run Summary")
    print("=" * 50)
    print(f"  CSV files processed : {len(csv_files)}")
    print(f"  Transactions parsed : {total}")
    print(f"  Auto-categorized    : {auto_categorized}")
    print(f"  Flagged for review  : {flagged}")
    for sheet, count in written.items():
        print(f"  → {sheet}: {count} transactions written to sheet")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Rental P&L Automation Pipeline")
    parser.add_argument("--config", default="config.yaml", help="Path to config file")
    parser.add_argument("--no-interactive", action="store_true", help="Skip interactive prompts; flag unknowns as REVIEW")
    parser.add_argument("--file", default=None, help="Process a single CSV file instead of all files in downloads/")
    parser.add_argument("--month", default=None, metavar="YYYY-MM", help="Only process transactions from this month (e.g. 2026-01)")
    args = parser.parse_args()
    run(args.config, interactive=not args.no_interactive, only_file=args.file, month=args.month)
