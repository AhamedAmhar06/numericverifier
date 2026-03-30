"""Verification endpoint. P&L-only: both endpoints call verifier/router.route_and_verify."""
from pathlib import Path
from typing import Any, Dict, Optional, Union

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from ..core.config import settings
from ..llm.provider import generate_llm_answer
from ..verifier.analyst_rationale import translate_for_analyst
from ..verifier.router import route_and_verify

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _attach_analyst_rationale(result: Dict[str, Any]) -> Dict[str, Any]:
    """Add analyst_rationale to a route_and_verify() result dict."""
    result["analyst_rationale"] = translate_for_analyst(
        signals=result.get("signals") or {},
        claim_audit=result.get("claim_audit") or [],
        decision=result.get("decision"),
        rationale=result.get("rationale"),
        audit_summary=result.get("audit_summary") or {},
        shap_explanation=result.get("shap_explanation"),
    )
    return result


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/verify-only")
async def verify_only(request: VerifyRequest):
    """
    Run P&L verification pipeline on a provided candidate answer.
    Evidence must be type=table and a P&L table; otherwise FLAG.
    """
    options = request.options or {}
    options.setdefault("tolerance", settings.tolerance)
    options.setdefault("log_run", True)
    result = route_and_verify(
        question=request.question,
        evidence=request.evidence,
        candidate_answer=request.candidate_answer,
        options=options,
        llm_used=False,
        llm_fallback_reason=None,
    )
    return _attach_analyst_rationale(result)


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
    # Alias for frontend consistency: candidate_answer = the LLM-generated answer
    result["candidate_answer"] = answer
    return _attach_analyst_rationale(result)


@router.post("/upload-table")
async def upload_table(file: UploadFile = File(...)):
    """Parse an uploaded CSV or Excel file into verifier-compatible table JSON.

    Accepts multipart/form-data with a single ``file`` field.
    Supported formats: .csv, .xlsx, .xls

    Returns:
        {"type": "table", "content": {"caption": "...", "columns": [...], "rows": [...]}}
    """
    filename = file.filename or ""
    ext = Path(filename).suffix.lower()
    if ext not in (".csv", ".xlsx", ".xls"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Upload a .csv, .xlsx, or .xls file.",
        )

    contents = await file.read()

    from ..ingestion.file_parser import parse_file  # noqa: PLC0415

    try:
        return parse_file(contents, filename=filename)
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
