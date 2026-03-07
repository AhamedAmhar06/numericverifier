"""Tests for context-aware normalization (Phase 2)."""
import pytest
from decimal import Decimal
from backend.app.verifier.normalize import normalize_claims, normalize_bps, detect_table_scale
from backend.app.verifier.types import NumericClaim


def _claim(raw: str, value: float, unit=None, scale_token=None) -> NumericClaim:
    return NumericClaim(raw_text=raw, parsed_value=value, char_span=(0, len(raw)),
                        unit=unit, scale_token=scale_token)


# --- Scale label ---
def test_scale_label_K():
    c = _claim("5K", 5000.0, scale_token="k")
    normalize_claims([c])
    assert c.scale_label == "K"

def test_scale_label_M():
    c = _claim("2.5 million", 2_500_000.0, scale_token="million")
    normalize_claims([c])
    assert c.scale_label == "M"

def test_scale_label_B():
    c = _claim("1B", 1_000_000_000.0, scale_token="b")
    normalize_claims([c])
    assert c.scale_label == "B"

def test_scale_label_raw():
    c = _claim("500", 500.0)
    normalize_claims([c])
    assert c.scale_label == "raw"


# --- Percentage ---
def test_percent_unit_type():
    c = _claim("15%", 0.15, unit="percent")
    normalize_claims([c])
    assert c.unit_type == "percent"

def test_percent_decimal_value():
    c = _claim("15%", 0.15, unit="percent")
    normalize_claims([c])
    assert c.value_decimal == Decimal("0.15")


# --- BPS ---
def test_bps_normalization():
    result = normalize_bps("spread was 150 bps")
    assert result is not None
    assert abs(result.parsed_value - 0.015) < 1e-9
    assert result.unit_type == "bps"

def test_bps_basis_points_word():
    result = normalize_bps("rate increased by 25 basis points")
    assert result is not None
    assert abs(result.parsed_value - 0.0025) < 1e-9

def test_bps_no_match():
    result = normalize_bps("revenue was 500")
    assert result is None


# --- Currency detection ---
def test_currency_dollar_symbol():
    c = _claim("$500", 500.0)
    normalize_claims([c])
    assert c.currency == "USD"

def test_currency_word():
    c = _claim("500 dollars", 500.0)
    normalize_claims([c])
    assert c.currency == "USD"

def test_currency_none():
    c = _claim("500", 500.0)
    normalize_claims([c])
    assert c.currency is None


# --- Period detection ---
def test_period_year():
    c = _claim("revenue in 2023 was 500", 500.0)
    normalize_claims([c])
    assert c.period == "2023"

def test_period_quarter():
    c = _claim("Q2 2023 profit", 100.0)
    normalize_claims([c])
    assert c.period is not None
    assert "Q2" in c.period


# --- Approximate hedge ---
def test_approximate_widens_tolerance():
    c = _claim("approximately 500", 500.0)
    normalize_claims([c], default_tolerance=0.01)
    assert c.approximate is True
    assert c.tolerance_rel == 0.02

def test_tilde_approximate():
    c = _claim("~500", 500.0)
    normalize_claims([c], default_tolerance=0.01)
    assert c.approximate is True

def test_no_approximate():
    c = _claim("exactly 500", 500.0)
    normalize_claims([c], default_tolerance=0.01)
    assert c.approximate is False
    assert c.tolerance_rel == 0.01


# --- Table-level scale ---
def test_table_scale_millions():
    evidence = {"columns": ["Line Item", "2022 (in millions)", "2023 (in millions)"],
                "rows": [["Revenue", "5", "6"]], "units": {}}
    c = _claim("5", 5.0)
    normalize_claims([c], evidence_content=evidence)
    assert c.parsed_value == 5_000_000.0
    assert c.scale_label == "M"

def test_table_scale_none():
    evidence = {"columns": ["Line Item", "2022", "2023"],
                "rows": [["Revenue", "500", "600"]], "units": {}}
    c = _claim("500", 500.0)
    normalize_claims([c], evidence_content=evidence)
    assert c.parsed_value == 500.0
    assert c.scale_label == "raw"

def test_detect_table_scale_thousands():
    scale = detect_table_scale({"columns": ["Item", "Amount (000s)"], "rows": [], "units": {}})
    assert scale == "K"


# --- Decimal precision ---
def test_value_decimal_set():
    c = _claim("123.45", 123.45)
    normalize_claims([c])
    assert c.value_decimal is not None
    assert c.value_decimal == Decimal("123.45")


# --- Negative parentheses (preserves existing extraction) ---
def test_negative_preserved():
    c = _claim("(1234)", -1234.0)
    normalize_claims([c])
    assert c.parsed_value == -1234.0
    assert c.value_decimal == Decimal("-1234.0")


# ===================================================================
# normalize_cell_text tests — financial cell formatting
# ===================================================================
from backend.app.verifier.normalize import normalize_cell_text


def test_cell_dollar_comma():
    r = normalize_cell_text("$1,105.6")
    assert r["value"] is not None
    assert abs(r["value"] - 1105.6) < 1e-6
    assert r["is_percent"] is False


def test_cell_parentheses_negative():
    r = normalize_cell_text("(1,234)")
    assert r["value"] is not None
    assert abs(r["value"] - (-1234.0)) < 1e-6


def test_cell_percent():
    r = normalize_cell_text("39%")
    assert r["is_percent"] is True
    assert r["value"] is not None
    assert abs(r["value"] - 0.39) < 1e-6


def test_cell_dollar_million():
    r = normalize_cell_text("$166.3 million")
    assert r["value"] is not None
    assert abs(r["value"] - 166_300_000.0) < 1.0


def test_cell_dollar_bn():
    r = normalize_cell_text("$1.2bn")
    assert r["value"] is not None
    assert abs(r["value"] - 1_200_000_000.0) < 1.0


def test_cell_negative_dollar():
    r = normalize_cell_text("-$3.2")
    assert r["value"] is not None
    assert abs(r["value"] - (-3.2)) < 1e-6


def test_cell_whitespace_currency():
    r = normalize_cell_text("  $ 1,234  ")
    assert r["value"] is not None
    assert abs(r["value"] - 1234.0) < 1e-6


def test_cell_euro():
    r = normalize_cell_text("€4,521")
    assert r["value"] is not None
    assert abs(r["value"] - 4521.0) < 1e-6


def test_cell_parentheses_percent():
    r = normalize_cell_text("(58.6%)")
    assert r["is_percent"] is True
    assert r["value"] is not None
    assert abs(r["value"] - (-0.586)) < 1e-6


def test_cell_comma_only():
    r = normalize_cell_text("1,000,000")
    assert r["value"] is not None
    assert abs(r["value"] - 1_000_000.0) < 1e-6


def test_cell_plain_decimal():
    r = normalize_cell_text("27.0")
    assert r["value"] is not None
    assert abs(r["value"] - 27.0) < 1e-6


def test_cell_empty_string():
    r = normalize_cell_text("")
    assert r["value"] is None


def test_cell_non_numeric():
    r = normalize_cell_text("N/A")
    assert r["value"] is None


def test_cell_en_dash_negative():
    r = normalize_cell_text("\u2013500")
    assert r["value"] is not None
    assert abs(r["value"] - (-500.0)) < 1e-6


def test_cell_dollar_with_space_and_comma():
    r = normalize_cell_text("$ 45.1")
    assert r["value"] is not None
    assert abs(r["value"] - 45.1) < 1e-6
