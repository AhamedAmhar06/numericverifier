"""Tests for signals computation with typed Violation codes (Phase 7)."""
import pytest
from backend.app.verifier.signals import compute_signals, is_temporal_claim
from backend.app.verifier.types import (
    NumericClaim, VerificationResult, GroundingMatch, EvidenceItem,
    VerifierSignals, Violation,
    V_SCALE_MISMATCH, V_PERIOD_MISMATCH, V_PNL_PERIOD_STRICT,
    V_MISSING_PERIOD_IN_EVIDENCE,
)


def _claim(raw, value):
    return NumericClaim(raw_text=raw, parsed_value=value, char_span=(0, len(raw)))


def _evidence(value):
    return EvidenceItem(value=value, source="table")


def _grounding(claim, ev, rel_err=0.0):
    return GroundingMatch(claim=claim, evidence=ev, distance=abs(claim.parsed_value - ev.value),
                          relative_error=rel_err)


def _vr(claim, grounded=True, match=None, violations=None):
    return VerificationResult(claim=claim, grounded=grounded, grounding_match=match,
                              constraint_violations=violations or [])


def test_coverage_ratio_full():
    c = _claim("500", 500)
    ev = _evidence(500)
    gm = _grounding(c, ev)
    vr = _vr(c, grounded=True, match=gm)
    signals = compute_signals([c], [vr], 0.01, domain_table_type="pnl")
    assert signals.coverage_ratio == 1.0


def test_coverage_ratio_none():
    c = _claim("500", 500)
    vr = _vr(c, grounded=False)
    signals = compute_signals([c], [vr], 0.01, domain_table_type="pnl")
    assert signals.coverage_ratio == 0.0
    assert signals.unsupported_claims_count == 1


def test_scale_mismatch_counted():
    c = _claim("5M", 5000000)
    ev = _evidence(5000000)
    gm = _grounding(c, ev)
    violation = Violation(code=V_SCALE_MISMATCH, message="scale mismatch test")
    vr = _vr(c, grounded=True, match=gm, violations=[violation])
    signals = compute_signals([c], [vr], 0.01, domain_table_type="pnl")
    assert signals.scale_mismatch_count == 1


def test_period_mismatch_counted():
    c = _claim("500", 500)
    ev = _evidence(500)
    gm = _grounding(c, ev)
    violation = Violation(code=V_PERIOD_MISMATCH, message="period mismatch test")
    vr = _vr(c, grounded=True, match=gm, violations=[violation])
    signals = compute_signals([c], [vr], 0.01, domain_table_type="pnl")
    assert signals.period_mismatch_count == 1


def test_pnl_strict_counted():
    c = _claim("500", 500)
    ev = _evidence(500)
    gm = _grounding(c, ev)
    violation = Violation(code=V_PNL_PERIOD_STRICT, message="strict period")
    vr = _vr(c, grounded=True, match=gm, violations=[violation])
    signals = compute_signals([c], [vr], 0.01, domain_table_type="pnl")
    assert signals.pnl_period_strict_mismatch_count >= 1


def test_missing_period_counted():
    c = _claim("500", 500)
    ev = _evidence(500)
    gm = _grounding(c, ev)
    violation = Violation(code=V_MISSING_PERIOD_IN_EVIDENCE, message="missing period")
    vr = _vr(c, grounded=True, match=gm, violations=[violation])
    signals = compute_signals([c], [vr], 0.01, domain_table_type="pnl")
    assert signals.pnl_period_strict_mismatch_count >= 1


def test_temporal_claim_excluded():
    c = _claim("2023", 2023)
    vr = _vr(c, grounded=False)
    signals = compute_signals([c], [vr], 0.01, domain_table_type="pnl")
    assert signals.unsupported_claims_count == 0


def test_is_temporal_year():
    assert is_temporal_claim(_claim("2023", 2023)) is True


def test_is_temporal_false():
    assert is_temporal_claim(_claim("500", 500)) is False


def test_pnl_table_detected_set():
    c = _claim("500", 500)
    ev = _evidence(500)
    gm = _grounding(c, ev)
    vr = _vr(c, grounded=True, match=gm)
    signals = compute_signals([c], [vr], 0.01, domain_table_type="pnl")
    assert signals.pnl_table_detected == 1


def test_legacy_string_violation_fallback():
    c = _claim("500", 500)
    ev = _evidence(500)
    gm = _grounding(c, ev)
    vr = _vr(c, grounded=True, match=gm, violations=["Scale mismatch: old style"])
    signals = compute_signals([c], [vr], 0.01, domain_table_type="pnl")
    assert signals.scale_mismatch_count == 1
