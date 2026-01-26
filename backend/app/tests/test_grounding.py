"""Tests for evidence grounding."""
from app.verifier.extract import extract_numeric_claims
from app.verifier.evidence import ingest_evidence
from app.verifier.grounding import ground_claims


def test_grounding_exact_match():
    """Test grounding with exact match."""
    text = "Revenue was $5,000,000."
    claims = extract_numeric_claims(text)
    
    evidence_data = {
        "type": "text",
        "content": "The company reported revenue of 5000000 dollars."
    }
    evidence_items = ingest_evidence(evidence_data)
    
    grounding = ground_claims(claims, evidence_items, tolerance=0.01)
    assert len(grounding) == 1
    assert grounding[0].distance < 0.01


def test_grounding_with_tolerance():
    """Test grounding with tolerance."""
    text = "Revenue was $5,000,000."
    claims = extract_numeric_claims(text)
    
    evidence_data = {
        "type": "text",
        "content": "The company reported revenue of 5000100 dollars."
    }
    evidence_items = ingest_evidence(evidence_data)
    
    grounding = ground_claims(claims, evidence_items, tolerance=0.01)
    assert len(grounding) == 1


def test_grounding_ambiguous():
    """Test grounding with ambiguous matches."""
    text = "The value was 100."
    claims = extract_numeric_claims(text)
    
    evidence_data = {
        "type": "text",
        "content": "First value: 100. Second value: 100. Third value: 100."
    }
    evidence_items = ingest_evidence(evidence_data)
    
    grounding = ground_claims(claims, evidence_items, tolerance=0.01)
    assert len(grounding) == 1
    assert grounding[0].ambiguous == True


def test_grounding_table():
    """Test grounding with table evidence."""
    text = "Revenue was $5,000,000."
    claims = extract_numeric_claims(text)
    
    evidence_data = {
        "type": "table",
        "content": {
            "columns": ["Quarter", "Revenue"],
            "rows": [
                ["Q1 2024", "5000000"],
                ["Q2 2024", "5500000"]
            ],
            "units": {
                "Revenue": "dollars"
            }
        }
    }
    evidence_items = ingest_evidence(evidence_data)
    
    grounding = ground_claims(claims, evidence_items, tolerance=0.01)
    assert len(grounding) >= 1

