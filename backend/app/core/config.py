"""Configuration settings for the application."""
try:
    from pydantic_settings import BaseSettings
except ImportError:
    # Fallback for older pydantic versions
    from pydantic import BaseSettings


class Settings(BaseSettings):
    """Application settings."""
    
    app_name: str = "NumericVerifier"
    debug: bool = False
    tolerance: float = 0.01
    coverage_threshold: float = 0.8
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

