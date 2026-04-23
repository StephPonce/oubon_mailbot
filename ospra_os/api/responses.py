"""
Standardized API Response Helpers
=================================

Provides consistent response formats across all API endpoints.

Standard Response Format:
{
    "success": true/false,
    "data": {...} or [...],    # For successful responses
    "message": "...",          # Optional message
    "error": "...",            # For error responses
    "error_code": "...",       # Machine-readable error code
    "meta": {...}              # Optional metadata (pagination, etc.)
}

Usage:
    from ospra_os.api.responses import success_response, error_response, paginated_response

    @router.get("/items")
    async def get_items():
        items = get_items_from_db()
        return success_response(data=items, message="Items retrieved successfully")

    @router.get("/items/{id}")
    async def get_item(id: int):
        item = get_item_from_db(id)
        if not item:
            return error_response("Item not found", error_code="ITEM_NOT_FOUND", status_code=404)
        return success_response(data=item)

Author: OspraOS
"""

from typing import Any, Optional, List, Dict
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)


def success_response(
    data: Any = None,
    message: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
    status_code: int = 200
) -> Dict[str, Any]:
    """
    Create a standardized success response.

    Args:
        data: Response data (any JSON-serializable type)
        message: Optional success message
        meta: Optional metadata (pagination, etc.)
        status_code: HTTP status code (default 200)

    Returns:
        Dictionary with standard success format
    """
    response = {
        "success": True,
    }

    if data is not None:
        response["data"] = data

    if message:
        response["message"] = message

    if meta:
        response["meta"] = meta

    return response


def error_response(
    error: str,
    error_code: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    status_code: int = 400
) -> JSONResponse:
    """
    Create a standardized error response.

    Args:
        error: Human-readable error message
        error_code: Machine-readable error code (e.g., "VALIDATION_ERROR")
        details: Additional error details
        status_code: HTTP status code (default 400)

    Returns:
        JSONResponse with standard error format
    """
    content = {
        "success": False,
        "error": error,
    }

    if error_code:
        content["error_code"] = error_code

    if details:
        content["details"] = details

    return JSONResponse(status_code=status_code, content=content)


def paginated_response(
    data: List[Any],
    total: int,
    page: int,
    per_page: int,
    message: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a standardized paginated response.

    Args:
        data: List of items for current page
        total: Total number of items across all pages
        page: Current page number (1-indexed)
        per_page: Items per page
        message: Optional message

    Returns:
        Dictionary with standard paginated format
    """
    total_pages = (total + per_page - 1) // per_page if per_page > 0 else 0

    return {
        "success": True,
        "data": data,
        "meta": {
            "pagination": {
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            }
        },
        "message": message
    }


def list_response(
    data: List[Any],
    message: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a standardized list response (without pagination).

    Args:
        data: List of items
        message: Optional message

    Returns:
        Dictionary with standard list format
    """
    return {
        "success": True,
        "data": data,
        "meta": {
            "count": len(data)
        },
        "message": message
    }


def created_response(
    data: Any,
    message: str = "Resource created successfully"
) -> Dict[str, Any]:
    """
    Create a standardized 201 Created response.

    Args:
        data: Created resource data
        message: Success message

    Returns:
        Dictionary with standard created format
    """
    return {
        "success": True,
        "data": data,
        "message": message
    }


def deleted_response(
    message: str = "Resource deleted successfully",
    resource_id: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Create a standardized delete response.

    Args:
        message: Success message
        resource_id: ID of deleted resource

    Returns:
        Dictionary with standard deleted format
    """
    response = {
        "success": True,
        "message": message
    }

    if resource_id is not None:
        response["deleted_id"] = resource_id

    return response


# Common error codes
class ErrorCodes:
    """Standard error codes for consistent error handling."""

    # Authentication errors
    AUTH_REQUIRED = "AUTH_REQUIRED"
    INVALID_TOKEN = "INVALID_TOKEN"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    INSUFFICIENT_PERMISSIONS = "INSUFFICIENT_PERMISSIONS"

    # Validation errors
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_INPUT = "INVALID_INPUT"
    MISSING_FIELD = "MISSING_FIELD"

    # Resource errors
    NOT_FOUND = "NOT_FOUND"
    ALREADY_EXISTS = "ALREADY_EXISTS"
    CONFLICT = "CONFLICT"

    # Rate limiting
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"

    # Server errors
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"


logger.info("[SUCCESS] API response helpers loaded")
