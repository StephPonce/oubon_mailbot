from dotenv import load_dotenv
import os
from pathlib import Path

# Load environment variables from .env file BEFORE any other imports
# Get the project root directory (where .env is located)
project_root = Path(__file__).parent.parent
env_path = project_root / ".env"
# In test mode (APP_ENV=testing) the test harness has already set the
# environment (DATABASE_URL pointing at the test SQLite, JWT_SECRET_KEY
# stable, etc.) BEFORE this module gets imported. Calling load_dotenv with
# override=True here would clobber those test-only values with the real
# .env (Neon Postgres URL, production secrets), which then breaks every
# downstream test that touches a settings-derived database. Drop into
# non-overriding load when running under tests so .env can still fill in
# anything the harness didn't set, without trampling what it did.
_in_tests = os.getenv("APP_ENV") == "testing" or "PYTEST_CURRENT_TEST" in os.environ
load_dotenv(dotenv_path=env_path, override=not _in_tests)


def _preflight_check_dependencies() -> None:
    """
    Fail fast with a clear, actionable message if a required dependency is
    missing. Without this, a missing ``psycopg2`` (the most common case
    after a ``.venv`` rebuild) surfaces as a confusing SQLAlchemy
    ``ModuleNotFoundError`` deep in the connection-pool stack — the kind of
    error that wedges local dev for fifteen minutes while you figure out
    you just forgot to ``uv sync``.

    Runs once at import time, before any ospra_os module that would
    otherwise trigger the lazy import. Skipped under pytest so the test
    harness doesn't pay the cost on every collection (test conftest
    already controls its own dependency surface).
    """
    if _in_tests:
        return

    # Only enforce when we'll actually need PostgreSQL — i.e. when
    # DATABASE_URL is set to a postgres URL. Local SQLite dev (no
    # DATABASE_URL set) doesn't need psycopg2.
    db_url = os.getenv("DATABASE_URL", "")
    needs_postgres = db_url.startswith(("postgres://", "postgresql://", "postgresql+"))

    missing: list[tuple[str, str]] = []  # (import_name, hint)

    if needs_postgres:
        try:
            import psycopg2  # noqa: F401
        except ImportError:
            missing.append(("psycopg2", "psycopg2-binary"))

    # cryptography is required by the credential-encryption module — a
    # missing import there fails-open in dev (ephemeral key) but the
    # underlying ``from cryptography.fernet import Fernet`` still raises
    # if cryptography isn't installed at all.
    try:
        import cryptography  # noqa: F401
    except ImportError:
        missing.append(("cryptography", "cryptography"))

    if not missing:
        return

    import sys
    package_list = ", ".join(p for _, p in missing)
    print(
        "\n"
        "─" * 72 + "\n"
        "  Ospra startup blocked — missing Python dependencies\n"
        "─" * 72 + "\n"
        f"  Missing: {', '.join(name for name, _ in missing)}\n"
        f"  Install: uv sync   (or pip install {package_list})\n"
        "\n"
        "  This usually happens after a fresh `.venv` rebuild or a Python\n"
        "  version bump. Re-run after dependencies are restored.\n"
        + "─" * 72 + "\n",
        file=sys.stderr,
        flush=True,
    )
    sys.exit(2)


_preflight_check_dependencies()


# Debug: Print if OAuth vars are loaded

from fastapi import FastAPI, Depends, Body, Request, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from ospra_os.core.settings import Settings, get_settings
from pathlib import Path
from typing import Optional, List, Dict
from pydantic import BaseModel
import logging

# API Request Schemas (Input Validation)
from ospra_os.api.schemas import (
    PlatformCredentials,
    ShopifyDeployRequest,
    ShopifyBulkDeployRequest,
    AliExpressSearchRequest,
    AliExpressAffiliateLinkRequest,
    AliExpressFulfillRequest,
    AliExpressSyncRequest,
    AliExpressMonitorPricesRequest,
    MetaCampaignRequest,
    MetaBulkCampaignCreateRequest,
    CampaignStatusUpdate,
    AdSetBudgetUpdate,
    ScheduleCreateRequest,
    DiscoverRequest as DiscoverRequestSchema,
    ChatRequest as ChatRequestSchema,
    MarketingAngleRequest,
    BulkMarketingRequest,
    SmartRecommendationRequest,
)

# Security - Rate Limiting (PHASE 1 SECURITY)
from slowapi.errors import RateLimitExceeded
from ospra_os.security.rate_limiting import limiter, rate_limit_exceeded_handler, get_tier_limit

# Multi-Tenant Isolation (GROK RECOMMENDATION #14)
from ospra_os.tenancy.middleware import TenantMiddleware, StoreContextMiddleware

# Observability (TECHNICAL FIX T5)
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from ospra_os.observability import setup_logging, setup_sentry, get_logger
    from ospra_os.observability.middleware import RequestLoggingMiddleware
    from ospra_os.observability.exception_handlers import register_exception_handlers
    _HAS_OBSERVABILITY = True
    logger = get_logger(__name__)
    logger.info("Observability system loaded successfully")
except Exception as e:
    _HAS_OBSERVABILITY = False
    logger.warning(f"Observability system not loaded: {e}")

# New integrations - Platform Adapters, AI, Deployment, Auto-Discovery
try:
    from ospra_os.platforms.factory import PlatformFactory
    _HAS_PLATFORM_FACTORY = True
    logger.info("Platform Factory loaded successfully")
except Exception as e:
    logger.warning(f"Platform Factory not loaded: {e}")
    PlatformFactory = None
    _HAS_PLATFORM_FACTORY = False

try:
    from ospra_os.deployment import UnifiedProductDeployer
    _HAS_UNIFIED_DEPLOYER = True
    logger.info("Unified Product Deployer loaded successfully")
except Exception as e:
    logger.warning(f"Unified Product Deployer not loaded: {e}")
    UnifiedProductDeployer = None
    _HAS_UNIFIED_DEPLOYER = False

try:
    from ospra_os.ai.factory import AIFactory
    _HAS_AI_FACTORY = True
    logger.info("AI Factory loaded successfully")
except Exception as e:
    logger.warning(f"AI Factory not loaded: {e}")
    AIFactory = None
    _HAS_AI_FACTORY = False

try:
    from ospra_os.background_jobs import start_auto_discovery_scheduler
    _HAS_AUTO_DISCOVERY = True
    logger.info("Auto-Discovery system loaded successfully")
except Exception as e:
    logger.warning(f"Auto-Discovery not loaded: {e}")
    start_auto_discovery_scheduler = None
    _HAS_AUTO_DISCOVERY = False

try:
    from ospra_os.utils.health_monitor import HealthMonitor
    _HAS_HEALTH_MONITOR = True
    logger.info("Health Monitor loaded successfully")
except Exception as e:
    logger.warning(f"Health Monitor not loaded: {e}")
    HealthMonitor = None
    _HAS_HEALTH_MONITOR = False

# JWT Authentication (required for secure endpoints)
try:
    from ospra_os.auth.jwt_auth import get_current_user
    from ospra_os.database import User
    _HAS_JWT_AUTH = True
    logger.info("JWT Authentication loaded successfully")
except Exception as e:
    logger.warning(f"JWT Authentication not loaded: {e}")
    _HAS_JWT_AUTH = False
    get_current_user = None
    User = None

# Authentication router (required for user accounts)
try:
    from ospra_os.api.auth_routes import router as auth_router  # type: ignore
    _HAS_AUTH = True
    logger.info("Authentication router loaded successfully")
except Exception as e:
    logger.warning(f"Authentication router not loaded: {e}")
    auth_router = None
    _HAS_AUTH = False

# Password Reset router (required for forgot password flow)
try:
    from ospra_os.api.password_reset_routes import router as password_reset_router  # type: ignore
    _HAS_PASSWORD_RESET = True
    logger.info("Password reset router loaded successfully")
except Exception as e:
    logger.warning(f"Password reset router not loaded: {e}")
    password_reset_router = None
    _HAS_PASSWORD_RESET = False

# Account / Data & Privacy router — Shopify Partner App approval blocker
# (Settings → Data & Privacy page must let users export + delete their data
# via the same handlers the GDPR webhooks call). See
# docs/guides/SHOPIFY_PARTNER_APP_APPROVAL_READINESS.md §4.
try:
    from ospra_os.api.account_routes import router as account_router  # type: ignore
    _HAS_ACCOUNT = True
    logger.info("Account / Data & Privacy router loaded successfully")
except Exception as e:
    logger.warning(f"Account router not loaded: {e}")
    account_router = None
    _HAS_ACCOUNT = False

# Frontend Compatibility router (provides missing endpoint aliases)
try:
    from ospra_os.api.frontend_compat_routes import router as frontend_compat_router  # type: ignore
    _HAS_FRONTEND_COMPAT = True
    logger.info("Frontend compatibility router loaded successfully")
except Exception as e:
    logger.warning(f"Frontend compatibility router not loaded: {e}")
    frontend_compat_router = None
    _HAS_FRONTEND_COMPAT = False

# Gmail OAuth router (optional)
try:
    from ospra_os.gmail.routes import router as gmail_oauth_router  # type: ignore
    logger.info("Gmail OAuth router loaded successfully")
except Exception as e:
    logger.warning(f"Gmail OAuth router not loaded: {e}")
    gmail_oauth_router = None

# TikTok router is optional — don't crash if it's not present
try:
    from ospra_os.tiktok.routes import router as tiktok_router  # type: ignore
    _HAS_TIKTOK = True
    logger.info("TikTok router loaded successfully")
except Exception as e:  # ImportError, etc.
    logger.warning(f"TikTok router not loaded: {e}")
    logger.debug("This is expected if TikTok integration is not yet enabled")
    tiktok_router = None
    _HAS_TIKTOK = False

# Product Research router
try:
    from ospra_os.product_research.routes import router as research_router  # type: ignore
    _HAS_RESEARCH = True
    logger.info("Product Research router loaded successfully")
except Exception as e:
    logger.warning(f"Product Research router not loaded: {e}")
    research_router = None
    _HAS_RESEARCH = False

# Admin Dashboard router
try:
    from ospra_os.admin.routes import router as admin_router  # type: ignore
    _HAS_ADMIN = True
    logger.info("Admin Dashboard router loaded successfully")
except Exception as e:
    logger.warning(f"Admin Dashboard router not loaded: {e}")
    admin_router = None
    _HAS_ADMIN = False

# Advertising Automation router
try:
    from ospra_os.advertising.routes import router as advertising_router  # type: ignore
    _HAS_ADVERTISING = True
    logger.info("Advertising Automation router loaded successfully")
except Exception as e:
    logger.warning(f"Advertising router not loaded: {e}")
    advertising_router = None
    _HAS_ADVERTISING = False

# Email OAuth router (Multi-Provider Email OAuth)
try:
    from ospra_os.email_automation.oauth.routes import router as email_oauth_router  # type: ignore
    _HAS_EMAIL_OAUTH = True
    logger.info("Email OAuth router loaded successfully")
except Exception as e:
    logger.warning(f"Email OAuth router not loaded: {e}")
    email_oauth_router = None
    _HAS_EMAIL_OAUTH = False

# Email Analytics router (Dashboard metrics)
try:
    from ospra_os.email_automation.analytics_routes import router as email_analytics_router  # type: ignore
    _HAS_EMAIL_ANALYTICS = True
    logger.info("Email Analytics router loaded successfully")
except Exception as e:
    logger.warning(f"Email Analytics router not loaded: {e}")
    email_analytics_router = None
    _HAS_EMAIL_ANALYTICS = False

# Email Sync router (Fetch and display emails from connected accounts)
try:
    from ospra_os.email_automation.sync_routes import router as email_sync_router  # type: ignore
    _HAS_EMAIL_SYNC = True
    logger.info("Email Sync router loaded successfully")
except Exception as e:
    logger.warning(f"Email Sync router not loaded: {e}")
    email_sync_router = None
    _HAS_EMAIL_SYNC = False

# Email Automation router (Smart replies, inbox processing, analytics)
try:
    from ospra_os.api.email_automation_routes import router as email_automation_router  # type: ignore
    _HAS_EMAIL_AUTOMATION = True
    logger.info("Email Automation router loaded successfully (/api/email-automation/*)")
except Exception as e:
    logger.warning(f"Email Automation router not loaded: {e}")
    email_automation_router = None
    _HAS_EMAIL_AUTOMATION = False

# Email User Settings router (User preferences and toggles)
try:
    from ospra_os.email_automation.settings_routes import router as email_settings_router  # type: ignore
    _HAS_EMAIL_SETTINGS = True
    logger.info("Email User Settings router loaded successfully")
except Exception as e:
    logger.warning(f"Email User Settings router not loaded: {e}")
    email_settings_router = None
    _HAS_EMAIL_SETTINGS = False

# Dashboard V2 router (Intelligence Platform) - REAL-TIME with Google Trends + Claude AI
try:
    from ospra_os.dashboard.routes import router as dashboard_v2_router  # type: ignore
    _HAS_DASHBOARD_V2 = True
    logger.info("Dashboard V2 REAL-TIME router loaded successfully")
except Exception as e:
    logger.warning(f"Dashboard V2 REAL-TIME router not loaded: {e}")
    import traceback
    traceback.print_exc()
    dashboard_v2_router = None
    _HAS_DASHBOARD_V2 = False

# Multi-Store Portfolio router
try:
    from ospra_os.dashboard.routes_multi_store import router as multi_store_router  # type: ignore
    _HAS_MULTI_STORE = True
    logger.info("Multi-Store Portfolio router loaded successfully")
except Exception as e:
    logger.warning(f"Multi-Store Portfolio router not loaded: {e}")
    multi_store_router = None
    _HAS_MULTI_STORE = False

# AliExpress OAuth router
try:
    from ospra_os.aliexpress.routes import router as aliexpress_router  # type: ignore
    _HAS_ALIEXPRESS = True
    logger.info("AliExpress OAuth router loaded successfully")
except Exception as e:
    logger.warning(f"AliExpress OAuth router not loaded: {e}")
    aliexpress_router = None
    _HAS_ALIEXPRESS = False

# AliExpress Dropshipping API OAuth Callback
try:
    from ospra_os.api.aliexpress_oauth import router as aliexpress_callback_router  # type: ignore
    _HAS_ALIEXPRESS_CALLBACK = True
    logger.info("AliExpress Dropshipping API callback router loaded successfully")
except Exception as e:
    logger.warning(f"AliExpress callback router not loaded: {e}")
    aliexpress_callback_router = None
    _HAS_ALIEXPRESS_CALLBACK = False

# AliExpress Affiliate API OAuth Callback (different callback URL)
try:
    from ospra_os.api.aliexpress_affiliate_oauth import router as aliexpress_affiliate_callback_router  # type: ignore
    _HAS_ALIEXPRESS_AFFILIATE_CALLBACK = True
    logger.info("AliExpress Affiliate API callback router loaded successfully")
except Exception as e:
    logger.warning(f"AliExpress Affiliate callback router not loaded: {e}")
    aliexpress_affiliate_callback_router = None
    _HAS_ALIEXPRESS_AFFILIATE_CALLBACK = False

# AliExpress Token Management (Automatic Refresh)
try:
    from ospra_os.api.aliexpress_token_routes import router as aliexpress_token_router  # type: ignore
    _HAS_ALIEXPRESS_TOKEN_MANAGEMENT = True
    logger.info("AliExpress Token Management router loaded successfully")
except Exception as e:
    logger.warning(f"AliExpress Token Management router not loaded: {e}")
    aliexpress_token_router = None
    _HAS_ALIEXPRESS_TOKEN_MANAGEMENT = False

# AliExpress Product Scraping
try:
    from ospra_os.api.aliexpress_product_routes import router as aliexpress_product_router  # type: ignore
    _HAS_ALIEXPRESS_PRODUCTS = True
    logger.info("AliExpress Product Scraping router loaded successfully")
except Exception as e:
    logger.warning(f"AliExpress Product Scraping router not loaded: {e}")
    aliexpress_product_router = None
    _HAS_ALIEXPRESS_PRODUCTS = False

# TikTok OAuth router
try:
    from ospra_os.auth.tiktok_oauth import router as tiktok_oauth_router  # type: ignore
    _HAS_TIKTOK_OAUTH = True
    logger.info("TikTok OAuth router loaded successfully")
except Exception as e:
    logger.warning(f"TikTok OAuth router not loaded: {e}")
    tiktok_oauth_router = None
    _HAS_TIKTOK_OAUTH = False

# Shopify webhooks router
try:
    from ospra_os.webhooks.shopify_webhooks import router as shopify_webhooks_router  # type: ignore
    _HAS_SHOPIFY_WEBHOOKS = True
    logger.info("Shopify webhooks router loaded successfully")
except Exception as e:
    logger.warning(f"Shopify webhooks router not loaded: {e}")
    shopify_webhooks_router = None
    _HAS_SHOPIFY_WEBHOOKS = False

# Shopify OAuth router (SaaS Multi-Store OAuth Flow)
try:
    from ospra_os.api.shopify_oauth_routes import router as shopify_oauth_router  # type: ignore
    _HAS_SHOPIFY_OAUTH = True
    logger.info("Shopify OAuth router loaded successfully")
except Exception as e:
    logger.warning(f"Shopify OAuth router not loaded: {e}")
    shopify_oauth_router = None
    _HAS_SHOPIFY_OAUTH = False

# Shopify Deployment router (AI-Enhanced Shopify Integration)
try:
    from ospra_os.integrations.shopify.routes import router as shopify_deployment_router  # type: ignore
    _HAS_SHOPIFY_DEPLOYMENT = True
    logger.info("Shopify Deployment router loaded successfully (AI-powered)")
except Exception as e:
    logger.warning(f"Shopify Deployment router not loaded: {e}")
    shopify_deployment_router = None
    _HAS_SHOPIFY_DEPLOYMENT = False

# Shopify Store Management router (OAuth, store data, real-time sync)
try:
    from ospra_os.api.shopify_routes import router as shopify_store_router  # type: ignore
    _HAS_SHOPIFY_STORES = True
    logger.info("Shopify Store Management router loaded successfully")
except Exception as e:
    logger.warning(f"Shopify Store Management router not loaded: {e}")
    shopify_store_router = None
    _HAS_SHOPIFY_STORES = False

# WooCommerce Store Management router (Universal OAuth - No app registration needed)
try:
    from ospra_os.api.woocommerce_routes import router as woocommerce_router  # type: ignore
    _HAS_WOOCOMMERCE = True
    logger.info("WooCommerce Store Management router loaded successfully")
except Exception as e:
    logger.warning(f"WooCommerce Store Management router not loaded: {e}")
    woocommerce_router = None
    _HAS_WOOCOMMERCE = False

# Meta Ads router (Real API integration - No demo data)
try:
    from ospra_os.integrations.meta.routes import router as meta_ads_router  # type: ignore
    _HAS_META_ADS = True
    logger.info("Meta Ads router loaded successfully (Real API only)")
except Exception as e:
    logger.warning(f"Meta Ads router not loaded: {e}")
    meta_ads_router = None
    _HAS_META_ADS = False

# Deployment router (Unified Product Deployment with AI)
try:
    from ospra_os.api.deployment_routes import router as deployment_router  # type: ignore
    _HAS_DEPLOYMENT = True
    logger.info("Unified Deployment router loaded successfully (AI-powered)")
except Exception as e:
    logger.warning(f"Deployment router not loaded: {e}")
    deployment_router = None
    _HAS_DEPLOYMENT = False

# Auto-Deploy router (Automated Product Deployment)
try:
    from ospra_os.api.auto_deploy_routes import router as auto_deploy_router  # type: ignore
    _HAS_AUTO_DEPLOY = True
    logger.info("Auto-Deploy router loaded successfully")
except Exception as e:
    logger.warning(f"Auto-Deploy router not loaded: {e}")
    auto_deploy_router = None
    _HAS_AUTO_DEPLOY = False

# Analytics router (Revenue & Profit Tracking)
try:
    from ospra_os.analytics.routes import router as analytics_router  # type: ignore
    _HAS_ANALYTICS = True
    logger.info("Analytics router loaded successfully")
except Exception as e:
    logger.warning(f"Analytics router not loaded: {e}")
    analytics_router = None
    _HAS_ANALYTICS = False

# Customer Analytics router (Segments, LTV, Churn Prediction)
try:
    from ospra_os.analytics.customer_routes import router as customer_analytics_router  # type: ignore
    _HAS_CUSTOMER_ANALYTICS = True
    logger.info("Customer Analytics router loaded successfully")
except Exception as e:
    logger.warning(f"Customer Analytics router not loaded: {e}")
    customer_analytics_router = None
    _HAS_CUSTOMER_ANALYTICS = False

# Background Jobs router (Job Scheduler Management)
try:
    from ospra_os.jobs.routes import router as jobs_router  # type: ignore
    _HAS_JOBS = True
    logger.info("Background Jobs router loaded successfully")
except Exception as e:
    logger.warning(f"Background Jobs router not loaded: {e}")
    jobs_router = None
    _HAS_JOBS = False

# Customer Notifications router (Alert Management)
try:
    from ospra_os.services.notification_routes import router as notifications_router  # type: ignore
    _HAS_NOTIFICATIONS = True
    logger.info("Notifications router loaded successfully")
except Exception as e:
    logger.warning(f"Notifications router not loaded: {e}")
    notifications_router = None
    _HAS_NOTIFICATIONS = False

# System Health Monitoring router (Health Dashboard & Alerts)
try:
    from ospra_os.monitoring.routes import router as health_monitor_router  # type: ignore
    _HAS_HEALTH_MONITOR = True
    logger.info("System Health Monitoring router loaded successfully")
except Exception as e:
    logger.warning(f"System Health Monitoring router not loaded: {e}")
    health_monitor_router = None
    _HAS_HEALTH_MONITOR = False

# Niche Analysis router (Market Health & Entry Timing)
try:
    from ospra_os.intelligence.niche_routes import router as niche_router  # type: ignore
    _HAS_NICHE_ANALYSIS = True
    logger.info("Niche Analysis router loaded successfully")
except Exception as e:
    logger.warning(f"Niche Analysis router not loaded: {e}")
    niche_router = None
    _HAS_NICHE_ANALYSIS = False

# Competitor Intelligence router (Competitive Analysis & Price Tracking)
try:
    from ospra_os.intelligence.routes import router as competitor_router  # type: ignore
    _HAS_COMPETITOR_INTEL = True
    logger.info("Competitor Intelligence router loaded successfully")
except Exception as e:
    logger.warning(f"Competitor Intelligence router not loaded: {e}")
    competitor_router = None
    _HAS_COMPETITOR_INTEL = False

# Report Engine router
try:
    from ospra_os.reports.routes import router as report_router  # type: ignore
    _HAS_REPORTS = True
    logger.info("Report Engine router loaded successfully")
except Exception as e:
    logger.warning(f"Report Engine router not loaded: {e}")
    report_router = None
    _HAS_REPORTS = False

# Unified Product Discovery router (AliExpress Affiliate + Apify + Google Trends)
try:
    from ospra_os.intelligence.unified_discovery_routes import router as unified_discovery_router  # type: ignore
    _HAS_UNIFIED_DISCOVERY = True
    logger.info("Unified Product Discovery router loaded successfully")
except Exception as e:
    logger.warning(f"Unified Product Discovery router not loaded: {e}")
    unified_discovery_router = None
    _HAS_UNIFIED_DISCOVERY = False

# Intelligence Core router (Unified AI Brain - Briefings, Grading, Progress, Actions)
try:
    from ospra_os.intelligence.intelligence_core_routes import router as intelligence_core_router  # type: ignore
    _HAS_INTELLIGENCE_CORE = True
    logger.info("Intelligence Core router loaded successfully")
except Exception as e:
    logger.warning(f"Intelligence Core router not loaded: {e}")
    intelligence_core_router = None
    _HAS_INTELLIGENCE_CORE = False

# Learning System router (Self-Learning AI, Feedback, Insights)
try:
    from ospra_os.learning.learning_routes import router as learning_router  # type: ignore
    _HAS_LEARNING = True
    logger.info("Learning System router loaded successfully")
except Exception as e:
    logger.warning(f"Learning System router not loaded: {e}")
    learning_router = None
    _HAS_LEARNING = False

# Fulfillment System router (Auto-fulfillment, tracking, supplier integration)
try:
    from ospra_os.api.fulfillment_routes import router as fulfillment_router  # type: ignore
    _HAS_FULFILLMENT = True
    logger.info("Fulfillment System router loaded successfully")
except Exception as e:
    logger.warning(f"Fulfillment System router not loaded: {e}")
    fulfillment_router = None
    _HAS_FULFILLMENT = False

# Oi AI Assistant router (The Brain of Ospra Intelligence)
try:
    from ospra_os.api.oi_routes import router as oi_router  # type: ignore
    _HAS_OI = True
    logger.info("Oi AI Assistant router loaded successfully [BRAIN]")
except Exception as e:
    logger.warning(f"Oi AI Assistant router not loaded: {e}")
    oi_router = None
    _HAS_OI = False

# Product Analysis router (AI analysis and caption generation)
try:
    from ospra_os.api.product_analysis_routes import router as product_analysis_router  # type: ignore
    _HAS_PRODUCT_ANALYSIS = True
    logger.info("Product Analysis router loaded successfully")
except Exception as e:
    logger.warning(f"Product Analysis router not loaded: {e}")
    product_analysis_router = None
    _HAS_PRODUCT_ANALYSIS = False

# Oi Alerts router (Real-time notifications for Oi AI)
try:
    from ospra_os.api.alert_routes import router as alert_router, ws_router as alert_ws_router  # type: ignore
    _HAS_ALERTS = True
    logger.info("Oi Alerts router loaded successfully")
except Exception as e:
    logger.warning(f"Oi Alerts router not loaded: {e}")
    alert_router = None
    alert_ws_router = None
    _HAS_ALERTS = False

# Inventory Forecasting router
try:
    from ospra_os.inventory.routes import router as inventory_router  # type: ignore
    _HAS_INVENTORY = True
    logger.info("Inventory Forecasting router loaded successfully")
except Exception as e:
    logger.warning(f"Inventory Forecasting router not loaded: {e}")
    inventory_router = None
    _HAS_INVENTORY = False

# A/B Testing router
try:
    from ospra_os.testing.routes import router as abtesting_router  # type: ignore
    _HAS_ABTESTING = True
    logger.info("A/B Testing router loaded successfully")
except Exception as e:
    logger.warning(f"A/B Testing router not loaded: {e}")
    abtesting_router = None
    _HAS_ABTESTING = False

# Image Processing router
try:
    from ospra_os.api.image_routes import router as image_router  # type: ignore
    _HAS_IMAGE_PROCESSING = True
    logger.info("Image Processing router loaded successfully")
except Exception as e:
    logger.warning(f"Image Processing router not loaded: {e}")
    image_router = None
    _HAS_IMAGE_PROCESSING = False

# AI Chat router (Claude chat with learning context)
try:
    from ospra_os.api.ai_chat_routes import router as ai_chat_router  # type: ignore
    _HAS_AI_CHAT = True
    logger.info("AI Chat router loaded successfully")
except Exception as e:
    logger.warning(f"AI Chat router not loaded: {e}")
    ai_chat_router = None
    _HAS_AI_CHAT = False

# AI Image Generation router (DALL-E 3 brand images for Oubon Shop)
try:
    from ospra_os.api.image_generation_routes import router as image_generation_router  # type: ignore
    _HAS_IMAGE_GENERATION = True
    logger.info("AI Image Generation router loaded successfully")
except Exception as e:
    logger.warning(f"AI Image Generation router not loaded: {e}")
    image_generation_router = None
    _HAS_IMAGE_GENERATION = False

# Actions Queue router (AI-generated actions that require approval)
try:
    from ospra_os.api.actions_routes import router as actions_router  # type: ignore
    _HAS_ACTIONS = True
    logger.info("Actions Queue router loaded successfully")
except Exception as e:
    logger.warning(f"Actions Queue router not loaded: {e}")
    actions_router = None
    _HAS_ACTIONS = False

# Daily Brief router (Personalized morning summaries with AI actions)
try:
    from ospra_os.api.daily_brief_routes import router as daily_brief_router  # type: ignore
    _HAS_DAILY_BRIEF = True
    logger.info("Daily Brief router loaded successfully")
except Exception as e:
    logger.warning(f"Daily Brief router not loaded: {e}")
    daily_brief_router = None
    _HAS_DAILY_BRIEF = False

# Auto-Pilot router (Autonomous action execution - GROK RECOMMENDATION #7)
# NOTE: Using autopilot_routes.py (consolidated - auto_pilot_routes.py was duplicate)
try:
    from ospra_os.api.autopilot_routes import router as auto_pilot_router  # type: ignore
    _HAS_AUTO_PILOT = True
except Exception as e:
    auto_pilot_router = None
    _HAS_AUTO_PILOT = False

# Voice Commands router (Whisper API integration - GROK RECOMMENDATION #9)
try:
    from ospra_os.api.voice_routes import router as voice_router  # type: ignore
    _HAS_VOICE = True
    logger.info("Voice Commands router loaded successfully")
except Exception as e:
    logger.warning(f"Voice Commands router not loaded: {e}")
    voice_router = None
    _HAS_VOICE = False

# Store Management router (Multi-Store Selector - GROK RECOMMENDATION #11)
try:
    from ospra_os.api.store_routes import router as store_router  # type: ignore
    _HAS_STORES = True
    logger.info("Store Management router loaded successfully")
except Exception as e:
    logger.warning(f"Store Management router not loaded: {e}")
    store_router = None
    _HAS_STORES = False

# Template Vault router (Action Template Marketplace - GROK RECOMMENDATION #12)
try:
    from ospra_os.api.template_routes import router as template_router  # type: ignore
    _HAS_TEMPLATES = True
    logger.info("Template Vault router loaded successfully")
except Exception as e:
    logger.warning(f"Template Vault router not loaded: {e}")
    template_router = None
    _HAS_TEMPLATES = False

# Task Monitoring router (Celery Task Queue - GROK RECOMMENDATION #13)
try:
    from ospra_os.api.task_routes import router as task_router  # type: ignore
    _HAS_TASKS = True
    logger.info("Task Monitoring router loaded successfully")
except Exception as e:
    logger.warning(f"Task Monitoring router not loaded: {e}")
    task_router = None
    _HAS_TASKS = False

# ML System router (GROK RECOMMENDATION #15 - Llama Fine-Tuning for 70% Cost Savings)
try:
    from ospra_os.api.ml_routes import router as ml_router  # type: ignore
    _HAS_ML = True
    logger.info("ML System router loaded successfully (Cost-optimized AI)")
except Exception as e:
    logger.warning(f"ML System router not loaded: {e}")
    ml_router = None
    _HAS_ML = False

# Amazon FBA router (GROK RECOMMENDATION #16 - Amazon FBA Multi-Marketplace Integration)
try:
    from ospra_os.api.amazon_routes import router as amazon_router  # type: ignore
    _HAS_AMAZON = True
    logger.info("Amazon FBA router loaded successfully (Multi-Marketplace)")
except Exception as e:
    logger.warning(f"Amazon FBA router not loaded: {e}")
    amazon_router = None
    _HAS_AMAZON = False

# Federated Learning router (GROK RECOMMENDATION #18 - Privacy-Preserving Collective Intelligence)
try:
    from ospra_os.federated.routes import get_federated_router
    federated_router = get_federated_router()
    _HAS_FEDERATED = True
    logger.info("Federated Learning router loaded successfully (Privacy-Preserving)")
except Exception as e:
    logger.warning(f"Federated Learning router not loaded: {e}")
    federated_router = None
    _HAS_FEDERATED = False

# White-Label SaaS router (GROK RECOMMENDATION #19 - Agency Rebrand B2B2C)
try:
    from ospra_os.whitelabel.routes import get_whitelabel_router
    whitelabel_router = get_whitelabel_router()
    _HAS_WHITELABEL = True
    logger.info("White-Label SaaS router loaded successfully (Agency Rebrand B2B2C)")
except Exception as e:
    logger.warning(f"White-Label SaaS router not loaded: {e}")
    whitelabel_router = None
    _HAS_WHITELABEL = False

# Feedback Loop router (G4: Complete Feedback Loop - AI learns from real sales data)
try:
    from ospra_os.api.feedback_routes import router as feedback_router  # type: ignore
    _HAS_FEEDBACK = True
    logger.info("Feedback Loop router loaded successfully (G4: AI learns from sales)")
except Exception as e:
    logger.warning(f"Feedback Loop router not loaded: {e}")
    feedback_router = None
    _HAS_FEEDBACK = False

# Marketing API router (Marketing angles, A/B testing)
try:
    from ospra_os.api.marketing_routes import router as marketing_router  # type: ignore
    _HAS_MARKETING = True
    logger.info("Marketing routes loaded successfully")
except Exception as e:
    logger.warning(f"Marketing routes not loaded: {e}")
    marketing_router = None
    _HAS_MARKETING = False

# Live Trends router (Real-time product momentum)
try:
    from ospra_os.api.trends_routes import router as trends_router  # type: ignore
    _HAS_TRENDS = True
    logger.info("Trends routes loaded successfully")
except Exception as e:
    logger.warning(f"Trends routes not loaded: {e}")
    trends_router = None
    _HAS_TRENDS = False

# Product Rankings router retired (#57) — read never-written ORM tables; replaced
# by product_timeseries + lifecycle grade.
_HAS_RANKINGS = False
rankings_router = None

# ============================================================================
# BILLING / SUBSCRIPTION ROUTERS (LemonSqueezy)
# Wired up in Pass 2 cleanup — these route files existed but weren't included.
# Without them: /api/subscription/upgrade, /api/webhooks/lemonsqueezy/* etc.
# return 404 and LemonSqueezy webhooks silently drop.
# ============================================================================
try:
    from ospra_os.payments.routes import router as payments_router  # type: ignore
    _HAS_PAYMENTS = True
    logger.info("Payments router loaded successfully")
except Exception as e:
    logger.warning(f"Payments router not loaded: {e}")
    payments_router = None
    _HAS_PAYMENTS = False

try:
    from ospra_os.api.subscription_routes import router as subscription_router  # type: ignore
    _HAS_SUBSCRIPTION = True
    logger.info("Subscription router loaded successfully")
except Exception as e:
    logger.warning(f"Subscription router not loaded: {e}")
    subscription_router = None
    _HAS_SUBSCRIPTION = False

try:
    from ospra_os.api.webhook_routes import router as webhook_router  # type: ignore
    _HAS_WEBHOOKS = True
    logger.info("Webhook router loaded successfully (LemonSqueezy + Shopify + CJ)")
except Exception as e:
    logger.warning(f"Webhook router not loaded: {e}")
    webhook_router = None
    _HAS_WEBHOOKS = False

try:
    from ospra_os.api.user_routes import router as user_router  # type: ignore
    _HAS_USER_ROUTES = True
    logger.info("User routes loaded successfully")
except Exception as e:
    logger.warning(f"User routes not loaded: {e}")
    user_router = None
    _HAS_USER_ROUTES = False

# Public no-auth routes (task #52 — live scoreboard marketing page)
try:
    from ospra_os.api.public_routes import router as public_router  # type: ignore
    _HAS_PUBLIC_ROUTES = True
    logger.info("Public routes loaded successfully (scoreboard)")
except Exception as e:
    logger.warning(f"Public routes not loaded: {e}")
    public_router = None
    _HAS_PUBLIC_ROUTES = False

# Import GmailClient for the OAuth callback
try:
    from app.gmail_client import GmailClient
    logger.info("GmailClient loaded from app.gmail_client")
except Exception as e:
    logger.warning(f"Could not import GmailClient: {e}")
    GmailClient = None

# ============================================================================
# OPENAPI CONFIGURATION - Enhanced API Documentation
# ============================================================================

# Tag metadata for better API organization
tags_metadata = [
    {
        "name": "Authentication",
        "description": "User authentication, registration, and password management. **Rate limited for security.**",
    },
    {
        "name": "User",
        "description": "User profile and subscription management.",
    },
    {
        "name": "Stores",
        "description": "Multi-store management with cross-store learning capabilities.",
    },
    {
        "name": "Analytics",
        "description": "Revenue, profit, and performance analytics across all stores.",
    },
    {
        "name": "Intelligence Engine",
        "description": "AI-powered trend discovery, product analysis, and recommendations.",
    },
    {
        "name": "Actions",
        "description": "AI-suggested actions with auto-pilot execution capabilities.",
    },
    {
        "name": "Payments",
        "description": "Subscription billing and payment management via LemonSqueezy.",
    },
    {
        "name": "AliExpress",
        "description": "AliExpress OAuth and product sourcing integration.",
    },
    {
        "name": "Voice",
        "description": "Voice commands using OpenAI Whisper and text-to-speech.",
    },
    {
        "name": "Learning",
        "description": "Hybrid learning system that improves AI accuracy over time.",
    },
    {
        "name": "Reports",
        "description": "Generate and schedule business reports.",
    },
    {
        "name": "Templates",
        "description": "Action template marketplace for automation workflows.",
    },
]

# ---------------------------------------------------------------
# Lifespan (Pass 4d): replaces the deprecated @app.on_event pair.
#
# FastAPI 0.100+ emits DeprecationWarning on @app.on_event and will remove it
# in a future major. The lifespan async-context-manager form is equivalent:
# everything before `yield` runs on startup, everything after runs on
# shutdown. Forward references to `_run_startup` / `_run_shutdown` are safe
# because lookup happens at call time, not at definition time — both helpers
# are defined later in this module.
# ---------------------------------------------------------------
from contextlib import asynccontextmanager  # noqa: E402  (kept near use)


@asynccontextmanager
async def app_lifespan(app: "FastAPI"):  # type: ignore[name-defined]
    """
    Startup -> yield -> shutdown. See `_run_startup_critical`,
    ``_run_startup_deferred`` and ``_run_shutdown``.

    Cold-start optimization (Pass 4d-followup): the startup work is split
    in two. ``_run_startup_critical`` only does what request handlers
    genuinely need to be in place (DB schema). Everything else — schedulers,
    AliExpress token refresh, sentiment refresher, etc. — runs in
    ``_run_startup_deferred`` as a fire-and-forget background task so the
    lifespan can ``yield`` and uvicorn can start serving traffic
    seconds sooner. On Render Starter (1 vCPU, scales to zero) this turns
    a ~30–60 s blocking startup into a ~3–5 s one.
    """
    import asyncio as _asyncio

    try:
        await _run_startup_critical()
    except Exception as e:  # pragma: no cover - startup failures are logged below
        logger.error(f"Startup error bubbled to lifespan: {e}")
        raise

    # Schedule the deferred work but do NOT await it. If something in the
    # deferred phase fails we log it but never block the app.
    deferred_task = _asyncio.create_task(_run_startup_deferred())

    def _log_deferred_done(t: "_asyncio.Task") -> None:
        if t.cancelled():
            return
        exc = t.exception()
        if exc is not None:
            logger.error(f"Deferred startup task failed: {exc}")

    deferred_task.add_done_callback(_log_deferred_done)

    try:
        yield
    finally:
        # Best-effort: give the deferred task a chance to finish on shutdown
        # so any half-initialized scheduler can clean up.
        if not deferred_task.done():
            deferred_task.cancel()
            try:
                await deferred_task
            except (_asyncio.CancelledError, Exception):
                pass
        try:
            await _run_shutdown()
        except Exception as e:  # pragma: no cover - shutdown is best-effort
            logger.error(f"Shutdown error bubbled to lifespan: {e}")


# SECURITY: interactive API docs (and the openapi.json schema that powers them)
# are disabled in production — they expose the full route surface to anyone.
# Re-enable temporarily by setting EXPOSE_API_DOCS=true (e.g. on staging).
_EXPOSE_DOCS = (
    os.getenv("EXPOSE_API_DOCS", "").lower() == "true"
    or not (
        os.getenv("ENVIRONMENT", "").lower() in ("production", "prod")
        or os.getenv("RENDER", "") == "true"
    )
)

app = FastAPI(
    title="Ospra OS API",
    description="""
## Ospra OS - AI-Powered E-Commerce Automation Platform

Ospra OS provides intelligent automation for e-commerce businesses with features including:

- **AI Product Discovery** - Find trending products using Google Trends, Reddit, and social signals
- **Multi-Store Management** - Manage Shopify, Amazon, WooCommerce stores from one dashboard
- **Smart Actions** - AI-suggested actions with auto-pilot execution
- **Cross-Store Learning** - AI learns from your sales data to improve recommendations
- **Voice Commands** - Control your business with voice using Whisper API

### Security Features

- JWT-based authentication with refresh tokens
- Rate limiting on all endpoints (tier-based)
- Strict validation on all inputs
- Encrypted credential storage

### Rate Limits

Rate limits vary by subscription tier:
- **Nest (Free)**: 30 API requests/minute, 5 AI requests/minute
- **Flight**: 100 API requests/minute, 15 AI requests/minute
- **Soar**: 300 API requests/minute, 30 AI requests/minute
- **Stratosphere**: 1000 API requests/minute, 100 AI requests/minute

### Support

For API support, contact support@ospra.io
    """,
    version="2.0.0",
    openapi_tags=tags_metadata,
    docs_url="/docs" if _EXPOSE_DOCS else None,
    redoc_url="/redoc" if _EXPOSE_DOCS else None,
    openapi_url="/openapi.json" if _EXPOSE_DOCS else None,
    contact={
        "name": "Ospra Support",
        "email": "support@ospra.io",
    },
    license_info={
        "name": "Proprietary",
    },
    lifespan=app_lifespan,
)

#
# SECURITY: Rate Limiting Setup (PHASE 1)
# Must be configured BEFORE middleware to protect all endpoints
#
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
logger.info("✓ Rate limiting enabled (Phase 1 Security)")

#
# OBSERVABILITY SETUP (TECHNICAL FIX T5)
# Must be configured BEFORE other middleware for proper request tracking
#
if _HAS_OBSERVABILITY:
    settings = get_settings()

    # Setup structured logging
    setup_logging(
        log_level=settings.LOG_LEVEL,
        log_format=settings.LOG_FORMAT
    )

    # Setup Sentry error tracking
    if settings.SENTRY_DSN:
        setup_sentry(
            dsn=settings.SENTRY_DSN,
            environment=settings.SENTRY_ENVIRONMENT,
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            profiles_sample_rate=settings.SENTRY_PROFILES_SAMPLE_RATE
        )

    # Setup PostHog analytics (task #38) — feature flags + activation funnel
    if settings.POSTHOG_ENABLED and settings.POSTHOG_API_KEY:
        try:
            from ospra_os.observability.posthog_client import setup_posthog
            setup_posthog(
                api_key=settings.POSTHOG_API_KEY,
                host=settings.POSTHOG_HOST,
                debug=settings.POSTHOG_DEBUG,
            )
        except Exception as _e:
            logger.warning(f"PostHog init failed (analytics disabled): {_e}")

    # Register exception handlers
    register_exception_handlers(app)

    # Add request logging middleware
    app.add_middleware(RequestLoggingMiddleware)

    logger.info("[SUCCESS] Observability initialized successfully")

# Security Headers Middleware (CRITICAL SECURITY)
# Adds X-Frame-Options, X-Content-Type-Options, HSTS, CSP, etc.
from ospra_os.middleware.security_headers import SecurityHeadersMiddleware
app.add_middleware(SecurityHeadersMiddleware, enable_hsts=True)
logger.info("✓ Security headers middleware active (XSS, Clickjacking, HSTS protection)")

#
# CORS middleware - Restricted to ospra.io + localhost for dev (PHASE 1 SECURITY)
#
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        # Production domains - Primary ospra.io domain only
        "https://ospra.io",
        "https://www.ospra.io",
        "https://app.ospra.io",
        # Development - Localhost only (all ports for flexibility)
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:5176",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
        "http://127.0.0.1:5176",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Store-ID"],
)
logger.info("✓ CORS restricted to ospra.io + localhost (Phase 1 Security)")

# Request Timeout Protection (PHASE 1 SECURITY)
# Prevents requests from hanging indefinitely by enforcing 30-second timeout
from ospra_os.middleware.timeout_middleware import TimeoutMiddleware
app.add_middleware(TimeoutMiddleware, timeout_seconds=30)
logger.info("✓ Request timeout protection active (30s limit)")

# Custom Rate Limiting (PHASE 1 SECURITY)
# In-memory rate limiter with tier-based limits (upgradable to Redis)
from ospra_os.middleware.custom_rate_limiter import CustomRateLimitMiddleware
app.add_middleware(CustomRateLimitMiddleware, get_tier_limit_func=get_tier_limit)
logger.info("✓ Custom rate limiting active (tier-based, in-memory)")

# Trust proxy headers from Render (for HTTPS URL generation)
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

# Multi-Tenant Isolation (GROK RECOMMENDATION #14)
# IMPORTANT: These middleware run AFTER auth, extracting tenant context from JWT
# Order matters: Tenant middleware must come after CORS/Proxy but before routes
app.add_middleware(StoreContextMiddleware)  # Extract store_id from query params/headers
app.add_middleware(TenantMiddleware)  # Extract tenant_id from JWT token
logger.info("Tenant isolation middleware registered (GROK #14)")

# Tier Enforcement (PHASE 1 SECURITY)
# Enforces subscription limits and feature access based on user tier
from ospra_os.middleware.tier_enforcement import TierEnforcementMiddleware
app.add_middleware(TierEnforcementMiddleware)
logger.info("✓ Tier enforcement middleware active (Phase 1 Security)")

# Debug Endpoint Protection (CRITICAL SECURITY)
# Blocks /debug/* routes in production to prevent information leakage
from ospra_os.security.debug_protection import DebugEndpointProtectionMiddleware
app.add_middleware(DebugEndpointProtectionMiddleware)
logger.info("✓ Debug endpoint protection active (blocks /debug/* in production)")

# Request Tracing Middleware (OBSERVABILITY)
# Adds unique request IDs for tracking and debugging
from ospra_os.observability.request_tracing import RequestTracingMiddleware
app.add_middleware(RequestTracingMiddleware)
logger.info("✓ Request tracing middleware active (X-Request-ID headers)")

# Mount static files for product images (only if directory exists)
import os
from pathlib import Path

# Use absolute path to ensure static files work regardless of working directory
PROJECT_ROOT = Path(__file__).parent.parent
images_dir = PROJECT_ROOT / "data" / "images"
if not images_dir.exists():
    os.makedirs(images_dir, exist_ok=True)
    logger.info(f"Created images directory: {images_dir}")

# Also ensure enhanced subdirectory exists
enhanced_dir = images_dir / "enhanced"
enhanced_dir.mkdir(exist_ok=True)

logger.debug(f"Mounting /static/images -> {images_dir}")
app.mount("/static/images", StaticFiles(directory=str(images_dir)), name="images")

# ---------------------------------------------------------------
# CRITICAL: Immediate Health Check Endpoint
# Must be defined BEFORE heavy router imports to respond quickly
# This ensures Render health checks pass even during startup
# ---------------------------------------------------------------
@app.get("/health")
def health_check_immediate():
    """Immediate health check that responds before full initialization.

    Exposes the deployed git commit so "what code is prod actually running"
    is one curl away. Render injects RENDER_GIT_COMMIT; we also accept an
    explicit GIT_COMMIT override. This exists because a "green" deploy was
    silently serving stale pre-gate code (#54) with no way to verify it.
    """
    commit = (
        os.getenv("RENDER_GIT_COMMIT")
        or os.getenv("GIT_COMMIT")
        or "unknown"
    )
    return {
        "status": "ok",
        "service": "Ospra Intelligence Platform",
        "version": "2026-01-11",
        "commit": commit[:12],
    }

@app.get("/health/celery")
def celery_health():
    """
    Check Celery worker and task queue health.

    Returns:
    - healthy: Workers are running and responding
    - no_workers: No workers detected (Celery not started)
    - error: Unable to inspect Celery (Redis unavailable or config issue)
    """
    if not _HAS_TASKS:
        return {"status": "disabled", "message": "Celery tasks not loaded"}

    try:
        from ospra_os.celery_app import celery_app
        inspect = celery_app.control.inspect()
        active = inspect.active()

        if active:
            active_count = sum(len(tasks) for tasks in active.values())
            return {
                "status": "healthy",
                "workers": list(active.keys()),
                "active_tasks": active_count,
                "message": f"{len(active)} worker(s) online, {active_count} active task(s)"
            }
        else:
            return {
                "status": "no_workers",
                "workers": [],
                "message": "No Celery workers detected. Start workers with: celery -A ospra_os.celery_app worker"
            }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "message": "Unable to connect to Celery. Ensure Redis is running: docker-compose up redis -d"
        }

# ---------------------------------------------------------------
# Startup helper — invoked from the lifespan context manager above
# (migrated from @app.on_event("startup") in Pass 4d).
# ---------------------------------------------------------------
async def _run_startup_critical():
    """
    Minimum work that MUST finish before request handlers can serve traffic.

    Cold-start optimization (Pass 4d-followup): we used to do all 17 startup
    steps inline before yielding to uvicorn — schedulers, AliExpress token
    refresh, sentiment refresher, etc. On Render Starter that meant logins
    waited 30+ seconds even after the container was hot. The only step that
    request handlers genuinely need is ``init_database`` (otherwise they
    query nonexistent tables); everything else is moved to
    ``_run_startup_deferred`` and runs in the background.
    """
    import time
    import os

    # Skip startup initialization in test mode
    if os.getenv("APP_ENV") == "testing":
        logger.debug("Test mode detected - skipping startup initialization")
        return

    startup_start = time.time()
    logger.info(f"Critical startup initiated at {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Validate environment variables (cheap, but we want it visible in
    # the logs BEFORE we yield in case something is misconfigured).
    try:
        from ospra_os.core.env_validator import validate_environment
        env_result = validate_environment(fail_fast=False, require_ai_provider=True)
        if env_result["errors"]:
            logger.warning(f"Environment validation found {len(env_result['errors'])} error(s)")
        if env_result["warnings"]:
            logger.info(f"Environment validation found {len(env_result['warnings'])} warning(s)")
    except Exception as e:
        logger.warning(f"Environment validation failed: {e}")

    settings = get_settings()

    # The core DB init — handlers expect tables to exist. We deliberately
    # DON'T raise on the lighter-weight init_followup_db / init_analytics_db
    # / init_aliexpress_oauth_db calls, because those move to the deferred
    # phase below. Only ``init_database`` is hard-blocking.
    try:
        from ospra_os.database import init_database
        init_database(settings.database_url)
        logger.info("All database tables initialized (including users table)")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        import traceback
        traceback.print_exc()
        raise

    # Schema drift check. ``Base.metadata.create_all`` only CREATES
    # missing tables — it never ALTERs an existing one. So when a column
    # is added to a model after the table already exists, the gap is
    # silent until a query selects the new column. We surface it at
    # boot so it's findable in 30 seconds, not 30 minutes after a 500
    # at the worst possible moment. (Origin story: ``brand_name`` /
    # ``brand_descriptor`` added to User model during the SaaS-launch
    # refactor; bit prod login the next time the .venv was rebuilt.)
    try:
        from ospra_os.database.schema_drift import warn_on_drift
        warn_on_drift()
    except Exception as e:
        logger.warning(f"schema_drift check failed (non-fatal): {e}")

    critical_duration = time.time() - startup_start
    logger.info(f"Critical startup completed in {critical_duration:.2f}s — yielding to uvicorn")


async def _run_startup_deferred():
    """
    Everything else: schedulers, secondary DB init, network token refresh.

    Runs as a fire-and-forget task AFTER lifespan yields, so request
    handlers don't wait on it. Each step is wrapped in try/except — a
    scheduler that fails to start should not prevent the rest from
    starting, and certainly should not affect serving traffic.
    """
    import time
    import os

    if os.getenv("APP_ENV") == "testing":
        return

    startup_start = time.time()
    logger.info("Deferred startup initiated (background)")

    settings = get_settings()

    # Follow-up tracking tables (EmailFollowup) are created by the main
    # init_database() call in _run_startup_critical — they live in
    # ospra_os.database.email_models now, so the old app.models.init_followup_db
    # bootstrap is redundant and was removed during the app/ -> ospra_os/ migration.

    # Initialize analytics database (email_metrics / daily_stats tables)
    try:
        from ospra_os.analytics.email_analytics import init_analytics_db
        init_analytics_db(settings.database_url)
        logger.info("Analytics database initialized")
    except Exception as e:
        logger.warning(f"Analytics database initialization failed: {e}")

    # Initialize AliExpress OAuth database
    try:
        from ospra_os.aliexpress.oauth import init_aliexpress_oauth_db
        init_aliexpress_oauth_db(settings.database_url)
        logger.info("AliExpress OAuth database initialized")
    except Exception as e:
        logger.warning(f"AliExpress OAuth database initialization failed: {e}")

    # Initialize Ad Schedule database
    try:
        from ospra_os.models.ad_schedule import Base
        from ospra_os.database.connection import get_engine
        engine = get_engine(settings.database_url)
        Base.metadata.create_all(engine)
        logger.info("Ad Schedule database initialized")
    except Exception as e:
        logger.warning(f"Ad Schedule database initialization failed: {e}")

    # Initialize Report database
    try:
        from ospra_os.models.report import init_report_tables
        from ospra_os.database.connection import get_engine
        engine = get_engine(settings.database_url)
        init_report_tables(engine)
        logger.info("Report database initialized")
    except Exception as e:
        logger.warning(f"Report database initialization failed: {e}")

    # Start report scheduler
    try:
        from ospra_os.reports.scheduler import get_scheduler
        scheduler = get_scheduler()
        await scheduler.start()
        logger.info("Report scheduler started")
    except Exception as e:
        logger.warning(f"Report scheduler failed to start: {e}")

    # Start background schedule processor
    try:
        from ospra_os.jobs.schedule_processor import start_schedule_processor
        start_schedule_processor()
        logger.info("Schedule processor started (runs every 5 minutes)")
    except Exception as e:
        logger.warning(f"Schedule processor failed to start: {e}")

    # DEPRECATED: APScheduler replaced by Celery Beat (GROK #13)
    # Background email checking is now handled by Celery tasks
    # See: ospra_os/tasks/email_tasks.py
    # To enable: Use Celery Beat scheduler instead
    # try:
    #     from app.scheduler import start_scheduler
    #     start_scheduler()
    #     logger.info("Background scheduler started")
    # except Exception as e:
    #     logger.warning(f"Scheduler failed to start: {e}")
    logger.info(" Email scheduling managed by Celery Beat (see /api/tasks/beat-schedule)")

    # Start product monitoring in background thread
    try:
        from ospra_os.background_jobs.product_monitor import ProductMonitor
        from threading import Thread
        import time

        monitor = ProductMonitor()

        def monitoring_task():
            """Background task to monitor product changes every 6 hours"""
            while True:
                try:
                    logger.info("[SEARCH] Running product change detection...")
                    changes = monitor.check_all_products()

                    if changes:
                        logger.info(f"[SUCCESS] Detected {len(changes)} product changes")
                        notification = monitor.format_notification(changes)
                        logger.info(f"Product changes notification:\n{notification}")

                        # Mark as notified
                        monitor.db.mark_all_notified()

                    # Show stats
                    stats = monitor.get_stats()
                    logger.info(f"[STATS] Monitor stats: {stats['tracked_products']} products tracked")

                except Exception as e:
                    logger.error(f"Product monitoring error: {e}")

                # Wait 6 hours
                time.sleep(6 * 60 * 60)

        # Start monitoring thread
        monitor_thread = Thread(target=monitoring_task, daemon=True)
        monitor_thread.start()
        logger.info("Product monitoring started (6-hour intervals)")

    except Exception as e:
        logger.warning(f"Product monitoring failed to start: {e}")

    # Start Level 3 AI background jobs
    try:
        from ospra_os.intelligence.background_jobs import start_background_jobs

        start_background_jobs()
        logger.info("[SUCCESS] Level 3 AI activated - background monitoring enabled")
        logger.info("Level 3 AI activated - background monitoring enabled")
    except Exception as e:
        logger.warning(f"Level 3 AI not available - continuing without background monitoring: {e}")

    # Start auto-discovery background scheduler
    if _HAS_AUTO_DISCOVERY and start_auto_discovery_scheduler:
        try:
            import os
            # Check if auto-discovery is enabled in environment
            auto_discovery_enabled = os.getenv('AUTO_DISCOVERY_ENABLED', 'true').lower() == 'true'

            if auto_discovery_enabled and settings.database_url:
                discovery_hour = int(os.getenv('DISCOVERY_HOUR', '3'))  # Default: 3 AM
                discovery_interval = os.getenv('DISCOVERY_INTERVAL_HOURS')

                if discovery_interval:
                    # Interval-based scheduling
                    start_auto_discovery_scheduler(
                        database_url=settings.database_url,
                        interval_hours=int(discovery_interval)
                    )
                    logger.info(f"Auto-discovery scheduler started (every {discovery_interval} hours)")
                else:
                    # Daily scheduling
                    start_auto_discovery_scheduler(
                        database_url=settings.database_url,
                        hour=discovery_hour
                    )
                    logger.info(f"Auto-discovery scheduler started (daily at {discovery_hour:02d}:00)")
            else:
                logger.warning("Auto-discovery disabled in environment or no database URL")
        except Exception as e:
            logger.warning(f"Auto-discovery scheduler failed to start: {e}")
            import traceback
            traceback.print_exc()

    # Daily ranking scheduler retired (#57): ranking subsystem removed — it read
    # never-written ORM tables and the new product_timeseries + lifecycle grade
    # replace its purpose. (daily_ranking_job / ranking_engine / rankings_routes)

    # Start realtime momentum updater
    try:
        from ospra_os.intelligence.realtime_updater import start_realtime_updates

        await start_realtime_updates()
        logger.info("Realtime momentum updater started (5-minute intervals)")
    except Exception as e:
        logger.warning(f"Realtime momentum updater failed to start: {e}")
        import traceback
        traceback.print_exc()

    # DEPRECATED: APScheduler replaced by Celery Beat (GROK #13)
    # Customer analytics jobs are now handled by Celery tasks
    # See: ospra_os/tasks/analytics_tasks.py and ospra_os/tasks/learning_tasks.py
    # To enable: Use Celery Beat scheduler instead
    # try:
    #     from ospra_os.jobs.scheduler import start_scheduler as start_customer_scheduler
    #     start_customer_scheduler()
    #     logger.info("Customer analytics scheduler started")
    # except Exception as e:
    #     logger.warning(f"Customer analytics scheduler failed to start: {e}")
    logger.info(" Customer analytics managed by Celery Beat (see /api/tasks/beat-schedule)")

    # Start AliExpress token refresh scheduler
    #
    # Cold-start note: ``check_tokens_on_startup`` makes an outbound HTTP
    # call to AliExpress, which can be slow or hang on regional issues. We
    # run it as its own sub-task with a hard timeout so a slow AliExpress
    # response can never stall the rest of deferred startup. The scheduler
    # itself (which runs the same check on a cadence) is started
    # synchronously since that's just APScheduler config.
    try:
        from ospra_os.api.aliexpress_token_scheduler import (
            start_token_refresh_scheduler,
            check_tokens_on_startup,
        )
        import asyncio as _asyncio

        start_token_refresh_scheduler()

        async def _bounded_aliexpress_check() -> None:
            try:
                await _asyncio.wait_for(check_tokens_on_startup(), timeout=15.0)
                logger.info("AliExpress startup token check completed")
            except _asyncio.TimeoutError:
                logger.warning(
                    "AliExpress startup token check timed out after 15s "
                    "— scheduler will retry on its next tick"
                )
            except Exception as e:
                logger.warning(f"AliExpress startup token check failed: {e}")

        _asyncio.create_task(_bounded_aliexpress_check())
        logger.info("AliExpress token refresh scheduler started")
    except Exception as e:
        logger.warning(f"AliExpress token refresh scheduler failed to start: {e}")

    # Start Auto-Deploy scheduler
    try:
        from ospra_os.background_jobs.auto_deploy_job import start_auto_deploy_scheduler
        start_auto_deploy_scheduler()
        logger.info("Auto-deploy scheduler started (runs every hour)")
    except Exception as e:
        logger.warning(f"Auto-deploy scheduler failed to start: {e}")

    # Start Discovery Cache Warmer — keeps the (niche, tier) discovery cache hot
    # in the background so the dashboard reads instantly instead of triggering a
    # ~80s live discovery on the request path (which Safari times out at ~60s).
    # Reuses the SAME engine singleton the discovery route uses (get_engine()).
    try:
        from ospra_os.intelligence.unified_discovery_routes import get_engine
        from ospra_os.intelligence.cache_warmer import start_cache_warmer
        start_cache_warmer(get_engine().discover_products)
        logger.info("Discovery cache warmer started (background pre-warm)")
    except Exception as e:
        logger.warning(f"Discovery cache warmer failed to start: {e}")

    # Start Learning Summary background jobs
    try:
        from ospra_os.learning.summary_jobs import setup_summary_jobs
        setup_summary_jobs()
        logger.info("Learning summary jobs started (nightly at 3:00 AM UTC)")
    except Exception as e:
        logger.warning(f"Learning summary jobs failed to start: {e}")

    # Task #17: Sentiment refresh on watched products (every 4 hours).
    # Live social sentiment is the stated differentiator, so we keep watched
    # (QUEUED/DEPLOYED/ACTIVE) products' sentiment fresh in the background.
    try:
        from ospra_os.intelligence.sentiment_refresher import start_sentiment_refresh_scheduler
        start_sentiment_refresh_scheduler()
    except Exception as e:
        logger.warning(f"Sentiment refresh scheduler failed to start: {e}")

    # Audit fix #5 — webhook DLQ retry worker. Picks up failed background
    # tasks (rows in ``webhook_failures``) every minute and retries with
    # exponential backoff. See ``ospra_os/webhooks/dlq.py`` for the full
    # contract. This is fire-and-forget; cancellation on shutdown is
    # handled by the lifespan deferred-task wrapper.
    try:
        import asyncio as _asyncio_dlq
        from ospra_os.webhooks.dlq import run_retry_worker
        _asyncio_dlq.create_task(run_retry_worker(interval_seconds=60))
        logger.info("Webhook DLQ retry worker started (60s interval)")
    except Exception as e:
        logger.warning(f"Webhook DLQ retry worker failed to start: {e}")

    # Log deferred-startup completion with timing. The "critical" portion
    # was already logged by ``_run_startup_critical`` before the lifespan
    # yielded; this number is the additional wall-clock time spent in the
    # background after traffic was being served.
    startup_duration = time.time() - startup_start
    logger.info(
        f"Deferred startup completed in {startup_duration:.2f} seconds "
        f"at {time.strftime('%Y-%m-%d %H:%M:%S')}"
    )


# ---------------------------------------------------------------
# Shutdown helper — invoked from the lifespan context manager above
# (migrated from @app.on_event("shutdown") in Pass 4d).
# ---------------------------------------------------------------
async def _run_shutdown():
    """Cleanup on shutdown"""
    logger.info("[PAUSE]  Shutting down Ospra Intelligence...")
    logger.info(" Shutting down Ospra Intelligence...")

    # Stop Level 3 AI background jobs
    try:
        from ospra_os.intelligence.background_jobs import stop_background_jobs
        stop_background_jobs()
        logger.info("[SUCCESS] Background jobs stopped")
        logger.info("Background jobs stopped")
    except Exception as e:
        logger.error(f"Error stopping background jobs: {e}")
        logger.warning(f"Error stopping background jobs: {e}")

    # Stop learning summary jobs
    try:
        from ospra_os.learning.summary_jobs import shutdown_summary_jobs
        shutdown_summary_jobs()
        logger.info("[SUCCESS] Learning summary jobs stopped")
        logger.info("Learning summary jobs stopped")
    except Exception as e:
        logger.error(f"Error stopping summary jobs: {e}")
        logger.warning(f"Error stopping summary jobs: {e}")

    # Stop realtime momentum updater
    try:
        from ospra_os.intelligence.realtime_updater import stop_realtime_updates
        await stop_realtime_updates()
        logger.info("[SUCCESS] Realtime momentum updater stopped")
        logger.info("Realtime momentum updater stopped")
    except Exception as e:
        logger.error(f"Error stopping realtime updater: {e}")
        logger.warning(f"Error stopping realtime updater: {e}")

    # Stop sentiment refresh scheduler (Task #17)
    try:
        from ospra_os.intelligence.sentiment_refresher import stop_sentiment_refresh_scheduler
        stop_sentiment_refresh_scheduler()
        logger.info("[SUCCESS] Sentiment refresh scheduler stopped")
    except Exception as e:
        logger.warning(f"Error stopping sentiment refresh scheduler: {e}")

    # Stop AliExpress token refresh scheduler
    try:
        from ospra_os.api.aliexpress_token_scheduler import stop_token_refresh_scheduler
        stop_token_refresh_scheduler()
        logger.info("[SUCCESS] AliExpress token refresh scheduler stopped")
        logger.info("AliExpress token refresh scheduler stopped")
    except Exception as e:
        logger.error(f"Error stopping token refresh scheduler: {e}")
        logger.warning(f"Error stopping token refresh scheduler: {e}")

    # Stop report scheduler
    try:
        from ospra_os.reports.scheduler import get_scheduler
        scheduler = get_scheduler()
        await scheduler.stop()
        logger.info("[SUCCESS] Report scheduler stopped")
        logger.info("Report scheduler stopped")
    except Exception as e:
        logger.error(f"Error stopping report scheduler: {e}")
        logger.warning(f"Error stopping report scheduler: {e}")

    # Stop customer analytics scheduler
    try:
        from ospra_os.jobs.scheduler import stop_scheduler as stop_customer_scheduler
        stop_customer_scheduler()
        logger.info("[SUCCESS] Customer analytics scheduler stopped")
        logger.info("Customer analytics scheduler stopped")
    except Exception as e:
        logger.error(f"Error stopping customer analytics scheduler: {e}")
        logger.warning(f"Error stopping customer analytics scheduler: {e}")

    # Flush pending PostHog events (task #38) — must happen before exit so we
    # don't drop activation-funnel events buffered in the async sender.
    try:
        from ospra_os.observability.posthog_client import shutdown as posthog_shutdown
        posthog_shutdown()
        logger.info("[SUCCESS] PostHog events flushed")
    except Exception as e:
        logger.warning(f"Error flushing PostHog events: {e}")


if gmail_oauth_router:
    app.include_router(gmail_oauth_router)  # exposes /gmail/auth/*

if _HAS_AUTH and auth_router:
    app.include_router(auth_router)  # exposes /api/auth/* (registration, login, JWT)

if _HAS_PASSWORD_RESET and password_reset_router:
    app.include_router(password_reset_router)  # exposes /api/auth/forgot-password, /api/auth/reset-password

if _HAS_ACCOUNT and account_router:
    app.include_router(account_router)  # exposes /api/account/data-summary, /data-export, /data-delete

if _HAS_FRONTEND_COMPAT and frontend_compat_router:
    app.include_router(frontend_compat_router)  # exposes /auth/* aliases + missing endpoints

if _HAS_TIKTOK and tiktok_router:
    app.include_router(tiktok_router)

if _HAS_RESEARCH and research_router:
    app.include_router(research_router)  # exposes /research/*

if _HAS_ADMIN and admin_router:
    app.include_router(admin_router)  # exposes /admin/*

if _HAS_DASHBOARD_V2 and dashboard_v2_router:
    app.include_router(dashboard_v2_router)  # exposes /api/dashboard/v2/* (REAL-TIME)

if _HAS_MULTI_STORE and multi_store_router:
    app.include_router(multi_store_router)  # exposes /api/portfolio/*

if _HAS_ALIEXPRESS and aliexpress_router:
    app.include_router(aliexpress_router)  # exposes /api/aliexpress/*

# AliExpress Dropshipping API OAuth callback
if _HAS_ALIEXPRESS_CALLBACK and aliexpress_callback_router:
    app.include_router(aliexpress_callback_router)

# AliExpress Affiliate API OAuth callback
if _HAS_ALIEXPRESS_AFFILIATE_CALLBACK and aliexpress_affiliate_callback_router:
    app.include_router(aliexpress_affiliate_callback_router)  # exposes /api/aliexpress/callback and /api/aliexpress/oauth-callback

# AliExpress Token Management
if _HAS_ALIEXPRESS_TOKEN_MANAGEMENT and aliexpress_token_router:
    app.include_router(aliexpress_token_router)  # exposes /api/aliexpress/tokens/*

# AliExpress Product Scraping
if _HAS_ALIEXPRESS_PRODUCTS and aliexpress_product_router:
    app.include_router(aliexpress_product_router)  # exposes /api/aliexpress/products/*

if _HAS_TIKTOK_OAUTH and tiktok_oauth_router:
    app.include_router(tiktok_oauth_router)  # exposes /auth/tiktok/*

if _HAS_SHOPIFY_WEBHOOKS and shopify_webhooks_router:
    app.include_router(shopify_webhooks_router)  # exposes /webhooks/shopify/*

if _HAS_SHOPIFY_OAUTH and shopify_oauth_router:
    app.include_router(shopify_oauth_router)  # exposes /oauth/shopify/*

if _HAS_SHOPIFY_DEPLOYMENT and shopify_deployment_router:
    app.include_router(shopify_deployment_router)  # exposes /api/shopify/* (AI-powered deployment)

if _HAS_SHOPIFY_STORES and shopify_store_router:
    app.include_router(shopify_store_router)  # exposes /api/shopify/* (Store management & OAuth)

if _HAS_WOOCOMMERCE and woocommerce_router:
    app.include_router(woocommerce_router)  # exposes /api/woocommerce/* (Universal OAuth - any WC store)

# Meta Ads Router (Real API only - No demo data)
if _HAS_META_ADS and meta_ads_router:
    app.include_router(meta_ads_router)  # exposes /api/meta/* (Real Meta Ads API)

if _HAS_ADVERTISING and advertising_router:
    app.include_router(advertising_router)  # exposes /api/ads/*

if _HAS_EMAIL_OAUTH and email_oauth_router:
    app.include_router(email_oauth_router)  # exposes /api/email-oauth/*

if _HAS_EMAIL_ANALYTICS and email_analytics_router:
    app.include_router(email_analytics_router)  # exposes /api/dashboard/emails, /api/emails/*

if _HAS_EMAIL_SYNC and email_sync_router:
    app.include_router(email_sync_router)  # exposes /api/emails/*

if _HAS_EMAIL_AUTOMATION and email_automation_router:
    app.include_router(email_automation_router)  # exposes /api/email-automation/*

if _HAS_EMAIL_SETTINGS and email_settings_router:
    app.include_router(email_settings_router)  # exposes /api/email-settings

if _HAS_DEPLOYMENT and deployment_router:
    app.include_router(deployment_router)  # exposes /api/deploy/*

if _HAS_AUTO_DEPLOY and auto_deploy_router:
    app.include_router(auto_deploy_router)  # exposes /api/auto-deploy/*

if _HAS_ANALYTICS and analytics_router:
    app.include_router(analytics_router)  # exposes /api/analytics/*

if _HAS_CUSTOMER_ANALYTICS and customer_analytics_router:
    app.include_router(customer_analytics_router)  # exposes /api/customers/*

if _HAS_JOBS and jobs_router:
    app.include_router(jobs_router)  # exposes /api/jobs/*

if _HAS_NOTIFICATIONS and notifications_router:
    app.include_router(notifications_router)  # exposes /api/notifications/*

if _HAS_HEALTH_MONITOR and health_monitor_router:
    app.include_router(health_monitor_router)  # exposes /api/health/*

if _HAS_NICHE_ANALYSIS and niche_router:
    app.include_router(niche_router)  # exposes /api/niches/*

if _HAS_COMPETITOR_INTEL and competitor_router:
    app.include_router(competitor_router)  # exposes /api/competitors/*

if _HAS_REPORTS and report_router:
    app.include_router(report_router)  # exposes /api/reports/*

if _HAS_UNIFIED_DISCOVERY and unified_discovery_router:
    app.include_router(unified_discovery_router)  # exposes /api/discovery/*

if _HAS_INTELLIGENCE_CORE and intelligence_core_router:
    app.include_router(intelligence_core_router)  # exposes /api/intelligence/*

if _HAS_LEARNING and learning_router:
    app.include_router(learning_router)  # exposes /api/learning/*

# Fulfillment System (Auto-fulfillment, tracking, supplier integration)
if _HAS_FULFILLMENT and fulfillment_router:
    app.include_router(fulfillment_router)  # exposes /api/fulfillment/*

# Oi AI Assistant (The Brain of Ospra Intelligence)
if _HAS_OI and oi_router:
    app.include_router(oi_router)  # exposes /api/oi/* (AI chat, actions, context)

# Product Analysis (AI analysis and caption generation)
if _HAS_PRODUCT_ANALYSIS and product_analysis_router:
    app.include_router(product_analysis_router)  # exposes /api/oi/analyze-product, /api/oi/generate-caption

# Oi Alerts (Real-time notifications for Oi AI)
if _HAS_ALERTS and alert_router:
    app.include_router(alert_router)  # exposes /api/oi/alerts/* (CRUD endpoints)
if _HAS_ALERTS and alert_ws_router:
    app.include_router(alert_ws_router)  # exposes /ws/oi/alerts (WebSocket)

if _HAS_INVENTORY and inventory_router:
    app.include_router(inventory_router)  # exposes /api/inventory/*

if _HAS_ABTESTING and abtesting_router:
    app.include_router(abtesting_router)  # exposes /api/abtesting/*

if _HAS_IMAGE_PROCESSING and image_router:
    app.include_router(image_router)  # exposes /api/images/*

if _HAS_AI_CHAT and ai_chat_router:
    app.include_router(ai_chat_router, prefix="/api")  # exposes /api/ai/chat and /api/claude/chat

if _HAS_IMAGE_GENERATION and image_generation_router:
    app.include_router(image_generation_router)  # exposes /api/images/generate, /api/images/status (AI product images)

if _HAS_ACTIONS and actions_router:
    app.include_router(actions_router)  # exposes /api/actions/* (AI action queue)

if _HAS_DAILY_BRIEF and daily_brief_router:
    app.include_router(daily_brief_router)  # exposes /api/daily-brief (Personalized morning summaries)

if _HAS_AUTO_PILOT and auto_pilot_router:
    app.include_router(auto_pilot_router)  # exposes /api/auto-pilot/* (Autonomous action execution)

if _HAS_VOICE and voice_router:
    app.include_router(voice_router)  # exposes /api/voice/* (Voice commands with Whisper API)

if _HAS_STORES and store_router:
    app.include_router(store_router)  # exposes /api/stores/* (Multi-store management & cross-store learning - GROK #11)

if _HAS_TEMPLATES and template_router:
    app.include_router(template_router)  # exposes /api/templates/* (Action template marketplace - GROK #12)

if _HAS_TASKS and task_router:
    app.include_router(task_router)  # exposes /api/tasks/* (Celery task monitoring - GROK #13)

if _HAS_ML and ml_router:
    app.include_router(ml_router)  # exposes /api/ml/* (Cost-optimized AI - GROK #15)

if _HAS_AMAZON and amazon_router:
    app.include_router(amazon_router)  # exposes /api/amazon/* (Multi-Marketplace FBA - GROK #16)

if _HAS_FEDERATED and federated_router:
    app.include_router(federated_router)  # exposes /api/federated/* (Privacy-Preserving Collective Intelligence - GROK #18)

if _HAS_WHITELABEL and whitelabel_router:
    app.include_router(whitelabel_router)  # exposes /api/whitelabel/* (Agency Rebrand B2B2C - GROK #19)

if _HAS_FEEDBACK and feedback_router:
    app.include_router(feedback_router)  # exposes /api/feedback/* (G4: AI learns from real sales)

# Marketing routes (extracted from main.py for better organization)
if _HAS_MARKETING and marketing_router:
    app.include_router(marketing_router)  # exposes /api/marketing/*

# Trends routes (extracted from main.py for better organization)
if _HAS_TRENDS and trends_router:
    app.include_router(trends_router)  # exposes /api/trends/*

# Rankings routes retired (#57) — see notes above.

# Billing / subscription routers (LemonSqueezy) — wired up in Pass 2 cleanup
if _HAS_PAYMENTS and payments_router:
    app.include_router(payments_router)  # exposes /api/payments/*
if _HAS_SUBSCRIPTION and subscription_router:
    app.include_router(subscription_router)  # exposes /api/subscription/*
if _HAS_WEBHOOKS and webhook_router:
    app.include_router(webhook_router)  # exposes /api/webhooks/* (LemonSqueezy + Shopify + CJ)
if _HAS_USER_ROUTES and user_router:
    app.include_router(user_router)  # exposes /api/users/*
if _HAS_PUBLIC_ROUTES and public_router:
    app.include_router(public_router)  # exposes /api/public/* (no auth — scoreboard)

# keep a root-level callback because your Google OAuth client JSON often points here
@app.get("/oauth2callback", include_in_schema=False)
def oauth_cb_root(code: str, settings: Settings = Depends(get_settings)):
    if GmailClient is None:
        return {"error": "GmailClient not available"}
    gc = GmailClient(settings)
    gc.exchange_code_for_tokens(code)
    return RedirectResponse(url="/admin/dashboard")

# NOTE: Duplicate health endpoint commented out - using immediate health endpoint defined earlier
# This detailed health endpoint moved to line 446 to respond before heavy router initialization
# @app.get("/health")
# def health_check():
#     return {
#         "status": "ok",
#         "service": "Ospra Intelligence Platform",
#         "version": "2.0.0",
#         "features": {
#             "multi_store": _HAS_MULTI_STORE,
#             "ai_abstraction": _HAS_AI_FACTORY,
#             "platform_adapters": _HAS_PLATFORM_FACTORY,
#             "auto_discovery": _HAS_AUTO_DISCOVERY,
#             "unified_deployment": _HAS_UNIFIED_DEPLOYER,
#             "product_research": _HAS_RESEARCH,
#             "admin_dashboard": _HAS_ADMIN,
#             "dashboard_v2": _HAS_DASHBOARD_V2
#         },
#         "integrations": {
#             "gmail": gmail_oauth_router is not None,
#             "shopify": _HAS_MULTI_STORE or _HAS_SHOPIFY_WEBHOOKS,
#             "amazon": _HAS_PLATFORM_FACTORY,
#             "woocommerce": _HAS_PLATFORM_FACTORY,
#             "tiktok": _HAS_TIKTOK or _HAS_TIKTOK_OAUTH,
#             "aliexpress": _HAS_ALIEXPRESS,
#             "claude": _HAS_AI_FACTORY,
#             "openai": _HAS_AI_FACTORY,
#             "gemini": _HAS_AI_FACTORY
#         },
#         "legacy_status": {
#             "gmail_oauth_loaded": gmail_oauth_router is not None,
#             "gmail_client_loaded": GmailClient is not None,
#             "tiktok_loaded": _HAS_TIKTOK,
#             "tiktok_oauth_loaded": _HAS_TIKTOK_OAUTH,
#             "product_research_loaded": _HAS_RESEARCH,
#             "aliexpress_oauth_loaded": _HAS_ALIEXPRESS,
#             "multi_store_loaded": _HAS_MULTI_STORE
#         }
#     }


@app.get("/api/health/detailed")
async def detailed_health_check(settings: Settings = Depends(get_settings)):
    """
    Comprehensive health check with detailed system monitoring.

    Returns:
    - Database connectivity status
    - AI provider availability
    - Platform adapter status
    - Background job status
    - System resource usage (CPU, memory, disk)
    """
    if not _HAS_HEALTH_MONITOR or not HealthMonitor:
        return {
            "success": False,
            "error": "Health Monitor not available",
            "basic_status": "ok" if True else "error"
        }

    try:
        monitor = HealthMonitor(settings.database_url)
        health_status = await monitor.check_system_health()
        return health_status
    except Exception as e:
        # SECURITY: Log traceback server-side, don't expose to client
        logger.error(f"Health check failed: {e}", exc_info=True)
        return {
            "success": False,
            "status": "error",
            "error": "Health check failed. Please check server logs."
        }


# ---------------------------------------------------------------
# Admin & Testing Endpoints
# ---------------------------------------------------------------
@app.post("/api/admin/run-discovery-now")
async def run_discovery_now(settings: Settings = Depends(get_settings)):
    """
    Manual trigger for auto-discovery (for testing).

    Runs product discovery immediately for all active users.
    Useful for testing without waiting for the scheduled job.

    Returns:
        dict: Discovery results with products found, saved, deployed
    """
    if not _HAS_AUTO_DISCOVERY:
        return {
            "success": False,
            "error": "Auto-discovery system not available"
        }

    try:
        from ospra_os.background_jobs.auto_discovery import AutoDiscoveryJob

        # Create discovery job instance
        job = AutoDiscoveryJob(database_url=settings.database_url)

        # Run discovery for all users
        result = await job.run_discovery_for_all_users()

        return {
            "success": True,
            "message": "Discovery completed successfully",
            "results": result
        }

    except Exception as e:
        # SECURITY: Log traceback server-side, don't expose to client
        logger.error(f"Discovery job failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": "Discovery failed. Please check server logs."
        }


# ---------------------------------------------------------------
# Self-Learning System API Endpoints
# REMOVED: Now handled by secured routers/learning.py
# ---------------------------------------------------------------

# ---------------------------------------------------------------
# Unified Deployment API Endpoints
# REMOVED: Now handled by secured routers/deploy.py
# ---------------------------------------------------------------


# ---------------------------------------------------------------
# AI Provider Management API Endpoints
# REMOVED: Now handled by secured routers/ai_providers.py
# ---------------------------------------------------------------


# ---------------------------------------------------------------
# NEW: Platform Management API Endpoints
# ---------------------------------------------------------------
@app.get("/api/platforms")
async def get_platforms():
    """
    Get available e-commerce platforms.

    Returns:
        {
            "success": true,
            "platforms": [
                {
                    "name": "shopify",
                    "display_name": "Shopify",
                    "complexity": "medium",
                    "credentials_count": 2,
                    "features": {...}
                },
                ...
            ]
        }
    """
    if not _HAS_PLATFORM_FACTORY or not PlatformFactory:
        return {
            "success": False,
            "error": "Platform Factory not available"
        }

    try:
        platforms = PlatformFactory.get_available_platforms()
        return {
            "success": True,
            "platforms": platforms
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@app.post("/api/platforms/{platform}/test")
async def test_platform_credentials(
    platform: str,
    credentials: PlatformCredentials,
    settings: Settings = Depends(get_settings)
):
    """
    Test platform credentials.

    Args:
        platform: Platform name (shopify, amazon, woocommerce)
        credentials: Platform credentials

    Returns:
        {
            "success": true,
            "store_name": "My Store",
            "store_url": "https://mystore.myshopify.com",
            "platform_version": "2024-01"
        }
    """
    if not _HAS_PLATFORM_FACTORY or not PlatformFactory:
        return {"success": False, "error": "Platform Factory not available"}

    try:
        adapter = PlatformFactory.get_adapter(platform, credentials)
        result = await adapter.test_connection()
        return result
    except Exception as e:
        # SECURITY: Log traceback server-side, don't expose to client
        logger.error(f"Platform connection test failed for {platform}: {e}", exc_info=True)
        return {
            "success": False,
            "error": "Connection test failed. Please verify your credentials."
        }


# ---------------------------------------------------------------
# Dashboard API Endpoints
# REMOVED: Now handled by secured routers/dashboard.py
# These endpoints are available at:
# - GET /api/dashboard/overview
# - GET /api/dashboard/products
# - GET /api/dashboard/emails
# - GET /api/dashboard/shopify
# - GET /api/dashboard/api-status
# ---------------------------------------------------------------


@app.post("/api/discover")
async def discover_products_api(
    niche: str,
    max_results: int = 15,
    min_score: float = 5.0,
    include_reddit: bool = True,
    include_trends: bool = True,
    include_aliexpress: bool = False,
    settings: Settings = Depends(get_settings)
):
    """
    Run product discovery engine for a niche.

    This is the main endpoint for the new ProductDiscoveryEngine.

    Example request body:
        {
            "niche": "smart home devices",
            "max_results": 15,
            "min_score": 5.0,
            "include_reddit": true,
            "include_trends": true,
            "include_aliexpress": false
        }

    Returns:
        {
            "niche": str,
            "total_found": int,
            "high_priority": int,
            "medium_priority": int,
            "low_priority": int,
            "products": [...],
            "search_time": str
        }
    """
    try:
        from ospra_os.product_research.discovery import ProductDiscoveryEngine

        # Initialize engine
        engine = ProductDiscoveryEngine(
            reddit_client_id=settings.REDDIT_CLIENT_ID,
            reddit_secret=settings.REDDIT_SECRET,
            aliexpress_api_key=settings.ALIEXPRESS_API_KEY,
            aliexpress_app_secret=settings.ALIEXPRESS_APP_SECRET,
        )

        # Run discovery
        results = await engine.discover(
            niche=niche,
            max_results=max_results,
            min_score=min_score,
            include_reddit=include_reddit,
            include_trends=include_trends,
            include_aliexpress=include_aliexpress,
        )

        return results

    except Exception as e:
        # SECURITY: Log traceback server-side, don't expose to client
        logger.error(f"Product discovery failed for niche '{niche}': {e}", exc_info=True)

        # Return demo products for development when APIs fail
        if os.getenv("DEBUG", "").lower() in ("true", "1", "yes"):
            logger.info(f"[DEMO] Returning demo products for {niche} due to API failure")
            demo_products = _get_demo_products_fallback(niche, max_results)
            return {
                "niche": niche,
                "total_found": len(demo_products),
                "high_priority": len([p for p in demo_products if p.get("priority") == "high"]),
                "medium_priority": len([p for p in demo_products if p.get("priority") == "medium"]),
                "low_priority": len([p for p in demo_products if p.get("priority") == "low"]),
                "products": demo_products,
                "search_time": "0.1s",
                "demo_mode": True,
                "note": "Demo data - real APIs not connected"
            }

        return {
            "error": "Product discovery failed. Please try again.",
            "niche": niche,
            "total_found": 0,
        }


def _get_demo_products_fallback(niche: str, count: int = 10) -> List[Dict]:
    """Return demo products for development when APIs fail."""
    import random
    from datetime import datetime

    DEMO_DATA = {
        "smart_home": [
            {"name": "Smart LED Strip Lights RGB WiFi", "cost": 8.50},
            {"name": "WiFi Smart Plug with Energy Monitor", "cost": 6.99},
            {"name": "Smart Motion Sensor PIR Detector", "cost": 5.50},
            {"name": "WiFi Smart Bulb RGBW Dimmable", "cost": 4.99},
            {"name": "Smart Door Lock Fingerprint", "cost": 45.00},
        ],
        "kitchen": [
            {"name": "Electric Milk Frother Handheld", "cost": 5.99},
            {"name": "Silicone Kitchen Utensil Set", "cost": 12.50},
            {"name": "Vegetable Chopper Dicer Slicer", "cost": 8.99},
            {"name": "Digital Kitchen Scale 5kg", "cost": 7.50},
            {"name": "Vacuum Food Storage Containers", "cost": 15.00},
        ],
        "fitness": [
            {"name": "Resistance Bands Set 5 Levels", "cost": 6.50},
            {"name": "Foam Roller Muscle Massage", "cost": 9.99},
            {"name": "Jump Rope Speed Skipping", "cost": 4.50},
            {"name": "Yoga Mat Non-Slip 6mm", "cost": 11.00},
            {"name": "Adjustable Dumbbells Set", "cost": 35.00},
        ],
    }

    products = []
    base_data = DEMO_DATA.get(niche.replace(" ", "_").lower(), DEMO_DATA["smart_home"])

    for i, item in enumerate(base_data[:count]):
        cost = item["cost"]
        price = round(cost * 2.5, 2)
        score = random.uniform(6.0, 9.0)
        priority = "high" if score >= 8 else "medium" if score >= 6.5 else "low"

        products.append({
            "id": f"demo_{i}",
            "name": item["name"],
            "niche": niche,
            "cost_price": cost,
            "suggested_price": price,
            "profit_margin": round((price - cost) / price * 100, 1),
            "score": round(score, 1),
            "priority": priority,
            "trend_score": random.randint(50, 85),
            "sentiment_score": random.randint(60, 90),
            "sources": ["demo"],
            "is_demo": True,
            "discovered_at": datetime.now().isoformat(),
        })

    return products


@app.post("/api/validate-product")
async def validate_product_api(
    product_name: str,
    settings: Settings = Depends(get_settings)
):
    """
    Validate a specific product idea.

    Example request body:
        {
            "product_name": "wireless charging pad"
        }

    Returns validation report with Reddit mentions, trends data, and sourcing.
    """
    try:
        from ospra_os.product_research.discovery import ProductDiscoveryEngine

        engine = ProductDiscoveryEngine(
            reddit_client_id=settings.REDDIT_CLIENT_ID,
            reddit_secret=settings.REDDIT_SECRET,
            aliexpress_api_key=settings.ALIEXPRESS_API_KEY,
            aliexpress_app_secret=settings.ALIEXPRESS_APP_SECRET,
        )

        validation = await engine.validate_product(product_name)
        return validation

    except Exception as e:
        # SECURITY: Log traceback server-side, don't expose to client
        logger.error(f"Product validation failed for '{product_name}': {e}", exc_info=True)
        return {
            "error": "Product validation failed. Please try again.",
            "product_name": product_name,
        }


# ---------------------------------------------------------------
# Debug Endpoints REMOVED for Security
# These endpoints exposed sensitive API configurations and internal
# system data without authentication. They have been removed.
# If debugging is needed, use admin tools with proper authentication.
# Removed endpoints:
# - /api/debug/reddit
# - /api/debug/trends-test
# - /api/debug/reddit-connector-logs
# - /api/debug/reddit-json
# - /api/debug/reddit-raw
# ---------------------------------------------------------------


class DiscoverRequest(BaseModel):
    min_score: float = 0.0  # Changed default from 7.0 to 0.0
    max_per_niche: int = 3
    top_overall: int = 15

@app.post("/api/discover-multi")
async def discover_multi_niche(
    request: DiscoverRequest,
    settings: Settings = Depends(get_settings)
):
    """
    [HOT] Discover trending products using Google Trends (NO REDDIT REQUIRED).

    **WORKS ON RENDER** - uses Google Trends instead of Reddit!

    This endpoint searches 10 profitable niches:
    - Smart Lighting
    - Home Security
    - Cleaning Gadgets
    - Kitchen Tech
    - Fitness Gadgets
    - Phone Accessories
    - Car Accessories
    - Pet Products
    - Gaming Accessories
    - Outdoor Gear

    **Data Source:** Google Trends (shows REAL buying intent)

    **Why this is better than Reddit:**
    - [SUCCESS] Works on Render (no IP blocking)
    - [SUCCESS] Shows real search behavior (not just discussions)
    - [SUCCESS] Millions of data points
    - [SUCCESS] No rate limits
    - [SUCCESS] Free forever

    Example request body:
    {
        "min_score": 7.0,       // 0-10 scale (converted to 0-100 for Trends)
        "max_per_niche": 5,
        "top_overall": 20
    }

    Returns:
    {
        "success": true,
        "total_products": 50,
        "niches_discovered": 10,
        "top_overall": [...],  // Top 20 products across all niches
        "by_niche": {          // Products organized by niche
            "smart_lighting": [...],
            "home_security": [...],
            ...
        },
        "stats": {
            "niches_searched": 10,
            "high_priority": 15,
            "medium_priority": 20,
            "low_priority": 15
        },
        "source": "Google Trends (Reddit-free)",
        "data_quality": "High - based on real search behavior"
    }
    """
    try:
        from ospra_os.product_research.multi_source_discovery import MultiSourceDiscovery

        # Initialize Google Trends-based discovery (NO REDDIT!)
        discovery = MultiSourceDiscovery()

        # Run discovery using Google Trends
        # Note: min_score is now 0-100 (Google Trends scale) instead of 0-10
        trends_min_score = request.min_score * 10  # Convert 0-10 to 0-100
        niche_products = await discovery.discover_all_niches(
            min_score=trends_min_score,
            max_per_niche=request.max_per_niche
        )

        # Get top products overall
        top_products = discovery.get_top_products_overall(
            niche_products=niche_products,
            limit=request.top_overall
        )

        # Get statistics
        stats = discovery.get_stats(niche_products)

        return {
            "success": True,
            "total_products": stats["total_products"],
            "niches_discovered": stats["niches_with_products"],
            "top_overall": top_products,
            "by_niche": niche_products,
            "stats": {
                "niches_searched": stats["niches_searched"],
                "min_score": request.min_score,
                "products_per_niche": request.max_per_niche,
                "high_priority": stats["high_priority"],
                "medium_priority": stats["medium_priority"],
                "low_priority": stats["low_priority"],
            },
            "source": "Google Trends (Reddit-free)",
            "data_quality": "High - based on real search behavior"
        }

    except Exception as e:
        # SECURITY: Log traceback server-side, don't expose to client
        logger.error(f"Multi-niche discovery failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": "Multi-niche discovery failed. Please try again.",
            "total_products": 0,
            "niches_discovered": 0,
        }


# ---------------------------------------------------------------
# Analytics API Endpoints (Legacy) - REMOVED
# Now handled by secured routers/analytics.py
# Removed endpoints:
# - /analytics/daily
# - /analytics/weekly
# - /analytics/costs
# - /analytics/labels
# - /analytics/cache-stats
# ---------------------------------------------------------------

# ---------------------------------------------------------------
# Debug Endpoints - REMOVED for Security
# These exposed sensitive scheduler data and email inbox contents
# without authentication. They have been removed.
# Removed endpoints:
# - /debug/routes
# - /debug/scheduler
# - /debug/check-inbox
# ---------------------------------------------------------------


# ---------------------------------------------------------------
# AI Automation Endpoints (Shopify Deploy, Content, Pricing)
# ---------------------------------------------------------------

@app.post("/api/deploy-to-shopify")
async def deploy_to_shopify(
    product_name: str,
    niche: str,
    score: float,
    trend_score: float = 50,
    aliexpress_cost: Optional[float] = None,
    product_images: Optional[List[str]] = None,
    settings: Settings = Depends(get_settings)
):
    """
    [START] ONE-CLICK SHOPIFY DEPLOYMENT

    Complete automated pipeline:
    1. Generate AI-powered product content
    2. Optimize pricing with competitor analysis
    3. Deploy to Shopify store

    Args:
        product_name: Product name
        niche: Product category
        score: Discovery score (0-10)
        trend_score: Google Trends score (0-100)
        aliexpress_cost: Cost from supplier (optional - will be estimated)
        product_images: List of image URLs (optional)

    Returns:
        {
            "success": True,
            "shopify_product_id": "8234567890",
            "shopify_admin_url": "https://admin.shopify.com/...",
            "price": 29.99,
            "profit_margin": 65.5
        }
    """
    try:
        from ospra_os.integrations.shopify_auto_deploy import ShopifyAutoDeployer

        deployer = ShopifyAutoDeployer()

        result = await deployer.deploy_product(
            product_name=product_name,
            niche=niche,
            score=score,
            trend_score=trend_score,
            aliexpress_cost=aliexpress_cost,
            product_images=product_images or []
        )

        return result

    except Exception as e:
        # SECURITY: Log traceback server-side, don't expose to client
        logger.error(f"Shopify deployment failed for '{product_name}': {e}", exc_info=True)
        return {
            "success": False,
            "error": "Shopify deployment failed. Please check your store connection."
        }


@app.post("/api/generate-content")
async def generate_product_content(
    product_name: str,
    niche: str,
    trend_score: float = 50,
    settings: Settings = Depends(get_settings)
):
    """
    [NOTE] AI PRODUCT CONTENT GENERATOR

    Generate SEO-optimized product content using AI:
    - Product title (SEO-optimized)
    - Product description (HTML)
    - Bullet points (benefit-focused)
    - Meta description
    - Tags
    - Marketing headline

    Args:
        product_name: Product name
        niche: Product category
        trend_score: Google Trends score (0-100)

    Returns:
        {
            "title": "LED Strip Lights - Transform Any Room",
            "description": "<p>Discover...</p>",
            "bullet_points": ["Feature 1", ...],
            "meta_description": "SEO description",
            "tags": ["led", "smart-home", ...],
            "headline": "Transform Your Home Today"
        }
    """
    try:
        from ospra_os.product_research.ai_content import AIContentGenerator

        generator = AIContentGenerator()

        content = await generator.generate_product_content(
            product_name=product_name,
            niche=niche,
            trend_score=trend_score
        )

        return {
            "success": True,
            "content": content
        }

    except Exception as e:
        # SECURITY: Log traceback server-side, don't expose to client
        logger.error(f"Content generation failed for '{product_name}': {e}", exc_info=True)
        return {
            "success": False,
            "error": "Content generation failed. Please try again."
        }


@app.post("/api/scrape-aliexpress-product")
async def scrape_aliexpress_product(url: str):
    """
    Scrape product details from AliExpress URL.

    DEPRECATED (2025-12-07): AliExpress scraper removed.
    Use official AliExpress Affiliate API instead via /api/aliexpress/* endpoints.

    Args:
        url: AliExpress product URL

    Returns:
        {
            "success": False,
            "error": "Scraper removed - use official AliExpress API",
            "message": "Use /api/aliexpress/search or /api/aliexpress/product endpoints"
        }
    """
    # AliExpress scraper removed 2025-12-07
    # Use official AliExpress Affiliate API instead
    return {
        "success": False,
        "error": "AliExpress scraper removed (2025-12-07)",
        "message": "Use official AliExpress API endpoints instead",
        "alternatives": [
            "POST /api/aliexpress/search - Search products",
            "GET /api/aliexpress/product/{product_id} - Get product details",
            "See docs/DATA_SOURCES.md for AliExpress API documentation"
        ]
    }


@app.post("/api/optimize-price")
async def optimize_product_price(
    product_name: str,
    aliexpress_cost: float,
    niche: str,
    trend_score: float = 50,
    settings: Settings = Depends(get_settings)
):
    """
    [PRICE] AI PRICE OPTIMIZER

    Optimize pricing with AI-powered competitor analysis:
    - Suggested price (with .99 endings)
    - Compare-at price (for perceived value)
    - Profit margin calculation
    - Profit per sale
    - Pricing strategy (premium/competitive/value)

    Args:
        product_name: Product name
        aliexpress_cost: Cost from supplier
        niche: Product category
        trend_score: Google Trends score (0-100)

    Returns:
        {
            "suggested_price": 29.99,
            "compare_at_price": 49.99,
            "profit_margin": 65.5,
            "profit_per_sale": 19.49,
            "pricing_strategy": "competitive",
            "reasoning": "AI explanation..."
        }
    """
    try:
        from ospra_os.product_research.price_optimizer import PriceOptimizer

        optimizer = PriceOptimizer()

        pricing = await optimizer.analyze_pricing(
            product_name=product_name,
            aliexpress_cost=aliexpress_cost,
            niche=niche,
            trend_score=trend_score
        )

        return {
            "success": True,
            "pricing": pricing
        }

    except Exception as e:
        # SECURITY: Log traceback server-side, don't expose to client
        logger.error(f"Price optimization failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": "Price optimization failed. Please try again."
        }


# ---------------------------------------------------------------
# Product Intelligence API Endpoints
# REMOVED: Now handled by secured routers/intelligence.py
# These endpoints are available at:
# - POST /api/intelligence/saturation
# - POST /api/intelligence/discover
# - POST /api/intelligence/discover-enriched
# - GET /api/intelligence/stats
# ---------------------------------------------------------------

# NOTE: The following intelligence endpoints were removed (lines 2149-2664):
# - @app.post("/api/intelligence/discover")
# - @app.post("/api/intelligence/discover-enriched")
# - @app.get("/api/products/test-discovery")
# These are now handled by secured routers/intelligence.py
# The following ~500 lines of orphaned code were cleaned up.

# [PLACEHOLDER - Intelligence endpoints moved to secured routers]
# See routers/intelligence.py for:
# - POST /api/intelligence/saturation
# - POST /api/intelligence/discover
# - POST /api/intelligence/discover-enriched
# - GET /api/intelligence/stats
# ~400 lines of orphaned intelligence endpoint code removed from here.

# ---------------------------------------------------------------
# Velocity Detection API Endpoints
# REMOVED: Now handled by secured routers/velocity.py
# These endpoints are available at:
# - GET /api/velocity/stats
# - GET /api/velocity/tier-products
# - GET /api/velocity/phase/{phase}
# ---------------------------------------------------------------

# ---------------------------------------------------------------
# Subscription Tier Management API
# REMOVED: These endpoints had critical security vulnerabilities
# accepting user_id as query parameters (user impersonation attack).
# Use secured endpoints with JWT authentication instead.
# Removed endpoints:
# - GET /api/user/tier (VULNERABLE: user_id query param)
# - POST /api/user/upgrade-tier (VULNERABLE: user_id query param)
# - GET /api/tiers/comparison
# - POST /api/user/check-limit (VULNERABLE: user_id query param)
# ---------------------------------------------------------------


# ---------------------------------------------------------------
# Claude AI Chat API for Dashboard Insights
# ---------------------------------------------------------------
class ChatRequest(BaseModel):
    message: str
    dashboard_context: Optional[Dict] = None
    context: Optional[Dict] = None  # Backward compatibility with frontend
    conversation_history: Optional[List[Dict]] = None

    def get_context(self) -> Optional[Dict]:
        """Get context from either dashboard_context or context field"""
        return self.dashboard_context or self.context


@app.post("/api/claude/chat")
async def claude_chat(request: ChatRequest):
    """
    Chat with Claude AI with full dashboard context and conversation history

    Features:
    - Comprehensive dashboard data (portfolio, products, emails, tier)
    - Conversation history for context-aware responses
    - Real-time metric analysis
    - Actionable business insights
    """
    import os
    from anthropic import Anthropic

    try:
        # Check for API key
        api_key = os.getenv('ANTHROPIC_API_KEY') or os.getenv('CLAUDE_API_KEY')
        if not api_key:
            demo_message = "I'm running in demo mode. To enable full AI capabilities, add ANTHROPIC_API_KEY to your environment variables.\n\nI can still help with basic questions about your dashboard!"
            return {
                'success': True,
                'response': demo_message,  # Frontend expects this field
                'message': demo_message,   # Keep for backward compatibility
                'demo_mode': True
            }

        claude = Anthropic(api_key=api_key)

        # Build comprehensive context summary
        context_summary = ""
        context_data = request.get_context()  # Use helper method for compatibility
        if context_data and context_data.get('data'):
            data = context_data['data']
            current_page = context_data.get('current_page', '/')

            context_summary += f"**Current Page:** {current_page}\n\n"

            # Portfolio summary
            if 'portfolio' in data:
                portfolio = data['portfolio']
                context_summary += f"""**Portfolio Status:**
- Total Revenue: ${portfolio.get('totalRevenue', 0):,.2f}
- Active Stores: {portfolio.get('activeStores', 0)}
- Total Products: {portfolio.get('totalProducts', 0)}
- Avg Conversion Rate: {portfolio.get('avgConversion', 0):.2f}%
- Growth Rate: {portfolio.get('growthRate', 0):.1f}%

"""

            # Store rankings
            if 'rankings' in data:
                rankings = data['rankings'].get('stores', [])
                if rankings:
                    context_summary += f"**Top Performing Stores:**\n"
                    for i, store in enumerate(rankings[:3], 1):
                        context_summary += f"{i}. {store.get('name', 'Unknown')}: ${store.get('revenue', 0):,.2f}\n"
                    context_summary += "\n"

            # Products summary
            if 'products' in data and data['products'].get('count', 0) > 0:
                products_info = data['products']
                context_summary += f"""**Product Discovery:**
- Found: {products_info['count']} products
- Data Source: {products_info.get('data_source', 'Unknown')}
- Top Products: {', '.join([p.get('name', 'Unknown')[:30] for p in products_info.get('samples', [])[:3]])}

"""

            # Email automation summary
            if 'email_stats' in data:
                email_stats = data['email_stats']
                context_summary += f"""**Email Management:**
- Total Emails: {email_stats.get('total_emails', 0)}
- Unread: {email_stats.get('unread_emails', 0)}
- Important/Starred: {email_stats.get('important_emails', 0)}
- Connected Accounts: {len(email_stats.get('accounts', []))}

"""

            # Recent emails list
            if 'emails' in data and isinstance(data['emails'], list):
                emails_list = data['emails'][:5]  # Show first 5 emails
                if emails_list:
                    context_summary += "**Recent Emails:**\n"
                    for email in emails_list:
                        from_addr = email.get('from_address', 'Unknown')
                        subject = email.get('subject', '(No subject)')[:50]
                        read_status = "[OK]" if email.get('is_read') else ""
                        context_summary += f"{read_status} From: {from_addr} - {subject}\n"
                    context_summary += "\n"

            # Subscription tier
            if 'tier' in data:
                tier = data['tier']
                tier_name = tier.get('tier', 'free').upper()
                context_summary += f"**Subscription:** {tier_name} Tier\n\n"

        # Build conversation context
        conversation_context = ""
        if request.conversation_history and len(request.conversation_history) > 0:
            conversation_context = "\n**Recent Conversation:**\n"
            for msg in request.conversation_history[-5:]:  # Last 5 messages
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                # Truncate long messages
                content_preview = content[:100] + "..." if len(content) > 100 else content
                conversation_context += f"- {role.upper()}: {content_preview}\n"
            conversation_context += "\n"

        # Build system prompt with all context
        email_capabilities = ""
        if context_data and context_data.get('capabilities', {}).get('can_read_emails'):
            email_capabilities = """

**Email Capabilities:**
You can help users with email tasks:
- Read and summarize emails
- Draft replies to customer emails
- Mark emails as read/unread
- Identify urgent emails that need attention
- Suggest responses based on email content
- Help with email organization

When users ask about specific emails, you can see the recent emails listed above."""

        system_prompt = f"""You are an AI assistant for Ospra Intelligence, an e-commerce automation platform.

Your expertise:
- E-commerce strategy and optimization
- Product research and selection
- Marketing and conversion optimization
- Business metrics analysis
- Shopify store management
- Customer support via email automation{email_capabilities}

{context_summary}

{conversation_context}

Provide helpful, actionable advice based on the actual dashboard data shown above. Be specific and reference real numbers when relevant. Use bullet points and emojis for readability."""

        # Call Claude API
        response = claude.messages.create(
            model="claude-sonnet-4-5-20250929",  # Latest Sonnet 4
            max_tokens=800,
            system=system_prompt,
            messages=[{
                "role": "user",
                "content": request.message
            }]
        )

        assistant_response = response.content[0].text
        return {
            'success': True,
            'response': assistant_response,  # Frontend expects this field
            'message': assistant_response,   # Keep for backward compatibility
            'model': 'claude-sonnet-4-5-20250929',
            'demo_mode': False
        }

    except Exception as e:
        import traceback
        return {
            'success': False,
            'error': str(e),
            'message': f"Error communicating with Claude AI: {str(e)}"
        }


# ---------------------------------------------------------------
# Marketing Angle Generator API
# ---------------------------------------------------------------
@app.post("/api/marketing/generate-angle")
async def generate_marketing_angle(
    product_name: str,
    product_description: str,
    niche: str = 'smart_home',
    user_brand_voice: str = 'professional',
    user_target_audience: str = 'general',
    avoid_angles: Optional[List[str]] = None
):
    """
    Generate unique marketing angle for a product

    Creates AI-powered marketing positioning to differentiate users
    selling the same products. Each user gets a unique angle.

    Query Parameters:
        product_name: Name of the product
        product_description: Product description
        niche: Product niche (smart_home, fitness, kitchen, etc.)
        user_brand_voice: Brand voice (professional, casual, luxury, etc.)
        user_target_audience: Target demographic
        avoid_angles: List of angles to avoid (already used)

    Returns:
        Marketing angle with title, description, target audience,
        pain points, benefits, CTA, ad copy, and hashtags
    """
    try:
        from ospra_os.intelligence.marketing_angle_generator import MarketingAngleGenerator

        # Initialize generator
        generator = MarketingAngleGenerator(ai_provider='claude')

        # Generate unique angle
        angle = await generator.generate_unique_angle(
            product_name=product_name,
            product_description=product_description,
            user_brand_voice=user_brand_voice,
            user_target_audience=user_target_audience,
            niche=niche,
            avoid_angles=avoid_angles or []
        )

        return {
            "success": True,
            "angle": angle
        }

    except Exception as e:
        # SECURITY: Log traceback server-side, don't expose to client
        logger.error(f"Marketing angle generation failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": "Marketing angle generation failed. Please try again."
        }


@app.post("/api/marketing/generate-multiple-angles")
async def generate_multiple_angles(
    product_name: str,
    product_description: str,
    niche: str = 'smart_home',
    num_angles: int = 3,
    user_brand_voice: str = 'professional',
    user_target_audience: str = 'general'
):
    """
    Generate multiple marketing angles for A/B testing

    Creates several different marketing angles for the same product
    to test which resonates best with the audience.

    Query Parameters:
        product_name: Name of the product
        product_description: Product description
        niche: Product niche
        num_angles: Number of angles to generate (default: 3, max: 5)
        user_brand_voice: Brand voice
        user_target_audience: Target demographic

    Returns:
        List of marketing angles for A/B testing
    """
    try:
        from ospra_os.intelligence.marketing_angle_generator import MarketingAngleGenerator

        # Limit num_angles to reasonable range
        num_angles = min(max(num_angles, 1), 5)

        # Initialize generator
        generator = MarketingAngleGenerator(ai_provider='claude')

        # Generate multiple angles
        angles = await generator.generate_multiple_angles(
            product_name=product_name,
            product_description=product_description,
            niche=niche,
            num_angles=num_angles,
            user_brand_voice=user_brand_voice,
            user_target_audience=user_target_audience
        )

        return {
            "success": True,
            "count": len(angles),
            "angles": angles,
            "recommendation": "Test each angle with a small audience to see which performs best"
        }

    except Exception as e:
        # SECURITY: Log traceback server-side, don't expose to client
        logger.error(f"Multiple angles generation failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": "Marketing angle generation failed. Please try again."
        }


@app.get("/api/marketing/available-angles")
async def get_available_angles(niche: str = 'smart_home'):
    """
    Get list of available marketing angles for a niche

    Returns all possible marketing angles that can be used
    for products in the specified niche.

    Query Parameters:
        niche: Product niche

    Returns:
        List of available angles and their descriptions
    """
    try:
        from ospra_os.intelligence.marketing_angle_generator import MarketingAngleGenerator

        generator = MarketingAngleGenerator(ai_provider='claude')

        # Get available angles
        angles = generator.get_available_angles(niche)

        # Get descriptions for each angle
        angle_details = []
        for angle in angles:
            details = generator.get_angle_description(angle)
            angle_details.append(details)

        return {
            "success": True,
            "niche": niche,
            "count": len(angles),
            "angles": angle_details
        }

    except Exception as e:
        # SECURITY: Log traceback server-side, don't expose to client
        logger.error(f"Failed to get available angles: {e}", exc_info=True)
        return {
            "success": False,
            "error": "Failed to retrieve available angles. Please try again."
        }


# =============================================================================
# SMART RECOMMENDATIONS - The Complete Anti-AutoDS System
# =============================================================================

@app.post("/api/recommendations/smart")
async def get_smart_recommendations(
    niches: Optional[List[str]] = None,
    max_products: int = 10,
    include_angles: bool = True,
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user)
):
    """
    Get personalized, anti-AutoDS product recommendations

    SECURITY: Requires JWT authentication. User ID extracted from token.

    This endpoint brings together ALL differentiation features:
    - Tier-based access (early access to trending products)
    - Saturation protection (no oversaturated products)
    - Velocity-based timing (lifecycle phase filtering)
    - Unique marketing angles (prevent direct competition)

    Query Parameters:
        niches: List of niches to search (uses user preferences if None)
        max_products: Maximum number of products to return (default: 10)
        include_angles: Whether to generate unique marketing angles (default: True)

    Returns:
        Personalized product recommendations with metadata:
        - User tier and access level
        - Filtered products based on all systems
        - Unique marketing angles per product
        - Analytics on filtering applied
    """
    try:
        from ospra_os.intelligence.smart_recommendations import SmartRecommendationEngine

        user_id = current_user.id
        logger.info(f"Getting smart recommendations for user {user_id}")

        # Initialize recommendation engine
        engine = SmartRecommendationEngine(database_url=settings.database_url)

        # Get personalized recommendations
        recommendations = await engine.get_personalized_recommendations(
            user_id=user_id,
            niches=niches,
            max_products=max_products,
            include_angles=include_angles
        )

        # Close engine
        await engine.close()

        logger.info(f"[SUCCESS] Smart recommendations complete: {recommendations.get('count', 0)} products")

        return recommendations

    except Exception as e:
        # SECURITY: Log traceback server-side, don't expose to client
        logger.error(f"Smart recommendations failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": "Smart recommendations failed. Please try again."
        }


@app.get("/api/recommendations/analytics")
async def get_recommendation_analytics(
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user)
):
    """
    Get analytics on user's recommendation performance

    SECURITY: Requires JWT authentication. User ID extracted from token.

    This endpoint provides insights into:
    - Total recommendations received
    - Products deployed vs recommended
    - Success rate of deployed products
    - Top performing niches
    - Most effective marketing angles

    Returns:
        Analytics dictionary with:
        - Overall statistics (total, deployed, successful, success_rate)
        - Product diversity (unique niches, unique angles)
        - Recent recommendations (latest 10)
        - Top performing niches (top 5 by success rate)
        - Most effective angles (top 5 by success rate)
    """
    try:
        from ospra_os.intelligence.smart_recommendations import SmartRecommendationEngine

        user_id = current_user.id
        logger.info(f"Getting recommendation analytics for user {user_id}")

        # Initialize recommendation engine
        engine = SmartRecommendationEngine(database_url=settings.database_url)

        # Get analytics
        analytics = await engine.get_recommendation_analytics(user_id)

        # Close engine
        await engine.close()

        logger.info(f"[SUCCESS] Analytics retrieved: {analytics.get('total_recommendations', 0)} total recommendations")

        return analytics

    except Exception as e:
        # SECURITY: Log traceback server-side, don't expose to client
        logger.error(f"Failed to get analytics: {e}", exc_info=True)
        return {
            "success": False,
            "error": "Failed to retrieve analytics. Please try again."
        }


@app.post("/api/shopify/deploy")
async def deploy_to_shopify(
    request: ShopifyDeployRequest,
    settings: Settings = Depends(get_settings)
):
    """
    Deploy a product to Shopify

    Request:
    {
        "product_id": "123",  # Optional - from database
        "product_data": {...}  # Or provide product data directly
    }

    Returns:
        {
            "success": true,
            "shopify_product_id": 12345,
            "shopify_url": "https://store.myshopify.com/products/...",
            "admin_url": "https://store.myshopify.com/admin/products/...",
            "title": "Product Title",
            "price": 29.99,
            "images_count": 3
        }
    """
    try:
        from ospra_os.integrations.shopify.deployment import ProductDeploymentService

        deployment_service = ProductDeploymentService()

        # Get product data
        if request.product_id:
            # TODO: Load from database
            product_data = {}  # Load from DB
        else:
            product_data = request.product_data

        if not product_data:
            return {
                'success': False,
                'error': 'No product data provided'
            }

        # Deploy
        result = await deployment_service.deploy_product(product_data)

        return result

    except Exception as e:
        logger.error(f"Deploy endpoint error: {e}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': str(e)
        }


@app.post("/api/shopify/bulk-deploy")
async def bulk_deploy_to_shopify(
    request: ShopifyBulkDeployRequest,
    settings: Settings = Depends(get_settings)
):
    """
    Deploy multiple products to Shopify

    Request:
    {
        "product_ids": ["1", "2", "3"],  # List of product IDs
        "products": [...]  # Or provide products array directly
    }

    Returns:
        {
            "success": true,
            "total": 10,
            "successful": 8,
            "failed": 2,
            "results": [...]
        }
    """
    try:
        from ospra_os.integrations.shopify.deployment import ProductDeploymentService

        deployment_service = ProductDeploymentService()

        # Get products
        if request.product_ids:
            # TODO: Load from database
            products = []  # Load from DB
        else:
            products = request.products or []

        if not products:
            return {
                'success': False,
                'error': 'No products provided'
            }

        # Deploy
        results = await deployment_service.bulk_deploy(products)

        successful = sum(1 for r in results if r.get('success'))

        return {
            'success': True,
            'total': len(results),
            'successful': successful,
            'failed': len(results) - successful,
            'results': results
        }

    except Exception as e:
        logger.error(f"Bulk deploy error: {e}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': str(e)
        }


@app.get("/api/shopify/products")
async def list_shopify_products(
    limit: int = 50,
    settings: Settings = Depends(get_settings)
):
    """
    List products in Shopify store

    Query parameters:
        limit: Maximum number of products to return (default: 50)

    Returns:
        {
            "success": true,
            "count": 25,
            "products": [...]
        }
    """
    try:
        from ospra_os.integrations.shopify.client import ShopifyClient

        shopify = ShopifyClient()
        products = await shopify.list_products(limit=limit)

        return {
            'success': True,
            'count': len(products),
            'products': products
        }

    except Exception as e:
        logger.error(f"List products error: {e}")
        return {
            'success': False,
            'error': str(e)
        }


@app.delete("/api/shopify/products/{product_id}")
async def delete_shopify_product(
    product_id: int,
    settings: Settings = Depends(get_settings)
):
    """
    Delete a product from Shopify

    Path parameters:
        product_id: Shopify product ID

    Returns:
        {
            "success": true,
            "message": "Product deleted"
        }
    """
    try:
        from ospra_os.integrations.shopify.client import ShopifyClient

        shopify = ShopifyClient()
        success = await shopify.delete_product(product_id)

        if success:
            return {
                'success': True,
                'message': 'Product deleted'
            }
        else:
            return {
                'success': False,
                'error': 'Delete failed'
            }

    except Exception as e:
        logger.error(f"Delete product error: {e}")
        return {
            'success': False,
            'error': str(e)
        }


@app.post("/api/aliexpress/search")
async def search_aliexpress(
    request: AliExpressSearchRequest,
    settings: Settings = Depends(get_settings)
):
    """
    Search AliExpress for products

    Request:
    {
        "keywords": "smart led strip",
        "min_price": 5,
        "max_price": 30
    }

    Returns:
        {
            "success": true,
            "count": 15,
            "products": [...]
        }
    """
    try:
        from ospra_os.integrations.aliexpress.client import AliExpressClient

        client = AliExpressClient()

        products = await client.search_products(
            keywords=request.keywords,
            min_price=request.min_price,
            max_price=request.max_price
        )

        return {
            'success': True,
            'count': len(products),
            'products': products
        }

    except Exception as e:
        logger.error(f"AliExpress search error: {e}")
        return {
            'success': False,
            'error': str(e)
        }


@app.post("/api/aliexpress/affiliate-links")
async def generate_affiliate_links(
    request: AliExpressAffiliateLinkRequest,
    settings: Settings = Depends(get_settings)
):
    """
    Generate affiliate tracking links

    Request:
    {
        "product_ids": ["123456", "789012"]
    }

    Returns:
        {
            "success": true,
            "links": {
                "123456": "https://s.click.aliexpress.com/...",
                "789012": "https://s.click.aliexpress.com/..."
            }
        }
    """
    try:
        from ospra_os.integrations.aliexpress.client import AliExpressClient

        client = AliExpressClient()

        links = await client.get_affiliate_links(
            request.product_ids
        )

        return {
            'success': True,
            'links': links
        }

    except Exception as e:
        logger.error(f"Affiliate link error: {e}")
        return {
            'success': False,
            'error': str(e)
        }


@app.post("/api/aliexpress/fulfill-order")
async def fulfill_order(
    request: AliExpressFulfillRequest,
    settings: Settings = Depends(get_settings)
):
    """
    Fulfill a Shopify order via AliExpress

    Request:
    {
        "shopify_order": {...},
        "aliexpress_product_id": "123456"
    }

    Returns:
        {
            "success": true,
            "shopify_order_id": "789",
            "aliexpress_order_id": "123456789",
            "total_cost": 12.50,
            "tracking_pending": true
        }
    """
    try:
        from ospra_os.integrations.aliexpress.fulfillment import OrderFulfillmentService

        fulfillment = OrderFulfillmentService()

        result = await fulfillment.fulfill_order(
            request.shopify_order,
            request.aliexpress_product_id
        )

        return result

    except Exception as e:
        logger.error(f"Order fulfillment error: {e}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': str(e)
        }


@app.post("/api/aliexpress/sync-inventory")
async def sync_inventory(
    request: AliExpressSyncRequest,
    settings: Settings = Depends(get_settings)
):
    """
    Sync inventory from AliExpress

    Request:
    {
        "products": [
            {
                "aliexpress_id": "123456",
                "shopify_id": "789012"
            }
        ]
    }

    Returns:
        {
            "success": true,
            "results": [...]
        }
    """
    try:
        from ospra_os.integrations.aliexpress.inventory import InventorySyncService

        sync_service = InventorySyncService()

        results = await sync_service.bulk_sync(
            request.products
        )

        return {
            'success': True,
            'results': results
        }

    except Exception as e:
        logger.error(f"Inventory sync error: {e}")
        return {
            'success': False,
            'error': str(e)
        }


@app.post("/api/aliexpress/monitor-prices")
async def monitor_prices(
    request: AliExpressMonitorPricesRequest,
    settings: Settings = Depends(get_settings)
):
    """
    Monitor price changes on AliExpress

    Request:
    {
        "products": [
            {
                "aliexpress_id": "123456",
                "name": "LED Strip",
                "last_known_price": 15.99
            }
        ],
        "threshold_percent": 10.0
    }

    Returns:
        {
            "success": true,
            "alerts": [...]
        }
    """
    try:
        from ospra_os.integrations.aliexpress.inventory import InventorySyncService

        sync_service = InventorySyncService()

        alerts = await sync_service.monitor_price_changes(
            request.products,
            request.threshold_percent
        )

        return {
            'success': True,
            'alerts': alerts
        }

    except Exception as e:
        logger.error(f"Price monitoring error: {e}")
        return {
            'success': False,
            'error': str(e)
        }


# 
# META (FACEBOOK/INSTAGRAM) AD AUTOMATION
# 

@app.post("/api/meta/create-campaign")
async def create_meta_campaign(
    request: MetaCampaignRequest,
    settings: Settings = Depends(get_settings)
):
    """
    Create complete Meta ad campaign for a product

    Request:
    {
        "product": {
            "name": "Smart LED Strip",
            "price": 29.99,
            "image_url": "https://...",
            "shopify_url": "https://..."
        },
        "daily_budget": 15.0,
        "auto_activate": false
    }
    """
    try:
        from ospra_os.integrations.meta.campaign_builder import CampaignBuilder

        builder = CampaignBuilder()

        result = await builder.create_complete_campaign(
            product=request.product.model_dump(),
            daily_budget=request.daily_budget,
            auto_activate=request.auto_activate
        )

        return result

    except Exception as e:
        logger.error(f"Campaign creation error: {e}")
        return {
            'success': False,
            'error': str(e)
        }


@app.post("/api/meta/bulk-campaigns")
async def create_bulk_campaigns(
    request: MetaBulkCampaignCreateRequest,
    settings: Settings = Depends(get_settings)
):
    """
    Create campaigns for multiple products

    Request:
    {
        "products": [{...}, {...}],
        "daily_budget_per_product": 10.0
    }
    """
    try:
        from ospra_os.integrations.meta.campaign_builder import CampaignBuilder

        builder = CampaignBuilder()

        results = await builder.bulk_create_campaigns(
            products=request.products,
            daily_budget_per_product=request.daily_budget_per_product
        )

        successful = sum(1 for r in results if r.get('success'))

        return {
            'success': True,
            'total': len(results),
            'successful': successful,
            'failed': len(results) - successful,
            'results': results
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


@app.get("/api/meta/campaign/{campaign_id}/insights")
async def get_campaign_insights(
    campaign_id: str,
    date_preset: str = 'last_7d',
    settings: Settings = Depends(get_settings)
):
    """Get campaign performance metrics"""
    try:
        from ospra_os.integrations.meta.client import MetaAdsClient

        client = MetaAdsClient()

        insights = await client.get_campaign_insights(
            campaign_id,
            date_preset
        )

        return {
            'success': True,
            'insights': insights
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


@app.post("/api/meta/campaign/{campaign_id}/status")
async def update_campaign_status(
    campaign_id: str,
    request: CampaignStatusUpdate,
    settings: Settings = Depends(get_settings)
):
    """
    Update campaign status (activate/pause)

    Request:
    {
        "status": "ACTIVE" or "PAUSED"
    }
    """
    try:
        from ospra_os.integrations.meta.client import MetaAdsClient

        client = MetaAdsClient()

        success = await client.update_campaign_status(
            campaign_id,
            request.status
        )

        return {
            'success': success
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


@app.post("/api/meta/adset/{ad_set_id}/budget")
async def update_ad_set_budget(
    ad_set_id: str,
    request: AdSetBudgetUpdate,
    settings: Settings = Depends(get_settings)
):
    """
    Update ad set daily budget

    Request:
    {
        "daily_budget": 20.0
    }
    """
    try:
        from ospra_os.integrations.meta.client import MetaAdsClient

        client = MetaAdsClient()

        budget_cents = int((request.daily_budget or 10.0) * 100)

        success = await client.update_ad_set_budget(
            ad_set_id,
            budget_cents
        )

        return {
            'success': success
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


# 
# AD SCHEDULING & AUTOMATION
# 

@app.post("/api/schedule/create")
async def create_ad_schedule(
    request: ScheduleCreateRequest,
    settings: Settings = Depends(get_settings)
):
    """
    Schedule an ad campaign for future activation

    Request:
    {
        "product": {...},
        "scheduled_start": "2025-11-20T10:00:00Z",
        "scheduled_end": "2025-11-27T10:00:00Z",
        "daily_budget": 15.0,
        "platform": "meta"
    }
    """
    try:
        from ospra_os.services.schedule_manager import ScheduleManager
        from datetime import datetime

        manager = ScheduleManager(settings.database_url)

        # Parse dates
        scheduled_start = datetime.fromisoformat(
            request.scheduled_start.replace('Z', '+00:00')
        )

        scheduled_end = None
        if request.scheduled_end:
            scheduled_end = datetime.fromisoformat(
                request.scheduled_end.replace('Z', '+00:00')
            )

        result = await manager.create_schedule(
            product=request.product,
            scheduled_start=scheduled_start,
            daily_budget=request.daily_budget,
            scheduled_end=scheduled_end,
            total_budget=request.total_budget,
            platform=request.platform,
            target_audience=request.target_audience
        )

        return result

    except Exception as e:
        logger.error(f"Schedule creation error: {e}")
        return {
            'success': False,
            'error': str(e)
        }


@app.get("/api/schedule/list")
async def list_schedules(
    status: str = None,
    limit: int = 50,
    settings: Settings = Depends(get_settings)
):
    """
    List ad schedules

    Query params:
    - status: pending, active, completed, cancelled, failed
    - limit: max results (default 50)
    """
    try:
        from ospra_os.services.schedule_manager import ScheduleManager

        manager = ScheduleManager(settings.database_url)

        schedules = manager.list_schedules(status=status, limit=limit)

        return {
            'success': True,
            'count': len(schedules),
            'schedules': schedules
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


@app.get("/api/schedule/{schedule_id}")
async def get_schedule(
    schedule_id: str,
    settings: Settings = Depends(get_settings)
):
    """Get schedule details"""
    try:
        from ospra_os.services.schedule_manager import ScheduleManager

        manager = ScheduleManager(settings.database_url)

        schedule = manager.get_schedule(schedule_id)

        if not schedule:
            return {
                'success': False,
                'error': 'Schedule not found'
            }

        return {
            'success': True,
            'schedule': schedule
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


@app.delete("/api/schedule/{schedule_id}")
async def cancel_schedule(
    schedule_id: str,
    settings: Settings = Depends(get_settings)
):
    """Cancel a pending schedule"""
    try:
        from ospra_os.services.schedule_manager import ScheduleManager

        manager = ScheduleManager(settings.database_url)

        success = await manager.cancel_schedule(schedule_id)

        return {
            'success': success
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


@app.post("/api/schedule/process")
async def manually_process_schedules(
    settings: Settings = Depends(get_settings)
):
    """
    Manually trigger schedule processing
    (normally runs automatically every 5 min)
    """
    try:
        from ospra_os.jobs.schedule_processor import process_schedules

        await process_schedules()

        return {
            'success': True,
            'message': 'Schedule processing completed'
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


@app.get("/api/schedule/calendar/week")
async def get_week_calendar(
    settings: Settings = Depends(get_settings)
):
    """Get week view of scheduled ads"""
    try:
        from ospra_os.services.schedule_manager import ScheduleManager
        from ospra_os.services.calendar_view import CalendarView

        manager = ScheduleManager(settings.database_url)
        calendar = CalendarView(manager)

        week_view = calendar.get_week_view()

        return {
            'success': True,
            'calendar': week_view
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


@app.get("/api/schedule/calendar/month")
async def get_month_calendar(
    year: int = None,
    month: int = None,
    settings: Settings = Depends(get_settings)
):
    """Get month view of scheduled ads"""
    try:
        from ospra_os.services.schedule_manager import ScheduleManager
        from ospra_os.services.calendar_view import CalendarView

        manager = ScheduleManager(settings.database_url)
        calendar = CalendarView(manager)

        month_view = calendar.get_month_view(year, month)

        return {
            'success': True,
            'calendar': month_view
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


@app.get("/api/schedule/forecast")
async def get_budget_forecast(
    days: int = 30,
    settings: Settings = Depends(get_settings)
):
    """Get daily budget forecast"""
    try:
        from ospra_os.services.schedule_manager import ScheduleManager
        from ospra_os.services.calendar_view import CalendarView

        manager = ScheduleManager(settings.database_url)
        calendar = CalendarView(manager)

        forecast = calendar.get_daily_budget_forecast(days)

        return {
            'success': True,
            'forecast': forecast
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }
# 
# LIVE TRENDS DASHBOARD - REAL-TIME PRODUCT MOMENTUM
# 

@app.get("/api/trends/live")
async def get_live_trending_products(
    limit: int = 20,
    sort_by: str = 'velocity',
    settings: Settings = Depends(get_settings)
):
    """
    Get top trending products with real-time momentum indicators

    Stock market-style live trends with velocity scores, momentum indicators,
    and rank changes. Updates every 5 minutes via background jobs.

    Query params:
    - limit: Number of products to return (default: 20)
    - sort_by: Sort criterion ('velocity', 'rank', 'breakout')

    Returns: Top trending products with momentum data
    """
    try:
        from ospra_os.intelligence.momentum_tracker import get_momentum_tracker
        from ospra_os.database.product_history import ProductHistoryDB

        # Get live product data directly from database
        db = ProductHistoryDB()
        products_data = db.get_all_products(niche=None)  # Get all niches for trends
        products_data = products_data[:limit * 2]  # Get more for filtering

        # Calculate momentum for each product
        tracker = get_momentum_tracker()
        trending = await tracker.get_trending_products(
            products_data=products_data,
            limit=limit,
            sort_by=sort_by
        )

        return {
            'success': True,
            'count': len(trending),
            'products': trending,
            'last_updated': trending[0]['last_updated'] if trending else None
        }

    except Exception as e:
        logger.error(f"Live trends error: {e}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': str(e),
            'products': []
        }


@app.get("/api/trends/movers")
async def get_biggest_movers(
    direction: str = 'up',
    limit: int = 10,
    settings: Settings = Depends(get_settings)
):
    """
    Get products with biggest rank changes (movers & shakers)

    Query params:
    - direction: 'up' for gainers, 'down' for losers (default: 'up')
    - limit: Number to return (default: 10)

    Returns: Products with biggest rank movements
    """
    try:
        from ospra_os.intelligence.momentum_tracker import get_momentum_tracker
        from ospra_os.database.product_history import ProductHistoryDB

        # Get live products with momentum directly from database
        db = ProductHistoryDB()
        products_data = db.get_all_products(niche=None)
        products_data = products_data[:50]  # Get more for filtering
        tracker = get_momentum_tracker()

        trending = await tracker.get_trending_products(
            products_data=products_data,
            limit=50
        )

        # Get biggest movers
        movers = tracker.get_biggest_movers(
            products=trending,
            limit=limit,
            direction=direction
        )

        return {
            'success': True,
            'direction': direction,
            'count': len(movers),
            'movers': movers
        }

    except Exception as e:
        logger.error(f"Movers error: {e}")
        return {
            'success': False,
            'error': str(e),
            'movers': []
        }


@app.get("/api/trends/breakouts")
async def get_breakout_products(settings: Settings = Depends(get_settings)):
    """
    Get products with explosive momentum (>50% velocity)

    Identifies breakout products showing rapid acceleration.
    Similar to stock market breakout detection.

    Returns: Products with breakout momentum
    """
    try:
        from ospra_os.intelligence.momentum_tracker import get_momentum_tracker
        from ospra_os.database.product_history import ProductHistoryDB

        # Get live products directly from database
        db = ProductHistoryDB()
        products_data = db.get_all_products(niche=None)
        products_data = products_data[:100]  # Get more for filtering
        tracker = get_momentum_tracker()

        trending = await tracker.get_trending_products(
            products_data=products_data,
            limit=100
        )

        # Filter breakouts
        breakouts = tracker.get_breakout_products(trending)

        return {
            'success': True,
            'count': len(breakouts),
            'breakouts': breakouts,
            'threshold': 50.0
        }

    except Exception as e:
        logger.error(f"Breakouts error: {e}")
        return {
            'success': False,
            'error': str(e),
            'breakouts': []
        }


@app.get("/api/trends/product/{product_id}")
async def get_product_momentum(
    product_id: str,
    settings: Settings = Depends(get_settings)
):
    """
    Get detailed momentum data for a single product

    Path params:
    - product_id: Product identifier

    Returns: Complete momentum breakdown with metrics
    """
    try:
        from ospra_os.intelligence.momentum_tracker import get_momentum_tracker
        from ospra_os.dashboard.routes import get_product_by_id

        # Get product data
        product = await get_product_by_id(product_id)
        if not product:
            return {
                'success': False,
                'error': 'Product not found'
            }

        # Calculate momentum
        tracker = get_momentum_tracker()

        current_metrics = {
            "google_trends": product.get("trend_score", 0),
            "velocity_score": product.get("velocity_score", 0),
            "final_score": product.get("final_score", 0),
        }

        # Use 70% of current as baseline (TODO: fetch actual historical data)
        baseline_metrics = {k: v * 0.7 for k, v in current_metrics.items()}

        momentum = tracker.calculate_product_momentum(
            product_id=product_id,
            product_name=product.get("name", "Unknown"),
            current_metrics=current_metrics,
            baseline_metrics=baseline_metrics,
            current_rank=product.get("rank", 0),
            previous_rank=product.get("previous_rank")
        )

        return {
            'success': True,
            'product': momentum
        }

    except Exception as e:
        logger.error(f"Product momentum error: {e}")
        return {
            'success': False,
            'error': str(e)
        }


@app.get("/api/trends/heatmap")
async def get_momentum_heatmap(
    rows: int = 10,
    cols: int = 5,
    settings: Settings = Depends(get_settings)
):
    """
    Get heat map visualization data

    Query params:
    - rows: Number of rows in grid (default: 10)
    - cols: Number of columns in grid (default: 5)

    Returns: Grid data with color-coded momentum cells
    """
    try:
        from ospra_os.intelligence.momentum_tracker import get_momentum_tracker
        from ospra_os.database.product_history import ProductHistoryDB

        # Get live products directly from database
        total_cells = rows * cols
        db = ProductHistoryDB()
        products_data = db.get_all_products(niche=None)
        products_data = products_data[:total_cells]

        # Calculate momentum
        tracker = get_momentum_tracker()
        trending = await tracker.get_trending_products(
            products_data=products_data,
            limit=total_cells
        )

        # Generate heatmap
        heatmap = tracker.generate_heatmap_data(
            products=trending,
            grid_size=(rows, cols)
        )

        return {
            'success': True,
            **heatmap
        }

    except Exception as e:
        logger.error(f"Heatmap error: {e}")
        return {
            'success': False,
            'error': str(e),
            'grid': []
        }


# PRODUCT RANKINGS API retired (#57): the /api/rankings/* endpoints read
# RankingHistory (written by the deleted daily_ranking_job) + ranking_engine
# (deleted) — a self-contained dead subsystem, unused by the frontend.
# Replaced by product_timeseries + the lifecycle/anti-saturation grade.

@app.websocket("/ws/trends")
async def trends_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for real-time trends updates

    Broadcasts momentum updates every 5 seconds to connected clients.
    Clients receive live product momentum data for real-time dashboard updates.

    Connection lifecycle:
    1. Client connects
    2. Server sends initial trending data
    3. Server broadcasts updates every 5 seconds
    4. Client can disconnect anytime
    """
    import asyncio
    import json
    from datetime import datetime, timezone  # T83: timezone was missing → NameError on every update

    await websocket.accept()
    logger.info("[SUCCESS] WebSocket client connected to /ws/trends")

    try:
        from ospra_os.intelligence.momentum_tracker import get_momentum_tracker
        from ospra_os.dashboard.routes import get_products as get_live_products

        tracker = get_momentum_tracker()

        while True:
            try:
                # Fetch latest trending products
                response = await get_live_products(niche="smart_home", per_page=20)
                products_data = response.get("products", [])

                # Calculate momentum
                trending = await tracker.get_trending_products(
                    products_data=products_data,
                    limit=20,
                    sort_by='velocity'
                )

                # Get additional insights
                movers_up = tracker.get_biggest_movers(trending, limit=5, direction='up')
                breakouts = tracker.get_breakout_products(trending)

                # Prepare update message
                update = {
                    'type': 'trends_update',
                    'timestamp': datetime.now(timezone.utc).isoformat() + 'Z',
                    'data': {
                        'trending': trending[:10],  # Top 10
                        'movers': movers_up,
                        'breakouts': breakouts[:5],  # Top 5 breakouts
                        'total_products': len(trending)
                    }
                }

                # Send update to client
                await websocket.send_json(update)

                # Wait 5 seconds before next update
                await asyncio.sleep(5)

            except WebSocketDisconnect:
                logger.info("WebSocket client disconnected")
                break

            except Exception as e:
                logger.error(f"WebSocket update error: {e}")
                # Send error message to client
                error_msg = {
                    'type': 'error',
                    'timestamp': datetime.now(timezone.utc).isoformat() + 'Z',
                    'error': str(e)
                }
                await websocket.send_json(error_msg)
                await asyncio.sleep(5)  # Continue trying

    except WebSocketDisconnect:
        logger.info("WebSocket connection closed")

    except Exception as e:
        logger.error(f"WebSocket fatal error: {e}")
        try:
            await websocket.close()
        except Exception:
            pass  # Already disconnected or failed to close


# 
# SHOPIFY WEBHOOKS - Now handled by shopify_webhooks_router
# Legacy manual endpoints removed - all 24 webhooks are in ospra_os/webhooks/shopify_webhooks.py
#


# Mount static files (must be last)
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except Exception as e:
    logger.warning(f"Static files not mounted: {e}")

# Mount generated images directory for AI-generated product images
try:
    generated_images_dir = Path(__file__).parent.parent / "generated_images"
    generated_images_dir.mkdir(exist_ok=True)  # Create if doesn't exist
    app.mount("/generated_images", StaticFiles(directory=str(generated_images_dir)), name="generated_images")
    logger.info(f"Generated images mounted at /generated_images")
except Exception as e:
    logger.warning(f"Generated images not mounted: {e}")
