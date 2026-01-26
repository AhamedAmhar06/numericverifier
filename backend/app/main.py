"""Main FastAPI application."""
from fastapi import FastAPI
from .core.logging import setup_logging
from .api import health, verify

# Setup logging
setup_logging()

# Create FastAPI app
app = FastAPI(title="NumericVerifier", version="1.0.0")

# Include routers
app.include_router(health.router)
app.include_router(verify.router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "NumericVerifier API"}

