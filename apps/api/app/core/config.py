import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# Determine which env file to load based on APP_ENV
# "local" (default) -> .env.local, "prod" -> .env.prod
_app_env = os.getenv("APP_ENV", "local")
# Load .env first, then override with environment-specific file
_env_file = (".env", f".env.{_app_env}")


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=_env_file,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_name: str = "Kureita API"
    debug: bool = False
    api_base_url: str = "http://localhost:8000"  # Public URL of the API

    # CORS (comma-separated string, use cors_origins_list property for list)
    cors_origins: str = "http://localhost:3000,https://app.kureita.com"

    @property
    def cors_origins_list(self) -> list[str]:
        """Get CORS origins as a list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    # MongoDB
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_database: str = "kureita"

    # AI/LLM APIs
    openai_api_key: str = ""
    gemini_api_key: str = ""  # Can also use GOOGLE_API_KEY
    google_api_key: str = ""  # Alternative to GEMINI_API_KEY
    anthropic_api_key: str = ""
    use_mock_veo: bool = True  # Set to False to use real Veo API
    runware_api_key: str = ""  # For unified image/video/audio generation
    kling_access_key: str = ""
    kling_secret_key: str = ""
    byteplus_access_key: str = ""
    byteplus_secret_key: str = ""

    @property
    def google_ai_key(self) -> str:
        """Get the Google API key (prefers GEMINI_API_KEY, falls back to GOOGLE_API_KEY)."""
        return self.gemini_api_key or self.google_api_key

    # Media Generation (Optional - Veo 3.1 includes native audio)
    elevenlabs_api_key: str = ""  # Optional: for custom voiceovers
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"

    # AWS (S3, SES, and other AWS services)
    storage_type: str = "local"  # "local" or "s3"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"
    s3_bucket: str = "kureita-assets"
    s3_endpoint: str = ""  # Optional: for S3-compatible services (R2, MinIO)

    # Remotion rendering service
    remotion_url: str = "http://localhost:3001"  # Remotion render server

    # Auth0
    auth0_domain: str = ""  # e.g. "yourapp.us.auth0.com"
    auth0_audience: str = ""  # e.g. "https://api.kureita.com"
    auth0_algorithms: str = "RS256"

    # Optional
    redis_url: str = "redis://localhost:6379"
    firecrawl_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
