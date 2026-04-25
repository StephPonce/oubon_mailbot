"""
Standardized API Response Utilities for Ospra OS
================================================

Provides consistent response formatting across all API endpoints.

Features:
- Success/error response wrappers
- Pagination response helpers
- Error response with error codes
- Request ID inclusion

Usage:
    from ospra_os.utils.api_response import success_response, error_response, paginated_response

    @router.get("/items")
    async def get_items():
        items = [...]
        return success_response(data=items, message="Items retrieved")

    @router.get("/items/{id}")
    async def get_item(id: int):
        item = db.get(id)
        if not item:
            return error_response(message="Item not found", code="NOT_FOUND", status=404)
        return success_response(data=item)

Author: OspraOS
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


# =============================================================================
# RESPONSE MODELS
# =============================================================================

class PaginationMeta(BaseModel):
    """Pagination metadata."""
    page: int
    per_page: int
    total: int
    total_pages: int
    has_next: bool
    has_prev: bool


class APIResponse(BaseModel):
    """Standard API response format."""
    success: bool
    message: Optional[str] = None
    data: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    meta: Optional[Dict[str, Any]] = None
    timestamp: str = None

    def __init__(self, **data):
        if "timestamp" not in data or data["timestamp"] is None:
            data["timestamp"] = datetime.now(timezone.utc).isoformat()
        super().__init__(**data)


# =============================================================================
# RESPONSE BUILDERS
# =============================================================================

def success_response(
    data: Any = None,
    message: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
    status_code: int = 200
) -> Union[Dict, JSONResponse]:
    """
    Create a standardized success response.

    Args:
        data: Response payload
        message: Optional success message
        meta: Optional metadata (timing, counts, etc.)
        status_code: HTTP status code (default: 200)

    Returns:
        Dict or JSONResponse with standardized format
    """
    response = {
        "success": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if message:
        response["message"] = message

    if data is not None:
        response["data"] = data

    if meta:
        response["meta"] = meta

    # Add request ID if available
    try:
        from ospra_os.observability.request_tracing import get_request_id
        request_id = get_request_id()
        if request_id:
            response["request_id"] = request_id
    except ImportError:
        pass

    if status_code != 200:
        return JSONResponse(content=response, status_code=status_code)

    return response


def error_response(
    message: str,
    code: Optional[str] = None,
    details: Optional[Any] = None,
    status_code: int = 400,
    error_id: Optional[str] = None
) -> JSONResponse:
    """
    Create a standardized error response.

    Args:
        message: User-friendly error message
        code: Machine-readable error code (e.g., "VALIDATION_ERROR", "NOT_FOUND")
        details: Additional error details (validation errors, etc.)
        status_code: HTTP status code (default: 400)
        error_id: Unique error ID for support reference

    Returns:
        JSONResponse with standardized error format
    """
    import uuid

    # Generate error ID if not provided
    if error_id is None:
        error_id = str(uuid.uuid4())[:8]

    response = {
        "success": False,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "error": {
            "message": message,
            "error_id": error_id,
        }
    }

    if code:
        response["error"]["code"] = code

    if details:
        response["error"]["details"] = details

    # Add request ID if available
    try:
        from ospra_os.observability.request_tracing import get_request_id
        request_id = get_request_id()
        if request_id:
            response["request_id"] = request_id
    except ImportError:
        pass

    return JSONResponse(content=response, status_code=status_code)


def paginated_response(
    items: List[Any],
    total: int,
    page: int,
    per_page: int,
    message: Optional[str] = None
) -> Dict:
    """
    Create a standardized paginated response.

    Args:
        items: List of items for current page
        total: Total count of items
        page: Current page number (1-indexed)
        per_page: Items per page
        message: Optional message

    Returns:
        Dict with items and pagination metadata
    """
    total_pages = (total + per_page - 1) // per_page if per_page > 0 else 0

    response = {
        "success": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": items,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
        }
    }

    if message:
        response["message"] = message

    # Add request ID if available
    try:
        from ospra_os.observability.request_tracing import get_request_id
        request_id = get_request_id()
        if request_id:
            response["request_id"] = request_id
    except ImportError:
        pass

    return response


def validation_error_response(
    errors: List[Dict[str, Any]],
    message: str = "Validation failed"
) -> JSONResponse:
    """
    Create a standardized validation error response.

    Args:
        errors: List of validation errors with field and message
        message: Overall error message

    Returns:
        JSONResponse with 422 status code
    """
    return error_response(
        message=message,
        code="VALIDATION_ERROR",
        details={"validation_errors": errors},
        status_code=422
    )


def not_found_response(
    resource: str,
    identifier: Optional[Any] = None
) -> JSONResponse:
    """
    Create a standardized 404 not found response.

    Args:
        resource: Type of resource (e.g., "Product", "User")
        identifier: Optional identifier that was not found

    Returns:
        JSONResponse with 404 status code
    """
    if identifier:
        message = f"{resource} with ID '{identifier}' not found"
    else:
        message = f"{resource} not found"

    return error_response(
        message=message,
        code="NOT_FOUND",
        status_code=404
    )


def unauthorized_response(
    message: str = "Authentication required"
) -> JSONResponse:
    """Create a standardized 401 unauthorized response."""
    return error_response(
        message=message,
        code="UNAUTHORIZED",
        status_code=401
    )


def forbidden_response(
    message: str = "Access denied"
) -> JSONResponse:
    """Create a standardized 403 forbidden response."""
    return error_response(
        message=message,
        code="FORBIDDEN",
        status_code=403
    )


def rate_limited_response(
    retry_after: Optional[int] = None
) -> JSONResponse:
    """
    Create a standardized 429 rate limit response.

    Args:
        retry_after: Seconds until rate limit resets
    """
    details = {}
    if retry_after:
        details["retry_after_seconds"] = retry_after

    response = error_response(
        message="Rate limit exceeded. Please try again later.",
        code="RATE_LIMITED",
        details=details if details else None,
        status_code=429
    )

    if retry_after:
        response.headers["Retry-After"] = str(retry_after)

    return response


def server_error_response(
    error_id: Optional[str] = None,
    message: str = "An internal error occurred. Please try again later."
) -> JSONResponse:
    """
    Create a standardized 500 server error response.

    Args:
        error_id: Unique error ID for support reference
        message: User-friendly error message
    """
    return error_response(
        message=message,
        code="INTERNAL_ERROR",
        error_id=error_id,
        status_code=500
    )


# =============================================================================
# EXCEPTION HANDLER
# =============================================================================

async def api_exception_handler(request, exc):
    """
    Global exception handler for consistent error responses.

    Usage in main.py:
        from ospra_os.utils.api_response import api_exception_handler
        app.add_exception_handler(Exception, api_exception_handler)
    """
    import traceback

    error_id = str(__import__("uuid").uuid4())[:8]

    logger.error(
        f"[{error_id}] Unhandled exception: {type(exc).__name__}: {str(exc)}\n"
        f"{traceback.format_exc()}"
    )

    return server_error_response(error_id=error_id)


logger.info("[SUCCESS] API response utilities loaded")
