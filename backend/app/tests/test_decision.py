"""Tests for decision rules."""
from typing import List
from app.verifier.types import VerifierSignals, VerificationResult, NumericClaim
from app.verifier.decision_rules import make_decision


def test_decision_accept():
    """Test ACCEPT decision."""
    signals = VerifierSignals(
        unsupported_claims_count=0,
        coverage_ratio=1.0,
        recomputation_fail_count=0,
        scale_mismatch_count=0,
        period_mismatch_count=0
    )
    
    decision = make_decision(signals, [])
    assert decision.decision == "ACCEPT"


def test_decision_repair():
    """Test REPAIR decision."""
    signals = VerifierSignals(
        unsupported_claims_count=1,
        coverage_ratio=0.8,
        recomputation_fail_count=1,
        scale_mismatch_count=1,
        period_mismatch_count=0
    )
    
    # Create multiple results so unsupported_claims_count is <= 30% of total
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
    """Test FLAG decision."""
    signals = VerifierSignals(
        unsupported_claims_count=5,
        coverage_ratio=0.3,
        recomputation_fail_count=0,
        scale_mismatch_count=0,
        period_mismatch_count=0,
        ambiguity_count=3
    )
    
    decision = make_decision(signals, [])
    assert decision.decision == "FLAG"

