"""
Email Sync Service - Fetch emails from all providers

Syncs emails from Gmail (OAuth), Outlook (Graph API), and IMAP providers.
"""

from typing import List, Dict, Optional
from datetime import datetime, timedelta
import base64
import json
import imaplib
import email
from email.header import decode_header
import ssl
import socket
import logging

# Get logger for this module
logger = logging.getLogger(__name__)

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import httpx

from ospra_os.database.multi_store_models import (
    UserEmailAccount, Email, get_multi_store_session
)
from ospra_os.email_automation.oauth.gmail_oauth import GmailOAuthHandler
from ospra_os.email_automation.oauth.outlook_oauth import OutlookOAuthHandler
from ospra_os.email_automation.oauth.imap_smtp_handler import IMAPSMTPHandler


class EmailSyncService:
    """
    Unified email sync service for all providers.

    Fetches emails from Gmail, Outlook, or IMAP and stores them in the database.
    """

    def __init__(self):
        self.gmail_handler = GmailOAuthHandler()
        self.outlook_handler = OutlookOAuthHandler()
        self.imap_handler = IMAPSMTPHandler()

    async def sync_account(
        self,
        account_id: int,
        max_emails: int = 50,
        days_back: int = 7
    ) -> Dict:
        """
        Sync emails for a specific email account.

        Args:
            account_id: UserEmailAccount ID
            max_emails: Maximum number of emails to fetch
            days_back: How many days back to fetch emails

        Returns:
            Dict with sync results
        """
        session = get_multi_store_session()

        try:
            # Get account
            account = session.query(UserEmailAccount).filter(
                UserEmailAccount.id == account_id
            ).first()

            if not account:
                return {
                    'success': False,
                    'error': f'Email account {account_id} not found'
                }

            # Route to appropriate provider
            if account.provider == 'gmail':
                result = await self._sync_gmail(account, max_emails, days_back, session)
            elif account.provider == 'outlook':
                result = await self._sync_outlook(account, max_emails, days_back, session)
            elif account.provider in ['icloud', 'yahoo', 'zoho', 'protonmail', 'custom']:
                result = await self._sync_imap(account, max_emails, days_back, session)
            else:
                result = {
                    'success': False,
                    'error': f'Unsupported provider: {account.provider}'
                }

            # Update account sync status
            if result['success']:
                account.last_synced = datetime.utcnow()
                account.sync_status = 'active'
                account.sync_error = None
            else:
                account.sync_status = 'error'
                account.sync_error = result.get('error', 'Unknown error')

            session.commit()

            return result

        except Exception as e:
            session.rollback()
            return {
                'success': False,
                'error': str(e)
            }
        finally:
            session.close()

    async def _sync_gmail(
        self,
        account: UserEmailAccount,
        max_emails: int,
        days_back: int,
        session
    ) -> Dict:
        """Sync emails from Gmail using Gmail API."""
        try:
            # Decrypt credentials
            creds_dict = self.gmail_handler.decrypt_credentials(account.encrypted_credentials)

            # Create Google OAuth credentials
            creds = Credentials(
                token=creds_dict['access_token'],
                refresh_token=creds_dict.get('refresh_token'),
                token_uri=creds_dict.get('token_uri', 'https://oauth2.googleapis.com/token'),
                client_id=creds_dict.get('client_id', self.gmail_handler.client_id),
                client_secret=creds_dict.get('client_secret', self.gmail_handler.client_secret),
                scopes=creds_dict.get('scopes', self.gmail_handler.SCOPES)
            )

            # Refresh token if expired
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())

                # Update stored credentials
                new_creds_dict = {
                    'access_token': creds.token,
                    'refresh_token': creds.refresh_token,
                    'token_uri': creds.token_uri,
                    'client_id': creds.client_id,
                    'client_secret': creds.client_secret,
                    'scopes': list(creds.scopes)
                }
                account.encrypted_credentials = self.gmail_handler.encrypt_credentials(new_creds_dict)
                session.commit()

            # Build Gmail API service
            service = build('gmail', 'v1', credentials=creds)

            # Calculate date for filtering (fetch from past year by default)
            after_date = datetime.now() - timedelta(days=days_back)
            query = f'after:{int(after_date.timestamp())}'

            # Fetch messages for each important label separately to ensure we get inbox emails
            # This prevents SENT emails from dominating and causing inbox emails to be skipped
            all_messages = []

            # Allocate quota: INBOX gets 40%, TRASH gets 20%, SENT gets remaining 40%
            # This ensures TRASH always gets synced even if there are many SENT emails
            inbox_quota = max(20, int(max_emails * 0.4))  # At least 20 emails
            trash_quota = max(10, int(max_emails * 0.2))  # At least 10 emails
            sent_quota = max_emails - inbox_quota - trash_quota

            # Fetch INBOX emails first (highest priority)
            try:
                inbox_results = service.users().messages().list(
                    userId='me',
                    labelIds=['INBOX'],
                    q=query,
                    maxResults=min(500, inbox_quota)
                ).execute()
                inbox_messages = inbox_results.get('messages', [])
                all_messages.extend(inbox_messages)
                logger.info(f"Fetched {len(inbox_messages)} INBOX messages (quota: {inbox_quota})")
            except Exception as e:
                logger.error(f"Error fetching INBOX messages: {e}")

            # Fetch TRASH emails second (ensure trash is always fetched)
            try:
                trash_results = service.users().messages().list(
                    userId='me',
                    labelIds=['TRASH'],
                    q=query,
                    maxResults=min(500, trash_quota)
                ).execute()
                trash_messages = trash_results.get('messages', [])
                all_messages.extend(trash_messages)
                logger.info(f"Fetched {len(trash_messages)} TRASH messages (quota: {trash_quota})")
            except Exception as e:
                logger.error(f"Error fetching TRASH messages: {e}")

            # Fetch SENT emails last (gets remaining quota)
            try:
                sent_results = service.users().messages().list(
                    userId='me',
                    labelIds=['SENT'],
                    q=query,
                    maxResults=min(500, sent_quota)
                ).execute()
                sent_messages = sent_results.get('messages', [])
                all_messages.extend(sent_messages)
                logger.info(f"Fetched {len(sent_messages)} SENT messages (quota: {sent_quota})")
            except Exception as e:
                logger.error(f"Error fetching SENT messages: {e}")

            logger.info(f"Total messages fetched: {len(all_messages)}")

            if not all_messages:
                return {
                    'success': True,
                    'emails_synced': 0,
                    'message': 'No new emails found'
                }

            logger.info(f"Fetched {len(all_messages)} message IDs from Gmail, starting detailed fetch...")
            emails_synced = 0

            for msg in all_messages:
                # Get full message details
                full_msg = service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='full'
                ).execute()

                # Check if email already exists
                existing = session.query(Email).filter(
                    Email.email_account_id == account.id,
                    Email.message_id == full_msg['id']
                ).first()

                if existing:
                    continue  # Skip already synced emails

                # Parse email
                headers = {h['name']: h['value'] for h in full_msg['payload']['headers']}

                # Extract body
                body_plain = ''
                body_html = ''

                if 'parts' in full_msg['payload']:
                    for part in full_msg['payload']['parts']:
                        if part['mimeType'] == 'text/plain' and 'data' in part['body']:
                            body_plain = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                        elif part['mimeType'] == 'text/html' and 'data' in part['body']:
                            body_html = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                elif 'body' in full_msg['payload'] and 'data' in full_msg['payload']['body']:
                    body_plain = base64.urlsafe_b64decode(full_msg['payload']['body']['data']).decode('utf-8', errors='ignore')

                # Parse date
                received_at = datetime.fromtimestamp(int(full_msg['internalDate']) / 1000)

                # Create email record
                email_record = Email(
                    user_id=account.user_id,
                    email_account_id=account.id,
                    message_id=full_msg['id'],
                    thread_id=full_msg.get('threadId'),
                    from_address=headers.get('From', ''),
                    from_name=headers.get('From', '').split('<')[0].strip(),
                    to_addresses=json.dumps([headers.get('To', '')]),
                    subject=headers.get('Subject', ''),
                    body_plain=body_plain,
                    body_html=body_html,
                    snippet=full_msg.get('snippet', ''),
                    received_at=received_at,
                    labels=json.dumps(full_msg.get('labelIds', [])),
                    is_read='UNREAD' not in full_msg.get('labelIds', []),
                    is_starred='STARRED' in full_msg.get('labelIds', []),
                    is_important='IMPORTANT' in full_msg.get('labelIds', []),
                    has_attachments=any('filename' in part for part in full_msg['payload'].get('parts', [])),
                    synced_at=datetime.utcnow(),
                    raw_data=full_msg
                )

                session.add(email_record)
                emails_synced += 1

            session.commit()

            return {
                'success': True,
                'emails_synced': emails_synced,
                'provider': 'gmail'
            }

        except Exception as e:
            return {
                'success': False,
                'error': f'Gmail sync failed: {str(e)}'
            }

    async def _sync_outlook(
        self,
        account: UserEmailAccount,
        max_emails: int,
        days_back: int,
        session
    ) -> Dict:
        """Sync emails from Outlook using Microsoft Graph API."""
        try:
            # Decrypt credentials
            creds_dict = self.outlook_handler.decrypt_credentials(account.encrypted_credentials)

            access_token = creds_dict['access_token']

            # Calculate date for filtering
            after_date = (datetime.now() - timedelta(days=days_back)).isoformat() + 'Z'

            # Fetch messages from Microsoft Graph
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f'https://graph.microsoft.com/v1.0/me/messages',
                    headers={'Authorization': f'Bearer {access_token}'},
                    params={
                        '$top': max_emails,
                        '$filter': f'receivedDateTime ge {after_date}',
                        '$orderby': 'receivedDateTime desc'
                    }
                )

                if response.status_code == 401:
                    # Token expired, try to refresh
                    refresh_result = await self.outlook_handler.refresh_access_token(creds_dict.get('refresh_token'))
                    access_token = refresh_result['access_token']

                    # Update stored credentials
                    creds_dict['access_token'] = access_token
                    account.encrypted_credentials = self.outlook_handler.encrypt_credentials(creds_dict)
                    session.commit()

                    # Retry request
                    response = await client.get(
                        f'https://graph.microsoft.com/v1.0/me/messages',
                        headers={'Authorization': f'Bearer {access_token}'},
                        params={
                            '$top': max_emails,
                            '$filter': f'receivedDateTime ge {after_date}',
                            '$orderby': 'receivedDateTime desc'
                        }
                    )

                response.raise_for_status()
                data = response.json()

            messages = data.get('value', [])

            if not messages:
                return {
                    'success': True,
                    'emails_synced': 0,
                    'message': 'No new emails found'
                }

            emails_synced = 0

            for msg in messages:
                # Check if email already exists
                existing = session.query(Email).filter(
                    Email.email_account_id == account.id,
                    Email.message_id == msg['id']
                ).first()

                if existing:
                    continue

                # Parse email
                from_email = msg.get('from', {}).get('emailAddress', {})
                to_emails = [r.get('emailAddress', {}).get('address') for r in msg.get('toRecipients', [])]

                # Parse date
                received_at = datetime.fromisoformat(msg['receivedDateTime'].replace('Z', '+00:00'))

                # Create email record
                email_record = Email(
                    user_id=account.user_id,
                    email_account_id=account.id,
                    message_id=msg['id'],
                    thread_id=msg.get('conversationId'),
                    from_address=from_email.get('address', ''),
                    from_name=from_email.get('name', ''),
                    to_addresses=json.dumps(to_emails),
                    subject=msg.get('subject', ''),
                    body_plain=msg.get('bodyPreview', ''),
                    body_html=msg.get('body', {}).get('content', ''),
                    snippet=msg.get('bodyPreview', '')[:200],
                    received_at=received_at,
                    labels=json.dumps(msg.get('categories', [])),
                    is_read=msg.get('isRead', False),
                    is_starred=msg.get('flag', {}).get('flagStatus') == 'flagged',
                    is_important=msg.get('importance') == 'high',
                    has_attachments=msg.get('hasAttachments', False),
                    synced_at=datetime.utcnow(),
                    raw_data=msg
                )

                session.add(email_record)
                emails_synced += 1

            session.commit()

            return {
                'success': True,
                'emails_synced': emails_synced,
                'provider': 'outlook'
            }

        except Exception as e:
            return {
                'success': False,
                'error': f'Outlook sync failed: {str(e)}'
            }

    async def _sync_imap(
        self,
        account: UserEmailAccount,
        max_emails: int,
        days_back: int,
        session
    ) -> Dict:
        """Sync emails from IMAP providers (iCloud, Yahoo, Zoho, etc.)."""
        imap = None
        try:
            # Decrypt credentials
            creds_dict = self.imap_handler.decrypt_credentials(account.encrypted_credentials)

            email_address = creds_dict['email']
            password = creds_dict['access_token']  # Password stored as access_token
            imap_config = creds_dict.get('imap_config', {})

            # Connect to IMAP server with timeout
            context = ssl.create_default_context()
            imap = imaplib.IMAP4_SSL(
                imap_config['host'],
                imap_config['port'],
                ssl_context=context,
                timeout=30  # 30 second timeout
            )

            # Login
            try:
                imap.login(email_address, password)
            except imaplib.IMAP4.error as e:
                return {
                    'success': False,
                    'error': f'IMAP login failed for {email_address}: {str(e)}'
                }

            # Select INBOX
            imap.select('INBOX')

            # Calculate date for filtering
            since_date = (datetime.now() - timedelta(days=days_back)).strftime('%d-%b-%Y')

            # Search for emails
            status, messages = imap.search(None, f'(SINCE {since_date})')

            if status != 'OK':
                return {
                    'success': False,
                    'error': 'IMAP search failed'
                }

            message_nums = messages[0].split()
            # Decode bytes to strings for IMAP fetch
            message_nums = [num.decode() if isinstance(num, bytes) else str(num) for num in message_nums]
            message_nums = list(reversed(message_nums))[:max_emails]  # Get most recent

            if not message_nums:
                imap.close()
                imap.logout()
                return {
                    'success': True,
                    'emails_synced': 0,
                    'message': 'No new emails found'
                }

            emails_synced = 0

            for num in message_nums:
                # Fetch email (using BODY.PEEK[] to avoid marking as read, more compatible with iCloud)
                status, msg_data = imap.fetch(num, '(BODY.PEEK[])')

                if status != 'OK':
                    continue

                # Parse email - validate raw_email is bytes
                raw_email = msg_data[0][1]
                if not isinstance(raw_email, bytes):
                    # Skip this email if data is in unexpected format
                    continue

                email_message = email.message_from_bytes(raw_email)

                # Extract UID as message_id
                status, uid_data = imap.fetch(num, '(UID)')
                # Handle both bytes and int responses from IMAP
                if isinstance(uid_data[0], bytes):
                    uid = uid_data[0].decode().split()[-1].rstrip(')')
                elif isinstance(uid_data[0], tuple) and len(uid_data[0]) > 0:
                    # uid_data might be a tuple like (b'1 (UID 123)',)
                    uid = uid_data[0][0].decode() if isinstance(uid_data[0][0], bytes) else str(uid_data[0][0])
                    uid = uid.split()[-1].rstrip(')')
                else:
                    uid = str(uid_data[0]).split()[-1].rstrip(')')

                # Check if email already exists
                existing = session.query(Email).filter(
                    Email.email_account_id == account.id,
                    Email.message_id == uid
                ).first()

                if existing:
                    continue

                # Parse headers
                from_header = email_message.get('From', '')
                subject_header = email_message.get('Subject', '')
                date_header = email_message.get('Date', '')

                # Decode subject
                subject = self._decode_header(subject_header)

                # Extract body (safely handle None values)
                body_plain = ''
                body_html = ''

                if email_message.is_multipart():
                    for part in email_message.walk():
                        content_type = part.get_content_type()
                        if content_type == 'text/plain':
                            payload = part.get_payload(decode=True)
                            if payload:
                                body_plain = payload.decode('utf-8', errors='ignore')
                        elif content_type == 'text/html':
                            payload = part.get_payload(decode=True)
                            if payload:
                                body_html = payload.decode('utf-8', errors='ignore')
                else:
                    payload = email_message.get_payload(decode=True)
                    if payload:
                        body_plain = payload.decode('utf-8', errors='ignore')

                # Parse date
                try:
                    received_at = email.utils.parsedate_to_datetime(date_header)
                except:
                    received_at = datetime.utcnow()

                # Create email record
                email_record = Email(
                    user_id=account.user_id,
                    email_account_id=account.id,
                    message_id=uid,
                    thread_id=None,
                    from_address=email.utils.parseaddr(from_header)[1],
                    from_name=email.utils.parseaddr(from_header)[0],
                    to_addresses=json.dumps([email_message.get('To', '')]),
                    subject=subject,
                    body_plain=body_plain,
                    body_html=body_html,
                    snippet=(body_plain or body_html)[:200],
                    received_at=received_at,
                    labels=None,
                    is_read=False,  # IMAP doesn't easily expose read status in this context
                    is_starred=False,
                    is_important=False,
                    has_attachments=email_message.is_multipart(),
                    synced_at=datetime.utcnow(),
                    raw_data=None  # Don't store raw email to save space
                )

                session.add(email_record)
                emails_synced += 1

            session.commit()

            # Close connection
            try:
                imap.close()
                imap.logout()
            except:
                pass  # Already disconnected

            return {
                'success': True,
                'emails_synced': emails_synced,
                'provider': account.provider
            }

        except socket.timeout:
            return {
                'success': False,
                'error': f'IMAP connection timeout - server took too long to respond. Check your internet connection.'
            }
        except socket.gaierror as e:
            return {
                'success': False,
                'error': f'IMAP DNS lookup failed - could not resolve {imap_config.get("host", "server")}. Check server address.'
            }
        except ssl.SSLError as e:
            return {
                'success': False,
                'error': f'IMAP SSL/TLS error: {str(e)}. The secure connection failed.'
            }
        except imaplib.IMAP4.error as e:
            return {
                'success': False,
                'error': f'IMAP protocol error: {str(e)}'
            }
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"IMAP sync error for {account.provider} ({account.email_address}):")
            print(error_details)
            return {
                'success': False,
                'error': f'IMAP sync failed: {type(e).__name__}: {str(e)}'
            }
        finally:
            # Ensure IMAP connection is closed
            if imap:
                try:
                    imap.logout()
                except:
                    pass

    def _decode_header(self, header: str) -> str:
        """Decode email header with robust error handling."""
        try:
            decoded_parts = []
            for part, encoding in decode_header(header):
                if isinstance(part, bytes):
                    decoded_parts.append(part.decode(encoding or 'utf-8', errors='ignore'))
                elif isinstance(part, str):
                    decoded_parts.append(part)
                else:
                    # Handle unexpected types (int, etc.) by converting to string
                    decoded_parts.append(str(part))
            return ''.join(decoded_parts)
        except (AttributeError, TypeError, ValueError) as e:
            # If decoding fails entirely, return the header as-is
            return str(header)
