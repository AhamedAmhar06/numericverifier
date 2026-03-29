"""Main FastAPI application."""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .core.logging import setup_logging
from .api import health, verify
from .llm.provider import get_llm_mode, get_openai_api_key_diagnostics

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="NumericVerifier", version="1.0.0")

# Allow local frontend dev server origins so browser preflight (OPTIONS) succeeds.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(verify.router)


@app.on_event("startup")
async def startup_log_llm_mode():
    """Log OPENAI_API_KEY presence and length only (never the key)."""
    diag = get_openai_api_key_diagnostics()
    logger.info("OPENAI_API_KEY present: %s. Length: %s.", diag["key_present"], diag["key_len"])
    mode = get_llm_mode()
    logger.info("Backend running in %s mode (LLM integration %s).", mode, "enabled" if mode == "LLM" else "disabled (stub)")


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "NumericVerifier API"}
