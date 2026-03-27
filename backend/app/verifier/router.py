"""Domain router: P&L-only pipeline. Both /verify-only and /verify call this."""
import logging
from typing import Dict, Any, Optional

from .domain import classify_table_type, DomainContext

logger = logging.getLogger(__name__)
from .pnl_parser import parse_pnl_table
from .extract import extract_numeric_claims
from .normalize import normalize_claims
from .evidence import ingest_evidence
from .grounding import ground_claims
from .engines.lookup import verify_lookup
from .engines.constraints import verify_constraints
from .engines.pnl_execution import (
    run_pnl_checks, execute_claim_against_table, PnLCheckResult,
)
from .signals import compute_signals
from .audit import build_claim_audit, build_audit_summary
from ..ml.decision_model import decide
from .report import generate_report
from .repair import attempt_repair
from .types import VerificationResult, Decision
from ..eval.logging import log_run, log_signals, ensure_runs_directory
from ..core.config import settings


def _evidence_type(evidence: Any) -> str:
    if hasattr(evidence, "type"):
        return getattr(evidence, "type", "") or ""
    return (evidence or {}).get("type", "")


def _evidence_content(evidence: Any) -> Dict[str, Any]:
    if hasattr(evidence, "content"):
        c = getattr(evidence, "content", None)
        return c if isinstance(c, dict) else {}
    c = (evidence or {}).get("content")
    return c if isinstance(c, dict) else {}


def _short_circuit_flag(
    decision: str,
    rationale: str,
    domain: Dict[str, Any],
    engine_used: str,
    llm_used: bool = False,
    llm_fallback_reason: Optional[str] = None,
) -> Dict[str, Any]:
    sig = {
        "unsupported_claims_count": 0,
        "coverage_ratio": 0.0,
        "recomputation_fail_count": 0,
        "max_relative_error": 0.0,
        "mean_relative_error": 0.0,
        "scale_mismatch_count": 0,
        "period_mismatch_count": 0,
        "ambiguity_count": 0,
        "schema_version": 2,
        "pnl_table_detected": 0,
        "pnl_identity_fail_count": 0,
        "pnl_margin_fail_count": 0,
        "pnl_missing_baseline_count": 0,
        "pnl_period_strict_mismatch_count": 0,
    }
    _empty_audit_summary = {
        "total_claims": 0,
        "supported_claims": 0,
        "value_error_claims": 0,
        "ungrounded_claims": 0,
        "violation_claims": 0,
        "repaired_claims": 0,
        "coverage_ratio": 0.0,
        "pipeline_passes": 0,
        "repair_applied": False,
        "overall_risk": "low",
    }
    return {
        "decision": decision,
        "rationale": rationale,
        "signals": sig,
        "claims": [],
        "grounding": [],
        "verification": [],
        "report": {},
        "domain": domain,
        "engine_used": engine_used,
        "llm_used": llm_used,
        "llm_fallback_reason": llm_fallback_reason,
        "original_answer": None,
        "corrected_answer": None,
        "repair_iterations": 0,
        "accepted_after_repair": False,
        "claim_audit": [],
        "audit_summary": _empty_audit_summary,
    }


def route_and_verify(
    question: str,
    evidence: Any,
    candidate_answer: str,
    options: Optional[Dict[str, Any]] = None,
    llm_used: bool = False,
    llm_fallback_reason: Optional[str] = None,
    generated_answer: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Single entry for verification. P&L-only: if not table or not P&L -> FLAG.

    Repair-and-reverify loop: when pass 1 returns REPAIR, attempt deterministic
    repair and re-run the full pipeline (pass 2).  Maximum 2 iterations.
      - pass 2 → ACCEPT : final_decision=ACCEPT, accepted_after_repair=True
      - pass 2 → REPAIR/FLAG or no repair possible : final_decision=FLAG

    options keys: tolerance, log_run, enable_repair (default True), disable_lookup,
                  disable_constraints, disable_execution, decision_mode.
    """
    options = options or {}
    tolerance = options.get("tolerance", settings.tolerance)
    log_run_flag = options.get("log_run", True)
    # enable_repair: gates the repair-and-reverify loop (default True).
    # Set to False when running the inner pass so we never nest beyond 2 iterations.
    enable_repair = options.get("enable_repair", True)
    disable_lookup = options.get("disable_lookup", False)
    disable_constraints = options.get("disable_constraints", False)
    disable_execution = options.get("disable_execution", False)
    decision_mode = options.get("decision_mode", None)  # "rules" | "ml" | None

    # ------------------------------------------------------------------
    # Early validation (shared between passes — evidence never changes)
    # ------------------------------------------------------------------
    if _evidence_type(evidence) != "table":
        return _short_circuit_flag(
            "FLAG",
            "P&L verifier requires table evidence.",
            {"table_type": "unknown", "confidence": 0.0},
            "none",
            llm_used=llm_used,
            llm_fallback_reason=llm_fallback_reason,
        )

    content = _evidence_content(evidence)
    domain_ctx = classify_table_type(content)
    if domain_ctx.table_type not in ("pnl", "weak_pnl"):
        return _short_circuit_flag(
            "FLAG",
            "Evidence is not a P&L / Income Statement table.",
            {"table_type": domain_ctx.table_type, "confidence": domain_ctx.confidence},
            "none",
            llm_used=llm_used,
            llm_fallback_reason=llm_fallback_reason,
        )

    pnl_table = parse_pnl_table(content)
    if pnl_table is None:
        return _short_circuit_flag(
            "FLAG",
            "Table layout not supported. P&L requires Layout A (line items + periods) or Layout B (Period, Line Item, Value).",
            {"table_type": "pnl", "confidence": domain_ctx.confidence},
            "none",
            llm_used=llm_used,
            llm_fallback_reason=llm_fallback_reason,
        )

    # Pre-compute shared inputs — same for both passes
    evidence_items = ingest_evidence({"type": "table", "content": content})
    pnl_periods = getattr(pnl_table, "periods", []) or []

    # ------------------------------------------------------------------
    # Inner pipeline closure — runs once per pass for a given answer.
    # Returns None when the answer contains no extractable numeric claims.
    # ------------------------------------------------------------------
    def _run_pass(answer: str) -> Optional[Dict[str, Any]]:
        claims_raw = extract_numeric_claims(answer)
        norm_claims = normalize_claims(
            claims_raw, evidence_content=content, default_tolerance=tolerance
        )
        if not norm_claims:
            return None

        grounding_results = ground_claims(
            norm_claims, evidence_items, tolerance, question=question
        )

        vrs = []
        for claim in norm_claims:
            gm = next((g for g in grounding_results if g.claim == claim), None)
            vr = VerificationResult(
                claim=claim, grounded=gm is not None, grounding_match=gm
            )
            if not disable_lookup:
                vr = verify_lookup(vr, gm, tolerance)
            if not disable_constraints:
                vr = verify_constraints(
                    claim, gm, norm_claims, evidence_items,
                    question=question, pnl_periods=pnl_periods,
                    table_scale=getattr(getattr(pnl_table, 'metadata', None), 'scale_label', None),
                )
            if not disable_execution:
                exec_result = execute_claim_against_table(
                    claim.parsed_value,
                    getattr(claim, "unit_type", "amount") or "amount",
                    question, pnl_table, tolerance,
                    scale_token=getattr(claim, "scale_token", None),
                )
                if exec_result["supported"]:
                    vr.execution_supported = True
                    vr.execution_result = exec_result["computed_value"]
                    vr.execution_confidence = exec_result["confidence"]
                    if not vr.grounded:
                        vr.grounded = True
                else:
                    if exec_result.get("error"):
                        vr.execution_error = exec_result["error"]
                    if exec_result.get("unverifiable_claim"):
                        vr.unverifiable_claim = True
            vrs.append(vr)

        if not disable_execution:
            pnl_check = run_pnl_checks(question, pnl_table, tolerance)
        else:
            pnl_check = PnLCheckResult()

        strict_count = _count_pnl_strict_violations(vrs)
        sigs = compute_signals(
            norm_claims, vrs, tolerance,
            pnl_check_result=pnl_check,
            domain_table_type="pnl",
            pnl_period_strict_mismatch_count=strict_count,
        )

        if decision_mode == "rules":
            from .decision_rules import make_decision
            dec = make_decision(sigs, vrs)
        elif decision_mode == "ml":
            import os
            _orig = os.environ.get("USE_ML_DECIDER")
            os.environ["USE_ML_DECIDER"] = "true"
            dec = decide(sigs, vrs)
            if _orig is None:
                os.environ.pop("USE_ML_DECIDER", None)
            else:
                os.environ["USE_ML_DECIDER"] = _orig
        else:
            dec = decide(sigs, vrs)

        return {
            "decision": dec,
            "signals": sigs,
            "claims": norm_claims,
            "verification": vrs,
            "grounding": grounding_results,
        }

    # ------------------------------------------------------------------
    # Pass 1: verify original candidate answer
    # ------------------------------------------------------------------
    pass1 = _run_pass(candidate_answer)
    if pass1 is None:
        return _short_circuit_flag(
            "FLAG",
            "Candidate answer contains no numeric values; cannot verify.",
            {"table_type": "pnl", "confidence": domain_ctx.confidence},
            "pnl",
            llm_used=llm_used,
            llm_fallback_reason=llm_fallback_reason,
        )

    decision = pass1["decision"]
    signals = pass1["signals"]
    verification_results = pass1["verification"]
    grounding = pass1["grounding"]
    normalized_claims = pass1["claims"]

    # ------------------------------------------------------------------
    # Repair-and-reverify loop (pass 2)
    # Fires when pass 1 → REPAIR.  Maximum 2 total pipeline runs.
    # ------------------------------------------------------------------
    repair_audit: Optional[Dict[str, Any]] = None
    accepted_after_repair = False
    corrected_answer: Optional[str] = None
    repair_iterations = 1

    if enable_repair and decision.decision == "REPAIR":
        repair_iterations = 2

        repair_result = attempt_repair(
            candidate_answer, normalized_claims,
            verification_results, grounding, signals,
            pnl_table=pnl_table, tolerance=tolerance,
        )
        corrected_answer = repair_result.repaired_answer

        pass2 = _run_pass(repair_result.repaired_answer) if repair_result.changed else None

        if pass2 is not None and pass2["decision"].decision == "ACCEPT":
            # Repair succeeded — adopt pass 2 as the authoritative result
            decision = pass2["decision"]
            signals = pass2["signals"]
            verification_results = pass2["verification"]
            grounding = pass2["grounding"]
            normalized_claims = pass2["claims"]
            accepted_after_repair = True
            repair_outcome = "ACCEPTED"
        else:
            # Repair produced no change, or pass 2 still not ACCEPT → escalate
            decision = Decision(
                decision="FLAG",
                rationale=(
                    "Repair attempted but re-verification did not yield ACCEPT. "
                    "Escalated from REPAIR."
                ),
            )
            repair_outcome = "ESCALATED_TO_FLAG"

        repair_audit = {
            "pass_1": {
                "answer": candidate_answer,
                "decision": pass1["decision"].decision,
                "signals": pass1["signals"].to_dict(),
            },
            "pass_2": {
                "answer": repair_result.repaired_answer,
                "decision": pass2["decision"].decision if pass2 else None,
                "signals": pass2["signals"].to_dict() if pass2 else None,
            },
            "repair_applied": [a.to_dict() for a in repair_result.repair_actions],
            "repair_outcome": repair_outcome,
        }

    # ------------------------------------------------------------------
    # Per-claim audit (computed from final pipeline state)
    # ------------------------------------------------------------------
    claim_audit = build_claim_audit(
        normalized_claims, verification_results, tolerance,
        repair_audit=repair_audit, accepted_after_repair=accepted_after_repair,
    )
    audit_summary = build_audit_summary(
        claim_audit, signals.to_dict(), repair_audit, accepted_after_repair,
    )

    # ------------------------------------------------------------------
    # Report generation
    # Use the corrected answer for the report when repair succeeded, so
    # the report reflects the verified (repaired) state.
    # ------------------------------------------------------------------
    report_answer = corrected_answer if accepted_after_repair else candidate_answer
    report = generate_report(
        question=question,
        candidate_answer=report_answer,
        evidence_type="table",
        tolerance=tolerance,
        claims=normalized_claims,
        grounding=grounding,
        verification=verification_results,
        signals=signals,
        decision=decision,
    )

    # ------------------------------------------------------------------
    # Audit logging
    # ------------------------------------------------------------------
    runs_dir = ensure_runs_directory()
    if log_run_flag:
        extra = {
            "domain": {"table_type": "pnl", "confidence": domain_ctx.confidence},
            "engine_used": "pnl",
            "llm_used": llm_used,
            "llm_fallback_reason": llm_fallback_reason,
            "claim_audit": claim_audit,
            "audit_summary": audit_summary,
        }
        if generated_answer is not None:
            extra["generated_answer"] = generated_answer
        if repair_audit is not None:
            extra["repair_audit"] = repair_audit
        log_run(report, runs_dir=runs_dir, extra=extra)
        log_signals(signals, decision.decision, runs_dir=runs_dir)

    # ------------------------------------------------------------------
    # Response
    # ------------------------------------------------------------------
    result = {
        "decision": decision.decision,
        "run_logged": log_run_flag,
        "rationale": decision.rationale,
        "signals": signals.to_dict(),
        "claims": [c.to_dict() for c in normalized_claims],
        "grounding": [g.to_dict() for g in grounding],
        "verification": [v.to_dict() for v in verification_results],
        "report": report.to_dict(),
        "domain": {"table_type": "pnl", "confidence": domain_ctx.confidence},
        "engine_used": "pnl",
        "llm_used": llm_used,
        "llm_fallback_reason": llm_fallback_reason,
        # Repair-loop metadata (always present for consistent API shape)
        "original_answer": candidate_answer,
        "corrected_answer": corrected_answer,
        "repair_iterations": repair_iterations,
        "accepted_after_repair": accepted_after_repair,
        # Per-claim structured audit
        "claim_audit": claim_audit,
        "audit_summary": audit_summary,
    }
    if repair_audit is not None:
        result["repair_audit"] = repair_audit
    return result


def _count_pnl_strict_violations(verification_results):
    from .types import Violation, V_PNL_PERIOD_STRICT, V_MISSING_PERIOD_IN_EVIDENCE
    count = 0
    for r in verification_results:
        for v in (r.constraint_violations or []):
            if isinstance(v, Violation):
                if v.code in (V_PNL_PERIOD_STRICT, V_MISSING_PERIOD_IN_EVIDENCE):
                    count += 1
            elif isinstance(v, str):
                vl = v.lower()
                if "pnl_period_strict_mismatch" in vl or "missing_period_in_evidence" in vl:
                    count += 1
    return count
