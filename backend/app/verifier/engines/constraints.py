"""Constraint-based verification engine. P&L mode: strict period and YoY."""
from typing import List, Optional, Set
from ..types import VerificationResult, NumericClaim, GroundingMatch

# Time-related keywords for period detection
_TIME_KEYWORDS = [
    '2020', '2021', '2022', '2023', '2024', '2025',
    'Q1', 'Q2', 'Q3', 'Q4',
    'january', 'february', 'march', 'april', 'may', 'june',
    'july', 'august', 'september', 'october', 'november', 'december',
]


def _periods_in_text(text: str) -> Set[str]:
    t = text.lower()
    return {kw for kw in _TIME_KEYWORDS if kw in t}


def verify_constraints(
    claim: NumericClaim,
    grounding_match: Optional[GroundingMatch],
    all_claims: List[NumericClaim],
    evidence_items: List,
    question: Optional[str] = None,
    pnl_periods: Optional[List[str]] = None,
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
    if grounding_match and grounding_match.evidence.context:
        claim_periods = _periods_in_text(claim.raw_text)
        evidence_context_lower = grounding_match.evidence.context.lower()
        evidence_periods = {kw for kw in _TIME_KEYWORDS if kw in evidence_context_lower}
        if claim_periods and evidence_periods:
            if not any(cp in evidence_periods for cp in claim_periods):
                violations.append("Period mismatch: claim and evidence reference different time periods")

    # P&L strict: question references period not in evidence
    if question and pnl_periods is not None:
        question_periods = _periods_in_text(question)
        for qp in question_periods:
            if qp not in pnl_periods:
                violations.append("missing_period_in_evidence")
                break
    # P&L strict: claim/grounding context uses different period than question
    if question and grounding_match and grounding_match.evidence.context and pnl_periods is not None:
        question_periods = _periods_in_text(question)
        evidence_context_lower = (grounding_match.evidence.context or "").lower()
        evidence_periods = {kw for kw in _TIME_KEYWORDS if kw in evidence_context_lower}
        if question_periods and evidence_periods:
            if not any(qp in evidence_periods for qp in question_periods):
                violations.append("pnl_period_strict_mismatch")

    result.constraint_violations = violations
    return result

