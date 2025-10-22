from __future__ import annotations

import base64
import logging
import re
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
logger = logging.getLogger(__name__)


@dataclass
class GmailMessage:
    id: str
    thread_id: str
    raw: dict

    def header(self, name: str) -> Optional[str]:
        headers = self.raw.get("payload", {}).get("headers", [])
        for h in headers:
            if h.get("name", "").lower() == name.lower():
                return h.get("value")
        return None


class GmailClient:
    def __init__(self, user_email: str, token_path: str, credentials_path: str):
        self.user_email = user_email
        self.token_path = Path(token_path)
        self.credentials_path = Path(credentials_path)
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        self.credentials_path.parent.mkdir(parents=True, exist_ok=True)

        self.creds = self.ensure_credentials()
        self.service = build("gmail", "v1", credentials=self.creds, cache_discovery=False)
        self._labels_cache: dict[str, str] = {}

    def ensure_credentials(self) -> Credentials:
        creds: Optional[Credentials] = None
        if self.token_path.exists():
            creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.debug("Refreshing Gmail credentials")
                creds.refresh(Request())
            else:
                if not self.credentials_path.exists():
                    raise FileNotFoundError(
                        f"Gmail credentials file missing at {self.credentials_path}. "
                        "Provide OAuth client credentials to authenticate."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(str(self.credentials_path), SCOPES)
                creds = flow.run_local_server(port=0)
            with self.token_path.open("w") as token_file:
                token_file.write(creds.to_json())
        return creds

    def list_unprocessed_messages(self, processed_label: Optional[str], limit: int = 25) -> List[GmailMessage]:
        # Only exclude the processed label if it's actually configured.
        if processed_label and processed_label.strip():
            query = f'in:inbox -label:"{processed_label.strip()}"'
        else:
            query = 'in:inbox'

        response = self.service.users().messages().list(
            userId="me", q=query, maxResults=limit, labelIds=["INBOX"]
        ).execute()

        messages = response.get("messages", []) or []
        results: List[GmailMessage] = []
        for msg in messages:
            full_msg = self.get_message(msg["id"])
            results.append(GmailMessage(id=full_msg["id"], thread_id=full_msg["threadId"], raw=full_msg))
        return results

    def get_message(self, msg_id: str, format: str = "full") -> dict:
        return (
            self.service.users()
            .messages()
            .get(userId="me", id=msg_id, format=format, metadataHeaders=["Subject", "From", "To"])
            .execute()
        )

    def modify_labels(
        self,
        msg_id: str,
        labels_to_add: Optional[Iterable[str]] = None,
        labels_to_remove: Optional[Iterable[str]] = None,
    ) -> dict:
        # Drop blanks before calling Gmail
        add_names = [l.strip() for l in (labels_to_add or []) if l and l.strip()]
        rem_names = [l.strip() for l in (labels_to_remove or []) if l and l.strip()]

        add_ids = [self._ensure_label(name) for name in add_names]

        remove_ids: List[str] = []
        for name in rem_names:
            # Gmail system labels are uppercase (e.g., UNREAD). Pass through as-is.
            if name.isupper():
                remove_ids.append(name)
            else:
                lid = self.get_label_id(name)
                if lid:
                    remove_ids.append(lid)

        body = {"addLabelIds": add_ids, "removeLabelIds": remove_ids}
        return self.service.users().messages().modify(userId="me", id=msg_id, body=body).execute()

    def get_label_id(self, label_name: str) -> Optional[str]:
        if not label_name:
            return None
        if label_name in self._labels_cache:
            return self._labels_cache[label_name]
        labels = self.service.users().labels().list(userId="me").execute().get("labels", [])
        for label in labels:
            if label.get("name") == label_name:
                label_id = label.get("id")
                if label_id:
                    self._labels_cache[label_name] = label_id
                    return label_id
        return None

    def ensure_label(self, label_name: str) -> str:
        return self._ensure_label(label_name)

    def thread_has_label(
        self,
        thread_id: str,
        label_id: Optional[str] = None,
        *,
        label_name: Optional[str] = None,
    ) -> bool:
        if label_id is None:
            if label_name is None:
                raise ValueError("label_id or label_name is required")
            label_id = self._ensure_label(label_name)
        thread = (
            self.service.users()
            .threads()
            .get(userId="me", id=thread_id, format="full")
            .execute()
        )
        for message in thread.get("messages", []):
            if label_id in (message.get("labelIds") or []):
                return True
        return False

    def add_label_to_thread(
        self,
        thread_id: str,
        label_id: Optional[str] = None,
        *,
        label_name: Optional[str] = None,
    ) -> dict:
        if label_id is None:
            if label_name is None:
                raise ValueError("label_id or label_name is required")
            label_id = self._ensure_label(label_name)
        body = {"addLabelIds": [label_id], "removeLabelIds": []}
        return (
            self.service.users()
            .threads()
            .modify(userId="me", id=thread_id, body=body)
            .execute()
        )

    def add_labels(self, thread_id: str, label_ids: List[str]) -> dict:
        unique = list(dict.fromkeys([lid for lid in label_ids if lid]))
        if not unique:
            return {}
        body = {"addLabelIds": unique, "removeLabelIds": []}
        return (
            self.service.users()
            .threads()
            .modify(userId="me", id=thread_id, body=body)
            .execute()
        )

    def get_thread(self, thread_id: str, format: str = "full") -> dict:
        return (
            self.service.users()
            .threads()
            .get(userId="me", id=thread_id, format=format)
            .execute()
        )

    def reply_to_thread(
        self,
        thread_id: str,
        body_text: str,
        from_alias: str,
        from_name: Optional[str] = None,
        subject_override: Optional[str] = None,
    ) -> str:
        thread = self.get_thread(thread_id, format="full")
        messages = thread.get("messages", [])
        if not messages:
            raise ValueError("Thread has no messages to reply to")
        last_msg = messages[-1]
        headers = {
            (h.get("name") or "").lower(): h.get("value") or ""
            for h in (last_msg.get("payload") or {}).get("headers") or []
        }
        original_subject = headers.get("subject", "")
        if subject_override:
            reply_subject = subject_override
        elif original_subject.lower().startswith("re:"):
            reply_subject = original_subject
        else:
            reply_subject = f"Re: {original_subject}" if original_subject else "Re:"
        reply_payload = {"subject": reply_subject, "body": body_text}
        return self.send_reply(
            self.user_email,
            last_msg,
            reply_payload,
            send_as=from_alias,
            from_name=from_name,
        )

    def send_reply(
        self,
        user_email: str,
        msg: dict,
        reply: dict,
        send_as: Optional[str] = None,
        from_name: Optional[str] = None,
    ) -> str:
        thread_id = msg.get("threadId")
        payload = msg.get("payload", {}) or {}
        headers = {
            (h.get("name") or "").lower(): h.get("value") or ""
            for h in (payload.get("headers") or [])
        }
        to_addr = headers.get("reply-to") or headers.get("from")
        if not to_addr:
            raise ValueError("Original message missing sender address; cannot compose reply.")

        message_id = headers.get("message-id")
        references = headers.get("references")

        email_msg = EmailMessage()
        email_msg["To"] = to_addr
        from_email = str(send_as or user_email)
        display_name = from_name or ""
        email_msg["From"] = formataddr((display_name, from_email)) if display_name else from_email
        email_msg["Subject"] = reply["subject"]
        reply_to_value = formataddr((display_name, from_email)) if display_name else from_email
        email_msg["Reply-To"] = reply_to_value
        if message_id:
            email_msg["In-Reply-To"] = message_id
        if references:
            email_msg["References"] = references
        email_msg.set_content(reply["body"].strip())

        raw = base64.urlsafe_b64encode(email_msg.as_bytes()).decode("utf-8")
        body = {"raw": raw}
        if thread_id:
            body["threadId"] = thread_id

        sent = self.service.users().messages().send(userId="me", body=body).execute()
        return sent["id"]

    def _ensure_label(self, label_name: str) -> str:
        label_id = self.get_label_id(label_name)
        if label_id:
            return label_id
        if not label_name:
            raise ValueError("label_name must be provided")
        label_body = {
            "name": label_name,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show",
        }
        created = self.service.users().labels().create(userId="me", body=label_body).execute()
        label_id = created["id"]
        self._labels_cache[label_name] = label_id
        return label_id

    @staticmethod
    def is_ignored_sender(sender_email: str, domains: List[str], patterns: List[str]) -> bool:
        email_lower = (sender_email or "").lower()
        if not email_lower:
            return False
        for domain in domains or []:
            d = domain.lower().strip()
            if d and email_lower.endswith(f"@{d}"):
                return True
        for pattern in patterns or []:
            if pattern and re.search(pattern, email_lower, flags=re.IGNORECASE):
                return True
        return False

    @staticmethod
    def thread_has_outgoing_from(thread: Dict[str, Any], alias: str) -> bool:
        if not alias:
            return False
        alias_lower = alias.lower()
        for message in thread.get("messages", []):
            headers = {
                (h.get("name") or "").lower(): h.get("value") or ""
                for h in (message.get("payload") or {}).get("headers") or []
            }
            frm = headers.get("from", "")
            if alias_lower in frm.lower():
                return True
        return False
