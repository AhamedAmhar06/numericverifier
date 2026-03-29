"""Tests for CSV and XLSX P&L ingestion parsers."""
import csv
import io
import tempfile
from pathlib import Path

import pytest

from backend.app.ingestion.csv_pnl_parser import parse_csv_pnl


# --------------- CSV tests ---------------

def test_csv_basic_parse():
    buf = io.StringIO("Line Item,2022,2023\nRevenue,100000,120000\nCOGS,60000,70000\n")
    result = parse_csv_pnl(buf)
    assert result["columns"] == ["Line Item", "2022", "2023"]
    assert len(result["rows"]) == 2
    assert result["rows"][0] == ["Revenue", "100000", "120000"]
    assert result["units"] == {}


def test_csv_file_path():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Item", "2021"])
        writer.writerow(["Revenue", "500"])
        f.flush()
        path = Path(f.name)
    result = parse_csv_pnl(path)
    assert result["columns"] == ["Item", "2021"]
    assert result["rows"] == [["Revenue", "500"]]
    path.unlink()


def test_csv_empty_cells():
    buf = io.StringIO("A,B,C\n1,,3\n,,\n")
    result = parse_csv_pnl(buf)
    assert result["rows"][0] == ["1", "", "3"]
    assert result["rows"][1] == ["", "", ""]


def test_csv_short_row_padded():
    buf = io.StringIO("A,B,C\n1\n")
    result = parse_csv_pnl(buf)
    assert result["rows"][0] == ["1", "", ""]


def test_csv_empty_file_raises():
    buf = io.StringIO("")
    with pytest.raises(ValueError, match="empty"):
        parse_csv_pnl(buf)


def test_csv_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        parse_csv_pnl("/nonexistent/path/file.csv")


# --------------- XLSX tests ---------------

def _write_xlsx(rows, path):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    wb.save(path)
    wb.close()


def test_xlsx_basic_parse():
    openpyxl = pytest.importorskip("openpyxl")
    from backend.app.ingestion.excel_pnl_parser import parse_excel_pnl
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        path = Path(f.name)
    _write_xlsx([["Item", "2022"], ["Revenue", 100000]], path)
    result = parse_excel_pnl(path)
    assert result["columns"] == ["Item", "2022"]
    assert len(result["rows"]) == 1
    assert result["rows"][0][0] == "Revenue"
    assert result["rows"][0][1] == "100000"
    path.unlink()


def test_xlsx_empty_cells():
    openpyxl = pytest.importorskip("openpyxl")
    from backend.app.ingestion.excel_pnl_parser import parse_excel_pnl
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        path = Path(f.name)
    _write_xlsx([["A", "B"], [None, "val"], ["x", None]], path)
    result = parse_excel_pnl(path)
    assert result["rows"][0] == ["", "val"]
    assert result["rows"][1] == ["x", ""]
    path.unlink()


def test_xlsx_missing_file_raises():
    openpyxl = pytest.importorskip("openpyxl")
    from backend.app.ingestion.excel_pnl_parser import parse_excel_pnl
    with pytest.raises(FileNotFoundError):
        parse_excel_pnl("/nonexistent/file.xlsx")


def test_xlsx_empty_sheet_raises():
    openpyxl = pytest.importorskip("openpyxl")
    from backend.app.ingestion.excel_pnl_parser import parse_excel_pnl
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        path = Path(f.name)
    _write_xlsx([], path)
    with pytest.raises(ValueError, match="empty"):
        parse_excel_pnl(path)
    path.unlink()
