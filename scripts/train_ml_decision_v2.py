"""ML decision model training script (v2, P&L-only).

Improvements over v1:
- schema_version removed from feature vector (metadata-only)
- SimpleImputer added to pipeline
- 5-fold stratified cross-validation
- CalibratedClassifierCV to minimize false ACCEPT
- Training metadata: sklearn version, dataset hash

Usage:
    python scripts/train_ml_decision_v2.py [--data runs/signals_v2.csv] [--output runs/]
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, classification_report, confusion_matrix, f1_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, StandardScaler
import sklearn
import joblib

np.random.seed(42)

# 13 features (schema_version removed)
FEATURE_COLS = [
    "unsupported_claims_count", "coverage_ratio", "recomputation_fail_count",
    "max_relative_error", "mean_relative_error", "scale_mismatch_count",
    "period_mismatch_count", "ambiguity_count",
    "pnl_table_detected", "pnl_identity_fail_count", "pnl_margin_fail_count",
    "pnl_missing_baseline_count", "pnl_period_strict_mismatch_count",
]


def dataset_hash(df: pd.DataFrame) -> str:
    return hashlib.sha256(df.to_csv(index=False).encode()).hexdigest()[:16]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="runs/signals_v2.csv")
    parser.add_argument("--output", default="runs/")
    args = parser.parse_args()

    data_path = Path(args.data)
    output_dir = Path(args.output)
    output_dir.mkdir(exist_ok=True)

    df = pd.read_csv(data_path)
    assert "decision" in df.columns, "Missing 'decision' column"

    # Use only the 13 features (drop schema_version)
    available = [c for c in FEATURE_COLS if c in df.columns]
    assert len(available) >= 10, f"Too few features found: {available}"
    X = df[available].copy()
    y = df["decision"].copy()

    print(f"Dataset: {len(df)} rows, {len(available)} features")
    print(f"Class distribution:\n{y.value_counts()}")

    le = LabelEncoder()
    y_encoded = le.fit_transform(y)

    X_train, X_val, y_train, y_val = train_test_split(
        X, y_encoded, test_size=0.2, random_state=42, stratify=y_encoded,
    )

    # Pipeline: imputer -> scaler -> classifier
    lr_pipe = Pipeline([
        ("imputer", SimpleImputer(strategy="constant", fill_value=0)),
        ("scaler", StandardScaler()),
        ("classifier", LogisticRegression(
            multi_class="multinomial", solver="lbfgs", max_iter=1000,
            class_weight="balanced", random_state=42,
        )),
    ])
    rf_pipe = Pipeline([
        ("imputer", SimpleImputer(strategy="constant", fill_value=0)),
        ("scaler", StandardScaler()),
        ("classifier", RandomForestClassifier(
            n_estimators=100, max_depth=10, min_samples_split=5, min_samples_leaf=2,
            class_weight="balanced", random_state=42, n_jobs=-1,
        )),
    ])

    # 5-fold stratified CV
    cv = StratifiedKFold(n_splits=min(5, min(np.bincount(y_train))), shuffle=True, random_state=42)

    lr_cv_scores = cross_val_score(lr_pipe, X_train, y_train, cv=cv, scoring="f1_macro")
    rf_cv_scores = cross_val_score(rf_pipe, X_train, y_train, cv=cv, scoring="f1_macro")
    print(f"LR CV macro F1: {lr_cv_scores.mean():.4f} +/- {lr_cv_scores.std():.4f}")
    print(f"RF CV macro F1: {rf_cv_scores.mean():.4f} +/- {rf_cv_scores.std():.4f}")

    # Select best by CV mean F1
    if rf_cv_scores.mean() >= lr_cv_scores.mean():
        best_pipe = rf_pipe
        best_name = "RandomForest"
        best_cv = rf_cv_scores
    else:
        best_pipe = lr_pipe
        best_name = "LogisticRegression"
        best_cv = lr_cv_scores

    best_pipe.fit(X_train, y_train)

    # Calibrate probabilities (sigmoid method)
    calibrated = CalibratedClassifierCV(best_pipe, method="sigmoid", cv=3)
    calibrated.fit(X_train, y_train)

    # Evaluate on validation
    y_pred = calibrated.predict(X_val)
    accuracy = accuracy_score(y_val, y_pred)
    macro_f1 = f1_score(y_val, y_pred, average="macro")
    report = classification_report(y_val, y_pred, target_names=le.classes_, output_dict=True)
    cm = confusion_matrix(y_val, y_pred)

    print(f"\nBest model: {best_name}")
    print(f"Validation accuracy: {accuracy:.4f}")
    print(f"Validation macro F1: {macro_f1:.4f}")
    print(classification_report(y_val, y_pred, target_names=le.classes_))

    # Export artifacts
    joblib.dump(calibrated, output_dir / "decision_model_v2.joblib")

    feature_schema = {
        "feature_names": available,
        "feature_order": available,
        "n_features": len(available),
        "schema_version": 2,
        "note": "schema_version field excluded from features; used as metadata assertion only",
    }
    with open(output_dir / "feature_schema_v2.json", "w") as f:
        json.dump(feature_schema, f, indent=2)

    label_mapping = {
        "index_to_label": {str(i): str(l) for i, l in enumerate(le.classes_)},
        "label_to_index": {str(l): int(i) for i, l in enumerate(le.classes_)},
        "classes": le.classes_.tolist(),
    }
    with open(output_dir / "label_mapping_v2.json", "w") as f:
        json.dump(label_mapping, f, indent=2)

    ml_metrics = {
        "model_name": best_name,
        "calibrated": True,
        "accuracy": float(accuracy),
        "macro_f1": float(macro_f1),
        "cv_mean_f1": float(best_cv.mean()),
        "cv_std_f1": float(best_cv.std()),
        "per_class": {label: {k: float(v) for k, v in metrics.items()}
                      for label, metrics in report.items() if label in le.classes_},
        "confusion_matrix": cm.tolist(),
        "class_labels": le.classes_.tolist(),
        "n_train": int(len(X_train)),
        "n_val": int(len(X_val)),
        "class_distribution": y.value_counts().to_dict(),
        "random_state": 42,
        "test_size": 0.2,
        "sklearn_version": sklearn.__version__,
        "dataset_hash": dataset_hash(df),
        "n_features": len(available),
        "features_used": available,
    }
    with open(output_dir / "ml_metrics_v2.json", "w") as f:
        json.dump(ml_metrics, f, indent=2)

    print(f"\nExported to {output_dir}:")
    print("  decision_model_v2.joblib")
    print("  feature_schema_v2.json")
    print("  label_mapping_v2.json")
    print("  ml_metrics_v2.json")


if __name__ == "__main__":
    main()
