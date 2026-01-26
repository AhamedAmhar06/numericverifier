"""LLM provider stubs (OpenAI integration not implemented in baseline)."""
from typing import Optional


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

