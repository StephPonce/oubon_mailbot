"""
AliExpress OAuth callback handler
"""
import json
import httpx
import time
import hashlib
import hmac
import os
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/api/aliexpress", tags=["aliexpress"])

# AliExpress Dropshipping API credentials (from .env)
# Dropshipping: 520918 / idjX6tOzHx6urVsSylVzEcHZKwBN4YhN
# Affiliate: 522382 / 9Kkt2Mn5icXLV7fShLfT38OarpjXqtrL
ALIEXPRESS_APP_KEY = os.getenv("ALIEXPRESS_APP_KEY", "520918")
ALIEXPRESS_APP_SECRET = os.getenv("ALIEXPRESS_APP_SECRET", "idjX6tOzHx6urVsSylVzEcHZKwBN4YhN")
# CORRECT OAuth 2.0 endpoint for OVERSEAS (api-sg = Singapore gateway)
# AliExpress uses REST API structure for token exchange
ALIEXPRESS_TOKEN_URL = "https://api-sg.aliexpress.com/rest/auth/token/create"
ALIEXPRESS_REDIRECT_URI = "https://oubon-mailbot.onrender.com/api/aliexpress/callback"

# Token storage path
TOKENS_FILE = Path(".secrets/aliexpress_tokens.json")


def generate_aliexpress_signature_md5(params: dict, app_secret: str, api_path: str = "/auth/token/create") -> str:
    """
    Generate AliExpress API signature using HMAC-MD5

    Algorithm:
    1. Sort parameters alphabetically by key (exclude 'sign')
    2. Concatenate as: /api/pathkey1value1key2value2...
    3. Use HMAC-MD5 with app_secret as key
    4. Convert to uppercase hexadecimal
    """
    # Sort parameters alphabetically (exclude 'sign' if present)
    sorted_params = sorted([(k, v) for k, v in params.items() if k != 'sign'])

    # Concatenate as: /api/path + key1value1key2value2...
    concat_str = api_path + ''.join([f"{k}{v}" for k, v in sorted_params])

    # Calculate HMAC-MD5 signature
    signature = hmac.new(
        app_secret.encode('utf-8'),
        concat_str.encode('utf-8'),
        hashlib.md5
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
                    <h1>❌ Authorization Failed</h1>
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
                    <h1>❌ Missing Authorization Code</h1>
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
            # AliExpress REST API requires system parameters + signature
            timestamp = str(int(time.time() * 1000))  # Milliseconds

            # System parameters (required for ALL AliExpress API calls)
            params = {
                "app_key": ALIEXPRESS_APP_KEY,
                "timestamp": timestamp,
                "sign_method": "md5",
                "format": "json",
                "v": "2.0",
                "method": "auth.token.create",  # The API method we're calling
                # API-specific parameter:
                "code": code  # The authorization code
            }

            # Generate signature (AliExpress uses MD5 signature)
            signature = generate_aliexpress_signature_md5(params, ALIEXPRESS_APP_SECRET)
            params["sign"] = signature

            # Exchange code for tokens using AliExpress REST API
            # Note: AliExpress uses POST with form-urlencoded, not JSON
            response = await client.post(
                ALIEXPRESS_TOKEN_URL,
                data=params,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )

            # Log response details for debugging
            print(f"📡 Token Exchange Response:")
            print(f"   Status Code: {response.status_code}")
            print(f"   Headers: {dict(response.headers)}")
            print(f"   Raw Body: {response.text[:500]}")

            # Try to parse JSON response
            try:
                token_response = response.json()
            except Exception as json_error:
                token_error = f"Failed to parse JSON response. Status: {response.status_code}, Body: {response.text}"
                print(f"❌ {token_error}")
                raise Exception(token_error)

            # Store tokens if successful
            if response.status_code == 200 and "access_token" in token_response:
                # Ensure .secrets directory exists
                TOKENS_FILE.parent.mkdir(parents=True, exist_ok=True)

                # Add timestamp
                token_response["obtained_at"] = datetime.now().isoformat()

                # Save to file
                with open(TOKENS_FILE, "w") as f:
                    json.dump(token_response, f, indent=2)

                print(f"✅ AliExpress tokens saved to {TOKENS_FILE}")
            else:
                token_error = f"Token exchange failed: {response.status_code} - {response.text}"
                print(f"❌ {token_error}")

    except Exception as e:
        import traceback
        token_error = f"Exception during token exchange: {str(e)}\n\nFull traceback:\n{traceback.format_exc()}"
        print(f"❌ {token_error}")

    # Display result to user
    if token_response and "access_token" in token_response:
        # Success - show tokens
        token_json = json.dumps(token_response, indent=2)
        return HTMLResponse(
            content=f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>AliExpress OAuth - Success</title>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        max-width: 1000px;
                        margin: 50px auto;
                        padding: 20px;
                        background: #f5f5f5;
                    }}
                    .success {{
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                        padding: 30px;
                        border-radius: 10px;
                        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                    }}
                    h1 {{ margin-top: 0; }}
                    .token-box {{
                        background: #263238;
                        color: #aed581;
                        padding: 20px;
                        margin: 20px 0;
                        font-family: monospace;
                        font-size: 13px;
                        border-radius: 5px;
                        overflow-x: auto;
                        white-space: pre-wrap;
                        word-break: break-all;
                    }}
                    .info {{
                        background: rgba(255,255,255,0.2);
                        padding: 15px;
                        border-radius: 5px;
                        margin: 20px 0;
                    }}
                    button {{
                        background: #4CAF50;
                        color: white;
                        border: none;
                        padding: 12px 24px;
                        font-size: 16px;
                        cursor: pointer;
                        border-radius: 5px;
                        margin: 10px 5px 10px 0;
                        font-weight: bold;
                    }}
                    button:hover {{
                        background: #45a049;
                    }}
                    .highlight {{
                        background: rgba(255,255,255,0.3);
                        padding: 2px 6px;
                        border-radius: 3px;
                        font-family: monospace;
                    }}
                </style>
            </head>
            <body>
                <div class="success">
                    <h1>🎉 OAuth Successful!</h1>

                    <div class="info">
                        <p><strong>✅ Tokens obtained and stored successfully!</strong></p>
                        <p>📁 Saved to: <span class="highlight">.secrets/aliexpress_tokens.json</span></p>
                        <p>🔑 Access Token: <span class="highlight">{token_response.get('access_token', '')[:20]}...</span></p>
                        <p>🔄 Refresh Token: <span class="highlight">{token_response.get('refresh_token', '')[:20] if token_response.get('refresh_token') else 'N/A'}...</span></p>
                        <p>⏱️ Expires In: <span class="highlight">{token_response.get('expires_in', 'N/A')} seconds</span></p>
                    </div>

                    <h3>📄 Full Token Response:</h3>
                    <div class="token-box" id="tokens">{token_json}</div>

                    <button onclick="copyTokens()">📋 Copy Full Response</button>
                    <button onclick="window.close()">✅ Done - Close Window</button>

                    <div class="info">
                        <p>🚀 <strong>Next Steps:</strong></p>
                        <ul>
                            <li>Tokens are automatically available for API calls</li>
                            <li>Check <span class="highlight">.secrets/aliexpress_tokens.json</span> for the full response</li>
                            <li>Use the access token in your AliExpress API requests</li>
                        </ul>
                    </div>
                </div>

                <script>
                    function copyTokens() {{
                        const tokens = document.getElementById('tokens').textContent;
                        navigator.clipboard.writeText(tokens.trim()).then(() => {{
                            alert('✅ Token response copied to clipboard!');
                        }});
                    }}
                </script>
            </body>
            </html>
            """
        )
    else:
        # Failed to get tokens
        error_msg = token_error or "Unknown error"
        return HTMLResponse(
            content=f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>AliExpress OAuth - Token Exchange Failed</title>
                <style>
                    body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }}
                    .error {{ background: #fee; border: 2px solid #c00; padding: 20px; border-radius: 5px; }}
                    h1 {{ color: #c00; }}
                    .code-box {{ background: #f9f9f9; padding: 10px; font-family: monospace; margin: 10px 0; }}
                </style>
            </head>
            <body>
                <div class="error">
                    <h1>❌ Token Exchange Failed</h1>
                    <p><strong>Error:</strong> {error_msg}</p>
                    <p><strong>Authorization Code:</strong></p>
                    <div class="code-box">{code}</div>
                    {f'<p><strong>Response:</strong></p><div class="code-box">{json.dumps(token_response, indent=2)}</div>' if token_response else ''}
                    <p>The authorization code may have expired (codes expire in minutes). Please try authorizing again.</p>
                </div>
            </body>
            </html>
            """,
            status_code=500
        )
