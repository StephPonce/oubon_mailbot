"""
Email Action Executor Service

Syncs email actions (star, archive, delete, label) to parent email platforms.
Supports Gmail API, Outlook Graph API, and IMAP/SMTP providers.
"""

import logging
import json
import os
from typing import Dict, List
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import httpx
import imaplib
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


class EmailActionExecutor:
    """
    Execute email actions on parent platforms (Gmail, Outlook, IMAP).

    Actions supported:
    - Star/unstar emails
    - Archive emails
    - Delete emails
    - Apply/remove labels
    - Mark as read/unread
    """

    def __init__(self):
        self.encryption_key = os.getenv('EMAIL_OAUTH_ENCRYPTION_KEY', 'lnl1Oc0BEMhbMN3CRvlz2K2sW7Xkz3gjc_6K5PL3nCc=')
        self.cipher = Fernet(self.encryption_key.encode())

    def _decrypt_credentials(self, encrypted_creds: str) -> Dict:
        """Decrypt stored credentials"""
        try:
            decrypted = self.cipher.decrypt(encrypted_creds.encode())
            return json.loads(decrypted)
        except Exception as e:
            logger.error(f"Failed to decrypt credentials: {e}")
            raise ValueError("Failed to decrypt account credentials")

    # ============================================================================
    # GMAIL API ACTIONS
    # ============================================================================

    async def gmail_star_email(self, account, email, is_starred: bool) -> Dict:
        """Star or unstar an email in Gmail"""
        try:
            creds = self._decrypt_credentials(account.encrypted_credentials)

            credentials = Credentials(
                token=creds.get('access_token'),
                refresh_token=creds.get('refresh_token'),
                token_uri='https://oauth2.googleapis.com/token',
                client_id=os.getenv('GOOGLE_OAUTH_CLIENT_ID'),
                client_secret=os.getenv('GOOGLE_OAUTH_CLIENT_SECRET'),
                scopes=['https://www.googleapis.com/auth/gmail.modify']
            )

            service = build('gmail', 'v1', credentials=credentials)

            if is_starred:
                # Add STARRED label
                service.users().messages().modify(
                    userId='me',
                    id=email.message_id,
                    body={'addLabelIds': ['STARRED']}
                ).execute()
            else:
                # Remove STARRED label
                service.users().messages().modify(
                    userId='me',
                    id=email.message_id,
                    body={'removeLabelIds': ['STARRED']}
                ).execute()

            logger.info(f"[Gmail] Email {email.message_id} {'starred' if is_starred else 'unstarred'}")
            return {'success': True, 'synced': True}

        except Exception as e:
            logger.error(f"[Gmail] Failed to star email: {e}")
            return {'success': False, 'error': str(e), 'synced': False}

    async def gmail_archive_email(self, account, email) -> Dict:
        """Archive an email in Gmail (remove INBOX label)"""
        try:
            creds = self._decrypt_credentials(account.encrypted_credentials)

            credentials = Credentials(
                token=creds.get('access_token'),
                refresh_token=creds.get('refresh_token'),
                token_uri='https://oauth2.googleapis.com/token',
                client_id=os.getenv('GOOGLE_OAUTH_CLIENT_ID'),
                client_secret=os.getenv('GOOGLE_OAUTH_CLIENT_SECRET'),
                scopes=['https://www.googleapis.com/auth/gmail.modify']
            )

            service = build('gmail', 'v1', credentials=credentials)

            # Archive = remove INBOX label
            service.users().messages().modify(
                userId='me',
                id=email.message_id,
                body={'removeLabelIds': ['INBOX']}
            ).execute()

            logger.info(f"[Gmail] Email {email.message_id} archived")
            return {'success': True, 'synced': True}

        except Exception as e:
            logger.error(f"[Gmail] Failed to archive email: {e}")
            return {'success': False, 'error': str(e), 'synced': False}

    async def gmail_delete_email(self, account, email) -> Dict:
        """Delete an email in Gmail (move to trash)"""
        try:
            creds = self._decrypt_credentials(account.encrypted_credentials)

            credentials = Credentials(
                token=creds.get('access_token'),
                refresh_token=creds.get('refresh_token'),
                token_uri='https://oauth2.googleapis.com/token',
                client_id=os.getenv('GOOGLE_OAUTH_CLIENT_ID'),
                client_secret=os.getenv('GOOGLE_OAUTH_CLIENT_SECRET'),
                scopes=['https://www.googleapis.com/auth/gmail.modify']
            )

            service = build('gmail', 'v1', credentials=credentials)

            # Move to trash
            service.users().messages().trash(
                userId='me',
                id=email.message_id
            ).execute()

            logger.info(f"[Gmail] Email {email.message_id} deleted (moved to trash)")
            return {'success': True, 'synced': True}

        except Exception as e:
            logger.error(f"[Gmail] Failed to delete email: {e}")
            return {'success': False, 'error': str(e), 'synced': False}

    async def gmail_apply_label(self, account, email, label_name: str) -> Dict:
        """Apply a label to an email in Gmail"""
        try:
            creds = self._decrypt_credentials(account.encrypted_credentials)

            credentials = Credentials(
                token=creds.get('access_token'),
                refresh_token=creds.get('refresh_token'),
                token_uri='https://oauth2.googleapis.com/token',
                client_id=os.getenv('GOOGLE_OAUTH_CLIENT_ID'),
                client_secret=os.getenv('GOOGLE_OAUTH_CLIENT_SECRET'),
                scopes=['https://www.googleapis.com/auth/gmail.modify']
            )

            service = build('gmail', 'v1', credentials=credentials)

            # Get or create label
            labels_response = service.users().labels().list(userId='me').execute()
            labels = labels_response.get('labels', [])

            label_id = None
            for label in labels:
                if label['name'].lower() == label_name.lower():
                    label_id = label['id']
                    break

            # Create label if it doesn't exist
            if not label_id:
                created_label = service.users().labels().create(
                    userId='me',
                    body={'name': label_name}
                ).execute()
                label_id = created_label['id']
                logger.info(f"[Gmail] Created new label: {label_name}")

            # Apply label
            service.users().messages().modify(
                userId='me',
                id=email.message_id,
                body={'addLabelIds': [label_id]}
            ).execute()

            logger.info(f"[Gmail] Applied label '{label_name}' to email {email.message_id}")
            return {'success': True, 'synced': True, 'label_id': label_id}

        except Exception as e:
            logger.error(f"[Gmail] Failed to apply label: {e}")
            return {'success': False, 'error': str(e), 'synced': False}

    async def gmail_mark_read(self, account, email, is_read: bool) -> Dict:
        """Mark an email as read or unread in Gmail"""
        try:
            creds = self._decrypt_credentials(account.encrypted_credentials)

            credentials = Credentials(
                token=creds.get('access_token'),
                refresh_token=creds.get('refresh_token'),
                token_uri='https://oauth2.googleapis.com/token',
                client_id=os.getenv('GOOGLE_OAUTH_CLIENT_ID'),
                client_secret=os.getenv('GOOGLE_OAUTH_CLIENT_SECRET'),
                scopes=['https://www.googleapis.com/auth/gmail.modify']
            )

            service = build('gmail', 'v1', credentials=credentials)

            if is_read:
                # Mark as read = remove UNREAD label
                service.users().messages().modify(
                    userId='me',
                    id=email.message_id,
                    body={'removeLabelIds': ['UNREAD']}
                ).execute()
            else:
                # Mark as unread = add UNREAD label
                service.users().messages().modify(
                    userId='me',
                    id=email.message_id,
                    body={'addLabelIds': ['UNREAD']}
                ).execute()

            logger.info(f"[Gmail] Email {email.message_id} marked as {'read' if is_read else 'unread'}")
            return {'success': True, 'synced': True}

        except Exception as e:
            logger.error(f"[Gmail] Failed to mark email: {e}")
            return {'success': False, 'error': str(e), 'synced': False}

    # ============================================================================
    # OUTLOOK GRAPH API ACTIONS
    # ============================================================================

    async def outlook_star_email(self, account, email, is_starred: bool) -> Dict:
        """Flag or unflag an email in Outlook"""
        try:
            creds = self._decrypt_credentials(account.encrypted_credentials)
            access_token = creds.get('access_token')

            message_id = email.external_id or email.message_id

            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    f'https://graph.microsoft.com/v1.0/me/messages/{message_id}',
                    headers={'Authorization': f'Bearer {access_token}'},
                    json={'flag': {'flagStatus': 'flagged' if is_starred else 'notFlagged'}},
                    timeout=30.0
                )

                if response.status_code not in [200, 204]:
                    return {'success': False, 'error': f'API error: {response.status_code}', 'synced': False}

            logger.info(f"[Outlook] Email {message_id} {'flagged' if is_starred else 'unflagged'}")
            return {'success': True, 'synced': True}

        except Exception as e:
            logger.error(f"[Outlook] Failed to flag email: {e}")
            return {'success': False, 'error': str(e), 'synced': False}

    async def outlook_archive_email(self, account, email) -> Dict:
        """Archive an email in Outlook (move to Archive folder)"""
        try:
            creds = self._decrypt_credentials(account.encrypted_credentials)
            access_token = creds.get('access_token')

            message_id = email.external_id or email.message_id

            # Get Archive folder ID
            async with httpx.AsyncClient() as client:
                folders_response = await client.get(
                    'https://graph.microsoft.com/v1.0/me/mailFolders',
                    headers={'Authorization': f'Bearer {access_token}'},
                    timeout=30.0
                )

                archive_folder_id = None
                if folders_response.status_code == 200:
                    folders = folders_response.json().get('value', [])
                    for folder in folders:
                        if folder.get('displayName', '').lower() == 'archive':
                            archive_folder_id = folder['id']
                            break

                # Move to archive folder
                if archive_folder_id:
                    move_response = await client.post(
                        f'https://graph.microsoft.com/v1.0/me/messages/{message_id}/move',
                        headers={'Authorization': f'Bearer {access_token}'},
                        json={'destinationId': archive_folder_id},
                        timeout=30.0
                    )

                    if move_response.status_code not in [200, 201]:
                        return {'success': False, 'error': f'Failed to move: {move_response.status_code}', 'synced': False}

                    logger.info(f"[Outlook] Email {message_id} archived")
                    return {'success': True, 'synced': True}
                else:
                    logger.warning(f"[Outlook] Archive folder not found")
                    return {'success': False, 'error': 'Archive folder not found', 'synced': False}

        except Exception as e:
            logger.error(f"[Outlook] Failed to archive email: {e}")
            return {'success': False, 'error': str(e), 'synced': False}

    async def outlook_delete_email(self, account, email) -> Dict:
        """Delete an email in Outlook"""
        try:
            creds = self._decrypt_credentials(account.encrypted_credentials)
            access_token = creds.get('access_token')

            message_id = email.external_id or email.message_id

            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f'https://graph.microsoft.com/v1.0/me/messages/{message_id}',
                    headers={'Authorization': f'Bearer {access_token}'},
                    timeout=30.0
                )

                if response.status_code not in [200, 204]:
                    return {'success': False, 'error': f'API error: {response.status_code}', 'synced': False}

            logger.info(f"[Outlook] Email {message_id} deleted")
            return {'success': True, 'synced': True}

        except Exception as e:
            logger.error(f"[Outlook] Failed to delete email: {e}")
            return {'success': False, 'error': str(e), 'synced': False}

    async def outlook_apply_category(self, account, email, category_name: str) -> Dict:
        """Apply a category to an email in Outlook"""
        try:
            creds = self._decrypt_credentials(account.encrypted_credentials)
            access_token = creds.get('access_token')

            message_id = email.external_id or email.message_id

            async with httpx.AsyncClient() as client:
                # Get current categories
                get_response = await client.get(
                    f'https://graph.microsoft.com/v1.0/me/messages/{message_id}',
                    headers={'Authorization': f'Bearer {access_token}'},
                    params={'$select': 'categories'},
                    timeout=30.0
                )

                current_categories = []
                if get_response.status_code == 200:
                    current_categories = get_response.json().get('categories', [])

                # Add new category if not already present
                if category_name not in current_categories:
                    current_categories.append(category_name)

                    # Update categories
                    update_response = await client.patch(
                        f'https://graph.microsoft.com/v1.0/me/messages/{message_id}',
                        headers={'Authorization': f'Bearer {access_token}'},
                        json={'categories': current_categories},
                        timeout=30.0
                    )

                    if update_response.status_code not in [200, 204]:
                        return {'success': False, 'error': f'API error: {update_response.status_code}', 'synced': False}

            logger.info(f"[Outlook] Applied category '{category_name}' to email {message_id}")
            return {'success': True, 'synced': True}

        except Exception as e:
            logger.error(f"[Outlook] Failed to apply category: {e}")
            return {'success': False, 'error': str(e), 'synced': False}

    async def outlook_mark_read(self, account, email, is_read: bool) -> Dict:
        """Mark an email as read or unread in Outlook"""
        try:
            creds = self._decrypt_credentials(account.encrypted_credentials)
            access_token = creds.get('access_token')

            message_id = email.external_id or email.message_id

            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    f'https://graph.microsoft.com/v1.0/me/messages/{message_id}',
                    headers={'Authorization': f'Bearer {access_token}'},
                    json={'isRead': is_read},
                    timeout=30.0
                )

                if response.status_code not in [200, 204]:
                    return {'success': False, 'error': f'API error: {response.status_code}', 'synced': False}

            logger.info(f"[Outlook] Email {message_id} marked as {'read' if is_read else 'unread'}")
            return {'success': True, 'synced': True}

        except Exception as e:
            logger.error(f"[Outlook] Failed to mark email: {e}")
            return {'success': False, 'error': str(e), 'synced': False}

    # ============================================================================
    # IMAP ACTIONS (for iCloud, Yahoo, Zoho, etc.)
    # ============================================================================

    async def imap_star_email(self, account, email, is_starred: bool) -> Dict:
        """Star/flag an email via IMAP"""
        try:
            creds = self._decrypt_credentials(account.encrypted_credentials)
            imap_config = creds.get('imap_config', {})

            mail = imaplib.IMAP4_SSL(
                imap_config.get('host'),
                imap_config.get('port', 993),
                timeout=30
            )
            mail.login(account.email_address, creds.get('access_token'))  # App password
            mail.select('INBOX')

            if is_starred:
                mail.store(email.message_id, '+FLAGS', '\\Flagged')
            else:
                mail.store(email.message_id, '-FLAGS', '\\Flagged')

            mail.logout()

            logger.info(f"[IMAP] Email {email.message_id} {'flagged' if is_starred else 'unflagged'}")
            return {'success': True, 'synced': True}

        except Exception as e:
            logger.error(f"[IMAP] Failed to flag email: {e}")
            return {'success': False, 'error': str(e), 'synced': False}

    async def imap_delete_email(self, account, email) -> Dict:
        """Delete an email via IMAP"""
        try:
            creds = self._decrypt_credentials(account.encrypted_credentials)
            imap_config = creds.get('imap_config', {})

            mail = imaplib.IMAP4_SSL(
                imap_config.get('host'),
                imap_config.get('port', 993),
                timeout=30
            )
            mail.login(account.email_address, creds.get('access_token'))
            mail.select('INBOX')

            # Mark for deletion and expunge
            mail.store(email.message_id, '+FLAGS', '\\Deleted')
            mail.expunge()

            mail.logout()

            logger.info(f"[IMAP] Email {email.message_id} deleted")
            return {'success': True, 'synced': True}

        except Exception as e:
            logger.error(f"[IMAP] Failed to delete email: {e}")
            return {'success': False, 'error': str(e), 'synced': False}

    async def imap_mark_read(self, account, email, is_read: bool) -> Dict:
        """Mark an email as read/unread via IMAP"""
        try:
            creds = self._decrypt_credentials(account.encrypted_credentials)
            imap_config = creds.get('imap_config', {})

            mail = imaplib.IMAP4_SSL(
                imap_config.get('host'),
                imap_config.get('port', 993),
                timeout=30
            )
            mail.login(account.email_address, creds.get('access_token'))
            mail.select('INBOX')

            if is_read:
                mail.store(email.message_id, '+FLAGS', '\\Seen')
            else:
                mail.store(email.message_id, '-FLAGS', '\\Seen')

            mail.logout()

            logger.info(f"[IMAP] Email {email.message_id} marked as {'read' if is_read else 'unread'}")
            return {'success': True, 'synced': True}

        except Exception as e:
            logger.error(f"[IMAP] Failed to mark email: {e}")
            return {'success': False, 'error': str(e), 'synced': False}

    # ============================================================================
    # UNIFIED ACTION ROUTER
    # ============================================================================

    async def execute_action(self, account, email, action: str, **kwargs) -> Dict:
        """
        Route action to appropriate provider.

        Actions: 'star', 'unstar', 'archive', 'delete', 'label', 'mark_read', 'mark_unread'
        """
        provider = account.provider.lower()

        try:
            if action == 'star':
                if provider == 'gmail':
                    return await self.gmail_star_email(account, email, True)
                elif provider == 'outlook':
                    return await self.outlook_star_email(account, email, True)
                elif provider in ['icloud', 'yahoo', 'zoho', 'protonmail', 'custom']:
                    return await self.imap_star_email(account, email, True)

            elif action == 'unstar':
                if provider == 'gmail':
                    return await self.gmail_star_email(account, email, False)
                elif provider == 'outlook':
                    return await self.outlook_star_email(account, email, False)
                elif provider in ['icloud', 'yahoo', 'zoho', 'protonmail', 'custom']:
                    return await self.imap_star_email(account, email, False)

            elif action == 'archive':
                if provider == 'gmail':
                    return await self.gmail_archive_email(account, email)
                elif provider == 'outlook':
                    return await self.outlook_archive_email(account, email)
                else:
                    return {'success': False, 'error': 'Archive not supported for this provider', 'synced': False}

            elif action == 'delete':
                if provider == 'gmail':
                    return await self.gmail_delete_email(account, email)
                elif provider == 'outlook':
                    return await self.outlook_delete_email(account, email)
                elif provider in ['icloud', 'yahoo', 'zoho', 'protonmail', 'custom']:
                    return await self.imap_delete_email(account, email)

            elif action == 'label':
                label_name = kwargs.get('label_name')
                if not label_name:
                    return {'success': False, 'error': 'label_name required', 'synced': False}

                if provider == 'gmail':
                    return await self.gmail_apply_label(account, email, label_name)
                elif provider == 'outlook':
                    return await self.outlook_apply_category(account, email, label_name)
                else:
                    return {'success': False, 'error': 'Labels not supported for this provider', 'synced': False}

            elif action == 'mark_read':
                if provider == 'gmail':
                    return await self.gmail_mark_read(account, email, True)
                elif provider == 'outlook':
                    return await self.outlook_mark_read(account, email, True)
                elif provider in ['icloud', 'yahoo', 'zoho', 'protonmail', 'custom']:
                    return await self.imap_mark_read(account, email, True)

            elif action == 'mark_unread':
                if provider == 'gmail':
                    return await self.gmail_mark_read(account, email, False)
                elif provider == 'outlook':
                    return await self.outlook_mark_read(account, email, False)
                elif provider in ['icloud', 'yahoo', 'zoho', 'protonmail', 'custom']:
                    return await self.imap_mark_read(account, email, False)

            else:
                return {'success': False, 'error': f'Unknown action: {action}', 'synced': False}

        except Exception as e:
            logger.error(f"Failed to execute action {action}: {e}")
            return {'success': False, 'error': str(e), 'synced': False}
