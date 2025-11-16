"""
Gmail OAuth Handler

Implements OAuth 2.0 flow for Gmail using Google OAuth.
"""

import os
from typing import Dict
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import httpx

from .base_email_oauth import EmailOAuthHandler


class GmailOAuthHandler(EmailOAuthHandler):
    """
    Gmail OAuth 2.0 handler using Google OAuth.

    Scopes: gmail.modify, gmail.send
    """

    SCOPES = [
        'https://www.googleapis.com/auth/gmail.modify',
        'https://www.googleapis.com/auth/gmail.send',
        'https://www.googleapis.com/auth/userinfo.email'
    ]

    def __init__(self):
        """Initialize Gmail OAuth handler."""
        super().__init__()

        self.client_id = os.getenv('GOOGLE_OAUTH_CLIENT_ID')
        self.client_secret = os.getenv('GOOGLE_OAUTH_CLIENT_SECRET')

        if not self.client_id or not self.client_secret:
            raise ValueError("GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET must be set")

        self.client_config = {
            "web": {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }

    async def get_authorization_url(self, state: str, redirect_uri: str) -> str:
        """
        Generate Google OAuth authorization URL.

        Args:
            state: CSRF protection state
            redirect_uri: OAuth callback URL

        Returns:
            str: Authorization URL for user consent
        """
        flow = Flow.from_client_config(
            self.client_config,
            scopes=self.SCOPES,
            state=state,
            redirect_uri=redirect_uri
        )

        authorization_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )

        return authorization_url

    async def exchange_code_for_token(self, code: str, redirect_uri: str) -> Dict:
        """
        Exchange authorization code for tokens.

        Args:
            code: Authorization code from OAuth callback
            redirect_uri: OAuth callback URL

        Returns:
            Dict: Tokens (access_token, refresh_token, expires_in)
        """
        flow = Flow.from_client_config(
            self.client_config,
            scopes=self.SCOPES,
            redirect_uri=redirect_uri
        )

        flow.fetch_token(code=code)

        credentials = flow.credentials

        return {
            'access_token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'expires_in': credentials.expiry.timestamp() if credentials.expiry else None,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }

    async def refresh_access_token(self, refresh_token: str) -> Dict:
        """
        Refresh expired access token.

        Args:
            refresh_token: Refresh token from initial authorization

        Returns:
            Dict: New access token and expiry
        """
        credentials = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.client_id,
            client_secret=self.client_secret,
            scopes=self.SCOPES
        )

        request = Request()
        credentials.refresh(request)

        return {
            'access_token': credentials.token,
            'expires_in': credentials.expiry.timestamp() if credentials.expiry else None
        }

    async def get_user_profile(self, access_token: str) -> Dict:
        """
        Fetch user email address from Google.

        Args:
            access_token: Valid OAuth access token

        Returns:
            Dict: User profile with email
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                'https://www.googleapis.com/oauth2/v2/userinfo',
                headers={'Authorization': f'Bearer {access_token}'}
            )
            response.raise_for_status()
            data = response.json()

            return {
                'email': data.get('email'),
                'name': data.get('name'),
                'picture': data.get('picture')
            }
