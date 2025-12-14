import base64
import pathlib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from ospra_os.core.settings import Settings  # Use ospra_os settings for Render compatibility


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
        msg.attach(MIMEText("Please view this email in an HTML-capable client.", "plain"))
        msg.attach(MIMEText(body, "html"))
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
        svc.users().messages().send(userId="me", body={"raw": raw}).execute()
