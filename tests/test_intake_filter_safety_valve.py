"""Intake filter — the niche-only path must never zero out a healthy batch.

Third of three stacked causes behind "[AE-DS] feed empty/dead for every niche".
The AE DS bestseller feeds are globally scoped by design, so a strict niche gate
can reject 100% of a perfectly good batch. That is indistinguishable from a dead
feed downstream, and silently triggers the affiliate keyword fallback.

_filter_supplier_results' docstring has always promised it "never empties a
non-empty batch to zero on the niche-only path". These tests make that true.
"""

from ospra_os.intelligence.product_discovery import ProductDiscoveryEngine


def _engine() -> ProductDiscoveryEngine:
    return ProductDiscoveryEngine.__new__(ProductDiscoveryEngine)


BATCH = [
    {"title": "Orthopedic Tendon Extractor Surgical Instrument"},
    {"title": "Pool Vacuum Hose Swimming Cleaner"},
]


def test_niche_only_path_keeps_batch_when_gate_rejects_everything():
    eng = _engine()
    eng._passes_niche_gate = lambda p, n: (False, "off_niche")  # type: ignore[method-assign]

    out = eng._filter_supplier_results(list(BATCH), query="", niche="kitchen")

    assert out == BATCH, (
        "a globally-scoped feed must survive the intake gate — STEP-3b trims it"
    )


def test_niche_only_path_still_drops_the_off_niche_subset():
    """The valve is a floor, not an off-switch: partial rejection still trims."""
    eng = _engine()
    eng._passes_niche_gate = lambda p, n: (  # type: ignore[method-assign]
        ("Pool" in p["title"]), "gate"
    )

    out = eng._filter_supplier_results(list(BATCH), query="", niche="outdoor")

    assert [p["title"] for p in out] == ["Pool Vacuum Hose Swimming Cleaner"]


def test_query_path_can_still_drop_everything():
    """A keyword returning 100% unrelated rows SHOULD contribute nothing —
    the valve must not leak into the query-overlap path."""
    eng = _engine()
    eng._title_overlaps_query = lambda title, query: False  # type: ignore[method-assign]

    out = eng._filter_supplier_results(list(BATCH), query="wifi smart plug", niche="smart_home")

    assert out == []
