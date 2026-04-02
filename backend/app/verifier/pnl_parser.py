"""P&L table parsing: Layout A/B, synonym mapping to canonical line items.

Enhanced preprocessing handles real-world financial report tables:
- Multi-row headers  (e.g. "Fiscal Year Ended" row + date row collapsed)
- Parentheses negatives: (1,234) → -1234
- Table-level scale declarations ("in millions", "in thousands") applied to all values
- Standalone dash / em-dash (—) treated as zero
- Footnote markers (*, †, ‡, trailing superscript digits) stripped before parsing
- FY notation: FY2024, FY24, '24 normalised to canonical period strings
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .normalize import normalize_cell_text

# ---------------------------------------------------------------------------
# Canonical synonyms
# ---------------------------------------------------------------------------
_SYNONYMS: Dict[str, List[str]] = {
    "revenue": [
        "revenue", "sales", "turnover",
        "total revenue", "net revenue", "net sales", "total net sales",
        "total revenues",
    ],
    "cogs": [
        "cogs", "cost of sales", "cost of revenue", "cost of goods sold",
        "cost of products", "cost of services", "total cost of sales",
        "total cost of revenue",
    ],
    "gross_profit": ["gross profit", "gross income"],
    # Individual opex line items get their own keys so the ratio library can
    # verify claims like "R&D as % of revenue" without value collisions.
    # These keys appear before "operating_expenses" so Pass 1 (exact match)
    # resolves them first, preventing false matches to "revenue" via Pass 2.
    "research_and_development": [
        "research and development", "research development",
        "research development and engineering",
    ],
    "sales_marketing": [
        "sales and marketing", "selling and marketing", "marketing and sales",
        "sales marketing and support",
    ],
    "operating_expenses": [
        "operating expenses", "opex", "sg&a",
        "selling general and administrative", "selling general administrative",
        "selling general and administrative expenses",
        "total operating expenses",
        # Combined opex items and standalone G&A remain here.
        # Note: "research and development" and "sales and marketing" are now
        # handled by the dedicated keys above to prevent value collision when
        # both appear as separate rows in the same table.
        "selling marketing and administrative",
        "general and administrative", "general and administrative expenses",
    ],
    "operating_income": [
        "operating income", "operating profit", "ebit",
        "income from operations", "operating earnings",
    ],
    "taxes": [
        "tax", "taxes", "income tax", "income taxes",
        "provision for income taxes", "provision for income tax",
        "income tax expense",
    ],
    "interest": [
        "interest", "interest expense", "interest income",
        "net interest expense", "net interest income",
    ],
    "net_income": [
        "net income", "net profit", "profit after tax", "profit",
        "net earnings", "earnings", "net income attributable",
    ],
}

# ---------------------------------------------------------------------------
# Preprocessing patterns
# ---------------------------------------------------------------------------
# Footnote markers: *, †, ‡, §, ¶, or trailing whitespace + 1-2 digits
_FOOTNOTE_RE = re.compile(r"[\*†‡§¶]|\s+\d{1,2}$")

# Standalone dash cell (hyphen, en-dash, em-dash only → means zero)
_STANDALONE_DASH_RE = re.compile(r"^[\-\u2013\u2014\s]+$")

# Scale in header / caption text
_SCALE_HEADER_RE = re.compile(
    r"\bin\s+(thousands?|millions?|billions?)\b"
    r"|\(in\s+(thousands?|millions?|billions?)\)"
    r"|\(thousands?\)|\(millions?\)|\(billions?\)"
    r"|\b(USD\s+)?(thousands?|millions?|billions?)\b",
    re.IGNORECASE,
)
_SCALE_WORD_TO_MULT = {
    "thousand": 1_000,     "thousands": 1_000,
    "million":  1_000_000, "millions":  1_000_000,
    "billion":  1_000_000_000, "billions": 1_000_000_000,
}
_SCALE_WORD_TO_LABEL = {
    "thousand": "K", "thousands": "K",
    "million":  "M", "millions":  "M",
    "billion":  "B", "billions":  "B",
}

# Period normalisation
_PERIOD_FY4    = re.compile(r"^FY\s*(\d{4})$", re.IGNORECASE)
_PERIOD_FY2    = re.compile(r"^FY\s*(\d{2})$", re.IGNORECASE)
_PERIOD_QUOTE2 = re.compile(r"^['\u2018\u2019](\d{2})$")   # '24 or '24
_PERIOD_BARE4  = re.compile(r"^(\d{4})$")
_PERIOD_QUARTER = re.compile(r"^(Q[1-4])\s*['\u2018\u2019]?(\d{2,4})$", re.IGNORECASE)
_PERIOD_DATE   = re.compile(r"\b(20\d{2})\b")               # "Sep 30, 2023" → 2023

# Multi-row header detection
_FISCAL_ROW_RE = re.compile(
    r"fiscal\s+year|year\s+ended|twelve\s+months|52\s+weeks|53\s+weeks|period\s+ended",
    re.IGNORECASE,
)
# Cell that looks like a period (year, FY-year, quarter, or date)
_LOOKS_LIKE_PERIOD_RE = re.compile(
    r"(?:FY\s*)?\d{4}"
    r"|FY\s*\d{2}"
    r"|['\u2018\u2019]\d{2}"
    r"|Q[1-4]\s*\d{2,4}"
    r"|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{1,2},\s*20\d{2}",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
@dataclass
class TableMetadata:
    """Table-level metadata extracted from headers / captions."""
    scale_label: Optional[str] = None        # "K" | "M" | "B"
    scale_multiplier: float = 1.0            # 1 | 1_000 | 1_000_000 | 1_000_000_000
    currency: Optional[str] = None           # "USD" | "EUR" | …
    fiscal_period_format: Optional[str] = None  # "FY" | "Calendar" | "Quarter"
    raw_scale_text: Optional[str] = None     # e.g. "in millions"


@dataclass
class PnLTable:
    """Structured P&L: periods, items, metadata, provenance."""
    periods: List[str] = field(default_factory=list)
    items: Dict[str, Dict[str, float]] = field(default_factory=dict)
    row_label_by_key: Dict[str, str] = field(default_factory=dict)
    metadata: TableMetadata = field(default_factory=TableMetadata)


# ---------------------------------------------------------------------------
# Label helpers
# ---------------------------------------------------------------------------
def _normalize_label(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = s.lower().strip().rstrip(":")          # strip trailing colon (Apple-style)
    for c in ".,;&":
        s = s.replace(c, " ")
    s = s.replace("\u2013", " ").replace("\u2014", " ")   # en/em-dash in labels
    return " ".join(s.split())


def _match_canonical(label: str) -> Optional[str]:
    """Return canonical key if label matches a synonym.  Exact match beats substring."""
    norm = _normalize_label(label)
    if not norm:
        return None
    # Pass 1: exact
    for canonical, synonyms in _SYNONYMS.items():
        for syn in synonyms:
            if syn == norm:
                return canonical
    # Pass 2: longest substring
    best_canonical: Optional[str] = None
    best_len = 0
    for canonical, synonyms in _SYNONYMS.items():
        for syn in synonyms:
            if syn in norm and len(syn) > best_len:
                best_canonical = canonical
                best_len = len(syn)
    return best_canonical


# ---------------------------------------------------------------------------
# Cell-level preprocessing
# ---------------------------------------------------------------------------
def _strip_footnote_markers(s: str) -> str:
    """Strip trailing *, †, ‡, §, ¶ or whitespace-separated digit(s)."""
    return _FOOTNOTE_RE.sub("", s).strip()


def _is_standalone_dash(s: str) -> bool:
    """Return True when the whole cell is dashes/spaces (meaning zero)."""
    stripped = s.strip()
    return bool(stripped) and bool(_STANDALONE_DASH_RE.fullmatch(stripped))


def _parse_pnl_cell(cell: Any, scale_multiplier: float = 1.0) -> Optional[float]:
    """Parse one table cell into a float.

    Preprocessing order:
    1. Numeric / float passthrough (scale applied).
    2. Standalone dash / em-dash → 0.0 (scale irrelevant).
    3. Strip footnote markers.
    4. Delegate to normalize_cell_text for parentheses-negatives, commas, etc.
    5. Apply table-level scale ONLY when the cell had no own scale notation.
    """
    if isinstance(cell, (int, float)):
        return float(cell) * scale_multiplier
    if not isinstance(cell, str):
        return None

    s = cell.strip()
    if not s:
        return None

    # Zero-meaning dashes
    if _is_standalone_dash(s):
        return 0.0

    # Remove footnote markers before numeric parsing
    s = _strip_footnote_markers(s)
    if not s:
        return None

    result = normalize_cell_text(s)
    val = result["value"]
    if val is None:
        return None

    # Apply table-level scale only when the cell did not carry its own scale
    if result["scale_factor"] == 1.0:
        val = val * scale_multiplier

    return val


# ---------------------------------------------------------------------------
# Period normalisation
# ---------------------------------------------------------------------------
def _normalize_period(raw: str) -> str:
    """Map diverse period labels to a canonical string.

    FY2024 → FY2024   FY24 → FY2024   '24 → FY2024
    2023   → 2023     Q1 2024 → Q1 2024
    "September 30, 2023" → 2023
    """
    s = raw.strip()
    if not s:
        return raw

    m = _PERIOD_FY4.match(s)
    if m:
        return f"FY{m.group(1)}"

    m = _PERIOD_FY2.match(s)
    if m:
        return f"FY20{m.group(1)}"

    m = _PERIOD_QUOTE2.match(s)
    if m:
        return f"FY20{m.group(1)}"

    m = _PERIOD_BARE4.match(s)
    if m:
        return m.group(1)

    m = _PERIOD_QUARTER.match(s)
    if m:
        q = m.group(1).upper()
        yr = m.group(2)
        if len(yr) == 2:
            yr = f"20{yr}"
        return f"{q} {yr}"

    # Date string like "September 30, 2023"
    m = _PERIOD_DATE.search(s)
    if m:
        return m.group(1)

    return s  # unrecognised → return as-is


# ---------------------------------------------------------------------------
# Table metadata extraction
# ---------------------------------------------------------------------------
def _extract_table_metadata(texts: List[str]) -> TableMetadata:
    """Scan header / caption strings for scale, currency, and period-format clues."""
    meta = TableMetadata()

    for txt in texts:
        if not isinstance(txt, str) or not txt.strip():
            continue

        # Scale
        if meta.scale_label is None:
            m = _SCALE_HEADER_RE.search(txt)
            if m:
                word = next(
                    (g.lower() for g in m.groups() if g and g.lower() in _SCALE_WORD_TO_MULT),
                    None,
                )
                if word:
                    meta.scale_label = _SCALE_WORD_TO_LABEL[word]
                    meta.scale_multiplier = _SCALE_WORD_TO_MULT[word]
                    meta.raw_scale_text = m.group(0).strip()

        # Currency
        if meta.currency is None:
            if "$" in txt or re.search(r"\bUSD\b", txt):
                meta.currency = "USD"
            elif "€" in txt or re.search(r"\bEUR\b", txt):
                meta.currency = "EUR"
            elif "£" in txt or re.search(r"\bGBP\b", txt):
                meta.currency = "GBP"

        # Period format
        if meta.fiscal_period_format is None:
            if re.search(r"\bFY\b|fiscal\s+year", txt, re.IGNORECASE):
                meta.fiscal_period_format = "FY"
            elif re.search(r"\bQ[1-4]\b", txt, re.IGNORECASE):
                meta.fiscal_period_format = "Quarter"
            elif re.search(r"\b20\d{2}\b", txt):
                meta.fiscal_period_format = "Calendar"

    return meta


# ---------------------------------------------------------------------------
# Multi-row header collapsing
# ---------------------------------------------------------------------------
def _is_header_row(row: List[Any]) -> bool:
    """Heuristic: does this row look like a continuation of the header band?

    True when:
    - The first cell is empty OR matches a fiscal-year descriptor, AND
    - All non-empty remaining cells look like period labels.
    """
    if not row:
        return False
    first = str(row[0]).strip() if row[0] is not None else ""
    if first and not _FISCAL_ROW_RE.search(first):
        return False

    period_cells = [
        str(c).strip() for c in row[1:]
        if c is not None and str(c).strip()
    ]
    if not period_cells:
        # Row has only a fiscal-year descriptor → still a header row
        return bool(_FISCAL_ROW_RE.search(first))

    return all(_LOOKS_LIKE_PERIOD_RE.search(c) for c in period_cells)


def _collapse_multi_row_headers(
    columns: List[Any],
    rows: List[Any],
) -> Tuple[List[str], List[Any]]:
    """Detect and absorb a second header row into the column period list.

    Returns (normalised_periods, remaining_data_rows).
    """
    period_cols: List[str] = [str(c).strip() for c in columns[1:]]
    data_rows = list(rows)

    if data_rows and _is_header_row(data_rows[0]):
        header_row = data_rows.pop(0)
        new_periods = [str(c).strip() for c in header_row[1:]]
        if any(new_periods):
            period_cols = new_periods

    periods = [_normalize_period(p) for p in period_cols]
    return periods, data_rows


# ---------------------------------------------------------------------------
# Layout A parser  (first column = labels, rest = periods)
# ---------------------------------------------------------------------------
def _parse_layout_a(
    columns: List[Any],
    rows: List[Any],
    meta: TableMetadata,
) -> Optional[PnLTable]:
    if len(columns) < 2 or not rows:
        return None

    periods, data_rows = _collapse_multi_row_headers(columns, rows)
    scale = meta.scale_multiplier
    out = PnLTable(periods=periods, metadata=meta)

    for row in data_rows:
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
            val = _parse_pnl_cell(row[idx], scale)
            if val is not None:
                out.items[canonical][period] = val

    if not out.items or not out.periods:
        return None
    return out


# ---------------------------------------------------------------------------
# Layout B parser  (long format: Period | Line Item | Value)
# ---------------------------------------------------------------------------
def _parse_layout_b(
    columns: List[Any],
    rows: List[Any],
    meta: TableMetadata,
) -> Optional[PnLTable]:
    if len(columns) < 3 or not rows:
        return None

    col_lower = [str(c).lower() for c in columns]
    period_idx = item_idx = value_idx = None
    for i, c in enumerate(col_lower):
        if "period" in c or "year" in c or "quarter" in c:
            period_idx = i
        elif "line" in c or "item" in c or "account" in c:
            item_idx = i
        elif "value" in c or "amount" in c:
            value_idx = i
    if period_idx is None or item_idx is None or value_idx is None:
        return None

    scale = meta.scale_multiplier
    periods_set: set = set()
    items_raw: Dict[str, Dict[str, float]] = {}
    row_label_by_key: Dict[str, str] = {}

    for row in rows:
        if (
            not isinstance(row, (list, tuple))
            or max(period_idx, item_idx, value_idx) >= len(row)
        ):
            continue
        period = _normalize_period(str(row[period_idx]).strip())
        label = str(row[item_idx]).strip() if row[item_idx] is not None else ""
        canonical = _match_canonical(label)
        if not canonical:
            continue
        periods_set.add(period)
        row_label_by_key[canonical] = label
        if canonical not in items_raw:
            items_raw[canonical] = {}
        val = _parse_pnl_cell(row[value_idx], scale)
        if val is not None:
            items_raw[canonical][period] = val

    periods = sorted(periods_set)
    if not items_raw or not periods:
        return None
    return PnLTable(
        periods=periods,
        items=items_raw,
        row_label_by_key=row_label_by_key,
        metadata=meta,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def parse_pnl_table(content: Dict[str, Any]) -> Optional[PnLTable]:
    """Parse table content into a structured PnLTable.

    Supports Layout A (row-per-line-item, columns = periods) and Layout B
    (long/tidy format: Period | Line Item | Value).

    Preprocessing handles:
    - Multi-row headers collapsed to single period list
    - Parentheses negatives: (1,234) → -1234
    - Table-level scale ("in millions") multiplied into every value
    - Standalone dash / em-dash → 0.0
    - Footnote markers (*, †, trailing digits) stripped
    - FY notation (FY2024, FY24, '24) normalised to canonical period

    Returns None when the layout is not supported or no canonical P&L line
    items are found.
    """
    columns = content.get("columns", [])
    rows = content.get("rows", [])
    if not columns or not rows:
        return None

    # Gather all header/caption text for metadata extraction
    caption = content.get("caption", "")
    all_texts: List[str] = [str(caption)] + [str(c) for c in columns]
    if "units" in content:
        units_val = content["units"]
        if isinstance(units_val, dict):
            all_texts += [str(v) for v in units_val.values()]
        elif isinstance(units_val, str) and units_val:
            all_texts.append(units_val)

    meta = _extract_table_metadata(all_texts)

    # Layout A: first column is a text label column (not a period)
    first_col = str(columns[0]).strip() if columns else ""
    if not _LOOKS_LIKE_PERIOD_RE.fullmatch(first_col):
        result = _parse_layout_a(columns, rows, meta)
        if result and len(result.items) >= 1:
            return result

    # Layout B: long / tidy format
    result = _parse_layout_b(columns, rows, meta)
    if result and len(result.items) >= 1:
        return result

    return None
