"""
Oi Context Builder - REAL DATA ONLY

Gathers ACTUAL data from connected services. Returns empty/null
when data isn't available - NEVER fabricates information.

Author: OspraOS
Date: December 2024
"""

import logging
import os
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ContextBuilder:
    """
    Builds context for Oi from REAL data sources only.
    
    CRITICAL: This class NEVER returns fake data. If data isn't available,
    it returns None or empty collections with clear indicators.
    """
    
    def __init__(self, user_id: str):
        """Initialize context builder for a user."""
        self.user_id = user_id
        self._api_base = os.getenv("API_BASE_URL", "http://localhost:8001")
    
    async def build_full_context(self) -> Dict[str, Any]:
        """
        Build context from all REAL sources.
        
        Returns dict with actual data or clear "not_connected" indicators.
        Each fetch is wrapped in try/except to prevent cascading failures.
        """
        context = {
            "data_status": "real",  # Flag that this is real data
            "built_at": datetime.utcnow().isoformat(),
        }
        
        # Gather from real sources - each returns None if unavailable
        # Wrap each in try/except to prevent one failure from killing everything
        try:
            context["user"] = await self._get_user_context()
        except Exception as e:
            logger.warning(f"Failed to get user context: {e}")
            context["user"] = None
        
        try:
            context["stores"] = await self._get_stores_context()
        except Exception as e:
            logger.warning(f"Failed to get stores context: {e}")
            context["stores"] = None
        
        try:
            context["store_metrics"] = await self._get_store_metrics()
        except Exception as e:
            logger.warning(f"Failed to get store metrics: {e}")
            context["store_metrics"] = None
        
        try:
            context["products"] = await self._get_products_context()
        except Exception as e:
            logger.warning(f"Failed to get products context: {e}")
            context["products"] = None
        
        try:
            context["trending"] = await self._get_trending_products()
        except Exception as e:
            logger.warning(f"Failed to get trending products: {e}")
            context["trending"] = None
        
        try:
            context["recent_orders"] = await self._get_recent_orders()
        except Exception as e:
            logger.warning(f"Failed to get recent orders: {e}")
            context["recent_orders"] = None
        
        try:
            context["email_stats"] = await self._get_email_stats()
        except Exception as e:
            logger.warning(f"Failed to get email stats: {e}")
            context["email_stats"] = None
        
        try:
            context["market_insights"] = await self._get_market_insights()
        except Exception as e:
            logger.warning(f"Failed to get market insights: {e}")
            context["market_insights"] = None
        
        # Add summary of what's connected vs not
        context["connection_status"] = self._summarize_connections(context)
        
        logger.info(f"Built REAL context for user {self.user_id}: {context['connection_status']}")
        
        return context
    
    async def build_minimal_context(self) -> Dict[str, Any]:
        """Build minimal context with just essential real data."""
        return {
            "data_status": "real",
            "built_at": datetime.utcnow().isoformat(),
            "user": await self._get_user_context(),
            "stores": await self._get_stores_context(),
            "store_metrics": await self._get_store_metrics()
        }
    
    def _summarize_connections(self, context: Dict[str, Any]) -> Dict[str, bool]:
        """Summarize what data sources are actually connected."""
        return {
            "has_stores": bool(context.get("stores")),
            "has_metrics": bool(context.get("store_metrics")),
            "has_products": bool(context.get("products")),
            "has_trending": bool(context.get("trending")),
            "has_orders": bool(context.get("recent_orders")),
            "has_email": bool(context.get("email_stats")),
            "has_market_data": bool(context.get("market_insights")),
        }
    
    # ========================================================================
    # REAL DATA FETCHERS - Return None if not available
    # ========================================================================
    
    async def _get_user_context(self) -> Optional[Dict[str, Any]]:
        """Get REAL user profile from database."""
        try:
            # TODO: Connect to actual Supabase user table
            # For now, return minimal known info
            return {
                "id": self.user_id,
                "data_source": "pending_database_connection",
                "note": "User profile data pending Supabase integration"
            }
        except Exception as e:
            logger.error(f"Failed to get user context: {e}")
            return None
    
    async def _get_stores_context(self) -> Optional[List[Dict[str, Any]]]:
        """Get REAL connected stores from database."""
        try:
            # Import here to avoid circular imports
            from ospra_os.database.supabase_client import get_supabase_client
            
            supabase = get_supabase_client()
            if not supabase:
                logger.warning("Supabase client not available")
                return None
            
            # Query actual connected stores
            response = supabase.table("connected_stores").select("*").eq(
                "user_id", self.user_id
            ).execute()
            
            if response.data:
                return response.data
            return []
            
        except Exception as e:
            logger.error(f"Failed to get stores: {e}")
            return None
    
    async def _get_store_metrics(self) -> Optional[Dict[str, Any]]:
        """Get REAL store metrics from connected platforms."""
        try:
            stores = await self._get_stores_context()
            if not stores:
                return None
            
            # TODO: Query actual Shopify/WooCommerce APIs for metrics
            # This requires store tokens and API calls
            
            # For now, indicate metrics need API connection
            return {
                "status": "pending_api_integration",
                "note": "Store metrics require active API connection to Shopify/WooCommerce",
                "stores_connected": len(stores) if stores else 0
            }
            
        except Exception as e:
            logger.error(f"Failed to get store metrics: {e}")
            return None
    
    async def _get_products_context(self) -> Optional[List[Dict[str, Any]]]:
        """Get REAL products from connected stores."""
        try:
            stores = await self._get_stores_context()
            if not stores:
                return None
            
            # TODO: Query actual store products via APIs
            return {
                "status": "pending_api_integration", 
                "note": "Product data requires Shopify/WooCommerce API connection"
            }
            
        except Exception as e:
            logger.error(f"Failed to get products: {e}")
            return None
    
    async def _get_trending_products(self) -> Optional[List[Dict[str, Any]]]:
        """Get REAL trending products from Intelligence Engine."""
        try:
            # Try to get from actual Intelligence Engine
            from ospra_os.intelligence.core import get_intelligence_engine
            
            engine = get_intelligence_engine()
            if engine:
                # Query real trending data
                trending = await engine.get_trending_products(limit=10)
                if trending:
                    return trending
            
            # Intelligence Engine not available
            return {
                "status": "pending_intelligence_engine",
                "note": "Trending data requires Intelligence Engine to be running with data sources"
            }
            
        except ImportError:
            logger.warning("Intelligence Engine not available")
            return None
        except Exception as e:
            logger.error(f"Failed to get trending: {e}")
            return None
    
    async def _get_recent_orders(self) -> Optional[List[Dict[str, Any]]]:
        """Get REAL recent orders from connected stores."""
        try:
            stores = await self._get_stores_context()
            if not stores:
                return None
            
            # TODO: Query actual orders from Shopify/WooCommerce
            return {
                "status": "pending_api_integration",
                "note": "Order data requires store API connection"
            }
            
        except Exception as e:
            logger.error(f"Failed to get orders: {e}")
            return None
    
    async def _get_email_stats(self) -> Optional[Dict[str, Any]]:
        """Get REAL email automation stats."""
        try:
            # Check if email is connected
            from ospra_os.database.supabase_client import get_supabase_client
            
            supabase = get_supabase_client()
            if not supabase:
                return None
            
            # Check for connected email accounts
            response = supabase.table("email_connections").select("*").eq(
                "user_id", self.user_id
            ).execute()
            
            if not response.data:
                return {
                    "status": "not_connected",
                    "note": "No email accounts connected"
                }
            
            # TODO: Get actual email stats from Gmail API
            return {
                "status": "connected",
                "accounts": len(response.data),
                "note": "Email stats require Gmail API query"
            }
            
        except Exception as e:
            logger.error(f"Failed to get email stats: {e}")
            return None
    
    async def _get_market_insights(self) -> Optional[Dict[str, Any]]:
        """Get REAL market insights from Intelligence Engine."""
        try:
            from ospra_os.intelligence.core import get_intelligence_engine
            
            engine = get_intelligence_engine()
            if engine:
                insights = await engine.get_market_insights()
                if insights:
                    return insights
            
            return {
                "status": "pending_intelligence_engine",
                "note": "Market insights require Intelligence Engine with active data sources"
            }
            
        except ImportError:
            return None
        except Exception as e:
            logger.error(f"Failed to get market insights: {e}")
            return None


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def summarize_context(context: Dict[str, Any]) -> str:
    """Create honest summary of what data is available."""
    lines = ["Context Summary (REAL DATA ONLY):"]
    
    status = context.get("connection_status", {})
    
    if status.get("has_stores"):
        stores = context.get("stores", [])
        lines.append(f"[SUCCESS] Stores: {len(stores)} connected")
    else:
        lines.append("[ERROR] Stores: None connected")
    
    if status.get("has_metrics"):
        lines.append("[SUCCESS] Metrics: Available")
    else:
        lines.append("[ERROR] Metrics: Not available (need store connection)")
    
    if status.get("has_trending"):
        lines.append("[SUCCESS] Trending: Intelligence Engine active")
    else:
        lines.append("[ERROR] Trending: Intelligence Engine not connected")
    
    if status.get("has_email"):
        lines.append("[SUCCESS] Email: Connected")
    else:
        lines.append("[ERROR] Email: Not connected")
    
    return "\n".join(lines)
