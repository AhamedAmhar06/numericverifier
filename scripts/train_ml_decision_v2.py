#!/usr/bin/env python3
"""
Train ML decision model for NumericVerifier (P&L-only, schema v2).

- Loads runs/signals_v2.csv only.
- Features = all signal columns except decision (fixed order).
- Label = decision (ACCEPT / REPAIR / FLAG).
- Stratified 80/20, class_weight balanced, macro F1 selection.
- Exports artifacts to runs/ (same as ml_decision_model.ipynb).

Canonical way to update the model: run ml_decision_model.ipynb from top to bottom
(interactive, same logic). This script is an alternative for headless/CI runs.

Run from project root:
  pip install pandas numpy scikit-learn joblib
  python scripts/train_ml_decision_v2.py

Requires: pandas, numpy, scikit-learn, joblib.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, StandardScaler

# -----------------------------------------------------------------------------
# Schema v2: fixed feature order (must match VerifierSignals / CSV)
# -----------------------------------------------------------------------------
FEATURE_COLS_V2 = [
    "unsupported_claims_count",
    "coverage_ratio",
    "recomputation_fail_count",
    "max_relative_error",
    "mean_relative_error",
    "scale_mismatch_count",
    "period_mismatch_count",
    "ambiguity_count",
    "schema_version",
    "pnl_table_detected",
    "pnl_identity_fail_count",
    "pnl_margin_fail_count",
    "pnl_missing_baseline_count",
    "pnl_period_strict_mismatch_count",
]
LABEL_COL = "decision"
EXPECTED_V2_COLUMNS = set(FEATURE_COLS_V2) | {LABEL_COL}

RANDOM_STATE = 42
TEST_SIZE = 0.2


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def main() -> int:
    runs_dir = project_root() / "runs"
    signals_path = runs_dir / "signals_v2.csv"
    if not signals_path.exists():
        print(f"ERROR: {signals_path} not found. Run from project root.", file=sys.stderr)
        return 1

    # -------------------------------------------------------------------------
    # 1) Data loading
    # -------------------------------------------------------------------------
    df = pd.read_csv(signals_path)
    actual_cols = set(df.columns)
    if actual_cols != EXPECTED_V2_COLUMNS:
        missing = EXPECTED_V2_COLUMNS - actual_cols
        extra = actual_cols - EXPECTED_V2_COLUMNS
        if missing:
            print(f"ERROR: signals_v2.csv missing columns: {missing}", file=sys.stderr)
        if extra:
            print(f"ERROR: signals_v2.csv unexpected columns: {extra}", file=sys.stderr)
        return 1

    for col in FEATURE_COLS_V2:
        if col not in df.columns:
            print(f"ERROR: feature column missing: {col}", file=sys.stderr)
            return 1
    if LABEL_COL not in df.columns:
        print(f"ERROR: label column missing: {LABEL_COL}", file=sys.stderr)
        return 1

    X = df[FEATURE_COLS_V2].astype(np.float64)
    y = df[LABEL_COL].astype(str).str.strip()

    # Valid labels only
    valid = y.isin({"ACCEPT", "REPAIR", "FLAG"})
    if not valid.all():
        invalid = y[~valid].unique().tolist()
        print(f"ERROR: invalid decision values: {invalid}", file=sys.stderr)
        return 1

    # -------------------------------------------------------------------------
    # 2) Class distribution (before split)
    # -------------------------------------------------------------------------
    class_counts = y.value_counts()
    print("Class distribution (before split):")
    for label, count in class_counts.items():
        pct = 100 * count / len(y)
        print(f"  {label}: {count} ({pct:.1f}%)")
    print()

    # -------------------------------------------------------------------------
    # 3) Stratified train / validation split
    # -------------------------------------------------------------------------
    label_encoder = LabelEncoder()
    y_encoded = label_encoder.fit_transform(y)

    X_train, X_val, y_train, y_val = train_test_split(
        X, y_encoded, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y_encoded
    )
    print(f"Train size: {len(X_train)}, Validation size: {len(X_val)}")
    print()

    # -------------------------------------------------------------------------
    # 4) Models: Logistic Regression + Random Forest (class_weight balanced)
    # -------------------------------------------------------------------------
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled = scaler.transform(X_val)

    lr = LogisticRegression(
        multi_class="multinomial",
        solver="lbfgs",
        max_iter=1000,
        class_weight="balanced",
        random_state=RANDOM_STATE,
    )
    lr.fit(X_train_scaled, y_train)
    lr_pred = lr.predict(X_val_scaled)
    lr_f1 = f1_score(y_val, lr_pred, average="macro")

    rf = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        min_samples_split=5,
        min_samples_leaf=2,
        class_weight="balanced",
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    rf.fit(X_train_scaled, y_train)
    rf_pred = rf.predict(X_val_scaled)
    rf_f1 = f1_score(y_val, rf_pred, average="macro")

    if rf_f1 >= lr_f1:
        best_model = rf
        best_name = "RandomForest"
    else:
        best_model = lr
        best_name = "LogisticRegression"
    best_f1 = max(lr_f1, rf_f1)
    best_pred = best_model.predict(X_val_scaled)

    print(f"Best model by macro F1: {best_name} (macro F1 = {best_f1:.4f})")
    print()

    # -------------------------------------------------------------------------
    # 5) Metrics: macro F1, per-class precision/recall, confusion matrix
    # -------------------------------------------------------------------------
    class_names = list(label_encoder.classes_)
    report = classification_report(
        y_val, best_pred, target_names=class_names, output_dict=True
    )
    cm = confusion_matrix(y_val, best_pred)
    accuracy = (best_pred == y_val).mean()

    # -------------------------------------------------------------------------
    # 6) Export artifacts to runs/
    # -------------------------------------------------------------------------
    pipeline = Pipeline([
        ("scaler", scaler),
        ("classifier", best_model),
    ])
    joblib.dump(pipeline, runs_dir / "decision_model_v2.joblib")
    print("Exported: runs/decision_model_v2.joblib")

    feature_schema = {
        "feature_names": FEATURE_COLS_V2,
        "feature_order": FEATURE_COLS_V2,
        "n_features": len(FEATURE_COLS_V2),
        "schema_version": 2,
    }
    with open(runs_dir / "feature_schema_v2.json", "w") as f:
        json.dump(feature_schema, f, indent=2)
    print("Exported: runs/feature_schema_v2.json")

    # index -> label (e.g. 0 -> ACCEPT, 1 -> REPAIR, 2 -> FLAG)
    label_mapping = {
        "index_to_label": {int(i): str(l) for i, l in enumerate(label_encoder.classes_)},
        "label_to_index": {str(l): int(i) for i, l in enumerate(label_encoder.classes_)},
        "classes": list(label_encoder.classes_),
    }
    with open(runs_dir / "label_mapping_v2.json", "w") as f:
        json.dump(label_mapping, f, indent=2)
    print("Exported: runs/label_mapping_v2.json")

    metrics = {
        "model_name": best_name,
        "accuracy": float(accuracy),
        "macro_f1": float(best_f1),
        "per_class": {
            name: {
                "precision": float(report[name]["precision"]),
                "recall": float(report[name]["recall"]),
                "f1-score": float(report[name]["f1-score"]),
                "support": int(report[name]["support"]),
            }
            for name in class_names
        },
        "confusion_matrix": cm.tolist(),
        "class_labels": class_names,
        "n_train": int(len(X_train)),
        "n_val": int(len(X_val)),
        "class_distribution": class_counts.to_dict(),
        "random_state": RANDOM_STATE,
        "test_size": TEST_SIZE,
    }
    with open(runs_dir / "ml_metrics_v2.json", "w") as f:
        json.dump(metrics, f, indent=2)
    print("Exported: runs/ml_metrics_v2.json")

    # -------------------------------------------------------------------------
    # 7) ml_readme_v2.md
    # -------------------------------------------------------------------------
    readme = _readme_content(best_name, best_f1, metrics, class_names, cm)
    with open(runs_dir / "ml_readme_v2.md", "w") as f:
        f.write(readme)
    print("Exported: runs/ml_readme_v2.md")

    print()
    print("--- Summary ---")
    print(f"Macro F1: {best_f1:.4f}")
    print("Per-class precision/recall: see runs/ml_metrics_v2.json")
    print("Confusion matrix:")
    print(cm)
    return 0


def _readme_content(
    best_name: str,
    best_f1: float,
    metrics: dict,
    class_names: list,
    cm: np.ndarray,
) -> str:
    return f"""# ML Decision Model v2 (P&L-only)

## Role and limits

- **What the model does:** Predicts ACCEPT / REPAIR / FLAG from verifier signals only (no raw text, no question, no evidence).
- **When it is used:** Only in the "soft region" after hard safety gates. If any of the following are true, the system returns FLAG immediately and the model is **not** called:
  - `pnl_missing_baseline_count > 0` (YoY/baseline missing)
  - `pnl_period_strict_mismatch_count > 0` (period mismatch)
  - `pnl_table_detected == 0` (non-P&L)
- **Why no raw text:** Decisions are based solely on numeric signals produced by the P&L verifier. Using question or LLM output would introduce leakage and non-reproducibility; the design keeps inputs to the decider as structured, auditable signals only.
- **Why hard rules remain:** Finance verification requires that certain conditions (missing baseline, wrong period, non-P&L table) always result in FLAG. The ML model is not allowed to override these; it only decides in the remaining cases.
- **Safety:** This design is appropriate for finance verification because (1) high-risk cases are always FLAG by rule, (2) the model sees only signals, and (3) if the model is unavailable, the system falls back to the rule-based decision.

## Training

- **Dataset:** `runs/signals_v2.csv` (schema v2, P&L-only; each row from a real LLM + verifier run).
- **Features:** All signal columns in fixed order (see `feature_schema_v2.json`). No `decision` or derived rule logic as input.
- **Label:** `decision` (ACCEPT / REPAIR / FLAG), produced deterministically by `decision_rules.py` at data collection time.
- **Split:** Stratified 80/20 train/validation. Class weight balanced.
- **Models:** Multinomial Logistic Regression and Random Forest; best selected by macro F1.

## Artifacts

| File | Purpose |
|------|---------|
| `decision_model_v2.joblib` | Trained pipeline (StandardScaler + classifier) |
| `feature_schema_v2.json` | Ordered feature list for inference |
| `label_mapping_v2.json` | Index ↔ ACCEPT/REPAIR/FLAG |
| `ml_metrics_v2.json` | Metrics and confusion matrix |
| `ml_readme_v2.md` | This file |

## This run

- **Best model:** {best_name}
- **Macro F1:** {best_f1:.4f}
- **Classes:** {class_names}
- **Confusion matrix (val):**
```
{_fmt_cm(cm, class_names)}
```

## Runtime

- Set `USE_ML_DECIDER=true` to use the ML model after hard gates.
- Set `USE_ML_DECIDER=false` (default) for rule-based decision only.
- If the model file is missing or prediction fails, the backend falls back to rule-based decision.
"""


def _fmt_cm(cm: np.ndarray, labels: list) -> str:
    lines = ["  " + "  ".join([f"{l:>6}" for l in labels])]
    for i, row in enumerate(cm):
        lines.append(f"{labels[i]:>6}  " + "  ".join(f"{v:>6}" for v in row))
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
