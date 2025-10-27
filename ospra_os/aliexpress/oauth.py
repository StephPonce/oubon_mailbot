"""
AliExpress OAuth 2.0 Implementation for Dropshipping Solution API.

This module handles OAuth authentication to get access tokens for
AliExpress Dropshipping Solution APIs.
"""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import secrets
import requests
from urllib.parse import urlencode
from sqlalchemy import Column, Integer, String, DateTime, Boolean, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

Base = declarative_base()


class AliExpressToken(Base):
    """Store AliExpress OAuth tokens."""
    __tablename__ = "aliexpress_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    access_token = Column(String, nullable=False)
    refresh_token = Column(String)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_valid = Column(Boolean, default=True)


class AliExpressOAuth:
    """
    Handle AliExpress OAuth 2.0 authentication.

    Flow:
    1. User clicks "Connect AliExpress"
    2. Redirect to AliExpress authorization page
    3. User approves
    4. AliExpress redirects back with code
    5. Exchange code for access_token
    6. Store token in database
    """

    # AliExpress OAuth endpoints for Dropshipping Solution API
    AUTHORIZE_URL = "https://oauth.aliexpress.com/authorize"
    # Use the generateSecurityToken API for token exchange
    TOKEN_URL = "https://openservice.aliexpress.com/auth/token/security/create"

    def __init__(self, app_key: str, app_secret: str, redirect_uri: str, database_url: str = None):
        self.app_key = app_key
        self.app_secret = app_secret
        self.redirect_uri = redirect_uri
        self.database_url = database_url

        # Initialize database (optional for now)
        if database_url:
            self._init_db()

    def _init_db(self):
        """Initialize token storage database."""
        sync_url = self.database_url.replace("+aiosqlite", "")
        self.engine = create_engine(sync_url, echo=False)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

    def get_authorization_url(self, state: Optional[str] = None) -> str:
        """
        Generate OAuth authorization URL.

        Args:
            state: Optional state parameter for CSRF protection

        Returns:
            Full authorization URL to redirect user to
        """
        if state is None:
            state = secrets.token_urlsafe(32)

        params = {
            "client_id": self.app_key,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "state": state
        }

        return f"{self.AUTHORIZE_URL}?{urlencode(params)}"

    def _generate_signature(self, params: Dict[str, str]) -> str:
        """Generate HMAC-SHA256 signature for API request."""
        sorted_params = sorted(params.items())
        sign_string = "".join([f"{k}{v}" for k, v in sorted_params])
        signature = hmac.new(
            self.app_secret.encode('utf-8'),
            sign_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest().upper()
        return signature

    def exchange_code_for_token(self, authorization_code: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access token using generateSecurityToken API.

        Args:
            authorization_code: Code received from OAuth callback

        Returns:
            Token response with access_token, refresh_token, expires_in
        """
        import time

        params = {
            "app_key": self.app_key,
            "method": "generateSecurityToken",
            "timestamp": str(int(time.time() * 1000)),
            "format": "json",
            "v": "2.0",
            "sign_method": "sha256",
            "code": authorization_code,
        }

        # Generate signature
        params["sign"] = self._generate_signature(params)

        try:
            response = requests.post(self.TOKEN_URL, params=params, timeout=15)

            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}",
                    "details": response.text
                }

            data = response.json()

            # Check for API errors
            if "error_response" in data:
                error = data["error_response"]
                return {
                    "success": False,
                    "error": error.get("code", "unknown"),
                    "error_description": error.get("msg", "Unknown error")
                }

            # Success - extract token info from generateSecurityToken_response
            token_data = data.get("generateSecurityToken_response", {})

            access_token = token_data.get("access_token")
            refresh_token = token_data.get("refresh_token")
            expires_in = token_data.get("expires_in", 2592000)  # Default 30 days

            if not access_token:
                return {
                    "success": False,
                    "error": "No access_token in response",
                    "details": data
                }

            # Calculate expiry
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

            # Store token if database is initialized
            if self.database_url:
                self._store_token(access_token, refresh_token, expires_at)

            return {
                "success": True,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": expires_at.isoformat(),
                "expires_in": expires_in
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def _store_token(self, access_token: str, refresh_token: Optional[str], expires_at: datetime):
        """Store or update access token in database."""
        # Invalidate old tokens
        self.session.query(AliExpressToken).update({"is_valid": False})

        # Create new token record
        token = AliExpressToken(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            is_valid=True
        )

        self.session.add(token)
        self.session.commit()

        print(f"✅ AliExpress token stored, expires at {expires_at}")

    def get_valid_token(self) -> Optional[str]:
        """
        Get current valid access token.

        Returns:
            Access token if valid, None if expired/missing
        """
        token = self.session.query(AliExpressToken).filter(
            AliExpressToken.is_valid == True
        ).order_by(AliExpressToken.created_at.desc()).first()

        if not token:
            return None

        # Check if expired
        if datetime.utcnow() >= token.expires_at:
            print("⚠️  Token expired, attempting refresh...")
            # Try to refresh
            if token.refresh_token:
                refreshed = self.refresh_access_token(token.refresh_token)
                if refreshed.get("success"):
                    return refreshed.get("access_token")

            # Refresh failed - mark invalid
            token.is_valid = False
            self.session.commit()
            return None

        return token.access_token

    def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh expired access token.

        Args:
            refresh_token: Refresh token from previous authorization

        Returns:
            New token response
        """
        params = {
            "client_id": self.app_key,
            "client_secret": self.app_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token
        }

        try:
            response = requests.post(self.TOKEN_URL, data=params, timeout=15)

            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}"
                }

            data = response.json()

            if "error" in data:
                return {
                    "success": False,
                    "error": data.get("error")
                }

            access_token = data.get("access_token")
            new_refresh_token = data.get("refresh_token", refresh_token)
            expires_in = data.get("expires_in", 3600)
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

            # Store new token
            self._store_token(access_token, new_refresh_token, expires_at)

            return {
                "success": True,
                "access_token": access_token,
                "refresh_token": new_refresh_token,
                "expires_at": expires_at.isoformat()
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def is_connected(self) -> bool:
        """Check if we have a valid token."""
        return self.get_valid_token() is not None

    def get_token_status(self) -> Dict[str, Any]:
        """Get current token status information."""
        token = self.session.query(AliExpressToken).filter(
            AliExpressToken.is_valid == True
        ).order_by(AliExpressToken.created_at.desc()).first()

        if not token:
            return {
                "connected": False,
                "status": "Not connected",
                "message": "No valid token found. Please authorize the app."
            }

        now = datetime.utcnow()
        expires_in = (token.expires_at - now).total_seconds()

        if expires_in <= 0:
            return {
                "connected": False,
                "status": "Token expired",
                "message": "Token expired. Please re-authorize."
            }

        return {
            "connected": True,
            "status": "Connected",
            "expires_at": token.expires_at.isoformat(),
            "expires_in_seconds": int(expires_in),
            "expires_in_hours": round(expires_in / 3600, 1)
        }


def init_aliexpress_oauth_db(database_url: str):
    """Initialize AliExpress OAuth database."""
    sync_url = database_url.replace("+aiosqlite", "")
    engine = create_engine(sync_url, echo=False)
    Base.metadata.create_all(engine)
    print("✅ AliExpress OAuth database initialized")
