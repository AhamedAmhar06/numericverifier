"""ML decision model stubs (not implemented in baseline)."""
from pathlib import Path
from typing import Optional
from ..verifier.types import VerifierSignals, Decision
from ..verifier.decision_rules import make_decision


def load_model(model_path: Optional[Path] = None) -> Optional[object]:
    """
    Load ML model from joblib file (stub only).
    
    Returns None if model doesn't exist (falls back to rule-based).
    """
    # In baseline, always return None to use rule-based decision
    return None


def predict_decision(signals: VerifierSignals, model: Optional[object] = None) -> Decision:
    """
    Predict decision using ML model (stub only).
    
    Falls back to rule-based decision if model is None.
    """
    # In baseline, always use rule-based decision
    return make_decision(signals, [])

