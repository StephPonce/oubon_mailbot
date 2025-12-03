"""
Shopify Integration Module

Provides:
- ShopifyClient: Direct API interactions
- ProductDeploymentService: AI-powered product deployment
- API Routes: REST endpoints for dashboard

Usage:
    from ospra_os.integrations.shopify import ShopifyClient, ProductDeploymentService
"""

from ospra_os.integrations.shopify.client import ShopifyClient
from ospra_os.integrations.shopify.deployment import ProductDeploymentService

# Routes are imported by main.py directly

__all__ = [
    "ShopifyClient",
    "ProductDeploymentService",
]
