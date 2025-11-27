"""
Email Sender Service

Handles sending email replies through different providers (Gmail, Outlook, IMAP/SMTP).
"""

from typing import Dict
import json
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
import os
from cryptography.fernet import Fernet

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import base64
import httpx

logger = logging.getLogger(__name__)


class EmailSenderService:
    """
    Unified email sending service for all providers.

    Sends replies through Gmail OAuth, Outlook Graph API, or SMTP.
    """

    def __init__(self):
        # Get encryption key for decrypting stored credentials
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

    async def send_compose(self, account, to_addresses: list, subject: str, body: str,
                          cc_addresses: list = None, bcc_addresses: list = None) -> Dict:
        """
        Send a new composed email.

        Args:
            account: UserEmailAccount database object
            to_addresses: List of recipient email addresses
            subject: Email subject line
            body: Email body content
            cc_addresses: Optional list of CC addresses
            bcc_addresses: Optional list of BCC addresses

        Returns:
            Dict with success status and optional error message
        """
        try:
            # Decrypt account credentials
            creds = self._decrypt_credentials(account.encrypted_credentials)

            # Route to appropriate provider
            if account.provider == 'gmail':
                return await self._send_gmail_compose(account, to_addresses, subject, body,
                                                      cc_addresses, bcc_addresses, creds)
            elif account.provider == 'outlook':
                return await self._send_outlook_compose(account, to_addresses, subject, body,
                                                        cc_addresses, bcc_addresses, creds)
            elif account.provider in ['icloud', 'yahoo', 'zoho', 'protonmail', 'custom']:
                return await self._send_smtp_compose(account, to_addresses, subject, body,
                                                     cc_addresses, bcc_addresses, creds)
            else:
                return {
                    'success': False,
                    'error': f'Unsupported provider: {account.provider}'
                }

        except Exception as e:
            logger.error(f"Failed to send composed email: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    async def send_reply(self, account, original_email, reply_message: str) -> Dict:
        """
        Send a reply to an email.

        Args:
            account: UserEmailAccount database object
            original_email: Email database object (the email being replied to)
            reply_message: The reply text content

        Returns:
            Dict with success status and optional error message
        """
        try:
            # Decrypt account credentials
            creds = self._decrypt_credentials(account.encrypted_credentials)

            # Route to appropriate provider
            if account.provider == 'gmail':
                return await self._send_gmail_reply(account, original_email, reply_message, creds)
            elif account.provider == 'outlook':
                return await self._send_outlook_reply(account, original_email, reply_message, creds)
            elif account.provider in ['icloud', 'yahoo', 'zoho', 'protonmail', 'custom']:
                return await self._send_smtp_reply(account, original_email, reply_message, creds)
            else:
                return {
                    'success': False,
                    'error': f'Unsupported provider: {account.provider}'
                }

        except Exception as e:
            logger.error(f"Failed to send reply: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    async def _send_gmail_compose(self, account, to_addresses: list, subject: str, body: str,
                                  cc_addresses: list, bcc_addresses: list, creds: Dict) -> Dict:
        """Send new email via Gmail API"""
        try:
            # Build OAuth credentials
            credentials = Credentials(
                token=creds.get('access_token'),
                refresh_token=creds.get('refresh_token'),
                token_uri='https://oauth2.googleapis.com/token',
                client_id=os.getenv('GOOGLE_OAUTH_CLIENT_ID'),
                client_secret=os.getenv('GOOGLE_OAUTH_CLIENT_SECRET'),
                scopes=['https://www.googleapis.com/auth/gmail.send']
            )

            # Build Gmail service
            service = build('gmail', 'v1', credentials=credentials)

            # Create message
            message = MIMEMultipart()
            message['from'] = account.email_address
            message['to'] = ', '.join(to_addresses)
            message['subject'] = subject

            # Add CC and BCC if provided
            if cc_addresses:
                message['cc'] = ', '.join(cc_addresses)
            if bcc_addresses:
                message['bcc'] = ', '.join(bcc_addresses)

            # Add message body
            message.attach(MIMEText(body, 'plain'))

            # Encode message
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')

            # Send via Gmail API
            service.users().messages().send(
                userId='me',
                body={'raw': raw_message}
            ).execute()

            logger.info(f"Email sent via Gmail from {account.email_address} to {to_addresses}")
            return {'success': True}

        except Exception as e:
            logger.error(f"Gmail send failed: {e}")
            return {'success': False, 'error': f'Gmail send failed: {str(e)}'}

    async def _send_outlook_compose(self, account, to_addresses: list, subject: str, body: str,
                                    cc_addresses: list, bcc_addresses: list, creds: Dict) -> Dict:
        """Send new email via Microsoft Graph API"""
        try:
            access_token = creds.get('access_token')

            # Build message data
            message_data = {
                'message': {
                    'subject': subject,
                    'body': {
                        'contentType': 'Text',
                        'content': body
                    },
                    'toRecipients': [
                        {'emailAddress': {'address': addr}} for addr in to_addresses
                    ]
                }
            }

            # Add CC and BCC if provided
            if cc_addresses:
                message_data['message']['ccRecipients'] = [
                    {'emailAddress': {'address': addr}} for addr in cc_addresses
                ]
            if bcc_addresses:
                message_data['message']['bccRecipients'] = [
                    {'emailAddress': {'address': addr}} for addr in bcc_addresses
                ]

            # Send via Graph API
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    'https://graph.microsoft.com/v1.0/me/sendMail',
                    headers={'Authorization': f'Bearer {access_token}'},
                    json=message_data,
                    timeout=30.0
                )

                if response.status_code not in [200, 201, 202]:
                    return {
                        'success': False,
                        'error': f'Outlook API error: {response.status_code} - {response.text}'
                    }

            logger.info(f"Email sent via Outlook from {account.email_address} to {to_addresses}")
            return {'success': True}

        except Exception as e:
            logger.error(f"Outlook send failed: {e}")
            return {'success': False, 'error': f'Outlook send failed: {str(e)}'}

    async def _send_smtp_compose(self, account, to_addresses: list, subject: str, body: str,
                                cc_addresses: list, bcc_addresses: list, creds: Dict) -> Dict:
        """Send new email via SMTP (iCloud, Yahoo, Zoho, etc.)"""
        try:
            # Get SMTP configuration from credentials
            smtp_config = creds.get('smtp_config', {})
            smtp_host = smtp_config.get('host')
            smtp_port = smtp_config.get('port', 587)
            password = creds.get('access_token')  # App password is stored as access_token

            if not smtp_host or not password:
                return {
                    'success': False,
                    'error': 'Missing SMTP configuration or password'
                }

            # Create message
            message = MIMEMultipart()
            message['From'] = formataddr((account.email_address.split('@')[0], account.email_address))
            message['To'] = ', '.join(to_addresses)
            message['Subject'] = subject

            # Add CC and BCC if provided
            if cc_addresses:
                message['Cc'] = ', '.join(cc_addresses)
            if bcc_addresses:
                message['Bcc'] = ', '.join(bcc_addresses)

            # Add message body
            message.attach(MIMEText(body, 'plain'))

            # Build recipient list (To + CC + BCC)
            all_recipients = to_addresses.copy()
            if cc_addresses:
                all_recipients.extend(cc_addresses)
            if bcc_addresses:
                all_recipients.extend(bcc_addresses)

            # Send via SMTP
            with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
                server.starttls()
                server.login(account.email_address, password)
                server.sendmail(account.email_address, all_recipients, message.as_string())

            logger.info(f"Email sent via SMTP from {account.email_address} to {to_addresses}")
            return {'success': True}

        except Exception as e:
            logger.error(f"SMTP send failed: {e}")
            return {'success': False, 'error': f'SMTP send failed: {str(e)}'}

    async def _send_gmail_reply(self, account, original_email, reply_message: str, creds: Dict) -> Dict:
        """Send reply via Gmail API"""
        try:
            # Build OAuth credentials
            credentials = Credentials(
                token=creds.get('access_token'),
                refresh_token=creds.get('refresh_token'),
                token_uri='https://oauth2.googleapis.com/token',
                client_id=os.getenv('GOOGLE_OAUTH_CLIENT_ID'),
                client_secret=os.getenv('GOOGLE_OAUTH_CLIENT_SECRET'),
                scopes=['https://www.googleapis.com/auth/gmail.send']
            )

            # Build Gmail service
            service = build('gmail', 'v1', credentials=credentials)

            # Create reply message
            message = MIMEMultipart()
            message['to'] = original_email.from_address
            message['from'] = account.email_address
            message['subject'] = f"Re: {original_email.subject or '(No Subject)'}"

            # Add In-Reply-To and References headers for threading
            if original_email.message_id:
                message['In-Reply-To'] = original_email.message_id
                message['References'] = original_email.message_id

            # Add message body
            message.attach(MIMEText(reply_message, 'plain'))

            # Encode message
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')

            # Send via Gmail API
            service.users().messages().send(
                userId='me',
                body={'raw': raw_message}
            ).execute()

            logger.info(f"Reply sent via Gmail from {account.email_address}")
            return {'success': True}

        except Exception as e:
            logger.error(f"Gmail send failed: {e}")
            return {'success': False, 'error': f'Gmail send failed: {str(e)}'}

    async def _send_outlook_reply(self, account, original_email, reply_message: str, creds: Dict) -> Dict:
        """Send reply via Microsoft Graph API"""
        try:
            access_token = creds.get('access_token')

            # Build reply request
            reply_data = {
                'message': {
                    'toRecipients': [
                        {'emailAddress': {'address': original_email.from_address}}
                    ],
                    'body': {
                        'contentType': 'Text',
                        'content': reply_message
                    }
                }
            }

            # Get the original message ID from the stored email
            # (Outlook uses Graph API message IDs)
            message_id = original_email.external_id or original_email.message_id

            # Send reply via Graph API
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f'https://graph.microsoft.com/v1.0/me/messages/{message_id}/reply',
                    headers={'Authorization': f'Bearer {access_token}'},
                    json=reply_data,
                    timeout=30.0
                )

                if response.status_code not in [200, 201, 202]:
                    return {
                        'success': False,
                        'error': f'Outlook API error: {response.status_code} - {response.text}'
                    }

            logger.info(f"Reply sent via Outlook from {account.email_address}")
            return {'success': True}

        except Exception as e:
            logger.error(f"Outlook send failed: {e}")
            return {'success': False, 'error': f'Outlook send failed: {str(e)}'}

    async def _send_smtp_reply(self, account, original_email, reply_message: str, creds: Dict) -> Dict:
        """Send reply via SMTP (iCloud, Yahoo, Zoho, etc.)"""
        try:
            # Get SMTP configuration from credentials
            smtp_config = creds.get('smtp_config', {})
            smtp_host = smtp_config.get('host')
            smtp_port = smtp_config.get('port', 587)
            password = creds.get('access_token')  # App password is stored as access_token

            if not smtp_host or not password:
                return {
                    'success': False,
                    'error': 'Missing SMTP configuration or password'
                }

            # Create reply message
            message = MIMEMultipart()
            message['From'] = formataddr((account.email_address.split('@')[0], account.email_address))
            message['To'] = original_email.from_address
            message['Subject'] = f"Re: {original_email.subject or '(No Subject)'}"

            # Add In-Reply-To and References headers for threading
            if original_email.message_id:
                message['In-Reply-To'] = original_email.message_id
                message['References'] = original_email.message_id

            # Add message body
            message.attach(MIMEText(reply_message, 'plain'))

            # Send via SMTP
            with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
                server.starttls()
                server.login(account.email_address, password)
                server.send_message(message)

            logger.info(f"Reply sent via SMTP from {account.email_address}")
            return {'success': True}

        except Exception as e:
            logger.error(f"SMTP send failed: {e}")
            return {'success': False, 'error': f'SMTP send failed: {str(e)}'}
