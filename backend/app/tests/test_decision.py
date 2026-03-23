"""Tests for decision rules."""
from typing import List
from app.verifier.types import VerifierSignals, VerificationResult, NumericClaim
from app.verifier.decision_rules import make_decision


def test_decision_accept():
    """Test ACCEPT decision (P&L mode: pnl_table_detected=1, no P&L violations)."""
    signals = VerifierSignals(
        unsupported_claims_count=0,
        coverage_ratio=1.0,
        recomputation_fail_count=0,
        scale_mismatch_count=0,
        period_mismatch_count=0,
        pnl_table_detected=1,
        pnl_identity_fail_count=0,
        pnl_margin_fail_count=0,
        pnl_missing_baseline_count=0,
        pnl_period_strict_mismatch_count=0,
    )
    decision = make_decision(signals, [])
    assert decision.decision == "ACCEPT"


def test_decision_repair():
    """Test REPAIR decision (P&L mode: identity/margin failures, good coverage)."""
    signals = VerifierSignals(
        unsupported_claims_count=0,
        coverage_ratio=0.8,
        recomputation_fail_count=0,
        scale_mismatch_count=0,
        period_mismatch_count=0,
        pnl_table_detected=1,
        pnl_identity_fail_count=1,
        pnl_margin_fail_count=0,
        pnl_missing_baseline_count=0,
        pnl_period_strict_mismatch_count=0,
    )
    results = [
        VerificationResult(
            claim=NumericClaim("test1", 100.0, (0, 5)),
            grounded=True
        ),
        VerificationResult(
            claim=NumericClaim("test2", 200.0, (6, 11)),
            grounded=True
        ),
        VerificationResult(
            claim=NumericClaim("test3", 300.0, (12, 17)),
            grounded=True
        ),
        VerificationResult(
            claim=NumericClaim("test4", 400.0, (18, 23)),
            grounded=True
        )
    ]
    
    decision = make_decision(signals, results)
    assert decision.decision == "REPAIR"


def test_decision_flag():
    """Test FLAG decision (low coverage / non-P&L)."""
    signals = VerifierSignals(
        unsupported_claims_count=5,
        coverage_ratio=0.3,
        recomputation_fail_count=0,
        scale_mismatch_count=0,
        period_mismatch_count=0,
        ambiguity_count=3,
        pnl_table_detected=0,
    )
    decision = make_decision(signals, [])
    assert decision.decision == "FLAG"

