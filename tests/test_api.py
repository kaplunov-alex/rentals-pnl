"""Integration-style tests for the FastAPI routes using TestClient.

All Google Sheets / external I/O is mocked — no network calls made.
"""

import sys
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from api.app import app
from api import store
from src.models import Transaction

FIXTURES = Path(__file__).parent / "fixtures"

SAMPLE_CONFIG = {
    "spreadsheet_id": "fake-spreadsheet-id",
    "properties": ["154 Santa Clara", "30 Bishop Oak", "11873 E Maplewood"],
    "income_categories": ["Rental Income", "Security Deposit"],
    "categories": [
        "Mortgage", "Insurance", "Property Tax", "HOA",
        "Maintenance", "Utilities", "Property Management", "Other",
    ],
    "vendor_mappings": {
        "QUICKEN LOANS": {"property": "154 Santa Clara", "category": "Mortgage"},
    },
    "property_sheets": {
        "154 Santa Clara": {"spreadsheet_id": "fake-id-santa"},
    },
    "skip_descriptions": [],
}


def _make_txn(
    description="QUICKEN LOANS PMT",
    amount=-1250.0,
    property="154 Santa Clara",
    category="Mortgage",
    needs_review=False,
    txn_date=date(2026, 2, 1),
) -> Transaction:
    t = Transaction(
        date=txn_date,
        description=description,
        amount=amount,
        source="Wells Fargo",
    )
    t.property = property
    t.category = category
    t.needs_review = needs_review
    t.txn_type = "Expense" if amount < 0 else "Income"
    t.raw_file = "test.csv"
    return t


@pytest.fixture(autouse=True)
def clear_store():
    """Reset in-memory store before each test."""
    store.transactions.clear()
    store.last_run = None
    store.is_running = False
    yield
    store.transactions.clear()
    store.last_run = None
    store.is_running = False


@pytest.fixture()
def client():
    with patch("api.dependencies.get_config", return_value=SAMPLE_CONFIG):
        with patch("api.dependencies._config_cache", SAMPLE_CONFIG):
            with TestClient(app) as c:
                yield c


# ─── Health ──────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_ok(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


# ─── Transactions — list / update / delete ───────────────────────────────────

class TestListTransactions:
    def test_empty_store(self, client):
        r = client.get("/api/transactions")
        assert r.status_code == 200
        assert r.json() == []

    def test_returns_stored_transaction(self, client):
        store.transactions["abc"] = _make_txn()
        r = client.get("/api/transactions")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["id"] == "abc"
        assert data[0]["category"] == "Mortgage"

    def test_month_filter_matches(self, client):
        store.transactions["feb"] = _make_txn(txn_date=date(2026, 2, 1))
        store.transactions["jan"] = _make_txn(txn_date=date(2026, 1, 1))
        r = client.get("/api/transactions?month=2026-02")
        assert r.status_code == 200
        ids = [t["id"] for t in r.json()]
        assert "feb" in ids
        assert "jan" not in ids

    def test_month_filter_invalid_format(self, client):
        store.transactions["t1"] = _make_txn()
        r = client.get("/api/transactions?month=not-valid")
        # Route raises 400 on invalid format
        assert r.status_code == 400


class TestUpdateTransaction:
    def test_update_category_clears_needs_review(self, client):
        store.transactions["t1"] = _make_txn(needs_review=True, category="REVIEW")
        r = client.patch("/api/transactions/t1", json={"category": "Maintenance"})
        assert r.status_code == 200
        data = r.json()
        assert data["category"] == "Maintenance"
        assert data["needs_review"] is False

    def test_update_property(self, client):
        store.transactions["t1"] = _make_txn()
        r = client.patch("/api/transactions/t1", json={"property": "30 Bishop Oak"})
        assert r.status_code == 200
        assert r.json()["property"] == "30 Bishop Oak"

    def test_update_comments(self, client):
        store.transactions["t1"] = _make_txn()
        r = client.patch("/api/transactions/t1", json={"comments": "Feb mortgage"})
        assert r.status_code == 200
        assert r.json()["comments"] == "Feb mortgage"

    def test_not_found_returns_404(self, client):
        r = client.patch("/api/transactions/nonexistent", json={"category": "Other"})
        assert r.status_code == 404


class TestDeleteTransaction:
    def test_delete_removes_transaction(self, client):
        store.transactions["t1"] = _make_txn()
        r = client.delete("/api/transactions/t1")
        assert r.status_code == 204
        assert "t1" not in store.transactions

    def test_delete_not_found_returns_404(self, client):
        r = client.delete("/api/transactions/missing")
        assert r.status_code == 404


class TestBulkUpdate:
    def test_bulk_update_multiple(self, client):
        store.transactions["a"] = _make_txn(needs_review=True, category="REVIEW")
        store.transactions["b"] = _make_txn(needs_review=True, category="REVIEW")
        r = client.post("/api/transactions/bulk-update", json={
            "updates": [
                {"id": "a", "category": "Maintenance", "property": "30 Bishop Oak"},
                {"id": "b", "category": "Utilities"},
            ]
        })
        assert r.status_code == 200
        by_id = {t["id"]: t for t in r.json()}
        assert by_id["a"]["category"] == "Maintenance"
        assert by_id["a"]["needs_review"] is False
        assert by_id["b"]["category"] == "Utilities"

    def test_bulk_update_missing_id_returns_404(self, client):
        r = client.post("/api/transactions/bulk-update", json={
            "updates": [{"id": "ghost", "category": "Other"}]
        })
        assert r.status_code == 404


class TestUploadCSV:
    def test_upload_wf_csv(self, client):
        csv_content = (FIXTURES / "wells_fargo_sample.csv").read_bytes()
        with patch("api.routes.transactions.get_config", return_value=SAMPLE_CONFIG):
            with patch("api.routes.transactions.categorize_transactions") as mock_cat:
                # Return the same transactions, fully categorized
                def passthrough(txns, cfg, interactive):
                    for t in txns:
                        t.property = "154 Santa Clara"
                        t.category = "Mortgage"
                        t.needs_review = False
                        t.txn_type = "Expense"
                        t.raw_file = t.raw_file or "wf.csv"
                    return txns
                mock_cat.side_effect = passthrough

                r = client.post(
                    "/api/transactions/upload",
                    files=[("files", ("wells_fargo_sample.csv", csv_content, "text/csv"))],
                )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] > 0
        assert data["needs_review"] == 0


# ─── Pipeline ─────────────────────────────────────────────────────────────────

class TestPipelineStatus:
    def test_initial_status(self, client):
        r = client.get("/api/pipeline/status")
        assert r.status_code == 200
        data = r.json()
        assert data["running"] is False
        assert data["last_run"] is None


class TestPipelineRun:
    def test_run_fails_when_store_empty(self, client):
        r = client.post("/api/pipeline/run", json={})
        assert r.status_code == 422

    def test_run_fails_when_already_running(self, client):
        store.transactions["t1"] = _make_txn()
        store.is_running = True
        r = client.post("/api/pipeline/run", json={})
        assert r.status_code == 409

    def test_run_fails_when_transactions_need_review(self, client):
        store.transactions["t1"] = _make_txn(needs_review=True)
        r = client.post("/api/pipeline/run", json={})
        assert r.status_code == 422

    def test_run_success(self, client):
        store.transactions["t1"] = _make_txn()
        with patch("api.routes.pipeline.get_config", return_value=SAMPLE_CONFIG):
            with patch("api.routes.pipeline.append_transactions", return_value={"154 Santa Clara": 5}):
                with patch("api.routes.pipeline.write_property_transaction_sheets", return_value={"154 Santa Clara": 1}):
                    r = client.post("/api/pipeline/run", json={})

        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "success"
        assert data["transactions_written"] == 5
        assert "P&L" in data["message"]

    def test_run_with_month_filter_no_match(self, client):
        store.transactions["t1"] = _make_txn(txn_date=date(2026, 1, 1))
        with patch("api.routes.pipeline.get_config", return_value=SAMPLE_CONFIG):
            r = client.post("/api/pipeline/run", json={"month": "2026-02"})
        assert r.status_code == 422


# ─── Config routes ────────────────────────────────────────────────────────────

class TestConfigRoutes:
    def test_get_categories(self, client):
        with patch("api.routes.config.get_config", return_value=SAMPLE_CONFIG):
            r = client.get("/api/config/categories")
        assert r.status_code == 200
        data = r.json()
        assert "Mortgage" in data["categories"]
        assert "Rental Income" in data["income_categories"]

    def test_get_properties(self, client):
        with patch("api.routes.config.get_config", return_value=SAMPLE_CONFIG):
            r = client.get("/api/config/properties")
        assert r.status_code == 200
        assert "154 Santa Clara" in r.json()["properties"]

    def test_list_vendor_mappings(self, client):
        with patch("api.routes.config.get_config", return_value=SAMPLE_CONFIG):
            r = client.get("/api/config/vendor-mappings")
        assert r.status_code == 200
        data = r.json()
        assert any(m["key"] == "QUICKEN LOANS" for m in data)

    def test_add_vendor_mapping(self, client):
        with patch("api.routes.config.get_config", return_value=SAMPLE_CONFIG):
            with patch("api.routes.config.save_vendor_mapping"):
                with patch("api.routes.config.reload_config", return_value=SAMPLE_CONFIG):
                    r = client.post("/api/config/vendor-mappings", json={
                        "key": "STATE FARM",
                        "property": "154 Santa Clara",
                        "category": "Insurance",
                    })
        assert r.status_code == 201
        assert r.json()["key"] == "STATE FARM"

    def test_delete_vendor_mapping_with_slash_in_key(self, client):
        """Keys containing slashes must be routable via {key:path}."""
        config_with_slash = {**SAMPLE_CONFIG, "vendor_mappings": {
            "ZELLE TO/FROM TENANT": {"property": "154 Santa Clara", "category": "Rental Income"},
        }}
        with patch("api.routes.config.get_config", return_value=config_with_slash):
            with patch("api.routes.config.save_vendor_mapping"):
                with patch("api.routes.config.reload_config", return_value=config_with_slash):
                    r = client.delete("/api/config/vendor-mappings/ZELLE TO/FROM TENANT")
        # The route must be reachable (not a 404/405 from routing failure)
        assert r.status_code in (200, 204)


class TestSheetsTransactionsRoute:
    def test_returns_transactions_for_month(self, client):
        mock_rows = [
            {
                "date": "2026-02-05",
                "vendor": "TENANT RENT",
                "amount": 3200.0,
                "source": "Wells Fargo",
                "category": "Rental Income",
                "comments": "",
                "property": "154 Santa Clara",
            }
        ]
        with patch("api.routes.config.get_config", return_value=SAMPLE_CONFIG):
            with patch("api.routes.config.read_property_sheet_transactions", return_value=mock_rows):
                r = client.get("/api/sheets/transactions?month=2026-02")

        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["vendor"] == "TENANT RENT"
        assert data[0]["amount"] == 3200.0

    def test_requires_month_param(self, client):
        r = client.get("/api/sheets/transactions")
        assert r.status_code == 422  # month is required

    def test_property_filter_passed_through(self, client):
        with patch("api.routes.config.get_config", return_value=SAMPLE_CONFIG):
            with patch("api.routes.config.read_property_sheet_transactions", return_value=[]) as mock_read:
                client.get("/api/sheets/transactions?month=2026-02&property=154+Santa+Clara")
                args = mock_read.call_args[0]
                assert args[1] == "2026-02"
                assert args[2] == "154 Santa Clara"


class TestOverviewRoute:
    def test_overview_returns_values(self, client):
        mock_data = {"total_income": 5000.0, "total_expenses": 3000.0, "net_cash_flow": 2000.0}
        with patch("api.routes.config.get_config", return_value=SAMPLE_CONFIG):
            with patch("api.routes.config.get_overview_cells", return_value=mock_data):
                r = client.get("/api/overview")
        assert r.status_code == 200
        data = r.json()
        assert data["total_income"] == 5000.0
        assert data["total_expenses"] == 3000.0
        assert data["net_cash_flow"] == 2000.0
