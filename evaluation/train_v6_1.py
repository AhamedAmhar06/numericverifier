import sys
sys.path.insert(0, '.')

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
    train_test_split, StratifiedKFold, cross_val_score,
    cross_val_predict, learning_curve
)
from sklearn.metrics import (
    confusion_matrix, ConfusionMatrixDisplay,
    classification_report
)
from sklearn.inspection import permutation_importance

os.makedirs('evaluation/plots', exist_ok=True)
os.makedirs('runs', exist_ok=True)

df = pd.read_csv('evaluation/signals_v6_1_complete.csv')

features = [
    'unsupported_claims_count', 'coverage_ratio',
    'max_relative_error', 'mean_relative_error',
    'scale_mismatch_count', 'ambiguity_count',
    'pnl_identity_fail_count', 'pnl_period_strict_mismatch_count',
    'grounding_confidence_score', 'unverifiable_claim_count'
]
label_map = {'ACCEPT': 0, 'FLAG': 1, 'REPAIR': 2}
label_names = ['ACCEPT', 'FLAG', 'REPAIR']

X = df[features].values
y = df['label'].map(label_map).values

print(f"Dataset: {len(df)} rows")
print(f"Labels: {dict(df['label'].value_counts())}")

# 70/15/15 split
X_tv, X_test, y_tv, y_test = train_test_split(X, y, test_size=0.15, stratify=y, random_state=42)
X_train, X_val, y_train, y_val = train_test_split(X_tv, y_tv, test_size=0.15/0.85, stratify=y_tv, random_state=42)
print(f"Split: train={len(X_train)}, val={len(X_val)}, test={len(X_test)}")

model = XGBClassifier(
    n_estimators=100, max_depth=3, learning_rate=0.1,
    subsample=0.8, random_state=42,
    eval_metric='mlogloss', verbosity=0
)
model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)

# CHECK 1: Overfitting
train_acc = model.score(X_train, y_train)
val_acc = model.score(X_val, y_val)
test_acc = model.score(X_test, y_test)
gap = train_acc - val_acc
print(f"\n=== CHECK 1: Overfitting ===")
print(f"Train: {train_acc:.4f}  Val: {val_acc:.4f}  Test: {test_acc:.4f}  Gap: {gap:.4f}")
print("PASS" if gap < 0.08 else "WARNING: overfitting gap > 0.08")

# CHECK 2: 5-fold CV
skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
cv_scores = cross_val_score(model, X, y, cv=skf, scoring='accuracy')
print(f"\n=== CHECK 2: Cross-validation ===")
print(f"Folds: {[round(s,4) for s in cv_scores]}")
print(f"Mean: {cv_scores.mean():.4f}  Std: {cv_scores.std():.4f}")
print(f"V6 was: 0.9892 ± 0.0158")
print(f"Change: {cv_scores.mean()-0.9892:+.4f}")

# CHECK 3 & 4: Confusion matrix + recall
y_pred_cv = cross_val_predict(model, X, y, cv=skf)
cm = confusion_matrix(y, y_pred_cv)
print(f"\n=== CHECK 3+4: Confusion Matrix ===")
print(f"           ACCEPT   FLAG  REPAIR")
for i, lbl in enumerate(label_names):
    print(f"True {lbl:<8} {cm[i,0]:>6}  {cm[i,1]:>5}  {cm[i,2]:>6}")
accept_recall = cm[0,0]/cm[0].sum()
flag_recall = cm[1,1]/cm[1].sum()
repair_recall = cm[2,2]/cm[2].sum()
print(f"ACCEPT recall: {accept_recall:.4f} {'PASS' if accept_recall>=0.95 else 'FAIL'}")
print(f"FLAG recall:   {flag_recall:.4f} {'PASS' if flag_recall>=0.95 else 'FAIL'}")
print(f"REPAIR recall: {repair_recall:.4f}")

# CHECK 5: Permutation importance on test set
perm = permutation_importance(model, X_test, y_test, n_repeats=20, random_state=42)
sorted_idx = perm.importances_mean.argsort()[::-1]
print(f"\n=== CHECK 5: Permutation Importance (top 5) ===")
for i in sorted_idx[:5]:
    print(f"  #{sorted_idx.tolist().index(i)+1} {features[i]:<38} {perm.importances_mean[i]:.4f} ± {perm.importances_std[i]:.4f}")

# CHECK 6: Leakage
print(f"\n=== CHECK 6: Leakage ===")
leakage = False
for fi, feat in enumerate(features):
    Xf = X[:, fi:fi+1]
    m = XGBClassifier(n_estimators=50, max_depth=2, random_state=42, verbosity=0, eval_metric='mlogloss')
    s = cross_val_score(m, Xf, y, cv=3, scoring='accuracy').mean()
    flag = " <- WARNING: possible leakage" if s > 0.95 else ""
    if s > 0.95: leakage = True
    print(f"  {feat:<38} {s:.4f}{flag}")
print("PASS: no leakage" if not leakage else "WARNING: leakage detected")

# PLOTS
# Plot 1: Learning curve
ts, tr_sc, vl_sc = learning_curve(model, X, y, cv=5,
    train_sizes=np.linspace(0.2,1.0,6), scoring='accuracy', random_state=42)
fig, ax = plt.subplots(figsize=(8,5))
ax.plot(ts, tr_sc.mean(axis=1), 'o-', color='steelblue', label='Training')
ax.plot(ts, vl_sc.mean(axis=1), 'o-', color='coral', label='CV')
ax.fill_between(ts, vl_sc.mean(axis=1)-vl_sc.std(axis=1),
                vl_sc.mean(axis=1)+vl_sc.std(axis=1), alpha=0.2, color='coral')
ax.set(xlabel='Training set size', ylabel='Accuracy',
       title='Learning Curve -- XGBoost V6.1', ylim=(0.7,1.05))
ax.legend(); ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig('evaluation/plots/learning_curve_v6_1.png', dpi=150)
plt.close()
print("\nPlot 1: learning_curve_v6_1.png")

# Plot 2: Confusion matrix
fig, ax = plt.subplots(figsize=(7,6))
ConfusionMatrixDisplay(cm, display_labels=label_names).plot(ax=ax, colorbar=False, cmap='Blues')
ax.set_title('Confusion Matrix -- XGBoost V6.1 (5-fold CV)')
plt.tight_layout()
plt.savefig('evaluation/plots/confusion_matrix_v6_1.png', dpi=150)
plt.close()
print("Plot 2: confusion_matrix_v6_1.png")

# Plot 3: Feature importance
imp = model.feature_importances_
sidx = np.argsort(imp)
fig, ax = plt.subplots(figsize=(8,6))
ax.barh([features[i] for i in sidx], imp[sidx], color='steelblue', alpha=0.8)
ax.set(xlabel='XGBoost Feature Importance (gain)', title='Feature Importance -- XGBoost V6.1')
ax.grid(True, axis='x', alpha=0.3)
plt.tight_layout()
plt.savefig('evaluation/plots/feature_importance_v6_1.png', dpi=150)
plt.close()
print("Plot 3: feature_importance_v6_1.png")

# Plot 4: Permutation importance
psorted = perm.importances_mean.argsort()
fig, ax = plt.subplots(figsize=(8,6))
ax.barh([features[i] for i in psorted], perm.importances_mean[psorted],
        xerr=perm.importances_std[psorted], color='coral', alpha=0.8)
ax.set(xlabel='Permutation Importance (accuracy drop)',
       title='Permutation Importance -- XGBoost V6.1 (20 repeats)')
ax.grid(True, axis='x', alpha=0.3)
plt.tight_layout()
plt.savefig('evaluation/plots/permutation_importance_v6_1.png', dpi=150)
plt.close()
print("Plot 4: permutation_importance_v6_1.png")

# DECISION GATE
gate = cv_scores.mean() >= 0.95 and flag_recall >= 0.95 and accept_recall >= 0.95
print(f"\n=== DECISION GATE ===")
print(f"CV mean >= 0.95:      {cv_scores.mean():.4f} {'PASS' if cv_scores.mean()>=0.95 else 'FAIL'}")
print(f"FLAG recall >= 0.95:  {flag_recall:.4f} {'PASS' if flag_recall>=0.95 else 'FAIL'}")
print(f"ACCEPT recall >= 0.95:{accept_recall:.4f} {'PASS' if accept_recall>=0.95 else 'FAIL'}")
print(f"GATE: {'PASSED -- saving V6.1' if gate else 'FAILED -- keeping V6'}")

if gate:
    joblib.dump(model, 'runs/decision_model_v6_1.joblib')
    print("Saved: runs/decision_model_v6_1.joblib")

    schema = {
        "model_version": "v6_1",
        "version": "v6_1",
        "algorithm": "XGBClassifier",
        "citation": "Chen and Guestrin (2016). XGBoost: A Scalable Tree Boosting System. KDD 2016.",
        "n_features": 10,
        "features": features,
        "feature_order": features,
        "feature_names": features,
        "num_features": 10,
        "label_classes": list(label_map.keys()),
        "label_map": label_map,
        "dropped_from_v5": ["near_tolerance_flag", "claim_count"],
        "added_vs_v5b": ["unverifiable_claim_count"],
        "vs_v6": "balanced dataset -- TAT-QA gold ACCEPT cases restored, FLAG capped at 200",
        "training_cases": int(len(df)),
        "training_rows": int(len(df)),
        "training_label_distribution": {k: int(v) for k, v in df['label'].value_counts().items()},
        "label_distribution": {k: int(v) for k, v in df['label'].value_counts().items()}
    }
    with open('runs/feature_schema_v6_1.json', 'w') as f:
        json.dump(schema, f, indent=2)
    print("Saved: runs/feature_schema_v6_1.json")

    metrics = {
        "model_version": "v6_1",
        "algorithm": "XGBClassifier",
        "train_accuracy": float(train_acc),
        "val_accuracy": float(val_acc),
        "test_accuracy": float(test_acc),
        "overfit_gap": float(gap),
        "cv_mean": float(cv_scores.mean()),
        "cv_std": float(cv_scores.std()),
        "cv_scores": [float(s) for s in cv_scores],
        "flag_recall": float(flag_recall),
        "accept_recall": float(accept_recall),
        "repair_recall": float(repair_recall),
        "leakage_detected": leakage,
        "training_rows": int(len(df)),
        "label_distribution": {k: int(v) for k, v in df['label'].value_counts().items()},
        "gate_passed": True,
        "n_features": 10,
        "features": features
    }
    with open('runs/ml_metrics_v6_1.json', 'w') as f:
        json.dump(metrics, f, indent=2)
    print("Saved: runs/ml_metrics_v6_1.json")
    print("\nV6.1 SAVED AS CURRENT MODEL")
else:
    print("\nV6 RETAINED -- V6.1 failed gate")
    import sys; sys.exit(1)
