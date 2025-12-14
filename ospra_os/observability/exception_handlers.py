"""
Custom Exception Classes and Handlers
Provides structured exception hierarchy for better error handling.
"""

from typing import Optional, Dict, Any
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from .logger import get_logger
from .error_tracking import capture_exception, ErrorSeverity

logger = get_logger(__name__)


# ============================================================================
# CUSTOM EXCEPTIONS
# ============================================================================

class OspraException(Exception):
    """
    Base exception for all OspraOS errors.

    Attributes:
        message: Human-readable error message
        error_code: Machine-readable error code
        status_code: HTTP status code
        details: Additional error context
    """

    def __init__(
        self,
        message: str,
        error_code: str = "OSPRA_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class ValidationException(OspraException):
    """Raised when input validation fails"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details
        )


class AuthenticationException(OspraException):
    """Raised when authentication fails"""

    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_REQUIRED",
            status_code=status.HTTP_401_UNAUTHORIZED
        )


class AuthorizationException(OspraException):
    """Raised when user lacks required permissions"""

    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(
            message=message,
            error_code="INSUFFICIENT_PERMISSIONS",
            status_code=status.HTTP_403_FORBIDDEN
        )


class NotFoundException(OspraException):
    """Raised when requested resource not found"""

    def __init__(self, resource: str, resource_id: Any):
        super().__init__(
            message=f"{resource} not found: {resource_id}",
            error_code="RESOURCE_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"resource": resource, "resource_id": str(resource_id)}
        )


class RateLimitException(OspraException):
    """Raised when rate limit exceeded"""

    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(
            message=message,
            error_code="RATE_LIMIT_EXCEEDED",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS
        )


class ExternalServiceException(OspraException):
    """Raised when external API call fails"""

    def __init__(self, service: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"{service} error: {message}",
            error_code="EXTERNAL_SERVICE_ERROR",
            status_code=status.HTTP_502_BAD_GATEWAY,
            details={"service": service, **(details or {})}
        )


class TierLimitException(OspraException):
    """Raised when user exceeds tier limits"""

    def __init__(self, tier: str, limit_type: str):
        super().__init__(
            message=f"Tier limit exceeded: {limit_type} (current tier: {tier})",
            error_code="TIER_LIMIT_EXCEEDED",
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            details={"tier": tier, "limit_type": limit_type}
        )


# ============================================================================
# EXCEPTION HANDLERS
# ============================================================================

async def ospra_exception_handler(request: Request, exc: OspraException) -> JSONResponse:
    """
    Handler for custom OspraException errors.

    Returns structured JSON response with error details.
    """

    # Log the error
    logger.error(
        f"OspraException: {exc.message}",
        extra={
            "error_code": exc.error_code,
            "status_code": exc.status_code,
            "details": exc.details,
            "path": request.url.path,
        }
    )

    # Capture in Sentry (only for server errors)
    if exc.status_code >= 500:
        capture_exception(
            exc,
            level=ErrorSeverity.ERROR,
            extra={
                "error_code": exc.error_code,
                "details": exc.details,
            },
            tags={"error_type": "ospra_exception"}
        )

    # Return JSON response
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.error_code,
                "message": exc.message,
                "details": exc.details,
            }
        }
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Handler for FastAPI validation errors (Pydantic).

    Returns structured JSON response with validation details.
    """

    # Extract validation errors
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(x) for x in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        })

    # Log the validation error
    logger.warning(
        f"Validation error on {request.url.path}",
        extra={"validation_errors": errors}
    )

    # Return JSON response
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": {"errors": errors}
            }
        }
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """
    Handler for standard HTTP exceptions (404, 405, etc.).

    Returns structured JSON response.
    """

    # Log the HTTP error
    logger.warning(
        f"HTTP {exc.status_code}: {exc.detail}",
        extra={"path": request.url.path, "status_code": exc.status_code}
    )

    # Return JSON response
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": f"HTTP_{exc.status_code}",
                "message": exc.detail,
            }
        }
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all handler for unhandled exceptions.

    Logs the error, captures in Sentry, and returns generic 500 response.
    """

    # Log the unexpected error
    logger.exception(
        f"Unhandled exception on {request.url.path}",
        extra={"exception_type": type(exc).__name__}
    )

    # Capture in Sentry
    capture_exception(
        exc,
        level=ErrorSeverity.ERROR,
        extra={"path": request.url.path},
        tags={"error_type": "unhandled_exception"}
    )

    # Return generic error response (don't leak internal details)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred. Our team has been notified.",
            }
        }
    )


# ============================================================================
# REGISTRATION HELPER
# ============================================================================

def register_exception_handlers(app):
    """
    Register all exception handlers with FastAPI app.

    Usage:
        from ospra_os.observability.exception_handlers import register_exception_handlers

        app = FastAPI()
        register_exception_handlers(app)
    """

    # Custom exceptions
    app.add_exception_handler(OspraException, ospra_exception_handler)

    # FastAPI built-in exceptions
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)

    # Catch-all for unexpected errors
    app.add_exception_handler(Exception, generic_exception_handler)

    logger.info("Exception handlers registered")
