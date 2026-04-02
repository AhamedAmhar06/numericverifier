"""Numeric claim extraction from text."""
import re
from typing import List
from .types import NumericClaim


# Scale multipliers
SCALE_MULTIPLIERS = {
    'K': 1_000,
    'k': 1_000,
    'thousand': 1_000,
    'thousands': 1_000,
    'M': 1_000_000,
    'm': 1_000_000,
    'million': 1_000_000,
    'millions': 1_000_000,
    'B': 1_000_000_000,
    'b': 1_000_000_000,
    'billion': 1_000_000_000,
    'billions': 1_000_000_000,
}


def extract_numeric_claims(text: str) -> List[NumericClaim]:
    """
    Extract numeric claims from text.
    
    Supports:
    - integers, decimals
    - comma-separated numbers
    - negative numbers (including parentheses notation)
    - percentages
    - currency tokens
    - scale tokens (K, M, B, thousand, million, billion)
    """
    claims = []
    
    # Pattern for base number (with optional commas and decimals)
    # Matches: 123, 1234, 1,234, 123.45, 1,234.56, 5000000
    # Use word boundaries to avoid partial matches
    base_number = r'\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+\.\d+|\d{4,}'
    
    # Build comprehensive pattern that captures:
    # 1. Percentages: 10%, 12.5%
    # 2. Scale tokens: 5M, 2.5K, 3 million
    # 3. Currency: $5,000, 5000 dollars
    # 4. Parentheses (negative): (500)
    # 5. Plain numbers: 5000, -5000
    
    patterns = [
        # Percentages (highest priority to avoid conflicts)
        (rf'\b({base_number})\s*%', 'percent', None),
        # Scale tokens with word boundaries
        (rf'\b({base_number})\s+({r"|".join(SCALE_MULTIPLIERS.keys())})\b', 'scale', None),
        (rf'\b({base_number})\s*([KMBkmb])\b', 'scale', None),
        # Currency before
        (rf'\$\s*({base_number})\b', 'currency', None),
        # Currency after
        (rf'\b({base_number})\s+(?:dollars?|USD|EUR|GBP)\b', 'currency', None),
        # Parentheses (negative)
        (rf'\(({base_number})\)', 'negative', None),
        # Negative sign
        (rf'-({base_number})\b', 'negative', None),
        # Plain numbers (lowest priority, with word boundaries)
        (rf'\b({base_number})\b', 'plain', None),
    ]
    
    all_matches = []
    
    # Find all matches
    for pattern, match_type, _ in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            start, end = match.span()
            # Check for overlap with existing matches
            overlap = False
            for existing_match in all_matches:
                existing_start, existing_end = existing_match[0], existing_match[1]
                if not (end <= existing_start or start >= existing_end):
                    overlap = True
                    break
            if not overlap:
                all_matches.append((start, end, match, match_type))
    
    # Sort by position
    all_matches.sort(key=lambda x: x[0])
    
    # Process each match
    for start, end, match, match_type in all_matches:
        matched_text = match.group(0)
        raw_text = matched_text
        
        # Extract the numeric part (first capture group)
        number_str = match.group(1)
        
        # Remove commas
        number_str = number_str.replace(',', '')
        
        # Determine if negative
        is_negative = match_type == 'negative' or number_str.startswith('-')
        if is_negative and not number_str.startswith('-'):
            # For parentheses, the number is already extracted without parentheses
            pass
        
        # Parse base value
        try:
            base_value = float(number_str)
            if is_negative:
                base_value = -base_value
        except ValueError:
            continue
        
        # Detect unit and scale
        unit = None
        scale_token = None
        parsed_value = base_value
        
        # Handle percentage
        if match_type == 'percent':
            unit = "percent"
            parsed_value = base_value / 100.0
        
        # Handle scale tokens
        if match_type == 'scale' and len(match.groups()) >= 2:
            scale_part = match.group(2).lower()
            if scale_part in SCALE_MULTIPLIERS:
                scale_token = scale_part
                parsed_value = base_value * SCALE_MULTIPLIERS[scale_part]
        
        # Handle currency
        if match_type == 'currency':
            if unit is None:
                unit = "dollar"
        
        # For plain numbers, check if there's currency nearby
        if match_type == 'plain':
            # Look for $ before or currency words after (within 10 chars)
            before_text = text[max(0, start - 10):start].lower()
            after_text = text[end:min(len(text), end + 20)].lower()
            if '$' in before_text or any(c in after_text for c in ['dollar', 'usd', 'eur', 'gbp']):
                unit = "dollar"
        
        claim = NumericClaim(
            raw_text=raw_text,
            parsed_value=parsed_value,
            char_span=(start, end),
            unit=unit,
            scale_token=scale_token
        )
        claims.append(claim)

    # Year-token filter: 4-digit integers 1900-2099 in temporal context
    # (e.g., "revenue in 2023") are period labels, not financial values.
    # Confirmed bug: without this filter, year tokens pass through the
    # scale normalizer and produce grounding failures on valid answers.
    # Fix applied after reproduction confirmed in current worktree.
    _TEMPORAL_PRECEDING = {"in", "for", "fiscal", "fy", "year", "during", "of", "since"}
    _CURRENCY_SYMS = {"$", "£", "€", "usd", "gbp", "eur"}
    _SCALE_WORDS = {
        "million", "millions", "billion", "billions", "thousand", "thousands",
        "trillion", "trillions", "m", "b", "k", "mn", "bn",
    }
    filtered = []
    for cl in claims:
        pv = cl.parsed_value
        keep = True
        if pv is not None:
            try:
                fv = float(pv)
                if 1900.0 <= fv <= 2099.0 and fv == int(fv):
                    s, e = cl.char_span
                    before_words = text[:s].split()
                    prec = before_words[-1].lower().strip(".,;:") if before_words else ""
                    char_before = text[max(0, s - 5):s].strip().lower()
                    has_currency = any(sym in char_before for sym in _CURRENCY_SYMS)
                    after_str = text[e:min(len(text), e + 25)].strip().lower()
                    after_first = after_str.split()[0].strip(".,;:") if after_str else ""
                    has_scale_after = after_first in _SCALE_WORDS
                    if prec in _TEMPORAL_PRECEDING or (not has_currency and not has_scale_after):
                        keep = False
            except (TypeError, ValueError):
                pass
        if keep:
            filtered.append(cl)
    claims = filtered

    return claims
