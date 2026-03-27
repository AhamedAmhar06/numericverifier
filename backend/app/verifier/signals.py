"""Verifier signals computation. Schema v2: P&L fields. Uses typed Violation codes."""
from typing import List, Optional, Any
from .types import (
    VerifierSignals, VerificationResult, NumericClaim, Violation,
    V_SCALE_MISMATCH, V_SCALE_LABEL_MISMATCH, V_PERIOD_MISMATCH,
    V_PNL_PERIOD_STRICT, V_MISSING_PERIOD_IN_EVIDENCE,
)


def is_temporal_claim(claim: NumericClaim) -> bool:
    try:
        if 1900 <= claim.parsed_value <= 2100 and claim.parsed_value == int(claim.parsed_value):
            return True
    except (TypeError, ValueError):
        pass
    raw_upper = (claim.raw_text or "").upper()
    if any(tok in raw_upper for tok in ("FY", "Q1", "Q2", "Q3", "Q4")):
        return True
    return False


def _violation_code(v) -> str:
    if isinstance(v, Violation):
        return v.code
    if isinstance(v, str):
        return v
    return ""


def compute_signals(
    claims: List[NumericClaim],
    verification_results: List[VerificationResult],
    tolerance: float,
    pnl_check_result: Optional[Any] = None,
    domain_table_type: Optional[str] = None,
    pnl_period_strict_mismatch_count: int = 0,
) -> VerifierSignals:
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
    unverifiable_count = 0
    recomputation_failures = 0
    relative_errors = []
    scale_mismatches = 0
    period_mismatches = 0
    ambiguity_count = 0
    pnl_strict_count = 0

    for i, result in enumerate(verification_results):
        claim = claims[i] if i < len(claims) else None
        is_temporal = claim is not None and is_temporal_claim(claim)
        supported = bool(result.grounded) or (result.execution_result is not None)
        if is_temporal:
            pass
        else:
            if supported:
                supported_value_count += 1
                if result.grounding_match and result.grounding_match.ambiguous:
                    ambiguity_count += 1
                if result.grounding_match:
                    relative_errors.append(result.grounding_match.relative_error)
            elif getattr(result, "unverifiable_claim", False):
                # Graceful scope limit: claim is a % formula outside the ratio library.
                # Do NOT count as unsupported — that would falsely penalise correct
                # answers to questions the verifier has no formula for.
                unverifiable_count += 1
            else:
                unsupported_value += 1

        if (not result.execution_supported) and (result.execution_error is not None):
            # Only count actual formula mismatches as recomputation failures,
            # not "no_matching_formula" or "period_not_found" which mean no formula was applicable
            err = result.execution_error or ""
            if err not in ("no_matching_formula", "period_not_found", "no_pnl_table",
                           "cannot_determine_baseline", "baseline_period_missing",
                           "revenue_missing_for_margin"):
                recomputation_failures += 1

        for v in (result.constraint_violations or []):
            code = _violation_code(v)
            if code in (V_SCALE_MISMATCH, V_SCALE_LABEL_MISMATCH):
                scale_mismatches += 1
            elif code == V_PERIOD_MISMATCH:
                period_mismatches += 1
            elif code in (V_PNL_PERIOD_STRICT, V_MISSING_PERIOD_IN_EVIDENCE):
                pnl_strict_count += 1
            else:
                # Legacy string fallback
                vl = code.lower() if isinstance(code, str) else ""
                if "scale mismatch" in vl:
                    scale_mismatches += 1
                elif "period mismatch" in vl and "strict" not in vl:
                    period_mismatches += 1
                elif "pnl_period_strict" in vl or "missing_period" in vl:
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

    # Schema v3 + v4 signals
    signals.claim_count = len(claims)
    signals.unverifiable_claim_count = unverifiable_count

    # near_tolerance_flag: fires when any grounded claim's relative error is in (tolerance, 0.10)
    # Meaning: grounded but error is real and financially material
    for result in verification_results:
        if result.grounding_match is not None:
            re = result.grounding_match.relative_error
            if re > tolerance and re < 0.10:
                signals.near_tolerance_flag = 1
                break

    # grounding_confidence_score: average composite grounding confidence across grounded claims
    confidence_scores = [
        result.grounding_match.confidence
        for result in verification_results
        if result.grounding_match is not None
    ]
    if confidence_scores:
        signals.grounding_confidence_score = round(
            sum(confidence_scores) / len(confidence_scores), 4
        )

    if domain_table_type == "pnl":
        signals.pnl_table_detected = 1
        signals.pnl_period_strict_mismatch_count = pnl_period_strict_mismatch_count + pnl_strict_count
        if pnl_check_result:
            signals.pnl_identity_fail_count = getattr(pnl_check_result, "identity_fail_count", 0)
            signals.pnl_margin_fail_count = getattr(pnl_check_result, "margin_fail_count", 0)
            signals.pnl_missing_baseline_count = 1 if getattr(pnl_check_result, "missing_yoy_baseline", False) else 0

    return signals
