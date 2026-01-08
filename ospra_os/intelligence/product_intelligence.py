"""
Product Intelligence - Backward Compatibility Module
=====================================================

This module provides backward compatibility for code that imports from:
- ospra_os.intelligence.product_intelligence

All classes now alias to ProductDiscoveryEngine in product_discovery.py
"""

from ospra_os.intelligence.product_discovery import (
    ProductDiscoveryEngine,
    get_engine,
    discover_products,
)

# Backward compatibility aliases
ProductIntelligenceEngine = ProductDiscoveryEngine
OspraIntelligenceEngine = ProductDiscoveryEngine

__all__ = [
    'ProductDiscoveryEngine',
    'ProductIntelligenceEngine', 
    'OspraIntelligenceEngine',
    'get_engine',
    'discover_products',
]
