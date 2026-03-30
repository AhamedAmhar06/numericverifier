"""Translate internal verification signals into plain English for financial analysts.

Provides translate_for_analyst() which converts the verifier's internal signal dict,
claim audit list, and decision into a structured analyst-readable summary.
"""
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Lookup tables
# ---------------------------------------------------------------------------

CLAIM_DECISION_TRANSLATIONS: Dict[str, str] = {
    "supported":        "Verified against source data ✓",
    "value_error":      "Value differs from source data ✗",
    "ungrounded":       "Could not find matching value in table ✗",
    "scale_violation":  "Unit scale mismatch detected ✗",
    "period_violation": "Wrong fiscal period ✗",
    "repaired":         "Automatically corrected to match source data ↻",
    "unverifiable":     "Could not be independently computed ?",
}

RISK_LEVEL_TRANSLATIONS: Dict[str, str] = {
    "low":      "Low risk — verified",
    "medium":   "Medium risk — review recommended",
    "high":     "High risk — manual verification required",
    "critical": "Critical — do not use without verification",
}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def translate_claim_decision(code: str) -> str:
    """Return analyst-readable text for a claim_decision code."""
    return CLAIM_DECISION_TRANSLATIONS.get(code, code)


def translate_risk_level(level: str) -> str:
    """Return analyst-readable text for a risk_level code."""
    return RISK_LEVEL_TRANSLATIONS.get((level or "").lower(), level)


# ---------------------------------------------------------------------------
# Main translation function
# ---------------------------------------------------------------------------

def translate_for_analyst(
    signals: Dict[str, Any],
    claim_audit: List[Dict[str, Any]],
    decision: Optional[str],
    rationale: Optional[str],
    audit_summary: Optional[Dict[str, Any]] = None,
    shap_explanation: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Produce an analyst-readable summary from verifier internals.

    Args:
        signals:       signals dict from the verifier response.
        claim_audit:   list of claim audit dicts.
        decision:      top-level decision ("ACCEPT" / "REPAIR" / "FLAG").
        rationale:     raw internal rationale string (used as fallback only).
        audit_summary: audit_summary dict (contains ml_confidence, requires_human_review).

    Returns:
        {
          "summary":        str,   # one-sentence plain-English summary
          "findings":       [str], # bulleted list of plain-English observations
          "recommendation": str,   # "Accept / Review / Reject" with reason
        }
    """
    audit_summary = audit_summary or {}
    findings: List[str] = []

    # -- Signal-driven findings ------------------------------------------

    unsupported = _int(signals.get("unsupported_claims_count", 0))
    if unsupported > 0:
        findings.append(
            "One or more numeric values in the answer could not be "
            "matched to the evidence table."
        )

    scale_mismatch = _int(signals.get("scale_mismatch_count", 0))
    if scale_mismatch > 0:
        findings.append(
            "The answer uses a different unit scale than the evidence "
            "table (e.g. billions vs millions)."
        )

    period_mismatch = _int(signals.get("pnl_period_strict_mismatch_count", 0))
    if period_mismatch > 0:
        findings.append(
            "The answer references a different fiscal period than "
            "the question asked about."
        )

    identity_fail = _int(signals.get("pnl_identity_fail_count", 0))
    if identity_fail > 0:
        findings.append(
            "The financial figures in the answer are internally "
            "inconsistent (e.g. stated gross profit does not equal "
            "revenue minus cost of sales)."
        )

    unverifiable = _int(signals.get("unverifiable_claim_count", 0))
    if unverifiable > 0:
        findings.append(
            "Some calculations could not be independently verified "
            "(complex derived metrics)."
        )

    try:
        coverage_f = float(signals.get("coverage_ratio", 1.0) or 1.0)
    except (TypeError, ValueError):
        coverage_f = 1.0

    all_clear = (unsupported == 0 and scale_mismatch == 0 and period_mismatch == 0)

    if coverage_f < 0.5:
        findings.append(
            "Less than half the numeric claims in the answer could "
            "be verified against the evidence."
        )
    elif coverage_f >= 0.8 and all_clear:
        findings.append("All key figures were verified against the source data.")

    requires_review = bool(audit_summary.get("requires_human_review", False))
    if requires_review:
        findings.append(
            "This decision was made with moderate confidence. "
            "Independent verification is recommended."
        )

    # -- Fallback when no signals fired ----------------------------------
    if not findings:
        d = (decision or "").upper()
        if d == "ACCEPT":
            findings.append("All key figures were verified against the source data.")
        else:
            findings.append(
                "Verification did not complete successfully. Manual review required."
            )

    # -- SHAP-driven primary factor finding ------------------------------
    if shap_explanation:
        top_signals = shap_explanation.get("top_signals") or []
        if top_signals:
            top = top_signals[0]
            top_signal_name = top.get("signal", "")
            shap_finding = f"Primary verification factor: {top_signal_name}"
            # Only add if not already mentioned
            if not any(top_signal_name in f for f in findings):
                findings.append(shap_finding)

    # -- Recommendation --------------------------------------------------
    ml_confidence = audit_summary.get("ml_confidence")
    recommendation = _build_recommendation(decision, ml_confidence)

    # -- One-line summary ------------------------------------------------
    summary = _build_summary(decision, requires_review)

    return {
        "summary": summary,
        "findings": findings,
        "recommendation": recommendation,
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _build_recommendation(decision: Optional[str], ml_confidence: Any) -> str:
    d = (decision or "").upper()
    if d == "ACCEPT":
        try:
            conf = float(ml_confidence) if ml_confidence is not None else None
        except (TypeError, ValueError):
            conf = None
        if conf is not None and conf >= 0.85:
            return "Accept — high confidence verification"
        return "Review — accepted with moderate confidence"
    if d == "REPAIR":
        return (
            "Review — answer was automatically corrected, "
            "please verify the correction"
        )
    # FLAG or unknown
    return "Reject — verification failed, do not use this answer"


def _build_summary(decision: Optional[str], requires_review: bool) -> str:
    d = (decision or "").upper()
    if d == "ACCEPT" and not requires_review:
        return (
            "The answer has been verified against the financial data "
            "and is consistent with the source table."
        )
    if d == "ACCEPT" and requires_review:
        return (
            "The answer appears consistent with the source data, but was accepted "
            "with moderate confidence — independent review is recommended."
        )
    if d == "REPAIR":
        return (
            "The answer contained errors that were automatically corrected; "
            "the repaired answer is consistent with the source table."
        )
    return (
        "The answer could not be verified against the financial data "
        "and should not be used without manual review."
    )
