"""
ML decision model for NumericVerifier (P&L-only, schema v2).

- USE_ML_DECIDER=true: apply hard safety gates, then ML prediction; fallback to rules if model missing/fails.
- USE_ML_DECIDER=false: rule-based decision only (default).

Hard safety gates (ML must never override): if any of the following, return FLAG and do not call the model:
  - pnl_missing_baseline_count > 0
  - pnl_period_strict_mismatch_count > 0
  - pnl_table_detected == 0
"""
import json
import logging
import os
from pathlib import Path
from typing import Any, List, Optional

from ..verifier.types import Decision, VerifierSignals, VerificationResult
from ..verifier.decision_rules import make_decision

logger = logging.getLogger(__name__)

# Project root / runs (same resolution as eval/logging and config)
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
_RUNS_DIR = _BACKEND_DIR.parent / "runs"

# Artifact names (must match scripts/train_ml_decision_v2.py exports)
_MODEL_FILE = "decision_model_v2.joblib"
_FEATURE_SCHEMA_FILE = "feature_schema_v2.json"
_LABEL_MAPPING_FILE = "label_mapping_v2.json"

# Runtime toggle: use ML after hard gates when true
def _use_ml_decider() -> bool:
    v = os.environ.get("USE_ML_DECIDER", "false").strip().lower()
    return v in ("true", "1", "yes")


def _hard_gate_flag(signals: VerifierSignals) -> bool:
    """Return True if any hard safety condition requires FLAG (do not call ML)."""
    if getattr(signals, "pnl_missing_baseline_count", 0) > 0:
        return True
    if getattr(signals, "pnl_period_strict_mismatch_count", 0) > 0:
        return True
    if getattr(signals, "pnl_table_detected", 0) == 0:
        return True
    return False


def load_model(model_path: Optional[Path] = None) -> Optional[object]:
    """
    Load ML pipeline and metadata from runs/.
    Returns a dict with keys: pipeline, feature_order, label_mapping, or None if not available.
    """
    base = model_path if model_path is not None else _RUNS_DIR
    pipeline_path = base / _MODEL_FILE
    schema_path = base / _FEATURE_SCHEMA_FILE
    mapping_path = base / _LABEL_MAPPING_FILE

    if not pipeline_path.exists() or not schema_path.exists() or not mapping_path.exists():
        logger.debug("ML artifacts missing in %s; using rule-based decision.", base)
        return None

    # Ensure joblib (and thus sklearn/numpy) are available; try project .pip-ml if needed
    try:
        import joblib
    except ImportError:
        _project_root = _RUNS_DIR.parent
        _pip_ml = _project_root / ".pip-ml"
        if _pip_ml.exists():
            import sys
            _path = str(_pip_ml)
            if _path not in sys.path:
                sys.path.insert(0, _path)
            try:
                import joblib
            except ImportError:
                logger.warning(
                    "joblib not found. Install backend deps: pip install -r backend/requirements.txt (from project root)."
                )
                return None
        else:
            logger.warning(
                "joblib not found. Install backend deps: pip install -r backend/requirements.txt (from project root)."
            )
            return None

    try:
        pipeline = joblib.load(pipeline_path)
        with open(schema_path, "r") as f:
            feature_schema = json.load(f)
        with open(mapping_path, "r") as f:
            label_mapping = json.load(f)
    except Exception as e:
        logger.warning("Failed to load ML model: %s. Using rule-based decision.", e)
        return None

    feature_order = feature_schema.get("feature_order") or feature_schema.get("feature_names")
    if not feature_order:
        logger.warning("feature_schema_v2.json missing feature_order. Using rule-based decision.")
        return None

    return {
        "pipeline": pipeline,
        "feature_order": feature_order,
        "label_mapping": label_mapping,
    }


def _signals_to_feature_vector(signals: VerifierSignals, feature_order: List[str]) -> List[float]:
    """Build feature vector in schema order. Uses VerifierSignals attributes / to_dict()."""
    d = signals.to_dict()
    return [float(d.get(k, 0)) for k in feature_order]


def predict_decision(
    signals: VerifierSignals,
    model: Optional[object] = None,
    verification_results: Optional[List[VerificationResult]] = None,
) -> Decision:
    """
    Predict decision using ML model after hard safety gates.

    - If model is None or invalid, falls back to rule-based decision.
    - Hard gates (pnl_missing_baseline_count > 0, pnl_period_strict_mismatch_count > 0,
      pnl_table_detected == 0) always return FLAG without calling the model.
    """
    if _hard_gate_flag(signals):
        logger.info("Decision path: hard-gate FLAG (no ML call). pnl_missing_baseline|period_strict|pnl_table_detected.")
        return Decision(
            decision="FLAG",
            rationale="Hard safety gate: missing baseline, period strict mismatch, or non-P&L. Requires review.",
        )

    if model is None:
        logger.info("Decision path: rules (ML model not loaded).")
        return make_decision(signals, verification_results or [])

    if not isinstance(model, dict) or "pipeline" not in model or "feature_order" not in model or "label_mapping" not in model:
        logger.info("Decision path: rules (ML model invalid or missing).")
        return make_decision(signals, verification_results or [])

    feature_order = model["feature_order"]
    label_mapping = model["label_mapping"]
    pipeline = model["pipeline"]

    try:
        import numpy as np
        vec = _signals_to_feature_vector(signals, feature_order)
        X = np.array([vec], dtype=np.float64)
        pred_index = pipeline.predict(X)[0]
        idx = int(pred_index)
        raw = label_mapping.get("index_to_label") or {}
        index_to_label = {int(k): v for k, v in raw.items()}
        decision_label = index_to_label.get(idx, "FLAG")
        logger.info("Decision path: ML (v2 model). decision=%s", decision_label)
        return Decision(
            decision=decision_label,
            rationale=f"ML decision (v2): {decision_label}.",
        )
    except Exception as e:
        logger.warning("ML prediction failed: %s. Falling back to rule-based decision.", e)
        return make_decision(signals, verification_results or [])


# Cached loaded model (avoids reloading every request)
_cached_model: Optional[object] = None


def decide(
    signals: VerifierSignals,
    verification_results: List[VerificationResult],
    model: Optional[object] = None,
) -> Decision:
    """
    Single entry point for the backend: either ML (after hard gates) or rule-based.

    - If USE_ML_DECIDER is false: always use rule-based decision.
    - If USE_ML_DECIDER is true: apply hard gates; if FLAG, return; else run ML or fallback to rules.
    """
    if not _use_ml_decider():
        logger.info("Decision path: rules (USE_ML_DECIDER=false).")
        return make_decision(signals, verification_results)

    global _cached_model
    if model is None:
        if _cached_model is None:
            _cached_model = load_model()
        model = _cached_model
    return predict_decision(signals, model=model, verification_results=verification_results)
