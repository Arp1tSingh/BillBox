"""Application configuration.

All values come from environment variables (or `backend/.env` for local work).
Defaults match the Supabase CLI so a fresh clone starts with one file to edit.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "test", "production"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "BillBox API"
    environment: Environment = "local"

    supabase_url: str = "http://127.0.0.1:54321"
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    # Used only for legacy HS256 projects. New projects verify against JWKS.
    supabase_jwt_secret: str = ""

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    max_household_members: int = Field(default=8, ge=1, le=50)
    invite_code_length: int = Field(default=8, ge=6, le=12)

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    gemini_thinking_level: str = "low"
    gemini_mock: bool = False

    max_file_mb: int = Field(default=10, ge=1, le=50)
    max_upload_mb: int = Field(default=25, ge=1, le=31)
    max_pages: int = Field(default=10, ge=1, le=20)
    processing_stale_seconds: int = Field(default=300, ge=30)

    @field_validator("supabase_url")
    @classmethod
    def _strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def issuer(self) -> str:
        return f"{self.supabase_url}/auth/v1"

    @property
    def jwks_url(self) -> str:
        return f"{self.issuer}/.well-known/jwks.json"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
