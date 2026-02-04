"""Configuration settings for the application."""
import os
from pathlib import Path
from typing import Optional

try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings

# Resolve backend directory via __file__ (works for cd backend && uvicorn and PYTHONPATH=backend uvicorn).
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = _BACKEND_DIR / ".env"

# Load backend/.env explicitly into os.environ. Never load .env.example.
if _ENV_FILE.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_ENV_FILE, override=True)
    except ImportError:
        pass
    else:
        # If dotenv did not set OPENAI_API_KEY (e.g. encoding/parse issue), read line manually.
        if not os.getenv("OPENAI_API_KEY") or not os.getenv("OPENAI_API_KEY").strip():
            with open(_ENV_FILE, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("OPENAI_API_KEY=") and not line.startswith("OPENAI_API_KEY=#"):
                        value = line.split("=", 1)[1].strip().strip('"').strip("'")
                        value = value.replace("\n", "").replace("\r", "").strip()
                        if value:
                            os.environ["OPENAI_API_KEY"] = value
                        break


class Settings(BaseSettings):
    """Application settings."""
    
    app_name: str = "NumericVerifier"
    debug: bool = False
    tolerance: float = 0.01
    coverage_threshold: float = 0.8
    openai_api_key: Optional[str] = None
    
    class Config:
        env_file = str(_ENV_FILE)
        case_sensitive = False


settings = Settings()

