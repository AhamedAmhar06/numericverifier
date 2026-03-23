"""Context-aware evidence grounding with composite scoring.

Scoring formula:
  score = w_numeric * numeric_score + w_period * period_score
        + w_unit * unit_score + w_lineitem * lineitem_score

Hard fail: if unit_type mismatch (amount vs percent), score forced to 0.
"""
import re
from typing import List, Optional
from .types import NumericClaim, EvidenceItem, GroundingMatch

# Scoring weights
_W_NUMERIC = 0.50
_W_PERIOD = 0.20
_W_UNIT = 0.15
_W_LINEITEM = 0.15

_PERIOD_RE = re.compile(r"\b((?:FY\s*)?20\d{2}|Q[1-4](?:\s*20\d{2})?)\b", re.IGNORECASE)

_PNL_LINE_ITEM_KEYWORDS = {
    "revenue": "revenue", "sales": "revenue", "turnover": "revenue",
    "cogs": "cogs", "cost of sales": "cogs", "cost of goods sold": "cogs", "cost of revenue": "cogs",
    "gross profit": "gross_profit", "gross income": "gross_profit",
    "operating expenses": "operating_expenses", "opex": "operating_expenses",
    "operating income": "operating_income", "operating profit": "operating_income", "ebit": "operating_income",
    "net income": "net_income", "net profit": "net_income", "profit after tax": "net_income",
    "tax": "taxes", "taxes": "taxes", "income tax": "taxes",
    "interest": "interest", "interest expense": "interest",
}


def _extract_periods(text: str) -> set:
    return {m.group(1).strip().lower() for m in _PERIOD_RE.finditer(text)}


def _infer_line_item_from_text(text: str) -> Optional[str]:
    text_lower = text.lower()
    for keyword, canonical in sorted(_PNL_LINE_ITEM_KEYWORDS.items(), key=lambda x: -len(x[0])):
        if keyword in text_lower:
            return canonical
    return None


def _numeric_score(claim_value: float, evidence_value: float, tolerance: float) -> float:
    if evidence_value == 0 and claim_value == 0:
        return 1.0
    if evidence_value == 0:
        return 0.0
    rel_error = abs((claim_value - evidence_value) / evidence_value)
    if rel_error <= tolerance:
        return 1.0
    if rel_error <= tolerance * 5:
        return max(0.0, 1.0 - (rel_error - tolerance) / (tolerance * 4))
    return 0.0


def _period_score(claim: NumericClaim, evidence: EvidenceItem, question: Optional[str] = None) -> float:
    claim_periods = set()
    if claim.period:
        claim_periods.add(claim.period.lower())
    claim_periods |= _extract_periods(claim.raw_text)
    if question:
        claim_periods |= _extract_periods(question)
    if not claim_periods:
        return 0.5  # neutral when no period info

    evidence_period = (evidence.period or "").lower()
    evidence_context_periods = _extract_periods(evidence.context or "")
    evidence_periods = evidence_context_periods
    if evidence_period:
        evidence_periods.add(evidence_period)
    if not evidence_periods:
        return 0.5

    if claim_periods & evidence_periods:
        return 1.0
    return 0.0


def _unit_score(claim: NumericClaim, evidence: EvidenceItem) -> float:
    claim_unit = getattr(claim, "unit_type", None) or ("percent" if claim.unit == "percent" else "amount")
    ev_is_percent = getattr(evidence, "is_percent", False)
    if claim_unit == "percent":
        if ev_is_percent:
            return 1.0  # both are percent-normalized
        if abs(evidence.value) <= 1.0:
            return 1.0  # evidence looks like a ratio
        # Evidence is a large absolute value — possible un-divided percent.
        # Don't hard-fail; allow _compute_score's percent-rescale fallback.
        return 0.5
    if claim_unit == "amount" and ev_is_percent:
        return 0.0  # hard fail: claim is amount but evidence is percent
    return 1.0


def _lineitem_score(claim: NumericClaim, evidence: EvidenceItem, question: Optional[str] = None) -> float:
    ev_canonical = getattr(evidence, "canonical_line_item", None)
    if not ev_canonical:
        return 0.5  # neutral

    claim_text = claim.raw_text
    if question:
        claim_text = question + " " + claim_text
    inferred = _infer_line_item_from_text(claim_text)
    if inferred and inferred == ev_canonical:
        return 1.0
    if inferred and inferred != ev_canonical:
        return 0.2
    return 0.5


def _compute_score(claim: NumericClaim, evidence: EvidenceItem, tolerance: float,
                   question: Optional[str] = None) -> float:
    ns = _numeric_score(claim.parsed_value, evidence.value, tolerance)
    us = _unit_score(claim, evidence)
    if us == 0.0:
        return 0.0

    # Percent-rescale fallback: if claim is percent (e.g., 0.586) and evidence is
    # un-divided (e.g., 58.6 in a "%" column), try claim*100 vs evidence.
    claim_unit = getattr(claim, "unit_type", None) or ("percent" if claim.unit == "percent" else "amount")
    ev_is_percent = getattr(evidence, "is_percent", False)
    if ns == 0.0 and claim_unit == "percent" and not ev_is_percent and evidence.value != 0:
        rescaled = claim.parsed_value * 100.0
        ns = _numeric_score(rescaled, evidence.value, tolerance)

    if ns == 0.0:
        return 0.0
    ps = _period_score(claim, evidence, question)
    ls = _lineitem_score(claim, evidence, question)
    return _W_NUMERIC * ns + _W_PERIOD * ps + _W_UNIT * us + _W_LINEITEM * ls


def ground_claim(
    claim: NumericClaim,
    evidence_items: List[EvidenceItem],
    tolerance: float,
    question: Optional[str] = None,
    top_k: int = 3,
) -> Optional[GroundingMatch]:
    """Ground a single claim using composite scoring.

    Returns the best match with confidence and top-k metadata, or None.
    """
    scored = []
    claim_unit = getattr(claim, "unit_type", None) or ("percent" if claim.unit == "percent" else "amount")
    for ev in evidence_items:
        score = _compute_score(claim, ev, tolerance, question)
        if score <= 0.0:
            continue
        # Use effective comparison value (handles percent rescale)
        cmp_value = claim.parsed_value
        ev_is_percent = getattr(ev, "is_percent", False)
        if claim_unit == "percent" and not ev_is_percent and abs(ev.value) > 1.0:
            cmp_value = claim.parsed_value * 100.0
        distance = abs(cmp_value - ev.value)
        if ev.value != 0:
            relative_error = abs((cmp_value - ev.value) / ev.value)
        else:
            relative_error = float('inf') if cmp_value != 0 else 0.0
        if not (distance <= tolerance or relative_error <= tolerance * 5):
            continue
        scored.append((score, distance, relative_error, ev))

    if not scored:
        return None

    scored.sort(key=lambda x: (-x[0], x[1]))
    best_score, best_dist, best_re, best_ev = scored[0]
    second_score = scored[1][0] if len(scored) > 1 else 0.0
    margin = best_score - second_score
    ambiguous = len(scored) > 1 and margin < 0.10

    match = GroundingMatch(
        claim=claim,
        evidence=best_ev,
        distance=best_dist,
        relative_error=best_re,
        ambiguous=ambiguous,
        confidence=round(best_score, 4),
        confidence_margin=round(margin, 4),
    )
    return match


def ground_claims(
    claims: List[NumericClaim],
    evidence_items: List[EvidenceItem],
    tolerance: float,
    question: Optional[str] = None,
) -> List[GroundingMatch]:
    """Ground all claims to evidence using composite scoring."""
    grounding = []
    for claim in claims:
        match = ground_claim(claim, evidence_items, tolerance, question=question)
        if match:
            grounding.append(match)
    return grounding
