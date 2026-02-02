"""LLM provider for answer generation."""
import os
import logging
from typing import Dict, Any, Optional

from openai import OpenAI

from ..core.config import settings

logger = logging.getLogger(__name__)


def get_openai_api_key() -> Optional[str]:
    """Read OPENAI_API_KEY from environment (os.getenv) or from settings (.env)."""
    return os.getenv("OPENAI_API_KEY") or settings.openai_api_key


def get_llm_mode() -> str:
    """Return 'LLM' if OpenAI key is set, else 'stub'. Used for startup logging."""
    return "LLM" if get_openai_api_key() else "stub"


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


def generate_llm_answer(question: str, table_evidence: Dict[str, Any]) -> str:
    """
    Generate answer using LLM from question and table evidence.
    
    Uses OpenAI API if OPENAI_API_KEY is set, otherwise uses stub mode.
    
    Args:
        question: The question to answer
        table_evidence: Table evidence dictionary with 'columns', 'rows', 'units'
        
    Returns:
        Generated answer string
    """
    api_key = get_openai_api_key()

    # Stub mode if API key is not set (LLM integration optional)
    if not api_key:
        # Deterministic stub answer based on question
        # This is a simple stub that returns a placeholder answer
        return f"Based on the provided table, the answer to '{question}' requires analysis of the data."
    
    # Format table for prompt
    formatted_table = format_table_for_prompt(table_evidence)
    
    # System prompt: enforce explicit numeric output
    system_prompt = """You are a financial assistant.

You MUST compute the numeric answer using the provided table.

You must compute the numeric answer.
If the question asks for a percentage, your answer must contain a percentage value (e.g., 50%).

Your answer MUST contain the final numeric value explicitly.
Do NOT give vague answers or prose without numbers."""
    
    # User prompt
    user_prompt = f"""Question:
{question}

Table:
{formatted_table}

Instructions:
- Perform any required calculation.
- Return ONE sentence.
- Include the numeric result explicitly."""
    
    try:
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
        return answer
        
    except ImportError:
        # Fallback to stub if openai package is not installed
        return f"Based on the provided table, the answer to '{question}' requires analysis of the data."
    except Exception as e:
        # Fail gracefully: log and fallback to stub
        logger.warning("OpenAI unavailable: %s. Using stub answer.", e)
        return f"Based on the provided table, the answer to '{question}' requires analysis of the data."


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

