"""Tests for enriched evidence ingestion (Phase 3)."""
import pytest
from backend.app.verifier.evidence import parse_table_evidence, ingest_evidence


_LAYOUT_A = {
    "columns": ["Line Item", "2022", "2023"],
    "rows": [
        ["Revenue", "500000", "620000"],
        ["COGS", "200000", "250000"],
        ["Gross Profit", "300000", "370000"],
    ],
    "units": {},
}

_LAYOUT_B = {
    "columns": ["Period", "Line Item", "Value"],
    "rows": [
        ["2022", "Revenue", "500000"],
        ["2023", "Revenue", "620000"],
        ["2022", "COGS", "200000"],
    ],
    "units": {},
}


def test_layout_a_produces_items():
    items = parse_table_evidence(_LAYOUT_A)
    assert len(items) == 6  # 3 rows * 2 period columns


def test_layout_a_row_label():
    items = parse_table_evidence(_LAYOUT_A)
    labels = {it.row_label for it in items}
    assert "Revenue" in labels
    assert "COGS" in labels


def test_layout_a_period():
    items = parse_table_evidence(_LAYOUT_A)
    periods = {it.period for it in items}
    assert "2022" in periods
    assert "2023" in periods


def test_layout_a_canonical_line_item():
    items = parse_table_evidence(_LAYOUT_A)
    revenue_items = [it for it in items if it.canonical_line_item == "revenue"]
    assert len(revenue_items) == 2


def test_layout_b_produces_items():
    items = parse_table_evidence(_LAYOUT_B)
    assert len(items) == 3


def test_layout_b_period():
    items = parse_table_evidence(_LAYOUT_B)
    periods = {it.period for it in items}
    assert "2022" in periods
    assert "2023" in periods


def test_layout_b_row_label():
    items = parse_table_evidence(_LAYOUT_B)
    labels = {it.row_label for it in items}
    assert "Revenue" in labels


def test_col_index_and_row_index():
    items = parse_table_evidence(_LAYOUT_A)
    first = items[0]
    assert first.row_index == 0
    assert first.col_index == 1


def test_table_level_scale_detection():
    table = {
        "columns": ["Line Item", "2022 (in millions)", "2023 (in millions)"],
        "rows": [["Revenue", "5", "6"]],
        "units": {},
    }
    items = parse_table_evidence(table)
    assert all(it.scale_label == "M" for it in items)


def test_ingest_text_evidence():
    items = ingest_evidence({"type": "text", "content": "Revenue was 500000."})
    assert len(items) >= 1
    assert items[0].source == "text"


def test_ingest_unknown_type():
    items = ingest_evidence({"type": "image", "content": "data"})
    assert items == []
