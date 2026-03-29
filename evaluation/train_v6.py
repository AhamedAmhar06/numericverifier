#!/usr/bin/env python3
"""
XGBoost V6 training script with all 6 diagnostic checks and plots.
"""

import sys
sys.path.insert(0, '/Users/ahamedamhar/Development - campus/numericverifier')

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import joblib
import json
import os
from xgboost import XGBClassifier
from sklearn.model_selection import (
    StratifiedKFold, cross_val_score, cross_val_predict,
    train_test_split, learning_curve
)
from sklearn.metrics import (
    confusion_matrix, ConfusionMatrixDisplay, classification_report
)
from sklearn.inspection import permutation_importance
from sklearn.preprocessing import LabelEncoder

os.makedirs('evaluation/plots', exist_ok=True)
os.makedirs('runs', exist_ok=True)

# ─── Load Data ────────────────────────────────────────────────────────────────
df = pd.read_csv('evaluation/signals_v6_complete.csv')
print(f"Total rows: {len(df)}")
print(f"Label distribution: {df['label'].value_counts().to_dict()}")
print()

features = [
    'unsupported_claims_count', 'coverage_ratio', 'max_relative_error',
    'mean_relative_error', 'scale_mismatch_count', 'ambiguity_count',
    'pnl_identity_fail_count', 'pnl_period_strict_mismatch_count',
    'grounding_confidence_score', 'unverifiable_claim_count'
]
label_names = ['ACCEPT', 'FLAG', 'REPAIR']
label_map = {'ACCEPT': 0, 'FLAG': 1, 'REPAIR': 2}

X = df[features].values
y = df['label'].map(label_map).values

# Check for NaN
if np.isnan(X).any():
    print("WARNING: NaN in features, filling with 0")
    X = np.nan_to_num(X, nan=0.0)

# ─── 70/15/15 stratified split ────────────────────────────────────────────────
X_tv, X_test, y_tv, y_test = train_test_split(
    X, y, test_size=0.15, stratify=y, random_state=42
)
X_train, X_val, y_train, y_val = train_test_split(
    X_tv, y_tv, test_size=0.15/0.85, stratify=y_tv, random_state=42
)

print(f"Split: train={len(X_train)}, val={len(X_val)}, test={len(X_test)}")
print()

# ─── Train Model ──────────────────────────────────────────────────────────────
model = XGBClassifier(
    n_estimators=100,
    max_depth=3,
    learning_rate=0.1,
    subsample=0.8,
    random_state=42,
    eval_metric='mlogloss',
    verbosity=0,
)
model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
print("Model trained successfully.")
print()

# ─── CHECK 1: Overfitting ─────────────────────────────────────────────────────
train_score = model.score(X_train, y_train)
val_score = model.score(X_val, y_val)
test_score = model.score(X_test, y_test)
print("=" * 60)
print("CHECK 1 — Overfitting")
print(f"  Train accuracy : {train_score:.4f}")
print(f"  Val accuracy   : {val_score:.4f}")
print(f"  Test accuracy  : {test_score:.4f}")
overfit_gap = train_score - test_score
print(f"  Overfit gap    : {overfit_gap:.4f} ({'OK' if overfit_gap < 0.05 else 'WARNING'})")
print()

# ─── CHECK 2: 5-fold CV ───────────────────────────────────────────────────────
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
cv_model = XGBClassifier(
    n_estimators=100, max_depth=3, learning_rate=0.1,
    subsample=0.8, random_state=42, eval_metric='mlogloss', verbosity=0,
)
cv_scores = cross_val_score(cv_model, X, y, cv=cv, scoring='accuracy')
cv_mean = cv_scores.mean()
cv_std = cv_scores.std()
print("=" * 60)
print("CHECK 2 — 5-fold Cross-Validation")
print(f"  CV scores : {cv_scores.round(4)}")
print(f"  CV mean   : {cv_mean:.4f} ± {cv_std:.4f}")
print(f"  V5b baseline: 0.9846 ± 0.0224")
print(f"  Gate (>= 0.95): {'PASS' if cv_mean >= 0.95 else 'FAIL'}")
print()

# ─── CHECK 3: Confusion Matrix + Recall ──────────────────────────────────────
y_pred_cv = cross_val_predict(cv_model, X, y, cv=cv)
cm = confusion_matrix(y, y_pred_cv)
print("=" * 60)
print("CHECK 3 — Confusion Matrix & Per-Class Recall")
report = classification_report(
    y, y_pred_cv,
    target_names=label_names,
    output_dict=True
)
for cls in label_names:
    recall = report[cls]['recall']
    prec = report[cls]['precision']
    f1 = report[cls]['f1-score']
    count = report[cls]['support']
    print(f"  {cls:8s}: precision={prec:.4f}, recall={recall:.4f}, f1={f1:.4f}, n={count}")

flag_recall = report['FLAG']['recall']
repair_recall = report['REPAIR']['recall']
print(f"\n  FLAG recall   : {flag_recall:.4f} (gate >= 0.95): {'PASS' if flag_recall >= 0.95 else 'FAIL'}")
print(f"  REPAIR recall : {repair_recall:.4f}")
print()

# ─── CHECK 4: Single-feature leakage check ───────────────────────────────────
print("=" * 60)
print("CHECK 4 — Single-Feature Leakage Check (5-fold CV each)")
leakage_detected = False
for i, feat in enumerate(features):
    feat_model = XGBClassifier(
        n_estimators=50, max_depth=3, random_state=42,
        eval_metric='mlogloss', verbosity=0,
    )
    scores = cross_val_score(feat_model, X[:, i:i+1], y, cv=cv, scoring='accuracy')
    solo_acc = scores.mean()
    flag = " <-- LEAKAGE WARNING" if solo_acc > 0.95 else ""
    print(f"  {feat:42s}: {solo_acc:.4f}{flag}")
    if solo_acc > 0.95:
        leakage_detected = True
print(f"\n  Leakage detected: {'YES — WARNING' if leakage_detected else 'NO'}")
print()

# ─── CHECK 5: Permutation Importance ─────────────────────────────────────────
print("=" * 60)
print("CHECK 5 — Permutation Importance (20 repeats on test set)")
perm_imp = permutation_importance(
    model, X_test, y_test, n_repeats=20, random_state=42, scoring='accuracy'
)
perm_order = np.argsort(perm_imp.importances_mean)[::-1]
for idx in perm_order:
    mean_imp = perm_imp.importances_mean[idx]
    std_imp = perm_imp.importances_std[idx]
    print(f"  {features[idx]:42s}: {mean_imp:.4f} ± {std_imp:.4f}")
print()

# ─── CHECK 6: Class Balance ───────────────────────────────────────────────────
print("=" * 60)
print("CHECK 6 — Class Balance")
total = len(y)
for i, name in enumerate(label_names):
    count = (y == i).sum()
    pct = 100 * count / total
    print(f"  {name:8s}: {count:4d} ({pct:.1f}%)")
print()

# ─── GATE DECISION ────────────────────────────────────────────────────────────
gate_pass = cv_mean >= 0.95 and flag_recall >= 0.95
print("=" * 60)
print("GATE DECISION")
print(f"  CV mean >= 0.95 : {'PASS' if cv_mean >= 0.95 else 'FAIL'} ({cv_mean:.4f})")
print(f"  FLAG recall >= 0.95 : {'PASS' if flag_recall >= 0.95 else 'FAIL'} ({flag_recall:.4f})")
print(f"  Overall: {'PROCEED TO V6' if gate_pass else 'FAIL — DO NOT DEPLOY'}")
print()

# ─── PLOTS ────────────────────────────────────────────────────────────────────

# Plot 1: Learning Curve
print("Generating plots...")
lc_model = XGBClassifier(
    n_estimators=100, max_depth=3, learning_rate=0.1,
    subsample=0.8, random_state=42, eval_metric='mlogloss', verbosity=0,
)
train_sizes, train_scores_lc, val_scores_lc = learning_curve(
    lc_model, X, y, cv=5, scoring='accuracy',
    train_sizes=np.linspace(0.1, 1.0, 10), random_state=42
)
fig, ax = plt.subplots(figsize=(8, 5))
ax.plot(train_sizes, train_scores_lc.mean(axis=1), 'b-o', label='Train')
ax.fill_between(train_sizes,
    train_scores_lc.mean(axis=1) - train_scores_lc.std(axis=1),
    train_scores_lc.mean(axis=1) + train_scores_lc.std(axis=1),
    alpha=0.1, color='blue')
ax.plot(train_sizes, val_scores_lc.mean(axis=1), 'r-o', label='CV Val')
ax.fill_between(train_sizes,
    val_scores_lc.mean(axis=1) - val_scores_lc.std(axis=1),
    val_scores_lc.mean(axis=1) + val_scores_lc.std(axis=1),
    alpha=0.1, color='red')
ax.set_xlabel('Training set size')
ax.set_ylabel('Accuracy')
ax.set_title('Learning Curve — V6 XGBoost')
ax.legend()
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig('evaluation/plots/learning_curve_v6.png', dpi=150)
plt.close()
print("  Saved learning_curve_v6.png")

# Plot 2: Confusion Matrix
fig, ax = plt.subplots(figsize=(7, 6))
disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=label_names)
disp.plot(ax=ax, colorbar=True, cmap='Blues')
ax.set_title(f'Confusion Matrix — V6 (5-fold CV)\nCV={cv_mean:.4f} ± {cv_std:.4f}')
plt.tight_layout()
plt.savefig('evaluation/plots/confusion_matrix_v6.png', dpi=150)
plt.close()
print("  Saved confusion_matrix_v6.png")

# Plot 3: Feature Importance (model native)
fig, ax = plt.subplots(figsize=(10, 6))
importances = model.feature_importances_
order = np.argsort(importances)[::-1]
feat_names_ordered = [features[i] for i in order]
ax.bar(range(len(features)), importances[order], color='steelblue')
ax.set_xticks(range(len(features)))
ax.set_xticklabels(feat_names_ordered, rotation=45, ha='right')
ax.set_ylabel('Feature Importance (gain)')
ax.set_title('Feature Importance — V6 XGBoost')
ax.grid(True, alpha=0.3, axis='y')
plt.tight_layout()
plt.savefig('evaluation/plots/feature_importance_v6.png', dpi=150)
plt.close()
print("  Saved feature_importance_v6.png")

# Plot 4: Signal Separation (top 4 features by importance)
top4_idx = order[:4]
fig, axes = plt.subplots(2, 2, figsize=(12, 8))
for plot_i, feat_idx in enumerate(top4_idx):
    ax = axes[plot_i // 2][plot_i % 2]
    feat_vals = X[:, feat_idx]
    for class_i, class_name in enumerate(label_names):
        mask = y == class_i
        ax.hist(feat_vals[mask], bins=20, alpha=0.6, label=class_name, density=True)
    ax.set_xlabel(features[feat_idx])
    ax.set_ylabel('Density')
    ax.set_title(f'Signal Separation: {features[feat_idx]}')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
plt.suptitle('Signal Separation by Class — V6', fontsize=12)
plt.tight_layout()
plt.savefig('evaluation/plots/signal_separation_v6.png', dpi=150)
plt.close()
print("  Saved signal_separation_v6.png")

# Plot 5: Permutation Importance
fig, ax = plt.subplots(figsize=(10, 6))
perm_means = perm_imp.importances_mean[perm_order]
perm_stds = perm_imp.importances_std[perm_order]
perm_feat_names = [features[i] for i in perm_order]
ax.barh(range(len(features)), perm_means, xerr=perm_stds, color='coral', alpha=0.8)
ax.set_yticks(range(len(features)))
ax.set_yticklabels(perm_feat_names)
ax.set_xlabel('Mean accuracy decrease')
ax.set_title('Permutation Importance — V6 (20 repeats, test set)')
ax.grid(True, alpha=0.3, axis='x')
plt.tight_layout()
plt.savefig('evaluation/plots/permutation_importance_v6.png', dpi=150)
plt.close()
print("  Saved permutation_importance_v6.png")

# Plot 6: SHAP (try XGBoost native, fallback to permutation)
try:
    import shap
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_test)

    # For multiclass, shap_values is a list; pick FLAG (class 1)
    if isinstance(shap_values, list):
        sv_flag = shap_values[1]
    else:
        sv_flag = shap_values[:, :, 1] if shap_values.ndim == 3 else shap_values

    # Summary plot for FLAG class
    fig, ax = plt.subplots(figsize=(10, 6))
    mean_abs_shap = np.abs(sv_flag).mean(axis=0)
    shap_order = np.argsort(mean_abs_shap)[::-1]
    shap_feat_names = [features[i] for i in shap_order]
    ax.barh(range(len(features)), mean_abs_shap[shap_order], color='mediumpurple')
    ax.set_yticks(range(len(features)))
    ax.set_yticklabels(shap_feat_names)
    ax.set_xlabel('Mean |SHAP value|')
    ax.set_title('SHAP Feature Importance — V6 (FLAG class)')
    ax.grid(True, alpha=0.3, axis='x')
    plt.tight_layout()
    plt.savefig('evaluation/plots/shap_flag_v6.png', dpi=150)
    plt.close()
    print("  Saved shap_flag_v6.png (SHAP native)")
    shap_used = True
except Exception as e:
    print(f"  SHAP failed ({e}), using permutation importance as substitute")
    # Just copy the permutation importance plot
    import shutil
    shutil.copy('evaluation/plots/permutation_importance_v6.png',
                'evaluation/plots/shap_flag_v6.png')
    print("  Saved shap_flag_v6.png (permutation substitute)")
    shap_used = False

print()

# ─── SAVE MODEL ARTIFACTS ─────────────────────────────────────────────────────
if gate_pass:
    print("=" * 60)
    print("SAVING MODEL ARTIFACTS (gate passed)")

    # Save model
    joblib.dump(model, 'runs/decision_model_v6.joblib')
    print("  Saved runs/decision_model_v6.joblib")

    # Save feature schema
    feature_schema = {
        "model_version": "v6",
        "features": features,
        "num_features": len(features),
        "label_classes": label_names,
        "label_map": label_map,
        "training_rows": len(df),
        "training_label_distribution": df['label'].value_counts().to_dict(),
    }
    with open('runs/feature_schema_v6.json', 'w') as f:
        json.dump(feature_schema, f, indent=2)
    print("  Saved runs/feature_schema_v6.json")

    # Save ML metrics
    ml_metrics = {
        "model_version": "v6",
        "algorithm": "XGBClassifier",
        "cv_folds": 5,
        "cv_mean": float(cv_mean),
        "cv_std": float(cv_std),
        "cv_scores": cv_scores.tolist(),
        "train_accuracy": float(train_score),
        "val_accuracy": float(val_score),
        "test_accuracy": float(test_score),
        "overfit_gap": float(overfit_gap),
        "flag_recall": float(flag_recall),
        "repair_recall": float(repair_recall),
        "accept_recall": float(report['ACCEPT']['recall']),
        "leakage_detected": leakage_detected,
        "training_rows": len(df),
        "label_distribution": df['label'].value_counts().to_dict(),
        "gate_passed": gate_pass,
        "n_features": len(features),
        "features": features,
        "hyperparams": {
            "n_estimators": 100,
            "max_depth": 3,
            "learning_rate": 0.1,
            "subsample": 0.8,
        }
    }
    with open('runs/ml_metrics_v6.json', 'w') as f:
        json.dump(ml_metrics, f, indent=2)
    print("  Saved runs/ml_metrics_v6.json")

    # Update model registry
    registry_path = 'runs/model_registry.json'
    if os.path.exists(registry_path):
        with open(registry_path) as f:
            registry = json.load(f)
    else:
        registry = {"models": {}, "current": None}

    # Mark v5b as deprecated
    if "v5b" in registry.get("models", {}):
        registry["models"]["v5b"]["status"] = "deprecated"

    # Add v6
    registry.setdefault("models", {})["v6"] = {
        "version": "v6",
        "algorithm": "XGBClassifier",
        "cv_mean": float(cv_mean),
        "cv_std": float(cv_std),
        "flag_recall": float(flag_recall),
        "training_rows": len(df),
        "status": "active",
        "artifacts": {
            "model": "decision_model_v6.joblib",
            "schema": "feature_schema_v6.json",
            "label_mapping": "label_mapping_v5.json",
        }
    }
    registry["current"] = "v6"

    with open(registry_path, 'w') as f:
        json.dump(registry, f, indent=2)
    print(f"  Updated {registry_path}")

    print()
    print("=" * 60)
    print("V6 TRAINING COMPLETE")
    print(f"  CV: {cv_mean:.4f} ± {cv_std:.4f}")
    print(f"  FLAG recall: {flag_recall:.4f}")
    print(f"  Test accuracy: {test_score:.4f}")
    print("=" * 60)
else:
    print("=" * 60)
    print("GATE FAILED — model NOT saved")
    print(f"  CV mean: {cv_mean:.4f} (need >= 0.95)")
    print(f"  FLAG recall: {flag_recall:.4f} (need >= 0.95)")
    sys.exit(1)
