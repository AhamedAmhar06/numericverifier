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

# Artifact names (v5b default; override with ML_MODEL_VERSION env var)
def _model_version():
    return os.environ.get("ML_MODEL_VERSION", "v6_1").strip().lower()


def _artifact_names():
    v = _model_version()
    if v == "v6_1":
        return "decision_model_v6_1.joblib", "feature_schema_v6_1.json", "label_mapping_v5.json"
    if v == "v6":
        return "decision_model_v6.joblib", "feature_schema_v6.json", "label_mapping_v5.json"
    if v == "v5b":
        return "decision_model_v5b.joblib", "feature_schema_v5b.json", "label_mapping_v5.json"
    if v == "v5":
        return "decision_model_v5.joblib", "feature_schema_v5.json", "label_mapping_v5.json"
    if v == "v4b":
        return "decision_model_v4b.joblib", "feature_schema_v4b.json", "label_mapping_v4.json"
    if v == "v4":
        return "decision_model_v4.joblib", "feature_schema_v4.json", "label_mapping_v4.json"
    if v == "v3":
        return "decision_model_v3.joblib", "feature_schema_v3.json", "label_mapping_v3.json"
    return "decision_model_v2.joblib", "feature_schema_v2.json", "label_mapping_v2.json"

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
    mf, sf, lf = _artifact_names()
    base = model_path if model_path is not None else _RUNS_DIR
    pipeline_path = base / mf
    schema_path = base / sf
    mapping_path = base / lf

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
        loaded = joblib.load(pipeline_path)
        with open(schema_path, "r") as f:
            feature_schema = json.load(f)
        with open(mapping_path, "r") as f:
            label_mapping = json.load(f)
    except Exception as e:
        logger.warning("Failed to load ML model: %s. Using rule-based decision.", e)
        return None

    feature_order = feature_schema.get("feature_order") or feature_schema.get("feature_names")
    if not feature_order:
        logger.warning("feature_schema missing feature_order. Using rule-based decision.")
        return None

    # v3 format: dict with pipeline, threshold, classes, flag_idx
    pipeline = loaded.get("pipeline", loaded) if isinstance(loaded, dict) else loaded
    return {
        "pipeline": pipeline,
        "feature_order": feature_order,
        "label_mapping": label_mapping,
        "threshold": loaded.get("threshold") if isinstance(loaded, dict) else None,
        "classes": loaded.get("classes") if isinstance(loaded, dict) else None,
        "flag_idx": loaded.get("flag_idx", -1) if isinstance(loaded, dict) else -1,
    }


_SIGNAL_PLAIN_NAMES = {
    "coverage_ratio": "evidence coverage",
    "unsupported_claims_count": "unverified claims",
    "scale_mismatch_count": "scale mismatch",
    "pnl_period_strict_mismatch_count": "period mismatch",
    "pnl_identity_fail_count": "accounting identity failure",
    "grounding_confidence_score": "grounding confidence",
    "max_relative_error": "maximum numeric error",
    "mean_relative_error": "average numeric error",
    "unverifiable_claim_count": "unverifiable calculations",
    "ambiguity_count": "ambiguous matches",
}


def _signals_to_feature_vector(signals: VerifierSignals, feature_order: List[str]) -> List[float]:
    """Build feature vector in schema order. Uses VerifierSignals attributes / to_dict()."""
    d = signals.to_dict()
    return [float(d.get(k, 0)) for k in feature_order]


def _compute_shap_explanation(
    pipeline: Any,
    X: Any,
    feature_order: List[str],
    decision_label: str,
    label_mapping: Optional[dict] = None,
) -> Optional[dict]:
    """Compute SHAP values for the prediction. Returns None on any failure."""
    try:
        import shap  # noqa: PLC0415
        import numpy as np  # noqa: PLC0415

        explainer = shap.TreeExplainer(pipeline)
        shap_values = explainer.shap_values(X)

        # Determine which class index corresponds to decision_label
        # classes_ may be integer indices [0, 1, 2] or string labels
        label_mapping_ref = None
        sv: Any = None

        if isinstance(shap_values, np.ndarray) and shap_values.ndim == 3:
            # Shape (n_samples, n_features, n_classes) — XGBoost multi-class
            # Map decision_label to class index using label_mapping
            class_idx = None

            if label_mapping is not None:
                lti = label_mapping.get("label_to_idx") or {}
                if decision_label in lti:
                    class_idx = int(lti[decision_label])

            if class_idx is None:
                classes_attr = getattr(pipeline, "classes_", None)
                if classes_attr is not None:
                    classes_list = list(classes_attr)
                    # Try direct match (string labels)
                    if decision_label in classes_list:
                        class_idx = classes_list.index(decision_label)

            if class_idx is None or class_idx >= shap_values.shape[2]:
                # Use first class as fallback
                class_idx = 0

            sv = shap_values[0, :, class_idx]

        elif isinstance(shap_values, list):
            # Older SHAP: list of arrays, one per class
            classes_attr = getattr(pipeline, "classes_", None)
            class_idx = 0
            if classes_attr is not None:
                classes_list = list(classes_attr)
                if decision_label in classes_list:
                    class_idx = classes_list.index(decision_label)
                    if class_idx >= len(shap_values):
                        class_idx = 0
            sv = shap_values[class_idx][0]
        else:
            # Binary: shape (n_samples, n_features)
            sv = shap_values[0]

        sv = list(sv)
        if len(sv) != len(feature_order):
            return None

        # Build (feature, shap_value) pairs sorted by |shap_value| descending
        pairs = sorted(
            zip(feature_order, sv),
            key=lambda x: abs(x[1]),
            reverse=True,
        )
        top_n = pairs[:5]

        top_signals = []
        for feat, val in top_n:
            plain = _SIGNAL_PLAIN_NAMES.get(feat, feat)
            v = float(val)
            # Direction logic
            if decision_label == "FLAG":
                direction = "toward_flag" if v > 0 else "toward_accept"
            elif decision_label == "ACCEPT":
                direction = "toward_accept" if v > 0 else "toward_flag"
            elif decision_label == "REPAIR":
                direction = "toward_repair" if v > 0 else "away_from_repair"
            else:
                direction = "toward_flag" if v > 0 else "toward_accept"

            top_signals.append({
                "signal": plain,
                "shap_value": round(v, 4),
                "direction": direction,
            })

        # Build plain-English sentence
        if top_signals:
            top = top_signals[0]
            plain_english = (
                f"The primary factor in this decision was '{top['signal']}' "
                f"(SHAP {top['shap_value']:+.3f}, {top['direction'].replace('_', ' ')})."
            )
        else:
            plain_english = f"Decision: {decision_label}."

        return {
            "predicted_class": decision_label,
            "top_signals": top_signals,
            "plain_english": plain_english,
        }
    except Exception as exc:
        logger.debug("SHAP computation failed (non-critical): %s", exc)
        return None


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
    threshold = model.get("threshold")
    classes = model.get("classes")
    flag_idx = model.get("flag_idx", -1)

    try:
        import numpy as np
        vec = _signals_to_feature_vector(signals, feature_order)
        X = np.array([vec], dtype=np.float64)

        # Always get probabilities when available — used for confidence reporting.
        try:
            proba_raw = pipeline.predict_proba(X)[0]
        except Exception:
            proba_raw = None

        confidence: Optional[float] = None
        proba_dict: Optional[dict] = None

        if threshold is not None and classes and flag_idx >= 0:
            proba = proba_raw
            if proba is not None:
                p_flag = proba[flag_idx] if flag_idx < len(proba) else 0
                if p_flag >= threshold:
                    decision_label = "FLAG"
                    confidence = float(proba[flag_idx])
                else:
                    pred_index = int(np.argmax(proba))
                    decision_label = classes[pred_index] if pred_index < len(classes) else "FLAG"
                    confidence = float(proba[pred_index]) if pred_index < len(proba) else None
                proba_dict = {classes[i]: float(proba[i]) for i in range(len(proba)) if i < len(classes)}
            else:
                p_flag = 0
                decision_label = "FLAG"
        else:
            pred_index = int(pipeline.predict(X)[0])
            raw = label_mapping.get("index_to_label") or {}
            index_to_label = {int(k): v for k, v in raw.items()}
            decision_label = index_to_label.get(pred_index, "FLAG")
            if proba_raw is not None:
                cls_list = label_mapping.get("classes") or [
                    index_to_label.get(i, str(i)) for i in range(len(proba_raw))
                ]
                proba_dict = {
                    cls_list[i]: float(proba_raw[i])
                    for i in range(len(proba_raw)) if i < len(cls_list)
                }
                confidence = float(proba_raw[pred_index]) if pred_index < len(proba_raw) else None

        v_label = _model_version()
        logger.info("Decision path: ML (%s model). decision=%s confidence=%.3f",
                    v_label, decision_label, confidence if confidence is not None else -1)
        rationale = "ML decision (%s): %s." % (v_label, decision_label)
        if confidence is not None and confidence < 0.75:
            rationale += " Low confidence decision — recommend human review."

        # SHAP explanation (best-effort, never breaks pipeline)
        shap_explanation = _compute_shap_explanation(pipeline, X, feature_order, decision_label, label_mapping)

        return Decision(
            decision=decision_label,
            rationale=rationale,
            ml_confidence=confidence,
            ml_probabilities=proba_dict,
            shap_explanation=shap_explanation,
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

    ml_decision = predict_decision(signals, model=model, verification_results=verification_results)

    # Post-ML ACCEPT gate: if the ML predicts REPAIR/FLAG but every claim is
    # independently verified against the table (coverage=1, unsupported=0, no
    # hard period/baseline violations), the ML's pnl_identity pessimism is
    # overridden.  Identity failures on incomplete real-world tables (missing
    # rows like G&A expense) are a table-structure artefact, not answer errors.
    from ..core.config import settings as _settings
    if (
        ml_decision.decision in ("REPAIR", "FLAG")
        and getattr(signals, "unsupported_claims_count", 1) == 0
        and getattr(signals, "coverage_ratio", 0.0) >= _settings.coverage_threshold
        and getattr(signals, "pnl_missing_baseline_count", 0) == 0
        and getattr(signals, "pnl_period_strict_mismatch_count", 0) == 0
        and getattr(signals, "scale_mismatch_count", 0) == 0
        and getattr(signals, "period_mismatch_count", 0) == 0
        and getattr(signals, "recomputation_fail_count", 0) == 0
    ):
        logger.info(
            "Decision path: ML post-gate ACCEPT override (all claims verified, coverage=%.2f). "
            "ML predicted %s (likely pnl_identity on incomplete table).",
            signals.coverage_ratio, ml_decision.decision,
        )
        return Decision(
            decision="ACCEPT",
            rationale=(
                "All claims independently verified against table data. "
                "ML P&L identity signal overridden: table may be structurally incomplete. "
                "No unsupported claims, no period or scale violations."
            ),
            ml_confidence=ml_decision.ml_confidence,
            ml_probabilities=ml_decision.ml_probabilities,
            shap_explanation=ml_decision.shap_explanation,
        )

    return ml_decision
