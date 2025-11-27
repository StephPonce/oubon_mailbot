"""
Generic IMAP/SMTP Handler

For business emails that don't use OAuth (Zoho, ProtonMail, custom domains, etc.)
Uses username/password with encrypted storage.
"""

from typing import Dict
import json
import hashlib
from .base_email_oauth import EmailOAuthHandler


class IMAPSMTPHandler(EmailOAuthHandler):
    """
    Generic IMAP/SMTP email handler for business emails.

    Supports any email provider with IMAP/SMTP access:
    - iCloud Mail (imap.mail.me.com / smtp.mail.me.com)
    - Zoho Mail (imap.zoho.com / smtp.zoho.com)
    - ProtonMail Bridge (127.0.0.1:1143 / 127.0.0.1:1025)
    - Yahoo Mail (imap.mail.yahoo.com / smtp.mail.yahoo.com)
    - Custom domains (mail.yourdomain.com)

    Uses app-specific passwords for security (not plain passwords).
    """

    # Common IMAP/SMTP configurations
    PRESETS = {
        "icloud": {
            "name": "iCloud Mail",
            "imap_host": "imap.mail.me.com",
            "imap_port": 993,
            "smtp_host": "smtp.mail.me.com",
            "smtp_port": 587,
            "requires_app_password": True,
            "instructions": "Use an app-specific password from appleid.apple.com"
        },
        "zoho": {
            "name": "Zoho Mail",
            "imap_host": "imap.zoho.com",
            "imap_port": 993,
            "smtp_host": "smtp.zoho.com",
            "smtp_port": 587,
            "requires_app_password": False
        },
        "yahoo": {
            "name": "Yahoo Mail",
            "imap_host": "imap.mail.yahoo.com",
            "imap_port": 993,
            "smtp_host": "smtp.mail.yahoo.com",
            "smtp_port": 587,
            "requires_app_password": True,
            "instructions": "Generate app password at account.yahoo.com/account/security"
        },
        "protonmail": {
            "name": "ProtonMail Bridge",
            "imap_host": "127.0.0.1",
            "imap_port": 1143,
            "smtp_host": "127.0.0.1",
            "smtp_port": 1025,
            "requires_app_password": False,
            "instructions": "Install ProtonMail Bridge desktop app first"
        },
        "custom": {
            "name": "Custom IMAP/SMTP",
            "imap_host": "",
            "imap_port": 993,
            "smtp_host": "",
            "smtp_port": 587,
            "requires_app_password": False
        }
    }

    def __init__(self):
        """Initialize IMAP/SMTP handler."""
        super().__init__()
        # No OAuth client needed for IMAP/SMTP

    async def get_authorization_url(self, state: str, redirect_uri: str) -> str:
        """
        Not used for IMAP/SMTP - credentials collected directly via form.

        Returns a special URL that frontend recognizes to show credential form.
        """
        return f"imap-smtp-form://collect-credentials?state={state}"

    async def exchange_code_for_token(self, code: str, redirect_uri: str) -> Dict:
        """
        For IMAP/SMTP, 'code' is actually JSON with credentials.

        Expected format:
        {
            "email": "user@domain.com",
            "password": "app-specific-password",
            "preset": "icloud" or "custom",
            "imap_host": "imap.mail.me.com",
            "imap_port": 993,
            "smtp_host": "smtp.mail.me.com",
            "smtp_port": 587
        }
        """
        credentials = json.loads(code)

        # Validate IMAP/SMTP connection
        try:
            await self._test_connection(credentials)
        except Exception as e:
            raise ValueError(f"Failed to connect to email server: {str(e)}")

        # Return credentials in OAuth-like format
        return {
            "access_token": credentials["password"],  # App password as token
            "refresh_token": credentials["password"],  # Same for refresh
            "token_type": "password",
            "email": credentials["email"],
            "imap_config": {
                "host": credentials["imap_host"],
                "port": credentials["imap_port"],
                "use_ssl": True
            },
            "smtp_config": {
                "host": credentials["smtp_host"],
                "port": credentials["smtp_port"],
                "use_tls": True
            }
        }

    async def refresh_access_token(self, refresh_token: str) -> Dict:
        """
        IMAP/SMTP doesn't need token refresh - passwords don't expire.
        Just return the same password.
        """
        return {
            "access_token": refresh_token,
            "token_type": "password"
        }

    async def get_user_profile(self, access_token: str) -> Dict:
        """
        For IMAP/SMTP, email address is stored with credentials.
        No separate profile fetch needed.
        """
        # Email is already stored, return placeholder
        return {"email": "stored_with_credentials"}

    async def _test_connection(self, credentials: Dict):
        """Test IMAP and SMTP connections to validate credentials."""
        import imaplib
        import smtplib
        import ssl

        # Sanitize inputs - strip whitespace
        email = credentials["email"].strip()
        password = credentials["password"].strip()

        # Test IMAP connection
        try:
            context = ssl.create_default_context()
            imap = imaplib.IMAP4_SSL(
                credentials["imap_host"],
                credentials["imap_port"],
                ssl_context=context
            )
            imap.login(email, password)
            imap.logout()
        except imaplib.IMAP4.error as e:
            error_msg = str(e)

            # Provide helpful error messages based on error type
            if 'AUTHENTICATIONFAILED' in error_msg or 'Authentication Failed' in error_msg:
                raise ValueError(
                    "IMAP authentication failed. "
                    "Please verify:\n"
                    "• You're using an app-specific password (not your regular password)\n"
                    "• The password is correct and hasn't expired\n"
                    "• Two-factor authentication is enabled on your account\n"
                    f"• Email: {email}"
                )
            elif 'UNAVAILABLE' in error_msg:
                raise ValueError(
                    f"IMAP server unavailable. "
                    f"The email server at {credentials['imap_host']} cannot be reached. "
                    f"Please check your internet connection and try again."
                )
            else:
                raise ValueError(f"IMAP connection failed: {error_msg}")
        except ssl.SSLError as e:
            raise ValueError(
                f"SSL connection failed to {credentials['imap_host']}:{credentials['imap_port']}. "
                f"This might be a firewall or network issue. Error: {str(e)}"
            )
        except Exception as e:
            raise ValueError(f"IMAP connection failed: {str(e)}")

        # Test SMTP connection
        try:
            smtp = smtplib.SMTP(credentials["smtp_host"], credentials["smtp_port"])
            smtp.starttls()
            smtp.login(email, password)
            smtp.quit()
        except smtplib.SMTPAuthenticationError as e:
            raise ValueError(
                f"SMTP authentication failed. "
                f"The password works for IMAP but not SMTP. "
                f"Error: {str(e)}"
            )
        except Exception as e:
            raise ValueError(f"SMTP connection failed: {str(e)}")

    @classmethod
    def get_preset(cls, preset_name: str) -> Dict:
        """Get preset configuration for common email providers."""
        return cls.PRESETS.get(preset_name, cls.PRESETS["custom"])
