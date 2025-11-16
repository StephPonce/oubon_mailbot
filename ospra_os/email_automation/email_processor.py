"""
Email Processor - Multi-User Email Automation

Processes emails for users using their connected OAuth accounts.
"""

from typing import Optional, Dict
from ospra_os.database.multi_store_models import UserEmailAccount, get_multi_store_session
from .oauth.gmail_oauth import GmailOAuthHandler
from .oauth.outlook_oauth import OutlookOAuthHandler


class EmailProcessor:
    """
    Process emails for users using their connected email accounts.
    """

    def __init__(self):
        self.handlers = {
            'gmail': GmailOAuthHandler,
            'outlook': OutlookOAuthHandler
        }

    def get_user_credentials(self, user_id: int, provider: str = 'gmail') -> Optional[Dict]:
        """
        Get decrypted OAuth credentials for a user's email account.

        Args:
            user_id: User ID
            provider: Email provider ('gmail', 'outlook', 'yahoo')

        Returns:
            Dict: Decrypted credentials or None if not found
        """
        session = get_multi_store_session()

        try:
            # Find primary account or first active account for provider
            account = session.query(UserEmailAccount).filter(
                UserEmailAccount.user_id == user_id,
                UserEmailAccount.provider == provider,
                UserEmailAccount.is_active == True
            ).order_by(
                UserEmailAccount.is_primary.desc(),
                UserEmailAccount.created_at.desc()
            ).first()

            if not account:
                return None

            # Get handler and decrypt credentials
            handler_class = self.handlers.get(provider)
            if not handler_class:
                return None

            handler = handler_class()
            credentials = handler.decrypt_credentials(account.encrypted_credentials)

            return {
                'account_id': account.id,
                'email_address': account.email_address,
                'credentials': credentials
            }

        finally:
            session.close()

    async def process_emails_for_user(self, user_id: int, provider: str = 'gmail'):
        """
        Process emails for a specific user using their OAuth credentials.

        Args:
            user_id: User ID
            provider: Email provider to use

        Returns:
            Dict: Processing results
        """
        creds = self.get_user_credentials(user_id, provider)

        if not creds:
            return {
                'success': False,
                'error': f'No active {provider} account found for user {user_id}'
            }

        # TODO: Implement actual email processing logic
        # This is a placeholder for future email automation features
        return {
            'success': True,
            'user_id': user_id,
            'provider': provider,
            'email': creds['email_address'],
            'message': 'Email processing placeholder - implement your logic here'
        }
