"""Lookup-based verification engine."""
from typing import Optional
from ..types import VerificationResult, GroundingMatch


def verify_lookup(verification_result: VerificationResult, grounding_match: Optional[GroundingMatch], tolerance: float) -> VerificationResult:
    """
    Verify claim using lookup engine.
    
    Supported if grounded match exists within tolerance.
    """
    if grounding_match is not None:
        # Check if the match is within tolerance
        if grounding_match.distance <= tolerance or grounding_match.relative_error <= tolerance:
            verification_result.lookup_supported = True
    
    return verification_result

