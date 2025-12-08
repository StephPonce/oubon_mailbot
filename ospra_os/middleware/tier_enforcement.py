"""
TIER ENFORCEMENT MIDDLEWARE

Enforces subscription tier limits and feature access.
Uses unified tier definitions from ospra_os.core.tiers
Uses persistent usage tracking from ospra_os.core.usage_tracking
"""

import logging
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Dict, Optional
from datetime import datetime

from ospra_os.core.tiers import (
    SubscriptionTier,
    TierEnforcer,
    get_tier_definition,
    get_tier_feature,
    tier_has_feature,
    get_tier_limit,
    log_tier_access,
)
from ospra_os.database.multi_store_models import SessionLocal, User

logger = logging.getLogger(__name__)


class TierEnforcementMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce tier limits on API endpoints.

    Features:
    - Rate limiting per tier (persistent in DB)
    - Feature access control
    - Usage tracking
    """

    # Endpoints that require tier checking with their required features/actions
    PROTECTED_ENDPOINTS = {
        # Intelligence endpoints
        '/api/intelligence/briefing/morning': {'feature': 'ai_briefings', 'action': 'ai_briefing'},
        '/api/intelligence/briefing/on-demand': {'feature': 'ai_briefings', 'action': 'ai_briefing'},
        '/api/intelligence/action/execute': {'feature': 'auto_ordering'},
        '/api/intelligence/grade/product': {'feature': 'ai_score', 'action': 'ai_query'},
        '/api/intelligence/velocity': {'feature': 'trend_velocity'},
        
        # Prophecizer (Inventory) endpoints
        '/api/inventory/forecast': {'feature': 'days_until_stockout', 'action': 'inventory_check'},
        '/api/inventory/restock': {'feature': 'restock_recommendations', 'action': 'inventory_check'},
        '/api/inventory/alerts': {'feature': 'low_stock_alerts', 'action': 'inventory_check'},
        '/api/inventory/seasonality': {'feature': 'seasonality_adjustments'},
        
        # Email automation endpoints
        '/api/email/draft': {'feature': 'ai_draft_replies', 'action': 'email_automation'},
        '/api/email/auto-classify': {'feature': 'auto_classification', 'action': 'email_automation'},
        '/api/email/quiet-hours': {'feature': 'quiet_hours_routing'},
        
        # Ad management endpoints
        '/api/ads/schedule': {'feature': 'ad_scheduling'},
        '/api/ads/budget': {'feature': 'ad_budget_management'},
        '/api/ads/analytics': {'feature': 'cross_platform_analytics'},
        
        # Product discovery endpoints
        '/api/products/discover': {'action': 'product_discovery'},
        '/api/products/deploy': {'feature': 'one_click_deploy', 'action': 'product_deploy'},
        '/api/products/bulk-deploy': {'feature': 'bulk_deploy', 'action': 'product_deploy'},
        '/api/products/pricing': {'feature': 'ai_pricing_suggestions'},
        
        # Learning endpoints
        '/api/learning/personal': {'feature': 'personal_learning'},
        '/api/learning/custom-weights': {'feature': 'custom_weights'},
        
        # AliExpress endpoints
        '/api/aliexpress/search': {'action': 'aliexpress_search'},
        '/api/aliexpress/products/search': {'action': 'aliexpress_search'},
        '/api/aliexpress/enrich': {'feature': 'aliexpress_enrichment', 'action': 'aliexpress_enrichment'},
        '/api/aliexpress/order': {'feature': 'aliexpress_auto_ordering'},
    }

    # Endpoints accessible to all tiers (no enforcement)
    PUBLIC_ENDPOINTS = [
        '/api/intelligence/health',
        '/api/intelligence/tier/info',
        '/api/tiers/',
        '/api/auth',
        '/api/payments',
        '/health',
        '/docs',
        '/openapi.json',
        '/api/pricing',
    ]

    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        """Process request and enforce tier limits"""

        # Skip tier enforcement for public endpoints
        if any(request.url.path.startswith(endpoint) for endpoint in self.PUBLIC_ENDPOINTS):
            return await call_next(request)

        # Find matching protected endpoint
        enforcement_config = None
        for endpoint, config in self.PROTECTED_ENDPOINTS.items():
            if request.url.path.startswith(endpoint):
                enforcement_config = config
                break
        
        # Skip if not a protected endpoint
        if not enforcement_config:
            return await call_next(request)

        # Get user ID from request
        user_id = await self._extract_user_id(request)

        if not user_id:
            # No user ID provided - allow request but log warning
            logger.warning(f"No user_id for tier enforcement on {request.url.path}")
            return await call_next(request)

        # Get user's tier
        user_tier = await self._get_user_tier(user_id)
        tier_enforcer = TierEnforcer(user_tier)

        try:
            feature = enforcement_config.get('feature')
            action = enforcement_config.get('action')

            # Check feature access
            if feature:
                if not tier_enforcer.can_access(feature):
                    upgrade_info = tier_enforcer.get_upgrade_prompt(feature)
                    log_tier_access(user_id, user_tier, feature, False)
                    
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={
                            "error": "Feature not available in your tier",
                            "feature": feature,
                            "current_tier": user_tier.value,
                            "upgrade_required": True,
                            "upgrade_to": upgrade_info.get("required_tier") if upgrade_info else None,
                            "upgrade_price": upgrade_info.get("price") if upgrade_info else None,
                            "message": upgrade_info.get("message") if upgrade_info else f"Upgrade to access {feature.replace('_', ' ')}"
                        }
                    )
                
                log_tier_access(user_id, user_tier, feature, True)

            # Check and record usage via persistent tracking
            if action:
                from ospra_os.core.usage_tracking import get_enforcer
                
                db = SessionLocal()
                try:
                    usage_enforcer = get_enforcer(db)
                    check_result = usage_enforcer.can_perform(user_id, action)
                    
                    if not check_result.get("allowed", True):
                        return JSONResponse(
                            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            content={
                                "error": "Usage limit exceeded",
                                "action": action,
                                "current_usage": check_result.get("current", 0),
                                "limit": check_result.get("limit", 0),
                                "remaining": check_result.get("remaining", 0),
                                "upgrade_required": True,
                                "upgrade_suggestion": check_result.get("upgrade_suggestion"),
                                "message": check_result.get("reason", "Limit reached")
                            }
                        )
                    
                    # Record the usage AFTER successful request
                    # Store in request state for post-processing
                    request.state.track_action = action
                    request.state.track_user_id = user_id
                    
                finally:
                    db.close()

        except Exception as e:
            logger.error(f"Tier enforcement error: {e}")
            # On error, allow request to proceed (fail open)
            return await call_next(request)

        # Proceed with request
        response = await call_next(request)
        
        # Record usage on successful response
        if response.status_code < 400:
            await self._record_usage_if_needed(request)
        
        return response

    async def _record_usage_if_needed(self, request: Request):
        """Record usage after successful request"""
        try:
            action = getattr(request.state, 'track_action', None)
            user_id = getattr(request.state, 'track_user_id', None)
            
            if action and user_id:
                from ospra_os.core.usage_tracking import get_enforcer
                
                db = SessionLocal()
                try:
                    usage_enforcer = get_enforcer(db)
                    usage_enforcer.record_action(user_id=user_id, action=action)
                    logger.debug(f"Recorded usage: user={user_id}, action={action}")
                finally:
                    db.close()
        except Exception as e:
            logger.error(f"Failed to record usage: {e}")

    async def _extract_user_id(self, request: Request) -> Optional[int]:
        """Extract user ID from request"""
        # Try query parameters
        user_id = request.query_params.get('user_id')
        if user_id:
            try:
                return int(user_id)
            except ValueError:
                pass

        # Try headers
        user_id = request.headers.get('X-User-ID')
        if user_id:
            try:
                return int(user_id)
            except ValueError:
                pass

        # Try JWT token from Authorization header
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            try:
                # TODO: Decode JWT and extract user_id
                # token = auth_header.replace('Bearer ', '')
                # payload = decode_jwt(token)
                # return payload.get('user_id')
                pass
            except Exception:
                pass

        return None

    async def _get_user_tier(self, user_id: int) -> SubscriptionTier:
        """Get user's subscription tier from database"""
        try:
            db = SessionLocal()
            user = db.query(User).filter(User.id == user_id).first()
            db.close()
            
            if user and user.subscription_tier:
                # Handle string values
                tier_value = user.subscription_tier.value if hasattr(user.subscription_tier, 'value') else str(user.subscription_tier)
                
                # Map to SubscriptionTier enum
                tier_map = {
                    'nest': SubscriptionTier.NEST,
                    'flight': SubscriptionTier.FLIGHT,
                    'soar': SubscriptionTier.SOAR,
                    'stratosphere': SubscriptionTier.STRATOSPHERE,
                    # Legacy mappings
                    'free': SubscriptionTier.NEST,
                    'starter': SubscriptionTier.FLIGHT,
                    'pro': SubscriptionTier.SOAR,
                    'enterprise': SubscriptionTier.STRATOSPHERE,
                }
                return tier_map.get(tier_value.lower(), SubscriptionTier.NEST)
            
            return SubscriptionTier.NEST
            
        except Exception as e:
            logger.error(f"Error getting user tier: {e}")
            return SubscriptionTier.NEST


# ==================== FACTORY ====================

_middleware_instance = None


def get_tier_enforcement_middleware(app) -> TierEnforcementMiddleware:
    """Get or create tier enforcement middleware"""
    global _middleware_instance
    if _middleware_instance is None:
        _middleware_instance = TierEnforcementMiddleware(app)
    return _middleware_instance


# ==================== ROUTE DECORATORS ====================

def require_tier(min_tier: SubscriptionTier):
    """
    Decorator to require a minimum tier for a route.
    
    Usage:
        @router.get("/premium-feature")
        @require_tier(SubscriptionTier.SOAR)
        async def premium_feature(user_tier: SubscriptionTier = Depends(get_current_user_tier)):
            return {"message": "You have access!"}
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Get user tier from kwargs (should be injected by dependency)
            user_tier = kwargs.get('user_tier', SubscriptionTier.NEST)
            
            from ospra_os.core.tiers import tier_at_least
            
            if not tier_at_least(user_tier, min_tier):
                tier_def = get_tier_definition(min_tier)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": f"Requires {tier_def['name']} tier or higher",
                        "required_tier": min_tier.value,
                        "current_tier": user_tier.value,
                        "upgrade_required": True,
                    }
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_feature(feature: str):
    """
    Decorator to require a specific feature for a route.
    
    Usage:
        @router.post("/deploy")
        @require_feature("one_click_deploy")
        async def deploy_product(user_tier: SubscriptionTier = Depends(get_current_user_tier)):
            return {"message": "Deploying..."}
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            user_tier = kwargs.get('user_tier', SubscriptionTier.NEST)
            enforcer = TierEnforcer(user_tier)
            
            if not enforcer.can_access(feature):
                upgrade_info = enforcer.get_upgrade_prompt(feature)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=upgrade_info or {
                        "error": f"Feature '{feature}' not available in your tier",
                        "upgrade_required": True,
                    }
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def track_usage(action: str):
    """
    Decorator to track usage for rate-limited actions.
    
    Usage:
        @router.get("/search")
        @track_usage("aliexpress_search")
        async def search_products(user_id: int):
            return {"results": [...]}
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            user_id = kwargs.get('user_id')
            
            if user_id:
                from ospra_os.core.usage_tracking import get_enforcer
                
                db = SessionLocal()
                try:
                    enforcer = get_enforcer(db)
                    
                    # Check if allowed
                    check = enforcer.can_perform(user_id, action)
                    if not check.get("allowed", True):
                        raise HTTPException(
                            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail={
                                "error": "Usage limit exceeded",
                                "action": action,
                                "current": check.get("current", 0),
                                "limit": check.get("limit", 0),
                                "remaining": check.get("remaining", 0),
                                "upgrade_suggestion": check.get("upgrade_suggestion"),
                            }
                        )
                    
                    # Execute function
                    result = await func(*args, **kwargs)
                    
                    # Record usage on success
                    enforcer.record_action(user_id=user_id, action=action)
                    
                    return result
                finally:
                    db.close()
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator
