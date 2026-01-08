"""
Ospra Intelligence Module
=========================

The core intelligence engine for Ospra OS.

Main Components:
- ProductDiscoveryEngine: Multi-source product discovery (10 data sources)
- ClaudeAdvisor: AI-powered business insights
- BriefingEngine: Daily/weekly briefings
- OpportunityScorer: Anti-saturation scoring

Usage:
    from ospra_os.intelligence import ProductDiscoveryEngine, get_engine
    
    engine = get_engine()
    products = await engine.discover_products(niche="smart_home")
"""

# Main discovery engine
from ospra_os.intelligence.product_discovery import (
    ProductDiscoveryEngine,
    get_engine,
    discover_products,
)

# Backward compatibility aliases
from ospra_os.intelligence.product_discovery import (
    ProductDiscoveryEngine as ProductIntelligenceEngine,
    ProductDiscoveryEngine as OspraIntelligenceEngine,
    ProductDiscoveryEngine as UnifiedProductDiscoveryV3,
)

__all__ = [
    'ProductDiscoveryEngine',
    'ProductIntelligenceEngine',
    'OspraIntelligenceEngine',
    'UnifiedProductDiscoveryV3',
    'get_engine',
    'discover_products',
]
