"""
Shopify Integration Module

Provides:
- ShopifyClient: Direct API interactions
- ProductDeploymentService: AI-powered product deployment (optional, requires extra deps)
- API Routes: REST endpoints for dashboard

Usage:
    from ospra_os.integrations.shopify import ShopifyClient
    # ProductDeploymentService only available if all dependencies installed:
    # from ospra_os.integrations.shopify import ProductDeploymentService
"""

from ospra_os.integrations.shopify.client import ShopifyClient

# Make ProductDeploymentService optional - it has heavy dependencies
try:
    from ospra_os.integrations.shopify.deployment import ProductDeploymentService
    __all__ = [
        "ShopifyClient",
        "ProductDeploymentService",
    ]
except ImportError as e:
    # Dependencies not installed - ProductDeploymentService unavailable
    ProductDeploymentService = None
    __all__ = [
        "ShopifyClient",
    ]
