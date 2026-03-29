"""Parse a CSV file into verifier-compatible table JSON."""
import csv
import io
from pathlib import Path
from typing import Dict, Any, Union


def parse_csv_pnl(source: Union[str, Path, io.TextIOBase]) -> Dict[str, Any]:
    """Read a CSV P&L table and return ``{columns, rows, units}``."""
    if isinstance(source, (str, Path)):
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"CSV file not found: {path}")
        with open(path, newline="", encoding="utf-8-sig") as fh:
            return _parse(fh)
    return _parse(source)


def _parse(fh) -> Dict[str, Any]:
    reader = csv.reader(fh)
    rows_raw = list(reader)
    if not rows_raw:
        raise ValueError("CSV file is empty")
    columns = [str(c).strip() for c in rows_raw[0]]
    rows = []
    for row in rows_raw[1:]:
        padded = row + [""] * max(0, len(columns) - len(row))
        rows.append([str(cell).strip() if cell is not None else "" for cell in padded[:len(columns)]])
    return {"columns": columns, "rows": rows, "units": {}}
