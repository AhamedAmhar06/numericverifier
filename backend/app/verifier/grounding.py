"""Evidence grounding - matching claims to evidence."""
from typing import List, Optional
from .types import NumericClaim, EvidenceItem, GroundingMatch


def ground_claim(claim: NumericClaim, evidence_items: List[EvidenceItem], tolerance: float) -> Optional[GroundingMatch]:
    """
    Ground a single claim to evidence.
    
    Returns the best match if found within tolerance, or None.
    Marks as ambiguous if multiple matches found.
    """
    matches = []
    
    for evidence in evidence_items:
        # Calculate absolute difference
        distance = abs(claim.parsed_value - evidence.value)
        
        # Calculate relative error
        if evidence.value != 0:
            relative_error = abs((claim.parsed_value - evidence.value) / evidence.value)
        else:
            relative_error = float('inf') if claim.parsed_value != 0 else 0.0
        
        # Check if within tolerance (absolute or relative)
        if distance <= tolerance or relative_error <= tolerance:
            match = GroundingMatch(
                claim=claim,
                evidence=evidence,
                distance=distance,
                relative_error=relative_error,
                ambiguous=False
            )
            matches.append(match)
    
    if not matches:
        return None
    
    # If multiple matches, mark as ambiguous
    if len(matches) > 1:
        # Return the best match (lowest distance)
        best_match = min(matches, key=lambda m: m.distance)
        best_match.ambiguous = True
        return best_match
    
    return matches[0]


def ground_claims(claims: List[NumericClaim], evidence_items: List[EvidenceItem], tolerance: float) -> List[GroundingMatch]:
    """
    Ground all claims to evidence.
    
    Returns list of grounding matches (one per claim if found).
    """
    grounding = []
    
    for claim in claims:
        match = ground_claim(claim, evidence_items, tolerance)
        if match:
            grounding.append(match)
    
    return grounding

