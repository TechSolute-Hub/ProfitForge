from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    cors_origins: str = "http://localhost:5173"
    twelve_data_api_key: str = ""
    twelve_data_base_url: str = "https://api.twelvedata.com"
    supabase_url: str = ""
    supabase_publishable_key: str = ""
    quote_cache_seconds: int = Field(default=30, ge=0, le=3600)
    bars_cache_seconds: int = Field(default=60, ge=0, le=3600)
    max_data_age_seconds: int = Field(default=900, ge=1, le=86400)
    supabase_request_timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    @property
    def cors_origin_list(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
