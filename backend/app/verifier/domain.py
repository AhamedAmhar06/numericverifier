"""P&L domain classification (gate). Deterministic; no LLM."""
from dataclasses import dataclass
from typing import Dict, Any, List

# Canonical P&L line-item terms (lowercase). Prefer false-negative over false-positive.
_PNL_TERMS = [
    "revenue", "sales", "turnover", "total revenue",
    "cogs", "cost of sales", "cost of revenue", "cost of goods sold",
    "gross profit", "gross income",
    "operating expenses", "opex", "sg&a", "selling general administrative",
    "operating income", "operating profit", "ebit",
    "tax", "taxes", "income tax",
    "interest", "interest expense",
    "net income", "net profit", "profit after tax", "profit",
]

# Minimum fraction of distinct P&L terms found in table to classify as pnl (conservative).
_MIN_CONFIDENCE = 0.25
# Minimum absolute count of matched terms.
_MIN_MATCH_COUNT = 2


@dataclass
class DomainContext:
    """Result of table-type classification."""
    table_type: str  # "pnl" | "unknown"
    confidence: float
    matched_terms: List[str]


def _normalize_label(s: str) -> str:
    """Lowercase, strip punctuation, collapse spaces."""
    if not isinstance(s, str):
        return ""
    s = s.lower().strip()
    for c in ".,;&-":
        s = s.replace(c, " ")
    return " ".join(s.split())


def _extract_labels_from_table(content: Dict[str, Any]) -> List[str]:
    """Extract all text labels from table (row labels or column headers) for scanning."""
    labels = []
    columns = content.get("columns", [])
    rows = content.get("rows", [])
    if not columns or not rows:
        return labels
    # Layout A: first column = line items
    first_col_idx = 0
    for row in rows:
        if isinstance(row, (list, tuple)) and len(row) > first_col_idx:
            cell = row[first_col_idx]
            if isinstance(cell, str):
                labels.append(_normalize_label(cell))
    for col in columns:
        if isinstance(col, str):
            labels.append(_normalize_label(col))
    # Layout B: columns might be ["Period", "Line Item", "Value"] -> second column = line items
    if len(columns) >= 2:
        col1 = (columns[1] or "").lower()
        if "line" in col1 or "item" in col1:
            for row in rows:
                if isinstance(row, (list, tuple)) and len(row) >= 2:
                    cell = row[1]
                    if isinstance(cell, str):
                        labels.append(_normalize_label(cell))
    return labels


def classify_table_type(evidence_table: Dict[str, Any]) -> DomainContext:
    """
    Classify table as P&L or unknown. Conservative: prefer unknown over false pnl.
    evidence_table: raw content dict with "columns", "rows" (and optionally "units").
    """
    labels = _extract_labels_from_table(evidence_table)
    if not labels:
        return DomainContext(table_type="unknown", confidence=0.0, matched_terms=[])
    seen = set()
    matched = []
    for label in labels:
        if len(label) < 3:
            continue
        for term in _PNL_TERMS:
            if len(term) < 3:
                continue
            if term in label or label in term:
                if term not in seen:
                    seen.add(term)
                    matched.append(term)
                break
    # Confidence = fraction of unique labels that matched a P&L term (capped by diversity)
    unique_labels = set(labels)
    if not unique_labels:
        confidence = 0.0
    else:
        match_ratio = len(matched) / max(len(unique_labels), 1)
        confidence = min(1.0, match_ratio)
    if len(matched) < _MIN_MATCH_COUNT or confidence < _MIN_CONFIDENCE:
        return DomainContext(table_type="unknown", confidence=confidence, matched_terms=matched)
    return DomainContext(table_type="pnl", confidence=confidence, matched_terms=matched)
