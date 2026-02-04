"""Evaluation logging for ML-ready dataset."""
import json
import csv
import logging
from pathlib import Path
from typing import Dict, Any
from ..verifier.types import VerifierSignals, AuditReport
from ..core.config import _BACKEND_DIR

logger = logging.getLogger(__name__)

# Use same project root as config so runs/ is always project_root/runs.
_PROJECT_ROOT = _BACKEND_DIR.parent


def ensure_runs_directory():
    """Ensure runs directory exists. Path: project_root/runs (same as backend/.env resolution)."""
    runs_dir = _PROJECT_ROOT / "runs"
    runs_dir.mkdir(exist_ok=True)
    return runs_dir


def log_run(report: AuditReport, runs_dir: Path = None, extra: Dict[str, Any] = None):
    """
    Log a verification run to runs/logs.jsonl.
    Optional extra (domain, engine_used, llm_used, llm_fallback_reason, generated_answer) is merged.
    """
    if runs_dir is None:
        runs_dir = ensure_runs_directory()
    logs_file = runs_dir / "logs.jsonl"
    report_dict = report.to_dict()
    if extra:
        report_dict.update(extra)
    with open(logs_file, 'a') as f:
        f.write(json.dumps(report_dict) + '\n')


def _signals_v2_path(runs_dir: Path) -> Path:
    """Path for schema v2 signals. Always use signals_v2.csv for v2 data."""
    return runs_dir / "signals_v2.csv"


def log_signals(signals: VerifierSignals, decision: str, runs_dir: Path = None):
    """
    Append one row to runs/signals_v2.csv. Depends on caller to only call when log_run=true.
    If file exists, use its header to avoid schema mismatch. Never overwrite; append only.
    """
    if runs_dir is None:
        runs_dir = ensure_runs_directory()
    signals_file = _signals_v2_path(runs_dir)
    signals_dict = signals.to_dict()
    signals_dict['decision'] = decision
    fieldnames = list(signals_dict.keys())

    try:
        file_exists = signals_file.exists()
        if file_exists:
            with open(signals_file, 'r', newline='') as f:
                reader = csv.reader(f)
                existing_header = next(reader, None)
            if existing_header and set(existing_header) != set(fieldnames):
                logger.error(
                    "signals_v2.csv schema mismatch (existing columns differ from current). Skipping append to avoid corrupting file."
                )
                return
            if existing_header:
                fieldnames = existing_header
        with open(signals_file, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            if not file_exists:
                writer.writeheader()
            writer.writerow(signals_dict)
    except Exception as e:
        logger.error("Failed to append to signals_v2.csv: %s", e, exc_info=True)
        raise

