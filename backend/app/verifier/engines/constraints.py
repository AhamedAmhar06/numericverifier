"""Constraint-based verification engine with typed Violation codes."""
from typing import List, Optional, Set
from ..types import (
    VerificationResult, NumericClaim, GroundingMatch, Violation,
    V_SCALE_MISMATCH, V_SCALE_LABEL_MISMATCH, V_PERIOD_MISMATCH,
    V_PNL_PERIOD_STRICT, V_MISSING_PERIOD_IN_EVIDENCE,
)

# Canonical scale family → set of tokens that belong to it.
# Used for label-based scale disagreement detection (TC3-style: "$383 billion"
# vs a table declared "in millions").
_SCALE_DENOMINATION_MAP = {
    "billion":  {"B", "b", "billion",  "billions"},
    "million":  {"M", "m", "million",  "millions"},
    "thousand": {"K", "k", "thousand", "thousands", "000s"},
}


def _scale_family(token: Optional[str]) -> Optional[str]:
    """Return canonical family ('billion'/'million'/'thousand') or None."""
    if not token:
        return None
    t = token.lower().strip()
    for family, variants in _SCALE_DENOMINATION_MAP.items():
        if t in variants:
            return family
    return None

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
    table_scale: Optional[str] = None,
) -> VerificationResult:
    result = VerificationResult(
        claim=claim,
        grounded=grounding_match is not None,
        grounding_match=grounding_match,
    )

    violations = []

    # Two-tier scale denomination check.
    #
    # Tier 1 — Label comparison (preferred): when the table declares its denomination
    # via caption (e.g. "in millions"), compare scale family tokens directly.  This is
    # robust regardless of whether evidence values are stored as raw units or pre-
    # expanded absolute dollars, because no magnitude arithmetic is involved.
    # Fires: "$383 billion" vs "in millions" table → FLAG (TC3).
    # Safe: "$169,148 million" vs "in millions" table → same family → no violation (TC1).
    #
    # Tier 2 — Magnitude fallback: when no caption-declared scale is available, infer
    # the expected scale from the raw magnitude of the evidence value and compare
    # against the claim's scale token.  This handles synthetic test cases where the
    # table has no caption but stores values in raw units (e.g. 500000 ≈ thousands),
    # and the claim uses the wrong scale (e.g. "0.50 million").
    # Tier 1: label comparison (no grounding required — only compares declared scale
    # families).  Fires whenever the claim carries a scale suffix and the table
    # caption declares a different scale family (e.g. "billion" vs "In millions").
    # Must run independently of grounding so it catches scale errors even when the
    # wrong-unit value happens to be numerically close to a table cell
    # (e.g. "$211 billion" ≈ "$211,915 million" within 0.5% tolerance).
    if claim.scale_token and table_scale:
        table_scale_family = _scale_family(table_scale)
        claim_scale_family = _scale_family(claim.scale_token)
        if (table_scale_family is not None
                and claim_scale_family is not None
                and table_scale_family != claim_scale_family):
            violations.append(Violation(
                code=V_SCALE_LABEL_MISMATCH,
                message=(
                    f"Scale label mismatch: answer uses '{claim.scale_token}' "
                    f"but table is declared in {table_scale_family}s"
                ),
                metadata={
                    "claim_scale": claim.scale_token,
                    "table_scale": table_scale,
                },
            ))

    if grounding_match and claim.scale_token and not table_scale:
        # Tier 2: magnitude fallback (no caption — raw-unit evidence assumed)
        evidence_value = grounding_match.evidence.value
        if abs(evidence_value) >= 1_000_000_000:
            expected_scale = "billion"
        elif abs(evidence_value) >= 1_000_000:
            expected_scale = "million"
        elif abs(evidence_value) >= 1_000:
            expected_scale = "thousand"
        else:
            expected_scale = None
        scale_map = {
            'K': 'thousand', 'k': 'thousand',
            'M': 'million',  'm': 'million',
            'B': 'billion',  'b': 'billion',
        }
        claim_scale_normalized = scale_map.get(claim.scale_token, claim.scale_token)
        if expected_scale and claim_scale_normalized != expected_scale:
            violations.append(Violation(
                code=V_SCALE_MISMATCH,
                message=(
                    f"Scale mismatch: claim uses '{claim.scale_token}' "
                    f"but evidence magnitude suggests {expected_scale}"
                ),
                metadata={
                    "claim_scale": claim.scale_token,
                    "expected_scale": expected_scale,
                },
            ))

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
