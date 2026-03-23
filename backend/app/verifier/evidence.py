"""Evidence ingestion and parsing with enriched metadata."""
import re
from typing import Dict, List, Any, Optional
from .types import EvidenceItem

_PERIOD_PATTERN = re.compile(r"\b((?:FY\s*)?20\d{2}|Q[1-4](?:\s*20\d{2})?|H[12](?:\s*20\d{2})?)\b", re.IGNORECASE)

_TABLE_SCALE_PATTERN = re.compile(
    r"\b(?:in\s+)?(thousands?|millions?|billions?|USD\s*(?:thousands?|millions?|billions?)|000s)\b",
    re.IGNORECASE,
)

_SCALE_WORD_TO_LABEL = {
    "thousand": "K", "thousands": "K", "000s": "K",
    "million": "M", "millions": "M",
    "billion": "B", "billions": "B",
}

_CURRENCY_PATTERN = re.compile(r"\b(USD|EUR|GBP|JPY|INR|LKR)\b|\$|£|€|¥|₹", re.IGNORECASE)


def _detect_period(text: str) -> Optional[str]:
    m = _PERIOD_PATTERN.search(text)
    return m.group(1).strip() if m else None


def _detect_scale(text: str) -> Optional[str]:
    m = _TABLE_SCALE_PATTERN.search(text)
    if m:
        word = m.group(1).lower().split()[-1]
        return _SCALE_WORD_TO_LABEL.get(word)
    return None


def _detect_currency(text: str) -> Optional[str]:
    m = _CURRENCY_PATTERN.search(text)
    if m:
        tok = m.group(0)
        sym_map = {"$": "USD", "£": "GBP", "€": "EUR", "¥": "JPY", "₹": "INR"}
        return sym_map.get(tok, tok.upper())
    return None


def _try_match_canonical(label: str) -> Optional[str]:
    """Attempt to match a row label to a canonical P&L line item key."""
    from .pnl_parser import _match_canonical
    return _match_canonical(label)


def parse_text_evidence(text: str) -> List[EvidenceItem]:
    """Parse text evidence and extract numeric values."""
    items = []
    number_pattern = r'\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\b|\b\d+\.\d+\b|\b\d{4,}\b'
    for match in re.finditer(number_pattern, text):
        start, end = match.span()
        number_str = match.group(0).replace(',', '')
        try:
            value = float(number_str)
            context_start = max(0, start - 50)
            context_end = min(len(text), end + 50)
            context = text[context_start:context_end]
            item = EvidenceItem(value=value, source="text", location=None, context=context)
            items.append(item)
        except ValueError:
            continue
    return items


def parse_table_evidence(table_data: Dict[str, Any]) -> List[EvidenceItem]:
    """Parse table evidence with enriched metadata (row/col labels, period, canonical line item)."""
    items = []
    columns = table_data.get("columns", [])
    rows = table_data.get("rows", [])
    units = table_data.get("units", {})

    table_currency = None
    table_scale = None
    for col in columns:
        col_str = str(col)
        if not table_currency:
            table_currency = _detect_currency(col_str)
        if not table_scale:
            table_scale = _detect_scale(col_str)
    for v in units.values():
        if not table_scale:
            table_scale = _detect_scale(str(v))
        if not table_currency:
            table_currency = _detect_currency(str(v))

    # Detect layout: Layout B has columns like [Period, Line Item, Value]
    col_lower = [str(c).lower() for c in columns]
    is_layout_b = False
    period_col_idx, item_col_idx, value_col_idx = None, None, None
    if len(columns) >= 3:
        for i, c in enumerate(col_lower):
            if "period" in c or "year" in c or "quarter" in c:
                period_col_idx = i
            elif "line" in c or "item" in c or "account" in c:
                item_col_idx = i
            elif "value" in c or "amount" in c:
                value_col_idx = i
        if period_col_idx is not None and item_col_idx is not None and value_col_idx is not None:
            is_layout_b = True

    if is_layout_b:
        return _parse_layout_b(rows, columns, period_col_idx, item_col_idx, value_col_idx,
                               table_currency, table_scale, units)

    # Layout A: first column = line items, rest = periods
    for row_idx, row in enumerate(rows):
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            continue
        row_label = str(row[0]).strip() if row[0] is not None else ""
        canonical = _try_match_canonical(row_label)

        for col_idx in range(1, len(row)):
            if col_idx >= len(columns):
                continue
            cell = row[col_idx]
            col_name = str(columns[col_idx])
            value, cell_is_percent = _parse_cell_value(cell)
            if value is None:
                continue

            period = _detect_period(col_name)
            col_currency = _detect_currency(col_name) or table_currency
            col_scale = _detect_scale(col_name) or table_scale

            item = EvidenceItem(
                value=value,
                source="table",
                location=f"row:{row_idx},col:{col_idx}",
                context=row_label,
                row_label=row_label,
                col_label=col_name,
                row_index=row_idx,
                col_index=col_idx,
                period=period,
                canonical_line_item=canonical,
                currency=col_currency,
                scale_label=col_scale,
                is_percent=cell_is_percent,
            )
            items.append(item)
    return items


def _parse_layout_b(rows, columns, period_idx, item_idx, value_idx,
                     table_currency, table_scale, units) -> List[EvidenceItem]:
    items = []
    for row_idx, row in enumerate(rows):
        if not isinstance(row, (list, tuple)):
            continue
        if max(period_idx, item_idx, value_idx) >= len(row):
            continue
        period = str(row[period_idx]).strip()
        label = str(row[item_idx]).strip() if row[item_idx] is not None else ""
        canonical = _try_match_canonical(label)
        value, cell_is_percent = _parse_cell_value(row[value_idx])
        if value is None:
            continue
        item = EvidenceItem(
            value=value,
            source="table",
            location=f"row:{row_idx},col:{value_idx}",
            context=label,
            row_label=label,
            col_label=str(columns[value_idx]),
            row_index=row_idx,
            col_index=value_idx,
            period=period,
            canonical_line_item=canonical,
            currency=table_currency,
            scale_label=table_scale,
            is_percent=cell_is_percent,
        )
        items.append(item)
    return items


def _parse_cell_value(cell):
    """Parse a table cell into (value, is_percent). Returns (float, bool) or (None, False)."""
    if isinstance(cell, (int, float)):
        return float(cell), False
    if isinstance(cell, str):
        from .normalize import normalize_cell_text
        result = normalize_cell_text(cell)
        if result["value"] is not None:
            return result["value"], result["is_percent"]
        return None, False
    return None, False


def ingest_evidence(evidence_data: Dict[str, Any]) -> List[EvidenceItem]:
    """Ingest evidence from request."""
    evidence_type = evidence_data.get("type")
    content = evidence_data.get("content")
    if evidence_type == "text" and isinstance(content, str):
        return parse_text_evidence(content)
    if evidence_type == "table" and isinstance(content, dict):
        return parse_table_evidence(content)
    return []
