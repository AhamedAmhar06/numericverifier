"""P&L table parsing: Layout A/B, synonym mapping to canonical line items."""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from .normalize import normalize_cell_text

# Canonical keys and their synonym lists (lowercase, normalized)
_SYNONYMS: Dict[str, List[str]] = {
    "revenue": ["revenue", "sales", "turnover", "total revenue"],
    "cogs": ["cogs", "cost of sales", "cost of revenue", "cost of goods sold"],
    "gross_profit": ["gross profit", "gross income"],
    "operating_expenses": ["operating expenses", "opex", "sg&a", "selling general administrative"],
    "operating_income": ["operating income", "operating profit", "ebit"],
    "taxes": ["tax", "taxes", "income tax"],
    "interest": ["interest", "interest expense"],
    "net_income": ["net income", "net profit", "profit after tax", "profit"],
}


def _normalize_label(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = s.lower().strip()
    for c in ".,;&-":
        s = s.replace(c, " ")
    return " ".join(s.split())


def _match_canonical(label: str) -> Optional[str]:
    """Return canonical key if label matches a synonym. Longest match wins.
    Exact matches are strongly preferred over substring matches."""
    norm = _normalize_label(label)
    if not norm:
        return None
    # Pass 1: exact match (highest priority)
    for canonical, synonyms in _SYNONYMS.items():
        for syn in synonyms:
            if syn == norm:
                return canonical
    # Pass 2: synonym is a substring of the label (e.g., "profit" in "gross profit")
    best_canonical = None
    best_len = 0
    for canonical, synonyms in _SYNONYMS.items():
        for syn in synonyms:
            if syn in norm and len(syn) > best_len:
                best_canonical = canonical
                best_len = len(syn)
    return best_canonical


def _parse_pnl_cell(cell) -> Optional[float]:
    """Parse a table cell into a float using robust normalization."""
    if isinstance(cell, (int, float)):
        return float(cell)
    if isinstance(cell, str):
        result = normalize_cell_text(cell)
        return result["value"]
    return None


@dataclass
class PnLTable:
    """Structured P&L: periods and items[key][period]=value. Provenance for logging."""
    periods: List[str] = field(default_factory=list)
    items: Dict[str, Dict[str, float]] = field(default_factory=dict)
    row_label_by_key: Dict[str, str] = field(default_factory=dict)


def _parse_layout_a(columns: List[Any], rows: List[Any]) -> Optional[PnLTable]:
    """
    Layout A: first column = line items, other columns = periods.
    columns: ["Line Item", "2022", "2023"]
    rows: [["Revenue", "100", "120"], ["COGS", "40", "50"], ...]
    """
    if len(columns) < 2 or not rows:
        return None
    period_cols = columns[1:]
    periods = [str(c).strip() for c in period_cols]
    out = PnLTable(periods=periods)
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            continue
        label = str(row[0]).strip() if row[0] is not None else ""
        canonical = _match_canonical(label)
        if not canonical:
            continue
        out.row_label_by_key[canonical] = label
        if canonical not in out.items:
            out.items[canonical] = {}
        for i, period in enumerate(periods):
            idx = i + 1
            if idx >= len(row):
                continue
            cell = row[idx]
            val = _parse_pnl_cell(cell)
            if val is not None:
                out.items[canonical][period] = val
    if not out.items or not out.periods:
        return None
    return out


def _parse_layout_b(columns: List[Any], rows: List[Any]) -> Optional[PnLTable]:
    """
    Layout B: columns = ["Period", "Line Item", "Value"]
    """
    if len(columns) < 3 or not rows:
        return None
    # Find column indices
    col_lower = [str(c).lower() for c in columns]
    period_idx = None
    item_idx = None
    value_idx = None
    for i, c in enumerate(col_lower):
        if "period" in c or "year" in c or "quarter" in c:
            period_idx = i
        elif "line" in c or "item" in c or "account" in c:
            item_idx = i
        elif "value" in c or "amount" in c:
            value_idx = i
    if period_idx is None or item_idx is None or value_idx is None:
        return None
    periods_set = set()
    items_raw: Dict[str, Dict[str, float]] = {}
    row_label_by_key: Dict[str, str] = {}
    for row in rows:
        if not isinstance(row, (list, tuple)) or max(period_idx, item_idx, value_idx) >= len(row):
            continue
        period = str(row[period_idx]).strip()
        label = str(row[item_idx]).strip() if row[item_idx] is not None else ""
        canonical = _match_canonical(label)
        if not canonical:
            continue
        periods_set.add(period)
        row_label_by_key[canonical] = label
        if canonical not in items_raw:
            items_raw[canonical] = {}
        cell = row[value_idx]
        val = _parse_pnl_cell(cell)
        if val is not None:
            items_raw[canonical][period] = val
    periods = sorted(periods_set)
    if not items_raw or not periods:
        return None
    return PnLTable(periods=periods, items=items_raw, row_label_by_key=row_label_by_key)


def parse_pnl_table(content: Dict[str, Any]) -> Optional[PnLTable]:
    """
    Parse table content into structured P&L. Supports Layout A (preferred) and Layout B.
    Returns None if layout is not supported or no P&L line items found.
    """
    columns = content.get("columns", [])
    rows = content.get("rows", [])
    if not columns or not rows:
        return None
    # Try Layout A first: first column looks like line items (text), rest like periods
    parsed = _parse_layout_a(columns, rows)
    if parsed is not None and len(parsed.items) >= 1:
        return parsed
    parsed = _parse_layout_b(columns, rows)
    if parsed is not None and len(parsed.items) >= 1:
        return parsed
    return None
