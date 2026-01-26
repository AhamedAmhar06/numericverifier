"""Verification endpoint."""
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

router = APIRouter()


class EvidenceRequest(BaseModel):
    type: str  # "text" or "table"
    content: Union[str, Dict[str, Any]]


class VerifyRequest(BaseModel):
    question: str
    evidence: EvidenceRequest
    candidate_answer: str
    options: Optional[Dict[str, Any]] = None


@router.post("/verify-only")
async def verify_only(request: VerifyRequest):
    """
    Run the full verification pipeline on a provided candidate answer.
    """
    # Get options with defaults
    options = request.options or {}
    tolerance = options.get("tolerance", settings.tolerance)
    log_run_flag = options.get("log_run", True)
    
    # Step 1: Extract numeric claims
    claims = extract_numeric_claims(request.candidate_answer)
    
    # Step 2: Normalize claims
    normalized_claims = normalize_claims(claims)
    
    # Step 3: Ingest evidence
    evidence_items = ingest_evidence({
        "type": request.evidence.type,
        "content": request.evidence.content
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
            request.candidate_answer
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
        question=request.question,
        candidate_answer=request.candidate_answer,
        evidence_type=request.evidence.type,
        tolerance=tolerance,
        claims=normalized_claims,
        grounding=grounding,
        verification=verification_results,
        signals=signals,
        decision=decision
    )
    
    # Step 9: Log if requested
    if log_run_flag:
        log_run(report)
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

