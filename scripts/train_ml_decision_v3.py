"""ML decision model v3 (P&L-only, Logistic Regression, safety-first).

- Logistic Regression only
- Pipeline: SimpleImputer(median) -> StandardScaler -> LogisticRegression
- CalibratedClassifierCV(sigmoid)
- Train on signals_pnl_train.csv, tune on signals_pnl_dev.csv
- Objective: minimize False ACCEPT subject to FLAG recall >= 0.95
- Final report on signals_pnl_test.csv ONLY

Usage:
  python scripts/train_ml_decision_v3.py [--train evaluation/signals_pnl_train.csv] [--output runs/]
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score, recall_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, StandardScaler
import sklearn
import joblib

np.random.seed(42)

FEATURE_COLS = [
    "unsupported_claims_count", "coverage_ratio", "recomputation_fail_count",
    "max_relative_error", "mean_relative_error", "scale_mismatch_count",
    "period_mismatch_count", "ambiguity_count",
    "pnl_table_detected", "pnl_identity_fail_count", "pnl_margin_fail_count",
    "pnl_missing_baseline_count", "pnl_period_strict_mismatch_count",
]


def dataset_hash(df):
    return hashlib.sha256(df.to_csv(index=False).encode()).hexdigest()[:16]


def _predict_with_threshold(proba, classes, flag_idx, threshold):
    """If P(FLAG) >= threshold, predict FLAG; else argmax."""
    if flag_idx < 0:
        return classes[np.argmax(proba)]
    p_flag = proba[flag_idx] if flag_idx < len(proba) else 0
    if p_flag >= threshold:
        return "FLAG"
    return classes[np.argmax(proba)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", default="evaluation/signals_pnl_train.csv")
    parser.add_argument("--dev", default="evaluation/signals_pnl_dev.csv")
    parser.add_argument("--test", default="evaluation/signals_pnl_test.csv")
    parser.add_argument("--output", default="runs/")
    args = parser.parse_args()

    base = Path(__file__).resolve().parent.parent
    train_path = base / args.train
    dev_path = base / args.dev
    test_path = base / args.test
    output_dir = base / args.output
    output_dir.mkdir(exist_ok=True)

    df_train = pd.read_csv(train_path)
    df_dev = pd.read_csv(dev_path)
    assert "decision" in df_train.columns, "Missing 'decision' column"

    available = [c for c in FEATURE_COLS if c in df_train.columns]
    assert len(available) >= 10, f"Too few features: {available}"

    X_train = df_train[available].fillna(0)
    y_train = df_train["decision"].copy()
    X_dev = df_dev[available].fillna(0)
    y_dev = df_dev["decision"].copy()

    # Merge rare classes (< 3 samples) into FLAG for CV stability
    for label in y_train.unique():
        if (y_train == label).sum() < 3 and label != "FLAG":
            print(f"  Merging rare class '{label}' ({(y_train == label).sum()} samples) -> FLAG")
            y_train = y_train.replace(label, "FLAG")
            y_dev = y_dev.replace(label, "FLAG")

    le = LabelEncoder()
    le.fit(list(y_train.unique()) + list(y_dev.unique()))
    y_train_enc = le.transform(y_train)
    y_dev_enc = le.transform(y_dev)

    n_classes = len(le.classes_)
    min_class_count = min((y_train == c).sum() for c in le.classes_)
    cv_folds = min(3, min_class_count)
    if cv_folds < 2:
        cv_folds = 2
    print(f"  Classes: {list(le.classes_)}, min_class_count={min_class_count}, cv_folds={cv_folds}")

    pipe = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("classifier", LogisticRegression(
            solver="lbfgs", max_iter=1000,
            class_weight="balanced", random_state=42,
        )),
    ])
    calibrated = CalibratedClassifierCV(pipe, method="sigmoid", cv=cv_folds)
    calibrated.fit(X_train, y_train_enc)

    classes = list(le.classes_)
    flag_idx = classes.index("FLAG") if "FLAG" in classes else -1

    # Tune threshold on dev: minimize False ACCEPT s.t. FLAG recall >= 0.95
    proba_dev = calibrated.predict_proba(X_dev)
    best_threshold = 0.2
    best_fa = 1.0
    flag_recall_target = 0.95

    for t in np.arange(0.05, 0.95, 0.05):
        preds = [_predict_with_threshold(p, classes, flag_idx, t) for p in proba_dev]
        flag_mask = y_dev == "FLAG"
        flag_recall = (np.sum([p == "FLAG" for p, m in zip(preds, flag_mask) if m]) / flag_mask.sum()
                      if flag_mask.any() else 1.0)

        should_not_accept = (y_dev != "ACCEPT").sum()
        false_accepts = sum(1 for py, pt in zip(preds, y_dev) if py == "ACCEPT" and pt != "ACCEPT")
        fa_rate = false_accepts / should_not_accept if should_not_accept else 0

        if flag_recall >= flag_recall_target and fa_rate <= best_fa:
            best_fa = fa_rate
            best_threshold = t

    # Final evaluation on TEST only
    if test_path.exists():
        df_test = pd.read_csv(test_path)
        X_test = df_test[available].fillna(0)
        y_test = df_test["decision"]
        proba_test = calibrated.predict_proba(X_test)
        preds_test = [_predict_with_threshold(p, classes, flag_idx, best_threshold) for p in proba_test]
        accuracy = accuracy_score(y_test, preds_test)
        report = classification_report(y_test, preds_test, output_dict=True, zero_division=0)
        cm = confusion_matrix(y_test, preds_test, labels=classes)
    else:
        accuracy = 0
        report = {}
        cm = []
        preds_test = []
        y_test = []

    ml_metrics = {
        "model_version": "v3",
        "model_type": "LogisticRegression",
        "calibrated": True,
        "imputer": "median",
        "threshold_tuned": True,
        "flag_recall_target": flag_recall_target,
        "best_threshold": float(best_threshold),
        "accuracy_test": float(accuracy),
        "per_class_test": report,
        "confusion_matrix_test": cm.tolist() if hasattr(cm, "tolist") else cm,
        "class_labels": classes,
        "n_train": int(len(X_train)),
        "n_dev": int(len(X_dev)),
        "n_test": int(len(X_test)) if test_path.exists() else 0,
        "sklearn_version": sklearn.__version__,
        "dataset_hash_train": dataset_hash(df_train),
        "n_features": len(available),
        "features_used": available,
        "threshold_rationale": "Minimize False ACCEPT subject to FLAG recall >= 0.95 on dev",
    }

    joblib.dump({
        "pipeline": calibrated,
        "threshold": best_threshold,
        "label_encoder": le,
        "classes": classes,
        "flag_idx": flag_idx,
    }, output_dir / "decision_model_v3.joblib")

    with open(output_dir / "feature_schema_v3.json", "w") as f:
        json.dump({
            "feature_names": available,
            "feature_order": available,
            "n_features": len(available),
            "schema_version": 3,
        }, f, indent=2)

    with open(output_dir / "ml_metrics_v3.json", "w") as f:
        json.dump(ml_metrics, f, indent=2)

    label_mapping = {
        "index_to_label": {str(i): str(c) for i, c in enumerate(le.classes_)},
        "label_to_index": {c: int(i) for i, c in enumerate(le.classes_)},
        "classes": classes,
    }
    with open(output_dir / "label_mapping_v3.json", "w") as f:
        json.dump(label_mapping, f, indent=2)

    print(f"v3 model trained. Threshold={best_threshold:.2f}")
    print(f"Test accuracy: {accuracy:.4f}")
    print(f"Exported to {output_dir}")


if __name__ == "__main__":
    main()
