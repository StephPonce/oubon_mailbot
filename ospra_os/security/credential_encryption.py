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


def _init_fernet():
    """Initialize Fernet cipher lazily."""
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
        # Check if we're in production
        is_production = (
            os.getenv("ENVIRONMENT", "").lower() in ("production", "prod") or
            os.getenv("RENDER", "") == "true" or
            os.getenv("RAILWAY_ENVIRONMENT", "") != ""
        )

        if is_production:
            logger.error(
                "[CRITICAL] CREDENTIALS_ENCRYPTION_KEY not set in production! "
                "Credentials will NOT be encrypted. "
                "Generate key with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
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

    fernet = _init_fernet()
    if fernet is None:
        logger.warning("Encryption unavailable - storing value unencrypted")
        return value

    try:
        encrypted = fernet.encrypt(value.encode())
        return encrypted.decode()
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
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

    fernet = _init_fernet()
    if fernet is None:
        # Assume value was stored unencrypted
        return encrypted_value

    try:
        decrypted = fernet.decrypt(encrypted_value.encode())
        return decrypted.decode()
    except Exception as e:
        # Value might not be encrypted (legacy data)
        logger.debug(f"Decryption failed, assuming plain text: {e}")
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

    fernet = _init_fernet()
    if fernet is None:
        logger.warning("Encryption unavailable - storing credentials as plain JSON")
        return json.dumps(credentials)

    try:
        json_str = json.dumps(credentials)
        encrypted = fernet.encrypt(json_str.encode())
        return encrypted.decode()
    except Exception as e:
        logger.error(f"Credential encryption failed: {e}")
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

    fernet = _init_fernet()
    if fernet is None:
        # Try parsing as plain JSON
        try:
            return json.loads(encrypted_credentials)
        except json.JSONDecodeError:
            return {}

    try:
        decrypted = fernet.decrypt(encrypted_credentials.encode())
        return json.loads(decrypted.decode())
    except Exception:
        # Might be unencrypted JSON (legacy data)
        try:
            return json.loads(encrypted_credentials)
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
