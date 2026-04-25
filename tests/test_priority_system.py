"""
Priority-Based Product Discovery — wiring contract test
========================================================

This test was originally a print-based smoke harness that called the live
discovery engine. We've trimmed it to a deterministic contract test that
just verifies the discovery wiring is intact:

1. ``ProductIntelligenceEngine`` instantiates without external network.
2. The AliExpress client (when credentials are present) exposes the
   attributes the priority logic depends on.
3. ``ProductDiscoveryEngine.discover_products`` is the expected
   coroutine signature so callers don't drift away from it silently.

Live discovery is exercised by the integration suite, not here — this
keeps the unit run hermetic.
"""

import inspect
import logging

from ospra_os.intelligence.product_intelligence import ProductIntelligenceEngine
from ospra_os.intelligence.product_discovery import ProductDiscoveryEngine

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def test_priority_system():
    # 1. Engine instantiates without raising.
    discovery = ProductIntelligenceEngine()

    # 2. AliExpress client wiring contract — when credentials are
    #    available the priority logic reaches in for ``app_key`` and
    #    ``base_url``. When they aren't, the attribute is None and we
    #    fall back to scraping/templates, which is also valid.
    if discovery.aliexpress is not None:
        assert hasattr(discovery.aliexpress, "app_key")
        assert hasattr(discovery.aliexpress, "base_url")

    # 3. Discovery method signature contract.
    sig = inspect.signature(ProductDiscoveryEngine.discover_products)
    params = sig.parameters
    assert "niche" in params, "discover_products must accept `niche`"
    assert "max_products" in params, "discover_products must accept `max_products`"
    assert inspect.iscoroutinefunction(
        ProductDiscoveryEngine.discover_products
    ), "discover_products must be async — callers `await` it"


if __name__ == "__main__":
    test_priority_system()
