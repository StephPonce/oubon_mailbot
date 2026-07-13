"""
Section C band 3 — admin-gating & privilege regression tests
(T34/T38/T48/T50/T51; T44 covered in test_auth_idor.py).

Privileged / platform-level surfaces were reachable by any authenticated user
(or, for T51, by any top-tier *customer*). These tests assert a real admin
flag is required — deny-by-default — and that the fake "stratosphere == admin"
grant is gone.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-admin-gating")


@pytest.fixture
def admin_client(client, test_user):
    """A client whose authenticated user is a real admin (is_admin=True)."""
    from ospra_os.main import app
    from ospra_os.auth.jwt_auth import get_current_user

    test_user.is_admin = True  # instance attr — getattr(user,'is_admin') sees it

    async def override():
        return test_user

    app.dependency_overrides[get_current_user] = override
    yield client
    app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# T34 — admin dashboard requires admin
# ---------------------------------------------------------------------------

class TestT34AdminDashboard:
    @pytest.mark.parametrize("path", [
        "/admin/dashboard/data",
        "/admin/dashboard",
        "/admin/dashboard/v2",
    ])
    def test_requires_auth(self, client, path):
        assert client.get(path).status_code in (401, 403)

    def test_regular_user_forbidden(self, auth_client):
        assert auth_client.get("/admin/dashboard/data").status_code == 403

    def test_admin_allowed(self, admin_client):
        # Admin passes the gate (200, or a non-auth error from downstream data
        # fetching — never 401/403).
        assert admin_client.get("/admin/dashboard/data").status_code not in (401, 403)


# ---------------------------------------------------------------------------
# T51 — aliexpress _is_admin no longer equals "stratosphere tier"
# ---------------------------------------------------------------------------

class TestT51StratosphereIsNotAdmin:
    def test_stratosphere_customer_is_not_admin(self):
        from types import SimpleNamespace
        from ospra_os.api.aliexpress_product_routes import _is_admin

        stratosphere_customer = SimpleNamespace(
            subscription_tier="stratosphere", is_admin=False, is_superuser=False
        )
        assert _is_admin(stratosphere_customer) is False

    def test_real_admin_flag_is_admin(self):
        from types import SimpleNamespace
        from ospra_os.api.aliexpress_product_routes import _is_admin

        admin = SimpleNamespace(subscription_tier="nest", is_admin=True, is_superuser=False)
        assert _is_admin(admin) is True

    def test_debug_endpoints_disabled_in_production(self, monkeypatch):
        from ospra_os.api import aliexpress_product_routes as ar

        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.delenv("ALLOW_ALIEXPRESS_DEBUG", raising=False)
        assert ar._debug_endpoints_enabled() is False

    def test_debug_endpoints_enabled_outside_prod(self, monkeypatch):
        from ospra_os.api import aliexpress_product_routes as ar

        monkeypatch.setenv("ENVIRONMENT", "development")
        assert ar._debug_endpoints_enabled() is True

    def test_debug_endpoint_stratosphere_customer_blocked(self, auth_client, test_user):
        """End-to-end: a stratosphere customer can no longer reach /debug.

        Denied either by the admin check (403) or, in prod-like envs, by the
        global DebugEndpointProtectionMiddleware (404). Both mean 'blocked' —
        the point is a paid customer no longer gets through.
        """
        test_user.subscription_tier = "stratosphere"
        test_user.is_admin = False

        response = auth_client.get("/api/aliexpress/products/debug/raw-response")
        assert response.status_code in (403, 404)


# ---------------------------------------------------------------------------
# T48 — raw platform token never handed to a normal tenant
# ---------------------------------------------------------------------------

class TestT48TokenExposure:
    def test_get_token_requires_admin(self, auth_client):
        """A normal authenticated tenant must NOT be able to fetch the shared
        platform access token."""
        response = auth_client.get("/aliexpress/auth/token")
        assert response.status_code == 403

    def test_get_token_unauthenticated(self, client):
        assert client.get("/aliexpress/auth/token").status_code in (401, 403)

    def test_status_never_echoes_token(self):
        """The /auth/status response body must not include a token preview."""
        import inspect
        from ospra_os.aliexpress import routes

        src = inspect.getsource(routes.check_auth_status)
        assert 'access_token"][:20]' not in src
        assert '"token":' not in src


# ---------------------------------------------------------------------------
# T50 — aliexpress token management router is admin-only
# ---------------------------------------------------------------------------

class TestT50TokenManagement:
    @pytest.mark.parametrize("method,path,body", [
        ("post", "/api/aliexpress/tokens/manual-entry",
         {"api_type": "dropship", "access_token": "x" * 20}),
        ("post", "/api/aliexpress/tokens/refresh/all", None),
        ("get", "/api/aliexpress/tokens/status", None),
    ])
    def test_requires_admin(self, auth_client, method, path, body):
        response = getattr(auth_client, method)(path, json=body) if body is not None \
            else getattr(auth_client, method)(path)
        assert response.status_code == 403, f"{path} reachable by non-admin"

    def test_debug_env_blocked_for_non_admin(self, auth_client):
        """/debug/env is denied by the admin gate (403) or the global debug
        middleware (404) — never reachable by a normal tenant."""
        response = auth_client.get("/api/aliexpress/tokens/debug/env")
        assert response.status_code in (403, 404)


# ---------------------------------------------------------------------------
# T38 — auto-deploy controls admin-only
# ---------------------------------------------------------------------------

class TestT38AutoDeploy:
    @pytest.mark.parametrize("method,path", [
        ("post", "/api/auto-deploy/enable"),
        ("post", "/api/auto-deploy/disable"),
        ("post", "/api/auto-deploy/run-now"),
        ("get", "/api/auto-deploy/status"),
    ])
    def test_requires_admin(self, auth_client, method, path):
        response = getattr(auth_client, method)(path)
        assert response.status_code == 403, f"{path} reachable by non-admin"

    def test_unauthenticated_blocked(self, client):
        assert client.post("/api/auto-deploy/enable").status_code in (401, 403)
