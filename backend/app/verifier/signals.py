"""Verifier signals computation."""
from typing import List
from .types import VerifierSignals, VerificationResult, NumericClaim


def compute_signals(
    claims: List[NumericClaim],
    verification_results: List[VerificationResult],
    tolerance: float
) -> VerifierSignals:
    """
    Compute risk signals from verification results.
    
    Signals describe risk, not decisions.
    """
    signals = VerifierSignals()
    
    if not claims:
        return signals
    
    # Count unsupported claims (neither grounded nor execution-verifiable)
    unsupported = 0
    supported_count = 0
    recomputation_failures = 0
    relative_errors = []
    scale_mismatches = 0
    period_mismatches = 0
    ambiguity_count = 0
    
    for result in verification_results:
        # Supported if grounded OR we could recompute something meaningful (even if mismatch)
        # (Mismatch is handled via recomputation_fail_count, but it's still "covered" by evidence.)
        supported = bool(result.grounded) or (result.execution_result is not None)
        if supported:
            supported_count += 1
            
            # Check for ambiguity
            if result.grounding_match and result.grounding_match.ambiguous:
                ambiguity_count += 1
            
            # Collect relative errors
            if result.grounding_match:
                relative_errors.append(result.grounding_match.relative_error)
        else:
            unsupported += 1
        
        # Check execution support
        if (not result.execution_supported) and (result.execution_error is not None):
            recomputation_failures += 1
        
        # Check constraint violations
        if result.constraint_violations:
            for violation in result.constraint_violations:
                if "scale mismatch" in violation.lower():
                    scale_mismatches += 1
                if "period mismatch" in violation.lower():
                    period_mismatches += 1
    
    # Compute coverage ratio (how many claims are supported by evidence/verification)
    signals.coverage_ratio = supported_count / len(claims) if claims else 0.0
    
    # Set counts
    signals.unsupported_claims_count = unsupported
    signals.recomputation_fail_count = recomputation_failures
    signals.scale_mismatch_count = scale_mismatches
    signals.period_mismatch_count = period_mismatches
    signals.ambiguity_count = ambiguity_count
    
    # Compute error statistics
    if relative_errors:
        signals.max_relative_error = max(relative_errors)
        signals.mean_relative_error = sum(relative_errors) / len(relative_errors)
    
    return signals

