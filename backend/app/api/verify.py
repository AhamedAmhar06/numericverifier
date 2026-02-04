"""Verification endpoint. P&L-only: both endpoints call verifier/router.route_and_verify."""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, Dict, Any, Union

from ..verifier.router import route_and_verify
from ..core.config import settings
from ..llm.provider import generate_llm_answer

router = APIRouter()


class EvidenceRequest(BaseModel):
    type: str  # "text" or "table" — P&L verifier requires "table"
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

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "question": "What was revenue in 2022?",
                    "evidence": {
                        "type": "table",
                        "content": {
                            "columns": ["Line Item", "2022", "2023"],
                            "rows": [["Revenue", "100", "120"], ["COGS", "40", "50"]],
                            "units": {},
                        },
                    },
                    "options": {"tolerance": 0.01, "log_run": True},
                }
            ]
        }
    }


@router.post("/verify-only")
async def verify_only(request: VerifyRequest):
    """
    Run P&L verification pipeline on a provided candidate answer.
    Evidence must be type=table and a P&L table; otherwise FLAG.
    """
    options = request.options or {}
    options.setdefault("tolerance", settings.tolerance)
    options.setdefault("log_run", True)
    return route_and_verify(
        question=request.question,
        evidence=request.evidence,
        candidate_answer=request.candidate_answer,
        options=options,
        llm_used=False,
        llm_fallback_reason=None,
    )


@router.post("/verify")
async def verify_with_llm(request: VerifyWithLLMRequest):
    """
    Generate answer using LLM (or stub on quota/network failure), then run P&L verification.
    Evidence must be type=table. Response includes llm_used and llm_fallback_reason.
    """
    if request.evidence.type != "table":
        return {
            "error": "P&L verifier requires table evidence.",
            "decision": "FLAG",
            "rationale": "P&L verifier requires table evidence.",
        }
    table_content = request.evidence.content
    if not isinstance(table_content, dict):
        return {
            "error": "Table evidence content must be a dictionary with 'columns', 'rows', and 'units'.",
        }

    answer, llm_used, llm_fallback_reason = generate_llm_answer(request.question, table_content)

    options = request.options or {}
    options.setdefault("tolerance", settings.tolerance)
    # Always log /verify (LLM) runs so signals_v2.csv gets every call from Swagger/API.
    options["log_run"] = True
    result = route_and_verify(
        question=request.question,
        evidence=request.evidence,
        candidate_answer=answer,
        options=options,
        llm_used=llm_used,
        llm_fallback_reason=llm_fallback_reason,
        generated_answer=answer,
    )
    result["generated_answer"] = answer
    return result
