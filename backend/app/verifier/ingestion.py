"""
LLM-assisted ingestion layer for P&L table row label normalization.

Two modes:
- rule_based: fast path using existing synonym coverage
- llm_assisted: LLM suggests canonical mappings for unmatched rows when confidence is low

This layer runs before pnl_parser.py and returns metadata about how well the
table row labels map to canonical P&L line items. It does NOT alter the table.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# Import synonym map from pnl_parser (single source of truth)
from .pnl_parser import _SYNONYMS

# Canonical keys the LLM is asked to map to
_CANONICAL_KEYS = list(_SYNONYMS.keys()) + ["unknown"]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_label(label: str) -> str:
    """Lower-case, strip punctuation/whitespace, collapse spaces."""
    s = re.sub(r"[^\w\s]", " ", str(label).lower())
    return " ".join(s.split())


def _match_canonical(label: str) -> Optional[str]:
    """Return canonical key if label matches a synonym (rule-based)."""
    norm = _normalize_label(label)
    if not norm:
        return None
    # Pass 1: exact match
    for canonical, synonyms in _SYNONYMS.items():
        for syn in synonyms:
            if syn == norm:
                return canonical
    # Pass 2: longest substring match
    best_canonical: Optional[str] = None
    best_len = 0
    for canonical, synonyms in _SYNONYMS.items():
        for syn in synonyms:
            if syn in norm and len(syn) > best_len:
                best_canonical = canonical
                best_len = len(syn)
    return best_canonical


def _extract_row_labels(table_dict: Dict[str, Any]) -> List[str]:
    """Extract the first column (row labels) from a table dict."""
    rows = table_dict.get("rows", [])
    labels: List[str] = []
    for row in rows:
        if isinstance(row, (list, tuple)) and len(row) > 0:
            cell = row[0]
            label = str(cell).strip() if cell is not None else ""
            if label:
                labels.append(label)
    return labels


def _call_llm_for_mappings(
    unmatched_labels: List[str],
) -> Dict[str, str]:
    """
    Call OpenAI (if available) to map unmatched row labels to canonical P&L keys.

    Returns a dict: {raw_label: canonical_key}
    Returns empty dict if LLM is unavailable or fails.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        logger.debug("ingestion: no OPENAI_API_KEY, skipping LLM mapping")
        return {}

    try:
        import openai  # type: ignore
    except ImportError:
        logger.debug("ingestion: openai package not installed, skipping LLM mapping")
        return {}

    canonical_list = ", ".join(c for c in _CANONICAL_KEYS if c != "unknown")
    prompt = (
        "You are a financial data expert. Map each P&L row label below to the most "
        "appropriate canonical category. Respond with valid JSON only — a single object "
        "where each key is the original label and the value is one of: "
        f"{canonical_list}, or 'unknown'.\n\n"
        "Row labels to map:\n"
        + "\n".join(f"- {label}" for label in unmatched_labels)
        + "\n\nJSON response:"
    )

    try:
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=256,
            temperature=0,
        )
        raw = response.choices[0].message.content or ""
        # Extract JSON object from response
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if json_match:
            suggestions = json.loads(json_match.group())
            # Validate: only allow known canonical keys
            validated: Dict[str, str] = {}
            for label, canonical in suggestions.items():
                if canonical in _CANONICAL_KEYS:
                    validated[label] = canonical
            return validated
    except Exception as exc:  # noqa: BLE001
        logger.warning("ingestion: LLM call failed: %s", exc)

    return {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def assess_ingestion(
    table_dict: Dict[str, Any],
    llm_available: Optional[bool] = None,
    confidence_threshold: float = 0.5,
) -> Dict[str, Any]:
    """
    Assess P&L ingestion confidence for a table dict.

    Parameters
    ----------
    table_dict : dict
        Table with 'columns' and 'rows' keys.
    llm_available : bool or None
        If True, attempt LLM-assisted mapping when coverage is below threshold.
        If None (default), auto-detect from OPENAI_API_KEY environment variable.
        If False, disable LLM even if OPENAI_API_KEY is set.
    confidence_threshold : float
        Coverage fraction below which LLM is triggered (if available).

    Returns
    -------
    dict with keys:
        mode          : "rule_based" | "llm_assisted"
        coverage      : float (0-1)
        matched_rows  : list of labels that matched canonical items
        unmapped_rows : list of labels that didn't match
        llm_suggestions : dict {raw_label: canonical_key} (empty if rule_based)
        confidence    : float (overall confidence 0-1)
    """
    # Auto-detect LLM availability only when not explicitly specified
    if llm_available is None:
        llm_available = bool(os.environ.get("OPENAI_API_KEY", "").strip())

    labels = _extract_row_labels(table_dict)

    if not labels:
        return {
            "mode": "rule_based",
            "coverage": 0.0,
            "matched_rows": [],
            "unmapped_rows": [],
            "llm_suggestions": {},
            "confidence": 0.0,
        }

    matched: List[str] = []
    unmatched: List[str] = []

    for label in labels:
        if _match_canonical(label) is not None:
            matched.append(label)
        else:
            unmatched.append(label)

    coverage = len(matched) / len(labels)
    llm_suggestions: Dict[str, str] = {}
    mode = "rule_based"

    # Attempt LLM-assisted mapping for unmatched rows if coverage is low
    if llm_available and unmatched and coverage < confidence_threshold:
        llm_suggestions = _call_llm_for_mappings(unmatched)
        if llm_suggestions:
            mode = "llm_assisted"
            # Re-compute coverage including LLM suggestions
            newly_matched = [
                label for label in unmatched
                if label in llm_suggestions and llm_suggestions[label] != "unknown"
            ]
            effective_matched = len(matched) + len(newly_matched)
            coverage = effective_matched / len(labels)

    # Confidence: blend coverage with a penalty for unmatched rows
    remaining_unmatched = len(unmatched) - sum(
        1 for label in unmatched
        if label in llm_suggestions and llm_suggestions[label] != "unknown"
    )
    unmatched_penalty = 0.1 * remaining_unmatched / len(labels)
    confidence = max(0.0, min(1.0, coverage - unmatched_penalty))

    return {
        "mode": mode,
        "coverage": round(coverage, 4),
        "matched_rows": matched,
        "unmapped_rows": unmatched,
        "llm_suggestions": llm_suggestions,
        "confidence": round(confidence, 4),
    }
