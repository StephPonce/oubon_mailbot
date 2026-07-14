"""
Section A band 2 — stop leaking secrets in logs/responses/transport
(T6/T11/T12/T13/T14). Every test fails if a leak is reintroduced.
"""

from __future__ import annotations

import inspect
import os

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-no-leak")


# ---------------------------------------------------------------------------
# T6 — AliExpress OAuth callbacks leak no tokens/params
# ---------------------------------------------------------------------------

class TestT6AliexpressOAuthNoLeak:
    @pytest.mark.parametrize("module", [
        "ospra_os.api.aliexpress_oauth",
        "ospra_os.api.aliexpress_affiliate_oauth",
    ])
    def test_callback_source_has_no_token_echo(self, module):
        import importlib
        mod = importlib.import_module(module)
        # Find the callback function(s) and assert they don't embed token JSON.
        src = inspect.getsource(mod)
        assert "json.dumps(token_response" not in src
        assert "token_json" not in src
        assert "[:20]" not in src  # no token previews
        # No print() of params/signatures/response bodies.
        assert 'print(f"   Parameters:' not in src
        assert '"   Raw Body:' not in src

    def test_neutral_success_page_no_secret(self, client):
        """Hitting the callback with a bad code returns a neutral page (no
        token/param echo). We can't complete a real OAuth here, but the error
        path must also be neutral."""
        r = client.get("/api/aliexpress/callback?code=invalid&state=x")
        # Whatever the status, the body must not contain token-ish structure.
        assert "access_token" not in r.text
        assert "refresh_token" not in r.text


# ---------------------------------------------------------------------------
# T11 — Sentry breadcrumb header redaction
# ---------------------------------------------------------------------------

class TestT11HeaderRedaction:
    def test_authorization_and_cookie_redacted(self):
        from ospra_os.observability.middleware import _safe_headers

        headers = {
            "authorization": "Bearer super-secret",
            "cookie": "session=abc123",
            "x-api-key": "sk-secret",
            "x-shopify-access-token": "shpat_secret",
            "user-agent": "pytest",
            "content-type": "application/json",
        }
        safe = _safe_headers(headers)
        assert safe["authorization"] == "[REDACTED]"
        assert safe["cookie"] == "[REDACTED]"
        assert safe["x-api-key"] == "[REDACTED]"
        assert safe["x-shopify-access-token"] == "[REDACTED]"
        # Safe headers pass through.
        assert safe["user-agent"] == "pytest"
        assert safe["content-type"] == "application/json"

    def test_no_secret_value_survives(self):
        from ospra_os.observability.middleware import _safe_headers
        safe = _safe_headers({"authorization": "Bearer leak-me"})
        assert "leak-me" not in str(safe)


# ---------------------------------------------------------------------------
# T13 — TikTok: bearer via header, tokens never returned
# ---------------------------------------------------------------------------

class TestT13TiktokTransport:
    def test_bearer_params_are_headers_not_query(self):
        import ospra_os.tiktok.routes as tr

        # profile / videos / upload must take Authorization via Header.
        src = inspect.getsource(tr)
        # No Query(...) aliased to Authorization anymore.
        assert 'Query(..., description="Bearer token", alias="Authorization")' not in src
        assert 'Header(..., description="Bearer token", alias="Authorization")' in src

    def test_callback_does_not_return_tokens(self):
        import ospra_os.tiktok.routes as tr
        src = inspect.getsource(tr.handle_oauth_callback)
        # Must not return the token response model that echoed access/refresh.
        assert "TikTokTokenResponse(" not in src
        # Must persist server-side instead of returning the token.
        assert "save_token(" in src
        # The return payload must not include token fields.
        return_idx = src.index("return {")
        return_block = src[return_idx:]
        assert "access_token" not in return_block
        assert "refresh_token" not in return_block


# ---------------------------------------------------------------------------
# T14 — in-memory Shopify router is not mounted
# ---------------------------------------------------------------------------

class TestT14ShopifyInMemoryRemoved:
    def test_in_memory_store_routes_not_reachable(self, client):
        """The leaky GET /api/shopify/stores (in-memory, all-users) is gone.
        The oauth surface at /api/shopify/oauth/* remains."""
        r = client.get("/api/shopify/stores")
        assert r.status_code == 404

    def test_router_not_mounted_in_app(self):
        from ospra_os.main import app
        paths = {getattr(rt, "path", "") for rt in app.routes}
        # The in-memory connect/stores endpoints must not be registered.
        assert "/api/shopify/stores" not in paths
        assert "/api/shopify/connect" not in paths


# ---------------------------------------------------------------------------
# T12 — migrate script never prints a generated key
# ---------------------------------------------------------------------------

class TestT12MigrateScriptNoKeyPrint:
    def test_no_generate_and_print(self):
        path = os.path.join(
            os.path.dirname(__file__), "..", "scripts", "old_tests", "migrate_gmail_to_db.py"
        )
        with open(path) as f:
            src = f.read()
        # It must not generate a key, and must not print one.
        assert "Fernet.generate_key()" not in src
        assert "Set EMAIL_OAUTH_ENCRYPTION_KEY=" not in src
