"""
Fail-if-reverted lock: CORS must be the OUTERMOST middleware.

Starlette runs the LAST-added middleware outermost. Before this fix, main.py
added CORSMiddleware early, so the rate limiter (429), TimeoutMiddleware (504)
and debug-protection (403) all sat OUTSIDE it — and any response those layers
FABRICATE never passed back through CORS. The browser received a response with
no Access-Control-Allow-Origin, blocked it, and fetch() surfaced an opaque
network error. Real-world hit: the day ENVIRONMENT=production activated strict
tier rate limits, AI analysis on ospra.io started dying with
"Analysis failed: Load failed. Check API connection." — a CORS-invisible 429.

Two locks:
  1. Structural — the real app's outermost middleware IS CORSMiddleware.
  2. Mechanism — with the REAL rate-limiter / timeout middleware classes
     stacked in main.py's relative order, their fabricated 429/504 responses
     carry Access-Control-Allow-Origin for an allowed origin.
"""

from __future__ import annotations

import asyncio
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-cors-order")

ORIGIN = "https://ospra.io"


class TestRealAppOrdering:
    def test_cors_is_the_outermost_middleware(self):
        """user_middleware[0] is the LAST middleware added = the OUTERMOST at
        runtime. If anyone adds a middleware after the CORS block in main.py
        (or moves CORS back up), this fails before prod does."""
        from ospra_os.main import app

        assert app.user_middleware, "expected registered middleware on the app"
        outermost = app.user_middleware[0]
        assert outermost.cls is CORSMiddleware, (
            f"outermost middleware is {outermost.cls.__name__}, not CORSMiddleware — "
            "responses fabricated by middleware outside CORS reach browsers without "
            "Access-Control-Allow-Origin and surface as opaque 'Load failed' network "
            "errors. Keep the CORS add_middleware call LAST in ospra_os/main.py."
        )


def _mini_app(limit: str, timeout_seconds: float) -> FastAPI:
    """The smallest app reproducing main.py's (fixed) middleware order:
    CORS added LAST = outermost, wrapping the real limiter + timeout classes."""
    from ospra_os.middleware.custom_rate_limiter import CustomRateLimitMiddleware
    from ospra_os.middleware.timeout_middleware import TimeoutMiddleware

    mini = FastAPI()

    @mini.get("/api/ping")
    async def ping():
        return {"ok": True}

    @mini.get("/api/slow")
    async def slow():
        await asyncio.sleep(timeout_seconds * 4)
        return {"ok": True}

    mini.add_middleware(TimeoutMiddleware, timeout_seconds=timeout_seconds)
    mini.add_middleware(
        CustomRateLimitMiddleware, get_tier_limit_func=lambda tier, resource: limit
    )
    # LAST = OUTERMOST, exactly like main.py post-fix.
    mini.add_middleware(
        CORSMiddleware,
        allow_origins=[ORIGIN],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return mini


class TestFabricatedResponsesCarryCors:
    def test_rate_limited_429_has_cors_headers(self):
        client = TestClient(_mini_app(limit="2/minute", timeout_seconds=5.0))
        headers = {"Origin": ORIGIN}

        assert client.get("/api/ping", headers=headers).status_code == 200
        assert client.get("/api/ping", headers=headers).status_code == 200
        third = client.get("/api/ping", headers=headers)

        assert third.status_code == 429  # the limiter fabricated this response
        assert third.headers.get("access-control-allow-origin") == ORIGIN, (
            "429 lacks Access-Control-Allow-Origin — browsers will block it and "
            "report an opaque network error ('Load failed') instead of the rate "
            "limit. CORS middleware must wrap the rate limiter."
        )
        # And it stays a READABLE body (message the frontend can surface).
        assert third.json().get("error") == "rate_limit_exceeded"

    def test_timeout_504_has_cors_headers(self):
        client = TestClient(_mini_app(limit="100/minute", timeout_seconds=0.05))
        resp = client.get("/api/slow", headers={"Origin": ORIGIN})

        assert resp.status_code == 504  # TimeoutMiddleware fabricated this
        assert resp.headers.get("access-control-allow-origin") == ORIGIN, (
            "504 lacks Access-Control-Allow-Origin — a timed-out AI analysis "
            "surfaces as 'Load failed' instead of a retryable timeout error. "
            "CORS middleware must wrap TimeoutMiddleware."
        )

    def test_preflight_is_answered_before_the_rate_limiter(self):
        """OPTIONS preflights must neither consume nor trip the quota: CORS
        (outermost) answers them before the limiter ever sees the request."""
        client = TestClient(_mini_app(limit="1/minute", timeout_seconds=5.0))
        preflight_headers = {
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "GET",
        }
        # Quota is 1/minute; many preflights must all succeed regardless.
        for _ in range(5):
            resp = client.options("/api/ping", headers=preflight_headers)
            assert resp.status_code == 200
            assert resp.headers.get("access-control-allow-origin") == ORIGIN
        # The single real request still goes through afterwards: quota unburned.
        assert client.get("/api/ping", headers={"Origin": ORIGIN}).status_code == 200
