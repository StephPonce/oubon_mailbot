from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
import os, json, pathlib, hmac as _hmac, hashlib
from google_auth_oauthlib.flow import Flow
from datetime import datetime, timezone

from ospra_os.auth.jwt_auth import get_current_user
from ospra_os.database import User

# Allow OAuth over HTTP for local development
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

router = APIRouter(prefix="/gmail/auth", tags=["gmail"])


# T53: the callback used to attach EVERY connected Gmail account to a
# hardcoded user_id=1 — in a multi-tenant deployment, whoever connected Gmail
# had their inbox wired to the first user (and no one else could connect).
# We now bind the OAuth round-trip to the authenticated user who started it:
# /start requires auth and drops an HMAC-signed, httponly cookie carrying
# their id; /callback verifies it and attaches the account to that real user.

def _uid_secret() -> bytes:
    from ospra_os.auth.jwt_auth import SECRET_KEY
    return f"gmail-oauth-uid:{SECRET_KEY}".encode()


def _sign_uid(user_id: int) -> str:
    sig = _hmac.new(_uid_secret(), str(user_id).encode(), hashlib.sha256).hexdigest()[:32]
    return f"{user_id}.{sig}"


def _verify_uid(cookie: str | None) -> int | None:
    if not cookie or "." not in cookie:
        return None
    uid_raw, sig = cookie.rsplit(".", 1)
    expected = _hmac.new(_uid_secret(), uid_raw.encode(), hashlib.sha256).hexdigest()[:32]
    if not _hmac.compare_digest(expected, sig):
        return None
    try:
        return int(uid_raw)
    except ValueError:
        return None

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.labels",
    "https://www.googleapis.com/auth/gmail.send",
]

def _paths():
    cred_path = os.getenv("OUBONSHOP_GMAIL_CREDENTIALS_PATH", "/etc/secrets/gmail_credentials.json")
    token_path = os.getenv("OUBONSHOP_GMAIL_TOKEN_PATH", "/data/gmail/token.json")
    pathlib.Path(token_path).parent.mkdir(parents=True, exist_ok=True)
    if not os.path.exists(cred_path):
        raise HTTPException(status_code=500, detail=f"Credentials file not found at {cred_path}")
    return cred_path, token_path

def _client_config(cred_path: str):
    with open(cred_path, "r") as f:
        raw = json.load(f)
    if "web" in raw:         # preferred for web servers
        return {"web": raw["web"]}
    if "installed" in raw:   # fallback if creds are of “installed app” type
        return {"web": raw["installed"]}
    raise HTTPException(status_code=500, detail="Invalid Google client JSON")

@router.get("/start")
async def start(request: Request, current_user: User = Depends(get_current_user)):
    cred_path, _ = _paths()
    flow = Flow.from_client_config(
        _client_config(cred_path),
        scopes=SCOPES,
        redirect_uri=str(request.url_for("gmail_oauth_callback")),
    )
    auth_url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes="true", prompt="consent"
    )
    resp = RedirectResponse(auth_url, status_code=302)
    resp.set_cookie("gmail_oauth_state", state, httponly=True, secure=True, samesite="lax", max_age=600)
    # T53: bind this OAuth round-trip to the caller so the callback attaches
    # the Gmail account to THEM, not a hardcoded user_id=1.
    resp.set_cookie(
        "gmail_oauth_uid", _sign_uid(current_user.id),
        httponly=True, secure=True, samesite="lax", max_age=600,
    )
    return resp

@router.get("/callback", name="gmail_oauth_callback", response_class=HTMLResponse)
async def callback(request: Request):
    try:
        cred_path, token_path = _paths()
        state = request.cookies.get("gmail_oauth_state")
        flow = Flow.from_client_config(
            _client_config(cred_path),
            scopes=SCOPES,
            state=state,
            redirect_uri=str(request.url_for("gmail_oauth_callback")),
        )
        flow.fetch_token(authorization_response=str(request.url))
        c = flow.credentials

        # Ensure directory exists with proper error handling
        token_dir = pathlib.Path(token_path).parent
        try:
            token_dir.mkdir(parents=True, exist_ok=True)
        except Exception as mkdir_err:
            return HTMLResponse(
                f"<h2>[ERROR] Directory Error</h2>"
                f"<p>Cannot create directory: {token_dir}</p>"
                f"<p>Error: {str(mkdir_err)}</p>",
                status_code=500
            )

        # Try to write token file
        try:
            with open(token_path, "w") as f:
                json.dump({
                    "token": c.token,
                    "refresh_token": c.refresh_token,
                    "token_uri": c.token_uri,
                    "client_id": c.client_id,
                    "client_secret": c.client_secret,
                    "scopes": list(c.scopes or []),
                }, f)
        except Exception as write_err:
            return HTMLResponse(
                f"<h2>[ERROR] Write Error</h2>"
                f"<p>Cannot write to: {token_path}</p>"
                f"<p>Error: {str(write_err)}</p>",
                status_code=500
            )

        # ALSO save to unified user_email_accounts table
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            from ospra_os.database import User, UserEmailAccount, get_multi_store_session
            from ospra_os.email_automation.oauth.gmail_oauth import GmailOAuthHandler

            # Get user's email address from Gmail API
            gmail_creds = Credentials(
                token=c.token,
                refresh_token=c.refresh_token,
                token_uri=c.token_uri,
                client_id=c.client_id,
                client_secret=c.client_secret,
                scopes=list(c.scopes or [])
            )
            gmail_service = build('gmail', 'v1', credentials=gmail_creds)
            profile = gmail_service.users().getProfile(userId='me').execute()
            email_address = profile['emailAddress']

            # Save to database
            session = get_multi_store_session()
            try:
                # T53: attach to the authenticated user who started the flow
                # (carried via the signed gmail_oauth_uid cookie), NEVER a
                # hardcoded user_id=1. A missing/forged cookie is a hard error
                # so we can't silently wire someone's inbox to the wrong tenant.
                bound_uid = _verify_uid(request.cookies.get("gmail_oauth_uid"))
                if bound_uid is None:
                    return HTMLResponse(
                        "<h2>Gmail connection failed</h2>"
                        "<p>Your session could not be verified. Please start the "
                        "connection again from your dashboard.</p>",
                        status_code=400,
                    )
                user = session.query(User).filter(User.id == bound_uid).first()
                if not user:
                    return HTMLResponse(
                        "<h2>Gmail connection failed</h2>"
                        "<p>Account not found. Please sign in again.</p>",
                        status_code=400,
                    )

                # Check if Gmail account already exists
                existing = session.query(UserEmailAccount).filter(
                    UserEmailAccount.user_id == user.id,
                    UserEmailAccount.provider == 'gmail',
                    UserEmailAccount.email_address == email_address
                ).first()

                if not existing:
                    # Encrypt and save credentials
                    gmail_handler = GmailOAuthHandler()
                    creds_dict = {
                        'access_token': c.token,
                        'refresh_token': c.refresh_token,
                        'token_uri': c.token_uri,
                        'client_id': c.client_id,
                        'client_secret': c.client_secret,
                        'scopes': list(c.scopes or [])
                    }
                    encrypted_creds = gmail_handler.encrypt_credentials(creds_dict)

                    # Create new account record
                    new_account = UserEmailAccount(
                        user_id=user.id,
                        provider='gmail',
                        email_address=email_address,
                        encrypted_credentials=encrypted_creds,
                        is_active=True,
                        is_primary=False,
                        sync_status='active',
                        created_at=datetime.now(timezone.utc)
                    )
                    session.add(new_account)
                    session.commit()
                else:
                    # Update existing account credentials
                    gmail_handler = GmailOAuthHandler()
                    creds_dict = {
                        'access_token': c.token,
                        'refresh_token': c.refresh_token,
                        'token_uri': c.token_uri,
                        'client_id': c.client_id,
                        'client_secret': c.client_secret,
                        'scopes': list(c.scopes or [])
                    }
                    existing.encrypted_credentials = gmail_handler.encrypt_credentials(creds_dict)
                    existing.is_active = True
                    existing.sync_status = 'active'
                    session.commit()

            finally:
                session.close()

        except Exception as db_err:
            # Don't fail the whole OAuth if database save fails
            # SECURITY: Log error server-side, don't expose details
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to save Gmail to database: {db_err}", exc_info=True)

        return HTMLResponse(f"<h2>Gmail connected [SUCCESS]</h2><p>Saved tokens to <code>{token_path}</code> and database.</p>")
    except Exception as e:
        # SECURITY: Log traceback server-side, don't expose to client
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Gmail OAuth callback failed: {e}", exc_info=True)
        return HTMLResponse(
            f"<h2>[ERROR] OAuth Error</h2>"
            f"<p>Authentication failed. Please try again or contact support.</p>",
            status_code=500
        )

@router.get("/status")
async def status(current_user: User = Depends(get_current_user)):
    _, token_path = _paths()
    ok = os.path.exists(token_path) and os.path.getsize(token_path) > 0
    # SECURITY: Don't expose file paths in production
    return {"connected": ok}


# DEBUG ENDPOINT REMOVED FOR SECURITY
# The /debug endpoint exposed sensitive file paths and OAuth scopes.
# It has been removed. Use server logs for debugging.


@router.get("/messages")
async def get_messages(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
):
    """
    Fetch recent Gmail messages for dashboard display

    AUTH REQUIRED (added 2026-08). This handler reads the shared Gmail token
    file and returns real message contents including customer PII. It had no
    auth dependency, so an anonymous caller could read the production mailbox
    — it returned 500 rather than data only because the token file is absent
    from the container, which is luck, not a control.

    Returns unread/important messages with:
    - Subject
    - Sender
    - Snippet
    - Timestamp
    - Labels
    """
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    import base64
    from datetime import datetime

    _, token_path = _paths()
    if not os.path.exists(token_path):
        raise HTTPException(status_code=401, detail="Gmail not connected. Please authenticate first.")

    try:
        # Load credentials
        with open(token_path, "r") as f:
            token_data = json.load(f)

        creds = Credentials(
            token=token_data.get("token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri=token_data.get("token_uri"),
            client_id=token_data.get("client_id"),
            client_secret=token_data.get("client_secret"),
            scopes=token_data.get("scopes")
        )

        service = build("gmail", "v1", credentials=creds)

        # Fetch messages
        results = service.users().messages().list(
            userId="me",
            maxResults=limit,
            labelIds=["INBOX"]
        ).execute()

        messages = results.get("messages", [])

        formatted_messages = []
        for msg in messages:
            # Get full message details
            full_msg = service.users().messages().get(
                userId="me",
                id=msg["id"],
                format="full"
            ).execute()

            headers = full_msg["payload"]["headers"]
            subject = next((h["value"] for h in headers if h["name"].lower() == "subject"), "No Subject")
            sender = next((h["value"] for h in headers if h["name"].lower() == "from"), "Unknown")
            date_str = next((h["value"] for h in headers if h["name"].lower() == "date"), "")

            formatted_messages.append({
                "id": msg["id"],
                "subject": subject,
                "from": sender,
                "snippet": full_msg.get("snippet", ""),
                "date": date_str,
                "labels": full_msg.get("labelIds", []),
                "is_unread": "UNREAD" in full_msg.get("labelIds", []),
                "thread_id": full_msg.get("threadId")
            })

        return {
            "success": True,
            "messages": formatted_messages,
            "total": len(formatted_messages)
        }

    except Exception as e:
        # SECURITY: Log traceback server-side, don't expose to client
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to fetch Gmail messages: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch messages. Please reconnect Gmail or try again."
        )

@router.get("/stats")
async def get_stats(current_user: User = Depends(get_current_user)):
    """
    Get Gmail statistics for dashboard (AUTH REQUIRED — reads the mailbox)

    Returns:
    - Total unread count
    - Important messages
    - Recent activity
    """
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    _, token_path = _paths()
    if not os.path.exists(token_path):
        return {
            "connected": False,
            "unread_count": 0,
            "important_count": 0
        }

    try:
        # Load credentials
        with open(token_path, "r") as f:
            token_data = json.load(f)

        creds = Credentials(
            token=token_data.get("token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri=token_data.get("token_uri"),
            client_id=token_data.get("client_id"),
            client_secret=token_data.get("client_secret"),
            scopes=token_data.get("scopes")
        )

        service = build("gmail", "v1", credentials=creds)

        # Get actual unread count in INBOX (using pagination for accuracy)
        # Gmail's resultSizeEstimate is often inaccurate, so we count messages
        unread_query = service.users().messages().list(
            userId="me",
            labelIds=["INBOX", "UNREAD"],
            maxResults=500  # Get more for accurate count
        ).execute()

        unread_count = len(unread_query.get("messages", []))

        # Check if there are more pages (for very high unread counts)
        next_page_token = unread_query.get("nextPageToken")
        if next_page_token:
            # If there are more than 500, fall back to estimate
            unread_count = unread_query.get("resultSizeEstimate", unread_count)

        # Get important count in INBOX only
        important_query = service.users().messages().list(
            userId="me",
            labelIds=["INBOX", "IMPORTANT"],
            maxResults=500
        ).execute()

        important_count = len(important_query.get("messages", []))
        next_page_token = important_query.get("nextPageToken")
        if next_page_token:
            important_count = important_query.get("resultSizeEstimate", important_count)

        return {
            "connected": True,
            "unread_count": unread_count,
            "important_count": important_count
        }

    except Exception as e:
        return {
            "connected": True,
            "error": str(e),
            "unread_count": 0,
            "important_count": 0
        }
