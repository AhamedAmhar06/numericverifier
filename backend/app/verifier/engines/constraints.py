"""Constraint-based verification engine."""
from typing import List, Optional
from ..types import VerificationResult, NumericClaim, GroundingMatch


def verify_constraints(
    claim: NumericClaim,
    grounding_match: Optional[GroundingMatch],
    all_claims: List[NumericClaim],
    evidence_items: List
) -> VerificationResult:
    """
    Verify claim using constraint engine.
    
    Checks:
    - scale mismatch (millions vs absolute)
    - period mismatch (basic heuristic via text)
    """
    result = VerificationResult(
        claim=claim,
        grounded=grounding_match is not None,
        grounding_match=grounding_match
    )
    
    violations = []
    
    # Check scale mismatch
    if grounding_match:
        claim_scale = claim.scale_token
        claim_value = claim.parsed_value
        
        # Get evidence value
        evidence_value = grounding_match.evidence.value
        
        # Check if scales are mismatched
        # If claim has scale token but evidence doesn't match scale
        if claim_scale:
            # Determine expected scale from evidence value magnitude
            if abs(evidence_value) >= 1_000_000_000:
                expected_scale = "billion"
            elif abs(evidence_value) >= 1_000_000:
                expected_scale = "million"
            elif abs(evidence_value) >= 1_000:
                expected_scale = "thousand"
            else:
                expected_scale = None
            
            # Normalize scale tokens
            scale_map = {
                'K': 'thousand', 'k': 'thousand',
                'M': 'million', 'm': 'million',
                'B': 'billion', 'b': 'billion'
            }
            claim_scale_normalized = scale_map.get(claim_scale, claim_scale)
            
            if expected_scale and claim_scale_normalized != expected_scale:
                # Check if values are close when accounting for scale
                # e.g., 5M vs 5,000,000
                violations.append(f"Scale mismatch: claim uses {claim_scale}, evidence suggests {expected_scale}")
        else:
            # Claim has no scale token, but evidence might be in different scale
            # This is harder to detect, so we'll skip for now
            pass
    
    # Check period mismatch (basic heuristic)
    # Look for time-related keywords in claim vs evidence context
    time_keywords = ['2023', '2024', '2025', 'Q1', 'Q2', 'Q3', 'Q4', 'january', 'february', 'march',
                     'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december']
    
    if grounding_match and grounding_match.evidence.context:
        claim_text_lower = claim.raw_text.lower()
        evidence_context_lower = grounding_match.evidence.context.lower()
        
        claim_periods = [kw for kw in time_keywords if kw in claim_text_lower]
        evidence_periods = [kw for kw in time_keywords if kw in evidence_context_lower]
        
        if claim_periods and evidence_periods:
            if not any(cp in evidence_periods for cp in claim_periods):
                violations.append("Period mismatch: claim and evidence reference different time periods")
    
    result.constraint_violations = violations
    return result

