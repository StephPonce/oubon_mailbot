"""
AI ACTIONS SYSTEM

Allows AI to propose actionable recommendations that users can:
1. Accept (execute with one click)
2. Decline (AI learns from rejection)
3. Modify (adjust parameters before execution)

AI learns from which actions are accepted/declined to improve future recommendations.
"""

from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
from enum import Enum
import uuid
import json
from sqlalchemy.orm import Session

from ospra_os.database import Product, Store, AdCampaign


class ActionType(str, Enum):
    """Types of AI-proposed actions."""
    DEPLOY_PRODUCT = "deploy_product"
    PAUSE_AD = "pause_ad"
    INCREASE_AD_BUDGET = "increase_ad_budget"
    DECREASE_AD_BUDGET = "decrease_ad_budget"
    ADJUST_PRICE = "adjust_price"
    REORDER_INVENTORY = "reorder_inventory"
    SEND_EMAIL = "send_email"
    CREATE_AD_CAMPAIGN = "create_ad_campaign"
    UPDATE_PRODUCT_DESCRIPTION = "update_product_description"
    ADD_TO_FEATURED = "add_to_featured"
    REMOVE_PRODUCT = "remove_product"


class ActionStatus(str, Enum):
    """Status of an AI action."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


class AIAction:
    """
    Represents a single actionable AI recommendation.

    Each action can be:
    - Displayed to user with Accept/Decline buttons
    - Executed programmatically when accepted
    - Used for learning (track accept rate)
    """

    def __init__(
        self,
        action_id: str,
        action_type: ActionType,
        title: str,
        description: str,
        impact_summary: str,
        parameters: Dict[str, Any],
        confidence: float,
        execution_function: Optional[Callable] = None,
        created_at: Optional[datetime] = None,
        expires_at: Optional[datetime] = None
    ):
        self.action_id = action_id
        self.action_type = action_type
        self.title = title
        self.description = description
        self.impact_summary = impact_summary
        self.parameters = parameters
        self.confidence = confidence
        self.execution_function = execution_function
        self.status = ActionStatus.PENDING
        self.created_at = created_at or datetime.utcnow()
        self.expires_at = expires_at or (datetime.utcnow() + timedelta(days=7))
        self.accepted_at = None
        self.declined_at = None
        self.completed_at = None
        self.result = None
        self.error = None

    async def execute(self, db: Session, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the AI action."""
        if self.status != ActionStatus.ACCEPTED:
            return {
                "success": False,
                "error": "Action must be accepted before execution"
            }

        self.status = ActionStatus.EXECUTING

        try:
            # Execute based on action type
            if self.action_type == ActionType.DEPLOY_PRODUCT:
                result = await self._deploy_product(db, user_context)

            elif self.action_type == ActionType.PAUSE_AD:
                result = await self._pause_ad(db, user_context)

            elif self.action_type == ActionType.INCREASE_AD_BUDGET:
                result = await self._adjust_ad_budget(db, user_context, increase=True)

            elif self.action_type == ActionType.DECREASE_AD_BUDGET:
                result = await self._adjust_ad_budget(db, user_context, increase=False)

            elif self.action_type == ActionType.ADJUST_PRICE:
                result = await self._adjust_price(db, user_context)

            elif self.action_type == ActionType.UPDATE_PRODUCT_DESCRIPTION:
                result = await self._update_product_description(db, user_context)

            elif self.execution_function:
                # Custom execution function
                result = await self.execution_function(db, self.parameters, user_context)

            else:
                result = {
                    "success": False,
                    "error": f"No executor for action type: {self.action_type}"
                }

            if result.get("success"):
                self.status = ActionStatus.COMPLETED
                self.completed_at = datetime.utcnow()
            else:
                self.status = ActionStatus.FAILED
                self.error = result.get("error", "Unknown error")

            self.result = result
            return result

        except Exception as e:
            self.status = ActionStatus.FAILED
            self.error = str(e)
            return {
                "success": False,
                "error": str(e)
            }

    async def _deploy_product(self, db: Session, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Deploy a new product to store."""
        product_id = self.parameters.get("product_id")
        store_id = self.parameters.get("store_id")

        if not product_id:
            return {"success": False, "error": "Missing product_id"}

        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            return {"success": False, "error": "Product not found"}

        # Update product status to active
        from ospra_os.database import ProductStatus
        product.status = ProductStatus.ACTIVE
        product.deployed_at = datetime.utcnow()

        db.commit()

        return {
            "success": True,
            "message": f"Product '{product.title}' deployed successfully",
            "product_id": product_id,
            "deployed_at": product.deployed_at.isoformat()
        }

    async def _pause_ad(self, db: Session, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Pause an underperforming ad campaign."""
        campaign_id = self.parameters.get("campaign_id")

        campaign = db.query(AdCampaign).filter(AdCampaign.id == campaign_id).first()
        if not campaign:
            return {"success": False, "error": "Campaign not found"}

        # Update campaign status
        campaign.status = "PAUSED"
        campaign.paused_at = datetime.utcnow()

        db.commit()

        return {
            "success": True,
            "message": f"Campaign '{campaign.campaign_name}' paused",
            "campaign_id": campaign_id,
            "reason": self.parameters.get("reason", "AI recommendation")
        }

    async def _adjust_ad_budget(self, db: Session, user_context: Dict[str, Any], increase: bool) -> Dict[str, Any]:
        """Adjust ad campaign budget."""
        campaign_id = self.parameters.get("campaign_id")
        adjustment_percent = self.parameters.get("adjustment_percent", 20)

        campaign = db.query(AdCampaign).filter(AdCampaign.id == campaign_id).first()
        if not campaign:
            return {"success": False, "error": "Campaign not found"}

        old_budget = float(campaign.daily_budget)

        # Calculate new budget
        if increase:
            new_budget = old_budget * (1 + adjustment_percent / 100)
        else:
            new_budget = old_budget * (1 - adjustment_percent / 100)

        campaign.daily_budget = new_budget
        db.commit()

        return {
            "success": True,
            "message": f"Budget {'increased' if increase else 'decreased'} by {adjustment_percent}%",
            "campaign_id": campaign_id,
            "old_budget": old_budget,
            "new_budget": new_budget,
            "adjustment": f"{'+' if increase else '-'}{adjustment_percent}%"
        }

    async def _adjust_price(self, db: Session, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Adjust product price."""
        product_id = self.parameters.get("product_id")
        new_price = self.parameters.get("new_price")

        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            return {"success": False, "error": "Product not found"}

        old_price = float(product.price)
        product.price = new_price

        # Recalculate profit margin
        if product.supplier_cost:
            product.profit_margin = ((new_price - float(product.supplier_cost)) / new_price) * 100

        db.commit()

        return {
            "success": True,
            "message": f"Price updated from ${old_price:.2f} to ${new_price:.2f}",
            "product_id": product_id,
            "old_price": old_price,
            "new_price": new_price,
            "new_margin": float(product.profit_margin) if product.profit_margin else None
        }

    async def _update_product_description(self, db: Session, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Update product description with AI-generated content."""
        product_id = self.parameters.get("product_id")
        new_description = self.parameters.get("new_description")

        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            return {"success": False, "error": "Product not found"}

        old_description = product.description
        product.description = new_description

        db.commit()

        return {
            "success": True,
            "message": "Product description updated",
            "product_id": product_id,
            "description_length": {
                "old": len(old_description) if old_description else 0,
                "new": len(new_description)
            }
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert action to dictionary for API responses."""
        return {
            "id": self.action_id,  # Alias for compatibility
            "action_id": self.action_id,
            "action_type": self.action_type.value,
            "title": self.title,
            "description": self.description,
            "impact_summary": self.impact_summary,
            "parameters": self.parameters,
            "confidence": self.confidence,
            "status": self.status.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "accepted_at": self.accepted_at.isoformat() if self.accepted_at else None,
            "declined_at": self.declined_at.isoformat() if self.declined_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
            "error": self.error
        }


class AIActionManager:
    """
    Manages all AI actions and learns from user decisions.

    Features:
    - Stores pending actions
    - Tracks accept/decline rates
    - Learns which types of actions users prefer
    - Adjusts future recommendations based on feedback
    """

    def __init__(self, db: Session):
        self.db = db
        self.pending_actions: Dict[str, AIAction] = {}
        self.action_history: List[AIAction] = []

    def create_action(
        self,
        action_type: ActionType,
        title: str,
        description: str,
        impact_summary: str,
        parameters: Dict[str, Any],
        confidence: float,
        execution_function: Optional[Callable] = None
    ) -> AIAction:
        """Create a new AI action."""
        action_id = str(uuid.uuid4())

        action = AIAction(
            action_id=action_id,
            action_type=action_type,
            title=title,
            description=description,
            impact_summary=impact_summary,
            parameters=parameters,
            confidence=confidence,
            execution_function=execution_function
        )

        self.pending_actions[action_id] = action

        return action

    def get_pending_actions(
        self,
        user_id: Optional[int] = None,
        min_confidence: float = 0.7
    ) -> List[AIAction]:
        """Get all pending actions for user."""
        actions = list(self.pending_actions.values())

        # Filter by confidence
        actions = [a for a in actions if a.confidence >= min_confidence]

        # Filter expired
        now = datetime.utcnow()
        actions = [a for a in actions if a.expires_at > now]

        # Sort by confidence (highest first)
        actions.sort(key=lambda x: x.confidence, reverse=True)

        return actions

    async def accept_action(
        self,
        action_id: str,
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """User accepts an AI action - execute it."""
        action = self.pending_actions.get(action_id)

        if not action:
            return {"success": False, "error": "Action not found"}

        if action.status != ActionStatus.PENDING:
            return {"success": False, "error": f"Action already {action.status.value}"}

        # Mark as accepted
        action.status = ActionStatus.ACCEPTED
        action.accepted_at = datetime.utcnow()

        # Execute the action
        result = await action.execute(self.db, user_context)

        # Move to history
        self.action_history.append(action)
        if action_id in self.pending_actions:
            del self.pending_actions[action_id]

        # Learn from acceptance
        await self._learn_from_action(action, accepted=True)

        return result

    async def decline_action(
        self,
        action_id: str,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """User declines an AI action - AI learns from this."""
        action = self.pending_actions.get(action_id)

        if not action:
            return {"success": False, "error": "Action not found"}

        if action.status != ActionStatus.PENDING:
            return {"success": False, "error": f"Action already {action.status.value}"}

        # Mark as declined
        action.status = ActionStatus.DECLINED
        action.declined_at = datetime.utcnow()

        if reason:
            action.error = f"Declined by user: {reason}"

        # Move to history
        self.action_history.append(action)
        if action_id in self.pending_actions:
            del self.pending_actions[action_id]

        # Learn from rejection
        await self._learn_from_action(action, accepted=False, decline_reason=reason)

        return {
            "success": True,
            "message": "Action declined",
            "action_id": action_id
        }

    async def _learn_from_action(
        self,
        action: AIAction,
        accepted: bool,
        decline_reason: Optional[str] = None
    ):
        """Learn from user's decision on an action."""
        # Track statistics by action type
        action_type = action.action_type.value

        # This would integrate with competitive learning engine
        # to adjust future action proposals

        # For now, just track in memory
        if not hasattr(self, '_action_stats'):
            self._action_stats = {}

        if action_type not in self._action_stats:
            self._action_stats[action_type] = {
                "proposed": 0,
                "accepted": 0,
                "declined": 0,
                "acceptance_rate": 0.0
            }

        stats = self._action_stats[action_type]
        stats["proposed"] += 1

        if accepted:
            stats["accepted"] += 1
        else:
            stats["declined"] += 1

        stats["acceptance_rate"] = stats["accepted"] / stats["proposed"]

        # Learn patterns
        # If action type has <30% acceptance rate, reduce confidence for future similar actions
        # If action type has >70% acceptance rate, increase confidence

    def get_action_stats(self) -> Dict[str, Any]:
        """Get statistics on action acceptance rates."""
        if not hasattr(self, '_action_stats'):
            return {}

        return self._action_stats

    def get_action(self, action_id: str) -> Optional[AIAction]:
        """Get a specific action by ID."""
        # Check pending
        if action_id in self.pending_actions:
            return self.pending_actions[action_id]

        # Check history
        for action in self.action_history:
            if action.action_id == action_id:
                return action

        return None


# Global action manager instance
_action_manager = None


def get_action_manager(db: Session) -> AIActionManager:
    """Get or create global action manager."""
    global _action_manager

    if _action_manager is None:
        _action_manager = AIActionManager(db)

    return _action_manager


# Wrapper functions for backwards compatibility with nl_routes.py
def propose_action(
    user_id: int,
    action_type: ActionType,
    title: str,
    description: str,
    impact_summary: str,
    parameters: Dict[str, Any],
    confidence: float,
    execution_function: Optional[Callable] = None,
    db: Optional[Session] = None
) -> Optional[AIAction]:
    """
    Propose a new AI action.

    This is a wrapper function for nl_routes.py compatibility.
    Creates an action using the AIActionManager.

    Args:
        user_id: User ID proposing the action
        action_type: Type of action to create
        title: Action title
        description: Action description
        impact_summary: Summary of expected impact
        parameters: Action parameters
        confidence: Confidence score (0.0 - 1.0)
        execution_function: Optional custom execution function
        db: Optional database session (will use global manager if None)

    Returns:
        AIAction instance if successful, None otherwise
    """
    try:
        # If no db provided, we need to get one from the global context
        # For now, create a simple in-memory action without db
        if db is None:
            # Create action without manager (stateless mode)
            action_id = str(uuid.uuid4())
            action = AIAction(
                action_id=action_id,
                action_type=action_type,
                title=title,
                description=description,
                impact_summary=impact_summary,
                parameters=parameters,
                confidence=confidence,
                execution_function=execution_function
            )
            return action
        else:
            # Use manager when db is available
            manager = get_action_manager(db)
            return manager.create_action(
                action_type=action_type,
                title=title,
                description=description,
                impact_summary=impact_summary,
                parameters=parameters,
                confidence=confidence,
                execution_function=execution_function
            )
    except Exception as e:
        print(f"Error proposing action: {e}")
        return None


def get_pending_actions(
    user_id: Optional[int] = None,
    min_confidence: float = 0.7,
    db: Optional[Session] = None
) -> List[AIAction]:
    """
    Get pending AI actions.

    This is a wrapper function for nl_routes.py compatibility.

    Args:
        user_id: Filter by user ID (optional)
        min_confidence: Minimum confidence threshold
        db: Optional database session

    Returns:
        List of pending AIAction instances
    """
    try:
        if db is None:
            # Return empty list if no db (stateless mode)
            return []

        manager = get_action_manager(db)
        return manager.get_pending_actions(
            user_id=user_id,
            min_confidence=min_confidence
        )
    except Exception as e:
        print(f"Error getting pending actions: {e}")
        return []
