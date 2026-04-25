"""
PostHog Analytics Integration (task #38)
========================================

Server-side PostHog client for:
1. Feature flags — gate experimental features per-user / per-cohort
2. Funnel events — signup → first discovery → first deploy → first sale

Design principles:
- Optional dependency: if `posthog` isn't installed or `POSTHOG_API_KEY` is
  unset, every public function becomes a no-op (we never break the request
  path on missing telemetry).
- Server-side only: this module never embeds keys in the frontend bundle.
  The frontend should use a separate public-key client for in-page tracking.
- PII safe: we capture by `user_id` (hashed integer ID), never by email.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Dict, Optional, Union

logger = logging.getLogger(__name__)

# PostHog SDK is an optional dependency. If it's not installed we degrade
# gracefully so the app still boots.
try:
    import posthog as _posthog
    HAS_POSTHOG = True
except ImportError:
    _posthog = None
    HAS_POSTHOG = False


# ---------------------------------------------------------------------------
# Funnel event names — single source of truth
# ---------------------------------------------------------------------------

class FunnelEvent(str, Enum):
    """Canonical names for the activation funnel.

    Keep these stable: PostHog dashboards are keyed off these strings.
    """
    SIGNUP = "user_signup"
    FIRST_DISCOVERY = "first_discovery_run"
    FIRST_DEPLOY = "first_product_deployed"
    FIRST_SALE = "first_sale_recorded"

    # Secondary funnel events (not part of the core 4-step funnel but useful
    # for cohort analysis)
    EMAIL_VERIFIED = "email_verified"
    SHOPIFY_CONNECTED = "shopify_connected"
    APIFY_CONNECTED = "apify_connected"
    SUBSCRIPTION_STARTED = "subscription_started"
    SUBSCRIPTION_CANCELLED = "subscription_cancelled"


# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

_initialized: bool = False
_enabled: bool = False


def setup_posthog(
    api_key: Optional[str],
    host: str = "https://us.i.posthog.com",
    debug: bool = False,
    sync_mode: bool = False,
) -> bool:
    """
    Initialize PostHog for the lifetime of the process.

    Args:
        api_key: PostHog project API key (POSTHOG_API_KEY env var).
        host: PostHog host (us.i.posthog.com or eu.i.posthog.com or self-host).
        debug: Verbose SDK logging — only enable in dev.
        sync_mode: If True, capture() blocks until upload completes. Use only
                   in test fixtures; the default async batched mode is fine
                   for production.

    Returns:
        True if PostHog was initialized successfully, False otherwise.
        Callers can check this to log a startup banner.
    """
    global _initialized, _enabled

    if _initialized:
        logger.debug("[POSTHOG] Already initialized — skipping re-init")
        return _enabled

    _initialized = True

    if not HAS_POSTHOG:
        logger.warning("[POSTHOG] posthog SDK not installed — analytics disabled")
        _enabled = False
        return False

    if not api_key:
        logger.info("[POSTHOG] POSTHOG_API_KEY not set — analytics disabled")
        _enabled = False
        return False

    try:
        _posthog.api_key = api_key
        _posthog.host = host
        _posthog.debug = debug
        _posthog.sync_mode = sync_mode
        # Disable PostHog's GeoIP feature server-side — we don't need it for
        # funnel analytics and it adds latency.
        _posthog.disable_geoip = True
        _enabled = True
        logger.info(f"[POSTHOG] Analytics initialized (host={host})")
        return True
    except Exception as e:
        logger.error(f"[POSTHOG] Init failed: {e}")
        _enabled = False
        return False


def is_enabled() -> bool:
    """True iff PostHog is configured and ready to capture events."""
    return _enabled


# ---------------------------------------------------------------------------
# Event capture
# ---------------------------------------------------------------------------

def capture(
    user_id: Union[str, int],
    event: Union[FunnelEvent, str],
    properties: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Capture an event for a user. No-op if PostHog isn't configured.

    Args:
        user_id: Stable identifier for the user. We use the integer DB id
                 cast to string — never the email.
        event: A FunnelEvent (preferred) or raw event name string.
        properties: Optional event metadata. Avoid sending PII.
    """
    if not _enabled:
        return

    try:
        event_name = event.value if isinstance(event, FunnelEvent) else str(event)
        _posthog.capture(
            distinct_id=str(user_id),
            event=event_name,
            properties=properties or {},
        )
    except Exception as e:
        # Telemetry failures must never break the request path.
        logger.debug(f"[POSTHOG] capture({event}) failed: {e}")


def identify(
    user_id: Union[str, int],
    properties: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Set user-level properties (plan tier, cohort, signup_at, etc.).

    Use this once on signup and again on plan changes — not every request.
    """
    if not _enabled:
        return

    try:
        _posthog.identify(
            distinct_id=str(user_id),
            properties=properties or {},
        )
    except Exception as e:
        logger.debug(f"[POSTHOG] identify failed: {e}")


# ---------------------------------------------------------------------------
# Feature flags
# ---------------------------------------------------------------------------

def feature_enabled(
    flag_key: str,
    user_id: Union[str, int],
    default: bool = False,
    person_properties: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Check whether a feature flag is enabled for the given user.

    Args:
        flag_key: PostHog feature-flag key (e.g. "new-discovery-engine").
        user_id: User identifier (same as distinct_id used in capture).
        default: Returned if PostHog is unreachable or the flag is unknown.
        person_properties: Optional cohort hints (plan tier, signup_at, etc.).

    Returns:
        True/False. Always returns `default` when PostHog isn't initialized.
    """
    if not _enabled:
        return default

    try:
        result = _posthog.feature_enabled(
            flag_key,
            str(user_id),
            person_properties=person_properties or {},
        )
        # PostHog returns None when the flag is unknown or it can't reach
        # the server. We treat that as the default.
        return default if result is None else bool(result)
    except Exception as e:
        logger.debug(f"[POSTHOG] feature_enabled({flag_key}) failed: {e}")
        return default


def get_feature_flag_payload(
    flag_key: str,
    user_id: Union[str, int],
    default: Any = None,
    person_properties: Optional[Dict[str, Any]] = None,
) -> Any:
    """
    Get the JSON payload for a multivariate feature flag.

    Returns `default` if the flag isn't found or PostHog is disabled.
    """
    if not _enabled:
        return default

    try:
        payload = _posthog.get_feature_flag_payload(
            flag_key,
            str(user_id),
            person_properties=person_properties or {},
        )
        return default if payload is None else payload
    except Exception as e:
        logger.debug(f"[POSTHOG] get_feature_flag_payload({flag_key}) failed: {e}")
        return default


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

def shutdown() -> None:
    """
    Flush any pending events and shut down the SDK cleanly.

    Called from the FastAPI lifespan handler at app shutdown so we don't
    drop events buffered in the async sender.
    """
    if not _enabled or not HAS_POSTHOG:
        return

    try:
        _posthog.shutdown()
        logger.info("[POSTHOG] Flushed pending events")
    except Exception as e:
        logger.debug(f"[POSTHOG] shutdown failed: {e}")


# Test helper — never call from production code.
def _reset_for_tests() -> None:
    """Reset module state. Tests use this to re-init with new fixtures."""
    global _initialized, _enabled
    _initialized = False
    _enabled = False
