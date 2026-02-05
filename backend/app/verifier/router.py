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
from .engines.pnl_execution import run_pnl_checks
from .signals import compute_signals
from ..ml.decision_model import decide
from .report import generate_report
from .types import VerificationResult
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
    options: tolerance, log_run.
    """
    options = options or {}
    tolerance = options.get("tolerance", settings.tolerance)
    log_run_flag = options.get("log_run", True)

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
    if domain_ctx.table_type != "pnl":
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

    # Input validation: no numerics -> FLAG
    claims_raw = extract_numeric_claims(candidate_answer)
    normalized_claims = normalize_claims(claims_raw)
    if not normalized_claims:
        return _short_circuit_flag(
            "FLAG",
            "Candidate answer contains no numeric values; cannot verify.",
            {"table_type": "pnl", "confidence": domain_ctx.confidence},
            "pnl",
            llm_used=llm_used,
            llm_fallback_reason=llm_fallback_reason,
        )

    evidence_items = ingest_evidence({"type": "table", "content": content})
    grounding = ground_claims(normalized_claims, evidence_items, tolerance)
    pnl_periods = getattr(pnl_table, "periods", []) or []

    verification_results = []
    for claim in normalized_claims:
        grounding_match = None
        for g in grounding:
            if g.claim == claim:
                grounding_match = g
                break
        vr = VerificationResult(claim=claim, grounded=grounding_match is not None, grounding_match=grounding_match)
        vr = verify_lookup(vr, grounding_match, tolerance)
        vr = verify_constraints(
            claim,
            grounding_match,
            normalized_claims,
            evidence_items,
            question=question,
            pnl_periods=pnl_periods,
        )
        verification_results.append(vr)

    pnl_check = run_pnl_checks(question, pnl_table, tolerance, margin_asked_or_claimed=False)
    pnl_strict_count = sum(
        1
        for r in verification_results
        for v in (r.constraint_violations or [])
        if "pnl_period_strict_mismatch" in v.lower() or "missing_period_in_evidence" in v.lower()
    )

    signals = compute_signals(
        normalized_claims,
        verification_results,
        tolerance,
        pnl_check_result=pnl_check,
        domain_table_type="pnl",
        pnl_period_strict_mismatch_count=pnl_strict_count,
    )
    decision = decide(signals, verification_results)
    report = generate_report(
        question=question,
        candidate_answer=candidate_answer,
        evidence_type="table",
        tolerance=tolerance,
        claims=normalized_claims,
        grounding=grounding,
        verification=verification_results,
        signals=signals,
        decision=decision,
    )

    runs_dir = ensure_runs_directory()
    signals_path = runs_dir / "signals_v2.csv"
    logger.debug(
        "log_run_flag=%s, signals_path=%s",
        log_run_flag,
        signals_path.resolve(),
    )
    if log_run_flag:
        extra = {
            "domain": {"table_type": "pnl", "confidence": domain_ctx.confidence},
            "engine_used": "pnl",
            "llm_used": llm_used,
            "llm_fallback_reason": llm_fallback_reason,
        }
        if generated_answer is not None:
            extra["generated_answer"] = generated_answer
        log_run(report, runs_dir=runs_dir, extra=extra)
        log_signals(signals, decision.decision, runs_dir=runs_dir)
    else:
        logger.warning("Logging skipped: log_run=false. No row appended to runs/signals_v2.csv.")

    return {
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
    }
