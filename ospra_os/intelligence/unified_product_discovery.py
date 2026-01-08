"""
Unified Product Discovery - Backward Compatibility Module
==========================================================

This module provides backward compatibility for code that imports from:
- ospra_os.intelligence.unified_product_discovery

All classes now alias to ProductDiscoveryEngine in product_discovery.py
"""

from ospra_os.intelligence.product_discovery import (
    ProductDiscoveryEngine,
    get_engine,
    discover_products,
)

# Backward compatibility aliases
UnifiedProductDiscoveryV3 = ProductDiscoveryEngine
UnifiedProductDiscoveryV2 = ProductDiscoveryEngine
UnifiedProductDiscovery = ProductDiscoveryEngine

# Legacy function names
get_discovery_engine = get_engine
discover_live_products = discover_products
get_live_products = discover_products

__all__ = [
    'ProductDiscoveryEngine',
    'UnifiedProductDiscoveryV3',
    'UnifiedProductDiscoveryV2',
    'UnifiedProductDiscovery',
    'get_engine',
    'get_discovery_engine',
    'discover_products',
    'discover_live_products',
    'get_live_products',
]
