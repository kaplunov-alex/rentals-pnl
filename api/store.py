"""
In-memory transaction store for the API review workflow.

Transactions are uploaded, auto-categorized, and held here until the user
confirms and triggers a pipeline run to write them to Google Sheets.
The store is reset each time new CSVs are uploaded.
"""

from typing import Dict
from src.models import Transaction

# UUID -> Transaction
transactions: Dict[str, Transaction] = {}

# Last pipeline run result
last_run: dict | None = None
is_running: bool = False
