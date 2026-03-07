"""Context-aware normalization for numeric claims.

Converts raw NumericClaim objects into enriched claims with:
- Decimal-precision canonical value
- Typed unit (amount / percent / ratio / bps / count)
- Scale label (raw / K / M / B)
- Currency metadata
- Period extraction from surrounding text
- Approximate-hedge tolerance widening
- Table-level scale detection from evidence headers
"""
import re
from decimal import Decimal, InvalidOperation
from typing import List, Optional, Dict, Any
from .types import NumericClaim

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_APPROX_PATTERNS = re.compile(
    r"\b(approx(?:imately)?|about|around|roughly|circa|nearly|estimated)\b|~",
    re.IGNORECASE,
)

_PERIOD_PATTERN = re.compile(
    r"\b((?:FY\s*)?20\d{2}|Q[1-4]\s*(?:20\d{2})?|H[12]\s*(?:20\d{2})?)\b",
    re.IGNORECASE,
)

_CURRENCY_SYMBOLS = {"$": "USD", "£": "GBP", "€": "EUR", "¥": "JPY", "₹": "INR"}
_CURRENCY_WORDS = re.compile(
    r"\b(USD|EUR|GBP|JPY|INR|LKR|Rs\.?|dollars?|rupees?)\b", re.IGNORECASE
)

_TABLE_SCALE_PATTERN = re.compile(
    r"\b(?:in\s+)?(thousands?|millions?|billions?|USD\s*(?:thousands?|millions?|billions?)|000s)\b",
    re.IGNORECASE,
)

_SCALE_WORD_TO_LABEL = {
    "thousand": "K", "thousands": "K", "000s": "K",
    "million": "M", "millions": "M",
    "billion": "B", "billions": "B",
}

_BPS_PATTERN = re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:bps|basis\s+points?)\b", re.IGNORECASE)

# Cell-level normalization patterns
_CELL_CURRENCY_SYMBOLS = re.compile(r"[$€£¥₹]")
_CELL_CURRENCY_WORDS = re.compile(
    r"\b(USD|EUR|GBP|JPY|INR|LKR)\b", re.IGNORECASE
)
_CELL_SCALE_PATTERN = re.compile(
    r"\b(thousands?|millions?|billions?)\b|(bn)\b", re.IGNORECASE
)
_CELL_SCALE_SUFFIX = re.compile(r"(bn|[KkMmBb])$")
_CELL_SCALE_MAP = {
    "k": 1_000, "thousand": 1_000, "thousands": 1_000,
    "m": 1_000_000, "million": 1_000_000, "millions": 1_000_000,
    "b": 1_000_000_000, "billion": 1_000_000_000, "billions": 1_000_000_000,
    "bn": 1_000_000_000,
}


def normalize_cell_text(text: str) -> Dict[str, Any]:
    """Parse a financial-formatted cell string into a normalized numeric result.

    Returns {"value": float|None, "is_percent": bool, "scale_factor": float}.
    Handles: currency symbols/words, commas, parenthetical negatives,
    percent signs, scale words (thousand/million/billion/k/m/bn/b),
    en-dash negatives, and mixed whitespace.
    """
    if not isinstance(text, str):
        return {"value": None, "is_percent": False, "scale_factor": 1.0}

    s = text.strip()
    if not s:
        return {"value": None, "is_percent": False, "scale_factor": 1.0}

    is_percent = False
    scale_factor = 1.0
    is_negative = False

    # Detect parenthetical negatives: "(1,234)" or "( 1,234 )"
    if s.startswith("(") and s.endswith(")"):
        is_negative = True
        s = s[1:-1].strip()

    # Detect percent (before stripping, so we know it was there)
    if "%" in s:
        is_percent = True
        s = s.replace("%", "").strip()

    # Strip currency symbols
    s = _CELL_CURRENCY_SYMBOLS.sub("", s)

    # Strip currency words
    s = _CELL_CURRENCY_WORDS.sub("", s)

    # Detect and strip scale words (e.g., "166.3 million")
    m = _CELL_SCALE_PATTERN.search(s)
    if m:
        word = (m.group(1) or m.group(2)).lower()
        scale_factor = _CELL_SCALE_MAP.get(word, 1.0)
        s = s[:m.start()] + s[m.end():]

    # Detect scale suffix attached to number end (e.g., "1.2bn", "5K", "2.5M")
    if scale_factor == 1.0:
        stripped = s.strip()
        m2 = _CELL_SCALE_SUFFIX.search(stripped)
        if m2:
            suffix = m2.group(1).lower()
            scale_factor = _CELL_SCALE_MAP.get(suffix, 1.0)
            s = stripped[:m2.start()]

    # Handle en-dash / minus variants
    s = s.replace("\u2013", "-").replace("\u2014", "-")

    # Strip commas
    s = s.replace(",", "")

    # Collapse whitespace and strip
    s = s.strip()
    if not s:
        return {"value": None, "is_percent": is_percent, "scale_factor": scale_factor}

    # Check for explicit negative sign
    if s.startswith("-"):
        is_negative = True
        s = s[1:].strip()

    # Parse the remaining numeric string
    try:
        raw_value = float(s)
    except ValueError:
        return {"value": None, "is_percent": is_percent, "scale_factor": scale_factor}

    if is_negative:
        raw_value = -raw_value

    # Apply percent: divide by 100 (matches claim extraction behavior)
    if is_percent:
        raw_value = raw_value / 100.0

    # Apply scale factor
    raw_value = raw_value * scale_factor

    return {"value": raw_value, "is_percent": is_percent, "scale_factor": scale_factor}


def _to_decimal(v: float) -> Decimal:
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError):
        return Decimal(0)


def _detect_currency(text: str) -> Optional[str]:
    for sym, code in _CURRENCY_SYMBOLS.items():
        if sym in text:
            return code
    m = _CURRENCY_WORDS.search(text)
    if m:
        token = m.group(1).lower().rstrip(".")
        mapping = {"usd": "USD", "eur": "EUR", "gbp": "GBP", "jpy": "JPY",
                    "inr": "INR", "lkr": "LKR", "rs": "INR",
                    "dollar": "USD", "dollars": "USD",
                    "rupee": "INR", "rupees": "INR"}
        return mapping.get(token, token.upper())
    return None


def _detect_period(text: str) -> Optional[str]:
    m = _PERIOD_PATTERN.search(text)
    return m.group(1).strip() if m else None


def _classify_unit_type(claim: NumericClaim) -> str:
    if claim.unit == "percent":
        return "percent"
    if claim.scale_token:
        return "amount"
    return "amount"


def _scale_label(claim: NumericClaim) -> str:
    if not claim.scale_token:
        return "raw"
    token = claim.scale_token.lower()
    if token in ("k", "thousand", "thousands"):
        return "K"
    if token in ("m", "million", "millions"):
        return "M"
    if token in ("b", "billion", "billions"):
        return "B"
    return "raw"


def detect_table_scale(evidence_content: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Detect table-level scale from column headers or units metadata.

    Returns scale label (K/M/B) or None.
    """
    if not evidence_content or not isinstance(evidence_content, dict):
        return None
    columns = evidence_content.get("columns", [])
    units = evidence_content.get("units", {})
    search_texts = [str(c) for c in columns] + [str(v) for v in units.values()]
    for txt in search_texts:
        m = _TABLE_SCALE_PATTERN.search(txt)
        if m:
            word = m.group(1).lower().split()[-1]
            return _SCALE_WORD_TO_LABEL.get(word, None)
    return None


def normalize_claims(
    claims: List[NumericClaim],
    evidence_content: Optional[Dict[str, Any]] = None,
    default_tolerance: float = 0.01,
) -> List[NumericClaim]:
    """Normalize claims with context-aware enrichment.

    Mutates claims in-place and returns the same list for pipeline compatibility.
    Each claim is enriched with: value_decimal, unit_type, scale_label, currency,
    period, approximate flag, and adjusted tolerance.
    """
    table_scale = detect_table_scale(evidence_content)

    for claim in claims:
        # Decimal value
        claim.value_decimal = _to_decimal(claim.parsed_value)

        # Unit type
        claim.unit_type = _classify_unit_type(claim)

        # Scale label
        claim.scale_label = _scale_label(claim)

        # If table has a declared scale and claim has no explicit scale, apply it
        if table_scale and claim.scale_label == "raw" and claim.unit_type == "amount":
            multiplier = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}.get(table_scale, 1)
            claim.parsed_value = float(claim.value_decimal * Decimal(str(multiplier)))
            claim.value_decimal = _to_decimal(claim.parsed_value)
            claim.scale_label = table_scale

        # Currency
        claim.currency = _detect_currency(claim.raw_text)

        # Period
        claim.period = _detect_period(claim.raw_text)

        # Approximate hedge
        claim.approximate = bool(_APPROX_PATTERNS.search(claim.raw_text))

        # Tolerance
        claim.tolerance_rel = default_tolerance
        claim.tolerance_abs = 0.0
        if claim.approximate:
            claim.tolerance_rel = min(default_tolerance * 2.0, 0.10)
            claim.tolerance_abs = abs(claim.parsed_value) * 0.02

    return claims


def normalize_bps(raw_text: str) -> Optional[NumericClaim]:
    """Parse a basis-point expression and return a normalized NumericClaim.

    Example: '150 bps' -> parsed_value=0.015, unit_type='bps'
    Returns None if no BPS expression found.
    """
    m = _BPS_PATTERN.search(raw_text)
    if not m:
        return None
    bps_value = Decimal(m.group(1))
    decimal_value = bps_value / Decimal("10000")
    return NumericClaim(
        raw_text=m.group(0),
        parsed_value=float(decimal_value),
        char_span=(m.start(), m.end()),
        unit="bps",
        scale_token=None,
        unit_type="bps",
        scale_label="raw",
        value_decimal=decimal_value,
        tolerance_rel=0.01,
    )
