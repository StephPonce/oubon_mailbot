"""
Supplier intake relevance (task #55).

The AE/CJ supplier search returned off-niche junk (awnings, basin waste,
camping lanterns) for smart_home-class queries, and results were accepted
with no relevance check — so the STEP-3b gate had to do demolition. These
pin that off-target results are rejected at INTAKE, leaving a
majority-relevant pool before the gate.
"""

import pytest

from ospra_os.intelligence.product_discovery import ProductDiscoveryEngine


@pytest.fixture()
def engine(monkeypatch):
    monkeypatch.setenv("DISCOVERY_INTAKE_FILTER", "true")
    return ProductDiscoveryEngine.__new__(ProductDiscoveryEngine)


# A realistic AliExpress batch for the query "wifi smart plug": the first two
# genuinely match, the rest are the off-target results AE/keyword-drift surfaced.
AE_BATCH = [
    {"title": "WiFi Smart Plug with Energy Monitoring, Tuya App"},
    {"title": "Mini Smart Plug WiFi Outlet Works with Alexa"},
    {"title": "Basin Waste 40mm Adjustable Height For Bathroom Sink"},
    {"title": "Vintage Outdoor Camping Lantern Portable"},
    {"title": "D8300 Full Box Retractable Awning 2-6m"},
]


class TestQueryOverlapIntake:
    def test_rejects_results_not_matching_query(self, engine):
        kept = engine._filter_supplier_results(AE_BATCH, query="wifi smart plug")
        titles = [p["title"] for p in kept]
        assert len(kept) == 2
        assert all("plug" in t.lower() for t in titles)
        assert not any("basin" in t.lower() or "awning" in t.lower() for t in titles)

    def test_pool_majority_relevant_before_gate(self, engine):
        """Before: 2/5 relevant. After intake: 2/2 relevant (100%)."""
        before = AE_BATCH
        after = engine._filter_supplier_results(before, query="wifi smart plug")
        assert len(before) == 5
        assert len(after) == 2  # demolition happens at intake, not the gate

    def test_generic_query_tokens_dont_leak(self, engine):
        # "smart"/"wireless" are stopwords; matching on them alone is not enough
        batch = [{"title": "Smart Wireless Bluetooth Toilet Seat"}]
        kept = engine._filter_supplier_results(batch, query="smart wireless plug")
        assert kept == []  # only stopword overlap -> rejected

    def test_disabled_via_env(self, engine, monkeypatch):
        monkeypatch.setenv("DISCOVERY_INTAKE_FILTER", "false")
        kept = engine._filter_supplier_results(AE_BATCH, query="wifi smart plug")
        assert len(kept) == len(AE_BATCH)


class TestCategoryNicheIntake:
    def test_cj_category_results_filtered_by_niche(self, engine):
        # CJ category search has no query -> niche relevance applies
        batch = [
            {"title": "Smart Video Doorbell Camera 1080p"},
            {"title": "Basin Waste 40mm Bathroom"},
            {"title": "Retractable Patio Awning"},
        ]
        kept = engine._filter_supplier_results(batch, query="", niche="smart_home")
        titles = [p["title"] for p in kept]
        assert "Smart Video Doorbell Camera 1080p" in titles
        assert not any("Basin" in t or "Awning" in t for t in titles)

    def test_empty_batch_stays_empty(self, engine):
        assert engine._filter_supplier_results([], query="wifi smart plug") == []
