"""Verifier signals computation. Schema v2: P&L fields."""
from typing import List, Optional, Any
from .types import VerifierSignals, VerificationResult, NumericClaim


def is_temporal_claim(claim: NumericClaim) -> bool:
    """
    True if the claim is a temporal reference (year, quarter) and must not count toward coverage.
    Conservative heuristics: 1900-2100, or raw_text contains FY, Q1-Q4.
    """
    try:
        if 1900 <= claim.parsed_value <= 2100 and claim.parsed_value == int(claim.parsed_value):
            return True
    except (TypeError, ValueError):
        pass
    raw_upper = (claim.raw_text or "").upper()
    if "FY" in raw_upper or "Q1" in raw_upper or "Q2" in raw_upper or "Q3" in raw_upper or "Q4" in raw_upper:
        return True
    return False


def compute_signals(
    claims: List[NumericClaim],
    verification_results: List[VerificationResult],
    tolerance: float,
    pnl_check_result: Optional[Any] = None,
    domain_table_type: Optional[str] = None,
    pnl_period_strict_mismatch_count: int = 0,
) -> VerifierSignals:
    """
    Compute risk signals. Schema v2: when P&L, set pnl_table_detected and pnl_* counts.
    """
    signals = VerifierSignals()
    if not claims:
        if domain_table_type == "pnl":
            signals.pnl_table_detected = 1
            if pnl_check_result:
                signals.pnl_identity_fail_count = getattr(pnl_check_result, "identity_fail_count", 0)
                signals.pnl_margin_fail_count = getattr(pnl_check_result, "margin_fail_count", 0)
                signals.pnl_missing_baseline_count = 1 if getattr(pnl_check_result, "missing_yoy_baseline", False) else 0
            signals.pnl_period_strict_mismatch_count = pnl_period_strict_mismatch_count
        return signals
    
    unsupported_value = 0
    supported_value_count = 0
    recomputation_failures = 0
    relative_errors = []
    scale_mismatches = 0
    period_mismatches = 0
    ambiguity_count = 0
    pnl_strict_count = 0

    for i, result in enumerate(verification_results):
        claim = claims[i] if i < len(claims) else None
        is_temporal = claim is not None and is_temporal_claim(claim)

        # Supported if grounded OR we could recompute something meaningful (even if mismatch)
        supported = bool(result.grounded) or (result.execution_result is not None)
        if is_temporal:
            # Temporal claims stay in claims/verification but do not affect coverage or unsupported count
            pass
        else:
            if supported:
                supported_value_count += 1
                if result.grounding_match and result.grounding_match.ambiguous:
                    ambiguity_count += 1
                if result.grounding_match:
                    relative_errors.append(result.grounding_match.relative_error)
            else:
                unsupported_value += 1

        # Check execution support (all claims)
        if (not result.execution_supported) and (result.execution_error is not None):
            recomputation_failures += 1

        # Check constraint violations
        if result.constraint_violations:
            for violation in result.constraint_violations:
                v = violation.lower()
                if "scale mismatch" in v:
                    scale_mismatches += 1
                if "period mismatch" in v and "strict" not in v:
                    period_mismatches += 1
                if "pnl_period_strict_mismatch" in v or "missing_period_in_evidence" in v:
                    pnl_strict_count += 1

    value_claim_count = supported_value_count + unsupported_value
    signals.coverage_ratio = (supported_value_count / value_claim_count) if value_claim_count else 0.0
    signals.unsupported_claims_count = unsupported_value
    signals.recomputation_fail_count = recomputation_failures
    signals.scale_mismatch_count = scale_mismatches
    signals.period_mismatch_count = period_mismatches
    signals.ambiguity_count = ambiguity_count
    if relative_errors:
        signals.max_relative_error = max(relative_errors)
        signals.mean_relative_error = sum(relative_errors) / len(relative_errors)

    if domain_table_type == "pnl":
        signals.pnl_table_detected = 1
        signals.pnl_period_strict_mismatch_count = pnl_period_strict_mismatch_count + pnl_strict_count
        if pnl_check_result:
            signals.pnl_identity_fail_count = getattr(pnl_check_result, "identity_fail_count", 0)
            signals.pnl_margin_fail_count = getattr(pnl_check_result, "margin_fail_count", 0)
            signals.pnl_missing_baseline_count = 1 if getattr(pnl_check_result, "missing_yoy_baseline", False) else 0

    return signals

