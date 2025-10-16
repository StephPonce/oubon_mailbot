from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App configuration
    APP_HOST: str = Field(default="localhost")
    APP_PORT: int = Field(default=8011)
    APP_DEBUG: bool = Field(default=True)

    # OAuth / Google
    GOOGLE_CLIENT_ID: str = Field(default="")
    GOOGLE_CLIENT_SECRET: str = Field(default="")
    GOOGLE_REDIRECT_URI: str = Field(default="http://localhost:8011/oauth2callback")
    GOOGLE_SCOPES: str = Field(default="https://www.googleapis.com/auth/gmail.modify")
    GOOGLE_TOKEN_FILE: str = Field(default=".secrets/gmail_token.json")
    GOOGLE_CREDENTIALS_FILE: str = Field(default=".secrets/credentials.json")

    # Database
    DATABASE_URL: str = Field(default="sqlite+aiosqlite:///./data/mailbot.db")

    # AI defaults
    AI_PROVIDER: str = Field(default="openai")
    AI_MODEL: str = Field(default="gpt-4o-mini")
    OPENAI_API_KEY: str = Field(default="")
    GROK_API_KEY: str | None = Field(default=None)
    AI_DAILY_QUOTA: int = Field(default=100000)
    REPLY_ALWAYS: bool = Field(default=False)
    HELPBOT_SHARED_SECRET: str | None = Field(default=None)

    # Shopify
    SHOPIFY_STORE: str = Field(default="")
    SHOPIFY_API_TOKEN: str = Field(default="")
    SHOPIFY_API_VERSION: str = Field(default="2025-10")
    SHOPIFY_MODE: str = Field(default="safe")
    SHOPIFY_API_KEY: str = Field(default="")
    SHOPIFY_API_SECRET: str = Field(default="")
    SHOPIFY_DOMAIN: str = Field(default="")

    # Ads and affiliate
    FB_ADS_DAILY_LIMIT: float = Field(default=0.0)
    GOOGLE_ADS_DAILY_LIMIT: float = Field(default=0.0)
    ADS_BUDGET_CAP: float = Field(default=100.0)
    AMAZON_ACCESS_KEY: str = Field(default="")
    AMAZON_SECRET_KEY: str = Field(default="")
    AMAZON_ASSOC_TAG: str = Field(default="")
    AMAZON_COUNTRY: str = Field(default="us")
    ALIEXPRESS_API_KEY: str = Field(default="")

    # Store behaviour
    STORE_TIMEZONE: str = Field(default="America/Chicago")
    QUIET_HOURS_START: int = Field(default=22)
    QUIET_HOURS_END: int = Field(default=7)

    # Slack
    SLACK_WEBHOOK_URL: str | None = Field(default=None)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Backwards-compatible lowercase accessors
    @property
    def google_client_id(self) -> str:
        return self.GOOGLE_CLIENT_ID

    @property
    def google_client_secret(self) -> str:
        return self.GOOGLE_CLIENT_SECRET

    @property
    def google_redirect_uri(self) -> str:
        return self.GOOGLE_REDIRECT_URI

    @property
    def google_scopes(self) -> str:
        return self.GOOGLE_SCOPES

    @property
    def google_token_file(self) -> str:
        return self.GOOGLE_TOKEN_FILE

    @property
    def google_credentials_file(self) -> str:
        return self.GOOGLE_CREDENTIALS_FILE

    @property
    def openai_api_key(self) -> str:
        return self.OPENAI_API_KEY

    @property
    def slack_webhook_url(self) -> str | None:
        return self.SLACK_WEBHOOK_URL

    @property
    def grok_api_key(self) -> str | None:
        return self.GROK_API_KEY

    @property
    def store_timezone(self) -> str:
        return self.STORE_TIMEZONE


@lru_cache()
def get_settings() -> Settings:
    return Settings()
