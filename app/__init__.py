"""Top-level `app` package shim.

This package makes `import app` resolve to `backend/app` when running from
the repository root, so commands like `python -m uvicorn app.main:app` work
without modifying `PYTHONPATH` or installing the package.
"""
from pathlib import Path
import os

# Compute the absolute path to backend/app relative to this file.
_BACKEND_APP = Path(__file__).resolve().parent.parent / "backend" / "app"
_backend_app_path = str(_BACKEND_APP)

# Prepend to package __path__ so submodule imports (e.g., app.main) find files
# in backend/app first.
__path__.insert(0, _backend_app_path)
