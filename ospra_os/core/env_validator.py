"""
Environment Variable Validator for Ospra OS
============================================

Validates required and optional environment variables at application startup.
Provides clear error messages for missing or invalid configuration.

Features:
- Required vs optional variable validation
- Type validation (string, int, bool, url, email)
- Pattern validation (regex)
- Production-specific requirements
- Helpful error messages with documentation links

Usage:
    from ospra_os.core.env_validator import validate_environment

    # Call at app startup
    validate_environment()  # Raises ConfigurationError if invalid

Author: OspraOS
"""

import os
import re
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Pattern
from enum import Enum

logger = logging.getLogger(__name__)


# =============================================================================
# EXCEPTIONS
# =============================================================================

class ConfigurationError(Exception):
    """Raised when environment configuration is invalid."""
    def __init__(self, message: str, errors: List[str] = None):
        self.errors = errors or []
        super().__init__(message)


# =============================================================================
# VALIDATION TYPES
# =============================================================================

class VarType(Enum):
    """Environment variable types."""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    URL = "url"
    EMAIL = "email"
    PATH = "path"


@dataclass
class EnvVar:
    """Definition of an environment variable."""
    name: str
    description: str
    required: bool = False
    required_in_production: bool = False
    var_type: VarType = VarType.STRING
    default: Any = None
    pattern: Optional[str] = None
    min_length: Optional[int] = None
    choices: Optional[List[str]] = None
    sensitive: bool = False  # Don't log value


# =============================================================================
# ENVIRONMENT VARIABLE DEFINITIONS
# =============================================================================

# Core application variables
CORE_VARS = [
    EnvVar(
        name="DATABASE_URL",
        description="PostgreSQL database connection URL",
        required_in_production=True,
        var_type=VarType.URL,
        default="sqlite+aiosqlite:///./ospra_os.db"
    ),
    EnvVar(
        name="SECRET_KEY",
        description="Application secret key for sessions",
        required_in_production=True,
        sensitive=True,
        min_length=32
    ),
    EnvVar(
        name="JWT_SECRET_KEY",
        description="Secret key for JWT token signing",
        required_in_production=True,
        sensitive=True,
        min_length=32
    ),
    EnvVar(
        name="ENVIRONMENT",
        description="Deployment environment",
        default="development",
        choices=["development", "staging", "production", "prod", "test"]
    ),
]

# AI Provider variables
AI_VARS = [
    EnvVar(
        name="ANTHROPIC_API_KEY",
        description="Anthropic Claude API key",
        pattern=r"^sk-ant-",
        sensitive=True
    ),
    EnvVar(
        name="OPENAI_API_KEY",
        description="OpenAI API key",
        pattern=r"^sk-",
        sensitive=True
    ),
    EnvVar(
        name="GOOGLE_AI_API_KEY",
        description="Google AI (Gemini) API key",
        sensitive=True
    ),
    EnvVar(
        name="XAI_API_KEY",
        description="xAI Grok API key",
        sensitive=True
    ),
    EnvVar(
        name="GROQ_API_KEY",
        description="Groq API key",
        sensitive=True
    ),
]

# E-commerce integration variables
ECOMMERCE_VARS = [
    EnvVar(
        name="SHOPIFY_API_KEY",
        description="Shopify API key for store integration"
    ),
    EnvVar(
        name="SHOPIFY_API_SECRET",
        description="Shopify API secret",
        sensitive=True
    ),
    EnvVar(
        name="SHOPIFY_WEBHOOK_SECRET",
        description="Secret for verifying Shopify webhooks",
        sensitive=True
    ),
]

# Payment variables
PAYMENT_VARS = [
    EnvVar(
        name="LEMONSQUEEZY_API_KEY",
        description="LemonSqueezy API key for payments",
        sensitive=True
    ),
    EnvVar(
        name="LEMONSQUEEZY_WEBHOOK_SECRET",
        description="Secret for verifying LemonSqueezy webhooks",
        sensitive=True
    ),
    EnvVar(
        name="LEMONSQUEEZY_STORE_ID",
        description="LemonSqueezy store ID",
        var_type=VarType.INTEGER
    ),
]

# Email OAuth variables
EMAIL_VARS = [
    EnvVar(
        name="EMAIL_OAUTH_ENCRYPTION_KEY",
        description="Fernet key for encrypting email OAuth tokens",
        required_in_production=True,
        sensitive=True,
        min_length=32
    ),
    EnvVar(
        name="GOOGLE_CLIENT_ID",
        description="Google OAuth client ID for Gmail"
    ),
    EnvVar(
        name="GOOGLE_CLIENT_SECRET",
        description="Google OAuth client secret",
        sensitive=True
    ),
]

# AliExpress variables
ALIEXPRESS_VARS = [
    EnvVar(
        name="ALIEXPRESS_APP_KEY",
        description="AliExpress API app key"
    ),
    EnvVar(
        name="ALIEXPRESS_APP_SECRET",
        description="AliExpress API app secret",
        sensitive=True
    ),
]

# External services
SERVICE_VARS = [
    EnvVar(
        name="REDIS_URL",
        description="Redis connection URL for caching/queues",
        var_type=VarType.URL
    ),
    EnvVar(
        name="SUPABASE_URL",
        description="Supabase project URL",
        var_type=VarType.URL
    ),
    EnvVar(
        name="SUPABASE_KEY",
        description="Supabase service key",
        sensitive=True
    ),
    EnvVar(
        name="APIFY_TOKEN",
        description="Apify API token for web scraping",
        sensitive=True
    ),
]


# All variable definitions
ALL_ENV_VARS = CORE_VARS + AI_VARS + ECOMMERCE_VARS + PAYMENT_VARS + EMAIL_VARS + ALIEXPRESS_VARS + SERVICE_VARS


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================

def is_production() -> bool:
    """Check if running in production environment."""
    env = os.getenv("ENVIRONMENT", "development").lower()
    production_indicators = [
        env in ("production", "prod"),
        os.getenv("RENDER") == "true",
        os.getenv("RAILWAY_ENVIRONMENT") is not None,
        os.getenv("VERCEL") == "1",
        os.getenv("HEROKU") == "1",
        os.getenv("AWS_LAMBDA_FUNCTION_NAME") is not None,
        os.getenv("GOOGLE_CLOUD_PROJECT") is not None,
    ]
    return any(production_indicators)


def validate_var_type(value: str, var_type: VarType) -> tuple[bool, str]:
    """Validate a value against its expected type."""
    if var_type == VarType.STRING:
        return True, ""

    elif var_type == VarType.INTEGER:
        try:
            int(value)
            return True, ""
        except ValueError:
            return False, f"must be an integer, got '{value}'"

    elif var_type == VarType.FLOAT:
        try:
            float(value)
            return True, ""
        except ValueError:
            return False, f"must be a number, got '{value}'"

    elif var_type == VarType.BOOLEAN:
        if value.lower() in ("true", "false", "1", "0", "yes", "no"):
            return True, ""
        return False, f"must be a boolean (true/false), got '{value}'"

    elif var_type == VarType.URL:
        url_pattern = r"^(https?|postgresql|postgres|redis|sqlite)://"
        if re.match(url_pattern, value):
            return True, ""
        return False, f"must be a valid URL"

    elif var_type == VarType.EMAIL:
        email_pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        if re.match(email_pattern, value):
            return True, ""
        return False, f"must be a valid email address"

    elif var_type == VarType.PATH:
        if os.path.exists(value) or not os.path.isabs(value):
            return True, ""
        return False, f"path does not exist: {value}"

    return True, ""


def validate_env_var(var: EnvVar, in_production: bool) -> Optional[str]:
    """
    Validate a single environment variable.

    Returns:
        Error message if invalid, None if valid
    """
    value = os.getenv(var.name)

    # Check if required
    is_required = var.required or (var.required_in_production and in_production)

    if value is None or value == "":
        if is_required:
            return f"{var.name} is required: {var.description}"
        return None  # Optional and not set - OK

    # Type validation
    valid, error = validate_var_type(value, var.var_type)
    if not valid:
        return f"{var.name} {error}"

    # Min length validation
    if var.min_length and len(value) < var.min_length:
        return f"{var.name} must be at least {var.min_length} characters"

    # Pattern validation
    if var.pattern and not re.match(var.pattern, value):
        return f"{var.name} has invalid format (expected pattern: {var.pattern})"

    # Choices validation
    if var.choices and value not in var.choices:
        return f"{var.name} must be one of: {', '.join(var.choices)}"

    return None


def validate_environment(
    fail_fast: bool = False,
    require_ai_provider: bool = True
) -> Dict[str, Any]:
    """
    Validate all environment variables.

    Args:
        fail_fast: Raise immediately on first error
        require_ai_provider: Require at least one AI provider key

    Returns:
        Dict with validation results

    Raises:
        ConfigurationError: If validation fails and fail_fast is True
    """
    in_production = is_production()
    errors: List[str] = []
    warnings: List[str] = []
    configured: List[str] = []

    logger.info(f"Validating environment (production={in_production})...")

    # Validate all variables
    for var in ALL_ENV_VARS:
        error = validate_env_var(var, in_production)
        if error:
            if var.required or (var.required_in_production and in_production):
                errors.append(error)
                if fail_fast:
                    raise ConfigurationError(error, [error])
            else:
                warnings.append(error)
        elif os.getenv(var.name):
            configured.append(var.name)

    # Check for at least one AI provider
    if require_ai_provider:
        ai_keys = ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_AI_API_KEY", "XAI_API_KEY", "GROQ_API_KEY"]
        has_ai_provider = any(os.getenv(key) for key in ai_keys)
        if not has_ai_provider:
            warnings.append("No AI provider API key configured (ANTHROPIC_API_KEY, OPENAI_API_KEY, etc.)")

    # Log results
    if configured:
        logger.info(f"Configured variables: {', '.join(configured)}")

    for warning in warnings:
        logger.warning(f"Config warning: {warning}")

    if errors:
        error_msg = f"Environment validation failed with {len(errors)} error(s)"
        logger.error(error_msg)
        for error in errors:
            logger.error(f"  - {error}")

        if in_production:
            raise ConfigurationError(error_msg, errors)
        else:
            logger.warning("Continuing in development mode despite configuration errors")

    else:
        logger.info("[SUCCESS] Environment validation passed")

    return {
        "valid": len(errors) == 0,
        "production": in_production,
        "errors": errors,
        "warnings": warnings,
        "configured": configured
    }


def get_missing_required_vars() -> List[str]:
    """Get list of missing required environment variables."""
    in_production = is_production()
    missing = []

    for var in ALL_ENV_VARS:
        is_required = var.required or (var.required_in_production and in_production)
        if is_required and not os.getenv(var.name):
            missing.append(var.name)

    return missing


def print_env_template():
    """Print a template .env file with all variables."""
    print("# Ospra OS Environment Configuration")
    print("# Generated template - fill in your values\n")

    categories = [
        ("Core", CORE_VARS),
        ("AI Providers", AI_VARS),
        ("E-commerce", ECOMMERCE_VARS),
        ("Payments", PAYMENT_VARS),
        ("Email", EMAIL_VARS),
        ("AliExpress", ALIEXPRESS_VARS),
        ("Services", SERVICE_VARS),
    ]

    for category_name, vars_list in categories:
        print(f"\n# === {category_name} ===")
        for var in vars_list:
            required_marker = " (REQUIRED)" if var.required or var.required_in_production else ""
            print(f"# {var.description}{required_marker}")
            default = f'"{var.default}"' if var.default else '""'
            print(f"{var.name}={default}")


logger.info("[SUCCESS] env_validator module loaded")
