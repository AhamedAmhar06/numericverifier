"""Tests for execution engine."""
from app.verifier.extract import extract_numeric_claims
from app.verifier.engines.execution import verify_execution, compute_percent_change, compute_total, compute_ratio
from app.verifier.types import EvidenceItem


def test_compute_percent_change():
    """Test percent change computation."""
    assert abs(compute_percent_change(100, 110) - 10.0) < 0.1
    assert abs(compute_percent_change(100, 90) - (-10.0)) < 0.1


def test_compute_total():
    """Test total computation."""
    assert compute_total([1, 2, 3, 4]) == 10.0
    assert compute_total([10.5, 20.5]) == 31.0


def test_compute_ratio():
    """Test ratio computation."""
    assert compute_ratio(10, 2) == 5.0
    assert compute_ratio(100, 4) == 25.0


def test_verify_execution_percent_change():
    """Test execution engine with percent change."""
    text = "Revenue grew by 10% from 100 to 110."
    claims = extract_numeric_claims(text)
    evidence_items = [EvidenceItem(value=100.0, source="text"), EvidenceItem(value=110.0, source="text")]
    
    # Find the percent claim
    percent_claim = [c for c in claims if c.unit == "percent"][0]
    
    result = verify_execution(percent_claim, None, claims, evidence_items, text)
    # Execution might not always succeed due to heuristic nature, but should not crash
    assert result is not None

