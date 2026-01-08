"""
OSPRA SECURITY MODULE
=====================

Comprehensive security for Ospra Intelligence:
- JWT Authentication
- Webhook signature verification
- Rate limiting (all endpoints)
- Account lockout (brute force protection)
- Security headers (CSP, HSTS, etc.)
- Audit logging
- Input sanitization
- Password strength validation
"""

# Webhook verification
from ospra_os.security.webhook_verification import (
    WebhookVerifier,
    WebhookConfig,
    WebhookRateLimiter,
    get_webhook_verifier,
    verify_shopify_webhook,
    verify_stripe_webhook,
    verify_lemonsqueezy_webhook,
    webhook_rate_limit,
    generate_test_signature,
    get_webhook_status,
)

# Production security
from ospra_os.security.production_security import (
    SecurityConfig,
    RateLimiter,
    AccountLockout,
    AuditLogger,
    PasswordValidator,
    InputSanitizer,
    SecurityHeadersMiddleware,
    RateLimitMiddleware,
    rate_limiter,
    account_lockout,
    audit_logger,
    password_validator,
    input_sanitizer,
    check_rate_limit,
    check_account_lockout,
    validate_password_strength,
)

__all__ = [
    # Webhook
    "WebhookVerifier",
    "WebhookConfig",
    "WebhookRateLimiter",
    "get_webhook_verifier",
    "verify_shopify_webhook",
    "verify_stripe_webhook",
    "verify_lemonsqueezy_webhook",
    "webhook_rate_limit",
    "generate_test_signature",
    "get_webhook_status",
    # Production Security
    "SecurityConfig",
    "RateLimiter",
    "AccountLockout",
    "AuditLogger",
    "PasswordValidator",
    "InputSanitizer",
    "SecurityHeadersMiddleware",
    "RateLimitMiddleware",
    "rate_limiter",
    "account_lockout",
    "audit_logger",
    "password_validator",
    "input_sanitizer",
    "check_rate_limit",
    "check_account_lockout",
    "validate_password_strength",
]
