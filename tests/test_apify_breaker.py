"""Apify per-run circuit breaker tests (SaaS cost brief).

Pins the behavior that stops the retry storms: once an actor hits the quota/403
threshold in a run, it's tripped and skipped — no more actor-starts.
"""

import importlib

base = importlib.import_module("ospra_os.product_research.connectors.apify.base_apify")


def setup_function():
    base.reset_apify_budget()


def test_reset_clears_state():
    base._record_apify_quota_fail("foo/bar")
    base.reset_apify_budget()
    assert base.get_apify_budget_report()["quota_failures"] == {}
    assert base.get_apify_budget_report()["tripped_actors"] == []


def test_actor_trips_after_threshold():
    actor = "clockworks/free-tiktok-scraper"
    assert not base.apify_actor_tripped(actor)
    for _ in range(base._APIFY_BREAKER_THRESHOLD):
        base._record_apify_quota_fail(actor)
    assert base.apify_actor_tripped(actor), "actor should trip at threshold"
    report = base.get_apify_budget_report()
    assert actor in report["tripped_actors"]


def test_distinct_actors_trip_independently():
    a, b = "junglee/x", "curious_coder/meta"
    base._record_apify_quota_fail(a)
    # b untouched
    if base._APIFY_BREAKER_THRESHOLD <= 1:
        assert base.apify_actor_tripped(a)
    assert not base.apify_actor_tripped(b)


def test_spend_report_shape():
    r = base.get_apify_budget_report()
    assert set(r.keys()) == {"actor_starts", "quota_failures", "tripped_actors"}
    assert isinstance(r["actor_starts"], int)
