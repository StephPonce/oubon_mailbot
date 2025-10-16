import asyncio
import base64
import pathlib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from app.settings import Settings, get_settings


class GmailClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.SCOPES = [settings.google_scopes]
        self.creds = None

    def _creds_path(self) -> pathlib.Path:
        return pathlib.Path(self.settings.google_credentials_file)

    def _token_path(self) -> pathlib.Path:
        return pathlib.Path(self.settings.google_token_file)

    def build_auth_url(self) -> str:
        flow = Flow.from_client_secrets_file(
            str(self._creds_path()),
            scopes=self.SCOPES,
            redirect_uri=self.settings.google_redirect_uri,
        )
        auth_url, _state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )
        return auth_url

    def exchange_code_for_tokens(self, code: str):
        flow = Flow.from_client_secrets_file(
            str(self._creds_path()),
            scopes=self.SCOPES,
            redirect_uri=self.settings.google_redirect_uri,
        )
        flow.fetch_token(code=code)
        creds = flow.credentials
        self._token_path().parent.mkdir(parents=True, exist_ok=True)
        self._token_path().write_text(creds.to_json(), encoding="utf-8")
        self.creds = creds

    def _load_creds(self) -> Credentials:
        tp = self._token_path()
        if not tp.exists():
            raise RuntimeError("No token yet. Visit /auth/url and complete consent.")
        return Credentials.from_authorized_user_file(str(tp), self.SCOPES)

    def service(self):
        creds = self._load_creds()
        return build("gmail", "v1", credentials=creds)

    def fetch_threads(self, max_results: int = 5) -> List[Dict[str, Any]]:
        svc = self.service()
        resp = svc.users().threads().list(userId="me", maxResults=max_results).execute()
        return resp.get("threads", [])

    def send_simple_email(self, to: str, subject: str, body: str):
        """Send an HTML email with a plain-text fallback."""
        svc = self.service()
        msg = MIMEMultipart("alternative")
        msg["To"] = to
        msg["Subject"] = subject
        msg["Auto-Submitted"] = "auto-replied"
        msg["X-Auto-Response-Suppress"] = "All"
        msg["Precedence"] = "bulk"
        msg.attach(MIMEText("Please view this email in an HTML-capable client.", "plain"))
        msg.attach(MIMEText(body, "html"))
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
        svc.users().messages().send(userId="me", body={"raw": raw}).execute()


async def send_plain_email(to: str, subject: str, body: str) -> None:
    """
    Send a plain-text confirmation email asynchronously via Gmail.
    """
    gc = get_gmail_client()

    def _send():
        svc = gc.service()
        msg = MIMEText(body, "plain")
        msg["To"] = to
        msg["Subject"] = subject
        msg["Auto-Submitted"] = "auto-replied"
        msg["X-Auto-Response-Suppress"] = "All"
        msg["Precedence"] = "bulk"
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
        svc.users().messages().send(userId="me", body={"raw": raw}).execute()

    await asyncio.to_thread(_send)


# -----------------------------------------------------------------------------
# Compatibility shims (for older main.py references)
# -----------------------------------------------------------------------------
_settings = get_settings()
_gmail_client = GmailClient(_settings)

def get_gmail_client() -> GmailClient:
    """Return the singleton Gmail client (used by main.py)."""
    return _gmail_client

def _svc(gc: GmailClient):
    """Return the Gmail API service instance."""
    return gc.service()
