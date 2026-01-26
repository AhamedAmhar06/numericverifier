"""Evidence ingestion and parsing."""
from typing import Dict, List, Any, Union
from .types import EvidenceItem


def parse_text_evidence(text: str) -> List[EvidenceItem]:
    """Parse text evidence and extract numeric values."""
    items = []
    
    # Extract numbers from text (similar to claim extraction but simpler)
    import re
    
    # Pattern for numbers (handles both comma-separated and plain numbers)
    # Use word boundaries to avoid partial matches
    number_pattern = r'\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\b|\b\d+\.\d+\b|\b\d{4,}\b'
    
    for match in re.finditer(number_pattern, text):
        start, end = match.span()
        number_str = match.group(0).replace(',', '')
        
        try:
            value = float(number_str)
            # Get context (surrounding text)
            context_start = max(0, start - 50)
            context_end = min(len(text), end + 50)
            context = text[context_start:context_end]
            
            item = EvidenceItem(
                value=value,
                source="text",
                location=None,
                context=context
            )
            items.append(item)
        except ValueError:
            continue
    
    return items


def parse_table_evidence(table_data: Dict[str, Any]) -> List[EvidenceItem]:
    """
    Parse table evidence.
    
    Expected format:
    {
        "columns": [...],
        "rows": [...],
        "units": { column_name: unit }
    }
    """
    items = []
    
    columns = table_data.get("columns", [])
    rows = table_data.get("rows", [])
    units = table_data.get("units", {})
    
    for row_idx, row in enumerate(rows):
        for col_idx, cell in enumerate(row):
            if col_idx >= len(columns):
                continue
            
            col_name = columns[col_idx]
            
            # Try to parse as float
            if isinstance(cell, (int, float)):
                value = float(cell)
            elif isinstance(cell, str):
                # Remove commas and try to parse
                cell_clean = cell.replace(',', '').strip()
                try:
                    value = float(cell_clean)
                except ValueError:
                    continue
            else:
                continue
            
            location = f"row:{row_idx},col:{col_idx}"
            unit = units.get(col_name)
            
            item = EvidenceItem(
                value=value,
                source="table",
                location=location,
                context=None
            )
            items.append(item)
    
    return items


def ingest_evidence(evidence_data: Dict[str, Any]) -> List[EvidenceItem]:
    """
    Ingest evidence from request.
    
    Expected format:
    {
        "type": "text" | "table",
        "content": "string OR table JSON"
    }
    """
    evidence_type = evidence_data.get("type")
    content = evidence_data.get("content")
    
    if evidence_type == "text":
        if isinstance(content, str):
            return parse_text_evidence(content)
        else:
            return []
    elif evidence_type == "table":
        if isinstance(content, dict):
            return parse_table_evidence(content)
        else:
            return []
    else:
        return []

