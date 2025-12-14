"""
Action Executor Service
Handles the actual execution of approved actions.
Each action type has a dedicated executor that interfaces with platform APIs.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class ExecutionResult:
    """Result of an action execution."""

    def __init__(
        self,
        success: bool,
        message: str,
        before_state: Dict[str, Any] = None,
        after_state: Dict[str, Any] = None,
        platform_response: Dict[str, Any] = None,
        error: str = None,
        is_undoable: bool = True,
        undo_payload: Dict[str, Any] = None
    ):
        self.success = success
        self.message = message
        self.before_state = before_state or {}
        self.after_state = after_state or {}
        self.platform_response = platform_response or {}
        self.error = error
        self.is_undoable = is_undoable
        self.undo_payload = undo_payload or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "message": self.message,
            "before_state": self.before_state,
            "after_state": self.after_state,
            "platform_response": self.platform_response,
            "error": self.error,
            "is_undoable": self.is_undoable
        }


class BaseActionExecutor(ABC):
    """Base class for action executors."""

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id

    @abstractmethod
    async def execute(self, action) -> ExecutionResult:
        """Execute the action. Must be implemented by subclasses."""
        pass

    @abstractmethod
    async def undo(self, execution) -> ExecutionResult:
        """Undo a previously executed action."""
        pass


class DeployProductExecutor(BaseActionExecutor):
    """Executes product deployment to Shopify/Amazon."""

    async def execute(self, action) -> ExecutionResult:
        """Deploy a product to the store."""
        from ospra_os.database import Product, Store

        payload = action.payload
        product_id = payload.get("product_id")
        store_id = payload.get("store_id") or action.store_id

        # Get product and store
        product = self.db.query(Product).join(Store).filter(
            Product.id == product_id,
            Store.user_id == self.user_id
        ).first()

        if not product:
            return ExecutionResult(
                success=False,
                message="Product not found",
                error=f"Product {product_id} not found"
            )

        store = self.db.query(Store).filter(
            Store.id == store_id,
            Store.user_id == self.user_id
        ).first()

        if not store:
            return ExecutionResult(
                success=False,
                message="Store not found",
                error=f"Store {store_id} not found"
            )

        # Capture before state
        before_state = {
            "product_id": product.id,
            "status": product.status,
            "store_id": product.store_id,
            "platform_product_id": getattr(product, 'platform_product_id', None)
        }

        try:
            # Route to appropriate platform
            if store.platform == "shopify":
                result = await self._deploy_to_shopify(product, store, payload)
            elif store.platform == "amazon":
                result = await self._deploy_to_amazon(product, store, payload)
            else:
                return ExecutionResult(
                    success=False,
                    message=f"Unsupported platform: {store.platform}",
                    error=f"Platform {store.platform} not supported"
                )

            if result["success"]:
                # Update product
                product.status = "active"
                product.store_id = store.id
                if hasattr(product, 'platform_product_id'):
                    product.platform_product_id = result.get("platform_product_id")
                if hasattr(product, 'platform_url'):
                    product.platform_url = result.get("platform_url")
                if hasattr(product, 'deployed_at'):
                    product.deployed_at = datetime.utcnow()
                self.db.commit()

                # Capture after state
                after_state = {
                    "product_id": product.id,
                    "status": product.status,
                    "store_id": product.store_id,
                    "platform_product_id": result.get("platform_product_id"),
                    "platform_url": result.get("platform_url")
                }

                return ExecutionResult(
                    success=True,
                    message=f"Product deployed to {store.store_name}",
                    before_state=before_state,
                    after_state=after_state,
                    platform_response=result,
                    is_undoable=True,
                    undo_payload={
                        "product_id": product.id,
                        "platform_product_id": result.get("platform_product_id"),
                        "store_id": store.id
                    }
                )
            else:
                return ExecutionResult(
                    success=False,
                    message="Failed to deploy product",
                    before_state=before_state,
                    error=result.get("error", "Unknown error"),
                    platform_response=result
                )

        except Exception as e:
            logger.error(f"Error deploying product {product_id}: {e}")
            return ExecutionResult(
                success=False,
                message="Deployment failed",
                before_state=before_state,
                error=str(e)
            )

    async def _deploy_to_shopify(
        self,
        product,
        store,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Deploy product to Shopify."""
        from ospra_os.integrations.shopify_client import ShopifyClient

        try:
            client = ShopifyClient(
                store_url=store.store_url,
                access_token=store.credentials.get("access_token") if hasattr(store, 'credentials') else None
            )

            # Prepare product data
            product_data = {
                "title": product.product_name if hasattr(product, 'product_name') else product.name,
                "body_html": product.description or "",
                "vendor": "Ospra Store",
                "product_type": getattr(product, 'category', getattr(product, 'niche', 'General')),
                "tags": ",".join(product.tags) if hasattr(product, 'tags') and product.tags else "",
                "variants": [{
                    "price": str(product.price if hasattr(product, 'price') else product.sell_price),
                    "compare_at_price": str(product.compare_at_price) if hasattr(product, 'compare_at_price') and product.compare_at_price else None,
                    "inventory_management": "shopify",
                    "inventory_quantity": payload.get("initial_inventory", 100)
                }],
                "images": [{"src": img} for img in ([product.image_url] if hasattr(product, 'image_url') and product.image_url else [])]
            }

            # Create product in Shopify
            response = await client.create_product(product_data)

            if response and response.get("product"):
                shopify_product = response["product"]
                return {
                    "success": True,
                    "platform_product_id": str(shopify_product["id"]),
                    "platform_url": f"https://{store.store_url}/products/{shopify_product.get('handle', '')}",
                    "response": shopify_product
                }
            else:
                return {
                    "success": False,
                    "error": response.get("errors", "Failed to create product")
                }

        except Exception as e:
            logger.error(f"Shopify deployment error: {e}")
            return {"success": False, "error": str(e)}

    async def _deploy_to_amazon(
        self,
        product,
        store,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Deploy product to Amazon."""
        from ospra_os.integrations.amazon_client import AmazonClient

        try:
            client = AmazonClient(credentials=store.credentials if hasattr(store, 'credentials') else {})

            # Prepare listing data
            listing_data = {
                "title": product.product_name if hasattr(product, 'product_name') else product.name,
                "description": product.description,
                "price": product.price if hasattr(product, 'price') else product.sell_price,
                "quantity": payload.get("initial_inventory", 100),
                "category": getattr(product, 'category', 'General'),
                "images": [product.image_url] if hasattr(product, 'image_url') and product.image_url else []
            }

            response = await client.create_listing(listing_data)

            if response and response.get("success"):
                return {
                    "success": True,
                    "platform_product_id": response.get("asin") or response.get("sku"),
                    "platform_url": response.get("url"),
                    "response": response
                }
            else:
                return {
                    "success": False,
                    "error": response.get("error", "Failed to create listing")
                }

        except Exception as e:
            logger.error(f"Amazon deployment error: {e}")
            return {"success": False, "error": str(e)}

    async def undo(self, execution) -> ExecutionResult:
        """Remove product from store (undo deployment)."""
        from ospra_os.database import Product, Store

        undo_payload = execution.before_state
        product_id = undo_payload.get("product_id")

        product = self.db.query(Product).join(Store).filter(
            Product.id == product_id,
            Store.user_id == self.user_id
        ).first()

        if not product:
            return ExecutionResult(
                success=False,
                message="Product not found",
                error="Cannot undo - product not found"
            )

        store = self.db.query(Store).filter(
            Store.id == product.store_id
        ).first()

        if not store:
            return ExecutionResult(
                success=False,
                message="Store not found",
                error="Cannot undo - store not found"
            )

        try:
            # Remove from platform
            if store.platform == "shopify":
                from ospra_os.integrations.shopify_client import ShopifyClient
                client = ShopifyClient(store.store_url, store.credentials.get("access_token"))
                await client.delete_product(getattr(product, 'platform_product_id', ''))
            elif store.platform == "amazon":
                from ospra_os.integrations.amazon_client import AmazonClient
                client = AmazonClient(credentials=store.credentials)
                await client.delete_listing(getattr(product, 'platform_product_id', ''))

            # Update product status
            before_undo = {
                "status": product.status,
                "store_id": product.store_id,
                "platform_product_id": getattr(product, 'platform_product_id', None)
            }

            product.status = "draft"
            if hasattr(product, 'platform_product_id'):
                product.platform_product_id = None
            if hasattr(product, 'platform_url'):
                product.platform_url = None
            self.db.commit()

            return ExecutionResult(
                success=True,
                message="Product removed from store",
                before_state=before_undo,
                after_state={
                    "status": product.status,
                    "store_id": product.store_id,
                    "platform_product_id": None
                },
                is_undoable=False
            )

        except Exception as e:
            logger.error(f"Error undoing product deployment: {e}")
            return ExecutionResult(
                success=False,
                message="Failed to remove product",
                error=str(e)
            )


class AdjustPriceExecutor(BaseActionExecutor):
    """Executes price adjustments on products."""

    async def execute(self, action) -> ExecutionResult:
        """Adjust product price."""
        from ospra_os.database import Product, Store

        payload = action.payload
        product_id = payload.get("product_id")
        new_price = payload.get("new_price")
        new_compare_at_price = payload.get("new_compare_at_price")

        product = self.db.query(Product).join(Store).filter(
            Product.id == product_id,
            Store.user_id == self.user_id
        ).first()

        if not product:
            return ExecutionResult(
                success=False,
                message="Product not found",
                error=f"Product {product_id} not found"
            )

        # Get current price
        current_price = product.price if hasattr(product, 'price') else getattr(product, 'sell_price', 0)

        # Capture before state
        before_state = {
            "product_id": product.id,
            "sell_price": current_price,
            "compare_at_price": getattr(product, 'compare_at_price', None)
        }

        try:
            # Update in platform if deployed
            platform_updated = False
            if hasattr(product, 'platform_product_id') and product.platform_product_id and product.store_id:
                store = self.db.query(Store).filter(Store.id == product.store_id).first()
                if store:
                    platform_result = await self._update_platform_price(
                        product, store, new_price, new_compare_at_price
                    )
                    platform_updated = platform_result.get("success", False)

                    if not platform_updated:
                        return ExecutionResult(
                            success=False,
                            message="Failed to update price in store",
                            before_state=before_state,
                            error=platform_result.get("error"),
                            platform_response=platform_result
                        )

            # Update product
            old_price = current_price
            if hasattr(product, 'price'):
                product.price = new_price
            if hasattr(product, 'sell_price'):
                product.sell_price = new_price
            if new_compare_at_price and hasattr(product, 'compare_at_price'):
                product.compare_at_price = new_compare_at_price
            self.db.commit()

            # Capture after state
            after_state = {
                "product_id": product.id,
                "sell_price": new_price,
                "compare_at_price": new_compare_at_price
            }

            return ExecutionResult(
                success=True,
                message=f"Price updated from ${old_price:.2f} to ${new_price:.2f}",
                before_state=before_state,
                after_state=after_state,
                is_undoable=True,
                undo_payload={
                    "product_id": product.id,
                    "restore_price": old_price,
                    "restore_compare_at": before_state.get("compare_at_price")
                }
            )

        except Exception as e:
            logger.error(f"Error adjusting price for product {product_id}: {e}")
            return ExecutionResult(
                success=False,
                message="Price adjustment failed",
                before_state=before_state,
                error=str(e)
            )

    async def _update_platform_price(
        self,
        product,
        store,
        new_price: float,
        new_compare_at_price: float = None
    ) -> Dict[str, Any]:
        """Update price in the e-commerce platform."""

        if store.platform == "shopify":
            from ospra_os.integrations.shopify_client import ShopifyClient
            client = ShopifyClient(store.store_url, store.credentials.get("access_token"))

            try:
                # Get variant ID
                product_data = await client.get_product(product.platform_product_id)
                if product_data and product_data.get("product", {}).get("variants"):
                    variant_id = product_data["product"]["variants"][0]["id"]

                    update_data = {"price": str(new_price)}
                    if new_compare_at_price:
                        update_data["compare_at_price"] = str(new_compare_at_price)

                    result = await client.update_variant(variant_id, update_data)
                    return {"success": True, "response": result}
                else:
                    return {"success": False, "error": "Could not find product variant"}

            except Exception as e:
                return {"success": False, "error": str(e)}

        elif store.platform == "amazon":
            from ospra_os.integrations.amazon_client import AmazonClient
            client = AmazonClient(credentials=store.credentials)

            try:
                result = await client.update_price(
                    product.platform_product_id,
                    new_price
                )
                return {"success": result.get("success", False), "response": result}
            except Exception as e:
                return {"success": False, "error": str(e)}

        return {"success": False, "error": f"Unsupported platform: {store.platform}"}

    async def undo(self, execution) -> ExecutionResult:
        """Restore previous price."""

        restore_price = execution.before_state.get("sell_price")
        product_id = execution.before_state.get("product_id")

        if not restore_price:
            return ExecutionResult(
                success=False,
                message="Cannot undo - no previous price recorded",
                error="Missing restore price"
            )

        # Recursively call execute with old price
        from ospra_os.database import Action
        restore_action = type('obj', (object,), {
            'user_id': self.user_id,
            'payload': {
                "product_id": product_id,
                "new_price": restore_price,
                "new_compare_at_price": execution.before_state.get("compare_at_price")
            }
        })()

        return await self.execute(restore_action)


class DeployAdExecutor(BaseActionExecutor):
    """Executes ad campaign deployment."""

    async def execute(self, action) -> ExecutionResult:
        """Deploy an ad campaign."""
        from ospra_os.database import AdCampaign

        payload = action.payload
        campaign_id = payload.get("campaign_id")

        # Get or create campaign
        if campaign_id:
            campaign = self.db.query(AdCampaign).filter(
                AdCampaign.id == campaign_id,
                AdCampaign.user_id == self.user_id
            ).first()
        else:
            # Create new campaign from payload
            campaign = AdCampaign(
                user_id=self.user_id,
                store_id=payload.get("store_id"),
                product_id=payload.get("product_id"),
                campaign_name=payload.get("name", f"AI Campaign {datetime.now().strftime('%Y%m%d')}"),
                platform=payload.get("platform", "meta"),
                daily_budget=payload.get("daily_budget", 20.0),
                status="draft"
            )
            self.db.add(campaign)
            self.db.commit()
            self.db.refresh(campaign)

        if not campaign:
            return ExecutionResult(
                success=False,
                message="Campaign not found",
                error=f"Campaign {campaign_id} not found"
            )

        before_state = {
            "campaign_id": campaign.id,
            "status": campaign.status,
            "platform_campaign_id": getattr(campaign, 'platform_campaign_id', None)
        }

        try:
            # Route to appropriate ad platform
            if campaign.platform == "meta":
                result = await self._deploy_to_meta(campaign, payload)
            else:
                return ExecutionResult(
                    success=False,
                    message=f"Unsupported ad platform: {campaign.platform}",
                    error=f"Platform {campaign.platform} not supported yet"
                )

            if result["success"]:
                campaign.status = "active"
                if hasattr(campaign, 'platform_campaign_id'):
                    campaign.platform_campaign_id = result.get("platform_campaign_id")
                self.db.commit()

                after_state = {
                    "campaign_id": campaign.id,
                    "status": campaign.status,
                    "platform_campaign_id": result.get("platform_campaign_id")
                }

                return ExecutionResult(
                    success=True,
                    message=f"Ad campaign deployed on {campaign.platform}",
                    before_state=before_state,
                    after_state=after_state,
                    platform_response=result,
                    is_undoable=True,
                    undo_payload={
                        "campaign_id": campaign.id,
                        "platform_campaign_id": result.get("platform_campaign_id")
                    }
                )
            else:
                return ExecutionResult(
                    success=False,
                    message="Failed to deploy ad campaign",
                    before_state=before_state,
                    error=result.get("error"),
                    platform_response=result
                )

        except Exception as e:
            logger.error(f"Error deploying ad campaign: {e}")
            return ExecutionResult(
                success=False,
                message="Ad deployment failed",
                before_state=before_state,
                error=str(e)
            )

    async def _deploy_to_meta(
        self,
        campaign,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Deploy campaign to Meta (Facebook/Instagram)."""
        try:
            # Placeholder for Meta Ads integration
            logger.info(f"Deploying Meta campaign: {campaign.campaign_name}")

            # Would integrate with Meta Marketing API
            return {
                "success": True,
                "platform_campaign_id": f"META-{campaign.id}",
                "message": "Campaign created (demo mode)"
            }

        except Exception as e:
            logger.error(f"Meta Ads deployment error: {e}")
            return {"success": False, "error": str(e)}

    async def undo(self, execution) -> ExecutionResult:
        """Pause/stop the ad campaign."""
        from ospra_os.database import AdCampaign

        campaign_id = execution.before_state.get("campaign_id")

        campaign = self.db.query(AdCampaign).filter(
            AdCampaign.id == campaign_id,
            AdCampaign.user_id == self.user_id
        ).first()

        if not campaign:
            return ExecutionResult(
                success=False,
                message="Campaign not found",
                error="Cannot undo - campaign not found"
            )

        campaign.status = "paused"
        self.db.commit()

        return ExecutionResult(
            success=True,
            message="Ad campaign paused",
            after_state={"status": "paused"},
            is_undoable=False
        )


class PauseAdExecutor(BaseActionExecutor):
    """Executes pausing ad campaigns."""

    async def execute(self, action) -> ExecutionResult:
        """Pause an ad campaign."""
        from ospra_os.database import AdCampaign

        payload = action.payload
        campaign_id = payload.get("campaign_id")

        campaign = self.db.query(AdCampaign).filter(
            AdCampaign.id == campaign_id,
            AdCampaign.user_id == self.user_id
        ).first()

        if not campaign:
            return ExecutionResult(
                success=False,
                message="Campaign not found",
                error=f"Campaign {campaign_id} not found"
            )

        before_state = {
            "campaign_id": campaign.id,
            "status": campaign.status
        }

        try:
            # Update local status
            campaign.status = "paused"
            self.db.commit()

            return ExecutionResult(
                success=True,
                message=f"Ad campaign paused",
                before_state=before_state,
                after_state={"campaign_id": campaign.id, "status": "paused"},
                is_undoable=True,
                undo_payload={"campaign_id": campaign.id, "restore_status": "active"}
            )

        except Exception as e:
            logger.error(f"Error pausing campaign {campaign_id}: {e}")
            return ExecutionResult(
                success=False,
                message="Failed to pause campaign",
                before_state=before_state,
                error=str(e)
            )

    async def undo(self, execution) -> ExecutionResult:
        """Resume the paused campaign."""
        from ospra_os.database import AdCampaign

        campaign_id = execution.before_state.get("campaign_id")

        campaign = self.db.query(AdCampaign).filter(
            AdCampaign.id == campaign_id
        ).first()

        if campaign:
            campaign.status = "active"
            self.db.commit()
            return ExecutionResult(
                success=True,
                message="Campaign resumed",
                is_undoable=False
            )

        return ExecutionResult(
            success=False,
            message="Campaign not found",
            error="Cannot undo"
        )


class RestockAlertExecutor(BaseActionExecutor):
    """Handles restock alerts and supplier orders."""

    async def execute(self, action) -> ExecutionResult:
        """Process a restock alert."""
        from ospra_os.database import Product

        payload = action.payload
        product_id = payload.get("product_id")
        order_quantity = payload.get("quantity", 100)

        product = self.db.query(Product).join(Store).filter(
            Product.id == product_id,
            Store.user_id == self.user_id
        ).first()

        if not product:
            return ExecutionResult(
                success=False,
                message="Product not found",
                error=f"Product {product_id} not found"
            )

        before_state = {
            "product_id": product.id,
            "supplier_url": getattr(product, 'supplier_url', None)
        }

        # Just create an alert/notification
        return ExecutionResult(
            success=True,
            message=f"Restock alert created for {product.product_name if hasattr(product, 'product_name') else product.name}",
            before_state=before_state,
            after_state={
                "alert_created": True,
                "recommended_quantity": order_quantity,
                "supplier_url": getattr(product, 'supplier_url', None)
            },
            is_undoable=False
        )

    async def undo(self, execution) -> ExecutionResult:
        """Cannot undo restock orders."""
        return ExecutionResult(
            success=False,
            message="Restock orders cannot be undone",
            error="Not undoable"
        )


class RemoveProductExecutor(BaseActionExecutor):
    """Executes product removal from stores."""

    async def execute(self, action) -> ExecutionResult:
        """Remove a product from the store."""
        from ospra_os.database import Product, Store

        payload = action.payload
        product_id = payload.get("product_id")

        product = self.db.query(Product).join(Store).filter(
            Product.id == product_id,
            Store.user_id == self.user_id
        ).first()

        if not product:
            return ExecutionResult(
                success=False,
                message="Product not found",
                error=f"Product {product_id} not found"
            )

        before_state = {
            "product_id": product.id,
            "status": product.status,
            "store_id": product.store_id,
            "platform_product_id": getattr(product, 'platform_product_id', None),
            "platform_url": getattr(product, 'platform_url', None)
        }

        try:
            # Remove from platform if deployed
            if hasattr(product, 'platform_product_id') and product.platform_product_id and product.store_id:
                store = self.db.query(Store).filter(Store.id == product.store_id).first()

                if store and store.platform == "shopify":
                    from ospra_os.integrations.shopify_client import ShopifyClient
                    client = ShopifyClient(store.store_url, store.credentials.get("access_token"))
                    await client.delete_product(product.platform_product_id)
                elif store and store.platform == "amazon":
                    from ospra_os.integrations.amazon_client import AmazonClient
                    client = AmazonClient(credentials=store.credentials)
                    await client.delete_listing(product.platform_product_id)

            # Update product status
            product.status = "removed"
            if hasattr(product, 'platform_product_id'):
                product.platform_product_id = None
            if hasattr(product, 'platform_url'):
                product.platform_url = None
            self.db.commit()

            return ExecutionResult(
                success=True,
                message=f"Product removed from store",
                before_state=before_state,
                after_state={
                    "product_id": product.id,
                    "status": "removed"
                },
                is_undoable=True,
                undo_payload=before_state
            )

        except Exception as e:
            logger.error(f"Error removing product {product_id}: {e}")
            return ExecutionResult(
                success=False,
                message="Failed to remove product",
                before_state=before_state,
                error=str(e)
            )

    async def undo(self, execution) -> ExecutionResult:
        """Re-deploy the removed product."""
        # Use DeployProductExecutor to re-deploy
        deploy_executor = DeployProductExecutor(self.db, self.user_id)

        restore_action = type('obj', (object,), {
            'user_id': self.user_id,
            'store_id': execution.before_state.get("store_id"),
            'payload': {
                "product_id": execution.before_state.get("product_id"),
                "store_id": execution.before_state.get("store_id")
            }
        })()

        return await deploy_executor.execute(restore_action)


class ActionExecutorFactory:
    """Factory for creating action executors."""

    _executors = {
        "deploy_product": DeployProductExecutor,
        "remove_product": RemoveProductExecutor,
        "adjust_price": AdjustPriceExecutor,
        "deploy_ad": DeployAdExecutor,
        "pause_ad": PauseAdExecutor,
        "restock_alert": RestockAlertExecutor,
    }

    @classmethod
    def get_executor(
        cls,
        action_type: str,
        db: Session,
        user_id: int
    ) -> BaseActionExecutor:
        """Get the appropriate executor for an action type."""

        executor_class = cls._executors.get(action_type)

        if not executor_class:
            raise ValueError(f"Unknown action type: {action_type}")

        return executor_class(db, user_id)

    @classmethod
    def get_supported_actions(cls) -> List[str]:
        """
        Return list of all supported action types.

        Returns:
            List of action type names that can be executed
        """
        return list(cls._executors.keys())

    @classmethod
    def register_executor(cls, action_type: str, executor_class: type):
        """Register a new executor type."""
        cls._executors[action_type] = executor_class
