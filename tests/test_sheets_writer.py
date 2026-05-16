"""Unit tests for sheets_writer.py — mocks gspread, no real network calls."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.sheets_writer import _parse_row_date, read_property_sheet_transactions, update_property_sheet_transaction

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


# ─── update_property_sheet_transaction ───────────────────────────────────────

UPDATE_CONFIG = {
    "spreadsheet_id": "fake-pnl-id",
    "properties": ["30 Bishop Oak", "154 Santa Clara"],
    "income_categories": ["Rental Income"],
    "categories": ["Mortgage", "Maintenance", "Insurance"],
    "property_sheets": {
        "30 Bishop Oak": {"spreadsheet_id": "fake-id-bishop"},
        "154 Santa Clara": {"spreadsheet_id": "fake-id-santa"},
    },
}

# Sheet rows: [Date, Vendor, Amount, Bank/Card, Category, Comments]
_HEADER = ["Date", "Vendor", "Amount", "Bank/Card", "Category", "Comments"]
_EXISTING_ROWS = [
    _HEADER,
    ["2026-04-08", "WF HOME MTG", "-6607.10", "Wells Fargo", "Mortgage", ""],
    ["2026-04-14", "ALTITUDE RMS", "-59.00", "Wells Fargo", "Property Management", ""],
]


def _make_update_client(rows=None):
    """Mock gspread client for a single property sheet."""
    ws = MagicMock()
    ws.get_all_values.return_value = rows or _EXISTING_ROWS
    spreadsheet = MagicMock()
    spreadsheet.worksheet.return_value = ws
    client = MagicMock()
    client.open_by_key.return_value = spreadsheet
    return client, ws


class TestUpdatePropertySheetTransaction:
    def test_updates_category_in_place(self):
        mock_client, ws = _make_update_client()
        with patch("src.sheets_writer._get_client", return_value=mock_client):
            with patch("src.sheets_writer.recalculate_pnl_for_property_month") as mock_recalc:
                update_property_sheet_transaction(
                    config=UPDATE_CONFIG,
                    date_str="2026-04-08",
                    vendor="WF HOME MTG",
                    amount=-6607.10,
                    original_property="30 Bishop Oak",
                    new_category="Insurance",
                )
        # Column 5 (E) updated with new category
        ws.update_cell.assert_any_call(2, 5, "Insurance")
        # P&L recalculated because category changed
        mock_recalc.assert_called_once_with(UPDATE_CONFIG, "30 Bishop Oak", "2026-04", "service_account.json")

    def test_updates_comments_in_place_no_pnl_recalc(self):
        mock_client, ws = _make_update_client()
        with patch("src.sheets_writer._get_client", return_value=mock_client):
            with patch("src.sheets_writer.recalculate_pnl_for_property_month") as mock_recalc:
                update_property_sheet_transaction(
                    config=UPDATE_CONFIG,
                    date_str="2026-04-08",
                    vendor="WF HOME MTG",
                    amount=-6607.10,
                    original_property="30 Bishop Oak",
                    new_comments="April mortgage payment",
                )
        ws.update_cell.assert_any_call(2, 6, "April mortgage payment")
        # Category unchanged — no P&L recalc needed
        mock_recalc.assert_not_called()

    def test_raises_when_row_not_found(self):
        mock_client, _ = _make_update_client()
        with patch("src.sheets_writer._get_client", return_value=mock_client):
            with pytest.raises(ValueError, match="not found"):
                update_property_sheet_transaction(
                    config=UPDATE_CONFIG,
                    date_str="2026-04-01",
                    vendor="NONEXISTENT VENDOR",
                    amount=-999.00,
                    original_property="30 Bishop Oak",
                )

    def test_moves_row_to_new_property(self):
        src_client, src_ws = _make_update_client()
        tgt_ws = MagicMock()
        tgt_ws.get_all_values.return_value = [_HEADER]
        tgt_spreadsheet = MagicMock()
        tgt_spreadsheet.worksheet.return_value = tgt_ws

        def open_by_key(sid):
            if sid == "fake-id-bishop":
                return src_client.open_by_key.return_value
            return tgt_spreadsheet

        src_client.open_by_key.side_effect = open_by_key

        with patch("src.sheets_writer._get_client", return_value=src_client):
            with patch("src.sheets_writer.recalculate_pnl_for_property_month") as mock_recalc:
                update_property_sheet_transaction(
                    config=UPDATE_CONFIG,
                    date_str="2026-04-08",
                    vendor="WF HOME MTG",
                    amount=-6607.10,
                    original_property="30 Bishop Oak",
                    new_property="154 Santa Clara",
                    new_category="Mortgage",
                )

        # Row deleted from source
        src_ws.delete_rows.assert_called_once_with(2)
        # Row appended to target
        tgt_ws.append_row.assert_called_once()
        appended = tgt_ws.append_row.call_args[0][0]
        assert appended[0] == "2026-04-08"
        assert appended[1] == "WF HOME MTG"
        assert appended[4] == "Mortgage"

        # P&L recalculated for both properties
        recalc_calls = {c[0][1] for c in mock_recalc.call_args_list}
        assert "30 Bishop Oak" in recalc_calls
        assert "154 Santa Clara" in recalc_calls

    def test_raises_for_unknown_property(self):
        mock_client, _ = _make_update_client()
        with patch("src.sheets_writer._get_client", return_value=mock_client):
            with pytest.raises(ValueError, match="No property_sheets entry"):
                update_property_sheet_transaction(
                    config=UPDATE_CONFIG,
                    date_str="2026-04-08",
                    vendor="WF HOME MTG",
                    amount=-6607.10,
                    original_property="Unknown Property",
                )
