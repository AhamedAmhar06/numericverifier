"""Per-claim structured audit log builder."""
from typing import List, Optional, Dict, Any
from .types import (
    NumericClaim, VerificationResult,
    V_SCALE_MISMATCH, V_SCALE_LABEL_MISMATCH,
    V_PERIOD_MISMATCH, V_PNL_PERIOD_STRICT, V_MISSING_PERIOD_IN_EVIDENCE,
)
from .signals import is_temporal_claim

_SCALE_VIOLATIONS = {V_SCALE_MISMATCH, V_SCALE_LABEL_MISMATCH}
_PERIOD_VIOLATIONS = {V_PERIOD_MISMATCH, V_PNL_PERIOD_STRICT, V_MISSING_PERIOD_IN_EVIDENCE}


def _violation_code(v) -> str:
    from .types import Violation
    if isinstance(v, Violation):
        return v.code
    return str(v) if v else ""


def _claim_decision(
    vr: VerificationResult,
    tolerance: float,
    repaired: bool = False,
) -> str:
    if repaired:
        return "repaired"
    vcodes = [_violation_code(v) for v in (vr.constraint_violations or [])]
    if any(c in _SCALE_VIOLATIONS for c in vcodes):
        return "scale_violation"
    if any(c in _PERIOD_VIOLATIONS for c in vcodes):
        return "period_violation"
    if not vr.grounded:
        return "ungrounded"
    if vr.grounding_match and vr.grounding_match.relative_error > tolerance:
        return "value_error"
    return "supported"


def _risk_level(
    vr: VerificationResult,
    decision: str,
    tolerance: float,
) -> str:
    if decision in ("scale_violation", "period_violation"):
        return "critical"
    if decision in ("ungrounded", "value_error"):
        return "high"
    rel_err = vr.grounding_match.relative_error if vr.grounding_match else 0.0
    if rel_err < 0.001:
        return "low"
    return "medium"


def _build_grounding_block(vr: VerificationResult) -> Dict[str, Any]:
    gm = vr.grounding_match
    if gm is None:
        return {
            "matched": False,
            "evidence_label": None,
            "evidence_period": None,
            "evidence_value": None,
            "relative_error": None,
            "ambiguous": None,
            "confidence_margin": None,
        }
    ev = gm.evidence
    return {
        "matched": True,
        "evidence_label": ev.row_label,
        "evidence_period": ev.period or ev.col_label,
        "evidence_value": ev.value,
        "relative_error": round(gm.relative_error, 6),
        "ambiguous": gm.ambiguous,
        "confidence_margin": round(gm.confidence_margin, 4),
    }


def _build_verification_block(vr: VerificationResult, risk: str) -> Dict[str, Any]:
    vcodes_out = []
    for v in (vr.constraint_violations or []):
        from .types import Violation
        if isinstance(v, Violation):
            vcodes_out.append({"code": v.code, "message": v.message})
        else:
            vcodes_out.append({"code": str(v), "message": None})

    exec_result_str = None
    if vr.execution_supported and vr.execution_result is not None:
        exec_result_str = "identity_check_passed"
    elif vr.execution_error:
        exec_result_str = vr.execution_error

    return {
        "lookup_supported": vr.lookup_supported,
        "execution_checked": vr.execution_supported or vr.execution_error is not None,
        "execution_result": exec_result_str,
        "constraint_violations": vcodes_out,
        "risk_level": risk,
    }


def build_claim_audit(
    claims: List[NumericClaim],
    verification_results: List[VerificationResult],
    tolerance: float,
    repair_audit: Optional[Dict[str, Any]] = None,
    accepted_after_repair: bool = False,
) -> List[Dict[str, Any]]:
    """Build per-claim audit entries from the final pipeline state."""
    # Build a set of new_text values from applied repair actions so we can
    # detect repaired claims by matching raw_text in pass-2 (spans shift after repair).
    repaired_texts: set = set()
    repair_by_new_text: Dict[str, Dict] = {}
    if accepted_after_repair and repair_audit:
        for action in repair_audit.get("repair_applied", []):
            nt = action.get("new_text")
            if nt:
                repaired_texts.add(nt)
                repair_by_new_text[nt] = action

    entries = []
    for i, (claim, vr) in enumerate(zip(claims, verification_results)):
        if is_temporal_claim(claim):
            continue

        is_repaired = claim.raw_text in repaired_texts
        decision = _claim_decision(vr, tolerance, repaired=is_repaired)
        risk = _risk_level(vr, decision, tolerance)

        entry: Dict[str, Any] = {
            "claim_id": i + 1,
            "raw_text": claim.raw_text,
            "parsed_value": claim.parsed_value,
            "unit_type": claim.unit_type,
            "scale_label": claim.scale_token or claim.scale_label,
            "grounding": _build_grounding_block(vr),
            "verification": _build_verification_block(vr, risk),
            "claim_decision": decision,
        }

        if is_repaired:
            action = repair_by_new_text.get(claim.raw_text, {})
            entry["repair_detail"] = {
                "original_text": action.get("old_text"),
                "corrected_text": action.get("new_text"),
                "correction_type": action.get("reason"),
            }

        entries.append(entry)
    return entries


def build_audit_summary(
    claim_audit: List[Dict[str, Any]],
    signals_dict: Dict[str, Any],
    repair_audit: Optional[Dict[str, Any]],
    accepted_after_repair: bool,
    ml_confidence: Optional[float] = None,
) -> Dict[str, Any]:
    total = len(claim_audit)
    supported = sum(1 for c in claim_audit if c["claim_decision"] == "supported")
    value_error = sum(1 for c in claim_audit if c["claim_decision"] == "value_error")
    ungrounded = sum(1 for c in claim_audit if c["claim_decision"] == "ungrounded")
    violation = sum(
        1 for c in claim_audit
        if c["claim_decision"] in ("scale_violation", "period_violation")
    )
    repaired = sum(1 for c in claim_audit if c["claim_decision"] == "repaired")

    risks = [c["verification"]["risk_level"] for c in claim_audit]
    if "critical" in risks:
        overall_risk = "critical"
    elif "high" in risks or (ungrounded > 0 and total > 1):
        overall_risk = "high"
    elif "medium" in risks or ungrounded > 0:
        overall_risk = "medium"
    elif total == 0:
        overall_risk = "low"
    else:
        overall_risk = "low"

    return {
        "total_claims": total,
        "supported_claims": supported,
        "value_error_claims": value_error,
        "ungrounded_claims": ungrounded,
        "violation_claims": violation,
        "repaired_claims": repaired,
        "coverage_ratio": signals_dict.get("coverage_ratio", 0.0),
        "pipeline_passes": 2 if repair_audit else 1,
        "repair_applied": accepted_after_repair,
        "overall_risk": overall_risk,
        "ml_confidence": round(ml_confidence, 4) if ml_confidence is not None else None,
        "requires_human_review": (ml_confidence is not None and ml_confidence < 0.75),
    }
