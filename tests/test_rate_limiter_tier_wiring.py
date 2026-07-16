"""
Fail-if-reverted lock: the rate limiter must resolve tier + user from the JWT.

Before this fix, CustomRateLimitMiddleware read request.state.tier /
request.state.user_id, documented as "set by the JWT auth middleware" — but no
such middleware ever existed. Consequences in prod (surfaced the day
ENVIRONMENT=production activated strict limits):

  * EVERY authenticated request — stratosphere included — was rate-limited at
    the anonymous nest/free tier. Paid tiers were cosmetic for rate limiting.
  * Buckets were keyed by IP, so users behind one NAT shared a single quota.

The fix hydrates request.state from a SIGNATURE-VERIFIED access token inside
the limiter (same decode_token as get_current_user), falling back to anonymous
defaults on any failure. These tests exercise the REAL middleware with REAL
signed tokens end-to-end.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-tier-wiring")

from ospra_os.auth import jwt_auth
from ospra_os.middleware.custom_rate_limiter import CustomRateLimitMiddleware

# Tier→limit table for these tests: anonymous/nest is tight, paid is roomy.
LIMITS = {"nest": "2/minute", "stratosphere": "100/minute"}


def _tier_limit(tier: str, resource: str) -> str:
    return LIMITS.get(tier, LIMITS["nest"])


def _app() -> FastAPI:
    app = FastAPI()

    @app.get("/api/ping")
    async def ping():
        return {"ok": True}

    app.add_middleware(CustomRateLimitMiddleware, get_tier_limit_func=_tier_limit)
    return app


def _user(user_id: int, tier: str = "stratosphere") -> SimpleNamespace:
    """The attribute surface create_access_token actually reads."""
    return SimpleNamespace(
        id=user_id,
        email=f"user{user_id}@test.io",
        subscription_tier=SimpleNamespace(value=tier),
    )


def _bearer(user_id: int, tier: str = "stratosphere") -> dict:
    token = jwt_auth.create_access_token(_user(user_id, tier))
    return {"Authorization": f"Bearer {token}"}


class TestTierIsHonored:
    def test_anonymous_hits_nest_limit(self):
        client = TestClient(_app())
        assert client.get("/api/ping").status_code == 200
        assert client.get("/api/ping").status_code == 200
        assert client.get("/api/ping").status_code == 429  # nest = 2/minute

    def test_stratosphere_token_gets_stratosphere_limits(self):
        """THE fix: a real signed token's tier claim must reach the limiter.
        Reverting to state-only extraction makes this fail (429 on request 3)."""
        client = TestClient(_app())
        headers = _bearer(1, "stratosphere")
        for i in range(10):  # far past the nest cap of 2/minute
            assert client.get("/api/ping", headers=headers).status_code == 200, (
                f"request {i + 1} rate-limited — stratosphere tier not honored"
            )

    def test_garbage_token_falls_back_to_anonymous(self):
        client = TestClient(_app())
        headers = {"Authorization": "Bearer not-a-real-token"}
        assert client.get("/api/ping", headers=headers).status_code == 200
        assert client.get("/api/ping", headers=headers).status_code == 200
        third = client.get("/api/ping", headers=headers)
        assert third.status_code == 429  # spoofing gets you nest, not a crash

    def test_expired_token_falls_back_to_anonymous(self):
        """An expired stratosphere token must NOT confer stratosphere limits."""
        from jose import jwt as jose_jwt

        expired = jose_jwt.encode(
            {
                "sub": "9",
                "tier": "stratosphere",
                "type": "access",
                "exp": datetime.now(timezone.utc) - timedelta(hours=1),
                "jti": "expired-jti",
            },
            jwt_auth.SECRET_KEY,
            algorithm=jwt_auth.ALGORITHM,
        )
        client = TestClient(_app())
        headers = {"Authorization": f"Bearer {expired}"}
        assert client.get("/api/ping", headers=headers).status_code == 200
        assert client.get("/api/ping", headers=headers).status_code == 200
        assert client.get("/api/ping", headers=headers).status_code == 429


class TestPerUserBuckets:
    def test_users_on_the_same_ip_get_separate_buckets(self):
        """TestClient presents one IP for everyone. With per-user keying, one
        user's burst must not consume another user's quota (pre-fix, IP keying
        pooled them into a single bucket)."""
        client = TestClient(_app())
        a = _bearer(101, "nest")
        b = _bearer(202, "nest")

        # User A burns their whole nest quota (2/minute)...
        assert client.get("/api/ping", headers=a).status_code == 200
        assert client.get("/api/ping", headers=a).status_code == 200
        assert client.get("/api/ping", headers=a).status_code == 429

        # ...and user B, same IP, is untouched.
        assert client.get("/api/ping", headers=b).status_code == 200
