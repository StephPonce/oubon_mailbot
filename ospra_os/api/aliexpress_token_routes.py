"""
API routes for AliExpress token management
"""
from fastapi import APIRouter, BackgroundTasks, Body
from fastapi.responses import JSONResponse, HTMLResponse
from datetime import datetime
from pydantic import BaseModel
from ospra_os.api.aliexpress_token_refresh import refresh_all_tokens, refresh_dropship_token, refresh_affiliate_token

router = APIRouter(prefix="/api/aliexpress/tokens", tags=["aliexpress-tokens"])


class TokenEntry(BaseModel):
    """Manual token entry model"""
    api_type: str  # "dropship" or "affiliate"
    access_token: str
    refresh_token: str = ""
    expires_in: int = 2592000  # 30 days default


@router.post("/refresh/all")
async def refresh_all_tokens_endpoint(background_tasks: BackgroundTasks):
    """
    Manually trigger token refresh for all AliExpress APIs

    This will check both Dropshipping and Affiliate API tokens,
    and refresh them if they're expiring within 7 days.
    """
    # Run refresh in background
    background_tasks.add_task(refresh_all_tokens)

    return JSONResponse({
        "status": "started",
        "message": "Token refresh task started in background",
        "timestamp": datetime.now().isoformat()
    })


@router.post("/refresh/dropship")
async def refresh_dropship_token_endpoint(background_tasks: BackgroundTasks):
    """
    Manually trigger token refresh for Dropshipping API
    """
    background_tasks.add_task(refresh_dropship_token)

    return JSONResponse({
        "status": "started",
        "message": "Dropshipping API token refresh started",
        "timestamp": datetime.now().isoformat()
    })


@router.post("/refresh/affiliate")
async def refresh_affiliate_token_endpoint(background_tasks: BackgroundTasks):
    """
    Manually trigger token refresh for Affiliate API
    """
    background_tasks.add_task(refresh_affiliate_token)

    return JSONResponse({
        "status": "started",
        "message": "Affiliate API token refresh started",
        "timestamp": datetime.now().isoformat()
    })


@router.get("/status")
async def get_token_status():
    """
    Get status of all AliExpress tokens (from database)

    Returns information about when tokens were obtained,
    when they expire, and whether they need refresh.
    """
    from ospra_os.database.aliexpress_tokens import get_token_status as db_get_status

    # Load status from database (survives deployments!)
    return JSONResponse(db_get_status())


@router.get("/debug/env")
async def debug_environment():
    """DEBUG: Check environment variable configuration"""
    import os

    dropship_secret = os.getenv("ALIEXPRESS_APP_SECRET") or os.getenv("OUBONSHOP_ALIEXPRESS_APP_SECRET", "idjX6tOzHx6urVsSylVzEcHZKwBN4YhN")
    affiliate_secret = os.getenv("ALIEXPRESS_AFFILIATE_APP_SECRET", "9Kkt2Mn5icXLV7fShLfT38OarpjXqtrL")

    return JSONResponse({
        "env_vars": {
            "ALIEXPRESS_APP_SECRET_exists": bool(os.getenv("ALIEXPRESS_APP_SECRET")),
            "OUBONSHOP_ALIEXPRESS_APP_SECRET_exists": bool(os.getenv("OUBONSHOP_ALIEXPRESS_APP_SECRET")),
            "ALIEXPRESS_AFFILIATE_APP_SECRET_exists": bool(os.getenv("ALIEXPRESS_AFFILIATE_APP_SECRET")),
        },
        "computed_secrets": {
            "dropship_secret_preview": dropship_secret[:20] + "..." if dropship_secret else "MISSING",
            "affiliate_secret_preview": affiliate_secret[:20] + "..." if affiliate_secret else "MISSING",
            "dropship_matches_expected": dropship_secret.startswith("idjX6tOzHx6urVsSylVz") if dropship_secret else False,
            "affiliate_matches_expected": affiliate_secret.startswith("9Kkt2Mn5icXLV7fShLfT") if affiliate_secret else False,
        }
    })


@router.get("/manual-entry")
async def show_manual_entry_form():
    """
    Display form for manually entering AliExpress tokens

    Use this if OAuth flow is not working. You can obtain tokens from:
    - AliExpress Developer Console
    - Previous successful authorization (.secrets files)
    """
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html>
    <head>
        <title>AliExpress Manual Token Entry</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 50px auto;
                padding: 20px;
                background: #f5f5f5;
            }
            .container {
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            h1 { color: #333; margin-top: 0; }
            .form-group {
                margin-bottom: 20px;
            }
            label {
                display: block;
                margin-bottom: 5px;
                font-weight: bold;
                color: #555;
            }
            input, select, textarea {
                width: 100%;
                padding: 10px;
                border: 1px solid #ddd;
                border-radius: 5px;
                font-size: 14px;
                box-sizing: border-box;
            }
            textarea {
                font-family: monospace;
                resize: vertical;
                min-height: 80px;
            }
            button {
                background: #4CAF50;
                color: white;
                border: none;
                padding: 12px 30px;
                font-size: 16px;
                cursor: pointer;
                border-radius: 5px;
                font-weight: bold;
            }
            button:hover {
                background: #45a049;
            }
            .info {
                background: #e3f2fd;
                padding: 15px;
                border-radius: 5px;
                margin-bottom: 20px;
                border-left: 4px solid #2196F3;
            }
            .warning {
                background: #fff3cd;
                padding: 15px;
                border-radius: 5px;
                margin-bottom: 20px;
                border-left: 4px solid #ffc107;
            }
            .result {
                margin-top: 20px;
                padding: 15px;
                border-radius: 5px;
                display: none;
            }
            .success {
                background: #d4edda;
                border-left: 4px solid #28a745;
                color: #155724;
            }
            .error {
                background: #f8d7da;
                border-left: 4px solid #dc3545;
                color: #721c24;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔑 Manual Token Entry</h1>

            <div class="warning">
                <strong>⚠️ OAuth Not Working?</strong>
                <p>Use this form if the OAuth flow returns "appkey not exists" error. You can obtain tokens from:</p>
                <ul>
                    <li>AliExpress Developer Console (if tokens are displayed there)</li>
                    <li>Previous successful authorization in .secrets/ files</li>
                    <li>AliExpress API support team</li>
                </ul>
            </div>

            <div class="info">
                <strong>📋 What You Need:</strong>
                <ul>
                    <li><strong>Dropshipping API (520918):</strong> Access token from dropshipping app</li>
                    <li><strong>Affiliate API (522382):</strong> Access token from affiliate app</li>
                </ul>
                <p>Tokens typically last 30 days and can be refreshed automatically.</p>
            </div>

            <form id="tokenForm">
                <div class="form-group">
                    <label for="api_type">API Type</label>
                    <select id="api_type" name="api_type" required>
                        <option value="">-- Select API Type --</option>
                        <option value="dropship">Dropshipping API (520918)</option>
                        <option value="affiliate">Affiliate API (522382)</option>
                    </select>
                </div>

                <div class="form-group">
                    <label for="access_token">Access Token *</label>
                    <textarea id="access_token" name="access_token" required
                              placeholder="Paste your access token here..."></textarea>
                </div>

                <div class="form-group">
                    <label for="refresh_token">Refresh Token (optional)</label>
                    <textarea id="refresh_token" name="refresh_token"
                              placeholder="Paste refresh token if available (optional)"></textarea>
                </div>

                <div class="form-group">
                    <label for="expires_in">Expires In (seconds)</label>
                    <input type="number" id="expires_in" name="expires_in" value="2592000"
                           placeholder="2592000 (30 days)">
                    <small style="color: #666;">Default: 2592000 seconds = 30 days</small>
                </div>

                <button type="submit">💾 Save Token to Database</button>
            </form>

            <div id="result" class="result"></div>
        </div>

        <script>
            document.getElementById('tokenForm').addEventListener('submit', async (e) => {
                e.preventDefault();

                const formData = {
                    api_type: document.getElementById('api_type').value,
                    access_token: document.getElementById('access_token').value.trim(),
                    refresh_token: document.getElementById('refresh_token').value.trim() || "",
                    expires_in: parseInt(document.getElementById('expires_in').value) || 2592000
                };

                const resultDiv = document.getElementById('result');
                resultDiv.style.display = 'block';
                resultDiv.className = 'result';
                resultDiv.innerHTML = 'Saving token...';

                try {
                    const response = await fetch('/api/aliexpress/tokens/manual-entry', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify(formData)
                    });

                    const data = await response.json();

                    if (response.ok) {
                        resultDiv.className = 'result success';
                        resultDiv.innerHTML = `
                            <strong>✅ Success!</strong>
                            <p>${data.message}</p>
                            <p>Token for <strong>${data.api_type}</strong> API saved to database.</p>
                            <p>Token will expire in ${Math.round(data.expires_in / 86400)} days.</p>
                        `;
                        document.getElementById('tokenForm').reset();
                    } else {
                        resultDiv.className = 'result error';
                        resultDiv.innerHTML = `
                            <strong>❌ Error</strong>
                            <p>${data.detail || 'Failed to save token'}</p>
                        `;
                    }
                } catch (error) {
                    resultDiv.className = 'result error';
                    resultDiv.innerHTML = `
                        <strong>❌ Error</strong>
                        <p>Network error: ${error.message}</p>
                    `;
                }
            });
        </script>
    </body>
    </html>
    """)


@router.post("/manual-entry")
async def save_manual_token(token_data: TokenEntry):
    """
    Manually save AliExpress token to database

    Use this endpoint when OAuth flow is not working.
    Tokens can be obtained from AliExpress Developer Console.
    """
    from ospra_os.database.aliexpress_tokens import save_token

    # Validate API type
    if token_data.api_type not in ["dropship", "affiliate"]:
        return JSONResponse(
            status_code=400,
            content={"detail": "api_type must be 'dropship' or 'affiliate'"}
        )

    # Validate access token
    if not token_data.access_token or len(token_data.access_token) < 10:
        return JSONResponse(
            status_code=400,
            content={"detail": "access_token is required and must be valid"}
        )

    # Save to database
    success = save_token(
        api_type=token_data.api_type,
        access_token=token_data.access_token,
        refresh_token=token_data.refresh_token,
        expires_in=token_data.expires_in
    )

    if success:
        return JSONResponse({
            "success": True,
            "message": f"{token_data.api_type.capitalize()} API token saved successfully",
            "api_type": token_data.api_type,
            "expires_in": token_data.expires_in,
            "timestamp": datetime.now().isoformat()
        })
    else:
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to save token to database"}
        )
