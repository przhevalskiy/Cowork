from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Supabase
    supabase_url: str = ""
    supabase_key: str = ""
    supabase_service_role_key: str = ""
    supabase_jwt_secret: str = ""

    # Anthropic
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"

    # Hive
    hive_api_key: str = ""
    hive_user_id: str = ""
    hive_workspace_id: str = ""
    # When true, requests route through the UAT twin maps in hive_service.py
    # (per service_type / impact_type) instead of the production projects.
    hive_uat_mode: bool = False

    # Mistral (fallback)
    mistral_api_key: str = ""
    mistral_model: str = "mistral-large-latest"

    # Email
    resend_api_key: str = ""
    email_cc_address: str = ""

    # CoSight — Google APIs (GA4 + GSC share one service-account JSON)
    google_credentials_json: str = ""     # full JSON string of the service-account key
    google_credentials_file: str = ""     # alternative: path to the JSON key file
    ga4_property_id: str = "288367390"   # numeric property ID, NOT G-XXXX
    gsc_site_url: str = "https://business.columbia.edu/"

    # CoSight — Emma email marketing
    emma_public_key: str = ""
    emma_private_key: str = ""
    emma_account_id: str = ""

    # CoSight — Sprout Social (pending credential)
    sprout_api_token: str = ""
    # Sprout group IDs for Columbia Business School (Business School, The Hub, Exec Ed)
    sprout_cbs_group_ids: str = "2415696,2468619,2551611"
    # Sprout/Facebook metrics are incomplete for recent days; exclude from latest date.
    sprout_data_lag_days: int = 2

    # CoSight — Event Registry (media mentions)
    eventregistry_api_key: str = ""

    # Application
    cors_origins: str = "http://localhost:5173,http://localhost:5174,http://localhost:3000"
    debug: bool = True
    log_level: str = "INFO"

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
