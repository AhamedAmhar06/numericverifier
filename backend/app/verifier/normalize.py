"""Normalization layer for numeric claims."""
from typing import List
from .types import NumericClaim


def normalize_claims(claims: List[NumericClaim]) -> List[NumericClaim]:
    """
    Normalize numeric claims.
    
    - Remove commas (already done in extraction)
    - Convert brackets to negative (already done in extraction)
    - Expand K/M/B (already done in extraction)
    - Percent stored as both decimal and percentage form
    - Keep original surface form
    """
    # Most normalization is already done during extraction
    # This function can be used for additional normalization if needed
    normalized = []
    
    for claim in claims:
        # Ensure percent values are stored correctly
        # The extraction already handles this, but we can add additional normalization here
        normalized.append(claim)
    
    return normalized

