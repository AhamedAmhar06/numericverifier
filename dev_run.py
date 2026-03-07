#!/usr/bin/env python3
"""
Run the development server from the repository root so Python can import
`app` (which lives under the `backend` directory).

Usage:
    python dev_run.py

This inserts `backend/` on `sys.path` and starts Uvicorn with reload.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
BACKEND_PATH = ROOT / "backend"

if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

try:
    import uvicorn
except ImportError:
    print("Uvicorn is not installed. Install backend dependencies with:")
    print("  python -m pip install -r backend/requirements.txt")
    print("(Use the same Python that runs this script.)")
    sys.exit(1)

if __name__ == "__main__":
    # Preserve existing env behavior; user can still set USE_ML_DECIDER.
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
