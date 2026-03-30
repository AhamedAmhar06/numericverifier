# How to Run NumericVerifier

## Prerequisites

- Python 3.10+
- pip

## 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

For ML training (optional):

```bash
pip install -r requirements-ml.txt
```

## 2. Start the Server

```bash
cd backend
uvicorn app.main:app --reload --port 8877
```

Swagger UI: http://localhost:8877/docs

## 3. Run Unit Tests

From project root:

```bash
python -m pytest tests/ -v
```

Or run legacy tests too:

```bash
python -m pytest tests/ backend/app/tests/ -v
```

## 4. Generate Evaluation Dataset

```bash
python evaluation/adapters/generate_pnl_cases.py
```

This creates `evaluation/cases_v2.json` (80+ cases).

## 5. Run Evaluation

```bash
python -m evaluation.run_eval --enable_repair
```

Outputs in `evaluation/`:
- `results_raw.jsonl`
- `results_summary.json`
- `confusion_matrix.csv`
- `metrics.md`

## 6. Run Ablation Study

```bash
python -m evaluation.run_ablation
```

Outputs:
- `evaluation/ablation_results.csv`
- `evaluation/ablation_report.md`

## 7. Train ML Model (Optional)

Requires `runs/signals_v2.csv` with labelled data.

```bash
python scripts/train_ml_decision_v2.py
```

Exports to `runs/`:
- `decision_model_v2.joblib`
- `feature_schema_v2.json`
- `label_mapping_v2.json`
- `ml_metrics_v2.json`

To use ML in the server:

```bash
USE_ML_DECIDER=true uvicorn app.main:app --reload --port 8877
```

## 8. Run Evaluation with ML Mode

```bash
python -m evaluation.run_eval --mode ml --enable_repair --config_name ml_full
```
