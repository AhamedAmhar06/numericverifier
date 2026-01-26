"""Rule-based decision logic."""
from typing import List
from .types import Decision, VerifierSignals, VerificationResult
from ..core.config import settings


def make_decision(signals: VerifierSignals, verification_results: List[VerificationResult], coverage_threshold: float = None) -> Decision:
    """
    Make decision based on signals using deterministic rules.
    
    ACCEPT if:
    - no unsupported claims
    - no scale/period mismatch
    - recomputation failures = 0
    - coverage_ratio >= threshold
    
    REPAIR if:
    - evidence coverage is good
    - arithmetic or scale issues exist
    - errors appear correctable
    
    FLAG if:
    - low coverage
    - ambiguity high
    - unsupported claims high
    """
    if coverage_threshold is None:
        coverage_threshold = settings.coverage_threshold
    
    # Check for ACCEPT conditions
    if (signals.unsupported_claims_count == 0 and
        signals.scale_mismatch_count == 0 and
        signals.period_mismatch_count == 0 and
        signals.recomputation_fail_count == 0 and
        signals.coverage_ratio >= coverage_threshold):
        return Decision(
            decision="ACCEPT",
            rationale="All claims are grounded and verified. No scale or period mismatches. All recomputations successful. Coverage meets threshold."
        )
    
    # Check for REPAIR conditions
    if (signals.coverage_ratio >= 0.6 and  # Good coverage
        (signals.scale_mismatch_count > 0 or
         signals.period_mismatch_count > 0 or
         signals.recomputation_fail_count > 0) and
        signals.unsupported_claims_count <= len(verification_results) * 0.3):  # Most claims supported
        issues = []
        if signals.scale_mismatch_count > 0:
            issues.append("scale mismatches")
        if signals.period_mismatch_count > 0:
            issues.append("period mismatches")
        if signals.recomputation_fail_count > 0:
            issues.append("recomputation failures")
        
        return Decision(
            decision="REPAIR",
            rationale=f"Good evidence coverage ({signals.coverage_ratio:.1%}), but issues detected: {', '.join(issues)}. Errors appear correctable."
        )
    
    # Default to FLAG
    issues = []
    if signals.coverage_ratio < coverage_threshold:
        issues.append(f"low coverage ({signals.coverage_ratio:.1%})")
    if signals.ambiguity_count > 0:
        issues.append(f"high ambiguity ({signals.ambiguity_count} ambiguous matches)")
    if signals.unsupported_claims_count > len(verification_results) * 0.3:
        issues.append(f"many unsupported claims ({signals.unsupported_claims_count})")
    
    return Decision(
        decision="FLAG",
        rationale=f"Issues detected: {', '.join(issues)}. Requires review."
    )

