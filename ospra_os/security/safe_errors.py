"""
Safe Error Handling for Ospra OS
================================

Provides secure error responses that don't leak implementation details,
stack traces, or sensitive information to API consumers.

SECURITY: Never expose internal errors, file paths, or stack traces to users.

Usage:
    from ospra_os.security.safe_errors import safe_error_response, SafeErrorHandler

    # Quick helper
    return safe_error_response(e, "Failed to process request")

    # Context manager
    with SafeErrorHandler("product deployment") as handler:
        result = await deploy_product(...)
    if handler.error:
        return handler.response

Author: OspraOS Security
"""

import os
import logging
import traceback
import uuid
from typing import Optional, Dict, Any
from datetime import datetime
from functools import wraps

logger = logging.getLogger(__name__)

# Check if we're in development mode
_is_development = os.getenv("ENVIRONMENT", "development").lower() in ("development", "dev", "local")


def _is_production() -> bool:
    """Check if running in production environment."""
    return (
        os.getenv("ENVIRONMENT", "").lower() in ("production", "prod") or
        os.getenv("RENDER", "") == "true" or
        os.getenv("RAILWAY_ENVIRONMENT", "") != "" or
        os.getenv("VERCEL", "") == "1" or
        os.getenv("HEROKU", "") == "1"
    )


def safe_error_response(
    error: Exception,
    user_message: str = "An error occurred",
    status_code: int = 500,
    include_error_id: bool = True,
    log_error: bool = True
) -> Dict[str, Any]:
    """
    Create a safe error response that doesn't leak sensitive information.

    Args:
        error: The exception that occurred
        user_message: A user-friendly message to display
        status_code: HTTP status code (for reference, not returned)
        include_error_id: Include a unique error ID for support reference
        log_error: Whether to log the full error details

    Returns:
        A safe dictionary response suitable for API consumers

    Example:
        try:
            result = await process_data()
        except Exception as e:
            return safe_error_response(e, "Failed to process data")
    """
    # Generate unique error ID for tracking
    error_id = str(uuid.uuid4())[:8] if include_error_id else None

    # Log the full error details server-side
    if log_error:
        logger.error(
            f"[ERROR_ID:{error_id}] {user_message}: {type(error).__name__}: {str(error)}\n"
            f"Traceback:\n{traceback.format_exc()}"
        )

    # Build safe response
    response = {
        "success": False,
        "error": user_message,
    }

    if error_id:
        response["error_id"] = error_id
        response["support_message"] = f"If this persists, contact support with error ID: {error_id}"

    # In development, include more details (but never in production)
    if _is_development and not _is_production():
        response["_dev_error_type"] = type(error).__name__
        response["_dev_error_message"] = str(error)[:200]  # Truncate
        # Still don't include full traceback even in dev for API responses

    return response


def safe_error_detail(error: Exception) -> str:
    """
    Get a safe error detail string for HTTPException.

    Never includes stack traces or sensitive information.

    Args:
        error: The exception

    Returns:
        A safe error message string
    """
    error_id = str(uuid.uuid4())[:8]

    # Log full error
    logger.error(
        f"[ERROR_ID:{error_id}] {type(error).__name__}: {str(error)}\n"
        f"Traceback:\n{traceback.format_exc()}"
    )

    # Return safe message
    if _is_development and not _is_production():
        return f"Error: {type(error).__name__} (ID: {error_id})"

    return f"An error occurred. Reference ID: {error_id}"


class SafeErrorHandler:
    """
    Context manager for safe error handling.

    Usage:
        with SafeErrorHandler("deploying product") as handler:
            result = await deploy_product(product_id)

        if handler.error:
            return handler.response
        return {"success": True, "data": result}
    """

    def __init__(
        self,
        operation_name: str,
        user_message: Optional[str] = None,
        log_errors: bool = True
    ):
        self.operation_name = operation_name
        self.user_message = user_message or f"Failed while {operation_name}"
        self.log_errors = log_errors
        self.error: Optional[Exception] = None
        self.error_id: Optional[str] = None
        self.response: Optional[Dict[str, Any]] = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val is not None:
            self.error = exc_val
            self.error_id = str(uuid.uuid4())[:8]

            # Log the full error
            if self.log_errors:
                logger.error(
                    f"[ERROR_ID:{self.error_id}] {self.operation_name} failed: "
                    f"{type(exc_val).__name__}: {str(exc_val)}\n"
                    f"Traceback:\n{traceback.format_exc()}"
                )

            # Build safe response
            self.response = {
                "success": False,
                "error": self.user_message,
                "error_id": self.error_id,
            }

            if _is_development and not _is_production():
                self.response["_dev_error_type"] = type(exc_val).__name__
                self.response["_dev_error_message"] = str(exc_val)[:200]

            # Suppress the exception (we've handled it)
            return True

        return False


def safe_endpoint(operation_name: str, user_message: Optional[str] = None):
    """
    Decorator for safe error handling on FastAPI endpoints.

    Usage:
        @router.get("/products/{id}")
        @safe_endpoint("fetching product")
        async def get_product(product_id: str):
            return await fetch_product(product_id)
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                return safe_error_response(
                    e,
                    user_message or f"Failed while {operation_name}"
                )
        return wrapper
    return decorator


# =============================================================================
# ERROR CATEGORIES
# =============================================================================

def database_error_response(error: Exception) -> Dict[str, Any]:
    """Safe response for database errors."""
    return safe_error_response(
        error,
        "A database error occurred. Please try again later."
    )


def external_api_error_response(error: Exception, service_name: str = "external service") -> Dict[str, Any]:
    """Safe response for external API errors."""
    return safe_error_response(
        error,
        f"Unable to connect to {service_name}. Please try again later."
    )


def validation_error_response(error: Exception, field: Optional[str] = None) -> Dict[str, Any]:
    """Safe response for validation errors."""
    if field:
        message = f"Invalid value for {field}"
    else:
        message = "Invalid request data"

    return safe_error_response(error, message, status_code=400)


def authentication_error_response(error: Exception) -> Dict[str, Any]:
    """Safe response for authentication errors."""
    return safe_error_response(
        error,
        "Authentication failed. Please check your credentials.",
        status_code=401
    )


def authorization_error_response(error: Exception) -> Dict[str, Any]:
    """Safe response for authorization errors."""
    return safe_error_response(
        error,
        "You don't have permission to perform this action.",
        status_code=403
    )


def not_found_error_response(resource: str = "Resource") -> Dict[str, Any]:
    """Safe response for not found errors."""
    return {
        "success": False,
        "error": f"{resource} not found",
        "status_code": 404
    }


def rate_limit_error_response() -> Dict[str, Any]:
    """Safe response for rate limit errors."""
    return {
        "success": False,
        "error": "Too many requests. Please slow down and try again.",
        "status_code": 429
    }


# =============================================================================
# MIGRATION HELPER
# =============================================================================

def replace_traceback_response(error: Exception, operation: str) -> Dict[str, Any]:
    """
    Drop-in replacement for the old traceback.format_exc() pattern.

    Old code:
        return {"success": False, "error": str(e), "traceback": traceback.format_exc()}

    New code:
        return replace_traceback_response(e, "product discovery")
    """
    return safe_error_response(error, f"Failed during {operation}")


# =============================================================================
# DEBUG ENDPOINT PROTECTION
# =============================================================================

def is_debug_allowed() -> bool:
    """
    Check if debug endpoints should be accessible.

    Debug endpoints should NEVER be accessible in production.
    """
    if _is_production():
        return False

    # Allow in development if explicitly enabled
    return os.getenv("ENABLE_DEBUG_ENDPOINTS", "false").lower() == "true"


def require_debug_mode():
    """
    FastAPI dependency to protect debug endpoints.

    Usage:
        @router.get("/debug/routes")
        async def debug_routes(_: None = Depends(require_debug_mode)):
            ...
    """
    from fastapi import HTTPException

    if not is_debug_allowed():
        raise HTTPException(
            status_code=404,
            detail="Not found"  # Don't reveal endpoint exists
        )
