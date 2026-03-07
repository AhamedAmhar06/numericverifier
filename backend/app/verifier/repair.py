"""Deterministic repair module: propose corrected answer and re-verify.

Repair strategies (applied in priority order):
1. Replace with grounded evidence value (when claim differs beyond tolerance)
2. Replace with recomputed arithmetic value (identity/margin/growth)
3. Correct scale mismatch (rescale based on evidence metadata)
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from .types import NumericClaim, VerificationResult, GroundingMatch, VerifierSignals, Violation

_MAX_REPAIR_DEPTH = 1


@dataclass
class RepairAction:
    span: tuple
    old_text: str
    new_text: str
    reason: str
    provenance: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "span": list(self.span),
            "old_text": self.old_text,
            "new_text": self.new_text,
            "reason": self.reason,
            "provenance": self.provenance,
        }


@dataclass
class RepairResult:
    repaired_answer: str
    repair_actions: List[RepairAction]
    changed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "repaired_answer": self.repaired_answer,
            "repair_actions": [a.to_dict() for a in self.repair_actions],
            "changed": self.changed,
        }


def _format_number(value: float) -> str:
    if value == int(value) and abs(value) < 1e15:
        return str(int(value))
    return f"{value:.2f}"


def _violation_code(v) -> str:
    if isinstance(v, Violation):
        return v.code
    if isinstance(v, str):
        return v.upper()
    return ""


def attempt_repair(
    candidate_answer: str,
    claims: List[NumericClaim],
    verification_results: List[VerificationResult],
    grounding: List[GroundingMatch],
    signals: VerifierSignals,
    pnl_table: Any = None,
    tolerance: float = 0.01,
) -> RepairResult:
    """Attempt deterministic repair on a candidate answer.

    Returns RepairResult with the patched string and list of actions taken.
    Applies repairs from right-to-left (by char_span) to preserve offsets.
    """
    actions: List[RepairAction] = []
    answer = candidate_answer

    # Build claim -> verification / grounding lookup
    vr_map: Dict[int, VerificationResult] = {}
    gr_map: Dict[int, GroundingMatch] = {}
    for i, vr in enumerate(verification_results):
        vr_map[id(claims[i])] = vr
    for gm in grounding:
        gr_map[id(gm.claim)] = gm

    # Collect repair proposals (claim, new_value, reason, provenance)
    proposals = []

    for claim in claims:
        vr = vr_map.get(id(claim))
        gm = gr_map.get(id(claim))
        if vr is None:
            continue

        # Strategy 1: Grounded but differs
        if gm and gm.relative_error > tolerance and gm.distance > 0:
            proposals.append((
                claim,
                gm.evidence.value,
                "grounded_value_replacement",
                f"evidence:{gm.evidence.location or 'unknown'}",
            ))
            continue

        # Strategy 2: Scale mismatch correction
        has_scale_violation = any(
            _violation_code(v) == "SCALE_MISMATCH" or "scale mismatch" in str(v).lower()
            for v in (vr.constraint_violations or [])
        )
        if has_scale_violation and gm:
            proposals.append((
                claim,
                gm.evidence.value,
                "scale_correction",
                f"evidence:{gm.evidence.location or 'unknown'}",
            ))
            continue

        # Strategy 3: Unsupported claim with execution result
        if not vr.grounded and vr.execution_result is not None:
            proposals.append((
                claim,
                vr.execution_result,
                "recomputed_value_replacement",
                f"execution:{vr.execution_confidence or 'unknown'}",
            ))

    if not proposals:
        return RepairResult(repaired_answer=answer, repair_actions=[], changed=False)

    # Apply replacements right-to-left
    proposals.sort(key=lambda p: p[0].char_span[0], reverse=True)
    for claim, new_value, reason, provenance in proposals:
        start, end = claim.char_span
        old_text = answer[start:end]
        new_text = _format_number(new_value)
        if old_text == new_text:
            continue
        answer = answer[:start] + new_text + answer[end:]
        actions.append(RepairAction(
            span=(start, end),
            old_text=old_text,
            new_text=new_text,
            reason=reason,
            provenance=provenance,
        ))

    actions.reverse()  # restore left-to-right order for reporting
    return RepairResult(
        repaired_answer=answer,
        repair_actions=actions,
        changed=answer != candidate_answer,
    )
