"""
Global Constants for OspraOS
============================

Centralized configuration constants to avoid magic numbers throughout the codebase.
Import these instead of using hardcoded values.

Author: OspraOS
Date: January 2026
"""

from typing import Final

# ============================================================================
# HTTP/API TIMEOUTS (in seconds)
# ============================================================================

HTTP_TIMEOUT_DEFAULT: Final[float] = 30.0
HTTP_TIMEOUT_SHORT: Final[float] = 10.0
HTTP_TIMEOUT_LONG: Final[float] = 60.0
HTTP_TIMEOUT_EXTENDED: Final[float] = 120.0

# Platform-specific timeouts
SHOPIFY_API_TIMEOUT: Final[float] = 30.0
WOOCOMMERCE_API_TIMEOUT: Final[float] = 30.0
AMAZON_API_TIMEOUT: Final[float] = 30.0
ALIEXPRESS_API_TIMEOUT: Final[float] = 15.0
CJ_DROPSHIPPING_API_TIMEOUT: Final[float] = 30.0

# Email service timeouts
SMTP_TIMEOUT: Final[float] = 30.0
EMAIL_API_TIMEOUT: Final[float] = 30.0

# AI provider timeouts
AI_API_TIMEOUT: Final[float] = 60.0
AI_CHAT_TIMEOUT: Final[float] = 30.0
AI_ANALYSIS_TIMEOUT: Final[float] = 120.0

# ============================================================================
# RETRY CONFIGURATION
# ============================================================================

DEFAULT_MAX_RETRIES: Final[int] = 3
CRITICAL_MAX_RETRIES: Final[int] = 5
MIN_RETRIES: Final[int] = 2

DEFAULT_RETRY_DELAY: Final[int] = 60  # seconds
SHORT_RETRY_DELAY: Final[int] = 30  # seconds
LONG_RETRY_DELAY: Final[int] = 120  # seconds
EXTENDED_RETRY_DELAY: Final[int] = 300  # seconds (5 min)

# Rate limit retry delays
RATE_LIMIT_RETRY_SHORT: Final[int] = 2  # seconds
RATE_LIMIT_RETRY_DEFAULT: Final[int] = 60  # seconds
RATE_LIMIT_RETRY_LONG: Final[int] = 120  # seconds

# ============================================================================
# RATE LIMITING
# ============================================================================

# Default rate limits (requests per minute)
RATE_LIMIT_DEFAULT_RPM: Final[int] = 60
RATE_LIMIT_STRICT_RPM: Final[int] = 10
RATE_LIMIT_RELAXED_RPM: Final[int] = 120

# API-specific rate limits
SHOPIFY_RATE_LIMIT_RPM: Final[int] = 80
TIKTOK_RATE_LIMIT_RPM: Final[int] = 100
CJ_RATE_LIMIT_RPS: Final[int] = 1  # 1 request per second

# ============================================================================
# PAGINATION
# ============================================================================

DEFAULT_PAGE_SIZE: Final[int] = 50
MAX_PAGE_SIZE: Final[int] = 250
MIN_PAGE_SIZE: Final[int] = 10

# Platform-specific pagination
SHOPIFY_MAX_PAGE_SIZE: Final[int] = 250
WOOCOMMERCE_MAX_PAGE_SIZE: Final[int] = 100
AMAZON_MAX_PAGE_SIZE: Final[int] = 20

# ============================================================================
# SCHEDULING INTERVALS (in seconds unless noted)
# ============================================================================

# Learning scheduler
DAILY_LEARNING_HOUR: Final[int] = 3  # 3 AM
WEEKLY_LEARNING_DAY: Final[str] = 'sun'  # Sunday
WEEKLY_LEARNING_HOUR: Final[int] = 4  # 4 AM

# Sync intervals
TRACKING_SYNC_INTERVAL_HOURS: Final[int] = 6
PRICE_MONITOR_INTERVAL_HOURS: Final[int] = 6
INVENTORY_SYNC_INTERVAL_HOURS: Final[int] = 4

# Background job intervals
BACKGROUND_JOB_CHECK_INTERVAL: Final[int] = 60  # seconds
SHUTDOWN_WAIT_TIMEOUT: Final[int] = 5  # seconds

# ============================================================================
# DATA RETENTION (in days)
# ============================================================================

LEARNING_DATA_RETENTION_DAYS: Final[int] = 90
PRICE_HISTORY_RETENTION_DAYS: Final[int] = 30
LOG_RETENTION_DAYS: Final[int] = 30
ACTION_RETENTION_DAYS: Final[int] = 30
SESSION_RETENTION_DAYS: Final[int] = 7

# ============================================================================
# AI SCORING THRESHOLDS
# ============================================================================

# Score boundaries (0-100 scale)
HIGH_SCORE_THRESHOLD: Final[int] = 85
MEDIUM_SCORE_THRESHOLD: Final[int] = 70
LOW_SCORE_THRESHOLD: Final[int] = 50

# Confidence thresholds (0-1 scale)
HIGH_CONFIDENCE_THRESHOLD: Final[float] = 0.8
MEDIUM_CONFIDENCE_THRESHOLD: Final[float] = 0.6
DEFAULT_CONFIDENCE: Final[float] = 0.7

# Sentiment thresholds
POSITIVE_SENTIMENT_THRESHOLD: Final[float] = 0.3
NEGATIVE_SENTIMENT_THRESHOLD: Final[float] = -0.2

# ============================================================================
# PRICING & PROFIT
# ============================================================================

DEFAULT_PROFIT_MARGIN: Final[float] = 0.6  # 60%
MINIMUM_PROFIT_MARGIN: Final[float] = 0.3  # 30%
HIGH_PROFIT_MARGIN: Final[float] = 0.5  # 50%

DEFAULT_MARKUP_MULTIPLIER: Final[float] = 2.5
MINIMUM_MARKUP_MULTIPLIER: Final[float] = 1.5

PRICE_CHANGE_THRESHOLD: Final[float] = 0.05  # 5% change triggers alert

# ============================================================================
# TOKEN LIMITS (AI)
# ============================================================================

DEFAULT_MAX_TOKENS: Final[int] = 1024
ANALYSIS_MAX_TOKENS: Final[int] = 2048
DESCRIPTION_MAX_TOKENS: Final[int] = 2048
EMAIL_MAX_TOKENS: Final[int] = 300
CHAT_MAX_TOKENS: Final[int] = 1024

# Input truncation
EMAIL_BODY_TRUNCATE_LENGTH: Final[int] = 300
ANALYSIS_TEXT_TRUNCATE_LENGTH: Final[int] = 500

# ============================================================================
# BATCH SIZES
# ============================================================================

DEFAULT_BATCH_SIZE: Final[int] = 50
LARGE_BATCH_SIZE: Final[int] = 100
SMALL_BATCH_SIZE: Final[int] = 10

PRODUCT_DISCOVERY_BATCH_SIZE: Final[int] = 50
ORDER_SYNC_BATCH_SIZE: Final[int] = 100
EMAIL_PROCESS_BATCH_SIZE: Final[int] = 10

# ============================================================================
# CONTENT LIMITS
# ============================================================================

TITLE_MAX_LENGTH: Final[int] = 60
DESCRIPTION_MAX_LENGTH: Final[int] = 2000
META_DESCRIPTION_MAX_LENGTH: Final[int] = 160
SHORT_DESCRIPTION_MAX_LENGTH: Final[int] = 500

# ============================================================================
# SUPPLIER RATINGS
# ============================================================================

DEFAULT_SUPPLIER_RATING: Final[float] = 4.0
MINIMUM_SUPPLIER_RATING: Final[float] = 3.5
EXCELLENT_SUPPLIER_RATING: Final[float] = 4.5

# ============================================================================
# TEMPERATURE SETTINGS (AI)
# ============================================================================

AI_TEMPERATURE_CREATIVE: Final[float] = 0.8
AI_TEMPERATURE_BALANCED: Final[float] = 0.7
AI_TEMPERATURE_PRECISE: Final[float] = 0.3

# ============================================================================
# SECURITY
# ============================================================================

JWT_EXPIRE_MINUTES: Final[int] = 60
REFRESH_TOKEN_EXPIRE_DAYS: Final[int] = 7
API_KEY_LENGTH: Final[int] = 32
STATE_TOKEN_LENGTH: Final[int] = 32
WEBHOOK_TOLERANCE_SECONDS: Final[int] = 300  # 5 minutes

# ============================================================================
# HTTP STATUS CODES (for reference)
# ============================================================================

HTTP_OK: Final[int] = 200
HTTP_CREATED: Final[int] = 201
HTTP_BAD_REQUEST: Final[int] = 400
HTTP_UNAUTHORIZED: Final[int] = 401
HTTP_FORBIDDEN: Final[int] = 403
HTTP_NOT_FOUND: Final[int] = 404
HTTP_RATE_LIMITED: Final[int] = 429
HTTP_SERVER_ERROR: Final[int] = 500
HTTP_SERVICE_UNAVAILABLE: Final[int] = 503
