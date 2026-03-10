from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class Transaction:
    date: date
    description: str
    amount: float
    source: str  # "Wells Fargo" or "Chase"
    property: Optional[str] = None
    category: Optional[str] = None
    needs_review: bool = False
    raw_file: str = ""
    txn_type: str = "Expense"  # "Income" or "Expense"

    def to_sheet_row(self):
        return [
            self.date.strftime("%Y-%m-%d"),
            self.description,
            self.category or "REVIEW",
            self.amount,
            self.source,
        ]
