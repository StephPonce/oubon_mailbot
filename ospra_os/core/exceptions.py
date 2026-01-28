"""
Ospra OS Exception Module - DEPRECATED
======================================

This module is deprecated. Use the existing exception handling systems:

1. For API endpoints:
   from ospra_os.security.safe_errors import safe_error_response, safe_endpoint

2. For custom exceptions:
   from ospra_os.observability.exception_handlers import (
       OspraException,
       ValidationException,
       AuthenticationException,
       # etc.
   )

The global exception handlers are registered in main.py via:
   register_exception_handlers(app)
"""

# Re-export from the canonical locations for backwards compatibility
from ospra_os.security.safe_errors import (
    safe_error_response,
    safe_endpoint,
    SafeErrorHandler,
)

from ospra_os.observability.exception_handlers import (
    OspraException,
    ValidationException,
    AuthenticationException,
    AuthorizationException,
    NotFoundException,
    RateLimitException,
    ExternalServiceException,
    TierLimitException,
)

__all__ = [
    "safe_error_response",
    "safe_endpoint",
    "SafeErrorHandler",
    "OspraException",
    "ValidationException",
    "AuthenticationException",
    "AuthorizationException",
    "NotFoundException",
    "RateLimitException",
    "ExternalServiceException",
    "TierLimitException",
]
