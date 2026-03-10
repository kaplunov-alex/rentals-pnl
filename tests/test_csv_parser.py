"""Unit tests for csv_parser.py using fixture files."""

import sys
from pathlib import Path

import pytest

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.csv_parser import detect_and_parse, parse_chase, parse_wells_fargo

FIXTURES = Path(__file__).parent / "fixtures"
WF_CSV = FIXTURES / "wells_fargo_sample.csv"
CHASE_CSV = FIXTURES / "chase_sample.csv"


class TestWellsFargoParser:
    def test_returns_correct_count(self):
        txns = parse_wells_fargo(WF_CSV)
        assert len(txns) == 5

    def test_source_is_wells_fargo(self):
        txns = parse_wells_fargo(WF_CSV)
        assert all(t.source == "Wells Fargo" for t in txns)

    def test_first_row_date(self):
        from datetime import date
        txns = parse_wells_fargo(WF_CSV)
        assert txns[0].date == date(2025, 1, 5)

    def test_first_row_amount(self):
        txns = parse_wells_fargo(WF_CSV)
        assert txns[0].amount == -1250.00

    def test_first_row_description(self):
        txns = parse_wells_fargo(WF_CSV)
        assert "QUICKEN LOANS" in txns[0].description

    def test_positive_amount(self):
        txns = parse_wells_fargo(WF_CSV)
        rent = [t for t in txns if t.amount > 0]
        assert len(rent) == 1
        assert rent[0].amount == 2400.00

    def test_raw_file_is_set(self):
        txns = parse_wells_fargo(WF_CSV)
        assert all(t.raw_file for t in txns)

    def test_nonexistent_file_returns_empty(self):
        txns = parse_wells_fargo(FIXTURES / "does_not_exist.csv")
        assert txns == []


class TestChaseParser:
    def test_returns_correct_count(self):
        txns = parse_chase(CHASE_CSV)
        assert len(txns) == 5

    def test_source_is_chase(self):
        txns = parse_chase(CHASE_CSV)
        assert all(t.source == "Chase" for t in txns)

    def test_first_row_date(self):
        from datetime import date
        txns = parse_chase(CHASE_CSV)
        assert txns[0].date == date(2025, 1, 6)

    def test_first_row_amount(self):
        txns = parse_chase(CHASE_CSV)
        assert txns[0].amount == -120.00

    def test_description_preserved(self):
        txns = parse_chase(CHASE_CSV)
        assert txns[0].description == "HOME DEPOT #1234"

    def test_nonexistent_file_returns_empty(self):
        txns = parse_chase(FIXTURES / "does_not_exist.csv")
        assert txns == []


class TestAutoDetect:
    def test_detects_chase_by_filename(self):
        txns = detect_and_parse(CHASE_CSV)
        assert all(t.source == "Chase" for t in txns)

    def test_detects_wf_by_filename(self):
        txns = detect_and_parse(WF_CSV)
        assert all(t.source == "Wells Fargo" for t in txns)
