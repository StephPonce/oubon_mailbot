"""
Section C band 2 — unauthenticated sensitive/spendy endpoints (T32/T35/T36/T37/T40).

These endpoints were reachable with no credentials and each one either leaked
internals, burned money, or triggered privileged automation. Every test fails
if the gate is removed.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-unauth")


# ---------------------------------------------------------------------------
# T32 — monitoring router is admin-only; only a trivial liveness probe is public
# ---------------------------------------------------------------------------

class TestT32Monitoring:
    @pytest.mark.parametrize("method,path", [
        ("get", "/api/health/detailed"),          # full health snapshot
        ("get", "/api/health/errors"),            # stack traces + internals
        ("get", "/api/health/jobs"),
        ("post", "/api/health/jobs/discovery/disable"),
        ("post", "/api/health/jobs/discovery/trigger"),
        ("get", "/api/health/overview"),          # was the public root
    ])
    def test_monitoring_routes_require_admin(self, client, method, path):
        response = getattr(client, method)(path)
        assert response.status_code in (401, 403), f"{path} not gated"

    def test_liveness_probe_stays_public(self, client):
        """A trivial GET /api/health must stay open (load balancers hit it)
        and must NOT leak service internals."""
        response = client.get("/api/health")
        assert response.status_code == 200
        body = response.json()
        assert body == {"status": "ok"}  # nothing else

    def test_regular_user_cannot_reach_admin_monitoring(self, auth_client):
        """A normal authenticated (non-admin) user is still blocked (401/403)."""
        response = auth_client.get("/api/health/errors")
        assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# T40 — deployment preview requires auth (AI/DALL-E spend)
# ---------------------------------------------------------------------------

class TestT40DeploymentPreview:
    def test_preview_requires_auth(self, client):
        response = client.post("/api/deploy/preview", json={
            "product": {"title": "x", "category": "c", "price": 1.0,
                        "features": [], "images": []},
            "niche": "smart_home",
        })
        assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# T37 — aliexpress product read endpoints gated like sibling /search
# ---------------------------------------------------------------------------

class TestT37AliexpressReads:
    @pytest.mark.parametrize("path", [
        "/api/aliexpress/products/feed-names",
        "/api/aliexpress/products/hot",
        "/api/aliexpress/products/bestsellers",
        "/api/aliexpress/products/details?product_ids=123",
        "/api/aliexpress/products/product/123",
    ])
    def test_read_endpoints_require_auth(self, client, path):
        response = client.get(path)
        assert response.status_code in (401, 403), f"{path} not gated"


# ---------------------------------------------------------------------------
# T36 — Gmail Pub/Sub webhook requires a verified Google OIDC token
# ---------------------------------------------------------------------------

class TestT36PubSubWebhook:
    def test_webhook_rejects_missing_token(self, client, monkeypatch):
        from ospra_os.core.settings import get_settings
        monkeypatch.setattr(
            get_settings(), "GMAIL_PUBSUB_AUDIENCE", "https://ex.com/webhook",
            raising=False,
        )
        response = client.post("/api/email-automation/gmail/pubsub/webhook")
        assert response.status_code in (401, 403)

    def test_webhook_rejects_bad_token(self, client, monkeypatch):
        from ospra_os.core.settings import get_settings
        monkeypatch.setattr(
            get_settings(), "GMAIL_PUBSUB_AUDIENCE", "https://ex.com/webhook",
            raising=False,
        )
        response = client.post(
            "/api/email-automation/gmail/pubsub/webhook",
            headers={"Authorization": "Bearer not-a-real-google-token"},
        )
        assert response.status_code in (401, 403)

    def test_unconfigured_audience_fails_closed(self, client, monkeypatch):
        """No audience configured must be a hard 500, never an open door."""
        from ospra_os.core.settings import get_settings
        monkeypatch.setattr(
            get_settings(), "GMAIL_PUBSUB_AUDIENCE", None, raising=False,
        )
        response = client.post(
            "/api/email-automation/gmail/pubsub/webhook",
            headers={"Authorization": "Bearer whatever"},
        )
        assert response.status_code == 500
        assert response.status_code != 200

    def test_verified_token_is_accepted(self, client, monkeypatch):
        """A token that passes Google verification with the right audience +
        issuer is accepted (verification itself is stubbed)."""
        import ospra_os.api.email_automation_routes as ear
        from ospra_os.core.settings import get_settings

        monkeypatch.setattr(
            get_settings(), "GMAIL_PUBSUB_AUDIENCE", "https://ex.com/webhook",
            raising=False,
        )

        # Stub the Google verification to return valid claims.
        import google.oauth2.id_token as gid
        monkeypatch.setattr(
            gid, "verify_oauth2_token",
            lambda token, request, audience: {
                "iss": "https://accounts.google.com",
                "email": "pubsub@example.iam.gserviceaccount.com",
                "aud": audience,
            },
        )
        # Don't actually process emails.
        monkeypatch.setattr(ear, "process_emails_background", lambda settings: None)

        response = client.post(
            "/api/email-automation/gmail/pubsub/webhook",
            headers={"Authorization": "Bearer good-token"},
        )
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# T35 — websocket alert handler no longer trusts client user_id
# ---------------------------------------------------------------------------

class TestT35WebsocketAuth:
    def test_root_ws_handler_delegates_to_jwt_validated_one(self):
        """The 'root' handler must be the same JWT-validated code path — no
        anonymous fallback. We assert the source no longer contains the
        client-trusting shortcut."""
        import inspect
        from ospra_os.api import alert_routes

        src = inspect.getsource(alert_routes.websocket_alerts_root)
        # It must delegate to the JWT-validated handler...
        assert "await websocket_alerts(websocket)" in src
        # ...and must NOT contain its own connection registration (the old
        # handler called add_connection directly with a client-trusted id).
        assert "add_connection" not in src
