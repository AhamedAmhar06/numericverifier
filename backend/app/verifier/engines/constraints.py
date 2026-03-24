"""Constraint-based verification engine with typed Violation codes."""
from typing import List, Optional, Set
from ..types import (
    VerificationResult, NumericClaim, GroundingMatch, Violation,
    V_SCALE_MISMATCH, V_SCALE_LABEL_MISMATCH, V_PERIOD_MISMATCH,
    V_PNL_PERIOD_STRICT, V_MISSING_PERIOD_IN_EVIDENCE,
)

# Base-10 exponents for scale labels used in financial claims and evidence items.
_SCALE_MAGNITUDE = {
    'T': 12,
    'B': 9, 'G': 9,
    'M': 6,
    'K': 3,
}


def _magnitude(scale_label: Optional[str]) -> Optional[int]:
    """Return the base-10 exponent for a scale label, or None if unknown/raw."""
    if not scale_label or scale_label.upper() == 'RAW':
        return None
    return _SCALE_MAGNITUDE.get(scale_label.upper(), None)

_TIME_KEYWORDS = [
    '2020', '2021', '2022', '2023', '2024', '2025',
    'Q1', 'Q2', 'Q3', 'Q4',
    'january', 'february', 'march', 'april', 'may', 'june',
    'july', 'august', 'september', 'october', 'november', 'december',
]

# Year/quarter only — used for MISSING_PERIOD_IN_EVIDENCE check (months are too granular
# for P&L period matching and cause false positives on real financial tables).
_STRICT_PERIOD_KEYWORDS = [
    '2020', '2021', '2022', '2023', '2024', '2025',
    'Q1', 'Q2', 'Q3', 'Q4',
]


def _periods_in_text(text: str) -> Set[str]:
    t = text.lower()
    return {kw for kw in _TIME_KEYWORDS if kw in t}


def _strict_periods_in_text(text: str) -> Set[str]:
    t = text.lower()
    return {kw for kw in _STRICT_PERIOD_KEYWORDS if kw in t}


def verify_constraints(
    claim: NumericClaim,
    grounding_match: Optional[GroundingMatch],
    all_claims: List[NumericClaim],
    evidence_items: List,
    question: Optional[str] = None,
    pnl_periods: Optional[List[str]] = None,
) -> VerificationResult:
    result = VerificationResult(
        claim=claim,
        grounded=grounding_match is not None,
        grounding_match=grounding_match,
    )

    violations = []

    if grounding_match:
        claim_scale = claim.scale_token
        evidence_value = grounding_match.evidence.value

        if claim_scale:
            if abs(evidence_value) >= 1_000_000_000:
                expected_scale = "billion"
            elif abs(evidence_value) >= 1_000_000:
                expected_scale = "million"
            elif abs(evidence_value) >= 1_000:
                expected_scale = "thousand"
            else:
                expected_scale = None
            scale_map = {'K': 'thousand', 'k': 'thousand', 'M': 'million', 'm': 'million',
                         'B': 'billion', 'b': 'billion'}
            claim_scale_normalized = scale_map.get(claim_scale, claim_scale)
            if expected_scale and claim_scale_normalized != expected_scale:
                violations.append(Violation(
                    code=V_SCALE_MISMATCH,
                    message=f"Scale mismatch: claim uses {claim_scale}, evidence suggests {expected_scale}",
                    metadata={"claim_scale": claim_scale, "expected_scale": expected_scale},
                ))

    # Scale LABEL disagreement — fires when the answer uses a different
    # order-of-magnitude scale label than the evidence even when expanded
    # numerics happen to be close (e.g. "$383 billion" vs evidence in millions).
    # Only fires when BOTH sides carry an explicit, known scale label and the
    # magnitude difference is >= 3 (i.e. at least one decade-of-thousand apart).
    if claim.scale_label:
        cl_mag = _magnitude(claim.scale_label)
        if cl_mag is not None:
            # Use grounding match evidence first; fall back to scanning all
            # evidence_items when the grounding engine found no direct match
            # (this happens when claim and evidence values are in different
            # absolute scales — e.g. claim=383e9, evidence=383285 raw-millions).
            candidates = (
                [grounding_match.evidence] if grounding_match
                else list(evidence_items)
            )
            for ev in candidates:
                ev_label = getattr(ev, 'scale_label', None)
                ev_mag = _magnitude(ev_label)
                if ev_mag is None or abs(cl_mag - ev_mag) < 3:
                    continue
                ev_abs = ev.value * (10 ** ev_mag)
                if ev_abs == 0:
                    continue
                rel_err = abs(claim.parsed_value - ev_abs) / abs(ev_abs)
                if rel_err <= claim.tolerance_rel:
                    violations.append(Violation(
                        code=V_SCALE_LABEL_MISMATCH,
                        message=(
                            f"Scale label mismatch: answer uses "
                            f"'{claim.scale_label}' (10^{cl_mag}) but "
                            f"evidence is '{ev_label}' (10^{ev_mag})"
                        ),
                        metadata={
                            "claim_scale_label": claim.scale_label,
                            "evidence_scale_label": ev_label,
                            "magnitude_diff": abs(cl_mag - ev_mag),
                        },
                    ))
                    break  # one violation per claim is enough

    if grounding_match and grounding_match.evidence.context:
        claim_periods = _periods_in_text(claim.raw_text)
        evidence_context_lower = grounding_match.evidence.context.lower()
        evidence_periods = {kw for kw in _TIME_KEYWORDS if kw in evidence_context_lower}
        if claim_periods and evidence_periods:
            if not any(cp in evidence_periods for cp in claim_periods):
                violations.append(Violation(
                    code=V_PERIOD_MISMATCH,
                    message="Period mismatch: claim and evidence reference different time periods",
                    metadata={"claim_periods": list(claim_periods),
                              "evidence_periods": list(evidence_periods)},
                ))

    if question and pnl_periods is not None:
        question_periods = _strict_periods_in_text(question)
        pnl_periods_lower = {p.lower() for p in pnl_periods}
        for qp in question_periods:
            # Bare year "2023" must match FY-prefixed label "fy2023" (substring).
            # pnl_parser._normalize_period() may produce "FY2023" from "FY23"/"'23",
            # so exact set membership would false-fire on every FY-labelled table.
            if not any(qp in p for p in pnl_periods_lower):
                violations.append(Violation(
                    code=V_MISSING_PERIOD_IN_EVIDENCE,
                    message="missing_period_in_evidence",
                    metadata={"missing_period": qp},
                ))
                break

    if question and grounding_match and grounding_match.evidence.context and pnl_periods is not None:
        question_periods = _strict_periods_in_text(question)
        evidence_context_lower = (grounding_match.evidence.context or "").lower()
        evidence_periods = {kw for kw in _STRICT_PERIOD_KEYWORDS if kw.lower() in evidence_context_lower}
        if question_periods and evidence_periods:
            if not any(qp in evidence_periods for qp in question_periods):
                violations.append(Violation(
                    code=V_PNL_PERIOD_STRICT,
                    message="pnl_period_strict_mismatch",
                    metadata={"question_periods": list(question_periods),
                              "evidence_periods": list(evidence_periods)},
                ))

    result.constraint_violations = violations
    return result
