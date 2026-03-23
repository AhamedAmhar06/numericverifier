"""Generate P&L evaluation figures (matplotlib only).

Figures:
  - confusion matrix (P&L test)
  - false ACCEPT before/after repair (if LLM eval ran)
  - ablation deltas bar chart
  - LR coefficient plot (if v3 model exists)

Usage:
  python -m evaluation.generate_figures_pnl [--output_dir evaluation/figures]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
except ImportError:
    print("matplotlib/numpy required: pip install matplotlib numpy")
    sys.exit(1)


def fig_confusion_matrix(base: Path, output_dir: Path):
    """Confusion matrix from P&L test gold results (expected=ACCEPT for all)."""
    path = base / "evaluation" / "tatqa_pnl_gold_test_signals.csv"
    if not path.exists():
        return
    import csv
    from collections import defaultdict
    rows = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
    if not rows:
        return
    labels = ["ACCEPT", "REPAIR", "FLAG"]
    cm = defaultdict(lambda: defaultdict(int))
    for r in rows:
        actual = r.get("decision", "")
        if actual in labels:
            cm["ACCEPT"][actual] += 1  # gold eval: all expected ACCEPT
    mat = [[cm[exp].get(act, 0) for act in labels] for exp in labels]
    fig, ax = plt.subplots(figsize=(5, 4))
    im = ax.imshow(mat, cmap="Blues")
    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels)
    ax.set_yticklabels(labels)
    for i in range(len(labels)):
        for j in range(len(labels)):
            ax.text(j, i, str(mat[i][j]), ha="center", va="center")
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Expected")
    ax.set_title("P&L Test Confusion Matrix (Gold Eval)")
    plt.tight_layout()
    plt.savefig(output_dir / "confusion_matrix_pnl.png", dpi=150)
    plt.close()


def fig_false_accept_repair(base: Path, output_dir: Path):
    """False ACCEPT before/after repair from LLM eval."""
    path = base / "evaluation" / "tatqa_pnl_llm_metrics.json"
    if not path.exists():
        return
    with open(path) as f:
        m = json.load(f)
    before = m.get("false_accept_before", 0)
    after = m.get("false_accept_after", 0)
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.bar(["Before Repair", "After Repair"], [before, after], color=["#e74c3c", "#27ae60"])
    ax.set_ylabel("False ACCEPT count")
    ax.set_title("False ACCEPT Before/After Repair (LLM Eval)")
    plt.tight_layout()
    plt.savefig(output_dir / "false_accept_repair.png", dpi=150)
    plt.close()


def fig_ablation_deltas(base: Path, output_dir: Path):
    """Ablation deltas bar chart."""
    path = base / "evaluation" / "ablation_pnl_results.csv"
    if not path.exists():
        path = base / "evaluation" / "ablation_results.csv"
    if not path.exists():
        return
    import csv
    rows = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
    if not rows:
        return
    baseline_fa = float(rows[0].get("false_accept_rate", 0))
    configs = [r["config"] for r in rows]
    deltas = [float(r.get("false_accept_rate", 0)) - baseline_fa for r in rows]
    fig, ax = plt.subplots(figsize=(8, 4))
    colors = ["#3498db" if d <= 0 else "#e74c3c" for d in deltas]
    ax.barh(configs, deltas, color=colors)
    ax.axvline(0, color="black", linewidth=0.5)
    ax.set_xlabel("False ACCEPT rate delta (vs baseline)")
    ax.set_title("Ablation: False ACCEPT Delta")
    plt.tight_layout()
    plt.savefig(output_dir / "ablation_deltas.png", dpi=150)
    plt.close()


def fig_lr_coefficients(base: Path, output_dir: Path):
    """LR coefficient plot from v3 model."""
    path = base / "runs" / "decision_model_v3.joblib"
    if not path.exists():
        return
    try:
        import joblib
    except ImportError:
        return
    loaded = joblib.load(path)
    pipe = loaded.get("pipeline")
    if pipe is None:
        return
    # CalibratedClassifierCV wraps base estimator
    base_est = pipe
    if hasattr(pipe, "calibrated_classifiers_"):
        base_est = pipe.calibrated_classifiers_[0]
        if isinstance(base_est, (list, tuple)):
            base_est = base_est[0]
    lr = base_est.named_steps.get("classifier", base_est) if hasattr(base_est, "named_steps") else base_est
    if not hasattr(lr, "coef_"):
        return
    coef = lr.coef_
    schema_path = base / "runs" / "feature_schema_v3.json"
    if schema_path.exists():
        with open(schema_path) as f:
            schema = json.load(f)
        names = schema.get("feature_order", schema.get("feature_names", []))
    else:
        names = [f"f{i}" for i in range(coef.shape[1])]
    # Use first class (or FLAG) coefficients
    idx = 0
    if coef.shape[0] > 1 and hasattr(lr, "classes_"):
        try:
            idx = list(lr.classes_).index("FLAG")
        except ValueError:
            pass
    c = coef[idx] if idx < len(coef) else coef[0]
    fig, ax = plt.subplots(figsize=(8, 5))
    y_pos = range(len(names))
    ax.barh(y_pos, c, color=["#27ae60" if x > 0 else "#e74c3c" for x in c])
    ax.set_yticks(y_pos)
    ax.set_yticklabels(names, fontsize=8)
    ax.set_xlabel("Coefficient")
    ax.set_title("LR v3 Coefficients")
    plt.tight_layout()
    plt.savefig(output_dir / "lr_coefficients_v3.png", dpi=150)
    plt.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output_dir", default="evaluation/figures")
    args = parser.parse_args()

    base = Path(__file__).resolve().parent.parent
    output_dir = base / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    fig_confusion_matrix(base, output_dir)
    fig_false_accept_repair(base, output_dir)
    fig_ablation_deltas(base, output_dir)
    fig_lr_coefficients(base, output_dir)

    print(f"Figures written to {output_dir}")


if __name__ == "__main__":
    main()
