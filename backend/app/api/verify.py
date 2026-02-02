"""Verification endpoint.

Flow: Question + Evidence → [LLM] candidate answer → extract claims → ground →
verify (lookup, execution, constraints) → signals → decision → report + logs.
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, Dict, Any, Union
from ..verifier.extract import extract_numeric_claims
from ..verifier.normalize import normalize_claims
from ..verifier.evidence import ingest_evidence
from ..verifier.grounding import ground_claims
from ..verifier.engines.lookup import verify_lookup
from ..verifier.engines.execution import verify_execution
from ..verifier.engines.constraints import verify_constraints
from ..verifier.signals import compute_signals
from ..verifier.decision_rules import make_decision
from ..verifier.report import generate_report
from ..verifier.types import VerificationResult
from ..eval.logging import log_run, log_signals
from ..core.config import settings
from ..llm.provider import generate_llm_answer

router = APIRouter()


class EvidenceRequest(BaseModel):
    type: str  # "text" or "table"
    content: Union[str, Dict[str, Any]]


class VerifyRequest(BaseModel):
    question: str
    evidence: EvidenceRequest
    candidate_answer: str
    options: Optional[Dict[str, Any]] = None


class VerifyWithLLMRequest(BaseModel):
    question: str
    evidence: EvidenceRequest
    options: Optional[Dict[str, Any]] = None


# Keywords that indicate the question expects an arithmetic/numeric answer
_ARITHMETIC_QUESTION_KEYWORDS = (
    "percent", "percentage", "change", "increase", "decrease", "growth", "decline",
    "total", "sum", "revenue", "ratio", "how much", "how many",
)


def _is_arithmetic_question(question: str) -> bool:
    """True if question likely expects a numeric/arithmetic answer."""
    q = question.lower()
    return any(kw in q for kw in _ARITHMETIC_QUESTION_KEYWORDS)


def _has_percent_claim(claims: list) -> bool:
    """True if any claim is a percentage."""
    return any(getattr(c, "unit", None) == "percent" for c in claims)


def validate_candidate_answer(
    question: str,
    candidate_answer: str,
) -> Optional[Dict[str, Any]]:
    """
    Input validation before verification.
    If candidate has no numeric values, or arithmetic question with no arithmetic claim,
    return a short-circuit response (FLAG). Otherwise return None (proceed with verification).
    """
    claims = extract_numeric_claims(candidate_answer)
    normalized = normalize_claims(claims)

    # No numeric values at all → FLAG
    if not normalized:
        return {
            "decision": "FLAG",
            "rationale": "Candidate answer contains no numeric values; cannot verify.",
            "signals": {
                "unsupported_claims_count": 0,
                "coverage_ratio": 0.0,
                "recomputation_fail_count": 0,
                "max_relative_error": 0.0,
                "mean_relative_error": 0.0,
                "scale_mismatch_count": 0,
                "period_mismatch_count": 0,
                "ambiguity_count": 0,
            },
            "claims": [],
            "grounding": [],
            "verification": [],
            "report": {
                "candidate_answer": candidate_answer,
                "question": question,
                "validation_short_circuit": True,
            },
        }
    # Arithmetic question but no percentage claim when question asks for percent
    if _is_arithmetic_question(question) and "percent" in question.lower():
        if not _has_percent_claim(normalized):
            return {
                "decision": "FLAG",
                "rationale": "Question asks for a percentage but answer contains no percentage value.",
                "signals": {
                    "unsupported_claims_count": len(normalized),
                    "coverage_ratio": 0.0,
                    "recomputation_fail_count": 0,
                    "max_relative_error": 0.0,
                    "mean_relative_error": 0.0,
                    "scale_mismatch_count": 0,
                    "period_mismatch_count": 0,
                    "ambiguity_count": 0,
                },
                "claims": [c.to_dict() for c in normalized],
                "grounding": [],
                "verification": [],
                "report": {
                    "candidate_answer": candidate_answer,
                    "question": question,
                    "validation_short_circuit": True,
                },
            }
    return None


def run_verification_pipeline(
    question: str,
    candidate_answer: str,
    evidence: EvidenceRequest,
    tolerance: float,
    log_run_flag: bool = True,
    generated_answer: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run the full verification pipeline on a candidate answer.
    Reused by both /verify-only and /verify endpoints.
    """
    # Input validation: no numerics or missing arithmetic claim → FLAG (no verifier change)
    short_circuit = validate_candidate_answer(question, candidate_answer)
    if short_circuit is not None:
        return short_circuit

    # Step 1: Extract numeric claims
    claims = extract_numeric_claims(candidate_answer)
    
    # Step 2: Normalize claims
    normalized_claims = normalize_claims(claims)
    
    # Step 3: Ingest evidence
    evidence_items = ingest_evidence({
        "type": evidence.type,
        "content": evidence.content
    })
    
    # Step 4: Ground claims to evidence
    grounding = ground_claims(normalized_claims, evidence_items, tolerance)
    
    # Step 5: Run verification engines
    verification_results = []
    for claim in normalized_claims:
        # Find grounding match for this claim
        grounding_match = None
        for g in grounding:
            if g.claim == claim:
                grounding_match = g
                break
        
        # Create verification result
        verification_result = VerificationResult(
            claim=claim,
            grounded=grounding_match is not None,
            grounding_match=grounding_match
        )
        
        # Run lookup engine
        verification_result = verify_lookup(verification_result, grounding_match, tolerance)
        
        # Run execution engine
        execution_result = verify_execution(
            claim,
            grounding_match,
            normalized_claims,
            evidence_items,
            candidate_answer
        )
        verification_result.execution_supported = execution_result.execution_supported
        verification_result.execution_result = execution_result.execution_result
        verification_result.execution_error = execution_result.execution_error
        
        # Run constraint engine
        constraint_result = verify_constraints(
            claim,
            grounding_match,
            normalized_claims,
            evidence_items
        )
        verification_result.constraint_violations = constraint_result.constraint_violations
        
        verification_results.append(verification_result)
    
    # Step 6: Compute signals
    signals = compute_signals(normalized_claims, verification_results, tolerance)
    
    # Step 7: Make decision
    decision = make_decision(signals, verification_results)
    
    # Step 8: Generate report
    report = generate_report(
        question=question,
        candidate_answer=candidate_answer,
        evidence_type=evidence.type,
        tolerance=tolerance,
        claims=normalized_claims,
        grounding=grounding,
        verification=verification_results,
        signals=signals,
        decision=decision
    )
    
    # Step 9: Log if requested (question, evidence type, candidate_answer, claims, verification, signals, decision)
    if log_run_flag:
        extra = {"generated_answer": generated_answer} if generated_answer else None
        log_run(report, extra=extra)
        log_signals(signals, decision.decision)
    
    # Return response
    return {
        "decision": decision.decision,
        "rationale": decision.rationale,
        "signals": signals.to_dict(),
        "claims": [c.to_dict() for c in normalized_claims],
        "grounding": [g.to_dict() for g in grounding],
        "verification": [v.to_dict() for v in verification_results],
        "report": report.to_dict()
    }


@router.post("/verify-only")
async def verify_only(request: VerifyRequest):
    """
    Run the full verification pipeline on a provided candidate answer.
    """
    # Get options with defaults
    options = request.options or {}
    tolerance = options.get("tolerance", settings.tolerance)
    log_run_flag = options.get("log_run", True)
    
    return run_verification_pipeline(
        question=request.question,
        candidate_answer=request.candidate_answer,
        evidence=request.evidence,
        tolerance=tolerance,
        log_run_flag=log_run_flag
    )


@router.post("/verify")
async def verify_with_llm(request: VerifyWithLLMRequest):
    """
    Generate answer using LLM and run verification pipeline.
    
    Accepts question + evidence (no candidate_answer).
    LLM generates the answer, which is then verified.
    """
    # Validate that evidence is table type (as per spec)
    if request.evidence.type != "table":
        return {
            "error": "Only table evidence is supported for LLM answer generation"
        }
    
    # Get options with defaults
    options = request.options or {}
    tolerance = options.get("tolerance", settings.tolerance)
    log_run_flag = options.get("log_run", True)
    
    # Step 1: Generate answer using LLM
    table_content = request.evidence.content
    if not isinstance(table_content, dict):
        return {
            "error": "Table evidence content must be a dictionary with 'columns', 'rows', and 'units'"
        }
    
    candidate_answer = generate_llm_answer(request.question, table_content)
    
    # Step 2: Run verification pipeline with generated answer; pass generated_answer for logging
    result = run_verification_pipeline(
        question=request.question,
        candidate_answer=candidate_answer,
        evidence=request.evidence,
        tolerance=tolerance,
        log_run_flag=log_run_flag,
        generated_answer=candidate_answer,
    )
    
    # Add generated answer to response
    result["generated_answer"] = candidate_answer
    
    return result

