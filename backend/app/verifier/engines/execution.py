"""Execution-based verification engine."""
from typing import List, Optional
from ..types import VerificationResult, NumericClaim, GroundingMatch, EvidenceItem


def compute_percent_change(old_value: float, new_value: float) -> float:
    """Compute percent change: ((new - old) / old) * 100"""
    if old_value == 0:
        return float('inf')
    return ((new_value - old_value) / old_value) * 100


def compute_total(values: List[float]) -> float:
    """Compute total of values."""
    return sum(values)


def compute_ratio(numerator: float, denominator: float) -> float:
    """Compute ratio: numerator / denominator"""
    if denominator == 0:
        return float('inf')
    return numerator / denominator


def verify_execution(
    claim: NumericClaim,
    grounding_match: Optional[GroundingMatch],
    all_claims: List[NumericClaim],
    evidence_items: List[EvidenceItem],
    answer_text: str
) -> VerificationResult:
    """
    Verify claim using execution engine.
    
    Attempts to recompute:
    - percent change
    - totals
    - ratios
    
    If operands missing, marks as unverifiable.
    """
    result = VerificationResult(
        claim=claim,
        grounded=grounding_match is not None,
        grounding_match=grounding_match
    )
    
    # Try to identify what kind of computation this might be
    claim_text = claim.raw_text.lower()
    claim_value = claim.parsed_value
    tol = 0.01
    computation_intent = False
    
    # Check for percent change indicators
    if claim.unit == "percent" or any(keyword in claim_text for keyword in ['change', 'increase', 'decrease', 'growth', 'decline', '%']):
        computation_intent = True

        # Interpret percent claim: we store percent as decimal (0.10), but comparisons are in percent points.
        claim_percent = claim_value * 100.0 if claim.unit == "percent" else claim_value

        # Candidate operands: numbers from answer (other claims) + evidence items.
        other_values = [c.parsed_value for c in all_claims if c != claim]
        candidate_values = other_values + [e.value for e in evidence_items]

        # Need at least two operands to compute a percent change.
        if len(candidate_values) >= 2:
            best_diff = None
            best_computed = None
            for i in range(len(candidate_values)):
                for j in range(len(candidate_values)):
                    if i == j:
                        continue
                    old_val = candidate_values[i]
                    new_val = candidate_values[j]
                    computed = compute_percent_change(old_val, new_val)  # percent points
                    diff = abs(computed - claim_percent)
                    if best_diff is None or diff < best_diff:
                        best_diff = diff
                        best_computed = computed

            if best_computed is not None:
                result.execution_result = best_computed
                # Support if within tolerance (allow rounding); tol is in percent points here.
                if best_diff is not None and best_diff <= max(0.1, tol * 100.0):
                    result.execution_supported = True
                else:
                    result.execution_supported = False
                    result.execution_error = f"Percent change mismatch: claimed {claim_percent:.4g}%, recomputed {best_computed:.4g}%"
                return result
    
    # Check for total/sum indicators
    if any(keyword in claim_text for keyword in ['total', 'sum', 'combined', 'together']):
        computation_intent = True
        # Try to find other values that sum to this
        other_values = [c.parsed_value for c in all_claims if c != claim]
        
        if len(other_values) >= 1:
            # Try subsets of other values
            for i in range(len(other_values)):
                for j in range(i + 1, len(other_values) + 1):
                    subset = other_values[i:j]
                    total = compute_total(subset)
                    if abs(total - claim_value) < 0.01:
                        result.execution_supported = True
                        result.execution_result = total
                        return result
            # If we got here, we tried but couldn't recompute.
            result.execution_error = "Total recomputation failed"
            return result
    
    # Check for ratio indicators
    if any(keyword in claim_text for keyword in ['ratio', 'per', 'divided', '/']):
        computation_intent = True
        other_values = [c.parsed_value for c in all_claims if c != claim]
        
        if len(other_values) >= 1:
            for other_val in other_values:
                # Try both directions
                ratio1 = compute_ratio(claim_value, other_val)
                ratio2 = compute_ratio(other_val, claim_value)
                
                # Check if either ratio matches a value in evidence
                for ev in evidence_items:
                    if abs(ratio1 - ev.value) < 0.01 or abs(ratio2 - ev.value) < 0.01:
                        result.execution_supported = True
                        result.execution_result = ratio1 if abs(ratio1 - ev.value) < 0.01 else ratio2
                        return result
        result.execution_error = "Ratio recomputation failed"
        return result
    
    # If we couldn't (or shouldn't) verify via execution, do NOT count it as a failure.
    # Only set execution_error when we had clear computation intent but couldn't verify.
    if computation_intent and result.execution_error is None:
        result.execution_error = "Operands missing or computation not identifiable"
    return result

