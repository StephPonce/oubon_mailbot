"""
Microsoft Outlook OAuth Handler

Implements OAuth 2.0 flow for Outlook/Office 365 using Microsoft Graph API.
"""

import os
from typing import Dict
from msal import ConfidentialClientApplication
import httpx

from .base_email_oauth import EmailOAuthHandler


class OutlookOAuthHandler(EmailOAuthHandler):
    """
    Microsoft Outlook OAuth 2.0 handler using Microsoft Graph API.

    Scopes: Mail.ReadWrite, Mail.Send
    """

    SCOPES = [
        'https://graph.microsoft.com/Mail.ReadWrite',
        'https://graph.microsoft.com/Mail.Send',
        'https://graph.microsoft.com/User.Read'
    ]

    def __init__(self):
        """Initialize Outlook OAuth handler."""
        super().__init__()

        self.client_id = os.getenv('MICROSOFT_OAUTH_CLIENT_ID')
        self.client_secret = os.getenv('MICROSOFT_OAUTH_CLIENT_SECRET')
        self.tenant_id = os.getenv('MICROSOFT_OAUTH_TENANT_ID', 'common')

        if not self.client_id or not self.client_secret:
            raise ValueError("MICROSOFT_OAUTH_CLIENT_ID and MICROSOFT_OAUTH_CLIENT_SECRET must be set")

        self.authority = f"https://login.microsoftonline.com/{self.tenant_id}"

        self.app = ConfidentialClientApplication(
            client_id=self.client_id,
            client_credential=self.client_secret,
            authority=self.authority
        )

    async def get_authorization_url(self, state: str, redirect_uri: str) -> str:
        """
        Generate Microsoft OAuth authorization URL.

        Args:
            state: CSRF protection state
            redirect_uri: OAuth callback URL

        Returns:
            str: Authorization URL for user consent
        """
        auth_url = self.app.get_authorization_request_url(
            scopes=self.SCOPES,
            state=state,
            redirect_uri=redirect_uri,
            prompt='consent'
        )

        return auth_url

    async def exchange_code_for_token(self, code: str, redirect_uri: str) -> Dict:
        """
        Exchange authorization code for tokens.

        Args:
            code: Authorization code from OAuth callback
            redirect_uri: OAuth callback URL

        Returns:
            Dict: Tokens (access_token, refresh_token, expires_in)
        """
        result = self.app.acquire_token_by_authorization_code(
            code=code,
            scopes=self.SCOPES,
            redirect_uri=redirect_uri
        )

        if 'error' in result:
            raise Exception(f"Token exchange failed: {result.get('error_description', result['error'])}")

        return {
            'access_token': result['access_token'],
            'refresh_token': result.get('refresh_token'),
            'expires_in': result.get('expires_in'),
            'scopes': result.get('scope', [])
        }

    async def refresh_access_token(self, refresh_token: str) -> Dict:
        """
        Refresh expired access token.

        Args:
            refresh_token: Refresh token from initial authorization

        Returns:
            Dict: New access token and expiry
        """
        result = self.app.acquire_token_by_refresh_token(
            refresh_token=refresh_token,
            scopes=self.SCOPES
        )

        if 'error' in result:
            raise Exception(f"Token refresh failed: {result.get('error_description', result['error'])}")

        return {
            'access_token': result['access_token'],
            'refresh_token': result.get('refresh_token', refresh_token),  # May return new refresh token
            'expires_in': result.get('expires_in')
        }

    async def get_user_profile(self, access_token: str) -> Dict:
        """
        Fetch user email address from Microsoft Graph API.

        Args:
            access_token: Valid OAuth access token

        Returns:
            Dict: User profile with email
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                'https://graph.microsoft.com/v1.0/me',
                headers={'Authorization': f'Bearer {access_token}'}
            )
            response.raise_for_status()
            data = response.json()

            return {
                'email': data.get('mail') or data.get('userPrincipalName'),
                'name': data.get('displayName'),
                'id': data.get('id')
            }
