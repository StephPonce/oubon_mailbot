"""
Base Email OAuth Handler

Abstract base class for all email OAuth providers (Gmail, Outlook, Yahoo).
Provides encryption, credential storage, and OAuth flow management.
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional
import json
import os
from cryptography.fernet import Fernet


class EmailOAuthHandler(ABC):
    """
    Abstract base class for email OAuth providers.

    Each provider (Gmail, Outlook, Yahoo) implements this interface
    to handle OAuth 2.0 authorization flows and credential management.
    """

    def __init__(self):
        """Initialize OAuth handler with encryption key from environment."""
        self.encryption_key = self._get_encryption_key()
        self.fernet = Fernet(self.encryption_key)

    def _get_encryption_key(self) -> bytes:
        """
        Get or generate encryption key for credentials.

        Returns:
            bytes: Fernet encryption key
        """
        key = os.getenv('EMAIL_OAUTH_ENCRYPTION_KEY')

        if not key:
            # Generate new key if not set (for development)
            key = Fernet.generate_key().decode()
            print(f"⚠️  Generated new encryption key. Set EMAIL_OAUTH_ENCRYPTION_KEY={key}")

        if isinstance(key, str):
            key = key.encode()

        return key

    @abstractmethod
    async def get_authorization_url(self, state: str, redirect_uri: str) -> str:
        """
        Generate OAuth authorization URL for user consent.

        Args:
            state: CSRF protection state parameter
            redirect_uri: OAuth callback URL

        Returns:
            str: Authorization URL to redirect user to
        """
        pass

    @abstractmethod
    async def exchange_code_for_token(self, code: str, redirect_uri: str) -> Dict:
        """
        Exchange authorization code for access and refresh tokens.

        Args:
            code: Authorization code from OAuth callback
            redirect_uri: OAuth callback URL (must match authorization)

        Returns:
            Dict: Token response with access_token, refresh_token, expires_in
        """
        pass

    @abstractmethod
    async def refresh_access_token(self, refresh_token: str) -> Dict:
        """
        Refresh expired access token using refresh token.

        Args:
            refresh_token: Refresh token from initial authorization

        Returns:
            Dict: New token response with access_token, expires_in
        """
        pass

    @abstractmethod
    async def get_user_profile(self, access_token: str) -> Dict:
        """
        Fetch user profile/email address using access token.

        Args:
            access_token: Valid OAuth access token

        Returns:
            Dict: User profile with email address
        """
        pass

    def encrypt_credentials(self, credentials: Dict) -> str:
        """
        Encrypt OAuth credentials for secure database storage.

        Args:
            credentials: Dict containing tokens and OAuth data

        Returns:
            str: Encrypted credentials as base64 string
        """
        credentials_json = json.dumps(credentials)
        encrypted = self.fernet.encrypt(credentials_json.encode())
        return encrypted.decode()

    def decrypt_credentials(self, encrypted_credentials: str) -> Dict:
        """
        Decrypt stored OAuth credentials.

        Args:
            encrypted_credentials: Encrypted credentials from database

        Returns:
            Dict: Decrypted credentials dictionary
        """
        decrypted = self.fernet.decrypt(encrypted_credentials.encode())
        return json.loads(decrypted.decode())
