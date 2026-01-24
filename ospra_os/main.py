from dotenv import load_dotenv
import os
from pathlib import Path

# Load environment variables from .env file BEFORE any other imports
# Get the project root directory (where .env is located)
project_root = Path(__file__).parent.parent
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path, override=True)

# Debug: Print if OAuth vars are loaded
print(f" GOOGLE_OAUTH_CLIENT_ID loaded: {bool(os.getenv('GOOGLE_OAUTH_CLIENT_ID'))}")

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

# Security - Rate Limiting (PHASE 1 SECURITY)
from slowapi.errors import RateLimitExceeded
from ospra_os.security.rate_limiting import limiter, rate_limit_exceeded_handler, get_tier_limit

# Multi-Tenant Isolation (GROK RECOMMENDATION #14)
from ospra_os.tenancy.middleware import TenantMiddleware, StoreContextMiddleware

# Observability (TECHNICAL FIX T5)
try:
    from ospra_os.observability import setup_logging, setup_sentry, get_logger
    from ospra_os.observability.middleware import RequestLoggingMiddleware
    from ospra_os.observability.exception_handlers import register_exception_handlers
    _HAS_OBSERVABILITY = True
    print("[SUCCESS] Observability system loaded successfully")
except Exception as e:
    print(f"[WARNING]  Observability system not loaded: {e}")
    _HAS_OBSERVABILITY = False
    # Fallback to standard logging
    import logging
    logging.basicConfig(level=logging.INFO)
    get_logger = logging.getLogger

# Initialize logger
logger = get_logger(__name__) if _HAS_OBSERVABILITY else logging.getLogger(__name__)

# New integrations - Platform Adapters, AI, Deployment, Auto-Discovery
try:
    from ospra_os.platforms.factory import PlatformFactory
    _HAS_PLATFORM_FACTORY = True
    print("[SUCCESS] Platform Factory loaded successfully")
except Exception as e:
    print(f"[WARNING]  Platform Factory not loaded: {e}")
    PlatformFactory = None
    _HAS_PLATFORM_FACTORY = False

try:
    from ospra_os.deployment import UnifiedProductDeployer
    _HAS_UNIFIED_DEPLOYER = True
    print("[SUCCESS] Unified Product Deployer loaded successfully")
except Exception as e:
    print(f"[WARNING]  Unified Product Deployer not loaded: {e}")
    UnifiedProductDeployer = None
    _HAS_UNIFIED_DEPLOYER = False

try:
    from ospra_os.ai.factory import AIFactory
    _HAS_AI_FACTORY = True
    print("[SUCCESS] AI Factory loaded successfully")
except Exception as e:
    print(f"[WARNING]  AI Factory not loaded: {e}")
    AIFactory = None
    _HAS_AI_FACTORY = False

try:
    from ospra_os.background_jobs import start_auto_discovery_scheduler
    _HAS_AUTO_DISCOVERY = True
    print("[SUCCESS] Auto-Discovery system loaded successfully")
except Exception as e:
    print(f"[WARNING]  Auto-Discovery not loaded: {e}")
    start_auto_discovery_scheduler = None
    _HAS_AUTO_DISCOVERY = False

try:
    from ospra_os.utils.health_monitor import HealthMonitor
    _HAS_HEALTH_MONITOR = True
    print("[SUCCESS] Health Monitor loaded successfully")
except Exception as e:
    print(f"[WARNING]  Health Monitor not loaded: {e}")
    HealthMonitor = None
    _HAS_HEALTH_MONITOR = False

# Authentication router (required for user accounts)
try:
    from ospra_os.api.auth_routes import router as auth_router  # type: ignore
    _HAS_AUTH = True
    print("[SUCCESS] Authentication router loaded successfully")
except Exception as e:
    print(f"[WARNING]  Authentication router not loaded: {e}")
    auth_router = None
    _HAS_AUTH = False

# Password Reset router (required for forgot password flow)
try:
    from ospra_os.api.password_reset_routes import router as password_reset_router  # type: ignore
    _HAS_PASSWORD_RESET = True
    print("[SUCCESS] Password reset router loaded successfully")
except Exception as e:
    print(f"[WARNING]  Password reset router not loaded: {e}")
    password_reset_router = None
    _HAS_PASSWORD_RESET = False

# Frontend Compatibility router (provides missing endpoint aliases)
try:
    from ospra_os.api.frontend_compat_routes import router as frontend_compat_router  # type: ignore
    _HAS_FRONTEND_COMPAT = True
    print("[SUCCESS] Frontend compatibility router loaded successfully")
except Exception as e:
    print(f"[WARNING]  Frontend compatibility router not loaded: {e}")
    frontend_compat_router = None
    _HAS_FRONTEND_COMPAT = False

# Gmail OAuth router (optional)
try:
    from ospra_os.gmail.routes import router as gmail_oauth_router  # type: ignore
    print("[SUCCESS] Gmail OAuth router loaded successfully")
except Exception as e:
    print(f"[WARNING]  Gmail OAuth router not loaded: {e}")
    gmail_oauth_router = None

# TikTok router is optional — don't crash if it's not present
try:
    from ospra_os.tiktok.routes import router as tiktok_router  # type: ignore
    _HAS_TIKTOK = True
    print("[SUCCESS] TikTok router loaded successfully")
except Exception as e:  # ImportError, etc.
    print(f"[WARNING]  TikTok router not loaded: {e}")
    print("   This is expected if TikTok integration is not yet enabled")
    tiktok_router = None
    _HAS_TIKTOK = False

# Product Research router
try:
    from ospra_os.product_research.routes import router as research_router  # type: ignore
    _HAS_RESEARCH = True
    print("[SUCCESS] Product Research router loaded successfully")
except Exception as e:
    print(f"[WARNING]  Product Research router not loaded: {e}")
    research_router = None
    _HAS_RESEARCH = False

# Admin Dashboard router
try:
    from ospra_os.admin.routes import router as admin_router  # type: ignore
    _HAS_ADMIN = True
    print("[SUCCESS] Admin Dashboard router loaded successfully")
except Exception as e:
    print(f"[WARNING]  Admin Dashboard router not loaded: {e}")
    admin_router = None
    _HAS_ADMIN = False

# Advertising Automation router
try:
    from ospra_os.advertising.routes import router as advertising_router  # type: ignore
    _HAS_ADVERTISING = True
    print("[SUCCESS] Advertising Automation router loaded successfully")
except Exception as e:
    print(f"[WARNING]  Advertising router not loaded: {e}")
    advertising_router = None
    _HAS_ADVERTISING = False

# Email OAuth router (Multi-Provider Email OAuth)
try:
    from ospra_os.email_automation.oauth.routes import router as email_oauth_router  # type: ignore
    _HAS_EMAIL_OAUTH = True
    print("[SUCCESS] Email OAuth router loaded successfully")
except Exception as e:
    print(f"[WARNING]  Email OAuth router not loaded: {e}")
    email_oauth_router = None
    _HAS_EMAIL_OAUTH = False

# Email Analytics router (Dashboard metrics)
try:
    from ospra_os.email_automation.analytics_routes import router as email_analytics_router  # type: ignore
    _HAS_EMAIL_ANALYTICS = True
    print("[SUCCESS] Email Analytics router loaded successfully")
except Exception as e:
    print(f"[WARNING]  Email Analytics router not loaded: {e}")
    email_analytics_router = None
    _HAS_EMAIL_ANALYTICS = False

# Email Sync router (Fetch and display emails from connected accounts)
try:
    from ospra_os.email_automation.sync_routes import router as email_sync_router  # type: ignore
    _HAS_EMAIL_SYNC = True
    print("[SUCCESS] Email Sync router loaded successfully")
except Exception as e:
    print(f"[WARNING]  Email Sync router not loaded: {e}")
    email_sync_router = None
    _HAS_EMAIL_SYNC = False

# Email Automation router (Smart replies, inbox processing, analytics)
try:
    from ospra_os.api.email_automation_routes import router as email_automation_router  # type: ignore
    _HAS_EMAIL_AUTOMATION = True
    print("[SUCCESS] Email Automation router loaded successfully (/api/email-automation/*)")
except Exception as e:
    print(f"[WARNING]  Email Automation router not loaded: {e}")
    email_automation_router = None
    _HAS_EMAIL_AUTOMATION = False

# Email User Settings router (User preferences and toggles)
try:
    from ospra_os.email_automation.settings_routes import router as email_settings_router  # type: ignore
    _HAS_EMAIL_SETTINGS = True
    print("[SUCCESS] Email User Settings router loaded successfully")
except Exception as e:
    print(f"[WARNING]  Email User Settings router not loaded: {e}")
    email_settings_router = None
    _HAS_EMAIL_SETTINGS = False

# Dashboard V2 router (Intelligence Platform) - REAL-TIME with Google Trends + Claude AI
try:
    from ospra_os.dashboard.routes import router as dashboard_v2_router  # type: ignore
    _HAS_DASHBOARD_V2 = True
    print("[SUCCESS] Dashboard V2 REAL-TIME router loaded successfully")
except Exception as e:
    print(f"[WARNING]  Dashboard V2 REAL-TIME router not loaded: {e}")
    import traceback
    traceback.print_exc()
    dashboard_v2_router = None
    _HAS_DASHBOARD_V2 = False

# Multi-Store Portfolio router
try:
    from ospra_os.dashboard.routes_multi_store import router as multi_store_router  # type: ignore
    _HAS_MULTI_STORE = True
    print("[SUCCESS] Multi-Store Portfolio router loaded successfully")
except Exception as e:
    print(f"[WARNING]  Multi-Store Portfolio router not loaded: {e}")
    multi_store_router = None
    _HAS_MULTI_STORE = False

# AliExpress OAuth router
try:
    from ospra_os.aliexpress.routes import router as aliexpress_router  # type: ignore
    _HAS_ALIEXPRESS = True
    print("[SUCCESS] AliExpress OAuth router loaded successfully")
except Exception as e:
    print(f"[WARNING]  AliExpress OAuth router not loaded: {e}")
    aliexpress_router = None
    _HAS_ALIEXPRESS = False

# AliExpress Dropshipping API OAuth Callback
try:
    from ospra_os.api.aliexpress_oauth import router as aliexpress_callback_router  # type: ignore
    _HAS_ALIEXPRESS_CALLBACK = True
    print("[SUCCESS] AliExpress Dropshipping API callback router loaded successfully")
except Exception as e:
    print(f"[WARNING]  AliExpress callback router not loaded: {e}")
    aliexpress_callback_router = None
    _HAS_ALIEXPRESS_CALLBACK = False

# AliExpress Affiliate API OAuth Callback (different callback URL)
try:
    from ospra_os.api.aliexpress_affiliate_oauth import router as aliexpress_affiliate_callback_router  # type: ignore
    _HAS_ALIEXPRESS_AFFILIATE_CALLBACK = True
    print("[SUCCESS] AliExpress Affiliate API callback router loaded successfully")
except Exception as e:
    print(f"[WARNING]  AliExpress Affiliate callback router not loaded: {e}")
    aliexpress_affiliate_callback_router = None
    _HAS_ALIEXPRESS_AFFILIATE_CALLBACK = False

# AliExpress Token Management (Automatic Refresh)
try:
    from ospra_os.api.aliexpress_token_routes import router as aliexpress_token_router  # type: ignore
    _HAS_ALIEXPRESS_TOKEN_MANAGEMENT = True
    print("[SUCCESS] AliExpress Token Management router loaded successfully")
except Exception as e:
    print(f"[WARNING]  AliExpress Token Management router not loaded: {e}")
    aliexpress_token_router = None
    _HAS_ALIEXPRESS_TOKEN_MANAGEMENT = False

# AliExpress Product Scraping
try:
    from ospra_os.api.aliexpress_product_routes import router as aliexpress_product_router  # type: ignore
    _HAS_ALIEXPRESS_PRODUCTS = True
    print("[SUCCESS] AliExpress Product Scraping router loaded successfully")
except Exception as e:
    print(f"[WARNING]  AliExpress Product Scraping router not loaded: {e}")
    aliexpress_product_router = None
    _HAS_ALIEXPRESS_PRODUCTS = False

# TikTok OAuth router
try:
    from ospra_os.auth.tiktok_oauth import router as tiktok_oauth_router  # type: ignore
    _HAS_TIKTOK_OAUTH = True
    print("[SUCCESS] TikTok OAuth router loaded successfully")
except Exception as e:
    print(f"[WARNING]  TikTok OAuth router not loaded: {e}")
    tiktok_oauth_router = None
    _HAS_TIKTOK_OAUTH = False

# Shopify webhooks router
try:
    from ospra_os.webhooks.shopify_webhooks import router as shopify_webhooks_router  # type: ignore
    _HAS_SHOPIFY_WEBHOOKS = True
    print("[SUCCESS] Shopify webhooks router loaded successfully")
except Exception as e:
    print(f"[WARNING]  Shopify webhooks router not loaded: {e}")
    shopify_webhooks_router = None
    _HAS_SHOPIFY_WEBHOOKS = False

# Shopify OAuth router (SaaS Multi-Store OAuth Flow)
try:
    from ospra_os.api.shopify_oauth_routes import router as shopify_oauth_router  # type: ignore
    _HAS_SHOPIFY_OAUTH = True
    print("[SUCCESS] Shopify OAuth router loaded successfully")
except Exception as e:
    print(f"[WARNING]  Shopify OAuth router not loaded: {e}")
    shopify_oauth_router = None
    _HAS_SHOPIFY_OAUTH = False

# Shopify Deployment router (AI-Enhanced Shopify Integration)
try:
    from ospra_os.integrations.shopify.routes import router as shopify_deployment_router  # type: ignore
    _HAS_SHOPIFY_DEPLOYMENT = True
    print("[SUCCESS] Shopify Deployment router loaded successfully (AI-powered)")
except Exception as e:
    print(f"[WARNING]  Shopify Deployment router not loaded: {e}")
    shopify_deployment_router = None
    _HAS_SHOPIFY_DEPLOYMENT = False

# Shopify Store Management router (OAuth, store data, real-time sync)
try:
    from ospra_os.api.shopify_routes import router as shopify_store_router  # type: ignore
    _HAS_SHOPIFY_STORES = True
    print("[SUCCESS] Shopify Store Management router loaded successfully")
except Exception as e:
    print(f"[WARNING]  Shopify Store Management router not loaded: {e}")
    shopify_store_router = None
    _HAS_SHOPIFY_STORES = False

# WooCommerce Store Management router (Universal OAuth - No app registration needed)
try:
    from ospra_os.api.woocommerce_routes import router as woocommerce_router  # type: ignore
    _HAS_WOOCOMMERCE = True
    print("[SUCCESS] WooCommerce Store Management router loaded successfully")
except Exception as e:
    print(f"[WARNING]  WooCommerce Store Management router not loaded: {e}")
    woocommerce_router = None
    _HAS_WOOCOMMERCE = False

# Meta Ads router (Real API integration - No demo data)
try:
    from ospra_os.integrations.meta.routes import router as meta_ads_router  # type: ignore
    _HAS_META_ADS = True
    print("[SUCCESS] Meta Ads router loaded successfully (Real API only)")
except Exception as e:
    print(f"[WARNING]  Meta Ads router not loaded: {e}")
    meta_ads_router = None
    _HAS_META_ADS = False

# Deployment router (Unified Product Deployment with AI)
try:
    from ospra_os.api.deployment_routes import router as deployment_router  # type: ignore
    _HAS_DEPLOYMENT = True
    print("[SUCCESS] Unified Deployment router loaded successfully (AI-powered)")
except Exception as e:
    print(f"[WARNING]  Deployment router not loaded: {e}")
    deployment_router = None
    _HAS_DEPLOYMENT = False

# Auto-Deploy router (Automated Product Deployment)
try:
    from ospra_os.api.auto_deploy_routes import router as auto_deploy_router  # type: ignore
    _HAS_AUTO_DEPLOY = True
    print("[SUCCESS] Auto-Deploy router loaded successfully")
except Exception as e:
    print(f"[WARNING]  Auto-Deploy router not loaded: {e}")
    auto_deploy_router = None
    _HAS_AUTO_DEPLOY = False

# Analytics router (Revenue & Profit Tracking)
try:
    from ospra_os.analytics.routes import router as analytics_router  # type: ignore
    _HAS_ANALYTICS = True
    print("[SUCCESS] Analytics router loaded successfully")
except Exception as e:
    print(f"[WARNING]  Analytics router not loaded: {e}")
    analytics_router = None
    _HAS_ANALYTICS = False

# Customer Analytics router (Segments, LTV, Churn Prediction)
try:
    from ospra_os.analytics.customer_routes import router as customer_analytics_router  # type: ignore
    _HAS_CUSTOMER_ANALYTICS = True
    print("[SUCCESS] Customer Analytics router loaded successfully")
except Exception as e:
    print(f"[WARNING]  Customer Analytics router not loaded: {e}")
    customer_analytics_router = None
    _HAS_CUSTOMER_ANALYTICS = False

# Background Jobs router (Job Scheduler Management)
try:
    from ospra_os.jobs.routes import router as jobs_router  # type: ignore
    _HAS_JOBS = True
    print("[SUCCESS] Background Jobs router loaded successfully")
except Exception as e:
    print(f"[WARNING]  Background Jobs router not loaded: {e}")
    jobs_router = None
    _HAS_JOBS = False

# Customer Notifications router (Alert Management)
try:
    from ospra_os.services.notification_routes import router as notifications_router  # type: ignore
    _HAS_NOTIFICATIONS = True
    print("[SUCCESS] Notifications router loaded successfully")
except Exception as e:
    print(f"[WARNING]  Notifications router not loaded: {e}")
    notifications_router = None
    _HAS_NOTIFICATIONS = False

# System Health Monitoring router (Health Dashboard & Alerts)
try:
    from ospra_os.monitoring.routes import router as health_monitor_router  # type: ignore
    _HAS_HEALTH_MONITOR = True
    print("[SUCCESS] System Health Monitoring router loaded successfully")
except Exception as e:
    print(f"[WARNING]  System Health Monitoring router not loaded: {e}")
    health_monitor_router = None
    _HAS_HEALTH_MONITOR = False

# Niche Analysis router (Market Health & Entry Timing)
try:
    from ospra_os.intelligence.niche_routes import router as niche_router  # type: ignore
    _HAS_NICHE_ANALYSIS = True
    print("[SUCCESS] Niche Analysis router loaded successfully")
except Exception as e:
    print(f"[WARNING]  Niche Analysis router not loaded: {e}")
    niche_router = None
    _HAS_NICHE_ANALYSIS = False

# Competitor Intelligence router (Competitive Analysis & Price Tracking)
try:
    from ospra_os.intelligence.routes import router as competitor_router  # type: ignore
    _HAS_COMPETITOR_INTEL = True
    print("[SUCCESS] Competitor Intelligence router loaded successfully")
except Exception as e:
    print(f"[WARNING]  Competitor Intelligence router not loaded: {e}")
    competitor_router = None
    _HAS_COMPETITOR_INTEL = False

# Report Engine router
try:
    from ospra_os.reports.routes import router as report_router  # type: ignore
    _HAS_REPORTS = True
    print("[SUCCESS] Report Engine router loaded successfully")
except Exception as e:
    print(f"[WARNING]  Report Engine router not loaded: {e}")
    report_router = None
    _HAS_REPORTS = False

# Unified Product Discovery router (AliExpress Affiliate + Apify + Google Trends)
try:
    from ospra_os.intelligence.unified_discovery_routes import router as unified_discovery_router  # type: ignore
    _HAS_UNIFIED_DISCOVERY = True
    print("[SUCCESS] Unified Product Discovery router loaded successfully")
except Exception as e:
    print(f"[WARNING]  Unified Product Discovery router not loaded: {e}")
    unified_discovery_router = None
    _HAS_UNIFIED_DISCOVERY = False

# Intelligence Core router (Unified AI Brain - Briefings, Grading, Progress, Actions)
try:
    from ospra_os.intelligence.intelligence_core_routes import router as intelligence_core_router  # type: ignore
    _HAS_INTELLIGENCE_CORE = True
    print("[SUCCESS] Intelligence Core router loaded successfully")
except Exception as e:
    print(f"[WARNING]  Intelligence Core router not loaded: {e}")
    intelligence_core_router = None
    _HAS_INTELLIGENCE_CORE = False

# Learning System router (Self-Learning AI, Feedback, Insights)
try:
    from ospra_os.learning.learning_routes import router as learning_router  # type: ignore
    _HAS_LEARNING = True
    print("[SUCCESS] Learning System router loaded successfully")
except Exception as e:
    print(f"[WARNING]  Learning System router not loaded: {e}")
    learning_router = None
    _HAS_LEARNING = False

# Fulfillment System router (Auto-fulfillment, tracking, supplier integration)
try:
    from ospra_os.api.fulfillment_routes import router as fulfillment_router  # type: ignore
    _HAS_FULFILLMENT = True
    print("[SUCCESS] Fulfillment System router loaded successfully")
except Exception as e:
    print(f"[WARNING]  Fulfillment System router not loaded: {e}")
    fulfillment_router = None
    _HAS_FULFILLMENT = False

# Oi AI Assistant router (The Brain of Ospra Intelligence)
try:
    from ospra_os.api.oi_routes import router as oi_router  # type: ignore
    _HAS_OI = True
    print("[SUCCESS] Oi AI Assistant router loaded successfully [BRAIN]")
except Exception as e:
    print(f"[WARNING]  Oi AI Assistant router not loaded: {e}")
    oi_router = None
    _HAS_OI = False

# Oi Alerts router (Real-time notifications for Oi AI)
try:
    from ospra_os.api.alert_routes import router as alert_router, ws_router as alert_ws_router  # type: ignore
    _HAS_ALERTS = True
    print("[SUCCESS] Oi Alerts router loaded successfully")
except Exception as e:
    print(f"[WARNING]  Oi Alerts router not loaded: {e}")
    alert_router = None
    alert_ws_router = None
    _HAS_ALERTS = False

# Inventory Forecasting router
try:
    from ospra_os.inventory.routes import router as inventory_router  # type: ignore
    _HAS_INVENTORY = True
    print("[SUCCESS] Inventory Forecasting router loaded successfully")
except Exception as e:
    print(f"[WARNING]  Inventory Forecasting router not loaded: {e}")
    inventory_router = None
    _HAS_INVENTORY = False

# A/B Testing router
try:
    from ospra_os.testing.routes import router as abtesting_router  # type: ignore
    _HAS_ABTESTING = True
    print("[SUCCESS] A/B Testing router loaded successfully")
except Exception as e:
    print(f"[WARNING]  A/B Testing router not loaded: {e}")
    abtesting_router = None
    _HAS_ABTESTING = False

# Image Processing router
try:
    from ospra_os.api.image_routes import router as image_router  # type: ignore
    _HAS_IMAGE_PROCESSING = True
    print("[SUCCESS] Image Processing router loaded successfully")
except Exception as e:
    print(f"[WARNING]  Image Processing router not loaded: {e}")
    image_router = None
    _HAS_IMAGE_PROCESSING = False

# AI Chat router (Claude chat with learning context)
try:
    from ospra_os.api.ai_chat_routes import router as ai_chat_router  # type: ignore
    _HAS_AI_CHAT = True
    print("[SUCCESS] AI Chat router loaded successfully")
except Exception as e:
    print(f"[WARNING]  AI Chat router not loaded: {e}")
    ai_chat_router = None
    _HAS_AI_CHAT = False

# AI Image Generation router (DALL-E 3 brand images for Oubon Shop)
try:
    from ospra_os.api.image_generation_routes import router as image_generation_router  # type: ignore
    _HAS_IMAGE_GENERATION = True
    print("[SUCCESS] AI Image Generation router loaded successfully")
except Exception as e:
    print(f"[WARNING]  AI Image Generation router not loaded: {e}")
    image_generation_router = None
    _HAS_IMAGE_GENERATION = False

# Actions Queue router (AI-generated actions that require approval)
try:
    from ospra_os.api.actions_routes import router as actions_router  # type: ignore
    _HAS_ACTIONS = True
    print("[SUCCESS] Actions Queue router loaded successfully")
except Exception as e:
    print(f"[WARNING]  Actions Queue router not loaded: {e}")
    actions_router = None
    _HAS_ACTIONS = False

# Daily Brief router (Personalized morning summaries with AI actions)
try:
    from ospra_os.api.daily_brief_routes import router as daily_brief_router  # type: ignore
    _HAS_DAILY_BRIEF = True
    print("[SUCCESS] Daily Brief router loaded successfully")
except Exception as e:
    print(f"[WARNING]  Daily Brief router not loaded: {e}")
    daily_brief_router = None
    _HAS_DAILY_BRIEF = False

# Auto-Pilot router (Autonomous action execution - GROK RECOMMENDATION #7)
try:
    from ospra_os.api.auto_pilot_routes import router as auto_pilot_router  # type: ignore
    _HAS_AUTO_PILOT = True
    print("[SUCCESS] Auto-Pilot router loaded successfully")
except Exception as e:
    print(f"[WARNING]  Auto-Pilot router not loaded: {e}")
    auto_pilot_router = None
    _HAS_AUTO_PILOT = False

# Voice Commands router (Whisper API integration - GROK RECOMMENDATION #9)
try:
    from ospra_os.api.voice_routes import router as voice_router  # type: ignore
    _HAS_VOICE = True
    print("[SUCCESS] Voice Commands router loaded successfully")
except Exception as e:
    print(f"[WARNING]  Voice Commands router not loaded: {e}")
    voice_router = None
    _HAS_VOICE = False

# Store Management router (Multi-Store Selector - GROK RECOMMENDATION #11)
try:
    from ospra_os.api.store_routes import router as store_router  # type: ignore
    _HAS_STORES = True
    print("[SUCCESS] Store Management router loaded successfully")
except Exception as e:
    print(f"[WARNING]  Store Management router not loaded: {e}")
    store_router = None
    _HAS_STORES = False

# Template Vault router (Action Template Marketplace - GROK RECOMMENDATION #12)
try:
    from ospra_os.api.template_routes import router as template_router  # type: ignore
    _HAS_TEMPLATES = True
    print("[SUCCESS] Template Vault router loaded successfully")
except Exception as e:
    print(f"[WARNING]  Template Vault router not loaded: {e}")
    template_router = None
    _HAS_TEMPLATES = False

# Task Monitoring router (Celery Task Queue - GROK RECOMMENDATION #13)
try:
    from ospra_os.api.task_routes import router as task_router  # type: ignore
    _HAS_TASKS = True
    print("[SUCCESS] Task Monitoring router loaded successfully")
except Exception as e:
    print(f"[WARNING]  Task Monitoring router not loaded: {e}")
    task_router = None
    _HAS_TASKS = False

# ML System router (GROK RECOMMENDATION #15 - Llama Fine-Tuning for 70% Cost Savings)
try:
    from ospra_os.api.ml_routes import router as ml_router  # type: ignore
    _HAS_ML = True
    print("[SUCCESS] ML System router loaded successfully (Cost-optimized AI)")
except Exception as e:
    print(f"[WARNING]  ML System router not loaded: {e}")
    ml_router = None
    _HAS_ML = False

# Amazon FBA router (GROK RECOMMENDATION #16 - Amazon FBA Multi-Marketplace Integration)
try:
    from ospra_os.api.amazon_routes import router as amazon_router  # type: ignore
    _HAS_AMAZON = True
    print("[SUCCESS] Amazon FBA router loaded successfully (Multi-Marketplace)")
except Exception as e:
    print(f"[WARNING]  Amazon FBA router not loaded: {e}")
    amazon_router = None
    _HAS_AMAZON = False

# Federated Learning router (GROK RECOMMENDATION #18 - Privacy-Preserving Collective Intelligence)
try:
    from ospra_os.federated.routes import get_federated_router
    federated_router = get_federated_router()
    _HAS_FEDERATED = True
    print("[SUCCESS] Federated Learning router loaded successfully (Privacy-Preserving)")
except Exception as e:
    print(f"[WARNING]  Federated Learning router not loaded: {e}")
    federated_router = None
    _HAS_FEDERATED = False

# White-Label SaaS router (GROK RECOMMENDATION #19 - Agency Rebrand B2B2C)
try:
    from ospra_os.whitelabel.routes import get_whitelabel_router
    whitelabel_router = get_whitelabel_router()
    _HAS_WHITELABEL = True
    print("[SUCCESS] White-Label SaaS router loaded successfully (Agency Rebrand B2B2C)")
except Exception as e:
    print(f"[WARNING]  White-Label SaaS router not loaded: {e}")
    whitelabel_router = None
    _HAS_WHITELABEL = False

# Feedback Loop router (G4: Complete Feedback Loop - AI learns from real sales data)
try:
    from ospra_os.api.feedback_routes import router as feedback_router  # type: ignore
    _HAS_FEEDBACK = True
    print("[SUCCESS] Feedback Loop router loaded successfully (G4: AI learns from sales)")
except Exception as e:
    print(f"[WARNING]  Feedback Loop router not loaded: {e}")
    feedback_router = None
    _HAS_FEEDBACK = False

# Import GmailClient for the OAuth callback
try:
    from app.gmail_client import GmailClient
    print("[SUCCESS] GmailClient loaded from app.gmail_client")
except Exception as e:
    print(f"[WARNING]  Could not import GmailClient: {e}")
    GmailClient = None

app = FastAPI(title="OspraOS API", version="0.1")

#
# SECURITY: Rate Limiting Setup (PHASE 1)
# Must be configured BEFORE middleware to protect all endpoints
#
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
print("[SUCCESS] ✓ Rate limiting enabled (Phase 1 Security)")

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

    # Register exception handlers
    register_exception_handlers(app)

    # Add request logging middleware
    app.add_middleware(RequestLoggingMiddleware)

    logger.info("[SUCCESS] Observability initialized successfully")

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
print("[SUCCESS] ✓ CORS restricted to ospra.io + localhost (Phase 1 Security)")

# Request Timeout Protection (PHASE 1 SECURITY)
# Prevents requests from hanging indefinitely by enforcing 30-second timeout
from ospra_os.middleware.timeout_middleware import TimeoutMiddleware
app.add_middleware(TimeoutMiddleware, timeout_seconds=30)
print("[SUCCESS] ✓ Request timeout protection active (30s limit)")

# Custom Rate Limiting (PHASE 1 SECURITY)
# In-memory rate limiter with tier-based limits (upgradable to Redis)
from ospra_os.middleware.custom_rate_limiter import CustomRateLimitMiddleware
app.add_middleware(CustomRateLimitMiddleware, get_tier_limit_func=get_tier_limit)
print("[SUCCESS] ✓ Custom rate limiting active (tier-based, in-memory)")

# Trust proxy headers from Render (for HTTPS URL generation)
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

# Multi-Tenant Isolation (GROK RECOMMENDATION #14)
# IMPORTANT: These middleware run AFTER auth, extracting tenant context from JWT
# Order matters: Tenant middleware must come after CORS/Proxy but before routes
app.add_middleware(StoreContextMiddleware)  # Extract store_id from query params/headers
app.add_middleware(TenantMiddleware)  # Extract tenant_id from JWT token
print("[SUCCESS] Tenant isolation middleware registered (GROK #14)")

# Tier Enforcement (PHASE 1 SECURITY)
# Enforces subscription limits and feature access based on user tier
from ospra_os.middleware.tier_enforcement import TierEnforcementMiddleware
app.add_middleware(TierEnforcementMiddleware)
print("[SUCCESS] ✓ Tier enforcement middleware active (Phase 1 Security)")

# Mount static files for product images (only if directory exists)
import os
from pathlib import Path

images_dir = Path("data/images")
if not images_dir.exists():
    os.makedirs(images_dir, exist_ok=True)
    print(f"[SUCCESS] Created images directory: {images_dir}")

app.mount("/static/images", StaticFiles(directory="data/images"), name="images")

# ---------------------------------------------------------------
# CRITICAL: Immediate Health Check Endpoint
# Must be defined BEFORE heavy router imports to respond quickly
# This ensures Render health checks pass even during startup
# ---------------------------------------------------------------
@app.get("/health")
def health_check_immediate():
    """Immediate health check that responds before full initialization."""
    return {"status": "ok", "service": "Ospra Intelligence Platform", "version": "2026-01-11"}

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
# Startup Event - Initialize DBs and Scheduler
# ---------------------------------------------------------------
@app.on_event("startup")
async def startup_event():
    """Initialize databases and start background scheduler."""
    import time
    import asyncio
    import os

    # Skip startup initialization in test mode
    if os.getenv("APP_ENV") == "testing":
        print("[TEST] Test mode detected - skipping startup initialization")
        return

    startup_start = time.time()
    print(f"[START] Startup initiated at {time.strftime('%Y-%m-%d %H:%M:%S')}")

    settings = get_settings()

    # Initialize follow-up tracking database
    try:
        from app.models import init_followup_db
        init_followup_db(settings.database_url)
        print("[SUCCESS] Follow-up database initialized")
    except Exception as e:
        print(f"[WARNING]  Follow-up database initialization failed: {e}")

    # Initialize analytics database
    try:
        from app.analytics import init_analytics_db
        init_analytics_db(settings.database_url)
        print("[SUCCESS] Analytics database initialized")
    except Exception as e:
        print(f"[WARNING]  Analytics database initialization failed: {e}")

    # Initialize AliExpress OAuth database
    try:
        from ospra_os.aliexpress.oauth import init_aliexpress_oauth_db
        init_aliexpress_oauth_db(settings.database_url)
        print("[SUCCESS] AliExpress OAuth database initialized")
    except Exception as e:
        print(f"[WARNING]  AliExpress OAuth database initialization failed: {e}")

    # Initialize Multi-Store database (CRITICAL: Must use init_database not init_multi_store_db)
    # init_multi_store_db uses legacy Base that doesn't include User model!
    try:
        from ospra_os.database import init_database
        init_database(settings.database_url)
        print("[SUCCESS] All database tables initialized (including users table)")
    except Exception as e:
        print(f"[ERROR] Database initialization failed: {e}")
        import traceback
        traceback.print_exc()
        # Don't swallow this error - it's critical
        raise

    # Initialize Ad Schedule database
    try:
        from ospra_os.models.ad_schedule import Base
        from ospra_os.database.connection import get_engine
        engine = get_engine(settings.database_url)
        Base.metadata.create_all(engine)
        print("[SUCCESS] Ad Schedule database initialized")
    except Exception as e:
        print(f"[WARNING]  Ad Schedule database initialization failed: {e}")

    # Initialize Report database
    try:
        from ospra_os.models.report import init_report_tables
        from ospra_os.database.connection import get_engine
        engine = get_engine(settings.database_url)
        init_report_tables(engine)
        print("[SUCCESS] Report database initialized")
    except Exception as e:
        print(f"[WARNING]  Report database initialization failed: {e}")

    # Start report scheduler
    try:
        from ospra_os.reports.scheduler import get_scheduler
        scheduler = get_scheduler()
        await scheduler.start()
        print("[SUCCESS] Report scheduler started")
    except Exception as e:
        print(f"[WARNING]  Report scheduler failed to start: {e}")

    # Start background schedule processor
    try:
        from ospra_os.jobs.schedule_processor import start_schedule_processor
        start_schedule_processor()
        print("[SUCCESS] Schedule processor started (runs every 5 minutes)")
    except Exception as e:
        print(f"[WARNING]  Schedule processor failed to start: {e}")

    # DEPRECATED: APScheduler replaced by Celery Beat (GROK #13)
    # Background email checking is now handled by Celery tasks
    # See: ospra_os/tasks/email_tasks.py
    # To enable: Use Celery Beat scheduler instead
    # try:
    #     from app.scheduler import start_scheduler
    #     start_scheduler()
    #     print("[SUCCESS] Background scheduler started")
    # except Exception as e:
    #     print(f"[WARNING]  Scheduler failed to start: {e}")
    print("[INFO]  Email scheduling managed by Celery Beat (see /api/tasks/beat-schedule)")

    # Start product monitoring in background thread
    try:
        from ospra_os.background_jobs.product_monitor import ProductMonitor
        from threading import Thread
        import time
        import logging

        logger = logging.getLogger(__name__)
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
                        print(notification)

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
        print("[SUCCESS] Product monitoring started (6-hour intervals)")

    except Exception as e:
        print(f"[WARNING]  Product monitoring failed to start: {e}")

    # Start Level 3 AI background jobs
    try:
        from ospra_os.intelligence.background_jobs import start_background_jobs
        import logging

        logger = logging.getLogger(__name__)

        start_background_jobs()
        logger.info("[SUCCESS] Level 3 AI activated - background monitoring enabled")
        print("[SUCCESS] Level 3 AI activated - background monitoring enabled")
    except Exception as e:
        print(f"[WARNING]  Level 3 AI not available - continuing without background monitoring: {e}")

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
                    print(f"[SUCCESS] Auto-discovery scheduler started (every {discovery_interval} hours)")
                else:
                    # Daily scheduling
                    start_auto_discovery_scheduler(
                        database_url=settings.database_url,
                        hour=discovery_hour
                    )
                    print(f"[SUCCESS] Auto-discovery scheduler started (daily at {discovery_hour:02d}:00)")
            else:
                print("[WARNING]  Auto-discovery disabled in environment or no database URL")
        except Exception as e:
            print(f"[WARNING]  Auto-discovery scheduler failed to start: {e}")
            import traceback
            traceback.print_exc()

    # Start daily ranking background scheduler
    try:
        from ospra_os.background_jobs.daily_ranking_job import start_daily_ranking_scheduler
        import os

        # Check if ranking job is enabled in environment (default: true)
        ranking_enabled = os.getenv('DAILY_RANKING_ENABLED', 'true').lower() == 'true'

        if ranking_enabled and settings.database_url:
            ranking_hour = int(os.getenv('RANKING_HOUR', '3'))  # Default: 3 AM
            ranking_minute = int(os.getenv('RANKING_MINUTE', '0'))  # Default: :00

            # Start daily ranking scheduler
            start_daily_ranking_scheduler(
                database_url=settings.database_url,
                hour=ranking_hour,
                minute=ranking_minute
            )
            print(f"[SUCCESS] Daily ranking scheduler started (daily at {ranking_hour:02d}:{ranking_minute:02d})")
        else:
            print("[WARNING]  Daily ranking disabled in environment or no database URL")
    except Exception as e:
        print(f"[WARNING]  Daily ranking scheduler failed to start: {e}")
        import traceback
        traceback.print_exc()

    # Start realtime momentum updater
    try:
        from ospra_os.intelligence.realtime_updater import start_realtime_updates

        await start_realtime_updates()
        print("[SUCCESS] Realtime momentum updater started (5-minute intervals)")
    except Exception as e:
        print(f"[WARNING]  Realtime momentum updater failed to start: {e}")
        import traceback
        traceback.print_exc()

    # DEPRECATED: APScheduler replaced by Celery Beat (GROK #13)
    # Customer analytics jobs are now handled by Celery tasks
    # See: ospra_os/tasks/analytics_tasks.py and ospra_os/tasks/learning_tasks.py
    # To enable: Use Celery Beat scheduler instead
    # try:
    #     from ospra_os.jobs.scheduler import start_scheduler as start_customer_scheduler
    #     start_customer_scheduler()
    #     print("[SUCCESS] Customer analytics scheduler started")
    # except Exception as e:
    #     print(f"[WARNING]  Customer analytics scheduler failed to start: {e}")
    print("[INFO]  Customer analytics managed by Celery Beat (see /api/tasks/beat-schedule)")

    # Start AliExpress token refresh scheduler
    try:
        from ospra_os.api.aliexpress_token_scheduler import start_token_refresh_scheduler, check_tokens_on_startup
        start_token_refresh_scheduler()
        # Check tokens immediately on startup
        await check_tokens_on_startup()
        print("[SUCCESS] AliExpress token refresh scheduler started")
    except Exception as e:
        print(f"[WARNING]  AliExpress token refresh scheduler failed to start: {e}")

    # Start Auto-Deploy scheduler
    try:
        from ospra_os.background_jobs.auto_deploy_job import start_auto_deploy_scheduler
        start_auto_deploy_scheduler()
        print("[SUCCESS] Auto-deploy scheduler started (runs every hour)")
    except Exception as e:
        print(f"[WARNING]  Auto-deploy scheduler failed to start: {e}")

    # Start Learning Summary background jobs
    try:
        from ospra_os.learning.summary_jobs import setup_summary_jobs
        setup_summary_jobs()
        print("[SUCCESS] Learning summary jobs started (nightly at 3:00 AM UTC)")
    except Exception as e:
        print(f"[WARNING]  Learning summary jobs failed to start: {e}")

    # Log startup completion with timing
    startup_duration = time.time() - startup_start
    print(f"[SUCCESS] Startup completed in {startup_duration:.2f} seconds at {time.strftime('%Y-%m-%d %H:%M:%S')}")


# ---------------------------------------------------------------
# Shutdown Event - Stop Background Jobs
# ---------------------------------------------------------------
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    import logging

    logger = logging.getLogger(__name__)
    logger.info("[PAUSE]  Shutting down Ospra Intelligence...")
    print("[PAUSE]  Shutting down Ospra Intelligence...")

    # Stop Level 3 AI background jobs
    try:
        from ospra_os.intelligence.background_jobs import stop_background_jobs
        stop_background_jobs()
        logger.info("[SUCCESS] Background jobs stopped")
        print("[SUCCESS] Background jobs stopped")
    except Exception as e:
        logger.error(f"Error stopping background jobs: {e}")
        print(f"[WARNING]  Error stopping background jobs: {e}")

    # Stop learning summary jobs
    try:
        from ospra_os.learning.summary_jobs import shutdown_summary_jobs
        shutdown_summary_jobs()
        logger.info("[SUCCESS] Learning summary jobs stopped")
        print("[SUCCESS] Learning summary jobs stopped")
    except Exception as e:
        logger.error(f"Error stopping summary jobs: {e}")
        print(f"[WARNING]  Error stopping summary jobs: {e}")

    # Stop realtime momentum updater
    try:
        from ospra_os.intelligence.realtime_updater import stop_realtime_updates
        await stop_realtime_updates()
        logger.info("[SUCCESS] Realtime momentum updater stopped")
        print("[SUCCESS] Realtime momentum updater stopped")
    except Exception as e:
        logger.error(f"Error stopping realtime updater: {e}")
        print(f"[WARNING]  Error stopping realtime updater: {e}")

    # Stop AliExpress token refresh scheduler
    try:
        from ospra_os.api.aliexpress_token_scheduler import stop_token_refresh_scheduler
        stop_token_refresh_scheduler()
        logger.info("[SUCCESS] AliExpress token refresh scheduler stopped")
        print("[SUCCESS] AliExpress token refresh scheduler stopped")
    except Exception as e:
        logger.error(f"Error stopping token refresh scheduler: {e}")
        print(f"[WARNING]  Error stopping token refresh scheduler: {e}")

    # Stop report scheduler
    try:
        from ospra_os.reports.scheduler import get_scheduler
        scheduler = get_scheduler()
        await scheduler.stop()
        logger.info("[SUCCESS] Report scheduler stopped")
        print("[SUCCESS] Report scheduler stopped")
    except Exception as e:
        logger.error(f"Error stopping report scheduler: {e}")
        print(f"[WARNING]  Error stopping report scheduler: {e}")

    # Stop customer analytics scheduler
    try:
        from ospra_os.jobs.scheduler import stop_scheduler as stop_customer_scheduler
        stop_customer_scheduler()
        logger.info("[SUCCESS] Customer analytics scheduler stopped")
        print("[SUCCESS] Customer analytics scheduler stopped")
    except Exception as e:
        logger.error(f"Error stopping customer analytics scheduler: {e}")
        print(f"[WARNING]  Error stopping customer analytics scheduler: {e}")


if gmail_oauth_router:
    app.include_router(gmail_oauth_router)  # exposes /gmail/auth/*

if _HAS_AUTH and auth_router:
    app.include_router(auth_router)  # exposes /api/auth/* (registration, login, JWT)

if _HAS_PASSWORD_RESET and password_reset_router:
    app.include_router(password_reset_router)  # exposes /api/auth/forgot-password, /api/auth/reset-password

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
        import traceback
        return {
            "success": False,
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc()
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
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


# ---------------------------------------------------------------
# Self-Learning System API Endpoints
# ---------------------------------------------------------------
@app.post("/api/learning/train")
async def train_learning_engine(
    sales_data: Optional[List[Dict]] = None,
    settings: Settings = Depends(get_settings)
):
    """
    Train self-learning engine with sales data

    Use this endpoint to:
    - Feed real Shopify sales data
    - Adjust AI confidence weights
    - Improve product predictions

    Returns: Learning cycle report
    """
    try:
        from ospra_os.learning.self_learning_engine import SelfLearningEngine
        from ospra_os.learning.performance_tracker import PerformanceTracker

        engine = SelfLearningEngine()

        # If no sales data provided, fetch from Shopify
        if not sales_data:
            tracker = PerformanceTracker()
            # TODO: Connect to real Shopify client
            sales_data = await tracker.get_learning_dataset()

        if not sales_data:
            # No data? Run demo
            report = await engine.simulate_learning_cycle()
        else:
            # Real data! Learn from it
            await engine.learn_from_sales(sales_data)
            report = await engine.get_learning_report()

        return {
            "success": True,
            "message": f"Learning cycle #{engine.weights['total_learning_cycles']} complete",
            "report": report
        }

    except Exception as e:
        import traceback
        return {"success": False, "error": str(e), "traceback": traceback.format_exc()}


@app.get("/api/learning/report")
async def get_learning_report():
    """Get current learning engine status"""
    try:
        from ospra_os.learning.self_learning_engine import SelfLearningEngine

        engine = SelfLearningEngine()
        report = await engine.get_learning_report()

        return {"success": True, "report": report}
    except Exception as e:
        import traceback
        return {"success": False, "error": str(e)}


@app.get("/api/learning/velocity")
async def get_velocity_report():
    """
    Get trend velocity report

    Shows:
    - Early spike opportunities (catch products early!)
    - Declining products (remove from store)
    - Sustained growth products (keep selling)
    """
    try:
        from ospra_os.learning.trend_velocity_detector import TrendVelocityDetector

        detector = TrendVelocityDetector()
        report = await detector.get_velocity_report()

        return {"success": True, "report": report}
    except Exception as e:
        import traceback
        return {"success": False, "error": str(e)}


@app.post("/api/learning/demo")
async def run_learning_demo():
    """
    DEMO: Test learning system with sample data

    Run this BEFORE you have real sales to see how it works!
    """
    try:
        from ospra_os.learning.self_learning_engine import SelfLearningEngine

        # Run demo learning cycle
        engine = SelfLearningEngine()
        learning_report = await engine.simulate_learning_cycle()

        return {
            "success": True,
            "learning_report": learning_report,
            "message": "Demo complete! AI learned from sample data."
        }
    except Exception as e:
        import traceback
        return {"success": False, "error": str(e), "traceback": traceback.format_exc()}

# ---------------------------------------------------------------
# NEW: Unified Deployment API Endpoints
# ---------------------------------------------------------------
@app.post("/api/deploy/product/{product_id}/to-store/{store_id}")
async def deploy_product_endpoint(
    product_id: int,
    store_id: int,
    settings: Settings = Depends(get_settings)
):
    """
    Deploy product to specific store using Unified Deployer.

    Features:
    - AI-powered content generation
    - Platform-specific optimization
    - Automatic deployment tracking
    """
    if not _HAS_UNIFIED_DEPLOYER or not UnifiedProductDeployer:
        return {"success": False, "error": "Unified Deployer not available"}

    try:
        deployer = UnifiedProductDeployer(database_url=settings.database_url)
        result = await deployer.deploy_to_store(
            product_id=product_id,
            store_id=store_id
        )
        return result
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


@app.post("/api/deploy/product/{product_id}/to-all-stores")
async def deploy_product_to_all(
    product_id: int,
    user_id: int,
    settings: Settings = Depends(get_settings)
):
    """
    Deploy product to all user's stores concurrently.

    Features:
    - Concurrent multi-store deployment
    - AI content generation for each platform
    - Comprehensive deployment tracking
    """
    if not _HAS_UNIFIED_DEPLOYER or not UnifiedProductDeployer:
        return {"success": False, "error": "Unified Deployer not available"}

    try:
        deployer = UnifiedProductDeployer(database_url=settings.database_url)
        result = await deployer.deploy_to_all_stores(
            product_id=product_id,
            user_id=user_id
        )
        return result
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


# ---------------------------------------------------------------
# NEW: AI Provider Management API Endpoints
# ---------------------------------------------------------------
@app.get("/api/ai/providers")
async def get_ai_providers():
    """
    Get available AI providers (OpenAI, Claude, Gemini).

    Returns:
        {
            "success": true,
            "providers": ["openai", "claude", "gemini"],
            "default": "openai"
        }
    """
    if not _HAS_AI_FACTORY or not AIFactory:
        return {
            "success": False,
            "error": "AI Factory not available"
        }

    try:
        return {
            "success": True,
            "providers": AIFactory.get_available_providers(),
            "default": AIFactory.get_default_provider()
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@app.post("/api/ai/test/{provider}")
async def test_ai_provider(
    provider: str,
    api_key: str = Body(...),
    settings: Settings = Depends(get_settings)
):
    """
    Test AI provider credentials.

    Args:
        provider: Provider name (openai, claude, gemini)
        api_key: API key to test

    Returns:
        {
            "success": true,
            "provider": "openai",
            "message": "Connection successful"
        }
    """
    if not _HAS_AI_FACTORY or not AIFactory:
        return {"success": False, "error": "AI Factory not available"}

    try:
        ai = AIFactory.get_provider(provider, {"api_key": api_key})
        result = await ai.test_connection()

        return {
            "success": result.get("success", False),
            "provider": provider,
            "message": "Connection successful" if result.get("success") else result.get("error", "Connection failed")
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


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
    credentials: Dict = Body(...),
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
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


# ---------------------------------------------------------------
# Dashboard API Endpoints (New Unified Dashboard)
# ---------------------------------------------------------------
@app.get("/api/dashboard/overview")
async def get_dashboard_overview(settings: Settings = Depends(get_settings)):
    """
    Dashboard overview with system stats.

    Returns:
    - Total products discovered
    - Total potential revenue
    - Average profit margin
    - Top performing category
    """
    try:
        from ospra_os.intelligence.product_intelligence import ProductIntelligenceEngine

        # Get products from intelligence engine
        engine = ProductIntelligenceEngine()
        products_data = await engine.discover_winning_products(
            niches=["smart home", "tech gadgets"],
            max_per_niche=3
        )

        if not products_data:
            return {
                "total_products": 0,
                "total_revenue": 0.0,
                "avg_profit_margin": 0.0,
                "top_performing_category": "N/A"
            }

        # Calculate metrics
        total_products = len(products_data)
        total_revenue = sum(p.get("display_data", {}).get("market_price", 0) * 10 for p in products_data)  # Assuming 10 units each
        avg_profit_margin = sum(p.get("display_data", {}).get("profit_margin", 0) for p in products_data) / total_products if total_products > 0 else 0

        # Find top category by average score
        category_scores = {}
        for p in products_data:
            niche = p.get("niche", "General")
            if niche not in category_scores:
                category_scores[niche] = []
            category_scores[niche].append(p.get("score", 0))

        top_category = max(category_scores.items(), key=lambda x: sum(x[1])/len(x[1]) if x[1] else 0)[0] if category_scores else "N/A"

        return {
            "total_products": total_products,
            "total_revenue": round(total_revenue, 2),
            "avg_profit_margin": round(avg_profit_margin, 1),
            "top_performing_category": top_category
        }
    except Exception as e:
        import traceback
        print(f"Error in dashboard overview: {e}")
        print(traceback.format_exc())
        return {
            "total_products": 0,
            "total_revenue": 0.0,
            "avg_profit_margin": 0.0,
            "top_performing_category": "Error"
        }


@app.get("/api/dashboard/products")
async def get_dashboard_products(
    limit: int = 6,
    min_score: float = 7.0,
    settings: Settings = Depends(get_settings)
):
    """
    Get product discovery results with scores.

    Returns recent product research results from intelligence engine.
    """
    try:
        from ospra_os.intelligence.product_intelligence import ProductIntelligenceEngine

        # Discover products using intelligence engine
        engine = ProductIntelligenceEngine()
        products_data = await engine.discover_winning_products(
            niches=["smart home", "tech gadgets"],
            max_per_niche=limit // 2
        )

        # Transform to dashboard format
        products = []
        for idx, p in enumerate(products_data[:limit]):
            display = p.get("display_data", {})
            products.append({
                "id": str(idx + 1),
                "name": display.get("name", "Unknown Product"),
                "category": p.get("niche", "General"),
                "price": display.get("market_price", 0),
                "cost": display.get("supplier_cost", 0),
                "profit_margin": display.get("profit_margin", 0),
                "score": p.get("score", 0),
                "description": p.get("ai_explanation", "")[:200] + "..." if p.get("ai_explanation") else "No description",
                "features": [
                    f"Supplier: {display.get('supplier_orders', 0):,} orders",
                    f"Rating: {display.get('supplier_rating', 0)}",
                    f"Profit: ${display.get('estimated_profit', 0):.2f} per sale"
                ],
                "supplier_url": display.get("supplier_url", ""),
                "created_at": "2025-11-02T00:00:00Z"
            })

        return products
    except Exception as e:
        import traceback
        print(f"Error fetching products: {e}")
        print(traceback.format_exc())
        return []


@app.get("/api/dashboard/emails")
async def get_dashboard_emails(settings: Settings = Depends(get_settings)):
    """
    Email analytics dashboard.

    Returns:
    - Processed emails count
    - Category breakdown
    - Recent emails
    - Response stats
    """
    try:
        from app.analytics import Analytics

        analytics = Analytics(settings.database_url)

        # Get stats
        daily = analytics.get_daily_stats()
        weekly = analytics.get_weekly_stats()  # Returns list of daily stats
        labels = analytics.get_top_labels(days=7)

        # Calculate weekly totals from list of daily stats
        weekly_total = sum(day.get("total_emails", 0) for day in weekly) if weekly else 0
        weekly_auto_replies = sum(day.get("auto_replies", 0) for day in weekly) if weekly else 0

        return {
            "summary": {
                "processed_today": daily.get("total_emails", 0),
                "processed_week": weekly_total,
                "auto_replied_today": daily.get("auto_replies", 0),
                "auto_replied_week": weekly_auto_replies,
            },
            "categories": labels if isinstance(labels, list) else [],
            "response_rate": daily.get("success_rate", 0),
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/emails/recent")
async def get_recent_emails(limit: int = 20, settings: Settings = Depends(get_settings)):
    """
    Get recent processed emails for the email dashboard tab.

    Returns list of recent emails with:
    - From address
    - Subject
    - Category/label
    - Date processed
    - Auto-reply status
    - Preview text
    """
    try:
        from app.analytics import Analytics
        from datetime import datetime

        analytics = Analytics(settings.database_url)

        # Query recent email metrics from database
        from app.analytics import EmailMetric

        recent = analytics.session.query(EmailMetric)\
            .order_by(EmailMetric.timestamp.desc())\
            .limit(limit)\
            .all()

        emails = []
        for email in recent:
            emails.append({
                "from": email.customer_email,
                "subject": email.subject,
                "category": email.label,
                "date": email.timestamp.isoformat() if email.timestamp else None,
                "auto_replied": email.auto_reply_sent,
                "ai_provider": email.ai_provider,
                "response_mode": email.response_mode,
                "processing_time_ms": email.processing_time_ms,
                "success": email.success,
                "error": email.error_message if not email.success else None
            })

        return {
            "success": True,
            "emails": emails,
            "total": len(emails)
        }

    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
            "emails": []
        }


@app.get("/api/dashboard/shopify")
async def get_dashboard_shopify(settings: Settings = Depends(get_settings)):
    """
    Shopify integration dashboard.

    Returns:
    - Store info
    - Recent orders
    - Revenue stats
    - Product count
    """
    try:
        # Check if Shopify is configured
        if not settings.SHOPIFY_STORE_DOMAIN:
            return {
                "connected": False,
                "message": "Shopify not configured. Set OUBONSHOP_SHOPIFY_STORE_DOMAIN and OUBONSHOP_SHOPIFY_ADMIN_TOKEN"
            }

        from ospra_os.integrations.shopify.client import ShopifyClient
        import requests

        # Get API token
        access_token = getattr(settings, "SHOPIFY_ADMIN_TOKEN", None) or getattr(settings, "SHOPIFY_API_TOKEN", None)

        if not access_token:
            return {
                "connected": False,
                "message": "Shopify API token not configured"
            }

        # Extract store name from domain (e.g., 'rxxj7d-1i.myshopify.com' -> 'rxxj7d-1i')
        store_domain = settings.SHOPIFY_STORE_DOMAIN
        store_name = store_domain.replace('.myshopify.com', '') if '.myshopify.com' in store_domain else store_domain

        client = ShopifyClient(
            store_name=store_name,
            access_token=access_token
        )

        # Get store info
        store_url = f"https://{settings.SHOPIFY_STORE_DOMAIN}/admin/api/{settings.SHOPIFY_API_VERSION}/shop.json"
        store_response = requests.get(store_url, headers=client.headers, timeout=10)

        if store_response.status_code != 200:
            return {
                "connected": False,
                "error": f"Failed to connect: HTTP {store_response.status_code}"
            }

        shop = store_response.json()["shop"]

        # Get recent orders
        orders_url = f"https://{settings.SHOPIFY_STORE_DOMAIN}/admin/api/{settings.SHOPIFY_API_VERSION}/orders.json?limit=10&status=any"
        orders_response = requests.get(orders_url, headers=client.headers, timeout=10)
        orders = orders_response.json().get("orders", []) if orders_response.status_code == 200 else []

        # Calculate revenue
        total_revenue = sum(float(order.get("total_price", 0)) for order in orders)

        return {
            "connected": True,
            "store": {
                "name": shop.get("name"),
                "email": shop.get("email"),
                "domain": shop.get("domain"),
                "currency": shop.get("currency"),
            },
            "orders": {
                "total_recent": len(orders),
                "total_revenue": round(total_revenue, 2),
                "recent_orders": [
                    {
                        "order_name": o.get("name"),
                        "total": float(o.get("total_price", 0)),
                        "status": o.get("financial_status"),
                        "created_at": o.get("created_at"),
                    }
                    for o in orders[:5]
                ]
            }
        }
    except Exception as e:
        return {
            "connected": False,
            "error": str(e)
        }


@app.get("/api/dashboard/api-status")
async def get_api_status(settings: Settings = Depends(get_settings)):
    """
    Check health of all API integrations.

    Returns status for:
    - Gmail
    - OpenAI/Anthropic
    - Reddit
    - Google Trends
    - Shopify
    - AliExpress
    """
    try:
        import os
        status_checks = []

        # Gmail
        gmail_configured = GmailClient is not None
        status_checks.append({
            "name": "Gmail API",
            "status": "connected" if gmail_configured else "not_configured",
            "health": "healthy" if gmail_configured else "unavailable",
        })

        # OpenAI - check both settings and env
        openai_configured = bool(settings.OPENAI_API_KEY) or bool(os.getenv('OPENAI_API_KEY'))
        status_checks.append({
            "name": "OpenAI API",
            "status": "connected" if openai_configured else "not_configured",
            "health": "healthy" if openai_configured else "unavailable",
        })

        # Claude (Anthropic) - check both CLAUDE_API_KEY and ANTHROPIC_API_KEY
        claude_configured = bool(settings.CLAUDE_API_KEY) or bool(os.getenv('ANTHROPIC_API_KEY')) or bool(os.getenv('CLAUDE_API_KEY'))
        status_checks.append({
            "name": "Claude API",
            "status": "connected" if claude_configured else "not_configured",
            "health": "healthy" if claude_configured else "unavailable",
        })

        # Reddit
        reddit_configured = bool(settings.REDDIT_CLIENT_ID) and bool(settings.REDDIT_SECRET)
        status_checks.append({
            "name": "Reddit API",
            "status": "connected" if reddit_configured else "not_configured",
            "health": "healthy" if reddit_configured else "unavailable",
        })

        # Google Trends (always available)
        status_checks.append({
            "name": "Google Trends",
            "status": "connected",
            "health": "healthy",
        })

        # Shopify - check multiple possible attribute names
        shopify_configured = bool(settings.SHOPIFY_STORE_DOMAIN) or bool(settings.SHOPIFY_STORE) or bool(settings.SHOPIFY_DOMAIN)
        status_checks.append({
            "name": "Shopify API",
            "status": "connected" if shopify_configured else "not_configured",
            "health": "healthy" if shopify_configured else "unavailable",
        })

        # AliExpress - check APP_KEY not API_KEY
        aliexpress_configured = bool(getattr(settings, 'ALIEXPRESS_API_KEY', None)) or bool(os.getenv('ALIEXPRESS_APP_KEY'))
        status_checks.append({
            "name": "AliExpress API",
            "status": "connected" if aliexpress_configured else "not_configured",
            "health": "healthy" if aliexpress_configured else "unavailable",
        })

        # Calculate overall health
        healthy_count = sum(1 for s in status_checks if s["health"] == "healthy")
        total_count = len(status_checks)

        return {
            "overall_health": "healthy" if healthy_count >= 4 else "degraded",
            "healthy_apis": healthy_count,
            "total_apis": total_count,
            "apis": status_checks,
        }
    except Exception as e:
        import traceback
        return {
            "error": str(e),
            "traceback": traceback.format_exc(),
            "overall_health": "error"
        }


@app.get("/admin/dashboard/data")
async def get_admin_dashboard_data(settings: Settings = Depends(get_settings)):
    """
    Unified endpoint for the premium dashboard v2.

    Returns complete dashboard data including:
    - Overview stats (products, emails, API connections)
    - Email analytics
    - Product discoveries
    - System health
    """
    try:
        from app.analytics import Analytics

        analytics = Analytics(settings.database_url)

        # Get email stats
        daily_stats = analytics.get_daily_stats()
        weekly_stats = analytics.get_weekly_stats()

        # Count active API connections
        active_apis = {
            "gmail": GmailClient is not None,
            "anthropic": settings.ANTHROPIC_API_KEY is not None,
            "aliexpress": settings.ALIEXPRESS_APP_KEY is not None,
            "shopify": settings.SHOPIFY_STORE is not None,
        }

        active_count = sum(1 for v in active_apis.values() if v)

        # Calculate system health
        system_health = "healthy" if active_count >= 2 else "degraded"

        return {
            "success": True,
            "overview": {
                "total_products": 0,  # Will be updated when products are discovered
                "avg_score": 0.0,
                "avg_profit": 0.0,
                "high_priority": 0,
                "emails_processed_today": daily_stats.get("total_processed", 0),
                "emails_processed_week": weekly_stats.get("total_processed", 0),
                "active_apis": active_count,
                "total_apis": len(active_apis),
                "system_health": system_health,
            },
            "email_stats": {
                "processed_today": daily_stats.get("total_processed", 0),
                "processed_week": weekly_stats.get("total_processed", 0),
                "auto_replied_today": daily_stats.get("auto_replied", 0),
                "auto_replied_week": weekly_stats.get("auto_replied", 0),
                "response_rate": daily_stats.get("auto_reply_rate", 0),
            },
            "products": [],  # Products will come from /api/intelligence/discover
            "api_status": active_apis,
            "timestamp": "2025-10-29",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "overview": {
                "total_products": 0,
                "system_health": "error"
            }
        }


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
        import traceback
        return {
            "error": str(e),
            "traceback": traceback.format_exc(),
            "niche": niche,
            "total_found": 0,
        }


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
        import traceback
        return {
            "error": str(e),
            "traceback": traceback.format_exc(),
            "product_name": product_name,
        }


@app.get("/api/debug/reddit")
async def debug_reddit(settings: Settings = Depends(get_settings)):
    """Debug endpoint to check Reddit API configuration - matches production flow exactly."""
    from ospra_os.product_research.connectors.social.reddit import RedditConnector
    import traceback

    reddit = RedditConnector(
        client_id=settings.REDDIT_CLIENT_ID,
        client_secret=settings.REDDIT_SECRET
    )

    result = {
        "reddit_configured": reddit.is_available(),
        "client_id": settings.REDDIT_CLIENT_ID[:10] + "..." if settings.REDDIT_CLIENT_ID else None,
        "client_secret_configured": bool(settings.REDDIT_SECRET),
        "tests": []
    }

    # Test 1: Try "week" time filter (matches production)
    try:
        products_week = await reddit.get_subreddit_products(
            subreddit="smarthome",
            time_filter="week",  # MATCHES PRODUCTION
            limit=25  # MATCHES PRODUCTION
        )
        result["tests"].append({
            "test": "smarthome (week, limit=25)",
            "success": True,
            "products_found": len(products_week),
            "sample_product": products_week[0].to_dict() if products_week else None
        })
    except Exception as e:
        result["tests"].append({
            "test": "smarthome (week, limit=25)",
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        })

    # Test 2: Try "month" time filter
    try:
        products_month = await reddit.get_subreddit_products(
            subreddit="smarthome",
            time_filter="month",
            limit=25
        )
        result["tests"].append({
            "test": "smarthome (month, limit=25)",
            "success": True,
            "products_found": len(products_month),
            "sample_product": products_month[0].to_dict() if products_month else None
        })
    except Exception as e:
        result["tests"].append({
            "test": "smarthome (month, limit=25)",
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        })

    # Test 3: Try different subreddit
    try:
        products_shutup = await reddit.get_subreddit_products(
            subreddit="shutupandtakemymoney",
            time_filter="week",
            limit=25
        )
        result["tests"].append({
            "test": "shutupandtakemymoney (week, limit=25)",
            "success": True,
            "products_found": len(products_shutup),
            "sample_product": products_shutup[0].to_dict() if products_shutup else None
        })
    except Exception as e:
        result["tests"].append({
            "test": "shutupandtakemymoney (week, limit=25)",
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        })

    return result


@app.get("/api/debug/trends-test")
async def debug_trends_test():
    """Simple test of Google Trends discovery."""
    from ospra_os.product_research.multi_source_discovery import MultiSourceDiscovery

    try:
        discovery = MultiSourceDiscovery()

        # Test single niche with low threshold
        niche_products = await discovery.discover_all_niches(min_score=40, max_per_niche=2)

        # Get stats
        stats = discovery.get_stats(niche_products)
        top = discovery.get_top_products_overall(niche_products, limit=5)

        return {
            "success": True,
            "test": "Google Trends Discovery",
            "products_found": stats["total_products"],
            "niches_with_products": stats["niches_with_products"],
            "top_5": [
                {
                    "name": p["name"],
                    "score": p["score"],
                    "trend_score": p["trend_score"],
                    "priority": p["priority"]
                }
                for p in top
            ],
            "stats": stats
        }
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


@app.get("/api/debug/reddit-connector-logs")
async def debug_reddit_connector_logs(settings: Settings = Depends(get_settings)):
    """Test Reddit connector and capture logs."""
    import io
    import sys
    from ospra_os.product_research.connectors.social.reddit import RedditConnector

    # Capture stdout
    captured_output = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = captured_output

    try:
        reddit = RedditConnector()
        products = await reddit.get_subreddit_products("smarthome", "week", 5)

        # Restore stdout
        sys.stdout = old_stdout
        logs = captured_output.getvalue()

        return {
            "success": True,
            "products_found": len(products),
            "sample_products": [
                {
                    "name": p.name,
                    "score": p.social_mentions,
                    "comments": p.social_engagement,
                    "url": p.url
                }
                for p in products[:3]
            ],
            "logs": logs
        }
    except Exception as e:
        sys.stdout = old_stdout
        logs = captured_output.getvalue()
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
            "logs": logs
        }


@app.get("/api/debug/reddit-json")
async def debug_reddit_json():
    """Test Reddit JSON API directly (no credentials needed)."""
    import aiohttp

    url = "https://www.reddit.com/r/smarthome/top.json"
    params = {"t": "week", "limit": 5}
    headers = {"User-Agent": "web:OspraOS:v1.0 (by /u/OspraBot)"}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers) as response:
            if response.status != 200:
                return {"error": f"HTTP {response.status}"}

            data = await response.json()
            posts = data.get("data", {}).get("children", [])

            results = []
            for post_wrapper in posts:
                post = post_wrapper.get("data", {})
                results.append({
                    "title": post.get("title", ""),
                    "score": post.get("score", 0),
                    "num_comments": post.get("num_comments", 0),
                    "stickied": post.get("stickied", False),
                    "removed_by_category": post.get("removed_by_category"),
                    "selftext": post.get("selftext", "")[:100] if post.get("selftext") else None
                })

            return {
                "total_posts": len(posts),
                "posts": results
            }


@app.get("/api/debug/reddit-raw")
async def debug_reddit_raw(settings: Settings = Depends(get_settings)):
    """Debug endpoint to see raw Reddit posts BEFORE filtering."""
    try:
        import praw
        import asyncio
    except ImportError:
        return {"error": "praw not installed"}

    if not settings.REDDIT_CLIENT_ID or not settings.REDDIT_SECRET:
        return {"error": "Reddit credentials not configured"}

    # Initialize Reddit in read-only mode (no user auth needed)
    reddit = praw.Reddit(
        client_id=settings.REDDIT_CLIENT_ID,
        client_secret=settings.REDDIT_SECRET,
        user_agent="web:OspraOS:v1.0 (by /u/OspraBot)",
        check_for_async=False
    )
    reddit.read_only = True

    result = {
        "reddit_auth": "success",
        "subreddit_tests": []
    }

    # Test r/smarthome
    try:
        subreddit = reddit.subreddit("smarthome")

        # Get raw top posts
        loop = asyncio.get_event_loop()
        top_posts = await loop.run_in_executor(
            None,
            lambda: list(subreddit.top(time_filter="week", limit=10))
        )

        raw_posts = []
        for post in top_posts:
            raw_posts.append({
                "title": post.title,
                "score": post.score,
                "num_comments": post.num_comments,
                "upvote_ratio": post.upvote_ratio,
                "stickied": post.stickied,
                "removed_by_category": post.removed_by_category,
                "selftext_preview": post.selftext[:100] if post.selftext else None,
                "url": f"https://reddit.com{post.permalink}"
            })

        result["subreddit_tests"].append({
            "subreddit": "smarthome",
            "time_filter": "week",
            "total_posts_fetched": len(top_posts),
            "posts": raw_posts,
            "filtered_count": {
                "stickied": sum(1 for p in top_posts if p.stickied),
                "removed": sum(1 for p in top_posts if p.removed_by_category),
                "after_filters": len([p for p in top_posts if not p.stickied and not p.removed_by_category])
            }
        })
    except Exception as e:
        import traceback
        result["subreddit_tests"].append({
            "subreddit": "smarthome",
            "error": str(e),
            "traceback": traceback.format_exc()
        })

    # Test r/shutupandtakemymoney
    try:
        subreddit = reddit.subreddit("shutupandtakemymoney")

        loop = asyncio.get_event_loop()
        top_posts = await loop.run_in_executor(
            None,
            lambda: list(subreddit.top(time_filter="week", limit=10))
        )

        raw_posts = []
        for post in top_posts:
            raw_posts.append({
                "title": post.title,
                "score": post.score,
                "num_comments": post.num_comments,
                "stickied": post.stickied,
                "removed_by_category": post.removed_by_category
            })

        result["subreddit_tests"].append({
            "subreddit": "shutupandtakemymoney",
            "time_filter": "week",
            "total_posts_fetched": len(top_posts),
            "posts": raw_posts,
            "filtered_count": {
                "stickied": sum(1 for p in top_posts if p.stickied),
                "removed": sum(1 for p in top_posts if p.removed_by_category),
                "after_filters": len([p for p in top_posts if not p.stickied and not p.removed_by_category])
            }
        })
    except Exception as e:
        import traceback
        result["subreddit_tests"].append({
            "subreddit": "shutupandtakemymoney",
            "error": str(e),
            "traceback": traceback.format_exc()
        })

    return result


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
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
            "total_products": 0,
            "niches_discovered": 0,
        }


# ---------------------------------------------------------------
# Analytics API Endpoints (Legacy)
# ---------------------------------------------------------------
@app.get("/analytics/daily")
def analytics_daily(settings: Settings = Depends(get_settings)):
    """Get today's email processing statistics."""
    from app.analytics import Analytics
    analytics = Analytics(settings.database_url)
    return analytics.get_daily_stats()

@app.get("/analytics/weekly")
def analytics_weekly(settings: Settings = Depends(get_settings)):
    """Get last 7 days of statistics."""
    from app.analytics import Analytics
    analytics = Analytics(settings.database_url)
    return analytics.get_weekly_stats()

@app.get("/analytics/costs")
def analytics_costs(days: int = 30, settings: Settings = Depends(get_settings)):
    """Get AI cost breakdown for the last N days."""
    from app.analytics import Analytics
    analytics = Analytics(settings.database_url)
    return analytics.get_cost_breakdown(days=days)

@app.get("/analytics/labels")
def analytics_labels(days: int = 7, settings: Settings = Depends(get_settings)):
    """Get most common email categories."""
    from app.analytics import Analytics
    analytics = Analytics(settings.database_url)
    return analytics.get_top_labels(days=days)

@app.get("/analytics/cache-stats")
def cache_stats():
    """Get response cache statistics."""
    from app.response_cache import get_cache_stats
    return get_cache_stats()

# (optional) quick route list for sanity checks
@app.get("/debug/routes", include_in_schema=False)
def debug_routes():
    return sorted([r.path for r in app.routes])

@app.get("/debug/scheduler", include_in_schema=False)
def debug_scheduler():
    """Check scheduler status and run a manual email check."""
    try:
        from app.scheduler import check_emails_job
        # Try to run the job manually
        check_emails_job()
        return {"status": "ok", "message": "Email check job executed"}
    except Exception as e:
        import traceback
        return {
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc()
        }

@app.get("/debug/check-inbox", include_in_schema=False)
def debug_check_inbox(settings: Settings = Depends(get_settings)):
    """Show what emails are in inbox and would be processed."""
    try:
        from app.gmail_client import GmailClient
        gc = GmailClient(settings)
        svc = gc.service()

        # Same query as email processor
        query = 'in:inbox (is:unread OR "order" OR "package" OR "delivery" OR "tracking" OR "shipment" OR "refund" OR "return" OR "damaged" OR "broken")'

        result = svc.users().messages().list(
            userId="me",
            q=query,
            maxResults=10
        ).execute()

        messages = result.get("messages", [])

        email_list = []
        for msg in messages[:5]:  # Only process first 5 for debug
            full_msg = svc.users().messages().get(userId="me", id=msg["id"], format="full").execute()
            headers = {h["name"].lower(): h["value"] for h in full_msg.get("payload", {}).get("headers", [])}

            email_list.append({
                "id": msg["id"],
                "subject": headers.get("subject", ""),
                "from": headers.get("from", ""),
                "date": headers.get("date", ""),
            })

        return {
            "status": "ok",
            "query": query,
            "total_found": len(messages),
            "sample_emails": email_list
        }
    except Exception as e:
        import traceback
        return {
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc()
        }


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
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
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
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
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
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


# ---------------------------------------------------------------
# Product Intelligence API Endpoints
# ---------------------------------------------------------------
class DiscoverRequest(BaseModel):
    niches: Optional[List[str]] = None
    max_per_niche: int = 5


@app.post("/api/intelligence/saturation")
async def check_product_saturation(product_name: str):
    """
    [TARGET] PRODUCT SATURATION CHECKER

    Analyze market saturation using Amazon data to avoid deploying
    products that are already oversaturated.

    Uses Amazon Bestsellers scraper to check:
    - Seller count (competition level)
    - Review velocity (market maturity)
    - Best Seller Rank (BSR) trends
    - Price competition

    Returns:
        {
            "saturation_score": float (0-100),
            "competitor_count": int,
            "review_velocity": float (reviews/day),
            "bsr": int,
            "bsr_trend": "rising" | "stable" | "falling",
            "price_range": {"min": float, "max": float},
            "recommendation": "deploy" | "caution" | "skip",
            "reasons": List[str],
            "opportunity_score": float (0-100)
        }

    Saturation Scores:
    - 0-30: [SUCCESS] DEPLOY - Blue ocean (low competition)
    - 31-60: [WARNING]  CAUTION - Moderate competition
    - 61-100: [ERROR] SKIP - Saturated (high competition)
    """
    try:
        from ospra_os.intelligence.saturation_scorer import calculate_saturation_score

        result = await calculate_saturation_score(product_name)

        return {
            "success": True,
            "product_name": product_name,
            **result
        }

    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


@app.post("/api/intelligence/discover")
async def discover_winning_products_unified(request: DiscoverRequest):
    """
    [START] UNIFIED PRODUCT DISCOVERY - One endpoint for everything!

    Combines ALL data sources:
    - Google Trends → Trending keywords (buying intent)
    - Amazon (Apify) → Research ONLY (velocity, reviews, images) - NO dropshipping!
    - AliExpress (Apify) → ACTUAL dropship URLs (supplier links)
    - TikTok (Apify) → Viral scores
    - Reddit (Apify) → Sentiment analysis

    [WARNING] IMPORTANT: Amazon data is for RESEARCH ONLY!
    - Use Amazon for velocity, reviews, and market validation
    - DO NOT dropship from Amazon (violates TOS, causes account bans)
    - Always use AliExpress URLs for actual dropshipping

    Returns enriched products with:
    - Amazon research data (velocity, reviews, bestseller rank)
    - AliExpress dropship URLs (actual supplier product links)
    - TikTok viral scores
    - Reddit sentiment
    - Final BUY/SKIP/CONSIDER recommendation
    - Profit calculations
    - Priority scores
    """
    try:
        import asyncio
        import hashlib
        from datetime import datetime
        from ospra_os.product_research.multi_source_discovery import MultiSourceDiscovery

        discovery = MultiSourceDiscovery()

        # Determine niches to search
        niches_to_search = request.niches or ["smart_lighting", "home_security", "cleaning_gadgets"]

        print(f"\n[START] UNIFIED QUAD-SOURCE DISCOVERY API Request:")
        print(f"   Niches: {niches_to_search}")
        print(f"   Max per niche: {request.max_per_niche}")
        print(f"   PRIMARY Sources: TikTok Shop + Amazon Bestsellers + Shopify Competitors + Google Trends")
        print(f"   SECONDARY Sources: AliExpress (dropship URLs) + Reddit (sentiment)")

        # Call unified discovery method with timeout
        try:
            products = await asyncio.wait_for(
                discovery.discover_unified(
                    niches=niches_to_search,
                    max_per_niche=request.max_per_niche,
                    min_trend_score=70.0,
                    use_tiktok_shop=True,  # PRIMARY SOURCE #1
                    use_amazon_bestsellers=True,  # PRIMARY SOURCE #2
                    use_shopify_competitors=True  # PRIMARY SOURCE #3
                    # Google Trends is always PRIMARY SOURCE #4 (no flag needed)
                ),
                timeout=600.0  # 10 minutes for full Apify scraping
            )
        except asyncio.TimeoutError:
            return {
                'success': False,
                'error': 'Discovery timeout after 10 minutes. Apify scrapers may be slow.',
                'timeout': True
            }

        print(f"\n[SUCCESS] Unified discovery complete: {len(products)} total products")

        # Helper functions for platform scoring and badges
        def _generate_platform_badges(product):
            """Generate visual badges for frontend display with brand logos"""
            badges = []

            # TikTok Shop Badge
            tiktok_sales = product.get('tiktok_sales', 0)
            if tiktok_sales > 5000:
                badges.append({
                    "platform": "tiktok",
                    "label": "Hot on TikTok",
                    "level": "hot",
                    "emoji": "[HOT]",
                    "color": "#FF0050",
                    "logo": {
                        "cdn": "https://cdn.simpleicons.org/tiktok/FF0050",
                        "local": "/assets/logos/tiktok.svg",
                        "icon_library": "FaTiktok",  # For react-icons
                        "brand_color": "#000000"
                    },
                    "metric": f"{tiktok_sales:,} sales"
                })
            elif tiktok_sales > 1000:
                badges.append({
                    "platform": "tiktok",
                    "label": "Trending on TikTok",
                    "level": "trending",
                    "emoji": "[TREND]",
                    "color": "#00F2EA",
                    "logo": {
                        "cdn": "https://cdn.simpleicons.org/tiktok/00F2EA",
                        "local": "/assets/logos/tiktok.svg",
                        "icon_library": "FaTiktok",
                        "brand_color": "#000000"
                    },
                    "metric": f"{tiktok_sales:,} sales"
                })
            elif tiktok_sales > 0:
                badges.append({
                    "platform": "tiktok",
                    "label": "On TikTok",
                    "level": "active",
                    "emoji": "[STAR]",
                    "color": "#000000",
                    "logo": {
                        "cdn": "https://cdn.simpleicons.org/tiktok/000000",
                        "local": "/assets/logos/tiktok.svg",
                        "icon_library": "FaTiktok",
                        "brand_color": "#000000"
                    },
                    "metric": f"{tiktok_sales:,} sales"
                })

            # Amazon Bestseller Badge
            if product.get('amazon_bestseller'):
                rank = product.get('amazon_rank', 999)
                reviews = product.get('amazon_reviews', 0)
                if rank <= 10:
                    badges.append({
                        "platform": "amazon",
                        "label": "Amazon Top 10",
                        "level": "top",
                        "emoji": "",
                        "color": "#FF9900",
                        "logo": {
                            "cdn": "https://cdn.simpleicons.org/amazon/FF9900",
                            "local": "/assets/logos/amazon.svg",
                            "icon_library": "FaAmazon",
                            "brand_color": "#FF9900"
                        },
                        "metric": f"Rank #{rank}"
                    })
                elif rank <= 50:
                    badges.append({
                        "platform": "amazon",
                        "label": "Amazon Bestseller",
                        "level": "bestseller",
                        "emoji": "[TOP]",
                        "color": "#FF9900",
                        "logo": {
                            "cdn": "https://cdn.simpleicons.org/amazon/FF9900",
                            "local": "/assets/logos/amazon.svg",
                            "icon_library": "FaAmazon",
                            "brand_color": "#FF9900"
                        },
                        "metric": f"Rank #{rank}"
                    })
                elif rank <= 100:
                    badges.append({
                        "platform": "amazon",
                        "label": "Amazon Top 100",
                        "level": "popular",
                        "emoji": "[STATS]",
                        "color": "#FF9900",
                        "logo": {
                            "cdn": "https://cdn.simpleicons.org/amazon/FF9900",
                            "local": "/assets/logos/amazon.svg",
                            "icon_library": "FaAmazon",
                            "brand_color": "#FF9900"
                        },
                        "metric": f"Rank #{rank}"
                    })

            # Shopify Competitor Badge
            if product.get('shopify_competitor'):
                badges.append({
                    "platform": "shopify",
                    "label": "Proven Winner",
                    "level": "proven",
                    "emoji": "",
                    "color": "#96BF48",
                    "logo": {
                        "cdn": "https://cdn.simpleicons.org/shopify/96BF48",
                        "local": "/assets/logos/shopify.svg",
                        "icon_library": "FaShopify",
                        "brand_color": "#96BF48"
                    },
                    "metric": "In competitor stores"
                })

            # Google Trends Badge
            trend_score = product.get('trend_score', 0)
            if trend_score >= 80:
                badges.append({
                    "platform": "google",
                    "label": "Trending",
                    "level": "hot",
                    "emoji": "[START]",
                    "color": "#4285F4",
                    "logo": {
                        "cdn": "https://cdn.simpleicons.org/google/4285F4",
                        "local": "/assets/logos/google.svg",
                        "icon_library": "FaGoogle",
                        "brand_color": "#4285F4"
                    },
                    "metric": f"{trend_score:.0f}% trend score"
                })
            elif trend_score >= 70:
                badges.append({
                    "platform": "google",
                    "label": "Rising",
                    "level": "rising",
                    "emoji": "[TREND]",
                    "color": "#4285F4",
                    "logo": {
                        "cdn": "https://cdn.simpleicons.org/google/4285F4",
                        "local": "/assets/logos/google.svg",
                        "icon_library": "FaGoogle",
                        "brand_color": "#4285F4"
                    },
                    "metric": f"{trend_score:.0f}% trend score"
                })

            # Multi-Source Badge (MOST IMPORTANT!)
            source_count = product.get('source_count', 0)
            if source_count >= 4:
                badges.insert(0, {
                    "platform": "multi",
                    "label": "4 SOURCES!",
                    "level": "jackpot",
                    "emoji": "[TARGET]",
                    "color": "#FFD700",
                    "logo": {
                        "cdn": None,  # Custom icon
                        "local": "/assets/logos/multi-source.svg",
                        "icon_library": "FaCheckDouble",
                        "brand_color": "#FFD700"
                    },
                    "metric": "Maximum confidence",
                    "sources": product.get('primary_sources', [])
                })
            elif source_count == 3:
                badges.insert(0, {
                    "platform": "multi",
                    "label": "3 Sources",
                    "level": "strong",
                    "emoji": "[HOT]",
                    "color": "#FF6B35",
                    "logo": {
                        "cdn": None,
                        "local": "/assets/logos/multi-source.svg",
                        "icon_library": "FaCheckDouble",
                        "brand_color": "#FF6B35"
                    },
                    "metric": "High confidence",
                    "sources": product.get('primary_sources', [])
                })
            elif source_count == 2:
                badges.insert(0, {
                    "platform": "multi",
                    "label": "2 Sources",
                    "level": "good",
                    "emoji": "[STAR]",
                    "color": "#4ECDC4",
                    "logo": {
                        "cdn": None,
                        "local": "/assets/logos/multi-source.svg",
                        "icon_library": "FaCheck",
                        "brand_color": "#4ECDC4"
                    },
                    "metric": "Good confidence",
                    "sources": product.get('primary_sources', [])
                })

            return badges

        def _calculate_tiktok_score(product):
            """Calculate dynamic TikTok score (0-100)"""
            sales = product.get('tiktok_sales', 0)
            if sales == 0:
                return 0
            # 10K+ sales = 100 points
            return round(min((sales / 10000) * 100, 100), 1)

        def _calculate_amazon_score(product):
            """Calculate dynamic Amazon score (0-100)"""
            if not (product.get('amazon_bestseller') or product.get('amazon_reference')):
                return 0
            rank = product.get('amazon_rank', 999)
            # Lower rank = higher score (rank 1 = 100 points, rank 100 = 0 points)
            return round(max(0, 100 - rank), 1)

        def _calculate_shopify_score(product):
            """Calculate Shopify score (0-100)"""
            if product.get('shopify_competitor'):
                return 100  # Binary: either it's proven (100) or not (0)
            return 0

        def _calculate_multi_source_bonus(product):
            """Calculate multi-source bonus score"""
            source_count = product.get('source_count', 0)
            if source_count >= 4:
                return 20
            elif source_count == 3:
                return 15
            elif source_count == 2:
                return 10
            return 0

        # Transform to frontend-expected format
        all_products = []
        for product in products:
            # Generate unique ID
            product_id = hashlib.md5(
                f"{product.get('name', 'unknown')}{product.get('niche', 'unknown')}".encode()
            ).hexdigest()[:12]

            transformed = {
                "id": product_id,
                "name": product.get('name', 'Unknown Product'),
                "niche": product.get('niche', 'unknown'),
                "category": product.get('niche', 'unknown'),

                # Pricing (from AliExpress)
                "cost": product.get('cost', product.get('aliexpress_price', 0)),
                "price": product.get('price', 0),
                "profit": product.get('profit', 0),
                "estimated_profit": product.get('profit', product.get('estimated_profit', 0)),  # Frontend expects this name
                "profit_margin": product.get('profit_margin', 0),

                # Scores
                "score": round(product.get('final_score', 0), 1),
                "trend_score": round(product.get('trend_score', 0), 1),
                "final_score": round(product.get('final_score', 0), 1),
                "velocity_score": round(product.get('velocity_score', product.get('trend_score', 0)), 1),  # Velocity indicator

                # Product metrics (for frontend display)
                "orders": product.get('orders', product.get('aliexpress_orders', product.get('amazon_orders_estimate', product.get('tiktok_sales', 0)))),
                "rating": product.get('rating', product.get('aliexpress_rating', product.get('amazon_rating', product.get('tiktok_rating', 0)))),

                # Multi-Source Discovery Tracking
                "source_count": product.get('source_count', 0),  # How many primary sources found this
                "primary_sources": product.get('primary_sources', []),  # Which primary sources found it
                "source": product.get('source', 'UNIFIED_DISCOVERY'),

                # Platform Badges for Visualization (frontend can display these as badges/tags)
                "platform_badges": _generate_platform_badges(product),

                # Individual Platform Scores (for detailed breakdown)
                "platform_scores": {
                    "tiktok_shop_score": _calculate_tiktok_score(product),
                    "amazon_score": _calculate_amazon_score(product),
                    "shopify_score": _calculate_shopify_score(product),
                    "google_trends_score": round(product.get('trend_score', 0), 1),
                    "multi_source_bonus": _calculate_multi_source_bonus(product),
                },

                # AliExpress (DROPSHIPPING SOURCE)
                "aliexpress_url": product.get('aliexpress_url', ''),  # ACTUAL dropship link!
                "aliexpress_orders": product.get('aliexpress_orders', 0),
                "aliexpress_rating": product.get('aliexpress_rating', 0),
                "aliexpress_supplier": product.get('aliexpress_supplier', 'Unknown'),
                "aliexpress_shipping_cost": product.get('aliexpress_shipping_cost', 0),
                "aliexpress_free_shipping": product.get('aliexpress_free_shipping', False),

                # Amazon (RESEARCH ONLY - NOT for dropshipping!)
                "amazon_reference": product.get('amazon_reference', False),
                "amazon_bestseller": product.get('amazon_bestseller', False),  # Found in bestsellers list!
                "amazon_reference_url": product.get('amazon_reference_url', ''),  # For research only!
                "amazon_rating": product.get('amazon_rating', 0),
                "amazon_reviews": product.get('amazon_reviews', 0),
                "amazon_rank": product.get('amazon_rank', 999),
                "amazon_orders_estimate": product.get('amazon_orders_estimate', 0),

                # Shopify Competitors
                "shopify_competitor": product.get('shopify_competitor', False),  # Found in competitor stores!
                "shopify_price": product.get('shopify_price', 0),
                "shopify_store_url": product.get('shopify_store_url', ''),

                # Images (prefer TikTok, then AliExpress, fallback to Amazon)
                "image_url": product.get('image_url') or (product.get('aliexpress_images', [None])[0] if product.get('aliexpress_images') else product.get('amazon_image', '')),
                "images": product.get('aliexpress_images', []),

                # TikTok Shop (ACTUAL SALES DATA!)
                "tiktok_shop_sales": product.get('tiktok_sales', 0),  # REAL sales count!
                "tiktok_shop_price": product.get('tiktok_price', 0),
                "tiktok_shop_rating": product.get('tiktok_rating', 0),
                "tiktok_shop_reviews": product.get('tiktok_reviews', 0),
                "tiktok_shop_likes": product.get('tiktok_likes', 0),
                "tiktok_shop_comments": product.get('tiktok_comments', 0),
                "tiktok_shop_shares": product.get('tiktok_shares', 0),
                "tiktok_shop_viral_score": product.get('tiktok_viral_score', 0),
                "tiktok_shop_url": product.get('tiktok_url', ''),

                # Social proof
                "tiktok_viral": product.get('tiktok_viral', False) or product.get('tiktok_sales', 0) > 0,
                "tiktok_views": product.get('tiktok_views', 0),
                "reddit_sentiment": product.get('reddit_sentiment', 'unknown'),
                "reddit_mentions": product.get('reddit_mentions', 0),

                # Recommendation
                "priority": product.get('priority', 'LOW'),
                "recommendation": product.get('recommendation', 'SKIP'),

                # Metadata
                "source": "UNIFIED_APIFY_DISCOVERY",
                "keyword": product.get('keyword', ''),
                "tags": [
                    product.get('niche', 'unknown'),
                    f"score_{int(product.get('final_score', 0))}",
                    product.get('priority', 'LOW').lower()
                ]
            }

            all_products.append(transformed)

        # Sort by final score
        all_products.sort(key=lambda x: x['final_score'], reverse=True)

        # No fallback - return empty if no products found
        if len(all_products) == 0:
            print("WARNING: No products discovered - APIs may be unavailable or returned no results")

        return {
            'success': True,
            'products': all_products,
            'count': len(all_products),
            'data_sources': {
                'google_trends': True,
                'amazon_research': discovery.amazon_bestsellers is not None,
                'aliexpress_dropship': discovery.aliexpress_scraper is not None,
                'tiktok': discovery.tiktok is not None,
                'reddit': discovery.reddit is not None
            },
            'niches_searched': niches_to_search,
            'timestamp': datetime.utcnow().isoformat(),
            'note': 'Amazon data is for RESEARCH ONLY - Use AliExpress URLs for dropshipping!'
        }

    except Exception as e:
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Unified discovery failed: {e}\n{traceback.format_exc()}")

        return {
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc(),
            'products': [],
            'count': 0
        }


@app.post("/api/intelligence/discover-enriched")
async def discover_products_enriched_endpoint(request: Dict):
    """
    [WARNING] DEPRECATED - Use /api/intelligence/discover instead!

    This endpoint has been merged into the unified discovery endpoint.
    The new endpoint combines ALL data sources in one call.

    This endpoint now redirects to the unified discovery for backward compatibility.
    """
    print("[WARNING]  /api/intelligence/discover-enriched is deprecated!")
    print("   Redirecting to unified /api/intelligence/discover endpoint...")

    # Convert Dict request to DiscoverRequest format
    discover_request = DiscoverRequest(
        niches=request.get("niches"),
        max_per_niche=request.get("max_per_niche", 5)
    )

    # Call the unified endpoint
    return await discover_winning_products_unified(discover_request)


@app.get("/api/products/test-discovery")
async def test_product_discovery(
    niche: str = "smart_home",
    max_products: int = 10
):
    """Test endpoint to verify product discovery works"""
    try:
        from ospra_os.intelligence.product_intelligence import ProductIntelligenceEngine
        from datetime import datetime

        print(f"[TEST] Testing discovery for niche: {niche}")

        engine = ProductIntelligenceEngine()
        products = await engine.discover_winning_products(
            niches=[niche],
            max_per_niche=max_products
        )

        print(f"[SUCCESS] Found {len(products)} products")

        return {
            "success": True,
            "products": products,
            "count": len(products),
            "niche": niche,
            "debug": {
                "timestamp": datetime.utcnow().isoformat(),
                "engine_type": str(type(engine))
            }
        }
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"[ERROR] Discovery error: {e}")
        print(error_trace)

        return {
            "success": False,
            "error": str(e),
            "traceback": error_trace,
            "products": [],
            "count": 0
        }


@app.get("/api/intelligence/stats")
async def get_intelligence_stats():
    """Get intelligence engine statistics"""
    import os
    try:
        from ospra_os.scraping.proxy_manager import proxy_manager

        proxy_stats = proxy_manager.get_stats()

        return {
            'success': True,
            'stats': {
                'proxy_manager': proxy_stats,
                'apis_configured': {
                    'amazon': bool(os.getenv('AMAZON_ACCESS_KEY')),
                    'aliexpress': bool(os.getenv('ALIEXPRESS_APP_KEY')),
                    'instagram': bool(os.getenv('INSTAGRAM_ACCESS_TOKEN')),
                    'tiktok': bool(os.getenv('TIKTOK_API_KEY')),
                    'twitter': bool(os.getenv('TWITTER_BEARER_TOKEN')),
                    'claude': bool(os.getenv('ANTHROPIC_API_KEY')),
                    'scraper_api': bool(os.getenv('SCRAPERAPI_KEY'))
                }
            }
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


# ---------------------------------------------------------------
# Velocity Detection API Endpoints
# ---------------------------------------------------------------

@app.get("/api/velocity/stats")
async def get_velocity_stats(
    niche: Optional[str] = None,
    settings: Settings = Depends(get_settings)
):
    """
    Get velocity statistics by lifecycle phase

    Returns product counts and metrics for each phase:
    - discovery: Just found, minimal data
    - early_spike: Rapid growth, trending up
    - growth: Sustained momentum
    - maturity: Stable, high volume
    - decline: Decreasing interest
    """
    try:
        from ospra_os.intelligence.velocity_detector import VelocityDetector

        detector = VelocityDetector(settings.database_url)

        # Get products by phase
        stats = {
            "discovery": await detector.get_products_by_phase('discovery', niche, 5),
            "early_spike": await detector.get_products_by_phase('early_spike', niche, 5),
            "growth": await detector.get_products_by_phase('growth', niche, 5),
            "maturity": await detector.get_products_by_phase('maturity', niche, 5),
            "decline": await detector.get_products_by_phase('decline', niche, 5)
        }

        # Get overall velocity statistics
        velocity_stats = await detector.get_velocity_stats(niche)

        await detector.close()

        return {
            "success": True,
            "stats": stats,
            "velocity_overview": velocity_stats
        }

    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


@app.get("/api/velocity/tier-products")
async def get_tier_products(
    tier: str,
    niche: Optional[str] = None,
    limit: int = 20,
    settings: Settings = Depends(get_settings)
):
    """
    Get products appropriate for a specific subscription tier

    Tier Access Levels:
    - free: maturity only (proven products, 30+ days old)
    - starter: growth + maturity (14+ days old)
    - pro: early_spike + growth (7+ days old, fast movers)
    - enterprise: discovery + early_spike (fresh products, first access)
    """
    try:
        from ospra_os.intelligence.velocity_detector import VelocityDetector

        detector = VelocityDetector(settings.database_url)

        products = await detector.get_tier_appropriate_products(
            user_tier=tier,
            niche=niche,
            limit=limit
        )

        await detector.close()

        return {
            "success": True,
            "tier": tier,
            "niche": niche or "all",
            "count": len(products),
            "products": products,
            "tier_info": {
                "free": "Maturity phase only - proven products",
                "starter": "Growth + Maturity - established products",
                "pro": "Early Spike + Growth - fast movers",
                "enterprise": "Discovery + Early Spike - first access to new trends"
            }.get(tier.lower(), "Unknown tier")
        }

    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


@app.get("/api/velocity/phase/{phase}")
async def get_products_in_phase(
    phase: str,
    niche: Optional[str] = None,
    limit: int = 20,
    settings: Settings = Depends(get_settings)
):
    """
    Get products in a specific lifecycle phase

    Valid phases:
    - discovery: < 7 days old
    - early_spike: Rapid growth, < 21 days old
    - growth: Sustained growth, < 45 days old
    - maturity: Stable, proven products
    - decline: Decreasing interest
    """
    valid_phases = ['discovery', 'early_spike', 'growth', 'maturity', 'decline']

    if phase not in valid_phases:
        return {
            "success": False,
            "error": f"Invalid phase. Valid phases: {', '.join(valid_phases)}"
        }

    try:
        from ospra_os.intelligence.velocity_detector import VelocityDetector

        detector = VelocityDetector(settings.database_url)

        products = await detector.get_products_by_phase(phase, niche, limit)

        await detector.close()

        return {
            "success": True,
            "phase": phase,
            "niche": niche or "all",
            "count": len(products),
            "products": products
        }

    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


# ---------------------------------------------------------------
# Subscription Tier Management API
# ---------------------------------------------------------------

@app.get("/api/user/tier")
async def get_user_tier_info(
    user_id: int,
    settings: Settings = Depends(get_settings)
):
    """
    Get user's tier info and limits

    Returns current tier, features, limits, and expiry information
    """
    try:
        from ospra_os.subscription.tier_manager import TierManager

        manager = TierManager(settings.database_url)
        tier_info = await manager.get_tier_info(user_id)
        await manager.close()

        return {
            "success": True,
            **tier_info
        }
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


@app.post("/api/user/upgrade-tier")
async def upgrade_user_tier(
    user_id: int,
    new_tier: str,
    duration_days: int = 30,
    settings: Settings = Depends(get_settings)
):
    """
    Upgrade user tier

    For testing - would connect to payment processor in production

    Args:
        user_id: User ID to upgrade
        new_tier: Target tier ('free', 'starter', 'pro', 'elite')
        duration_days: Subscription duration in days (default: 30)
    """
    try:
        from ospra_os.subscription.tier_manager import TierManager

        manager = TierManager(settings.database_url)
        result = await manager.upgrade_tier(user_id, new_tier, duration_days)
        await manager.close()

        return result
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


@app.get("/api/tiers/comparison")
async def get_tier_comparison(settings: Settings = Depends(get_settings)):
    """
    Get comparison of all subscription tiers

    Returns features, pricing, and limits for all tiers
    """
    try:
        from ospra_os.subscription.tier_manager import TierManager

        manager = TierManager(settings.database_url)
        comparison = await manager.get_tier_comparison()
        await manager.close()

        return {
            "success": True,
            **comparison
        }
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


@app.post("/api/user/check-limit")
async def check_tier_limit(
    user_id: int,
    action: str,
    settings: Settings = Depends(get_settings)
):
    """
    Check if user can perform action based on tier limits

    Args:
        user_id: User ID
        action: Action to check ('add_store', 'get_products', etc.)

    Returns:
        allowed: boolean
        reason: string (if not allowed)
        upgrade_to: suggested tier (if not allowed)
    """
    try:
        from ospra_os.subscription.tier_manager import TierManager

        manager = TierManager(settings.database_url)
        result = await manager.check_tier_limits(user_id, action)
        await manager.close()

        return {
            "success": True,
            **result
        }
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


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
        import traceback
        logger.error(f"Marketing angle generation failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
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
        import traceback
        logger.error(f"Multiple angles generation failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
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
        import traceback
        logger.error(f"Failed to get available angles: {e}")
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


# =============================================================================
# SMART RECOMMENDATIONS - The Complete Anti-AutoDS System
# =============================================================================

@app.post("/api/recommendations/smart")
async def get_smart_recommendations(
    user_id: int,
    niches: Optional[List[str]] = None,
    max_products: int = 10,
    include_angles: bool = True,
    settings: Settings = Depends(get_settings)
):
    """
    Get personalized, anti-AutoDS product recommendations

    This endpoint brings together ALL differentiation features:
    - Tier-based access (early access to trending products)
    - Saturation protection (no oversaturated products)
    - Velocity-based timing (lifecycle phase filtering)
    - Unique marketing angles (prevent direct competition)

    Query Parameters:
        user_id: User ID to get recommendations for
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
        import traceback
        logger.error(f"Smart recommendations failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


@app.get("/api/recommendations/analytics/{user_id}")
async def get_recommendation_analytics(
    user_id: int,
    settings: Settings = Depends(get_settings)
):
    """
    Get analytics on user's recommendation performance

    This endpoint provides insights into:
    - Total recommendations received
    - Products deployed vs recommended
    - Success rate of deployed products
    - Top performing niches
    - Most effective marketing angles

    Path Parameters:
        user_id: User ID to get analytics for

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
        import traceback
        logger.error(f"Failed to get analytics: {e}")
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


@app.post("/api/shopify/deploy")
async def deploy_to_shopify(
    request: Dict = Body(...),
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
        if request.get('product_id'):
            # TODO: Load from database
            product_data = {}  # Load from DB
        else:
            product_data = request.get('product_data')

        if not product_data:
            return {
                'success': False,
                'error': 'No product data provided'
            }

        # Deploy
        result = await deployment_service.deploy_product(product_data)

        return result

    except Exception as e:
        print(f"[ERROR] Deploy endpoint error: {e}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': str(e)
        }


@app.post("/api/shopify/bulk-deploy")
async def bulk_deploy_to_shopify(
    request: Dict = Body(...),
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
        if request.get('product_ids'):
            # TODO: Load from database
            products = []  # Load from DB
        else:
            products = request.get('products', [])

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
        print(f"[ERROR] Bulk deploy error: {e}")
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
        print(f"[ERROR] List products error: {e}")
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
        print(f"[ERROR] Delete product error: {e}")
        return {
            'success': False,
            'error': str(e)
        }


@app.post("/api/aliexpress/search")
async def search_aliexpress(
    request: Dict = Body(...),
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
            keywords=request.get('keywords'),
            min_price=request.get('min_price'),
            max_price=request.get('max_price')
        )

        return {
            'success': True,
            'count': len(products),
            'products': products
        }

    except Exception as e:
        print(f"[ERROR] AliExpress search error: {e}")
        return {
            'success': False,
            'error': str(e)
        }


@app.post("/api/aliexpress/affiliate-links")
async def generate_affiliate_links(
    request: Dict = Body(...),
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
            request.get('product_ids', [])
        )

        return {
            'success': True,
            'links': links
        }

    except Exception as e:
        print(f"[ERROR] Affiliate link error: {e}")
        return {
            'success': False,
            'error': str(e)
        }


@app.post("/api/aliexpress/fulfill-order")
async def fulfill_order(
    request: Dict = Body(...),
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
            request.get('shopify_order'),
            request.get('aliexpress_product_id')
        )

        return result

    except Exception as e:
        print(f"[ERROR] Order fulfillment error: {e}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': str(e)
        }


@app.post("/api/aliexpress/sync-inventory")
async def sync_inventory(
    request: Dict = Body(...),
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
            request.get('products', [])
        )

        return {
            'success': True,
            'results': results
        }

    except Exception as e:
        print(f"[ERROR] Inventory sync error: {e}")
        return {
            'success': False,
            'error': str(e)
        }


@app.post("/api/aliexpress/monitor-prices")
async def monitor_prices(
    request: Dict = Body(...),
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
            request.get('products', []),
            request.get('threshold_percent', 10.0)
        )

        return {
            'success': True,
            'alerts': alerts
        }

    except Exception as e:
        print(f"[ERROR] Price monitoring error: {e}")
        return {
            'success': False,
            'error': str(e)
        }


# 
# META (FACEBOOK/INSTAGRAM) AD AUTOMATION
# 

@app.post("/api/meta/create-campaign")
async def create_meta_campaign(
    request: Dict = Body(...),
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
            product=request.get('product'),
            daily_budget=request.get('daily_budget', 10.0),
            auto_activate=request.get('auto_activate', False)
        )

        return result

    except Exception as e:
        print(f"[ERROR] Campaign creation error: {e}")
        return {
            'success': False,
            'error': str(e)
        }


@app.post("/api/meta/bulk-campaigns")
async def create_bulk_campaigns(
    request: Dict = Body(...),
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
            products=request.get('products', []),
            daily_budget_per_product=request.get('daily_budget_per_product', 10.0)
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
    request: Dict = Body(...),
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
            request.get('status')
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
    request: Dict = Body(...),
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

        budget_cents = int(request.get('daily_budget', 10.0) * 100)

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
    request: Dict = Body(...),
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
            request.get('scheduled_start').replace('Z', '+00:00')
        )

        scheduled_end = None
        if request.get('scheduled_end'):
            scheduled_end = datetime.fromisoformat(
                request.get('scheduled_end').replace('Z', '+00:00')
            )

        result = await manager.create_schedule(
            product=request.get('product'),
            scheduled_start=scheduled_start,
            daily_budget=request.get('daily_budget', 10.0),
            scheduled_end=scheduled_end,
            total_budget=request.get('total_budget'),
            platform=request.get('platform', 'meta'),
            target_audience=request.get('target_audience')
        )

        return result

    except Exception as e:
        print(f"[ERROR] Schedule creation error: {e}")
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


# 
# PRODUCT RANKINGS API
# 

@app.get("/api/rankings/top")
async def get_top_rankings(
    limit: int = 20,
    store_id: Optional[int] = None,
    niche: Optional[str] = None,
    settings: Settings = Depends(get_settings)
):
    """
    Get current top ranked products from product_history database

    Query params:
    - limit: Number of products to return (default: 20)
    - store_id: Filter by store (optional) - DEPRECATED
    - niche: Filter by niche (optional)

    Returns: Top products with rankings and scores
    """
    try:
        from datetime import datetime, timedelta
        import sqlite3
        import json

        # Connect to product_history database
        db_path = "data/product_history.db"
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Build query
        query = """
            SELECT
                id,
                name,
                niche,
                price,
                cost,
                score,
                profit_margin,
                estimated_profit,
                rating,
                orders,
                velocity_score,
                image_url,
                aliexpress_url,
                source,
                description,
                last_updated
            FROM products
        """

        params = []
        if niche:
            query += " WHERE niche = ?"
            params.append(niche)

        query += " ORDER BY score DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        # Helper to determine tier
        def get_tier(rank: int):
            if 1 <= rank <= 3:
                return {"name": "ELITE", "emoji": "[TOP]", "color": "#FFD700"}
            elif 4 <= rank <= 10:
                return {"name": "TOP", "emoji": "[FIRST]", "color": "#C0C0C0"}
            elif 11 <= rank <= 20:
                return {"name": "RISING", "emoji": "[SECOND]", "color": "#CD7F32"}
            else:
                return {"name": "UNRANKED", "emoji": "[STATS]", "color": "#808080"}

        # Format rankings
        rankings = []
        for idx, row in enumerate(rows, start=1):
            rankings.append({
                "rank": idx,
                "tier": get_tier(idx),
                "product_id": row["id"],
                "product_name": row["name"],
                "composite_score": float(row["score"]) if row["score"] else 0.0,
                "score_breakdown": {
                    "ai_score": float(row["score"]) if row["score"] else 0.0,
                    "velocity_score": float(row["velocity_score"]) if row["velocity_score"] else 0.0,
                    "profit_margin": float(row["profit_margin"]) if row["profit_margin"] else 0.0,
                    "rating": float(row["rating"]) if row["rating"] else 0.0,
                },
                "niche": row["niche"],
                "price": float(row["price"]) if row["price"] else 0.0,
                "cost": float(row["cost"]) if row["cost"] else 0.0,
                "profit_margin": float(row["profit_margin"]) if row["profit_margin"] else 0.0,
                "estimated_profit": float(row["estimated_profit"]) if row["estimated_profit"] else 0.0,
                "rating": float(row["rating"]) if row["rating"] else 0.0,
                "orders": int(row["orders"]) if row["orders"] else 0,
                "image_url": row["image_url"],
                "aliexpress_url": row["aliexpress_url"],
                "source": row["source"],
                "last_updated": row["last_updated"],
                # Movement indicators (placeholder - would need historical data)
                "rank_change": 0,
                "rank_direction": "stable"
            })

        return {
            "success": True,
            "rankings": rankings,
            "total_count": len(rankings),
            "last_updated": datetime.utcnow().isoformat(),
            "next_update": (datetime.utcnow() + timedelta(hours=1)).isoformat()
        }

    except Exception as e:
        logger.error(f"Rankings error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e),
            "rankings": []
        }


@app.get("/api/rankings/movers")
async def get_ranking_movers(
    direction: str = 'gainers',
    limit: int = 10,
    timeframe: str = '24h',
    settings: Settings = Depends(get_settings)
):
    """
    Get biggest rank changes (gainers or losers)

    Query params:
    - direction: 'gainers' or 'losers' (default: 'gainers')
    - limit: Number of products (default: 10)
    - timeframe: '24h', '7d', or '30d' (default: '24h')

    Returns: Products with biggest rank movements
    """
    try:
        from datetime import datetime, timedelta
        from ospra_os.intelligence.ranking_engine import RankingEngine
        from ospra_os.database import get_multi_store_session

        db_url = settings.database_url or "sqlite:///./oubon_store.db"
        session = get_multi_store_session(db_url)
        engine = RankingEngine(session)

        if direction == 'gainers':
            movers = await engine.get_biggest_gainers(limit=limit, timeframe=timeframe)
        else:
            movers = await engine.get_biggest_losers(limit=limit, timeframe=timeframe)

        return {
            "success": True,
            "movers": movers,
            "direction": direction,
            "timeframe": timeframe
        }

    except Exception as e:
        logger.error(f"Movers error: {e}")
        return {
            "success": False,
            "error": str(e),
            "movers": []
        }


@app.get("/api/rankings/product/{product_id}")
async def get_product_ranking_details(
    product_id: int,
    settings: Settings = Depends(get_settings)
):
    """
    Get detailed ranking information for a single product

    Returns: Complete ranking history and stats
    """
    try:
        from datetime import datetime, timedelta
        from ospra_os.intelligence.ranking_engine import RankingEngine
        from ospra_os.database import get_multi_store_session

        db_url = settings.database_url or "sqlite:///./oubon_store.db"
        session = get_multi_store_session(db_url)
        engine = RankingEngine(session)

        details = await engine.get_product_rank_details(product_id)

        if not details:
            return {
                "success": False,
                "error": "Product not found"
            }

        return {
            "success": True,
            **details
        }

    except Exception as e:
        logger.error(f"Product ranking details error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@app.get("/api/rankings/history/{product_id}")
async def get_product_rank_history(
    product_id: int,
    days: int = 30,
    settings: Settings = Depends(get_settings)
):
    """
    Get rank history for a product over time

    Query params:
    - days: Number of days to look back (default: 30)

    Returns: Historical rankings with dates
    """
    try:
        from datetime import datetime, timedelta
        from ospra_os.database import get_multi_store_session, RankingHistory

        db_url = settings.database_url or "sqlite:///./oubon_store.db"
        session = get_multi_store_session(db_url)

        # Get history for the past N days
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        history = session.query(RankingHistory).filter(
            RankingHistory.product_id == product_id,
            RankingHistory.snapshot_date >= cutoff_date
        ).order_by(RankingHistory.snapshot_date.asc()).all()

        if not history:
            return {
                "success": True,
                "history": [],
                "message": "No history available for this product"
            }

        # Format history data
        history_data = [
            {
                "date": h.snapshot_date.isoformat(),
                "rank": h.rank,
                "composite_score": h.composite_score,
                "rank_change": h.rank_change,
                "rank_direction": h.rank_direction,
                "tier_name": h.tier_name
            }
            for h in history
        ]

        return {
            "success": True,
            "product_id": product_id,
            "history": history_data,
            "days_tracked": days
        }

    except Exception as e:
        logger.error(f"Rank history error: {e}")
        return {
            "success": False,
            "error": str(e),
            "history": []
        }


@app.get("/api/rankings/new-entries")
async def get_new_entries(
    limit: int = 10,
    settings: Settings = Depends(get_settings)
):
    """
    Get products that recently entered the top 20 rankings

    Returns: Products that are new to the top 20
    """
    try:
        from datetime import datetime, timedelta
        from ospra_os.database import get_multi_store_session, RankingHistory
        from sqlalchemy import and_

        db_url = settings.database_url or "sqlite:///./oubon_store.db"
        session = get_multi_store_session(db_url)

        # Get today's rankings
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        # Find products in top 20 today with rank_direction = 'new'
        new_entries = session.query(RankingHistory).filter(
            and_(
                RankingHistory.snapshot_date >= today,
                RankingHistory.rank <= 20,
                RankingHistory.rank_direction == 'new'
            )
        ).order_by(RankingHistory.rank.asc()).limit(limit).all()

        entries_data = [
            {
                "product_id": entry.product_id,
                "rank": entry.rank,
                "composite_score": entry.composite_score,
                "tier_name": entry.tier_name,
                "entered_date": entry.snapshot_date.isoformat()
            }
            for entry in new_entries
        ]

        return {
            "success": True,
            "new_entries": entries_data,
            "count": len(entries_data)
        }

    except Exception as e:
        logger.error(f"New entries error: {e}")
        return {
            "success": False,
            "error": str(e),
            "new_entries": []
        }


@app.get("/api/rankings/fallen")
async def get_fallen_products(
    limit: int = 10,
    settings: Settings = Depends(get_settings)
):
    """
    Get products that recently dropped out of the top 20 rankings

    Returns: Products that were previously in top 20 but are no longer
    """
    try:
        from datetime import datetime, timedelta
        from ospra_os.database import get_multi_store_session, RankingHistory

        db_url = settings.database_url or "sqlite:///./oubon_store.db"
        session = get_multi_store_session(db_url)

        # Get yesterday's and today's dates
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday = today - timedelta(days=1)

        # Find products that were in top 20 yesterday
        yesterday_top_20 = session.query(RankingHistory.product_id).filter(
            and_(
                RankingHistory.snapshot_date >= yesterday,
                RankingHistory.snapshot_date < today,
                RankingHistory.rank <= 20
            )
        ).all()

        yesterday_product_ids = {p.product_id for p in yesterday_top_20}

        # Find products in top 20 today
        today_top_20 = session.query(RankingHistory.product_id).filter(
            and_(
                RankingHistory.snapshot_date >= today,
                RankingHistory.rank <= 20
            )
        ).all()

        today_product_ids = {p.product_id for p in today_top_20}

        # Products that were in top 20 yesterday but not today
        fallen_product_ids = yesterday_product_ids - today_product_ids

        # Get details for fallen products
        fallen_products = []
        for product_id in list(fallen_product_ids)[:limit]:
            last_rank = session.query(RankingHistory).filter(
                RankingHistory.product_id == product_id
            ).order_by(RankingHistory.snapshot_date.desc()).first()

            if last_rank:
                fallen_products.append({
                    "product_id": product_id,
                    "previous_rank": last_rank.previous_rank or last_rank.rank,
                    "last_score": last_rank.composite_score,
                    "fell_on": last_rank.snapshot_date.isoformat()
                })

        return {
            "success": True,
            "fallen_products": fallen_products,
            "count": len(fallen_products)
        }

    except Exception as e:
        logger.error(f"Fallen products error: {e}")
        return {
            "success": False,
            "error": str(e),
            "fallen_products": []
        }


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
    from datetime import datetime

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
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
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
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
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
        except:
            pass


# 
# SHOPIFY WEBHOOKS - Now handled by shopify_webhooks_router
# Legacy manual endpoints removed - all 24 webhooks are in ospra_os/webhooks/shopify_webhooks.py
#


# Mount static files (must be last)
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except Exception as e:
    print(f"[WARNING]  Static files not mounted: {e}")

# Mount generated images directory for AI-generated product images
try:
    generated_images_dir = Path(__file__).parent.parent / "generated_images"
    generated_images_dir.mkdir(exist_ok=True)  # Create if doesn't exist
    app.mount("/generated_images", StaticFiles(directory=str(generated_images_dir)), name="generated_images")
    print(f"[SUCCESS] Generated images mounted at /generated_images")
except Exception as e:
    print(f"[WARNING]  Generated images not mounted: {e}")
