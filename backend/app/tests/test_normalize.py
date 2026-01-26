"""Tests for normalization."""
from app.verifier.extract import extract_numeric_claims
from app.verifier.normalize import normalize_claims


def test_normalize_preserves_claims():
    """Test that normalization preserves claims."""
    text = "Revenue was $1,234,567 and 10% growth."
    claims = extract_numeric_claims(text)
    normalized = normalize_claims(claims)
    assert len(normalized) == len(claims)
    assert normalized[0].parsed_value == claims[0].parsed_value

