from __future__ import annotations

import os
from datetime import time as time_cls
from functools import lru_cache
from typing import Dict, List, Optional
from pydantic import AliasChoices, EmailStr, Field, field_validator
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

    # Observability & Monitoring (TECHNICAL FIX T5)
    LOG_FORMAT: str = Field(default="console")  # "console" or "json"
    SENTRY_DSN: Optional[str] = None  # Sentry Data Source Name
    SENTRY_ENVIRONMENT: str = Field(default="production")  # production, staging, development
    SENTRY_TRACES_SAMPLE_RATE: float = Field(default=0.1)  # 10% of transactions
    SENTRY_PROFILES_SAMPLE_RATE: float = Field(default=0.1)  # 10% profiling

    # PostHog Analytics (task #38) — feature flags + activation funnel
    # signup → first discovery → first deploy → first sale
    POSTHOG_API_KEY: Optional[str] = None
    POSTHOG_HOST: str = Field(default="https://us.i.posthog.com")
    POSTHOG_DEBUG: bool = Field(default=False)
    POSTHOG_ENABLED: bool = Field(default=True)  # master switch — set False in tests

    # Gmail (optional for production without email features)
    GMAIL_USER_EMAIL: str = Field(default="noreply@ospra.io")
    GMAIL_TOKEN_PATH: str = Field(default=".secrets/gmail/token.json")
    GMAIL_CREDENTIALS_PATH: str = Field(default=".secrets/gmail/credentials.json")

    # Gmail API settings (for compatibility with app.gmail_client)
    google_scopes: str = Field(default="https://www.googleapis.com/auth/gmail.modify https://www.googleapis.com/auth/gmail.send")
    google_credentials_file: str = Field(default=".secrets/gmail/credentials.json")
    google_token_file: str = Field(default=".secrets/gmail/token.json")
    google_redirect_uri: str = Field(default="http://localhost:8000/oauth2callback")
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

    # Ad-spend safety rails (Section B, T21/T22/T24).
    # ADS_AUTOMATION_ENABLED gates every automated platform mutation that can
    # INCREASE spend (budget raises, activations). Protective actions (pauses,
    # budget decreases) run regardless. Default OFF — standing rule: money
    # auto-features ship disabled until explicitly enabled in prod.
    ADS_AUTOMATION_ENABLED: bool = Field(default=False)
    # Hard per-campaign daily budget ceiling (USD). Applies on creation and to
    # every optimizer adjustment, in addition to the per-campaign budget_limit
    # column when that is set.
    ADS_MAX_DAILY_BUDGET: float = Field(default=100.0)
    # Account-wide cap: the SUM of daily budgets across all active campaigns
    # may never exceed this (USD/day). Increases that would breach it are denied.
    ADS_MAX_ACCOUNT_DAILY_BUDGET: float = Field(default=500.0)
    # Throttle: at most one optimizer budget increase per campaign per this
    # many hours (the 6-hourly job would otherwise compound 1.2^4/day ≈ +107%).
    ADS_BUDGET_INCREASE_COOLDOWN_HOURS: int = Field(default=24)
    # Emergency stop: when True, all ad automation halts and activations are
    # refused platform-wide (the POST /api/ads/kill-switch endpoint pauses
    # everything immediately; this flag keeps it down across restarts).
    ADS_KILL_SWITCH: bool = Field(default=False)

    # Auto-fulfillment safety rails (Section B, T17/T19).
    # Master kill switch, checked INSIDE the engine (T17) — the dashboard
    # toggle in data/fulfillment_settings.json must ALSO be on. Default OFF:
    # money auto-features ship disabled.
    AUTO_FULFILL_ENABLED: bool = Field(default=False)
    # Per-order ceiling (USD, customer-facing order total). Orders above this
    # route to manual review instead of being auto-placed with the supplier.
    FULFILL_MAX_ORDER_VALUE: float = Field(default=200.0)
    # Daily cap on auto-placed supplier orders. Anything past it goes to the
    # manual queue — a runaway webhook storm can't place unlimited orders.
    FULFILL_MAX_ORDERS_PER_DAY: int = Field(default=50)

    # AI Providers
    AI_PROVIDER: str = Field(default="openai")
    OPENAI_API_KEY: Optional[str] = None
    AI_MODEL: str = Field(default="gpt-4o-mini")
    CLAUDE_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    GOOGLE_CLOUD_PROJECT: Optional[str] = None  # For Gemini API project ID

    # Gmail Push Notifications (Cloud Pub/Sub)
    GOOGLE_CLOUD_PROJECT_ID: Optional[str] = None  # GCP project ID for Gmail watch
    GMAIL_PUBSUB_TOPIC: str = Field(default="gmail-notifications")
    # T36: the OIDC audience configured on the Pub/Sub push subscription. The
    # webhook verifies the Google-signed bearer token has THIS audience and a
    # google issuer before doing any work. When set, an unauthenticated caller
    # can no longer trigger paid AI calls / auto-replies / refunds.
    GMAIL_PUBSUB_AUDIENCE: Optional[str] = None
    # Optional: restrict to a specific push service-account email.
    GMAIL_PUBSUB_SERVICE_ACCOUNT: Optional[str] = None

    # Alerts & Notifications
    SLACK_WEBHOOK_URL: Optional[str] = None  # Slack webhook for priority alerts

    # Store / public URLs
    STORE_DOMAIN: Optional[str] = None
    SUPPORT_FORM_URL: Optional[str] = None
    ALLOWED_ORIGIN: Optional[str] = None
    base_url: str = Field(default="http://localhost:8000")  # For OAuth redirects

    # Connectors (stubs for future phases)
    META_APP_ID: Optional[str] = None
    META_APP_SECRET: Optional[str] = None
    META_ACCESS_TOKEN: Optional[str] = None
    META_AD_ACCOUNT_ID: Optional[str] = None
    META_PAGE_ID: Optional[str] = None

    TIKTOK_APP_ID: Optional[str] = None
    TIKTOK_SECRET: Optional[str] = None
    TIKTOK_ACCESS_TOKEN: Optional[str] = None
    TIKTOK_CLIENT_KEY: Optional[str] = None
    TIKTOK_CLIENT_SECRET: Optional[str] = None
    TIKTOK_ADVERTISER_ID: Optional[str] = None
    TIKTOK_REDIRECT_URI: Optional[str] = Field(default="http://localhost:8001/api/tiktok/auth/callback")

    # TikTok Shop Partner API (https://developers.tiktok-shops.com/) — seller-side
    # product/order/trend-feed API. Distinct from TIKTOK_CLIENT_KEY/SECRET which
    # target the content-side TikTok Open Platform. App key + secret identify
    # the partner app; access token + shop cipher identify a single seller's
    # authorized shop and are rotated by the OAuth flow in auth/tiktok_oauth.py.
    TIKTOK_SHOP_APP_KEY: Optional[str] = None
    TIKTOK_SHOP_APP_SECRET: Optional[str] = None
    TIKTOK_SHOP_ACCESS_TOKEN: Optional[str] = None
    TIKTOK_SHOP_CIPHER: Optional[str] = None  # shop_cipher from OAuth callback
    TIKTOK_SHOP_REGION: str = "US"  # US | UK | ID | MY | PH | SG | TH | VN
    TIKTOK_SHOP_API_HOST: str = "https://open-api.tiktokglobalshop.com"

    # Google Ads Platform
    GOOGLE_ADS_CUSTOMER_ID: Optional[str] = None
    GOOGLE_ADS_DEVELOPER_TOKEN: Optional[str] = None
    GOOGLE_ADS_CLIENT_ID: Optional[str] = None
    GOOGLE_ADS_CLIENT_SECRET: Optional[str] = None
    GOOGLE_ADS_REFRESH_TOKEN: Optional[str] = None

    GOOGLE_API_KEY: Optional[str] = None
    REDDIT_CLIENT_ID: Optional[str] = None
    REDDIT_SECRET: Optional[str] = None

    # Shopify
    SHOPIFY_STORE: Optional[str] = None
    SHOPIFY_STORE_DOMAIN: Optional[str] = None
    SHOPIFY_DOMAIN: Optional[str] = None
    SHOPIFY_API_TOKEN: Optional[str] = None
    SHOPIFY_ADMIN_TOKEN: Optional[str] = None
    SHOPIFY_ACCESS_TOKEN: Optional[str] = None  # Admin API access token
    SHOPIFY_API_KEY: Optional[str] = None
    SHOPIFY_API_SECRET: Optional[str] = None
    SHOPIFY_API_VERSION: Optional[str] = Field(default="2025-01")
    SHOPIFY_MODE: str = Field(default="safe")  # "safe" or "live" mode for deployments

    # AliExpress
    # App Key — Render's env sets ALIEXPRESS_APP_KEY (AliExpress's own naming);
    # accept both so the OAuth routes don't 500 on a name mismatch.
    ALIEXPRESS_API_KEY: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices(
            "ALIEXPRESS_API_KEY", "ALIEXPRESS_APP_KEY", "OUBONSHOP_ALIEXPRESS_API_KEY"
        ),
    )
    ALIEXPRESS_APP_SECRET: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices(
            "ALIEXPRESS_APP_SECRET", "OUBONSHOP_ALIEXPRESS_APP_SECRET"
        ),
    )

    # Webhook Security (Phase 2A Security)
    SHOPIFY_WEBHOOK_SECRET: Optional[str] = None  # Shopify webhook signature verification
    STRIPE_WEBHOOK_SECRET: Optional[str] = None  # Stripe webhook signature verification
    LEMONSQUEEZY_WEBHOOK_SECRET: Optional[str] = None  # LemonSqueezy webhook signature verification
    ALIEXPRESS_WEBHOOK_SECRET: Optional[str] = None  # AliExpress webhook signature verification
    CJ_WEBHOOK_SECRET: Optional[str] = None  # CJ Dropshipping webhook signature verification
    TIKTOK_WEBHOOK_SECRET: Optional[str] = None  # TikTok webhook signature verification

    # Amazon Product Advertising API (PA-API 5.0)
    AMAZON_ACCESS_KEY: Optional[str] = None  # PA-API Access Key
    AMAZON_SECRET_KEY: Optional[str] = None  # PA-API Secret Key
    AMAZON_PARTNER_TAG: Optional[str] = None  # Amazon Associate Tracking ID
    AMAZON_COUNTRY: str = Field(default="US")  # Amazon marketplace country code

    # Apify (Web Scraping Infrastructure)
    APIFY_API_TOKEN: Optional[str] = None  # Apify API token for running actors

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
    database_url: str = Field(default="sqlite:///./data/oubon.db")

    @field_validator("database_url", mode="before")
    @classmethod
    def _fix_postgres_url(cls, v: str) -> str:
        """Convert postgres:// to postgresql:// for SQLAlchemy compatibility.
        Also check DATABASE_URL env var directly (without prefix) for Render compatibility.
        """
        # Priority: Check DATABASE_URL without prefix (Render standard)
        import os
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            v = db_url
        
        if v and v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql://", 1)
        return v

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
    def _validate_emails(cls, v: Optional[str]) -> Optional[str]:
        # Allow None/empty for production deployments without email features
        if v is None:
            return None
        if v and "@" not in v:
            raise ValueError(f"Invalid email address: {v}")
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

        # Sync gmail client settings
        object.__setattr__(self, "google_credentials_file", self.GMAIL_CREDENTIALS_PATH)
        object.__setattr__(self, "google_token_file", self.GMAIL_TOKEN_PATH)

        # Backwards compatibility for app/ lowercase field names
        object.__setattr__(self, "openai_api_key", self.OPENAI_API_KEY)
        object.__setattr__(self, "claude_api_key", self.CLAUDE_API_KEY)
        object.__setattr__(self, "slack_webhook_url", self.SLACK_WEBHOOK_URL)

    # ------------------------------------------------------------------
    # Feature flags — derived from which env vars are actually configured.
    # Call sites should use these instead of checking individual env vars,
    # so adding a new provider only requires updating one place.
    # ------------------------------------------------------------------
    @property
    def AI_ENABLED(self) -> bool:
        """True if at least one AI provider key is present."""
        return any([
            self.OPENAI_API_KEY,
            self.CLAUDE_API_KEY,
            self.GEMINI_API_KEY,
            os.getenv("GROQ_API_KEY"),
            os.getenv("XAI_API_KEY"),
        ])

    @property
    def EMAIL_AUTOMATION_ENABLED(self) -> bool:
        """True when at least one email provider (Gmail/Outlook/iCloud) can be used."""
        has_google = bool(os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET"))
        has_outlook = bool(os.getenv("OUTLOOK_CLIENT_ID") and os.getenv("OUTLOOK_CLIENT_SECRET"))
        has_encryption = bool(os.getenv("EMAIL_OAUTH_ENCRYPTION_KEY"))
        return has_encryption and (has_google or has_outlook)

    @property
    def SHOPIFY_OAUTH_ENABLED(self) -> bool:
        """True when Shopify Partner OAuth is configured (required for multi-tenant installs)."""
        return bool(
            os.getenv("SHOPIFY_PARTNER_CLIENT_ID")
            and os.getenv("SHOPIFY_PARTNER_CLIENT_SECRET")
        )

    @property
    def SHOPIFY_SINGLE_STORE_ENABLED(self) -> bool:
        """True for single-tenant deployments using a private app token."""
        return bool(self.SHOPIFY_STORE and (self.SHOPIFY_API_TOKEN or self.SHOPIFY_ACCESS_TOKEN))

    @property
    def ALIEXPRESS_ENABLED(self) -> bool:
        return bool(self.ALIEXPRESS_API_KEY and self.ALIEXPRESS_APP_SECRET)

    @property
    def CJ_DROPSHIPPING_ENABLED(self) -> bool:
        # Match what the CJ client actually authenticates with
        # (ospra_os/integrations/cj_dropshipping/client.py reads CJ_ACCESS_TOKEN).
        # The old check looked for CJ_API_EMAIL + CJ_API_KEY, which the client
        # never uses — so this reported CJ "disabled" even with a valid token.
        return bool(os.getenv("CJ_ACCESS_TOKEN") or os.getenv("OUBONSHOP_CJ_ACCESS_TOKEN"))

    @property
    def AMAZON_REVIEWS_ENABLED(self) -> bool:
        return bool(self.AMAZON_ACCESS_KEY and self.AMAZON_SECRET_KEY and self.AMAZON_PARTNER_TAG)

    @property
    def APIFY_ENABLED(self) -> bool:
        return bool(self.APIFY_API_TOKEN)

    @property
    def BILLING_ENABLED(self) -> bool:
        return bool(
            os.getenv("LEMONSQUEEZY_API_KEY")
            and self.LEMONSQUEEZY_WEBHOOK_SECRET
        )

    @property
    def META_ADS_ENABLED(self) -> bool:
        return bool(self.META_APP_ID and self.META_APP_SECRET and self.META_AD_ACCOUNT_ID)

    @property
    def TIKTOK_ADS_ENABLED(self) -> bool:
        return bool(self.TIKTOK_CLIENT_KEY and self.TIKTOK_CLIENT_SECRET)

    @property
    def GOOGLE_ADS_ENABLED(self) -> bool:
        return bool(self.GOOGLE_ADS_CUSTOMER_ID and self.GOOGLE_ADS_DEVELOPER_TOKEN)

    @property
    def OBSERVABILITY_ENABLED(self) -> bool:
        return bool(self.SENTRY_DSN)

    @property
    def ALERTS_ENABLED(self) -> bool:
        return bool(self.SLACK_WEBHOOK_URL)

    def feature_summary(self) -> Dict[str, bool]:
        """Snapshot of which features are enabled in this deployment.

        Useful for startup logs and a `/health/features` endpoint.
        """
        return {
            "ai": self.AI_ENABLED,
            "email_automation": self.EMAIL_AUTOMATION_ENABLED,
            "shopify_oauth": self.SHOPIFY_OAUTH_ENABLED,
            "shopify_single_store": self.SHOPIFY_SINGLE_STORE_ENABLED,
            "aliexpress": self.ALIEXPRESS_ENABLED,
            "cj_dropshipping": self.CJ_DROPSHIPPING_ENABLED,
            "amazon_reviews": self.AMAZON_REVIEWS_ENABLED,
            "apify": self.APIFY_ENABLED,
            "billing": self.BILLING_ENABLED,
            "meta_ads": self.META_ADS_ENABLED,
            "tiktok_ads": self.TIKTOK_ADS_ENABLED,
            "google_ads": self.GOOGLE_ADS_ENABLED,
            "observability": self.OBSERVABILITY_ENABLED,
            "alerts": self.ALERTS_ENABLED,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
