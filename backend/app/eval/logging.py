"""Evaluation logging for ML-ready dataset."""
import json
import csv
import os
from pathlib import Path
from typing import Dict, Any
from ..verifier.types import VerifierSignals, AuditReport


def ensure_runs_directory():
    """Ensure runs directory exists."""
    runs_dir = Path(__file__).parent.parent.parent.parent / "runs"
    runs_dir.mkdir(exist_ok=True)
    return runs_dir


def log_run(report: AuditReport, runs_dir: Path = None, extra: Dict[str, Any] = None):
    """
    Log a verification run to runs/logs.jsonl.
    Each run logs: question, evidence type, candidate_answer, claims, verification (recomputed values), signals, decision.
    Optional extra (e.g. generated_answer, evidence) is merged for reproducibility.
    """
    if runs_dir is None:
        runs_dir = ensure_runs_directory()
    
    logs_file = runs_dir / "logs.jsonl"
    
    report_dict = report.to_dict()
    if extra:
        report_dict.update(extra)
    
    with open(logs_file, 'a') as f:
        f.write(json.dumps(report_dict) + '\n')


def log_signals(signals: VerifierSignals, decision: str, runs_dir: Path = None):
    """
    Log signals to runs/signals.csv.
    
    Appends one row per run.
    """
    if runs_dir is None:
        runs_dir = ensure_runs_directory()
    
    signals_file = runs_dir / "signals.csv"
    
    # Check if file exists to determine if we need headers
    file_exists = signals_file.exists()
    
    signals_dict = signals.to_dict()
    signals_dict['decision'] = decision
    
    # Write CSV
    with open(signals_file, 'a', newline='') as f:
        fieldnames = list(signals_dict.keys())
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        
        if not file_exists:
            writer.writeheader()
        
        writer.writerow(signals_dict)

