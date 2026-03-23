"""Tests for context-aware grounding (Phase 4)."""
import pytest
from backend.app.verifier.grounding import ground_claim, ground_claims, _numeric_score
from backend.app.verifier.types import NumericClaim, EvidenceItem


def _claim(raw, value, unit=None, unit_type=None, period=None):
    return NumericClaim(raw_text=raw, parsed_value=value, char_span=(0, len(raw)),
                        unit=unit, unit_type=unit_type, period=period)


def _evidence(value, period=None, canonical=None, context=None):
    return EvidenceItem(value=value, source="table", location="row:0,col:1",
                        context=context or "", period=period,
                        canonical_line_item=canonical)


def test_exact_match():
    c = _claim("500", 500.0, unit_type="amount")
    ev = _evidence(500.0, period="2022", canonical="revenue")
    match = ground_claim(c, [ev], 0.01, question="What was revenue in 2022?")
    assert match is not None
    assert match.distance == 0.0
    assert match.confidence > 0.5


def test_no_match_outside_tolerance():
    c = _claim("999", 999.0, unit_type="amount")
    ev = _evidence(500.0)
    match = ground_claim(c, [ev], 0.01)
    assert match is None


def test_period_bonus():
    c = _claim("500 in 2022", 500.0, unit_type="amount", period="2022")
    ev_right = _evidence(500.0, period="2022", canonical="revenue")
    ev_wrong = _evidence(500.0, period="2023", canonical="revenue")
    match = ground_claim(c, [ev_right, ev_wrong], 0.01, question="revenue in 2022")
    assert match is not None
    assert match.evidence.period == "2022"


def test_line_item_bonus():
    c = _claim("500", 500.0, unit_type="amount")
    ev_rev = _evidence(500.0, period="2022", canonical="revenue")
    ev_cogs = _evidence(500.0, period="2022", canonical="cogs")
    match = ground_claim(c, [ev_rev, ev_cogs], 0.01, question="What was revenue?")
    assert match is not None
    assert match.evidence.canonical_line_item == "revenue"


def test_unit_type_hard_fail():
    c = _claim("15%", 0.15, unit="percent", unit_type="percent")
    ev = _evidence(150000.0, canonical="revenue")
    match = ground_claim(c, [ev], 0.01)
    assert match is None


def test_ambiguous_flag():
    c = _claim("500", 500.0, unit_type="amount")
    ev1 = _evidence(500.0, period="2022")
    ev2 = _evidence(500.0, period="2023")
    match = ground_claim(c, [ev1, ev2], 0.01)
    assert match is not None
    assert match.ambiguous is True


def test_confidence_margin():
    c = _claim("500", 500.0, unit_type="amount")
    ev1 = _evidence(500.0, period="2022", canonical="revenue")
    ev2 = _evidence(600.0, period="2022", canonical="revenue")
    match = ground_claim(c, [ev1, ev2], 0.5)
    assert match is not None
    assert match.confidence_margin >= 0.0


def test_ground_claims_multiple():
    claims = [
        _claim("500", 500.0, unit_type="amount"),
        _claim("200", 200.0, unit_type="amount"),
    ]
    evs = [_evidence(500.0, period="2022"), _evidence(200.0, period="2022")]
    matches = ground_claims(claims, evs, 0.01)
    assert len(matches) == 2


def test_numeric_score_exact():
    assert _numeric_score(100.0, 100.0, 0.01) == 1.0


def test_numeric_score_outside():
    assert _numeric_score(200.0, 100.0, 0.01) == 0.0


def test_ground_empty_evidence():
    c = _claim("500", 500.0, unit_type="amount")
    match = ground_claim(c, [], 0.01)
    assert match is None


# ===================================================================
# Domain gate tests — weak_pnl classification
# ===================================================================
from backend.app.verifier.domain import classify_table_type


def test_domain_strong_pnl():
    content = {
        "columns": ["", "2020", "2021"],
        "rows": [
            ["Revenue", "500", "600"],
            ["COGS", "200", "250"],
            ["Gross Profit", "300", "350"],
            ["Net Income", "100", "120"],
        ],
    }
    ctx = classify_table_type(content)
    assert ctx.table_type == "pnl"


def test_domain_weak_pnl_passes():
    """Table with some P&L terms but low confidence (many non-P&L rows) => weak_pnl."""
    content = {
        "columns": ["", "2020", "2021"],
        "rows": [
            ["Revenue", "500", "600"],
            ["EBITDA", "200", "250"],
            ["Cash and equivalents", "100", "120"],
            ["Total assets", "800", "900"],
            ["Depreciation", "50", "60"],
            ["Amortization", "30", "35"],
            ["Shareholders equity", "400", "450"],
            ["Accounts receivable", "150", "180"],
            ["Inventory", "100", "110"],
            ["Long term debt", "200", "220"],
            ["Working capital", "50", "60"],
            ["Goodwill", "100", "100"],
        ],
    }
    ctx = classify_table_type(content)
    assert ctx.table_type in ("pnl", "weak_pnl")
    assert len(ctx.matched_terms) >= 2


def test_domain_unknown_no_terms():
    content = {
        "columns": ["", "2020", "2021"],
        "rows": [
            ["Employee count", "500", "600"],
            ["Office space sqft", "10000", "12000"],
        ],
    }
    ctx = classify_table_type(content)
    assert ctx.table_type == "unknown"


# ===================================================================
# Percent-aware grounding tests (Phase 3)
# ===================================================================

def _evidence_pct(value, is_percent=False, period=None, canonical=None, context=None):
    """Evidence helper with is_percent support."""
    return EvidenceItem(
        value=value, source="table", location="row:0,col:1",
        context=context or "", period=period,
        canonical_line_item=canonical, is_percent=is_percent,
    )


def test_ground_dollar_formatted_vs_raw():
    """$1,105.6 in table (parsed to 1105.6) matches claim 1105.6."""
    c = _claim("1105.6", 1105.6, unit_type="amount")
    ev = _evidence_pct(1105.6, period="2019")
    match = ground_claim(c, [ev], 0.01)
    assert match is not None
    assert match.relative_error < 0.01


def test_ground_parentheses_negative():
    """(1,234) in table (parsed to -1234) matches claim -1234."""
    c = _claim("-1234", -1234.0, unit_type="amount")
    ev = _evidence_pct(-1234.0, period="2020")
    match = ground_claim(c, [ev], 0.01)
    assert match is not None


def test_ground_percent_both_normalized():
    """Both claim and evidence are percent-normalized (÷100): 0.586 vs 0.586."""
    c = _claim("58.6%", 0.586, unit="percent", unit_type="percent")
    ev = _evidence_pct(0.586, is_percent=True, period="2019")
    match = ground_claim(c, [ev], 0.01)
    assert match is not None
    assert match.relative_error < 0.01


def test_ground_percent_rescale():
    """Claim is 0.39 (39%), evidence is 39.0 (un-divided percent). Rescale fallback."""
    c = _claim("39%", 0.39, unit="percent", unit_type="percent")
    ev = _evidence_pct(39.0, is_percent=False, period="2020")
    match = ground_claim(c, [ev], 0.02)
    assert match is not None


def test_ground_percent_no_false_match():
    """Claim is 0.39 (39%), evidence is 390.0 (amount). Should NOT match."""
    c = _claim("39%", 0.39, unit="percent", unit_type="percent")
    ev = _evidence_pct(390.0, is_percent=False, period="2020")
    match = ground_claim(c, [ev], 0.01)
    assert match is None


def test_ground_amount_vs_percent_evidence():
    """Claim is amount 500, evidence is percent 0.05 → hard fail."""
    c = _claim("500", 500.0, unit_type="amount")
    ev = _evidence_pct(0.05, is_percent=True)
    match = ground_claim(c, [ev], 0.01)
    assert match is None


def test_ground_currency_stripped_match():
    """Evidence was '$45.1' (parsed to 45.1), claim is 45.1."""
    c = _claim("45.1", 45.1, unit_type="amount")
    ev = _evidence_pct(45.1, period="2019")
    match = ground_claim(c, [ev], 0.01)
    assert match is not None


def test_ground_percent_small_tolerance():
    """58.6% claim (0.586) vs 58.6% evidence (0.586), tight tolerance."""
    c = _claim("58.6%", 0.586, unit="percent", unit_type="percent")
    ev = _evidence_pct(0.586, is_percent=True)
    match = ground_claim(c, [ev], 0.001)
    assert match is not None
    assert match.relative_error < 0.001


def test_ground_negative_percent():
    """Negative percent: claim -0.012 (-1.2%), evidence -0.012."""
    c = _claim("(1.2%)", -0.012, unit="percent", unit_type="percent")
    ev = _evidence_pct(-0.012, is_percent=True)
    match = ground_claim(c, [ev], 0.01)
    assert match is not None


def test_ground_plain_number_unchanged():
    """Plain 27.0 → 27.0 — basic regression check."""
    c = _claim("27.0", 27.0, unit_type="amount")
    ev = _evidence_pct(27.0, period="2019")
    match = ground_claim(c, [ev], 0.01)
    assert match is not None
    assert match.relative_error < 0.001
