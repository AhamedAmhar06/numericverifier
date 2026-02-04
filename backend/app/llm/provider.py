"""LLM provider for answer generation."""
import os
import logging
from typing import Dict, Any, Optional

from openai import OpenAI

from ..core.config import settings

logger = logging.getLogger(__name__)


def _normalize_api_key(raw: str) -> str:
    """Strip whitespace, newlines, carriage returns, surrounding quotes."""
    if not raw or not isinstance(raw, str):
        return ""
    key = raw.strip().strip('"').strip("'")
    key = key.replace("\n", "").replace("\r", "").strip()
    if key and " " in key:
        key = key.split()[0].strip()
    return key


def get_openai_api_key() -> Optional[str]:
    """
    Return OPENAI_API_KEY from os.environ (set by config from backend/.env) or settings.
    Normalized: strip whitespace, newlines, quotes. Never returns placeholder.
    """
    raw = os.getenv("OPENAI_API_KEY") or settings.openai_api_key or ""
    key = _normalize_api_key(raw)
    if not key:
        return None
    if key.lower() in ("your-key-here", "sk-your-key-here", ""):
        return None
    if key.startswith("sk-") and len(key) < 30:
        return None
    return key


def get_llm_mode() -> str:
    """Return 'LLM' if OpenAI key is set, else 'stub'. Used for startup logging."""
    return "LLM" if get_openai_api_key() else "stub"


def get_openai_api_key_diagnostics() -> dict:
    """Safe diagnostics for startup: present, length. No key value, no stub_reason."""
    key = get_openai_api_key()
    return {"key_present": bool(key), "key_len": len(key) if key else 0}


def format_table_for_prompt(table_content: Dict[str, Any]) -> str:
    """
    Format table content for LLM prompt.
    
    Args:
        table_content: Dictionary with 'columns', 'rows', and 'units' keys
        
    Returns:
        Formatted table string
    """
    columns = table_content.get("columns", [])
    rows = table_content.get("rows", [])
    units = table_content.get("units", {})
    
    # Build header with units if available
    header_parts = []
    for col in columns:
        if col in units:
            header_parts.append(f"{col} ({units[col]})")
        else:
            header_parts.append(col)
    
    header = " | ".join(header_parts)
    separator = "-" * len(header)
    
    # Build rows
    formatted_rows = [header, separator]
    for row in rows:
        formatted_row = " | ".join(str(cell) for cell in row)
        formatted_rows.append(formatted_row)
    
    return "\n".join(formatted_rows)


def generate_llm_answer(question: str, table_evidence: Dict[str, Any]) -> tuple:
    """
    Generate answer using LLM from question and table evidence.
    Uses OPENAI_API_KEY from environment only (no hardcoded keys).
    On 429/quota/network failure: log warning, return stub and (llm_used=False, fallback_reason set).

    Returns:
        (answer: str, llm_used: bool, llm_fallback_reason: Optional[str])
    """
    stub_answer = f"Based on the provided table, the answer to '{question}' requires analysis of the data."
    api_key = get_openai_api_key()

    if not api_key:
        logger.info("LLM stub selected: OPENAI_API_KEY not loaded.")
        return (stub_answer, False, "OPENAI_API_KEY not set")

    formatted_table = format_table_for_prompt(table_evidence)
    system_prompt = """You are a financial assistant.

You MUST compute the numeric answer using the provided table.

You must compute the numeric answer.
If the question asks for a percentage, your answer must contain a percentage value (e.g., 50%).

Your answer MUST contain the final numeric value explicitly.
Do NOT give vague answers or prose without numbers."""

    user_prompt = f"""Question:
{question}

Table:
{formatted_table}

Instructions:
- Perform any required calculation.
- Return ONE sentence.
- Include the numeric result explicitly."""

    try:
        logger.info("OpenAI client constructed (LLM mode).")
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.0,
            max_tokens=100,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        answer = response.choices[0].message.content.strip()
        return (answer, True, None)
    except ImportError:
        logger.warning("LLM fallback: openai package not installed.")
        return (stub_answer, False, "openai package not installed")
    except Exception as e:
        reason = str(e)
        is_401 = "401" in reason or "invalid_api_key" in reason.lower() or "invalid" in reason.lower() and "auth" in reason.lower()
        if is_401:
            logger.error(
                "OpenAI returned 401/invalid_api_key but OPENAI_API_KEY was loaded (len=%s). Key may be revoked or wrong. Fix backend/.env and restart.",
                len(api_key),
            )
            return (stub_answer, False, "OpenAI authentication failed. Check OPENAI_API_KEY in backend/.env (no quotes, no trailing space).")
        logger.warning("LLM stub selected: OpenAI request failed: %s", reason)
        if "429" in reason or "quota" in reason.lower() or "insufficient_quota" in reason.lower():
            return (stub_answer, False, "OpenAI rate limit or quota exceeded.")
        return (stub_answer, False, reason)


def generate_answer(question: str, evidence: dict) -> str:
    """
    Generate answer using LLM (stub only).
    
    This is a placeholder for future OpenAI integration.
    No OpenAI calls in baseline.
    """
    raise NotImplementedError("LLM integration not implemented in baseline")


def repair_answer(original_answer: str, verification_results: dict) -> str:
    """
    Repair answer based on verification results (stub only).
    
    This is a placeholder for future OpenAI integration.
    No OpenAI calls in baseline.
    """
    raise NotImplementedError("LLM integration not implemented in baseline")

