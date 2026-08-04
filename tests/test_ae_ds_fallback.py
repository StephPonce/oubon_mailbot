"""
AliExpress DS→affiliate RUNTIME fallback (discovery-reliability spec, Step 0).

Root cause pinned here: `is_available()` returns True whenever a DS token
EXISTS — a stale `ALIEXPRESS_ACCESS_TOKEN` env passes that check and then dies
at call time (IllegalAccessToken, no refresh_token to self-heal). The affiliate
keyword search used to live behind an `elif` on that init-time flag, so a
dead-but-present DS token zeroed out ALL AliExpress sourcing (June 29 → July 15
prod outage: the June 29 catalog was built by the affiliate path; adding the
stopgap env token flipped discovery into the DS-only branch and starved it).

These tests pin the fix: the affiliate keyword search fires at RUNTIME when the
DS feed yields nothing, and stays quiet when DS is healthy.
"""

import asyncio

from ospra_os.intelligence.product_discovery import ProductDiscoveryEngine


class FakeDS:
    def __init__(self, result=None, exc=None):
        self.result = result or []
        self.exc = exc
        self.calls = 0
        self.feed_names: list = []

    # Signature must mirror the real AliExpressDSClient.get_hot_products —
    # a drifted double silently sends every call down the exception path
    # (TypeError caught by _fetch_aliexpress_ds) and the affiliate fallback
    # then hides it by returning plausible results.
    async def get_hot_products(self, feed_name=None, page_size=None, category_ids=None):
        self.calls += 1
        self.feed_names.append(feed_name)
        if self.exc:
            raise self.exc
        return [dict(p) for p in self.result]


def _engine(ds_available, affiliate_available, ds=None, affiliate_results=None):
    """Bare engine instance — only the attrs _fetch_aliexpress_ds touches."""
    eng = ProductDiscoveryEngine.__new__(ProductDiscoveryEngine)
    eng.aliexpress_ds_available = ds_available
    eng.aliexpress_available = affiliate_available
    eng.aliexpress_ds = ds
    eng.affiliate_calls = []

    async def fake_affiliate(keyword, count):
        eng.affiliate_calls.append((keyword, count))
        return [dict(p) for p in (affiliate_results or [])]

    eng._fetch_aliexpress = fake_affiliate
    # Identity filter: these tests pin the fallback contract, not the gate.
    eng._filter_supplier_results = lambda products, query="", niche=None: products
    return eng


DS_PRODUCT = {"title": "DS Hot Product", "product_id": "ds1"}
AFF_PRODUCT = {"title": "Affiliate Smart Plug", "product_id": "aff1"}


def test_dead_ds_call_falls_back_to_affiliate():
    """DS 'available' (stale token) but the CALL dies → affiliate runs."""
    eng = _engine(
        ds_available=True,
        affiliate_available=True,
        ds=FakeDS(exc=RuntimeError("IllegalAccessToken")),
        affiliate_results=[AFF_PRODUCT],
    )
    out = asyncio.run(eng._fetch_aliexpress_ds(
        "smart_home", count=20,
        fallback_keywords=["wifi smart plug", "video doorbell"], fallback_per_kw=10,
    ))
    assert [p["product_id"] for p in out] == ["aff1", "aff1"]  # one per keyword
    assert eng.affiliate_calls == [("wifi smart plug", 10), ("video doorbell", 10)]


def test_empty_ds_feed_falls_back_to_affiliate():
    """DS answers politely with nothing (capped/empty feed) → affiliate runs."""
    eng = _engine(
        ds_available=True, affiliate_available=True,
        ds=FakeDS(result=[]), affiliate_results=[AFF_PRODUCT],
    )
    out = asyncio.run(eng._fetch_aliexpress_ds(
        "smart_home", count=20, fallback_keywords=["wifi smart plug"], fallback_per_kw=5,
    ))
    assert len(out) == 1 and out[0]["product_id"] == "aff1"


def test_ds_feed_is_gated_off_by_default(monkeypatch):
    """DS rows carry raw AE fields but no cost_price/suggested_price/profit —
    those are computed in the AFFILIATE path (_fetch_aliexpress). Until DS rows
    share that normalisation, a working feed would SUPPRESS the affiliate
    fallback and hand the pipeline unpriceable rows (measured live: AE 9 -> 0).
    So the feed stays off unless AE_DS_FEED_ENABLED is set."""
    monkeypatch.delenv("AE_DS_FEED_ENABLED", raising=False)
    eng = _engine(
        ds_available=True, affiliate_available=True,
        ds=FakeDS(result=[DS_PRODUCT]), affiliate_results=[AFF_PRODUCT],
    )
    out = asyncio.run(eng._fetch_aliexpress_ds(
        "smart_home", count=20, fallback_keywords=["wifi smart plug"], fallback_per_kw=5,
    ))
    assert [p["product_id"] for p in out] == ["aff1"], "must use the priced affiliate path"
    assert eng.aliexpress_ds.calls == 0, "gated off — the feed must not even be called"


def test_healthy_ds_feed_never_touches_affiliate(monkeypatch):
    """DS produced products → the affiliate fallback must NOT fire (spend guard).
    Only applies when the feed is explicitly enabled."""
    monkeypatch.setenv("AE_DS_FEED_ENABLED", "true")
    eng = _engine(
        ds_available=True, affiliate_available=True,
        ds=FakeDS(result=[DS_PRODUCT]), affiliate_results=[AFF_PRODUCT],
    )
    out = asyncio.run(eng._fetch_aliexpress_ds(
        "smart_home", count=20, fallback_keywords=["wifi smart plug"], fallback_per_kw=5,
    ))
    assert [p["product_id"] for p in out] == ["ds1"]
    assert eng.affiliate_calls == []
    # The niche must select a VERIFIED feed name. "DS_Global_topsellers" is not
    # a valid feed for this app; an invalid name returns empty exactly like a
    # dead feed, which is what hid this for months.
    assert eng.aliexpress_ds.feed_names == ["DS_ConsumerElectronics_bestsellers"]
    # DS products keep the niche/source tagging the downstream readers expect.
    assert out[0]["niche"] == "smart_home"
    assert out[0]["source"] == "aliexpress"


def test_ds_unavailable_uses_affiliate_fallback():
    """No DS token at all but affiliate is up → fallback still sources."""
    eng = _engine(
        ds_available=False, affiliate_available=True,
        ds=None, affiliate_results=[AFF_PRODUCT],
    )
    out = asyncio.run(eng._fetch_aliexpress_ds(
        "smart_home", count=20, fallback_keywords=["wifi smart plug"], fallback_per_kw=5,
    ))
    assert len(out) == 1 and out[0]["product_id"] == "aff1"


def test_everything_dead_returns_empty_not_crash():
    eng = _engine(ds_available=True, affiliate_available=False,
                  ds=FakeDS(exc=RuntimeError("IllegalAccessToken")))
    out = asyncio.run(eng._fetch_aliexpress_ds(
        "smart_home", count=20, fallback_keywords=["wifi smart plug"], fallback_per_kw=5,
    ))
    assert out == []


def test_one_failing_affiliate_keyword_does_not_kill_the_rest():
    """gather(return_exceptions=True): a raising keyword search loses only
    its own slice."""
    eng = _engine(ds_available=True, affiliate_available=True, ds=FakeDS(result=[]))

    async def flaky_affiliate(keyword, count):
        if keyword == "bad":
            raise RuntimeError("AE 429")
        return [dict(AFF_PRODUCT)]

    eng._fetch_aliexpress = flaky_affiliate
    out = asyncio.run(eng._fetch_aliexpress_ds(
        "smart_home", count=20, fallback_keywords=["bad", "good"], fallback_per_kw=5,
    ))
    assert len(out) == 1 and out[0]["product_id"] == "aff1"
