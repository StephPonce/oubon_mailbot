"""
Shopify Webhook Registry
========================

Handles automatic registration and management of webhooks.
Called after successful OAuth to set up all required webhooks.

Author: Ospra Intelligence
"""

import httpx
import logging
import os
from typing import Dict, List, Any, Optional
from datetime import datetime

from .webhook_utils import WebhookTopics

logger = logging.getLogger(__name__)


class ShopifyWebhookRegistry:
    """
    Manages webhook registration for Shopify stores.
    
    Usage:
        registry = ShopifyWebhookRegistry(shop_domain, access_token)
        result = await registry.register_all_webhooks()
    """
    
    def __init__(
        self,
        shop_domain: str,
        access_token: str,
        webhook_url_base: Optional[str] = None,
        api_version: str = "2024-10"
    ):
        """
        Initialize webhook registry.
        
        Args:
            shop_domain: Store domain (e.g., 'mystore.myshopify.com')
            access_token: Shopify access token
            webhook_url_base: Base URL for webhook endpoints (default: from env)
            api_version: Shopify API version
        """
        # Normalize domain
        if not shop_domain.endswith(".myshopify.com"):
            shop_domain = f"{shop_domain}.myshopify.com"
        
        self.shop_domain = shop_domain
        self.access_token = access_token
        self.api_version = api_version
        
        # Get webhook URL base
        self.webhook_url_base = webhook_url_base or os.getenv(
            "WEBHOOK_URL_BASE",
            os.getenv("RENDER_EXTERNAL_URL", "https://ospra-intelligence-api.onrender.com")
        )
        
        self.base_url = f"https://{shop_domain}/admin/api/{api_version}"
        self.headers = {
            "X-Shopify-Access-Token": access_token,
            "Content-Type": "application/json",
        }
    
    def _get_webhook_address(self, topic: str) -> str:
        """
        Get full webhook URL for a topic.
        
        Converts topic like "orders/paid" to URL path.
        """
        # Convert topic to path: orders/paid -> /webhooks/shopify/orders/paid
        path = topic.replace("/", "/")
        
        # Special handling for GDPR webhooks
        if topic.startswith("customers/") and topic in [
            WebhookTopics.CUSTOMERS_DATA_REQUEST,
            WebhookTopics.CUSTOMERS_REDACT,
        ]:
            return f"{self.webhook_url_base}/webhooks/shopify/gdpr/{topic.replace('/', '/')}"
        
        if topic == WebhookTopics.SHOP_REDACT:
            return f"{self.webhook_url_base}/webhooks/shopify/gdpr/shop/redact"
        
        return f"{self.webhook_url_base}/webhooks/shopify/{path}"
    
    async def register_webhook(
        self,
        topic: str,
        address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Register a single webhook with Shopify.
        
        Args:
            topic: Webhook topic (e.g., "orders/paid")
            address: Optional custom address (default: auto-generated)
        
        Returns:
            Result dictionary with status
        """
        if not address:
            address = self._get_webhook_address(topic)
        
        payload = {
            "webhook": {
                "topic": topic,
                "address": address,
                "format": "json"
            }
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/webhooks.json",
                    headers=self.headers,
                    json=payload
                )
                
                if response.status_code in [200, 201]:
                    webhook_data = response.json().get("webhook", {})
                    logger.info(f"✅ Registered webhook: {topic} -> {address}")
                    return {
                        "topic": topic,
                        "status": "registered",
                        "id": webhook_data.get("id"),
                        "address": address,
                    }
                
                elif response.status_code == 422:
                    # Already exists or validation error
                    error_detail = response.json()
                    if "already" in str(error_detail).lower():
                        logger.info(f"ℹ️ Webhook already exists: {topic}")
                        return {
                            "topic": topic,
                            "status": "already_exists",
                            "address": address,
                        }
                    else:
                        logger.warning(f"⚠️ Validation error for {topic}: {error_detail}")
                        return {
                            "topic": topic,
                            "status": "validation_error",
                            "error": str(error_detail),
                        }
                
                else:
                    logger.error(f"❌ Failed to register {topic}: {response.status_code} - {response.text}")
                    return {
                        "topic": topic,
                        "status": "failed",
                        "error": response.text,
                        "status_code": response.status_code,
                    }
                    
        except Exception as e:
            logger.error(f"❌ Exception registering {topic}: {e}")
            return {
                "topic": topic,
                "status": "error",
                "error": str(e),
            }
    
    async def register_all_webhooks(
        self,
        topics: Optional[List[str]] = None,
        essential_only: bool = False
    ) -> Dict[str, Any]:
        """
        Register all webhooks for a store.
        
        Args:
            topics: Optional list of specific topics to register
            essential_only: If True, only register essential webhooks
        
        Returns:
            Summary of registration results
        """
        if topics:
            topics_to_register = topics
        elif essential_only:
            topics_to_register = WebhookTopics.essential_topics()
        else:
            topics_to_register = WebhookTopics.all_topics()
        
        results = []
        registered = 0
        already_existed = 0
        failed = 0
        
        logger.info(f"📝 Registering {len(topics_to_register)} webhooks for {self.shop_domain}")
        
        for topic in topics_to_register:
            result = await self.register_webhook(topic)
            results.append(result)
            
            if result["status"] == "registered":
                registered += 1
            elif result["status"] == "already_exists":
                already_existed += 1
            else:
                failed += 1
        
        summary = {
            "success": failed == 0,
            "shop": self.shop_domain,
            "total": len(topics_to_register),
            "registered": registered,
            "already_existed": already_existed,
            "failed": failed,
            "webhook_url_base": self.webhook_url_base,
            "details": results,
            "registered_at": datetime.utcnow().isoformat(),
        }
        
        logger.info(
            f"📊 Webhook registration complete: "
            f"{registered} new, {already_existed} existing, {failed} failed"
        )
        
        return summary
    
    async def list_webhooks(self) -> List[Dict[str, Any]]:
        """
        List all registered webhooks for the store.
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/webhooks.json",
                    headers=self.headers
                )
                
                if response.status_code == 200:
                    webhooks = response.json().get("webhooks", [])
                    return [
                        {
                            "id": w["id"],
                            "topic": w["topic"],
                            "address": w["address"],
                            "created_at": w.get("created_at"),
                            "updated_at": w.get("updated_at"),
                        }
                        for w in webhooks
                    ]
                else:
                    logger.error(f"Failed to list webhooks: {response.text}")
                    return []
                    
        except Exception as e:
            logger.error(f"Exception listing webhooks: {e}")
            return []
    
    async def delete_webhook(self, webhook_id: int) -> bool:
        """
        Delete a specific webhook by ID.
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.delete(
                    f"{self.base_url}/webhooks/{webhook_id}.json",
                    headers=self.headers
                )
                
                if response.status_code in [200, 204]:
                    logger.info(f"🗑️ Deleted webhook: {webhook_id}")
                    return True
                else:
                    logger.error(f"Failed to delete webhook {webhook_id}: {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Exception deleting webhook {webhook_id}: {e}")
            return False
    
    async def delete_all_webhooks(self) -> Dict[str, Any]:
        """
        Delete all webhooks for the store.
        Useful for cleanup or re-registration.
        """
        webhooks = await self.list_webhooks()
        
        deleted = 0
        failed = 0
        
        for webhook in webhooks:
            if await self.delete_webhook(webhook["id"]):
                deleted += 1
            else:
                failed += 1
        
        return {
            "deleted": deleted,
            "failed": failed,
            "total": len(webhooks),
        }
    
    async def sync_webhooks(self) -> Dict[str, Any]:
        """
        Sync webhooks - delete old ones, register new ones.
        Ensures webhook configuration is up to date.
        """
        logger.info(f"🔄 Syncing webhooks for {self.shop_domain}")
        
        # Get current webhooks
        current = await self.list_webhooks()
        current_topics = {w["topic"] for w in current}
        
        # Topics we need
        required_topics = set(WebhookTopics.all_topics())
        
        # Find what to add and remove
        topics_to_add = required_topics - current_topics
        
        # Check for outdated addresses
        webhooks_to_update = []
        for webhook in current:
            expected_address = self._get_webhook_address(webhook["topic"])
            if webhook["address"] != expected_address:
                webhooks_to_update.append(webhook)
        
        # Delete webhooks with wrong addresses
        for webhook in webhooks_to_update:
            await self.delete_webhook(webhook["id"])
            topics_to_add.add(webhook["topic"])
        
        # Register missing/updated webhooks
        results = []
        for topic in topics_to_add:
            result = await self.register_webhook(topic)
            results.append(result)
        
        return {
            "synced": True,
            "added": len(topics_to_add),
            "updated": len(webhooks_to_update),
            "current_count": len(current),
            "required_count": len(required_topics),
            "details": results,
        }


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

async def register_webhooks_for_store(
    shop_domain: str,
    access_token: str,
    essential_only: bool = False
) -> Dict[str, Any]:
    """
    Convenience function to register all webhooks for a store.
    
    Call this after OAuth success.
    """
    registry = ShopifyWebhookRegistry(shop_domain, access_token)
    return await registry.register_all_webhooks(essential_only=essential_only)


async def list_store_webhooks(
    shop_domain: str,
    access_token: str
) -> List[Dict[str, Any]]:
    """
    Convenience function to list webhooks for a store.
    """
    registry = ShopifyWebhookRegistry(shop_domain, access_token)
    return await registry.list_webhooks()


async def sync_store_webhooks(
    shop_domain: str,
    access_token: str
) -> Dict[str, Any]:
    """
    Convenience function to sync webhooks for a store.
    """
    registry = ShopifyWebhookRegistry(shop_domain, access_token)
    return await registry.sync_webhooks()
