# ospra_os/gmail/routes.py
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

def _load_client_dict(cred_path: str):
    with open(cred_path, "r") as f:
        raw = json.load(f)
    if "web" in raw:
        return {"web": raw["web"]}
    if "installed" in raw:  # fallback
        return {"web": raw["installed"]}
    raise HTTPException(status_code=500, detail="Invalid Google client JSON (missing 'web' or 'installed').")

@router.get("/start")
async def gmail_auth_start(request: Request):
    cred_path, _ = _paths()
    client_config = _load_client_dict(cred_path)
    redirect_uri = str(request.url_for("gmail_auth_callback"))
    flow = Flow.from_client_config(client_config, scopes=SCOPES, redirect_uri=redirect_uri)
    auth_url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes=True, prompt="consent"
    )
    resp = RedirectResponse(auth_url, status_code=302)
    resp.set_cookie("gmail_oauth_state", state, httponly=True, secure=True, samesite="lax", max_age=600)
    return resp

@router.get("/callback", name="gmail_auth_callback", response_class=HTMLResponse)
async def gmail_auth_callback(request: Request):
    cred_path, token_path = _paths()
    state = request.cookies.get("gmail_oauth_state")
    client_config = _load_client_dict(cred_path)
    redirect_uri = str(request.url_for("gmail_auth_callback"))
    flow = Flow.from_client_config(client_config, scopes=SCOPES, state=state, redirect_uri=redirect_uri)
    flow.fetch_token(authorization_response=str(request.url))

    creds = flow.credentials
    data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes or []),
    }
    with open(token_path, "w") as f:
        json.dump(data, f)

    html = f"""
    <html><body style="font-family: system-ui; padding: 2rem">
      <h2>Gmail connected ✅</h2>
      <p>Tokens saved at <code>{token_path}</code>.</p>
      <p>You can now start the worker:</p>
      <pre>curl -X POST {str(request.base_url)}gmail/worker/start</pre>
    </body></html>
    """
    return HTMLResponse(html)

@router.get("/status")
async def gmail_auth_status():
    _, token_path = _paths()
    return {"connected": os.path.exists(token_path) and os.path.getsize(token_path) > 0, "token_path": token_path}
