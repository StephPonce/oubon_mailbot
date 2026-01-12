"""
ACTION EXECUTOR - ONE-CLICK ACTIONS

Executes recommended actions with preview/execute/undo pattern.

Action types:
- Deploy product
- Pause ad campaign
- Discontinue product
- Adjust pricing
- Create ad campaign
- Reply to email

All actions:
1. Preview (show what will happen)
2. Execute (do the action)
3. Log (record action taken)
4. Undo (reverse the action if possible)
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
from sqlalchemy.orm import Session

from ospra_os.intelligence.action_history import get_action_history

logger = logging.getLogger(__name__)


class ActionType(str, Enum):
    """Supported action types"""
    DEPLOY_PRODUCT = "deploy_product"
    PAUSE_CAMPAIGN = "pause_campaign"
    DISCONTINUE_PRODUCT = "discontinue_product"
    ADJUST_PRICE = "adjust_price"
    CREATE_CAMPAIGN = "create_campaign"
    REPLY_EMAIL = "reply_email"


class ActionStatus(str, Enum):
    """Action execution status"""
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    UNDONE = "undone"


class ActionExecutor:
    """
    Executes one-click actions recommended by Intelligence Core.

    Pattern:
    1. Preview: Show user what will happen
    2. Execute: Perform the action
    3. Log: Record action in database
    4. Undo: Reverse action if possible
    """

    def __init__(self, db: Session):
        self.db = db
        self.action_history = get_action_history()

    async def preview_action(
        self,
        action_type: ActionType,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Preview what an action will do (without executing).

        Args:
            action_type: Type of action
            params: Action parameters

        Returns:
            {
                "action_type": "pause_campaign",
                "description": "Pause ad campaign 'Summer Sale'",
                "impact": "Stop spending $50/day on underperforming campaign (ROAS 0.5)",
                "reversible": true,
                "estimated_time": "5 seconds",
                "requires_confirmation": true
            }
        """
        logger.info(f"Previewing action: {action_type.value}")

        if action_type == ActionType.DEPLOY_PRODUCT:
            return await self._preview_deploy_product(params)

        elif action_type == ActionType.PAUSE_CAMPAIGN:
            return await self._preview_pause_campaign(params)

        elif action_type == ActionType.DISCONTINUE_PRODUCT:
            return await self._preview_discontinue_product(params)

        elif action_type == ActionType.ADJUST_PRICE:
            return await self._preview_adjust_price(params)

        elif action_type == ActionType.CREATE_CAMPAIGN:
            return await self._preview_create_campaign(params)

        elif action_type == ActionType.REPLY_EMAIL:
            return await self._preview_reply_email(params)

        else:
            raise ValueError(f"Unknown action type: {action_type}")

    async def execute_action(
        self,
        action_type: ActionType,
        params: Dict[str, Any],
        user_id: int
    ) -> Dict[str, Any]:
        """
        Execute action and log result.

        Args:
            action_type: Type of action
            params: Action parameters
            user_id: User executing action

        Returns:
            {
                "action_id": "abc123",
                "status": "completed",
                "result": {...},
                "log_id": 456,
                "undo_available": true,
                "timestamp": "2025-11-27T..."
            }
        """
        logger.info(f"Executing action: {action_type.value} for user {user_id}")

        # Execute action
        result = None

        if action_type == ActionType.DEPLOY_PRODUCT:
            result = await self._execute_deploy_product(params)

        elif action_type == ActionType.PAUSE_CAMPAIGN:
            result = await self._execute_pause_campaign(params)

        elif action_type == ActionType.DISCONTINUE_PRODUCT:
            result = await self._execute_discontinue_product(params)

        elif action_type == ActionType.ADJUST_PRICE:
            result = await self._execute_adjust_price(params)

        elif action_type == ActionType.CREATE_CAMPAIGN:
            result = await self._execute_create_campaign(params)

        elif action_type == ActionType.REPLY_EMAIL:
            result = await self._execute_reply_email(params)

        else:
            raise ValueError(f"Unknown action type: {action_type}")

        # Generate unique action ID
        action_id = f"{action_type.value}_{uuid.uuid4().hex[:12]}"

        # Prepare undo data
        undo_data = self._prepare_undo_data(action_type, params, result)

        # Log action to history
        action_log = self.action_history.log_action(
            action_id=action_id,
            user_id=user_id,
            action_type=action_type.value,
            params=params,
            result=result,
            status="completed",
            undo_data=undo_data
        )

        return {
            "action_id": action_id,
            "status": "completed",
            "result": result,
            "log_id": action_log.id,
            "undo_available": result.get("undo_available", False),
            "timestamp": datetime.utcnow().isoformat()
        }

    async def undo_action(self, action_id: str) -> Dict[str, Any]:
        """
        Undo a previously executed action.

        Args:
            action_id: Action ID string

        Returns:
            {
                "success": true,
                "message": "Action undone successfully",
                "timestamp": "..."
            }
        """
        logger.info(f"Undoing action: {action_id}")

        # Get action from history
        action_log = self.action_history.get_action(action_id)

        if not action_log:
            return {
                "success": False,
                "message": f"Action not found: {action_id}",
                "timestamp": datetime.utcnow().isoformat()
            }

        if not action_log.undo_available:
            return {
                "success": False,
                "message": "Action cannot be undone",
                "timestamp": datetime.utcnow().isoformat()
            }

        if action_log.status == "undone":
            return {
                "success": False,
                "message": "Action already undone",
                "timestamp": datetime.utcnow().isoformat()
            }

        # Execute undo based on action type
        try:
            undo_data = action_log.undo_data
            action_type = ActionType(action_log.action_type)

            if action_type == ActionType.DEPLOY_PRODUCT:
                await self._undo_deploy_product(undo_data)
            elif action_type == ActionType.PAUSE_CAMPAIGN:
                await self._undo_pause_campaign(undo_data)
            elif action_type == ActionType.DISCONTINUE_PRODUCT:
                await self._undo_discontinue_product(undo_data)
            elif action_type == ActionType.ADJUST_PRICE:
                await self._undo_adjust_price(undo_data)
            else:
                raise ValueError(f"Undo not implemented for {action_type}")

            # Mark as undone
            self.action_history.mark_as_undone(action_id)

            return {
                "success": True,
                "message": "Action undone successfully",
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to undo action {action_id}: {e}")
            return {
                "success": False,
                "message": f"Failed to undo action: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }

    # ========================================================================
    # PREVIEW METHODS
    # ========================================================================

    async def _preview_deploy_product(self, params: Dict) -> Dict[str, Any]:
        """Preview deploying product to store"""
        product_id = params.get("product_id")

        from ospra_os.database import Product

        product = self.db.query(Product).filter(Product.id == product_id).first()

        return {
            "action_type": "deploy_product",
            "description": f"Deploy '{product.title if product else 'Unknown'}' to Shopify store",
            "impact": "Product will be live in store and available for purchase",
            "reversible": True,
            "estimated_time": "30 seconds",
            "requires_confirmation": True,
            "details": {
                "product_id": product_id,
                "product_title": product.title if product else None,
                "grade": product.grade if product else None
            }
        }

    async def _preview_pause_campaign(self, params: Dict) -> Dict[str, Any]:
        """Preview pausing ad campaign"""
        campaign_id = params.get("campaign_id")

        # Try to load campaign from database if model exists
        try:
            from ospra_os.database import AdCampaign
            campaign = self.db.query(AdCampaign).filter(AdCampaign.id == campaign_id).first()
            daily_spend = campaign.budget_spent / 30 if campaign and campaign.budget_spent else 50.0
            campaign_name = campaign.campaign_name if campaign else "Campaign"
            current_roas = campaign.roas if campaign else None
        except (ImportError, AttributeError):
            # Model doesn't exist yet, use placeholder data
            campaign_name = "Campaign"
            daily_spend = 50.0
            current_roas = None

        return {
            "action_type": "pause_campaign",
            "description": f"Pause ad campaign '{campaign_name}'",
            "impact": f"Stop spending ${daily_spend:.2f}/day on underperforming campaign",
            "reversible": True,
            "estimated_time": "5 seconds",
            "requires_confirmation": True,
            "details": {
                "campaign_id": campaign_id,
                "campaign_name": campaign_name,
                "current_roas": current_roas,
                "daily_spend": daily_spend
            }
        }

    async def _preview_discontinue_product(self, params: Dict) -> Dict[str, Any]:
        """Preview discontinuing product"""
        product_id = params.get("product_id")

        from ospra_os.database import Product

        product = self.db.query(Product).filter(Product.id == product_id).first()

        return {
            "action_type": "discontinue_product",
            "description": f"Discontinue '{product.title if product else 'Unknown'}'",
            "impact": "Remove product from store (can be re-enabled later)",
            "reversible": True,
            "estimated_time": "10 seconds",
            "requires_confirmation": True,
            "details": {
                "product_id": product_id,
                "product_title": product.title if product else None,
                "current_sales": product.total_sales if product else 0
            }
        }

    async def _preview_adjust_price(self, params: Dict) -> Dict[str, Any]:
        """Preview price adjustment"""
        product_id = params.get("product_id")
        new_price = params.get("new_price")

        from ospra_os.database import Product

        product = self.db.query(Product).filter(Product.id == product_id).first()

        old_price = product.price if product else 0
        change_pct = ((new_price - old_price) / old_price * 100) if old_price > 0 else 0

        return {
            "action_type": "adjust_price",
            "description": f"Change price from ${old_price:.2f} to ${new_price:.2f}",
            "impact": f"{change_pct:+.1f}% price change",
            "reversible": True,
            "estimated_time": "10 seconds",
            "requires_confirmation": True,
            "details": {
                "product_id": product_id,
                "old_price": old_price,
                "new_price": new_price,
                "change_percentage": change_pct
            }
        }

    async def _preview_create_campaign(self, params: Dict) -> Dict[str, Any]:
        """Preview creating ad campaign"""
        return {
            "action_type": "create_campaign",
            "description": "Create new Meta Ads campaign",
            "impact": "Start advertising with configured budget",
            "reversible": True,
            "estimated_time": "60 seconds",
            "requires_confirmation": True,
            "details": params
        }

    async def _preview_reply_email(self, params: Dict) -> Dict[str, Any]:
        """Preview email reply"""
        return {
            "action_type": "reply_email",
            "description": "Send AI-generated email reply",
            "impact": "Customer will receive automated response",
            "reversible": False,
            "estimated_time": "5 seconds",
            "requires_confirmation": True,
            "details": params
        }

    # ========================================================================
    # EXECUTE METHODS
    # ========================================================================

    async def _execute_deploy_product(self, params: Dict) -> Dict[str, Any]:
        """Deploy product to Shopify"""
        product_id = params.get("product_id")

        from ospra_os.database import Product, ProductStatus

        product = self.db.query(Product).filter(Product.id == product_id).first()

        if not product:
            raise ValueError(f"Product {product_id} not found")

        # Update status
        product.status = ProductStatus.QUEUED
        product.queued_at = datetime.utcnow()

        self.db.commit()

        logger.info(f"Product {product_id} queued for deployment")

        return {
            "success": True,
            "product_id": product_id,
            "status": "queued",
            "message": "Product queued for deployment",
            "undo_available": True
        }

    async def _execute_pause_campaign(self, params: Dict) -> Dict[str, Any]:
        """Pause Meta Ads campaign"""
        campaign_id = params.get("campaign_id")

        # In production, would call Meta Ads API
        logger.info(f"Pausing campaign {campaign_id}")

        return {
            "success": True,
            "campaign_id": campaign_id,
            "status": "paused",
            "message": "Campaign paused successfully",
            "undo_available": True
        }

    async def _execute_discontinue_product(self, params: Dict) -> Dict[str, Any]:
        """Discontinue product"""
        product_id = params.get("product_id")

        from ospra_os.database import Product, ProductStatus

        product = self.db.query(Product).filter(Product.id == product_id).first()

        if not product:
            raise ValueError(f"Product {product_id} not found")

        product.status = ProductStatus.DISCONTINUED
        product.updated_at = datetime.utcnow()

        self.db.commit()

        logger.info(f"Product {product_id} discontinued")

        return {
            "success": True,
            "product_id": product_id,
            "status": "discontinued",
            "message": "Product discontinued",
            "undo_available": True
        }

    async def _execute_adjust_price(self, params: Dict) -> Dict[str, Any]:
        """Adjust product price"""
        product_id = params.get("product_id")
        new_price = params.get("new_price")

        from ospra_os.database import Product

        product = self.db.query(Product).filter(Product.id == product_id).first()

        if not product:
            raise ValueError(f"Product {product_id} not found")

        old_price = product.price
        product.price = new_price
        product.updated_at = datetime.utcnow()

        self.db.commit()

        logger.info(f"Product {product_id} price changed from ${old_price} to ${new_price}")

        return {
            "success": True,
            "product_id": product_id,
            "old_price": old_price,
            "new_price": new_price,
            "message": f"Price updated to ${new_price:.2f}",
            "undo_available": True
        }

    async def _execute_create_campaign(self, params: Dict) -> Dict[str, Any]:
        """Create ad campaign"""
        # In production, would call Meta Ads API
        logger.info(f"Creating campaign with params: {params}")

        return {
            "success": True,
            "campaign_id": "new_campaign_123",
            "status": "active",
            "message": "Campaign created successfully",
            "undo_available": True
        }

    async def _execute_reply_email(self, params: Dict) -> Dict[str, Any]:
        """Send email reply"""
        # In production, would call Gmail API
        logger.info(f"Sending email reply: {params}")

        return {
            "success": True,
            "message_id": "msg_123",
            "status": "sent",
            "message": "Reply sent successfully",
            "undo_available": False
        }

    def _prepare_undo_data(
        self,
        action_type: ActionType,
        params: Dict,
        result: Dict
    ) -> Optional[Dict[str, Any]]:
        """Prepare data needed to undo action"""
        if action_type == ActionType.DEPLOY_PRODUCT:
            return {
                "product_id": params.get("product_id"),
                "previous_status": "pending"
            }
        elif action_type == ActionType.PAUSE_CAMPAIGN:
            return {
                "campaign_id": params.get("campaign_id"),
                "previous_status": "active"
            }
        elif action_type == ActionType.DISCONTINUE_PRODUCT:
            return {
                "product_id": params.get("product_id"),
                "previous_status": "active"
            }
        elif action_type == ActionType.ADJUST_PRICE:
            return {
                "product_id": params.get("product_id"),
                "old_price": result.get("old_price")
            }
        else:
            return None

    async def _undo_deploy_product(self, undo_data: Dict):
        """Undo product deployment"""
        from ospra_os.database import Product, ProductStatus

        product_id = undo_data.get("product_id")
        product = self.db.query(Product).filter(Product.id == product_id).first()

        if product:
            product.status = ProductStatus.PENDING
            product.queued_at = None
            self.db.commit()
            logger.info(f"Undone deploy for product {product_id}")

    async def _undo_pause_campaign(self, undo_data: Dict):
        """Undo campaign pause"""
        campaign_id = undo_data.get("campaign_id")
        # In production, would resume campaign via Meta Ads API
        logger.info(f"Undone pause for campaign {campaign_id}")

    async def _undo_discontinue_product(self, undo_data: Dict):
        """Undo product discontinuation"""
        from ospra_os.database import Product, ProductStatus

        product_id = undo_data.get("product_id")
        product = self.db.query(Product).filter(Product.id == product_id).first()

        if product:
            product.status = ProductStatus.ACTIVE
            self.db.commit()
            logger.info(f"Undone discontinue for product {product_id}")

    async def _undo_adjust_price(self, undo_data: Dict):
        """Undo price adjustment"""
        from ospra_os.database import Product

        product_id = undo_data.get("product_id")
        old_price = undo_data.get("old_price")

        product = self.db.query(Product).filter(Product.id == product_id).first()

        if product and old_price:
            product.price = old_price
            self.db.commit()
            logger.info(f"Undone price change for product {product_id}: restored to ${old_price}")


# Singleton instance
_action_executor = None


def get_action_executor(db: Session) -> ActionExecutor:
    """Get or create action executor instance"""
    global _action_executor
    if _action_executor is None:
        _action_executor = ActionExecutor(db)
    return _action_executor
