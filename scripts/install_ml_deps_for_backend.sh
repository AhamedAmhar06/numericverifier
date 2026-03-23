#!/bin/sh
# One-time: install joblib/sklearn/numpy so the backend can load the ML model when USE_ML_DECIDER=true.
# Run from project root:  ./scripts/install_ml_deps_for_backend.sh
# Then start the backend (from backend/):  USE_ML_DECIDER=true python3 -m uvicorn app.main:app --reload

set -e
cd "$(dirname "$0")/.."
echo "Installing ML deps into .pip-ml (for backend to load decision_model_v2.joblib)..."
pip3 install -r requirements-ml.txt --target .pip-ml
echo "Done. Start backend with USE_ML_DECIDER=true; it will use .pip-ml if joblib is not in your Python."
