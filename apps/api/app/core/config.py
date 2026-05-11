import os
from functools import lru_cache
from typing import Literal

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
    app_env: str = "local"  # APP_ENV: "local" uses Dodo test_mode; "prod" uses live_mode
    debug: bool = False
    api_base_url: str = (
        "http://localhost:8000"  # Public URL of the API (also used for webhook URL in dashboard)
    )
    web_app_url: str = "http://localhost:3000"  # Browser app origin for Dodo return_url

    # CORS (comma-separated string, use cors_origins_list property for list)
    cors_origins: str = "http://localhost:3000,https://app.kureita.com"
    cors_origin_regex: str = r"https://([a-z0-9-]+\.)?kureita\.com"

    @property
    def cors_origins_list(self) -> list[str]:
        """Get CORS origins as a list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def dodo_payments_environment(self) -> Literal["test_mode", "live_mode"]:
        """Local/dev uses Dodo test Mode; production uses live (real money)."""
        return "live_mode" if (self.app_env or "").strip().lower() == "prod" else "test_mode"

    # MongoDB
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_database: str = "kureita"

    # AI/LLM APIs
    openai_api_key: str = ""
    gemini_api_key: str = ""  # Can also use GOOGLE_API_KEY
    google_api_key: str = ""  # Alternative to GEMINI_API_KEY
    anthropic_api_key: str = ""
    openrouter_api_key: str = ""
    use_mock_veo: bool = True  # Set to False to use real fal API

    # fal.ai (unified image/video/audio generation)
    fal_api_key: str = ""
    # Public URL where fal should deliver webhooks (e.g. https://app-api.kureita.com).
    # Leave empty in local dev to auto-fall back to synchronous subscribe mode.
    fal_webhook_public_url: str = ""
    # When true, video generation returns the exact fal payload without submitting.
    # Useful to verify start/end/elements wiring safely in production.
    fal_video_debug_dry_run: bool = False

    @property
    def google_ai_key(self) -> str:
        """Get the Google API key (prefers GEMINI_API_KEY, falls back to GOOGLE_API_KEY)."""
        return self.gemini_api_key or self.google_api_key

    # Media Generation (Optional - Veo 3.1 includes native audio on fal)
    elevenlabs_api_key: str = ""  # Optional: legacy / direct ElevenLabs use
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"

    # AWS (S3, SES, and other AWS services)
    storage_type: str = "local"  # "local" or "s3"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"
    s3_bucket: str = "kureita-assets"
    s3_endpoint: str = ""  # Optional: for S3-compatible services (R2, MinIO)

    # Upload limits. Direct browser-to-S3 uploads use these for per-file checks
    # and tenant storage quota enforcement. The API multipart route remains
    # intentionally small because API Gateway/Lambda reject large request bodies.
    upload_max_image_mb: int = 25
    upload_max_video_mb: int = 100
    upload_max_audio_mb: int = 50
    upload_api_max_mb: int = 8
    tenant_asset_storage_quota_mb: int = 500

    # Remotion rendering service
    remotion_url: str = "http://localhost:3001"  # Remotion render server

    # Auth0
    auth0_domain: str = ""  # e.g. "yourapp.us.auth0.com"
    auth0_audience: str = ""  # e.g. "https://api.kureita.com"
    auth0_algorithms: str = "RS256"

    # Billing
    commission_multiplier: float = 0.3  # 30% markup on API costs

    # Dodo Payments (https://docs.dodopayments.com/) — API key from Developer → API
    dodo_payments_api_key: str = ""
    # Webhook signing secret from Developer → Webhooks (whsec_...)
    dodo_webhook_secret: str = ""
    # One one-time product with "Pay what you want" enabled (dashboard → Products)
    dodo_topup_product_id: str = ""
    # Allowed custom top-up range (USD); enforced in API and should match product limits in Dodo
    dodo_min_topup_usd: float = 10.0
    dodo_max_topup_usd: float = 500.0

    # Optional
    redis_url: str = "redis://localhost:6379"
    firecrawl_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
