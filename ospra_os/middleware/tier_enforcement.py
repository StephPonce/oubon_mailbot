"""
TIER ENFORCEMENT MIDDLEWARE

Enforces subscription tier limits and feature access.
Integrates with Intelligence Core tier system.
"""

import logging
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Dict, Optional

from ospra_os.intelligence.tier_system import get_tier_system, Tier
from ospra_os.database.multi_store_models import SessionLocal

logger = logging.getLogger(__name__)


class TierEnforcementMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce tier limits on API endpoints.

    Features:
    - Rate limiting per tier
    - Feature access control
    - Usage tracking
    """

    # Endpoints that require tier checking
    PROTECTED_ENDPOINTS = {
        '/api/intelligence/briefing/morning': {'feature': 'ai_briefings', 'limit': 'ai_briefings_per_day'},
        '/api/intelligence/briefing/on-demand': {'feature': 'ai_briefings', 'limit': 'ai_briefings_per_day'},
        '/api/intelligence/action/execute': {'feature': 'auto_actions', 'limit': 'auto_actions_per_day'},
        '/api/intelligence/grade/product': {'feature': 'product_grading'},
        '/api/intelligence/progress/product': {'feature': 'progress_tracking'},
    }

    # Endpoints accessible to all tiers (no enforcement)
    PUBLIC_ENDPOINTS = [
        '/api/intelligence/health',
        '/api/intelligence/tier/info',
        '/health',
        '/docs',
        '/openapi.json',
    ]

    def __init__(self, app):
        super().__init__(app)
        self.usage_cache: Dict[int, Dict[str, int]] = {}  # user_id -> {limit_type: count}

    async def dispatch(self, request: Request, call_next):
        """Process request and enforce tier limits"""

        # Skip tier enforcement for public endpoints
        if any(request.url.path.startswith(endpoint) for endpoint in self.PUBLIC_ENDPOINTS):
            return await call_next(request)

        # Skip tier enforcement for non-protected endpoints
        if request.url.path not in self.PROTECTED_ENDPOINTS:
            return await call_next(request)

        # Get user ID from request (query params, headers, or JWT)
        user_id = await self._extract_user_id(request)

        if not user_id:
            # No user ID provided - allow request but log warning
            logger.warning(f"No user_id for tier enforcement on {request.url.path}")
            return await call_next(request)

        # Check tier access for this endpoint
        try:
            enforcement_config = self.PROTECTED_ENDPOINTS[request.url.path]
            feature = enforcement_config.get('feature')
            limit_type = enforcement_config.get('limit')

            # Check feature access
            if feature:
                has_access = await self._check_feature_access(user_id, feature)
                if not has_access:
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={
                            "error": "Feature not available in your tier",
                            "feature": feature,
                            "upgrade_required": True,
                            "message": f"Upgrade to access {feature}"
                        }
                    )

            # Check usage limits
            if limit_type:
                within_limit = await self._check_usage_limit(user_id, limit_type)
                if not within_limit:
                    return JSONResponse(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        content={
                            "error": "Usage limit exceeded",
                            "limit_type": limit_type,
                            "upgrade_required": True,
                            "message": f"Daily limit for {limit_type} exceeded. Upgrade for higher limits."
                        }
                    )

            # Increment usage counter
            if limit_type:
                self._increment_usage(user_id, limit_type)

        except Exception as e:
            logger.error(f"Tier enforcement error: {e}")
            # On error, allow request to proceed (fail open)
            return await call_next(request)

        # Proceed with request
        response = await call_next(request)
        return response

    async def _extract_user_id(self, request: Request) -> Optional[int]:
        """Extract user ID from request"""
        # Try query parameters
        user_id = request.query_params.get('user_id')
        if user_id:
            return int(user_id)

        # Try headers
        user_id = request.headers.get('X-User-ID')
        if user_id:
            return int(user_id)

        # TODO: Extract from JWT token in Authorization header
        # auth_header = request.headers.get('Authorization')
        # if auth_header:
        #     token = auth_header.replace('Bearer ', '')
        #     user_id = decode_jwt(token).get('user_id')
        #     return user_id

        return None

    async def _check_feature_access(self, user_id: int, feature: str) -> bool:
        """Check if user has access to feature"""
        try:
            db = SessionLocal()
            tier_system = get_tier_system(db)
            has_access = await tier_system.check_feature_access(user_id, feature)
            db.close()
            return has_access
        except Exception as e:
            logger.error(f"Feature access check failed: {e}")
            return True  # Fail open

    async def _check_usage_limit(self, user_id: int, limit_type: str) -> bool:
        """Check if user is within usage limit"""
        try:
            # Get current usage from cache
            current_usage = self.usage_cache.get(user_id, {}).get(limit_type, 0)

            db = SessionLocal()
            tier_system = get_tier_system(db)

            # Check limit
            limit_check = await tier_system.check_limit(user_id, limit_type, current_usage)
            db.close()

            return limit_check.get('within_limit', True)

        except Exception as e:
            logger.error(f"Usage limit check failed: {e}")
            return True  # Fail open

    def _increment_usage(self, user_id: int, limit_type: str):
        """Increment usage counter for user"""
        if user_id not in self.usage_cache:
            self.usage_cache[user_id] = {}

        if limit_type not in self.usage_cache[user_id]:
            self.usage_cache[user_id][limit_type] = 0

        self.usage_cache[user_id][limit_type] += 1

        logger.debug(f"Usage increment: user {user_id}, {limit_type} = {self.usage_cache[user_id][limit_type]}")

    def reset_usage_cache(self):
        """Reset usage cache (call daily)"""
        logger.info("Resetting tier usage cache")
        self.usage_cache.clear()


# Singleton instance
_tier_middleware = None


def get_tier_enforcement_middleware(app) -> TierEnforcementMiddleware:
    """Get or create tier enforcement middleware"""
    global _tier_middleware
    if _tier_middleware is None:
        _tier_middleware = TierEnforcementMiddleware(app)
    return _tier_middleware
