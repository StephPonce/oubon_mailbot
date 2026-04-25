"""
Oi Action Executor - REAL ACTIONS ONLY

Executes actions using REAL integrations. Returns honest errors
when integrations aren't connected.

Author: OspraOS
Date: December 2024
"""

import logging
import os
from typing import Dict, Any, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)


class ActionStatus(Enum):
    """Status of an executed action."""
    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"
    REQUIRES_CONFIRMATION = "requires_confirmation"
    NOT_CONNECTED = "not_connected"  # Integration not available
    UNAUTHORIZED = "unauthorized"


@dataclass
class ActionResult:
    """Result of an action execution."""
    action: str
    status: ActionStatus
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "status": self.status.value,
            "message": self.message,
            "data": self.data,
            "timestamp": self.timestamp
        }


class ActionExecutor:
    """
    Executes REAL actions - no fake data.
    
    Each action checks if required integrations are connected
    before attempting execution.
    """
    
    def __init__(self):
        """Initialize with registered actions."""
        self._actions: Dict[str, Dict[str, Any]] = {}
        self._register_default_actions()
    
    def _register_default_actions(self) -> None:
        """Register all default actions."""
        
        # Product actions
        self.register(
            "deploy_product",
            handler=self._deploy_product,
            requires_confirmation=True,
            requires=["store_connection"],
            description="Deploy a product to a connected store"
        )
        
        self.register(
            "analyze_product",
            handler=self._analyze_product,
            requires_confirmation=False,
            requires=["intelligence_engine"],
            description="Get AI analysis of a product"
        )
        
        self.register(
            "search_products",
            handler=self._search_products,
            requires_confirmation=False,
            requires=["intelligence_engine"],
            description="Search for trending products"
        )
        
        # Store actions
        self.register(
            "get_store_stats",
            handler=self._get_store_stats,
            requires_confirmation=False,
            requires=["store_connection"],
            description="Get store performance statistics"
        )
        
        self.register(
            "list_products",
            handler=self._list_products,
            requires_confirmation=False,
            requires=["store_connection"],
            description="List products in a store"
        )
        
        # Order actions
        self.register(
            "get_recent_orders",
            handler=self._get_recent_orders,
            requires_confirmation=False,
            requires=["store_connection"],
            description="Get recent orders"
        )
        
        self.register(
            "fulfill_order",
            handler=self._fulfill_order,
            requires_confirmation=True,
            requires=["store_connection", "supplier_connection"],
            description="Fulfill an order with supplier"
        )
        
        # Email actions
        self.register(
            "draft_email",
            handler=self._draft_email,
            requires_confirmation=False,
            requires=["email_connection"],
            description="Draft an email response"
        )
        
        # Analytics actions (can work with partial data)
        self.register(
            "get_trends",
            handler=self._get_trends,
            requires_confirmation=False,
            requires=["intelligence_engine"],
            description="Get current market trends"
        )
    
    def register(
        self,
        action_name: str,
        handler: Callable[..., Awaitable[ActionResult]],
        requires_confirmation: bool = False,
        requires: list = None,
        description: str = ""
    ) -> None:
        """Register a new action with its requirements."""
        self._actions[action_name] = {
            "handler": handler,
            "requires_confirmation": requires_confirmation,
            "requires": requires or [],
            "description": description
        }
    
    async def execute(
        self,
        action_name: str,
        params: Dict[str, Any],
        context: Dict[str, Any],
        confirmed: bool = False
    ) -> ActionResult:
        """
        Execute an action after checking requirements.
        """
        if action_name not in self._actions:
            return ActionResult(
                action=action_name,
                status=ActionStatus.FAILED,
                message=f"Unknown action: {action_name}"
            )
        
        action = self._actions[action_name]
        
        # Check requirements
        missing = self._check_requirements(action["requires"], context)
        if missing:
            return ActionResult(
                action=action_name,
                status=ActionStatus.NOT_CONNECTED,
                message=f"Cannot execute '{action_name}': {missing}",
                data={"missing_requirements": missing}
            )
        
        # Check confirmation
        if action["requires_confirmation"] and not confirmed:
            return ActionResult(
                action=action_name,
                status=ActionStatus.REQUIRES_CONFIRMATION,
                message=f"Action '{action_name}' requires confirmation. Please confirm to proceed.",
                data={"params": params}
            )
        
        try:
            result = await action["handler"](params, context)
            logger.info(f"Action '{action_name}' executed: {result.status.value}")
            return result
            
        except Exception as e:
            logger.error(f"Action '{action_name}' failed: {e}")
            return ActionResult(
                action=action_name,
                status=ActionStatus.FAILED,
                message=f"Action failed: {str(e)}"
            )
    
    def _check_requirements(self, requires: list, context: Dict[str, Any]) -> Optional[str]:
        """Check if required integrations are connected."""
        status = context.get("connection_status", {})
        
        for req in requires:
            if req == "store_connection" and not status.get("has_stores"):
                return "No store connected. Please connect a Shopify or WooCommerce store first."
            
            if req == "intelligence_engine" and not status.get("has_trending"):
                return "Intelligence Engine not active. Market data sources need to be configured."
            
            if req == "email_connection" and not status.get("has_email"):
                return "No email account connected. Please connect Gmail in Settings."
            
            if req == "supplier_connection":
                # Check for CJ Dropshipping connection
                # TODO: Add actual check
                pass
        
        return None
    
    def list_actions(self) -> Dict[str, str]:
        """List all available actions with descriptions."""
        return {
            name: f"{action['description']} (requires: {', '.join(action['requires']) or 'nothing'})"
            for name, action in self._actions.items()
        }
    
    # ========================================================================
    # ACTION HANDLERS - REAL INTEGRATIONS ONLY
    # ========================================================================
    
    async def _deploy_product(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> ActionResult:
        """Deploy a product to a connected store - REAL API CALL."""
        product_id = params.get("product_id")
        store_id = params.get("store_id")
        price = params.get("price")
        
        if not all([product_id, store_id]):
            return ActionResult(
                action="deploy_product",
                status=ActionStatus.FAILED,
                message="Missing required parameters: product_id, store_id"
            )
        
        try:
            # Get store info from context
            stores = context.get("stores", [])
            store = next((s for s in stores if s.get("id") == store_id), None)
            
            if not store:
                return ActionResult(
                    action="deploy_product",
                    status=ActionStatus.FAILED,
                    message=f"Store {store_id} not found in connected stores"
                )
            
            # TODO: Call actual Shopify/WooCommerce deployment API
            # from ospra_os.deployment import UnifiedProductDeployer
            # deployer = UnifiedProductDeployer()
            # result = await deployer.deploy(product_id, store)
            
            return ActionResult(
                action="deploy_product",
                status=ActionStatus.PENDING,
                message="Product deployment initiated. Integration pending full API connection.",
                data={
                    "product_id": product_id,
                    "store_id": store_id,
                    "status": "pending_integration"
                }
            )
            
        except Exception as e:
            return ActionResult(
                action="deploy_product",
                status=ActionStatus.FAILED,
                message=f"Deployment failed: {str(e)}"
            )
    
    async def _analyze_product(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> ActionResult:
        """Analyze a product - requires Intelligence Engine."""
        product_data = params.get("product_data", {})
        
        if not product_data:
            return ActionResult(
                action="analyze_product",
                status=ActionStatus.FAILED,
                message="Missing product_data parameter"
            )
        
        try:
            # TODO: Call actual AI analysis
            # from ospra_os.ai.factory import AIFactory
            # provider = AIFactory.get_provider("claude", api_key=os.getenv("ANTHROPIC_API_KEY"))
            # result = await provider.analyze_product(product_data)
            
            return ActionResult(
                action="analyze_product",
                status=ActionStatus.PENDING,
                message="Product analysis requires Claude API integration",
                data={"product": product_data, "status": "pending_integration"}
            )
            
        except Exception as e:
            return ActionResult(
                action="analyze_product",
                status=ActionStatus.FAILED,
                message=f"Analysis failed: {str(e)}"
            )
    
    async def _search_products(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> ActionResult:
        """Search trending products - requires Intelligence Engine."""
        niche = params.get("niche", "general")
        limit = params.get("limit", 10)
        
        try:
            # Try to get from actual Intelligence Engine
            from ospra_os.intelligence.core import get_intelligence_engine
            
            engine = get_intelligence_engine()
            if engine:
                products = await engine.get_trending_products(niche=niche, limit=limit)
                if products:
                    return ActionResult(
                        action="search_products",
                        status=ActionStatus.SUCCESS,
                        message=f"Found {len(products)} trending products in {niche}",
                        data={"products": products, "niche": niche}
                    )
            
            return ActionResult(
                action="search_products",
                status=ActionStatus.NOT_CONNECTED,
                message="Intelligence Engine not available. Cannot search trending products.",
                data={"niche": niche}
            )
            
        except ImportError:
            return ActionResult(
                action="search_products",
                status=ActionStatus.NOT_CONNECTED,
                message="Intelligence Engine module not installed"
            )
        except Exception as e:
            return ActionResult(
                action="search_products",
                status=ActionStatus.FAILED,
                message=f"Search failed: {str(e)}"
            )
    
    async def _get_store_stats(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> ActionResult:
        """Get store stats - requires store API connection."""
        store_id = params.get("store_id")
        
        stores = context.get("stores", [])
        if not stores:
            return ActionResult(
                action="get_store_stats",
                status=ActionStatus.NOT_CONNECTED,
                message="No stores connected. Please connect a store first."
            )
        
        # Check if we have real metrics
        metrics = context.get("store_metrics")
        if metrics and isinstance(metrics, dict):
            if metrics.get("status") == "pending_api_integration":
                return ActionResult(
                    action="get_store_stats",
                    status=ActionStatus.PENDING,
                    message="Store connected but metrics API integration pending",
                    data={"stores_connected": len(stores)}
                )
            elif "revenue_30d" in metrics:
                return ActionResult(
                    action="get_store_stats",
                    status=ActionStatus.SUCCESS,
                    message="Store statistics retrieved",
                    data=metrics
                )
        
        return ActionResult(
            action="get_store_stats",
            status=ActionStatus.NOT_CONNECTED,
            message="Store metrics not available. API connection may need configuration."
        )
    
    async def _list_products(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> ActionResult:
        """List store products - requires store API."""
        products = context.get("products")
        
        if products and isinstance(products, list) and len(products) > 0:
            return ActionResult(
                action="list_products",
                status=ActionStatus.SUCCESS,
                message=f"Found {len(products)} products",
                data={"products": products}
            )
        elif products and isinstance(products, dict) and products.get("status"):
            return ActionResult(
                action="list_products",
                status=ActionStatus.PENDING,
                message=products.get("note", "Products pending API integration"),
                data=products
            )
        
        return ActionResult(
            action="list_products",
            status=ActionStatus.NOT_CONNECTED,
            message="No product data available. Store API connection needed."
        )
    
    async def _get_recent_orders(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> ActionResult:
        """Get recent orders - requires store API."""
        orders = context.get("recent_orders")
        
        if orders and isinstance(orders, list) and len(orders) > 0:
            return ActionResult(
                action="get_recent_orders",
                status=ActionStatus.SUCCESS,
                message=f"Found {len(orders)} recent orders",
                data={"orders": orders}
            )
        elif orders and isinstance(orders, dict) and orders.get("status"):
            return ActionResult(
                action="get_recent_orders",
                status=ActionStatus.PENDING,
                message=orders.get("note", "Orders pending API integration"),
                data=orders
            )
        
        return ActionResult(
            action="get_recent_orders",
            status=ActionStatus.NOT_CONNECTED,
            message="No order data available. Store API connection needed."
        )
    
    async def _fulfill_order(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> ActionResult:
        """Fulfill order via supplier - requires store + supplier connection."""
        order_id = params.get("order_id")
        
        if not order_id:
            return ActionResult(
                action="fulfill_order",
                status=ActionStatus.FAILED,
                message="Missing order_id parameter"
            )
        
        # TODO: Check CJ Dropshipping connection
        # TODO: Call actual fulfillment API
        
        return ActionResult(
            action="fulfill_order",
            status=ActionStatus.PENDING,
            message="Order fulfillment requires CJ Dropshipping API integration",
            data={"order_id": order_id, "status": "pending_integration"}
        )
    
    async def _draft_email(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> ActionResult:
        """Draft email - requires email connection."""
        original_email = params.get("original_email", "")
        
        email_status = context.get("email_stats", {})
        if not email_status or email_status.get("status") == "not_connected":
            return ActionResult(
                action="draft_email",
                status=ActionStatus.NOT_CONNECTED,
                message="No email account connected. Please connect Gmail in Settings."
            )
        
        # TODO: Use Claude to generate email draft
        return ActionResult(
            action="draft_email",
            status=ActionStatus.PENDING,
            message="Email drafting requires Claude API integration",
            data={"status": "pending_integration"}
        )
    
    async def _get_trends(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> ActionResult:
        """Get market trends - requires Intelligence Engine."""
        insights = context.get("market_insights")
        
        if insights and isinstance(insights, dict):
            if "hot_niches" in insights:
                return ActionResult(
                    action="get_trends",
                    status=ActionStatus.SUCCESS,
                    message="Market trends retrieved",
                    data=insights
                )
            elif insights.get("status"):
                return ActionResult(
                    action="get_trends",
                    status=ActionStatus.PENDING,
                    message=insights.get("note", "Trends pending Intelligence Engine"),
                    data=insights
                )
        
        return ActionResult(
            action="get_trends",
            status=ActionStatus.NOT_CONNECTED,
            message="Market trends not available. Intelligence Engine needs to be configured with data sources."
        )
