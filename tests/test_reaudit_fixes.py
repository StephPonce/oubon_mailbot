"""
Re-audit fix pins (July 2026 batch, tasks #60-#61).

Each test targets a specific finding from OSPRA_BACKEND_REAUDIT_2026-07-01:
  M7  — stable supplier-ID-first product identity key (shared, single source)
  M5  — catalog_warm commits per product (one bad row loses one row, not all)
  M6  — empty catalog run exits non-zero
  M2  — absence snapshots keep dropped products' trajectories recording
  M3  — date-aware slopes (calendar gaps don't inflate trends)
  M4  — 2-point slopes contribute nothing; thin confidence never blends
  S1  — OAuth state is mandatory, HMAC-verified, owner-mintable only
  M8  — AE-DS token refresh is a SIGNED TOP call with envelope parsing
"""

import asyncio
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ospra_os.database.base import Base
from ospra_os.database.product_timeseries import ProductTimeseries, product_identity_key
from ospra_os.database.discovered_catalog import DiscoveredProduct
from ospra_os.intelligence.velocity_saturation import (
    linear_slope,
    velocity_saturation_from_series,
)
import ospra_os.tasks.catalog_warm as cw


# ---------------------------------------------------------------------------
# M7 — product identity key
# ---------------------------------------------------------------------------

class TestIdentityKey:
    def test_supplier_id_survives_title_and_image_change(self):
        p1 = {"cj_pid": "CJ123", "title": "Smart Plug WiFi", "image_url": "https://cdn/a.jpg"}
        p2 = {"cj_pid": "CJ123", "title": "NEW! Smart Plug WiFi 2024", "image_url": "https://cdn2/b.jpg"}
        assert product_identity_key(p1) == product_identity_key(p2)

    def test_different_supplier_ids_differ(self):
        assert product_identity_key({"cj_pid": "A"}) != product_identity_key({"cj_pid": "B"})

    def test_field_name_disambiguates(self):
        # cj_pid=123 and product_id=123 must not collide.
        assert product_identity_key({"cj_pid": "123"}) != product_identity_key({"product_id": "123"})

    def test_priority_order_cj_first(self):
        p = {"cj_pid": "CJ1", "product_id": "AE9"}
        assert product_identity_key(p) == product_identity_key({"cj_pid": "CJ1"})

    def test_legacy_fallback_matches_old_formula(self):
        import hashlib
        p = {"title": "Basin Waste 40mm", "image_url": "https://cdn/x.jpg"}
        legacy = hashlib.sha256("basin waste 40mm|https://cdn/x.jpg".encode()).hexdigest()[:32]
        assert product_identity_key(p) == legacy

    def test_writer_and_reader_share_the_key(self):
        from ospra_os.intelligence.product_discovery import _velocity_timeseries_key
        p = {"cj_pid": "CJ42", "title": "t", "image_url": "i"}
        assert cw._product_key(p) == _velocity_timeseries_key(p) == product_identity_key(p)


# ---------------------------------------------------------------------------
# M5 / M2 — catalog_warm transaction + absence snapshots
# ---------------------------------------------------------------------------

@pytest.fixture()
def session():
    # StaticPool: every connection shares ONE in-memory DB — without it, a
    # session.close() inside the code under test would hand the next query a
    # brand-new empty database and the assertions would lie.
    from sqlalchemy.pool import StaticPool
    engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(
        engine, tables=[DiscoveredProduct.__table__, ProductTimeseries.__table__]
    )
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


GOOD = {"cj_pid": "CJ-GOOD", "title": "Smart Plug", "image_url": "i1",
        "grade": "A", "score": 80, "saturation_score": 0.2}


class TestCatalogWarmTransactions:
    def test_one_bad_product_does_not_lose_earlier_rows(self, session, monkeypatch):
        """M5: with per-product commits, rows before a failure survive."""
        products = [dict(GOOD), {"cj_pid": "CJ-BAD", "title": "Bad"},
                    {"cj_pid": "CJ-ALSO-GOOD", "title": "Doorbell", "grade": "B+", "score": 70}]

        real_snapshot = cw.snapshot_timeseries

        def exploding_snapshot(sess, product, niche):
            if product.get("cj_pid") == "CJ-BAD":
                raise RuntimeError("malformed product")
            return real_snapshot(sess, product, niche)

        monkeypatch.setattr(cw, "snapshot_timeseries", exploding_snapshot)
        monkeypatch.setattr(cw, "_session", lambda: session)

        async def fake_discover(niche, count, include_captions=True):
            return products
        import ospra_os.intelligence.product_discovery as pd
        monkeypatch.setattr(pd, "discover_products", fake_discover)

        result = asyncio.run(cw.warm_niche("smart_home"))

        keys = {r.product_key for r in session.query(ProductTimeseries).all()}
        assert product_identity_key(GOOD) in keys, "row BEFORE the bad product must survive"
        assert product_identity_key(products[2]) in keys, "row AFTER the bad product must survive"
        assert result["snapshots"] == 2  # honest counter: only committed rows

    def test_absence_snapshot_written_for_dropped_product(self, session):
        """M2: a recently-seen catalog product missing from today's discovery
        gets a seen_in_discovery=False row with NULL signals."""
        now = datetime.utcnow()
        session.add(DiscoveredProduct(
            product_key="deadbeef" * 4, niche="smart_home", title="Dropped Product",
            first_seen_at=now - timedelta(days=5), last_seen_at=now - timedelta(days=1),
            times_seen=3, created_at=now,
        ))
        session.commit()

        written = cw._snapshot_absent_products(session, "smart_home", seen_keys=set())
        assert written == 1
        row = session.query(ProductTimeseries).one()
        assert row.seen_in_discovery is False
        assert row.signal_count == 0
        assert row.meta_advertiser_count is None
        assert row.grade is None  # stale grades are NOT carried forward

    def test_absence_skips_products_seen_today(self, session):
        now = datetime.utcnow()
        key = "cafebabe" * 4
        session.add(DiscoveredProduct(
            product_key=key, niche="smart_home", title="Seen Today",
            first_seen_at=now, last_seen_at=now, times_seen=1, created_at=now,
        ))
        session.commit()
        assert cw._snapshot_absent_products(session, "smart_home", seen_keys={key}) == 0

    def test_absence_window_excludes_zombies(self, session):
        now = datetime.utcnow()
        session.add(DiscoveredProduct(
            product_key="feedface" * 4, niche="smart_home", title="Zombie",
            first_seen_at=now - timedelta(days=90),
            last_seen_at=now - timedelta(days=cw.ABSENCE_WINDOW_DAYS + 1),
            times_seen=1, created_at=now,
        ))
        session.commit()
        assert cw._snapshot_absent_products(session, "smart_home", seen_keys=set()) == 0

    def test_rediscovery_flips_same_day_absence_row(self, session):
        """An absence row written earlier today flips to seen on rediscovery."""
        now = datetime.utcnow()
        p = dict(GOOD)
        key = cw._product_key(p)
        session.add(DiscoveredProduct(
            product_key=key, niche="smart_home", title="Smart Plug",
            first_seen_at=now - timedelta(days=3), last_seen_at=now - timedelta(days=1),
            times_seen=2, created_at=now,
        ))
        session.commit()
        cw._snapshot_absent_products(session, "smart_home", seen_keys=set())
        assert session.query(ProductTimeseries).one().seen_in_discovery is False

        cw.snapshot_timeseries(session, p, "smart_home")
        session.commit()
        row = session.query(ProductTimeseries).one()
        assert row.seen_in_discovery is True


# ---------------------------------------------------------------------------
# M6 — empty run exits non-zero
# ---------------------------------------------------------------------------

def test_empty_run_exits_nonzero(monkeypatch):
    async def empty_run():
        return {"niches": 5, "discovered": 0, "new": 0, "seen": 0, "snapshots": 0}
    monkeypatch.setattr(cw, "run", empty_run)
    with pytest.raises(SystemExit) as exc:
        cw.main()
    assert exc.value.code == 2


def test_productive_run_exits_zero(monkeypatch):
    async def ok_run():
        return {"niches": 5, "discovered": 12, "new": 3, "seen": 9, "snapshots": 12}
    monkeypatch.setattr(cw, "run", ok_run)
    cw.main()  # no SystemExit


# ---------------------------------------------------------------------------
# M3 / M4 — date-aware slopes, 3-point floor
# ---------------------------------------------------------------------------

class TestSlopeMath:
    def test_gap_aware_slope_not_inflated(self):
        """Two points 10 days apart: +10 over 10 days = slope 1/day, NOT 10/day."""
        assert linear_slope([5, 15], xs=[0, 10]) == pytest.approx(1.0)

    def test_uniform_fallback_unchanged(self):
        assert linear_slope([1, 2, 3, 4]) == pytest.approx(1.0)

    def test_two_points_contribute_no_slope_terms(self):
        """M4: 2 measurements can't trigger fast_filling/demand adjustments."""
        r = velocity_saturation_from_series([8, 20], [100, 300], day_offsets=[0, 1])
        assert r is not None
        assert "fast_filling" not in r["components"]
        assert "demand_rising" not in r["components"]

    def test_three_points_do_contribute(self):
        r = velocity_saturation_from_series([8, 14, 20], [100, 100, 100], day_offsets=[0, 1, 2])
        assert "fast_filling" in r["components"]

    def test_gappy_series_uses_calendar_days(self):
        """Advertisers 8→20 over 12 calendar days (3 snapshots) = ~1/day = 7/wk —
        crosses the >=5/wk demote line but NOT because gaps compressed it."""
        r = velocity_saturation_from_series(
            [8, 14, 20], [None, None, None], day_offsets=[0, 6, 12]
        )
        # slope = 1/day → weekly 7 → fast_filling fires legitimately
        assert r["components"].get("fast_filling") == 0.25
        # same data read gap-blind would be slope 6/day = 42/wk; verify we
        # didn't do that by checking a slow filler over long gaps stays calm:
        slow = velocity_saturation_from_series(
            [8, 10, 12], [None, None, None], day_offsets=[0, 14, 28]
        )
        assert "fast_filling" not in slow["components"]

    def test_none_alignment_keeps_offsets(self):
        """None-dropping must not compact days: demand measured on days 0 and
        13 only, falling — with day offsets the fall is slow (~-7.5%/wk), so
        the demote must NOT fire (gap-blind math would see -50%/step)."""
        r = velocity_saturation_from_series(
            [10, 10, 10], [200, None, 100], day_offsets=[0, 1, 13]
        )
        assert "demand_falling" not in r["components"]


# ---------------------------------------------------------------------------
# S1 — OAuth state
# ---------------------------------------------------------------------------

class TestOAuthState:
    def test_roundtrip_valid(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET_KEY", "s" * 32)
        from ospra_os.aliexpress import routes as r
        state = r._make_oauth_state()
        assert r._verify_oauth_state(state) is True

    def test_missing_and_garbage_rejected(self):
        from ospra_os.aliexpress import routes as r
        assert r._verify_oauth_state(None) is False
        assert r._verify_oauth_state("") is False
        assert r._verify_oauth_state("abc") is False
        assert r._verify_oauth_state("a.b.c") is False

    def test_tampered_signature_rejected(self):
        from ospra_os.aliexpress import routes as r
        state = r._make_oauth_state()
        nonce, exp, sig = state.split(".")
        assert r._verify_oauth_state(f"{nonce}.{exp}.{'0'*32}") is False

    def test_expired_state_rejected(self, monkeypatch):
        from ospra_os.aliexpress import routes as r
        import time as _t
        state = r._make_oauth_state()
        monkeypatch.setattr(_t, "time", lambda: _t.time.__wrapped__() + 10_000 if hasattr(_t.time, "__wrapped__") else 9e12)
        # simpler: craft an already-expired state
        nonce = "n"
        expiry = 1  # 1970
        import hashlib as _h, hmac as _hm
        sig = _hm.new(r._state_secret(), f"{nonce}.{expiry}".encode(), _h.sha256).hexdigest()[:32]
        assert r._verify_oauth_state(f"{nonce}.{expiry}.{sig}") is False

    def test_setup_key_gate(self, monkeypatch):
        from ospra_os.aliexpress import routes as r
        monkeypatch.delenv("AE_OAUTH_SETUP_KEY", raising=False)
        assert r._setup_key_ok("anything") is False   # unset env → closed
        monkeypatch.setenv("AE_OAUTH_SETUP_KEY", "topsecret")
        assert r._setup_key_ok("topsecret") is True
        assert r._setup_key_ok("wrong") is False
        assert r._setup_key_ok(None) is False


# ---------------------------------------------------------------------------
# M8 — AE-DS signed token refresh
# ---------------------------------------------------------------------------

class TestDSRefresh:
    def _client(self, monkeypatch):
        monkeypatch.setenv("ALIEXPRESS_APP_KEY", "520918")
        monkeypatch.setenv("ALIEXPRESS_APP_SECRET", "shhh")
        from ospra_os.aliexpress.ds_client import AliExpressDSClient
        return AliExpressDSClient()

    def _patch_http(self, monkeypatch, response_body, capture):
        class FakeResp:
            def __init__(self, body): self._body = body
            async def json(self, content_type=None): return self._body
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False

        class FakeSession:
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
            def post(self, url, params=None, timeout=None):
                capture["url"] = url
                capture["params"] = params
                return FakeResp(response_body)

        import ospra_os.aliexpress.ds_client as ds
        monkeypatch.setattr(ds.aiohttp, "ClientSession", lambda: FakeSession())

    def _patch_tokens(self, monkeypatch, refresh_token="rt-1"):
        saved = {}
        import ospra_os.database.aliexpress_tokens as tok
        monkeypatch.setattr(tok, "load_token",
                            lambda api_type: {"access_token": "old", "refresh_token": refresh_token})
        monkeypatch.setattr(tok, "save_token",
                            lambda api_type, access_token, refresh_token, expires_in: saved.update(
                                {"access": access_token, "refresh": refresh_token, "exp": expires_in}) or True)
        return saved

    def test_refresh_sends_signed_top_call(self, monkeypatch):
        client = self._client(monkeypatch)
        capture = {}
        saved = self._patch_tokens(monkeypatch)
        self._patch_http(monkeypatch, {
            "top_auth_token_refresh_response": {
                "access_token": "new-at", "refresh_token": "new-rt", "expires_in": 3600}
        }, capture)

        ok = asyncio.run(client._refresh_token())
        assert ok is True
        p = capture["params"]
        assert p["method"] == "/auth/token/refresh"
        assert p["sign_method"] == "sha256"
        assert "sign" in p and len(p["sign"]) == 64  # HMAC-SHA256 hex, uppercased
        assert p["refresh_token"] == "rt-1"
        assert "client_secret" not in p  # never send the raw secret
        assert saved["access"] == "new-at" and saved["refresh"] == "new-rt"
        assert client._access_token == "new-at"

    def test_refresh_handles_error_response(self, monkeypatch):
        client = self._client(monkeypatch)
        self._patch_tokens(monkeypatch)
        self._patch_http(monkeypatch, {
            "error_response": {"code": "InvalidRefreshToken", "msg": "expired"}
        }, {})
        assert asyncio.run(client._refresh_token()) is False

    def test_refresh_without_stored_refresh_token_fails_gracefully(self, monkeypatch):
        client = self._client(monkeypatch)
        import ospra_os.database.aliexpress_tokens as tok
        monkeypatch.setattr(tok, "load_token", lambda api_type: {"access_token": "x"})
        assert asyncio.run(client._refresh_token()) is False


# ---------------------------------------------------------------------------
# Adversarial-review follow-ups (the bugs the mocked tests hid)
# ---------------------------------------------------------------------------

class TestTokenRoundTripUnmocked:
    """The M8 refresh was 'fixed' but unreachable in prod: load_token raised
    TypeError (naive vs aware datetime) on EVERY real row — invisible to the
    earlier tests because they monkeypatched load_token. This round-trip uses
    the REAL save/load path against a real (temp) database."""

    def test_save_then_load_returns_usable_payload(self, tmp_path, monkeypatch):
        db = tmp_path / "tok.db"
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db}")
        # Fresh import so the module binds to the temp DATABASE_URL.
        import importlib
        import ospra_os.database.aliexpress_tokens as tok
        importlib.reload(tok)
        try:
            tok.init_db()
            assert tok.save_token("dropship", "at-1", "rt-1", 3600)
            payload = tok.load_token("dropship")   # must NOT raise TypeError
            assert payload is not None
            assert payload["access_token"] == "at-1"
            assert payload["refresh_token"] == "rt-1"
            assert payload["is_expired"] is False
            assert isinstance(payload["needs_refresh"], bool)

            # Expired token: is_expired flips without raising.
            assert tok.save_token("dropship", "at-2", "rt-2", 1)
            import time as _t
            _t.sleep(1.1)
            payload = tok.load_token("dropship")
            assert payload["is_expired"] is True
        finally:
            importlib.reload(tok)  # restore module state for other tests


class TestAbsenceGating:
    def test_no_absence_rows_on_zero_discovery_run(self, session, monkeypatch):
        """Outage days must NOT be recorded as 'every product vanished'."""
        now = datetime.utcnow()
        session.add(DiscoveredProduct(
            product_key="0" * 32, niche="smart_home", title="Active Product",
            first_seen_at=now - timedelta(days=2), last_seen_at=now - timedelta(days=1),
            times_seen=2, created_at=now,
        ))
        session.commit()

        monkeypatch.setattr(cw, "_session", lambda: session)

        async def dead_sources(niche, count, include_captions=True):
            return []
        import ospra_os.intelligence.product_discovery as pd
        monkeypatch.setattr(pd, "discover_products", dead_sources)

        result = asyncio.run(cw.warm_niche("smart_home"))
        assert result["discovered"] == 0
        assert session.query(ProductTimeseries).count() == 0, \
            "zero-discovery run must write NO absence rows"

    def test_failed_commit_product_not_marked_absent(self, session, monkeypatch):
        """A product discovered today whose persistence failed must not get a
        seen_in_discovery=False row — it did NOT vanish from the market."""
        now = datetime.utcnow()
        bad = {"cj_pid": "CJ-EXPLODES", "title": "Fragile", "image_url": "i"}
        key = cw._product_key(bad)
        session.add(DiscoveredProduct(
            product_key=key, niche="smart_home", title="Fragile",
            first_seen_at=now - timedelta(days=2), last_seen_at=now - timedelta(days=1),
            times_seen=2, created_at=now,
        ))
        session.commit()

        monkeypatch.setattr(cw, "_session", lambda: session)
        real_snapshot = cw.snapshot_timeseries

        def exploding(sess, product, niche):
            if product.get("cj_pid") == "CJ-EXPLODES":
                raise RuntimeError("boom")
            return real_snapshot(sess, product, niche)
        monkeypatch.setattr(cw, "snapshot_timeseries", exploding)

        async def fake_discover(niche, count, include_captions=True):
            return [dict(bad), dict(GOOD)]
        import ospra_os.intelligence.product_discovery as pd
        monkeypatch.setattr(pd, "discover_products", fake_discover)

        asyncio.run(cw.warm_niche("smart_home"))
        rows = {r.product_key: r for r in session.query(ProductTimeseries).all()}
        assert key not in rows or rows[key].seen_in_discovery is True


class TestDemoIdentityFallback:
    def test_demo_product_id_falls_back_to_stable_hash(self):
        """Timestamped demo IDs must not fork identity every run."""
        d1 = {"product_id": "demo_smart_home_1_1750000000", "title": "Demo Plug", "image_url": "d.jpg"}
        d2 = {"product_id": "demo_smart_home_1_1750000999", "title": "Demo Plug", "image_url": "d.jpg"}
        assert product_identity_key(d1) == product_identity_key(d2)


def test_zero_snapshots_with_discoveries_exits_nonzero(monkeypatch):
    """DB dead while APIs healthy = moat clock stopped = red cron."""
    async def db_dead_run():
        return {"niches": 5, "discovered": 40, "new": 0, "seen": 0, "snapshots": 0}
    monkeypatch.setattr(cw, "run", db_dead_run)
    with pytest.raises(SystemExit) as exc:
        cw.main()
    assert exc.value.code == 2
