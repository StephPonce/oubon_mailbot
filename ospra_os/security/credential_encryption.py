"""
Credential Encryption for Ospra OS
===================================

Provides Fernet-based encryption for sensitive credentials stored in the database.

SECURITY: All API tokens, secrets, and credentials MUST be encrypted before
storing in the database using these utilities.

Usage:
    from ospra_os.security.credential_encryption import (
        encrypt_credentials,
        decrypt_credentials,
        encrypt_field,
        decrypt_field,
    )

    # Encrypt a dict of credentials
    encrypted = encrypt_credentials({"access_token": "sk-xxx", "secret": "abc123"})

    # Decrypt when needed
    credentials = decrypt_credentials(encrypted)

    # Encrypt a single field
    encrypted_token = encrypt_field("sk-xxx-secret-token")

Environment Variables:
    CREDENTIALS_ENCRYPTION_KEY: Fernet key for encrypting credentials
        Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Author: OspraOS Security
"""

import os
import json
import logging
from typing import Dict, Any, Optional, Union
from functools import lru_cache

logger = logging.getLogger(__name__)

# Lazy import to avoid startup failures if cryptography not installed
_fernet = None
_encryption_available = False


class CredentialEncryptionError(RuntimeError):
    """
    Raised when credential encryption is required but unavailable.

    In production, every call to ``encrypt_*`` / ``decrypt_*`` MUST
    succeed. The previous behaviour was to log ``[CRITICAL]`` and
    silently store credentials as plain JSON — that's a fail-OPEN posture
    that turned a missing env var into a silent data-at-rest exposure.
    We now fail closed: callers see a clear 500 the first time the key
    is missing or wrong, the operator notices, the env var gets fixed.
    """


def _is_production() -> bool:
    """
    Detect production deployment via standard host markers.

    Centralised so the env-var heuristic is one line to update if we add
    a new host (Fly, Heroku, ...).
    """
    return (
        os.getenv("ENVIRONMENT", "").lower() in ("production", "prod") or
        os.getenv("RENDER", "") == "true" or
        os.getenv("RAILWAY_ENVIRONMENT", "") != ""
    )


def _init_fernet():
    """
    Initialize Fernet cipher lazily.

    Returns the Fernet instance on success. Returns ``None`` ONLY in
    development when the cryptography package is missing or the key is
    intentionally absent — in production, raising is the responsibility
    of the call site (see ``_require_fernet``) so import never crashes
    the whole app.
    """
    global _fernet, _encryption_available

    if _fernet is not None:
        return _fernet

    try:
        from cryptography.fernet import Fernet, InvalidToken
    except ImportError:
        logger.error(
            "[CRITICAL] cryptography package not installed. "
            "Run: pip install cryptography"
        )
        _encryption_available = False
        return None

    # Get encryption key from environment
    key = os.getenv("CREDENTIALS_ENCRYPTION_KEY")

    if not key:
        # Check for legacy key name
        key = os.getenv("EMAIL_OAUTH_ENCRYPTION_KEY")

    if not key:
        if _is_production():
            # Loud, machine-readable, and structured. The actual ``raise``
            # happens at first use (not at import) so the rest of the app
            # can still come up enough to serve /health and surface the
            # error in logs.
            logger.error(
                "[CRITICAL] CREDENTIALS_ENCRYPTION_KEY not set in production. "
                "Refusing to fall back to plaintext storage — every "
                "credential read/write will now raise. Generate a key with: "
                'python -c "from cryptography.fernet import Fernet; '
                'print(Fernet.generate_key().decode())"'
            )
            _encryption_available = False
            return None
        else:
            # Development only - generate temporary key
            key = Fernet.generate_key().decode()
            logger.warning(
                f"[WARNING] CREDENTIALS_ENCRYPTION_KEY not set. "
                f"Using temporary key for development. "
                f"Set CREDENTIALS_ENCRYPTION_KEY={key} in .env for persistence."
            )

    try:
        if isinstance(key, str):
            key = key.encode()
        _fernet = Fernet(key)
        _encryption_available = True
        logger.info("[SUCCESS] Credential encryption initialized")
        return _fernet
    except Exception as e:
        logger.error(f"[CRITICAL] Failed to initialize encryption: {e}")
        _encryption_available = False
        return None


def _require_fernet():
    """
    Get the Fernet instance, raising in production if it's unavailable.

    Wrap every call site that's about to write or read sensitive data.
    Development environments still get the soft-fail behaviour so
    test-suite imports don't blow up if cryptography isn't installed.
    """
    fernet = _init_fernet()
    if fernet is None and _is_production():
        raise CredentialEncryptionError(
            "Credential encryption is unavailable in production. "
            "Set CREDENTIALS_ENCRYPTION_KEY (Fernet key) and restart the "
            "service. See ospra_os/security/credential_encryption.py for "
            "the generation command."
        )
    return fernet


def is_encryption_available() -> bool:
    """Check if encryption is properly configured."""
    _init_fernet()
    return _encryption_available


def encrypt_field(value: str) -> str:
    """
    Encrypt a single string field.

    Args:
        value: Plain text value to encrypt

    Returns:
        str: Base64-encoded encrypted value, or original value if encryption unavailable

    Example:
        encrypted_token = encrypt_field("sk-xxx-secret-token")
    """
    if not value:
        return value

    # Production: raises if the key is missing. Development: falls back
    # to an ephemeral key (set up in ``_init_fernet``).
    fernet = _require_fernet()
    if fernet is None:
        # Development-only branch — cryptography not installed. Returning
        # the raw value is acceptable here because ``_is_production`` is
        # False; ``_require_fernet`` would have raised otherwise.
        logger.warning("Encryption unavailable (dev mode) - storing value unencrypted")
        return value

    try:
        encrypted = fernet.encrypt(value.encode())
        return encrypted.decode()
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        if _is_production():
            raise CredentialEncryptionError(
                f"Field encryption failed in production: {e}"
            ) from e
        return value


def decrypt_field(encrypted_value: str) -> str:
    """
    Decrypt a single string field.

    Args:
        encrypted_value: Base64-encoded encrypted value

    Returns:
        str: Decrypted plain text value

    Raises:
        ValueError: If decryption fails (invalid token or wrong key)
    """
    if not encrypted_value:
        return encrypted_value

    fernet = _require_fernet()
    if fernet is None:
        # Dev-only branch.
        return encrypted_value

    try:
        decrypted = fernet.decrypt(encrypted_value.encode())
        return decrypted.decode()
    except Exception as e:
        # Legacy unencrypted-row tolerance: the value pre-dates
        # encryption and is stored as plain text. We keep returning it,
        # but warn so operators can run a backfill — silent debug-level
        # logging here used to mean nobody noticed unencrypted rows for
        # months.
        logger.warning(
            "decrypt_field: value did not decrypt with current key — "
            "treating as legacy plaintext. Run a credential migration."
        )
        return encrypted_value


def encrypt_credentials(credentials: Dict[str, Any]) -> str:
    """
    Encrypt a dictionary of credentials.

    Args:
        credentials: Dict containing sensitive values (tokens, secrets, etc.)

    Returns:
        str: Base64-encoded encrypted JSON string

    Example:
        encrypted = encrypt_credentials({
            "access_token": "shpat_xxx",
            "refresh_token": "shprt_xxx",
            "shop_url": "mystore.myshopify.com"
        })
    """
    if not credentials:
        return ""

    fernet = _require_fernet()
    if fernet is None:
        # Dev-only branch (cryptography missing). In production
        # ``_require_fernet`` would have raised.
        logger.warning("Encryption unavailable (dev mode) - storing credentials as plain JSON")
        return json.dumps(credentials)

    try:
        json_str = json.dumps(credentials)
        encrypted = fernet.encrypt(json_str.encode())
        return encrypted.decode()
    except Exception as e:
        logger.error(f"Credential encryption failed: {e}")
        if _is_production():
            raise CredentialEncryptionError(
                f"Credential encryption failed in production: {e}"
            ) from e
        return json.dumps(credentials)


def decrypt_credentials(encrypted_credentials: Union[str, Dict]) -> Dict[str, Any]:
    """
    Decrypt a credentials string back to dictionary.

    Args:
        encrypted_credentials: Encrypted string or plain dict (for backwards compatibility)

    Returns:
        Dict: Decrypted credentials dictionary

    Example:
        credentials = decrypt_credentials(store.credentials)
        access_token = credentials.get("access_token")
    """
    if not encrypted_credentials:
        return {}

    # Handle already-decrypted dict (backwards compatibility)
    if isinstance(encrypted_credentials, dict):
        return encrypted_credentials

    fernet = _require_fernet()
    if fernet is None:
        # Dev-only branch. Try parsing as plain JSON.
        try:
            return json.loads(encrypted_credentials)
        except json.JSONDecodeError:
            return {}

    try:
        decrypted = fernet.decrypt(encrypted_credentials.encode())
        return json.loads(decrypted.decode())
    except Exception:
        # Legacy plain-JSON tolerance — same rationale as
        # ``decrypt_field``. Warn at warning-level so unencrypted rows
        # show up in the operator's log feed.
        try:
            parsed = json.loads(encrypted_credentials)
            logger.warning(
                "decrypt_credentials: value did not decrypt with current "
                "key but parsed as plain JSON — treating as legacy row. "
                "Run a credential migration."
            )
            return parsed
        except json.JSONDecodeError:
            logger.error("Failed to decrypt or parse credentials")
            return {}


# ============================================================================
# SENSITIVE FIELD DEFINITIONS
# ============================================================================

# Fields that MUST be encrypted when stored
SENSITIVE_FIELDS = {
    "access_token",
    "refresh_token",
    "api_key",
    "api_secret",
    "secret_key",
    "client_secret",
    "consumer_secret",
    "aws_secret_key",
    "lwa_client_secret",
    "sp_api_client_secret",
    "webhook_secret",
    "password",
    "private_key",
}


def encrypt_sensitive_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Encrypt only the sensitive fields in a dictionary.

    Non-sensitive fields (like URLs, IDs) are left as-is.

    Args:
        data: Dictionary potentially containing sensitive fields

    Returns:
        Dict: Same dictionary with sensitive fields encrypted

    Example:
        # Input:
        {"shop_url": "mystore.com", "access_token": "shpat_xxx"}

        # Output:
        {"shop_url": "mystore.com", "access_token": "gAAA...encrypted..."}
    """
    if not data:
        return data

    result = {}
    for key, value in data.items():
        if key.lower() in SENSITIVE_FIELDS and isinstance(value, str):
            result[key] = encrypt_field(value)
        else:
            result[key] = value

    return result


def decrypt_sensitive_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Decrypt only the sensitive fields in a dictionary.

    Args:
        data: Dictionary with potentially encrypted sensitive fields

    Returns:
        Dict: Same dictionary with sensitive fields decrypted
    """
    if not data:
        return data

    result = {}
    for key, value in data.items():
        if key.lower() in SENSITIVE_FIELDS and isinstance(value, str):
            result[key] = decrypt_field(value)
        else:
            result[key] = value

    return result


# ============================================================================
# SQLALCHEMY INTEGRATION HELPERS
# ============================================================================

class EncryptedCredentialsMixin:
    """
    Mixin for SQLAlchemy models that store encrypted credentials.

    Usage:
        class Store(Base, EncryptedCredentialsMixin):
            credentials = Column(Text)  # Store encrypted string

            def set_credentials(self, creds: dict):
                self.credentials = self._encrypt_creds(creds)

            def get_credentials(self) -> dict:
                return self._decrypt_creds(self.credentials)
    """

    def _encrypt_creds(self, credentials: Dict[str, Any]) -> str:
        """Encrypt credentials for storage."""
        return encrypt_credentials(credentials)

    def _decrypt_creds(self, encrypted: str) -> Dict[str, Any]:
        """Decrypt credentials for use."""
        return decrypt_credentials(encrypted)


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "encrypt_field",
    "decrypt_field",
    "encrypt_credentials",
    "decrypt_credentials",
    "encrypt_sensitive_fields",
    "decrypt_sensitive_fields",
    "is_encryption_available",
    "SENSITIVE_FIELDS",
    "EncryptedCredentialsMixin",
]
