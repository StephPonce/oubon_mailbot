"""
PostHog Client Tests (task #38)
================================

Validates that the PostHog client wrapper:
  1. Falls through to no-ops when PostHog is unconfigured (missing key or
     missing SDK), so a missing/unreachable PostHog never breaks the request
     path.
  2. Forwards captures with the correct distinct_id (string-cast user id) and
     event name (FunnelEvent enum coerced to its string value).
  3. Returns the caller's `default` for feature flags when PostHog is
     unavailable, the flag is unknown, or the underlying SDK raises.
  4. Validates the FunnelEvent enum names match the canonical funnel keys the
     dashboards are wired against — these strings are a stable contract.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ospra_os.observability import posthog_client as ph


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_posthog_state():
    """Each test gets a fresh module-level state."""
    ph._reset_for_tests()
    yield
    ph._reset_for_tests()


@pytest.fixture
def enabled_client():
    """Initialize the client with a fake SDK so capture/identify/flags work."""
    fake_sdk = MagicMock()
    fake_sdk.feature_enabled = MagicMock(return_value=True)
    fake_sdk.get_feature_flag_payload = MagicMock(return_value={"k": "v"})
    with patch.object(ph, "_posthog", fake_sdk), patch.object(ph, "HAS_POSTHOG", True):
        ph.setup_posthog(api_key="phc_test_key", host="https://us.i.posthog.com")
        yield fake_sdk


# ---------------------------------------------------------------------------
# FunnelEvent contract
# ---------------------------------------------------------------------------

class TestFunnelEventContract:
    """The funnel event names are referenced by PostHog dashboards. Renaming
    them silently would break activation reporting — this test pins them."""

    def test_core_funnel_keys(self):
        assert ph.FunnelEvent.SIGNUP.value == "user_signup"
        assert ph.FunnelEvent.FIRST_DISCOVERY.value == "first_discovery_run"
        assert ph.FunnelEvent.FIRST_DEPLOY.value == "first_product_deployed"
        assert ph.FunnelEvent.FIRST_SALE.value == "first_sale_recorded"

    def test_secondary_event_keys(self):
        assert ph.FunnelEvent.EMAIL_VERIFIED.value == "email_verified"
        assert ph.FunnelEvent.SHOPIFY_CONNECTED.value == "shopify_connected"
        assert ph.FunnelEvent.APIFY_CONNECTED.value == "apify_connected"
        assert ph.FunnelEvent.SUBSCRIPTION_STARTED.value == "subscription_started"
        assert ph.FunnelEvent.SUBSCRIPTION_CANCELLED.value == "subscription_cancelled"


# ---------------------------------------------------------------------------
# Disabled-state behaviour
# ---------------------------------------------------------------------------

class TestDisabledNoOp:
    """Every public function is a no-op when PostHog isn't initialized."""

    def test_capture_no_op_when_disabled(self):
        # Never called setup_posthog → _enabled should be False.
        assert ph.is_enabled() is False
        # Should not raise.
        ph.capture(42, ph.FunnelEvent.SIGNUP, {"plan": "nest"})

    def test_identify_no_op_when_disabled(self):
        assert ph.is_enabled() is False
        ph.identify(42, {"plan": "nest"})

    def test_feature_enabled_returns_default_when_disabled(self):
        assert ph.is_enabled() is False
        assert ph.feature_enabled("any-flag", 42, default=False) is False
        assert ph.feature_enabled("any-flag", 42, default=True) is True

    def test_get_feature_flag_payload_returns_default_when_disabled(self):
        assert ph.feature_enabled("any-flag", 42, default=False) is False
        sentinel = object()
        assert ph.get_feature_flag_payload("any-flag", 42, default=sentinel) is sentinel

    def test_setup_with_no_api_key_disables_client(self):
        with patch.object(ph, "HAS_POSTHOG", True), patch.object(ph, "_posthog", MagicMock()):
            ok = ph.setup_posthog(api_key=None)
            assert ok is False
            assert ph.is_enabled() is False

    def test_setup_with_missing_sdk_disables_client(self):
        with patch.object(ph, "HAS_POSTHOG", False):
            ok = ph.setup_posthog(api_key="phc_test")
            assert ok is False
            assert ph.is_enabled() is False

    def test_shutdown_no_op_when_disabled(self):
        # Should not raise even though we never set up.
        ph.shutdown()


# ---------------------------------------------------------------------------
# Capture path
# ---------------------------------------------------------------------------

class TestCapture:

    def test_capture_with_funnel_event(self, enabled_client):
        ph.capture(42, ph.FunnelEvent.SIGNUP, {"plan": "nest"})
        enabled_client.capture.assert_called_once()
        call_kwargs = enabled_client.capture.call_args.kwargs
        assert call_kwargs["distinct_id"] == "42"  # always string-cast
        assert call_kwargs["event"] == "user_signup"
        assert call_kwargs["properties"] == {"plan": "nest"}

    def test_capture_with_raw_event_name(self, enabled_client):
        ph.capture("user-7", "custom_event", {"foo": "bar"})
        enabled_client.capture.assert_called_once()
        call_kwargs = enabled_client.capture.call_args.kwargs
        assert call_kwargs["distinct_id"] == "user-7"
        assert call_kwargs["event"] == "custom_event"

    def test_capture_with_no_properties(self, enabled_client):
        ph.capture(42, ph.FunnelEvent.SIGNUP)
        call_kwargs = enabled_client.capture.call_args.kwargs
        assert call_kwargs["properties"] == {}

    def test_capture_swallows_sdk_exceptions(self, enabled_client):
        enabled_client.capture.side_effect = RuntimeError("PostHog network blip")
        # Must not raise — telemetry never breaks request path.
        ph.capture(42, ph.FunnelEvent.SIGNUP)


# ---------------------------------------------------------------------------
# Identify path
# ---------------------------------------------------------------------------

class TestIdentify:

    def test_identify_forwards_properties(self, enabled_client):
        ph.identify(42, {"plan": "nest", "signup_at": "2026-04-24T00:00:00"})
        enabled_client.identify.assert_called_once()
        call_kwargs = enabled_client.identify.call_args.kwargs
        assert call_kwargs["distinct_id"] == "42"
        assert call_kwargs["properties"]["plan"] == "nest"

    def test_identify_swallows_sdk_exceptions(self, enabled_client):
        enabled_client.identify.side_effect = RuntimeError("PostHog network blip")
        ph.identify(42, {"plan": "nest"})  # must not raise


# ---------------------------------------------------------------------------
# Feature flags
# ---------------------------------------------------------------------------

class TestFeatureFlags:

    def test_feature_enabled_returns_sdk_value(self, enabled_client):
        enabled_client.feature_enabled.return_value = True
        assert ph.feature_enabled("new-engine", 42) is True
        enabled_client.feature_enabled.assert_called_once()

    def test_feature_enabled_returns_default_for_unknown_flag(self, enabled_client):
        # PostHog returns None when it can't reach the server / unknown flag.
        enabled_client.feature_enabled.return_value = None
        assert ph.feature_enabled("unknown-flag", 42, default=False) is False
        assert ph.feature_enabled("unknown-flag", 42, default=True) is True

    def test_feature_enabled_swallows_sdk_exceptions(self, enabled_client):
        enabled_client.feature_enabled.side_effect = RuntimeError("network down")
        assert ph.feature_enabled("flag", 42, default=False) is False
        assert ph.feature_enabled("flag", 42, default=True) is True

    def test_feature_enabled_passes_person_properties(self, enabled_client):
        ph.feature_enabled("flag", 42, person_properties={"plan": "pro"})
        call_kwargs = enabled_client.feature_enabled.call_args.kwargs
        assert call_kwargs["person_properties"] == {"plan": "pro"}

    def test_get_feature_flag_payload_returns_payload(self, enabled_client):
        enabled_client.get_feature_flag_payload.return_value = {"variant": "B"}
        assert ph.get_feature_flag_payload("flag", 42) == {"variant": "B"}

    def test_get_feature_flag_payload_returns_default_on_none(self, enabled_client):
        enabled_client.get_feature_flag_payload.return_value = None
        sentinel = {"fallback": True}
        assert ph.get_feature_flag_payload("flag", 42, default=sentinel) is sentinel

    def test_get_feature_flag_payload_swallows_exceptions(self, enabled_client):
        enabled_client.get_feature_flag_payload.side_effect = RuntimeError("oops")
        assert ph.get_feature_flag_payload("flag", 42, default="X") == "X"


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

class TestLifecycle:

    def test_setup_initializes_only_once(self, enabled_client):
        # Re-running setup should be a no-op (returns current _enabled).
        ph.setup_posthog(api_key="phc_other_key")
        assert ph.is_enabled() is True

    def test_setup_records_host_on_sdk(self, enabled_client):
        # The fake SDK is a MagicMock, so attribute writes are tracked.
        assert enabled_client.host == "https://us.i.posthog.com"
        assert enabled_client.api_key == "phc_test_key"
        assert enabled_client.disable_geoip is True

    def test_shutdown_calls_sdk_shutdown(self, enabled_client):
        ph.shutdown()
        enabled_client.shutdown.assert_called_once()

    def test_shutdown_swallows_sdk_exceptions(self, enabled_client):
        enabled_client.shutdown.side_effect = RuntimeError("flush failed")
        ph.shutdown()  # must not raise


# ---------------------------------------------------------------------------
# Wiring sanity — settings + main.py integration
# ---------------------------------------------------------------------------

class TestSettingsWiring:
    """Make sure the PostHog config keys exist on Settings — main.py reads
    these at boot and a typo would silently disable analytics."""

    def test_settings_has_posthog_keys(self):
        from ospra_os.core.settings import Settings
        # Pydantic v2 field introspection
        fields = Settings.model_fields if hasattr(Settings, "model_fields") else {}
        assert "POSTHOG_API_KEY" in fields
        assert "POSTHOG_HOST" in fields
        assert "POSTHOG_DEBUG" in fields
        assert "POSTHOG_ENABLED" in fields
