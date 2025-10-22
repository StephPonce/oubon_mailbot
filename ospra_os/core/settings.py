from __future__ import annotations

import os
from datetime import time as time_cls
from functools import lru_cache
from typing import List, Optional
from pydantic import EmailStr, Field, field_validator
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
    BRAND_NAME: str = Field(default="Oubon Shop")
    SUPPORT_FROM_NAME: str = Field(default="Oubon Shop Support")
    SUPPORT_FROM_EMAIL: EmailStr = Field(default="support@oubonshop.com")
    LOG_LEVEL: str = Field(default="INFO")

    # Gmail
    GMAIL_USER_EMAIL: str
    GMAIL_TOKEN_PATH: str = Field(default=".secrets/gmail/token.json")
    GMAIL_CREDENTIALS_PATH: str = Field(default=".secrets/gmail/credentials.json")
    GMAIL_POLL_SECONDS: int = Field(default=60)
    GMAIL_LABEL_PREFIX: str = Field(default="OUBON")
    GMAIL_LABEL_PROCESSED: Optional[str] = Field(default=None)
    GMAIL_LABEL_ERROR: Optional[str] = Field(default=None)
    GMAIL_LABEL_CUSTOMER: Optional[str] = Field(default=None)
    GMAIL_LABEL_ORDER: Optional[str] = Field(default=None)
    GMAIL_LABEL_AUTO_REPLY: Optional[str] = Field(default=None)
    GMAIL_LABEL_AUTO_IGNORED: Optional[str] = Field(default=None)
    GMAIL_AUTO_REPLY_LABEL: Optional[str] = Field(default=None)
    GMAIL_STATE_DB_PATH: str = Field(default="data/gmail_worker.sqlite")
    GMAIL_SQLITE_PATH: Optional[str] = Field(default=None)
    GMAIL_REPLY_FROM: Optional[str] = Field(default=None)
    GMAIL_BRAND_NAME: Optional[str] = Field(default=None)
    GMAIL_SIGNATURE: Optional[str] = Field(default=None)

    # Quiet hours (local server time)
    QUIET_HOURS_START: time_cls = Field(default=time_cls(hour=21, minute=0))
    QUIET_HOURS_END: time_cls = Field(default=time_cls(hour=7, minute=0))
    QUIET_HOURS_TIMEZONE: Optional[str] = Field(default="UTC")
    QUIET_HOURS_BRAND: Optional[str] = Field(default=None)
    AUTO_REPLY_ENABLED: bool = Field(default=True)

    # AI Providers
    AI_PROVIDER: str = Field(default="openai")
    OPENAI_API_KEY: Optional[str] = None
    AI_MODEL: str = Field(default="gpt-4o-mini")
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

    # Shopify
    SHOPIFY_STORE: Optional[str] = None
    SHOPIFY_STORE_DOMAIN: Optional[str] = None
    SHOPIFY_DOMAIN: Optional[str] = None
    SHOPIFY_API_TOKEN: Optional[str] = None
    SHOPIFY_ADMIN_TOKEN: Optional[str] = None
    SHOPIFY_API_KEY: Optional[str] = None
    SHOPIFY_API_SECRET: Optional[str] = None
    SHOPIFY_API_VERSION: Optional[str] = Field(default="2024-10")

    # Gmail canonical label names
    LABEL_SUPPORT: str = Field(default="Support")
    LABEL_ORDERS: str = Field(default="Orders")
    LABEL_BILLING: str = Field(default="Billing")
    LABEL_MARKETING: str = Field(default="Marketing")
    LABEL_VIP: str = Field(default="VIP")
    LABEL_ADMIN: str = Field(default="Admin")
    LABEL_AUTO_REPLIED: str = Field(default="Auto Replied")
    LABEL_AUTO_IGNORED: str = Field(default="Auto Ignored")

    # Reply safety
    REPLY_COOLDOWN_HOURS: int = Field(default=24)
    IGNORE_SENDER_PATTERNS: List[str] = Field(
        default_factory=lambda: ["no[-_.]?reply@", "donotreply@", "noreply@"]
    )
    IGNORE_SUBJECT_PATTERNS: List[str] = Field(
        default_factory=lambda: ["do not reply", r"auto(?:mated|matic) notification"]
    )
    IGNORE_DOMAINS: List[str] = Field(default_factory=list)

    # Data
    DATABASE_PATH: str = Field(default="data/oubon.db")

    # Research module knobs
    RESEARCH_MAX_TERMS: int = Field(default=5)
    RESEARCH_MAX_CANDIDATES_PER_TERM: int = Field(default=3)

    model_config = SettingsConfigDict(
        env_prefix="OUBONSHOP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
    )

    @field_validator("STORE_DOMAIN", "SUPPORT_FORM_URL", "ALLOWED_ORIGIN", mode="before")
    @classmethod
    def _sanitize(cls, v: Optional[str]) -> Optional[str]:
        return _strip_quotes_and_slash(v)
    
    @field_validator("QUIET_HOURS_START", "QUIET_HOURS_END", mode="before")
    @classmethod
    def _parse_time(cls, v):
        if isinstance(v, time_cls):
            return v
        if isinstance(v, str):
            parts = v.strip()
            if not parts:
                return v
            try:
                hours, minutes = parts.split(":")
                return time_cls(hour=int(hours), minute=int(minutes))
            except ValueError as exc:
                raise ValueError(f"Invalid time format '{v}'. Expected HH:MM.") from exc
        if isinstance(v, int):
            return time_cls(hour=v, minute=0)
        raise ValueError(f"Unsupported time value '{v}' for quiet hours.")

    @field_validator("GMAIL_USER_EMAIL", "GMAIL_REPLY_FROM", mode="after")
    @classmethod
    def _validate_emails(cls, v: str) -> str:
        if not v or "@" not in v:
            raise ValueError("Missing/invalid Gmail address in settings")
        return v

    @field_validator("GMAIL_CREDENTIALS_PATH", "GMAIL_TOKEN_PATH", mode="after")
    @classmethod
    def _validate_paths(cls, v: str) -> str:
        if not v:
            raise ValueError("Missing Gmail credentials/token path")
        return v

    @field_validator("IGNORE_SENDER_PATTERNS", "IGNORE_SUBJECT_PATTERNS", "IGNORE_DOMAINS", mode="before")
    @classmethod
    def _split_patterns(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            if not v.strip():
                return []
            return [item.strip() for item in v.split(",") if item.strip()]
        if isinstance(v, (list, tuple)):
            return [str(item).strip() for item in v if str(item).strip()]
        return v

    @field_validator("IGNORE_DOMAINS", mode="after")
    @classmethod
    def _normalize_domains(cls, v: List[str]) -> List[str]:
        return [item.lower() for item in v]

    def model_post_init(self, __context):
        # Allow non-prefixed overrides from environment for backwards compatibility
        label_overrides = {
            "LABEL_SUPPORT": "LABEL_SUPPORT",
            "LABEL_ORDERS": "LABEL_ORDERS",
            "LABEL_BILLING": "LABEL_BILLING",
            "LABEL_MARKETING": "LABEL_MARKETING",
            "LABEL_ADMIN": "LABEL_ADMIN",
            "LABEL_VIP": "LABEL_VIP",
            "LABEL_AUTO_REPLIED": "LABEL_AUTO_REPLIED",
            "LABEL_AUTO_IGNORED": "LABEL_AUTO_IGNORED",
        }
        for env_key, attr in label_overrides.items():
            value = os.getenv(env_key)
            if value:
                object.__setattr__(self, attr, value.strip())

        list_overrides = {
            "IGNORE_SENDER_PATTERNS": "IGNORE_SENDER_PATTERNS",
            "IGNORE_SUBJECT_PATTERNS": "IGNORE_SUBJECT_PATTERNS",
            "IGNORE_DOMAINS": "IGNORE_DOMAINS",
        }
        for env_key, attr in list_overrides.items():
            value = os.getenv(env_key)
            if value:
                items = [item.strip() for item in value.split(",") if item.strip()]
                if attr == "IGNORE_DOMAINS":
                    items = [item.lower() for item in items]
                object.__setattr__(self, attr, items)

        cooldown_override = os.getenv("REPLY_COOLDOWN_HOURS")
        if cooldown_override:
            try:
                object.__setattr__(self, "REPLY_COOLDOWN_HOURS", int(cooldown_override))
            except ValueError:
                pass

        prefix = (self.GMAIL_LABEL_PREFIX or "OUBON").strip()
        object.__setattr__(self, "GMAIL_LABEL_PREFIX", prefix)

        def _ensure(attr: str, value: str):
            if getattr(self, attr, None) is None:  # only fill if truly None (not empty string)
                object.__setattr__(self, attr, value)

        def _prefixed(name: Optional[str], fallback: Optional[str] = None) -> str:
            label = (name or fallback or "").strip()
            if prefix and label:
                return f"{prefix} {label}".strip()
            if label:
                return label
            return prefix

        env_processed = os.getenv("OSPRA_GMAIL_LABEL_PROCESSED")
        env_error = os.getenv("OSPRA_GMAIL_LABEL_ERROR")
        env_customer = os.getenv("OSPRA_GMAIL_LABEL_CUSTOMER")
        env_order = os.getenv("OSPRA_GMAIL_LABEL_ORDER")
        env_auto_reply = os.getenv("OSPRA_GMAIL_LABEL_AUTO_REPLY")
        env_auto_ignored = os.getenv("OSPRA_GMAIL_LABEL_AUTO_IGNORED")

        if env_processed is not None:
            object.__setattr__(self, "GMAIL_LABEL_PROCESSED", env_processed.strip())
        else:
            _ensure("GMAIL_LABEL_PROCESSED", _prefixed("Processed"))

        if env_error is not None:
            object.__setattr__(self, "GMAIL_LABEL_ERROR", env_error.strip())
        else:
            _ensure("GMAIL_LABEL_ERROR", _prefixed(self.LABEL_ADMIN, "Admin"))

        if env_customer is not None:
            object.__setattr__(self, "GMAIL_LABEL_CUSTOMER", env_customer.strip())
        else:
            _ensure("GMAIL_LABEL_CUSTOMER", _prefixed(self.LABEL_SUPPORT, "Support"))

        if env_order is not None:
            object.__setattr__(self, "GMAIL_LABEL_ORDER", env_order.strip())
        else:
            _ensure("GMAIL_LABEL_ORDER", _prefixed(self.LABEL_ORDERS, "Orders"))

        if env_auto_reply is not None:
            object.__setattr__(self, "GMAIL_LABEL_AUTO_REPLY", env_auto_reply.strip())
        else:
            _ensure("GMAIL_LABEL_AUTO_REPLY", _prefixed(self.LABEL_AUTO_REPLIED, "Auto Replied"))

        if env_auto_ignored is not None:
            object.__setattr__(self, "GMAIL_LABEL_AUTO_IGNORED", env_auto_ignored.strip())
        else:
            _ensure("GMAIL_LABEL_AUTO_IGNORED", _prefixed(self.LABEL_AUTO_IGNORED, "Auto Ignored"))

        if not self.GMAIL_AUTO_REPLY_LABEL:
            object.__setattr__(self, "GMAIL_AUTO_REPLY_LABEL", self.GMAIL_LABEL_AUTO_REPLY)

        _ensure("GMAIL_BRAND_NAME", self.BRAND_NAME)
        _ensure("GMAIL_SIGNATURE", f"— {self.SUPPORT_FROM_NAME}")
        if not self.GMAIL_REPLY_FROM:
            object.__setattr__(self, "GMAIL_REPLY_FROM", str(self.SUPPORT_FROM_EMAIL))
        if not self.QUIET_HOURS_BRAND:
            object.__setattr__(self, "QUIET_HOURS_BRAND", self.BRAND_NAME)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
