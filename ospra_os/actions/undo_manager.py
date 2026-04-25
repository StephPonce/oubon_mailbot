"""
Undo Manager - Handle reversing executed actions

Allows users to undo recently executed actions within a time window.
Builds trust by making AI decisions reversible.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from ospra_os.database.action_models import Action, ActionLog, AIActionStatus, AIActionType

logger = logging.getLogger(__name__)


class UndoManager:
    """Manage undo operations for executed actions"""

    # How long after execution an action can be undone (hours)
    UNDO_WINDOWS = {
        AIActionType.DEPLOY_PRODUCT: 24,      # Can unpublish within 24 hours
        AIActionType.ADJUST_PRICE: 48,        # Can revert price within 48 hours
        AIActionType.PAUSE_AD: 168,           # Can resume within 7 days
        AIActionType.RESUME_AD: 168,          # Can pause within 7 days
        AIActionType.DROP_PRODUCT: 24,        # Can republish within 24 hours
        AIActionType.SEND_REFUND: 0,          # Cannot undo refunds
        AIActionType.REPLY_EMAIL: 0,          # Cannot unsend emails
        AIActionType.RESTOCK_ALERT: None,     # N/A - just an alert
    }

    def __init__(self, db: Session):
        self.db = db

    def can_undo(self, action: Action) -> Dict[str, Any]:
        """
        Check if an action can be undone.

        Returns dict with can_undo boolean and reason/deadline info.
        """

        # Must be executed
        if action.status != AIActionStatus.EXECUTED:
            return {"can_undo": False, "reason": "Action not yet executed"}

        # Already undone
        if action.undone_at:
            return {"can_undo": False, "reason": "Action already undone"}

        # Check if action type is undoable
        undo_window = self.UNDO_WINDOWS.get(action.action_type)

        if undo_window == 0:
            return {"can_undo": False, "reason": f"{action.action_type.value} cannot be undone"}

        if undo_window is None:
            return {"can_undo": False, "reason": "This action type has no undo support"}

        # Check time window
        if action.executed_at:
            deadline = action.executed_at + timedelta(hours=undo_window)
            if datetime.now(timezone.utc) > deadline:
                return {
                    "can_undo": False,
                    "reason": f"Undo window expired ({undo_window}h after execution)"
                }

            time_remaining = deadline - datetime.now(timezone.utc)
            hours_remaining = time_remaining.total_seconds() / 3600

            return {
                "can_undo": True,
                "hours_remaining": round(hours_remaining, 1),
                "deadline": deadline.isoformat()
            }

        return {"can_undo": False, "reason": "No execution timestamp"}

    async def undo_action(
        self,
        action: Action,
        user_id: int,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Undo an executed action.

        Args:
            action: The action to undo
            user_id: User requesting the undo
            reason: Optional reason for undo

        Returns:
            Dict with success status and message
        """

        # Verify can undo
        check = self.can_undo(action)
        if not check["can_undo"]:
            return {"success": False, "error": check["reason"]}

        try:
            # Execute the undo based on action type
            result = await self._execute_undo(action)

            if result["success"]:
                # Mark as undone
                action.undone_at = datetime.now(timezone.utc)
                action.undone_by = "user"
                action.status = AIActionStatus.UNDONE

                # Log the undo
                log = ActionLog(
                    action_id=action.id,
                    user_id=user_id,
                    old_status=AIActionStatus.EXECUTED,
                    new_status=AIActionStatus.UNDONE,
                    reason=reason or "User requested undo"
                )
                self.db.add(log)
                self.db.commit()

                logger.info(f"Action {action.id} undone by user {user_id}")

                return {
                    "success": True,
                    "message": result.get("message", "Action undone successfully"),
                    "action_id": action.id
                }
            else:
                logger.error(f"Failed to undo action {action.id}: {result.get('error')}")
                return result

        except Exception as e:
            logger.error(f"Exception undoing action {action.id}: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}

    async def _execute_undo(self, action: Action) -> Dict[str, Any]:
        """
        Execute the actual undo operation based on action type.

        This is where the reverse operation happens (unpublish product, revert price, etc.)
        """

        if action.action_type == AIActionType.DEPLOY_PRODUCT:
            return await self._undo_deploy_product(action)

        elif action.action_type == AIActionType.ADJUST_PRICE:
            return await self._undo_price_adjustment(action)

        elif action.action_type == AIActionType.PAUSE_AD:
            return await self._undo_pause_ad(action)

        elif action.action_type == AIActionType.RESUME_AD:
            return await self._undo_resume_ad(action)

        elif action.action_type == AIActionType.DROP_PRODUCT:
            return await self._undo_drop_product(action)

        else:
            return {"success": False, "error": f"No undo handler for {action.action_type.value}"}

    async def _undo_deploy_product(self, action: Action) -> Dict[str, Any]:
        """
        Unpublish/archive a deployed product.

        In production, this would call Shopify API to set product status to 'draft'.
        """

        payload = action.payload or {}
        execution_result = action.execution_result or {}

        product_name = payload.get("product_name", "Unknown Product")
        shopify_product_id = execution_result.get("shopify_product_id")

        # For now, simulate successful unpublish
        # In production: call ShopifyClient().update_product(shopify_product_id, {"status": "draft"})

        logger.info(f"Simulating unpublish of product: {product_name} (Shopify ID: {shopify_product_id})")

        return {
            "success": True,
            "message": f"Product '{product_name}' unpublished from store"
        }

    async def _undo_price_adjustment(self, action: Action) -> Dict[str, Any]:
        """
        Revert price to previous value.

        In production, this would call Shopify API to update variant price.
        """

        previous_state = action.previous_state or {}
        payload = action.payload or {}

        old_price = previous_state.get("price") or payload.get("current_price")
        product_name = payload.get("product_name", "Unknown Product")

        if not old_price:
            return {"success": False, "error": "No previous price found"}

        # For now, simulate successful price reversion
        # In production: call ShopifyClient().update_variant_price(variant_id, old_price)

        logger.info(f"Simulating price revert for {product_name} to ${old_price}")

        return {
            "success": True,
            "message": f"Price reverted to ${old_price:.2f}"
        }

    async def _undo_pause_ad(self, action: Action) -> Dict[str, Any]:
        """
        Resume a paused ad campaign.

        In production, this would call Meta Ads API or Google Ads API.
        """

        payload = action.payload or {}
        campaign_name = payload.get("campaign_name", "Unknown Campaign")
        platform = payload.get("platform", "meta")

        # For now, simulate successful resume
        # In production: call MetaAdsClient().update_campaign(campaign_id, {"status": "ACTIVE"})

        logger.info(f"Simulating resume of {platform} campaign: {campaign_name}")

        return {
            "success": True,
            "message": f"Campaign '{campaign_name}' resumed on {platform}"
        }

    async def _undo_resume_ad(self, action: Action) -> Dict[str, Any]:
        """
        Pause a resumed ad campaign.

        In production, this would call Meta Ads API or Google Ads API.
        """

        payload = action.payload or {}
        campaign_name = payload.get("campaign_name", "Unknown Campaign")
        platform = payload.get("platform", "meta")

        # For now, simulate successful pause
        # In production: call MetaAdsClient().update_campaign(campaign_id, {"status": "PAUSED"})

        logger.info(f"Simulating pause of {platform} campaign: {campaign_name}")

        return {
            "success": True,
            "message": f"Campaign '{campaign_name}' paused again on {platform}"
        }

    async def _undo_drop_product(self, action: Action) -> Dict[str, Any]:
        """
        Republish a dropped product.

        In production, this would call Shopify API to set product status to 'active'.
        """

        payload = action.payload or {}
        previous_state = action.previous_state or {}

        product_name = payload.get("product_name", "Unknown Product")
        shopify_product_id = previous_state.get("shopify_product_id")

        # For now, simulate successful republish
        # In production: call ShopifyClient().update_product(shopify_product_id, {"status": "active"})

        logger.info(f"Simulating republish of product: {product_name} (Shopify ID: {shopify_product_id})")

        return {
            "success": True,
            "message": f"Product '{product_name}' republished to store"
        }


def get_undo_manager(db: Session) -> UndoManager:
    """Get undo manager instance"""
    return UndoManager(db)
