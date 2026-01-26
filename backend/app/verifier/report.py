"""Audit report generation."""
from datetime import datetime
from typing import Dict, Any
from .types import AuditReport, NumericClaim, GroundingMatch, VerificationResult, VerifierSignals, Decision


def generate_report(
    question: str,
    candidate_answer: str,
    evidence_type: str,
    tolerance: float,
    claims: list[NumericClaim],
    grounding: list[GroundingMatch],
    verification: list[VerificationResult],
    signals: VerifierSignals,
    decision: Decision
) -> AuditReport:
    """Generate full audit report."""
    return AuditReport(
        timestamp=datetime.utcnow().isoformat(),
        question=question,
        candidate_answer=candidate_answer,
        evidence_type=evidence_type,
        tolerance=tolerance,
        claims=claims,
        grounding=grounding,
        verification=verification,
        signals=signals,
        decision=decision
    )

