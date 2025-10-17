from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _strip_quotes_and_slash(v: Optional[str]) -> Optional[str]:
    """
    Normalize env strings by trimming whitespace, removing surrounding quotes,
    and stripping trailing slashes so downstream URL joins remain predictable.
    """
    if not v:
        return v
    v = v.strip()
    if (v.startswith("'") and v.endswith("'")) or (v.startswith('"') and v.endswith('"')):
        v = v[1:-1].strip()
    return v.rstrip("/")


class Settings(BaseSettings):
    # --- App / runtime ---
    APP_HOST: str = Field(default="localhost")
    APP_PORT: int = Field(default=8011)
    APP_DEBUG: bool = Field(default=True)
    DATABASE_URL: str = Field(default="sqlite+aiosqlite:///./data/mailbot.db")

    # --- Google API / Gmail ---
    GOOGLE_CLIENT_ID: Optional[str] = Field(default=None)
    GOOGLE_CLIENT_SECRET: Optional[str] = Field(default=None)
    GOOGLE_REDIRECT_URI: str = Field(default="http://localhost:8011/oauth2callback")
    GOOGLE_SCOPES: str = Field(default="https://www.googleapis.com/auth/gmail.modify")
    GOOGLE_TOKEN_FILE: str = Field(default=".secrets/gmail_token.json")
    GOOGLE_CREDENTIALS_FILE: str = Field(default=".secrets/credentials.json")

    # --- Slack / notifications ---
    SLACK_WEBHOOK_URL: Optional[str] = Field(default=None)

    # --- AI settings ---
    AI_PROVIDER: str = Field(default="openai")
    AI_MODEL: str = Field(default="gpt-4o-mini")
    AI_FORCE_OPENAI_ONLY: bool = Field(default=False)
    AI_DAILY_QUOTA: int = Field(default=100000)
    AI_BUDGET_CAP: float = Field(default=10.0)
    REPLY_ALWAYS: bool = Field(default=False)
    GROK_API_KEY: Optional[str] = Field(default=None)
    HELPBOT_SHARED_SECRET: Optional[str] = Field(default=None)
    PUBLIC_FORM_SECRET: Optional[str] = Field(default=None)


    # --- Research feature toggles ---
    ENABLE_RESEARCH_REDDIT: bool | None = False
    ENABLE_RESEARCH_INSTAGRAM: bool | None = False
    ENABLE_RESEARCH_TIKTOK: bool | None = False
    ENABLE_RESEARCH_GOOGLE: bool | None = True

    # --- Research API credentials ---
    REDDIT_CLIENT_ID: Optional[str] = Field(default=None)
    REDDIT_CLIENT_SECRET: Optional[str] = Field(default=None)
    REDDIT_USER_AGENT: Optional[str] = Field(default="oubon-research/1.0")

    META_APP_ID: Optional[str] = Field(default=None)
    META_APP_SECRET: Optional[str] = Field(default=None)
    META_IG_BUSINESS_ID: Optional[str] = Field(default=None)
    META_ACCESS_TOKEN: Optional[str] = Field(default=None)

    SERPAPI_KEY: Optional[str] = Field(default=None)
    GOOGLE_CSE_ID: Optional[str] = Field(default=None)

    RESEARCH_MAX_RESULTS: Optional[int] = Field(default=10)
    RESEARCH_TIMEOUT_SEC: Optional[int] = Field(default=15)

    # --- Shopify / store ---
    STORE_DOMAIN: Optional[str] = Field(default=None)
    SUPPORT_FORM_URL: Optional[str] = Field(default=None)
    ALLOWED_ORIGIN: Optional[str] = Field(default=None)
    SHOPIFY_STORE: Optional[str] = Field(default=None)
    SHOPIFY_API_TOKEN: Optional[str] = Field(default=None)
    SHOPIFY_API_VERSION: str = Field(default="2025-10")
    SHOPIFY_MODE: str = Field(default="safe")
    SHOPIFY_API_KEY: Optional[str] = Field(default=None)
    SHOPIFY_API_SECRET: Optional[str] = Field(default=None)

    # --- Time / scheduling ---
    STORE_TIMEZONE: str = Field(default="America/Chicago")
    QUIET_HOURS_START: int = Field(default=22)
    QUIET_HOURS_END: int = Field(default=7)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
    )

    @field_validator(
        "STORE_DOMAIN",
        "SUPPORT_FORM_URL",
        "ALLOWED_ORIGIN",
        "SHOPIFY_STORE",
        mode="before",
    )
    @classmethod
    def _sanitize_links(cls, v: Optional[str]) -> Optional[str]:
        return _strip_quotes_and_slash(v)

    # --- Compatibility helpers (legacy lowercase attributes) ---
    @property
    def google_scopes(self) -> str:
        return self.GOOGLE_SCOPES

    @property
    def google_credentials_file(self) -> str:
        return self.GOOGLE_CREDENTIALS_FILE

    @property
    def google_token_file(self) -> str:
        return self.GOOGLE_TOKEN_FILE

    @property
    def google_redirect_uri(self) -> str:
        return self.GOOGLE_REDIRECT_URI

    @property
    def slack_webhook_url(self) -> Optional[str]:
        return self.SLACK_WEBHOOK_URL

    @property
    def store_timezone(self) -> str:
        return self.STORE_TIMEZONE


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
