from __future__ import annotations
from functools import lru_cache
from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _strip_quotes_and_slash(v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    s = v.strip()
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        s = s[1:-1].strip()
    # remove trailing slash for URL-ish fields
    return s.rstrip("/")


class Settings(BaseSettings):
    # Environment
    ENV: str = Field(default="local")

    # AI Providers
    OPENAI_API_KEY: Optional[str] = None
    CLAUDE_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None

    # Store / public URLs
    STORE_DOMAIN: Optional[str] = None
    SUPPORT_FORM_URL: Optional[str] = None
    ALLOWED_ORIGIN: Optional[str] = None

    # Connectors (stubs for future phases)
    META_ACCESS_TOKEN: Optional[str] = None
    TIKTOK_ACCESS_TOKEN: Optional[str] = None
    GOOGLE_API_KEY: Optional[str] = None
    REDDIT_CLIENT_ID: Optional[str] = None
    REDDIT_SECRET: Optional[str] = None

    # Data
    DATABASE_PATH: str = Field(default="data/oubon.db")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
    )

    @field_validator("STORE_DOMAIN", "SUPPORT_FORM_URL", "ALLOWED_ORIGIN", mode="before")
    @classmethod
    def _sanitize(cls, v: Optional[str]) -> Optional[str]:
        return _strip_quotes_and_slash(v)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
