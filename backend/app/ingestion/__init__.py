"""P&L table ingestion: convert CSV/XLSX files to verifier-compatible table JSON."""
from .csv_pnl_parser import parse_csv_pnl
from .excel_pnl_parser import parse_excel_pnl

__all__ = ["parse_csv_pnl", "parse_excel_pnl"]
