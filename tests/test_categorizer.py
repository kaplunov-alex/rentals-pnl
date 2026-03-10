"""Unit tests for categorizer.py — mocks the Claude API."""

import json
import sys
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.categorizer import _rule_based_match, categorize_transactions
from src.models import Transaction

SAMPLE_CONFIG = {
    "properties": ["Property 1", "Property 2", "Property 3"],
    "income_categories": ["Rental Income", "Security Deposit"],
    "categories": [
        "Mortgage", "Insurance", "Property Tax", "HOA",
        "Maintenance", "Utilities", "Property Management", "Other",
    ],
    "vendor_mappings": {
        "QUICKEN LOANS": {"property": "Property 1", "category": "Mortgage"},
        "STATE FARM": {"property": "Property 1", "category": "Insurance"},
    },
}


def _make_txn(description: str, amount: float = -100.0) -> Transaction:
    return Transaction(
        date=date(2025, 1, 15),
        description=description,
        amount=amount,
        source="Wells Fargo",
    )


class TestRuleBasedMatch:
    def test_exact_vendor_match(self):
        result = _rule_based_match("QUICKEN LOANS MORTGAGE PMT", SAMPLE_CONFIG["vendor_mappings"])
        assert result == {"property": "Property 1", "category": "Mortgage"}

    def test_partial_vendor_match(self):
        result = _rule_based_match("STATE FARM INSURANCE 8001234", SAMPLE_CONFIG["vendor_mappings"])
        assert result == {"property": "Property 1", "category": "Insurance"}

    def test_case_insensitive(self):
        result = _rule_based_match("quicken loans payment", SAMPLE_CONFIG["vendor_mappings"])
        assert result is not None
        assert result["category"] == "Mortgage"

    def test_no_match_returns_none(self):
        result = _rule_based_match("UNKNOWN VENDOR XYZ", SAMPLE_CONFIG["vendor_mappings"])
        assert result is None

    def test_empty_mappings(self):
        result = _rule_based_match("QUICKEN LOANS", {})
        assert result is None


class TestCategorizeTransactions:
    def test_rule_based_hits_no_api_call(self):
        txn = _make_txn("QUICKEN LOANS MORTGAGE PMT")
        with patch("src.categorizer._get_client") as mock_client:
            result = categorize_transactions([txn], SAMPLE_CONFIG, interactive=False)
            mock_client.assert_not_called()
        assert result[0].property == "Property 1"
        assert result[0].category == "Mortgage"
        assert not result[0].needs_review
        assert result[0].txn_type == "Expense"

    def test_claude_fallback_called_for_unknown(self):
        txn = _make_txn("ACME PLUMBING REPAIR")
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"property": "Property 2", "category": "Maintenance"}')]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with patch("src.categorizer._get_client", return_value=mock_client):
            result = categorize_transactions([txn], SAMPLE_CONFIG, interactive=False)

        assert result[0].property == "Property 2"
        assert result[0].category == "Maintenance"
        assert not result[0].needs_review
        assert result[0].txn_type == "Expense"

    def test_claude_null_response_flags_review(self):
        txn = _make_txn("STARBUCKS COFFEE 12345")
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"property": null, "category": null}')]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with patch("src.categorizer._get_client", return_value=mock_client):
            result = categorize_transactions([txn], SAMPLE_CONFIG, interactive=False)

        assert result[0].needs_review
        assert result[0].category == "REVIEW"

    def test_claude_bad_json_flags_review(self):
        txn = _make_txn("WEIRD TRANSACTION")
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="not valid json")]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with patch("src.categorizer._get_client", return_value=mock_client):
            result = categorize_transactions([txn], SAMPLE_CONFIG, interactive=False)

        assert result[0].needs_review
        assert result[0].category == "REVIEW"

    def test_multiple_transactions_mixed(self):
        txns = [
            _make_txn("QUICKEN LOANS MORTGAGE PMT"),  # rule-based
            _make_txn("UNKNOWN VENDOR XYZ"),           # claude
        ]
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"property": "Property 3", "category": "Other"}')]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with patch("src.categorizer._get_client", return_value=mock_client):
            result = categorize_transactions(txns, SAMPLE_CONFIG, interactive=False)

        # First: rule-based
        assert result[0].category == "Mortgage"
        assert not result[0].needs_review
        assert result[0].txn_type == "Expense"
        # Second: Claude
        assert result[1].category == "Other"
        assert result[1].property == "Property 3"
        assert result[1].txn_type == "Expense"
        # Claude called exactly once (only for unknown)
        mock_client.messages.create.assert_called_once()

    def test_positive_amount_infers_income_type(self):
        """Positive-amount transaction should be typed as Income."""
        txn = _make_txn("RENT PAYMENT RECEIVED", amount=1500.0)
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"property": "Property 1", "category": "Rental Income"}')]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with patch("src.categorizer._get_client", return_value=mock_client):
            result = categorize_transactions([txn], SAMPLE_CONFIG, interactive=False)

        assert result[0].txn_type == "Income"
        assert result[0].category == "Rental Income"

    def test_negative_amount_infers_expense_type(self):
        """Negative-amount transaction should be typed as Expense."""
        txn = _make_txn("ACME PLUMBING REPAIR", amount=-250.0)
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"property": "Property 2", "category": "Maintenance"}')]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with patch("src.categorizer._get_client", return_value=mock_client):
            result = categorize_transactions([txn], SAMPLE_CONFIG, interactive=False)

        assert result[0].txn_type == "Expense"
