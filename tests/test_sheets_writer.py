"""Unit tests for sheets_writer.py — mocks gspread, no real network calls."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.sheets_writer import _parse_row_date, read_property_sheet_transactions

SAMPLE_CONFIG = {
    "property_sheets": {
        "30 Bishop Oak": {"spreadsheet_id": "fake-id-bishop"},
        "154 Santa Clara": {"spreadsheet_id": "fake-id-santa"},
    }
}


# ─── _parse_row_date ──────────────────────────────────────────────────────────

class TestParseRowDate:
    def test_m_d_yyyy(self):
        assert _parse_row_date("2/12/2026") == "2026-02-12"

    def test_m_d_yyyy_single_digit(self):
        assert _parse_row_date("1/5/2026") == "2026-01-05"

    def test_iso_format(self):
        assert _parse_row_date("2026-02-12") == "2026-02-12"

    def test_strips_whitespace(self):
        assert _parse_row_date("  2/12/2026  ") == "2026-02-12"

    def test_non_date_text_returns_none(self):
        assert _parse_row_date("m/d/yyyy") is None

    def test_empty_string_returns_none(self):
        assert _parse_row_date("") is None

    def test_garbage_returns_none(self):
        assert _parse_row_date("not a date at all") is None

    def test_vendor_text_returns_none(self):
        assert _parse_row_date("Vendor") is None


# ─── read_property_sheet_transactions ────────────────────────────────────────

def _make_sheet_rows(dates_amounts):
    """Build fake gspread get_all_values() output: header + data rows."""
    header = ["Date", "Vendor", "Amount", "Bank/Card", "Category", "Comments"]
    rows = [header]
    for date_str, vendor, amount, source, cat, comment in dates_amounts:
        rows.append([date_str, vendor, str(amount), source, cat, comment])
    return rows


def _make_mock_client(rows, worksheet_name_raises=False):
    """Return a mock gspread client that serves the given rows."""
    ws = MagicMock()
    ws.get_all_values.return_value = rows

    spreadsheet = MagicMock()
    if worksheet_name_raises:
        import gspread
        spreadsheet.worksheet.side_effect = gspread.exceptions.WorksheetNotFound
        spreadsheet.worksheets.return_value = [ws]
    else:
        spreadsheet.worksheet.return_value = ws

    client = MagicMock()
    client.open_by_key.return_value = spreadsheet
    return client


class TestReadPropertySheetTransactions:
    def test_empty_when_no_property_sheets_config(self):
        result = read_property_sheet_transactions({}, "2026-02")
        assert result == []

    def test_reads_matching_month(self):
        rows = _make_sheet_rows([
            ("2/12/2026", "Altitude RMS", "-59.00", "Wells Fargo", "Property Management", ""),
            ("2/5/2026",  "ZELLE FROM TENANT", "3200.00", "Wells Fargo", "Rental Income", "Feb rent"),
        ])
        mock_client = _make_mock_client(rows)
        with patch("src.sheets_writer._get_client", return_value=mock_client):
            result = read_property_sheet_transactions(SAMPLE_CONFIG, "2026-02", "30 Bishop Oak")

        assert len(result) == 2
        # Results sorted by date: ZELLE (2/5) before Altitude (2/12)
        by_vendor = {r["vendor"]: r for r in result}
        assert by_vendor["Altitude RMS"]["amount"] == -59.0
        assert by_vendor["ZELLE FROM TENANT"]["amount"] == 3200.0
        assert result[0]["date"] == "2026-02-05"
        assert result[0]["property"] == "30 Bishop Oak"

    def test_filters_out_wrong_month(self):
        rows = _make_sheet_rows([
            ("1/13/2026", "Altitude RMS", "-59.00", "Wells Fargo", "Property Management", ""),
            ("2/5/2026",  "ZELLE FROM TENANT", "3200.00", "Wells Fargo", "Rental Income", ""),
        ])
        mock_client = _make_mock_client(rows)
        with patch("src.sheets_writer._get_client", return_value=mock_client):
            result = read_property_sheet_transactions(SAMPLE_CONFIG, "2026-02", "30 Bishop Oak")

        assert len(result) == 1
        assert result[0]["date"] == "2026-02-05"

    def test_skips_non_date_rows(self):
        """Format rows like 'm/d/yyyy' or 'Vendor' in date column are skipped."""
        rows = [
            ["Date", "Vendor", "Amount", "Bank/Card", "Category", "Comments"],
            ["m/d/yyyy", "Vendor", "$xx", "", "", ""],  # format hint row
            ["2/5/2026", "ZELLE FROM TENANT", "3200.00", "Wells Fargo", "Rental Income", ""],
        ]
        mock_client = _make_mock_client(rows)
        with patch("src.sheets_writer._get_client", return_value=mock_client):
            result = read_property_sheet_transactions(SAMPLE_CONFIG, "2026-02", "30 Bishop Oak")

        assert len(result) == 1

    def test_strips_dollar_sign_from_amount(self):
        rows = _make_sheet_rows([
            ("2/5/2026", "ZELLE", "$3,200.00", "Wells Fargo", "Rental Income", ""),
        ])
        mock_client = _make_mock_client(rows)
        with patch("src.sheets_writer._get_client", return_value=mock_client):
            result = read_property_sheet_transactions(SAMPLE_CONFIG, "2026-02", "30 Bishop Oak")

        assert result[0]["amount"] == 3200.0

    def test_falls_back_to_first_worksheet_when_year_tab_missing(self):
        rows = _make_sheet_rows([
            ("2/5/2026", "TENANT RENT", "3200.00", "Wells Fargo", "Rental Income", ""),
        ])
        mock_client = _make_mock_client(rows, worksheet_name_raises=True)
        with patch("src.sheets_writer._get_client", return_value=mock_client):
            result = read_property_sheet_transactions(SAMPLE_CONFIG, "2026-02", "30 Bishop Oak")

        assert len(result) == 1
        assert result[0]["vendor"] == "TENANT RENT"

    def test_all_properties_aggregates(self):
        rows = _make_sheet_rows([
            ("2/5/2026", "TENANT RENT", "3200.00", "Wells Fargo", "Rental Income", ""),
        ])
        mock_client = _make_mock_client(rows)
        with patch("src.sheets_writer._get_client", return_value=mock_client):
            result = read_property_sheet_transactions(SAMPLE_CONFIG, "2026-02")  # no filter

        # Both properties read → 2 rows (one per property sheet, same mock data)
        assert len(result) == 2
        properties = {r["property"] for r in result}
        assert properties == {"30 Bishop Oak", "154 Santa Clara"}

    def test_property_filter_case_insensitive(self):
        rows = _make_sheet_rows([
            ("2/5/2026", "TENANT RENT", "3200.00", "Wells Fargo", "Rental Income", ""),
        ])
        mock_client = _make_mock_client(rows)
        with patch("src.sheets_writer._get_client", return_value=mock_client):
            result = read_property_sheet_transactions(SAMPLE_CONFIG, "2026-02", "30 bishop oak")

        assert len(result) == 1
        assert result[0]["property"] == "30 Bishop Oak"

    def test_results_sorted_by_date(self):
        rows = _make_sheet_rows([
            ("2/20/2026", "LATE VENDOR", "-100.00", "Chase", "Maintenance", ""),
            ("2/5/2026",  "EARLY VENDOR", "-50.00", "Wells Fargo", "Utilities", ""),
        ])
        mock_client = _make_mock_client(rows)
        with patch("src.sheets_writer._get_client", return_value=mock_client):
            result = read_property_sheet_transactions(SAMPLE_CONFIG, "2026-02", "30 Bishop Oak")

        assert result[0]["date"] == "2026-02-05"
        assert result[1]["date"] == "2026-02-20"

    def test_missing_spreadsheet_id_skipped(self):
        config = {"property_sheets": {"Bad Property": {}}}
        result = read_property_sheet_transactions(config, "2026-02")
        assert result == []

    def test_invalid_month_returns_empty(self):
        result = read_property_sheet_transactions(SAMPLE_CONFIG, "not-a-month")
        assert result == []
