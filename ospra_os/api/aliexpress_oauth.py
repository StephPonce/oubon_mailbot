"""
AliExpress OAuth callback handler
"""
import json
import httpx
import time
import hashlib
import hmac
import logging
import os
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/aliexpress", tags=["aliexpress"])

# AliExpress Dropshipping API credentials (from .env)
# SECURITY: Secrets must be provided via environment variables - no defaults
ALIEXPRESS_APP_KEY = os.getenv("ALIEXPRESS_APP_KEY", "")
ALIEXPRESS_APP_SECRET = os.getenv("ALIEXPRESS_APP_SECRET", "")
# Token endpoint - AliExpress REST API structure
# NOTE: Both endpoints tested, both fail:
#   - https://oauth.aliexpress.com/token → "appkey not exists" error
#   - https://api-sg.aliexpress.com/rest/auth/token/create → "IncompleteSignature" error
# Waiting for clarification from AliExpress support on correct endpoint
ALIEXPRESS_TOKEN_URL = "https://api-sg.aliexpress.com/rest/auth/token/create"
# Redirect URI must point at the API host (this is a backend callback route).
# Env-driven so it's never pinned to a stale domain again (was the dead
# oubon-mailbot host, which broke the OAuth callback). Default = current API.
ALIEXPRESS_REDIRECT_URI = os.getenv(
    "ALIEXPRESS_REDIRECT_URI",
    "https://ospra-intelligence-api.onrender.com/api/aliexpress/callback",
)

# Token storage path
TOKENS_FILE = Path(".secrets/aliexpress_tokens.json")


def generate_aliexpress_signature_md5_wrapped(params: dict, app_secret: str) -> str:
    """
    Generate AliExpress API signature using MD5 with secret wrapping

    Algorithm (from working Stack Overflow examples):
    1. Sort parameters alphabetically by key (exclude 'sign')
    2. Concatenate as: key1value1key2value2...
    3. Wrap with secret: secret + concatenated_string + secret
    4. Calculate MD5 hash
    5. Convert to uppercase hexadecimal
    """
    # Sort parameters alphabetically (exclude 'sign' if present)
    sorted_params = sorted([(k, v) for k, v in params.items() if k != 'sign'])

    # Concatenate as: key1value1key2value2...
    concat_str = ''.join([f"{k}{v}" for k, v in sorted_params])

    # Wrap with secret on both sides
    sign_str = f"{app_secret}{concat_str}{app_secret}"

    # Calculate plain MD5 and convert to uppercase
    signature = hashlib.md5(sign_str.encode('utf-8')).hexdigest().upper()

    return signature


def generate_aliexpress_signature_sha256(params: dict, app_secret: str, api_path: str = "/auth/token/create") -> str:
    """
    Generate AliExpress API signature using HMAC-SHA256

    Algorithm (from working JavaScript examples):
    1. Sort parameters alphabetically by key (exclude 'sign')
    2. Concatenate as: /api/pathkey1value1key2value2...
    3. Use HMAC-SHA256 with app_secret as key
    4. Convert to uppercase hexadecimal
    """
    # Sort parameters alphabetically (exclude 'sign' if present)
    sorted_params = sorted([(k, v) for k, v in params.items() if k != 'sign'])

    # Concatenate as: /api/path + key1value1key2value2...
    concat_str = api_path + ''.join([f"{k}{v}" for k, v in sorted_params])

    # Calculate HMAC-SHA256 signature
    signature = hmac.new(
        app_secret.encode('utf-8'),
        concat_str.encode('utf-8'),
        hashlib.sha256
    ).hexdigest().upper()

    return signature


def generate_aliexpress_signature_hmac(params: dict, app_secret: str) -> str:
    """
    Generate AliExpress API signature using HMAC-MD5

    Algorithm:
    1. Sort parameters alphabetically by key
    2. Concatenate as: key1value1key2value2...
    3. Use HMAC-MD5 with app_secret as key
    4. Convert to uppercase
    """
    # Sort parameters alphabetically (exclude 'sign' if present)
    sorted_params = sorted([(k, v) for k, v in params.items() if k != 'sign'])

    # Concatenate as key1value1key2value2...
    concat_str = ''.join([f"{k}{v}" for k, v in sorted_params])

    # Calculate HMAC-MD5 and convert to uppercase
    signature = hmac.new(
        app_secret.encode('utf-8'),
        concat_str.encode('utf-8'),
        hashlib.md5
    ).hexdigest().upper()

    return signature


@router.get("/oauth-callback")
@router.get("/callback")  # Support both /oauth-callback and /callback
async def oauth_callback(
    code: str = Query(None, description="Authorization code from AliExpress"),
    state: str = Query(None, description="State parameter"),
    error: str = Query(None, description="Error if authorization failed")
):
    """
    OAuth callback endpoint for AliExpress Dropshipping API

    Automatically exchanges the authorization code for access tokens
    """

    if error:
        return HTMLResponse(
            content=f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>AliExpress OAuth - Error</title>
                <style>
                    body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }}
                    .error {{ background: #fee; border: 2px solid #c00; padding: 20px; border-radius: 5px; }}
                    h1 {{ color: #c00; }}
                </style>
            </head>
            <body>
                <div class="error">
                    <h1>[ERROR] Authorization Failed</h1>
                    <p><strong>Error:</strong> {error}</p>
                    <p>Please try again or check your AliExpress app configuration.</p>
                </div>
            </body>
            </html>
            """,
            status_code=400
        )

    if not code:
        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html>
            <head>
                <title>AliExpress OAuth - Missing Code</title>
                <style>
                    body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }}
                    .error {{ background: #fee; border: 2px solid #c00; padding: 20px; border-radius: 5px; }}
                    h1 {{ color: #c00; }}
                </style>
            </head>
            <body>
                <div class="error">
                    <h1>[ERROR] Missing Authorization Code</h1>
                    <p>No authorization code received from AliExpress.</p>
                </div>
            </body>
            </html>
            """,
            status_code=400
        )

    # Exchange code for tokens
    token_response = None
    token_error = None

    try:
        async with httpx.AsyncClient() as client:
            # AliExpress REST API token exchange with signature
            # Based on working examples from Stack Overflow and official SDKs
            timestamp = str(int(time.time() * 1000))  # Milliseconds

            # System parameters (required for all AliExpress API calls)
            params = {
                "app_key": ALIEXPRESS_APP_KEY,
                "timestamp": timestamp,
                "sign_method": "sha256",  # Using SHA256 (more common in recent examples)
                "format": "json",
                "v": "2.0",
                "method": "auth.token.create",
                "code": code  # Authorization code
            }

            # Generate signature using HMAC-SHA256 (from working JavaScript examples)
            signature = generate_aliexpress_signature_sha256(params, ALIEXPRESS_APP_SECRET)
            params["sign"] = signature

            # T6: the signature + full params (incl. app_key/sign) and the raw
            # token-exchange body used to be print()ed to stdout — secrets in
            # the logs. Log only the non-sensitive status.
            logger.info("AliExpress dropship token exchange: submitting authorization code")

            # Exchange code for tokens
            response = await client.post(
                ALIEXPRESS_TOKEN_URL,
                data=params,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )

            logger.info("AliExpress dropship token exchange status: %s", response.status_code)

            # Try to parse JSON response
            try:
                token_response = response.json()
            except Exception:
                # T6: do NOT include response.text (may contain token material).
                token_error = f"Failed to parse token response (HTTP {response.status_code})"
                logger.error("AliExpress dropship token parse failed (HTTP %s)", response.status_code)
                raise Exception(token_error)

            # Store tokens if successful
            if response.status_code == 200 and "access_token" in token_response:
                # Save to database (survives deployments!)
                from ospra_os.database.aliexpress_tokens import save_token

                success = save_token(
                    api_type="dropship",
                    access_token=token_response["access_token"],
                    refresh_token=token_response.get("refresh_token", ""),
                    expires_in=token_response.get("expires_in", 2592000)
                )

                if success:
                    logger.info("AliExpress Dropshipping tokens saved to database")
                else:
                    token_error = "Failed to save tokens to database"
                    logger.error(token_error)
            else:
                # T6: never echo response.text (contains error detail + possible secrets).
                token_error = f"Token exchange failed (HTTP {response.status_code})"
                logger.error(token_error)

    except Exception as e:
        # T6: no traceback dump to stdout (params/secrets can appear in frames).
        token_error = f"Token exchange error: {str(e)[:200]}"
        logger.error("AliExpress dropship token exchange exception: %s", str(e)[:200])

    # T6: NEUTRAL result pages. Tokens are stored server-side (DB) only — the
    # success page confirms connection without echoing any token, preview,
    # params, or raw response, and the error page shows no code/response body.
    if token_response and "access_token" in token_response:
        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html>
            <head><title>AliExpress Connected</title>
                <style>body{font-family:Arial,sans-serif;max-width:600px;margin:60px auto;padding:20px;text-align:center}
                .card{background:#0d1b2a;color:#fff;padding:40px;border-radius:12px}</style>
            </head>
            <body>
                <div class="card">
                    <h1>&#10003; AliExpress Connected</h1>
                    <p>Your AliExpress Dropshipping account is connected. You can close this window.</p>
                </div>
            </body>
            </html>
            """
        )
    else:
        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html>
            <head><title>AliExpress Connection Failed</title>
                <style>body{font-family:Arial,sans-serif;max-width:600px;margin:60px auto;padding:20px;text-align:center}
                .card{background:#fee;border:2px solid #c00;padding:30px;border-radius:10px}h1{color:#c00}</style>
            </head>
            <body>
                <div class="card">
                    <h1>Connection Failed</h1>
                    <p>We couldn't complete the AliExpress connection. Authorization codes expire
                    within minutes &mdash; please start the connection again from your dashboard.</p>
                </div>
            </body>
            </html>
            """,
            status_code=500
        )
