"""LLM fallback verification for UNVERIFIABLE derived claims.

Tier 3 of the three-tier verification architecture:
  Tier 1: Symbolic constraints (deterministic)
  Tier 2: ML disambiguation (probabilistic)
  Tier 3: LLM fallback (targeted, for derived claims the formula library cannot check)

Called ONLY when the symbolic+ML pipeline returned UNVERIFIABLE.
Falls back gracefully to None if provider is unavailable or uncertain.
"""
from __future__ import annotations

import json
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a financial fact-checker.
You are given a financial data table, a question, and a
candidate answer. Determine if the answer is numerically
consistent with the table.

Rules:
- Use ONLY data from the provided table. No external knowledge.
- If the answer states a value directly from the table, check
  the match. Rounding differences under 2% are acceptable.
- If the answer requires computation (percentage change,
  difference, average), compute the correct value from the
  table yourself first, then compare to the candidate answer.
- Respond with EXACTLY one word:
  YES              — you are fully confident the answer is correct
  NO               — you are fully confident there is a clear
                     numeric error (not rounding, a real mistake)
  CANNOT_DETERMINE — you are not certain, or the computation
                     is complex, or data is insufficient

CRITICAL: Default to CANNOT_DETERMINE when in doubt.
Only answer NO for obvious significant errors.
Rounding and approximation are NOT errors."""

_USER_TEMPLATE = """Table:
{table_json}

Question: {question}

Candidate answer: {candidate_answer}

If computation is needed, compute the correct value from
the table first, then compare.
Answer with one word only: YES, NO, or CANNOT_DETERMINE"""


def llm_verify_fallback(
    question: str,
    table_content: dict,
    candidate_answer: str,
    llm_caller: Callable,
) -> Optional[str]:
    """
    Verify a candidate answer using LLM when symbolic
    verification returned UNVERIFIABLE.

    Args:
        question: The financial question asked.
        table_content: Raw table dict (columns + rows).
        candidate_answer: The answer to verify.
        llm_caller: Callable(prompt, system_prompt=None) -> str | None.

    Returns:
        "ACCEPT" if LLM confirms numeric consistency
        "FLAG"   if LLM detects numeric error
        None     if LLM unavailable or cannot determine

    Called ONLY when symbolic verifier returned UNVERIFIABLE.
    Falls back to None gracefully if provider unavailable.
    """
    try:
        table_str = json.dumps(table_content, indent=2)
        if len(table_str) > 3000:
            table_str = table_str[:3000] + "\n...[truncated]"

        user_prompt = _USER_TEMPLATE.format(
            table_json=table_str,
            question=question,
            candidate_answer=candidate_answer,
        )

        response = llm_caller(user_prompt, system_prompt=_SYSTEM_PROMPT)

        if response is None:
            return None

        verdict = response.strip().upper().split()[0]
        if verdict == "YES":
            return "ACCEPT"
        elif verdict == "NO":
            return "FLAG"
        return None  # CANNOT_DETERMINE or unexpected response

    except Exception as e:
        logger.debug("LLM fallback failed silently: %s", e)
        return None


def make_llm_caller() -> Optional[Callable]:
    """
    Build an LLM caller using the OpenAI provider.
    Returns None if provider is unavailable (key missing, etc.).
    The returned callable signature: (prompt, system_prompt=None) -> str | None.
    """
    try:
        from ..llm.provider import get_openai_api_key
        from openai import OpenAI

        api_key = get_openai_api_key()
        if not api_key:
            return None

        client = OpenAI(api_key=api_key)

        def _caller(prompt: str, system_prompt: Optional[str] = None) -> Optional[str]:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            try:
                resp = client.chat.completions.create(
                    model="gpt-4o-mini",
                    temperature=0.0,
                    max_tokens=10,  # one word only
                    messages=messages,
                )
                return resp.choices[0].message.content.strip()
            except Exception as e:
                logger.debug("LLM fallback call failed: %s", e)
                return None

        return _caller

    except Exception as e:
        logger.debug("make_llm_caller failed: %s", e)
        return None
