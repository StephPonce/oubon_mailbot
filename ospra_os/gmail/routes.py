from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
import os, json, pathlib
from google_auth_oauthlib.flow import Flow

router = APIRouter(prefix="/gmail/auth", tags=["gmail"])

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.labels",
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
async def start(request: Request):
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
                f"<h2>❌ Directory Error</h2>"
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
                f"<h2>❌ Write Error</h2>"
                f"<p>Cannot write to: {token_path}</p>"
                f"<p>Error: {str(write_err)}</p>",
                status_code=500
            )

        return HTMLResponse(f"<h2>Gmail connected ✅</h2><p>Saved tokens to <code>{token_path}</code>.</p>")
    except Exception as e:
        import traceback
        return HTMLResponse(
            f"<h2>❌ OAuth Error</h2>"
            f"<p>Error: {str(e)}</p>"
            f"<pre>{traceback.format_exc()}</pre>",
            status_code=500
        )

@router.get("/status")
async def status():
    _, token_path = _paths()
    ok = os.path.exists(token_path) and os.path.getsize(token_path) > 0
    return {"connected": ok, "token_path": token_path}

@router.get("/debug")
async def debug(request: Request):
    cred_path, token_path = _paths()
    redirect_uri = str(request.url_for("gmail_oauth_callback"))
    return {
        "redirect_uri": redirect_uri,
        "cred_path": cred_path,
        "token_path": token_path,
        "creds_exist": os.path.exists(cred_path),
        "scopes": SCOPES,
    }
