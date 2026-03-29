"""Unit tests for the assess_ingestion() function in the ingestion confidence layer."""
import pytest

from backend.app.verifier.ingestion import assess_ingestion


# ---------------------------------------------------------------------------
# Test 1: High-coverage table — all rows map to canonical items
# ---------------------------------------------------------------------------

def test_full_coverage_rule_based():
    """Standard Apple FY2023 P&L — all rows should match canonical synonyms."""
    table = {
        "columns": ["", "FY2023", "FY2022"],
        "rows": [
            ["Net sales", "383,285", "394,328"],
            ["Cost of sales", "214,137", "223,546"],
            ["Gross margin", "169,148", "170,782"],
            ["Operating expenses", "54,847", "51,345"],
            ["Operating income", "114,301", "119,437"],
            ["Income taxes", "29,749", "19,300"],
            ["Net income", "96,995", "99,803"],
        ],
    }
    result = assess_ingestion(table, llm_available=False)

    assert result["mode"] == "rule_based"
    assert result["coverage"] >= 0.8, f"Expected coverage >= 0.8, got {result['coverage']}"
    assert result["confidence"] > 0.0
    assert isinstance(result["matched_rows"], list)
    assert isinstance(result["unmapped_rows"], list)
    assert isinstance(result["llm_suggestions"], dict)
    assert len(result["llm_suggestions"]) == 0  # LLM not triggered


# ---------------------------------------------------------------------------
# Test 2: Low-coverage table — ambiguous/unknown row labels
# ---------------------------------------------------------------------------

def test_low_coverage_no_llm():
    """Table with completely unknown labels — coverage should be low, no LLM."""
    table = {
        "columns": ["Category", "2023"],
        "rows": [
            ["Widget Manufacturing Output", "50000"],
            ["Distribution Network Costs", "12000"],
            ["Customer Acquisition Pipeline", "8000"],
            ["Inventory Turnover Index", "1.5"],
        ],
    }
    result = assess_ingestion(table, llm_available=False)

    assert result["mode"] == "rule_based"
    assert result["coverage"] < 0.5, f"Expected low coverage, got {result['coverage']}"
    assert len(result["unmapped_rows"]) > 0
    assert len(result["llm_suggestions"]) == 0


# ---------------------------------------------------------------------------
# Test 3: Empty table — returns zero coverage, no errors
# ---------------------------------------------------------------------------

def test_empty_table():
    """Empty rows should return zero coverage gracefully."""
    table = {
        "columns": ["Item", "Value"],
        "rows": [],
    }
    result = assess_ingestion(table)

    assert result["mode"] == "rule_based"
    assert result["coverage"] == 0.0
    assert result["confidence"] == 0.0
    assert result["matched_rows"] == []
    assert result["unmapped_rows"] == []
    assert result["llm_suggestions"] == {}


# ---------------------------------------------------------------------------
# Test 4: Partial coverage — mix of matched and unmatched
# ---------------------------------------------------------------------------

def test_partial_coverage():
    """Table with some recognizable and some unrecognized rows."""
    table = {
        "columns": ["Line Item", "FY2023"],
        "rows": [
            ["Revenue", "100000"],          # maps to revenue
            ["Net income", "15000"],         # maps to net_income
            ["Q4 Adjustment Factor", "500"],  # unknown
        ],
    }
    result = assess_ingestion(table, llm_available=False)

    assert result["mode"] == "rule_based"
    # At least 2 out of 3 rows match
    assert result["coverage"] >= 0.5, f"Expected coverage >= 0.5, got {result['coverage']}"
    assert "Revenue" in result["matched_rows"] or "Net income" in result["matched_rows"]
    assert len(result["unmapped_rows"]) >= 1


# ---------------------------------------------------------------------------
# Test 5: Result dict has all required keys
# ---------------------------------------------------------------------------

def test_result_shape():
    """Result must always contain all required keys."""
    table = {
        "columns": ["Item", "2023"],
        "rows": [["Gross profit", "50000"]],
    }
    result = assess_ingestion(table)

    required_keys = {"mode", "coverage", "matched_rows", "unmapped_rows", "llm_suggestions", "confidence"}
    assert required_keys.issubset(result.keys()), f"Missing keys: {required_keys - result.keys()}"
    assert result["mode"] in ("rule_based", "llm_assisted")
    assert 0.0 <= result["coverage"] <= 1.0
    assert 0.0 <= result["confidence"] <= 1.0


# ---------------------------------------------------------------------------
# Test 6: Synonym variations map correctly
# ---------------------------------------------------------------------------

def test_synonym_variations():
    """Alternate synonyms from pnl_parser._SYNONYMS should match."""
    table = {
        "columns": ["Metric", "Value"],
        "rows": [
            ["Total revenue", "200000"],       # revenue
            ["Cost of goods sold", "100000"],  # cogs
            ["EBIT", "50000"],                 # operating_income
            ["Net earnings", "30000"],         # net_income
        ],
    }
    result = assess_ingestion(table, llm_available=False)

    assert result["coverage"] == 1.0, f"Expected full coverage, got {result['coverage']}"
    assert result["mode"] == "rule_based"
    assert len(result["unmapped_rows"]) == 0


# ---------------------------------------------------------------------------
# Test 7: LLM path not triggered when coverage is above threshold
# ---------------------------------------------------------------------------

def test_llm_not_triggered_when_coverage_high():
    """LLM should not be triggered if coverage is already above threshold."""
    table = {
        "columns": ["Item", "FY2023"],
        "rows": [
            ["Net sales", "383285"],
            ["Cost of sales", "214137"],
            ["Gross margin", "169148"],
            ["Net income", "96995"],
        ],
    }
    # Even with llm_available=True, coverage >= threshold → no LLM
    result = assess_ingestion(table, llm_available=True, confidence_threshold=0.5)

    # Coverage should be 100% for these well-known labels
    assert result["coverage"] >= 0.75
    # LLM suggestions must be empty because threshold not triggered
    assert result["llm_suggestions"] == {}
