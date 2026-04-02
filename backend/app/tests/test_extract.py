"""Tests for numeric claim extraction."""
import pytest
from app.verifier.extract import extract_numeric_claims


def test_extract_integers():
    """Test extraction of integers."""
    text = "The revenue was 5000000 dollars."
    claims = extract_numeric_claims(text)
    assert len(claims) == 1
    assert claims[0].parsed_value == 5000000.0


def test_extract_decimals():
    """Test extraction of decimals."""
    text = "The growth rate was 12.5%."
    claims = extract_numeric_claims(text)
    assert len(claims) == 1
    assert abs(claims[0].parsed_value - 0.125) < 0.001
    assert claims[0].unit == "percent"


def test_extract_comma_separated():
    """Test extraction of comma-separated numbers."""
    text = "Revenue was $1,234,567."
    claims = extract_numeric_claims(text)
    assert len(claims) == 1
    assert claims[0].parsed_value == 1234567.0


def test_extract_negative_parentheses():
    """Test extraction of negative numbers in parentheses."""
    text = "The loss was (500) dollars."
    claims = extract_numeric_claims(text)
    assert len(claims) == 1
    assert claims[0].parsed_value == -500.0


def test_extract_scale_tokens():
    """Test extraction with scale tokens."""
    text = "Revenue was 5M dollars and expenses were 2.5K."
    claims = extract_numeric_claims(text)
    assert len(claims) == 2
    assert claims[0].parsed_value == 5000000.0
    assert claims[0].scale_token in ['M', 'm', 'million', 'millions']
    assert claims[1].parsed_value == 2500.0
    assert claims[1].scale_token in ['K', 'k', 'thousand', 'thousands']


def test_extract_percentages():
    """Test extraction of percentages."""
    text = "The growth was 10% and decline was 5%."
    claims = extract_numeric_claims(text)
    assert len(claims) == 2
    assert abs(claims[0].parsed_value - 0.10) < 0.001
    assert claims[0].unit == "percent"
    assert abs(claims[1].parsed_value - 0.05) < 0.001


def test_extract_multiple_numbers():
    """Test extraction of multiple numbers."""
    text = "Q1: $1M, Q2: $1.5M, Q3: $2M"
    claims = extract_numeric_claims(text)
    assert len(claims) == 3
    assert claims[0].parsed_value == 1000000.0
    assert claims[1].parsed_value == 1500000.0
    assert claims[2].parsed_value == 2000000.0


def test_year_token_not_extracted_as_claim():
    """
    Regression test: year references in temporal context must not
    be extracted as numeric financial claims.
    Confirmed bug: 2023 was being extracted and scale-expanded.
    """
    answer = "Apple's net revenue in 2023 was $383.285 billion."
    claims = extract_numeric_claims(answer)
    numeric_values = [
        float(str(c.parsed_value).replace(',', ''))
        for c in claims
        if c.parsed_value is not None
    ]
    year_tokens = [v for v in numeric_values if 1900 <= v <= 2099]
    assert year_tokens == [], (
        f"Year token extracted as financial claim: {year_tokens}. "
        f"All extracted values: {numeric_values}"
    )
    non_year = [v for v in numeric_values if v > 100 and not 1900 <= v <= 2099]
    assert len(non_year) >= 1, (
        f"Expected at least one revenue value extracted, found none. "
        f"All values: {numeric_values}"
    )

