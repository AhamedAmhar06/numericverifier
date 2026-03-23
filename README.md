# numericverifier

This repository contains tools and services for numeric verification and decisioning.

## Development

If you run the app from the repository root, ensure Python can import the `app` package
which lives under the `backend` directory. Easiest options:

- Change into the `backend` folder and run the server:

```bash
cd backend
USE_ML_DECIDER=true python3 -m uvicorn app.main:app --reload
```

- Or run the small helper from the repo root which ensures `backend/` is on `PYTHONPATH`:

```bash
USE_ML_DECIDER=true python3 dev_run.py
```

Alternatively set `PYTHONPATH=backend` when invoking Uvicorn from the repo root.
