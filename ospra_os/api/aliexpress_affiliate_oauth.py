"""
AliExpress Affiliate API OAuth callback handler
Separate from Dropshipping API - uses different callback URL
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

router = APIRouter(prefix="/api/aliexpress-affiliate", tags=["aliexpress-affiliate"])

# AliExpress Affiliate API credentials (from .env)
ALIEXPRESS_AFFILIATE_APP_KEY = os.getenv("ALIEXPRESS_AFFILIATE_APP_KEY", "522382")
ALIEXPRESS_AFFILIATE_APP_SECRET = os.getenv("ALIEXPRESS_AFFILIATE_APP_SECRET", "9Kkt2Mn5icXLV7fShLfT38OarpjXqtrL")
# OAuth 2.0 token endpoint - uses standard OAuth format (NO signature needed!)
# This is SEPARATE from the API endpoints which require signatures
ALIEXPRESS_TOKEN_URL = "https://oauth.aliexpress.com/token"
ALIEXPRESS_AFFILIATE_REDIRECT_URI = "https://oubon-mailbot.onrender.com/api/aliexpress-affiliate/callback"

# Token storage path
TOKENS_FILE = Path(".secrets/aliexpress_affiliate_tokens.json")


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


@router.get("/oauth-callback")
@router.get("/callback")  # Support both routes
async def affiliate_oauth_callback(
    code: str = Query(None, description="Authorization code from AliExpress"),
    state: str = Query(None, description="State parameter"),
    error: str = Query(None, description="Error if authorization failed")
):
    """
    OAuth callback endpoint for AliExpress Affiliate API

    Callback URL: https://ospra-intelligence.com/api/aliexpress/callback
    App Key: 522382
    """

    if error:
        return HTMLResponse(
            content=f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>AliExpress Affiliate OAuth - Error</title>
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
                    <p>Please try again or check your AliExpress Affiliate app configuration.</p>
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
                <title>AliExpress Affiliate OAuth - Missing Code</title>
                <style>
                    body { font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
                    .error { background: #fee; border: 2px solid #c00; padding: 20px; border-radius: 5px; }
                    h1 { color: #c00; }
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
            # Standard OAuth 2.0 token exchange - NO signature required!
            # AliExpress OAuth endpoint uses standard OAuth 2.0 format
            params = {
                "client_id": ALIEXPRESS_AFFILIATE_APP_KEY,
                "client_secret": ALIEXPRESS_AFFILIATE_APP_SECRET,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": ALIEXPRESS_AFFILIATE_REDIRECT_URI,
                "sp": "ae"  # AliExpress account type
            }

            # Exchange code for tokens using standard OAuth 2.0
            response = await client.post(
                ALIEXPRESS_TOKEN_URL,
                data=params,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )

            # Log response details for debugging
            print(f"📡 Token Exchange Response (Affiliate):")
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
                token_response["app_key"] = ALIEXPRESS_AFFILIATE_APP_KEY

                # Save to file
                with open(TOKENS_FILE, "w") as f:
                    json.dump(token_response, f, indent=2)

                print(f"✅ AliExpress Affiliate API tokens saved to {TOKENS_FILE}")

                # Also update .env file with new token
                access_token = token_response.get("access_token")
                print(f"✅ Access Token: {access_token[:20]}...")
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
        access_token = token_response.get("access_token", "")
        return HTMLResponse(
            content=f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>AliExpress Affiliate OAuth - Success</title>
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
                    .env-update {{
                        background: #fff3cd;
                        color: #856404;
                        padding: 15px;
                        border-radius: 5px;
                        margin: 20px 0;
                        border: 2px solid #ffc107;
                    }}
                </style>
            </head>
            <body>
                <div class="success">
                    <h1>🎉 Affiliate OAuth Successful!</h1>

                    <div class="info">
                        <p><strong>✅ Tokens obtained and stored successfully!</strong></p>
                        <p>📁 Saved to: <span class="highlight">.secrets/aliexpress_affiliate_tokens.json</span></p>
                        <p>🔑 App Key: <span class="highlight">{ALIEXPRESS_AFFILIATE_APP_KEY}</span></p>
                        <p>🔑 Access Token: <span class="highlight">{access_token[:20]}...</span></p>
                        <p>🔄 Refresh Token: <span class="highlight">{token_response.get('refresh_token', 'N/A')[:20] if token_response.get('refresh_token') else 'N/A'}...</span></p>
                        <p>⏱️ Expires In: <span class="highlight">{token_response.get('expires_in', 'N/A')} seconds</span></p>
                    </div>

                    <div class="env-update">
                        <p><strong>⚠️ UPDATE YOUR .env FILE:</strong></p>
                        <p>Replace the old ALIEXPRESS_ACCESS_TOKEN with:</p>
                        <code style="display:block; background:#fff; color:#000; padding:10px; margin-top:10px; border-radius:3px;">
                        ALIEXPRESS_ACCESS_TOKEN={access_token}
                        </code>
                    </div>

                    <h3>📄 Full Token Response:</h3>
                    <div class="token-box" id="tokens">{token_json}</div>

                    <button onclick="copyTokens()">📋 Copy Full Response</button>
                    <button onclick="copyAccessToken()">🔑 Copy Access Token</button>
                    <button onclick="window.close()">✅ Done - Close Window</button>

                    <div class="info">
                        <p>🚀 <strong>Next Steps:</strong></p>
                        <ul>
                            <li>Update ALIEXPRESS_ACCESS_TOKEN in your .env file</li>
                            <li>Test with: python3 /tmp/test_affiliate_api.py</li>
                            <li>Fetch 50 products and verify it works!</li>
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
                    function copyAccessToken() {{
                        navigator.clipboard.writeText('{access_token}').then(() => {{
                            alert('✅ Access token copied to clipboard!');
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
                <title>AliExpress Affiliate OAuth - Token Exchange Failed</title>
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
