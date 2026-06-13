"""
Niche relevance gate tests (task #54).

The prod probe of /api/discovery/quick/smart_home surfaced plush slippers,
holiday flags, and a neck pillow inside the smart_home niche. These pin the
gate that must reject those while keeping genuine smart_home products —
including branded ones whose titles don't literally contain "smart".
"""

import pytest

from ospra_os.intelligence.product_discovery import ProductDiscoveryEngine


@pytest.fixture()
def engine(monkeypatch):
    monkeypatch.setenv("DISCOVERY_RELEVANCE_GATE", "true")
    # __init__ wires up live connectors; we only need the pure gate methods,
    # so build a bare instance without running heavy init.
    return ProductDiscoveryEngine.__new__(ProductDiscoveryEngine)


def gate(engine, title, niche="smart_home", category=None):
    product = {"title": title}
    if category:
        product["category_name"] = category
    return engine._passes_niche_gate(product, niche)


class TestSmartHomeGate:
    @pytest.mark.parametrize("title", [
        "Womens Plush Home Slippers Winter Thick Soles",
        "Holiday Home Decorative Flags",
        "Neck Support Anti-lower Head Neck Forward Leaning Pillow",
    ])
    def test_off_niche_products_rejected(self, engine, title):
        passed, reason = gate(engine, title)
        assert passed is False, f"{title!r} should be rejected (got {reason})"

    @pytest.mark.parametrize("title", [
        "WiFi Smart Plug with Energy Monitoring",
        "Smart Video Doorbell Camera 1080p",
        "Robot Vacuum Cleaner with Mapping",
        "Motion Sensor PIR Detector Alarm",
        "Smart Door Lock Fingerprint",
    ])
    def test_genuine_smart_home_products_pass(self, engine, title):
        passed, reason = gate(engine, title)
        assert passed is True, f"{title!r} should pass (got {reason})"

    @pytest.mark.parametrize("title", [
        # Live /api/discovery/quick/smart_home probe (2026-06-13): each of these
        # slipped through the gate on a single generic include token — "plug"
        # (sink plug), "light" (camping lantern), "bluetooth"/"camera" (wearables).
        # The exclude-vocabulary tightening must reject them at the gate.
        "Basin Waste   40mm Adjustable Height For Bathroom, Universal Sink Plug - Black",
        "Vintage Outdoor Camping Lantern, Portable Kerosene Lamp Style Light, LED Tent Light",
        "8MP Camera Smart Eyewear, AI Translation Bluetooth Glasses, Recording Sunglasses",
        "2-in-1 Smart Watch & Bluetooth Earphones, MP3 Player, Heart Rate Sleep Monitor",
    ])
    def test_word_collision_offniche_rejected(self, engine, title):
        passed, reason = gate(engine, title)
        assert passed is False, f"{title!r} should be rejected (got {reason})"
        assert reason == "exclude_match"

    def test_collision_tokens_still_pass_genuine_products(self, engine):
        # The collision tokens (plug/light/camera) MUST remain valid for real
        # smart_home products — the fix excludes the off-niche *category* words,
        # not the include tokens themselves.
        for title in [
            "WiFi Smart Plug with Energy Monitoring",
            "Smart Bulb Dimmable WiFi LED Light",
            "Smart Video Doorbell Camera 1080p",
            "LED Light Strip RGB WiFi",
        ]:
            passed, reason = gate(engine, title)
            assert passed is True, f"{title!r} should still pass (got {reason})"

    def test_neck_pillow_hits_exclude(self, engine):
        # "pillow" is an explicit exclude term for smart_home
        passed, reason = gate(engine, "Memory Foam Neck Pillow")
        assert passed is False
        assert reason == "exclude_match"

    def test_branded_product_passes_via_category(self, engine):
        # A branded title with no niche keyword still passes if its category does
        passed, reason = gate(
            engine, "Aosu Life E10", category="Security Camera System"
        )
        assert passed is True
        assert reason == "category_match"

    def test_unknown_niche_not_gated(self, engine):
        passed, reason = gate(engine, "Random Product", niche="nonexistent_niche")
        assert passed is True
        assert reason == "no_vocab"

    def test_gate_can_be_disabled(self, engine, monkeypatch):
        monkeypatch.setenv("DISCOVERY_RELEVANCE_GATE", "false")
        passed, reason = gate(engine, "Plush Slippers")
        assert passed is True
        assert reason == "gate_disabled"


class TestApplyGate:
    def test_filters_pool_and_keeps_relevant(self, engine):
        pool = [
            {"title": "WiFi Smart Plug"},
            {"title": "Plush Winter Slippers"},
            {"title": "Smart Video Doorbell"},
            {"title": "Holiday Decorative Flags"},
        ]
        kept = engine._apply_niche_gate(pool, "smart_home")
        titles = {p["title"] for p in kept}
        assert titles == {"WiFi Smart Plug", "Smart Video Doorbell"}

    def test_safety_valve_keeps_all_if_gate_empties_pool(self, engine):
        # An all-off-niche pool would empty out; the safety valve keeps it
        # rather than returning nothing (discovery must not go dark).
        pool = [{"title": "Plush Slippers"}, {"title": "Holiday Flags"}]
        kept = engine._apply_niche_gate(pool, "smart_home")
        assert len(kept) == 2  # kept unfiltered with a logged warning

    def test_empty_pool_stays_empty(self, engine):
        assert engine._apply_niche_gate([], "smart_home") == []
