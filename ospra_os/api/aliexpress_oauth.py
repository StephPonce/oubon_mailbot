"""
AliExpress OAuth callback handler
"""
from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/api/aliexpress", tags=["aliexpress"])


@router.get("/oauth-callback")
async def oauth_callback(
    code: str = Query(None, description="Authorization code from AliExpress"),
    state: str = Query(None, description="State parameter"),
    error: str = Query(None, description="Error if authorization failed")
):
    """
    OAuth callback endpoint for AliExpress

    This receives the authorization code from AliExpress after user authorization.
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

    # Success - show the code to the user
    return HTMLResponse(
        content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>AliExpress OAuth - Success</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    max-width: 900px;
                    margin: 50px auto;
                    padding: 20px;
                    background: #f5f5f5;
                }}
                .success {{
                    background: #efe;
                    border: 2px solid #0a0;
                    padding: 30px;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                h1 {{ color: #0a0; margin-top: 0; }}
                .code-box {{
                    background: #fff;
                    border: 1px solid #ddd;
                    padding: 15px;
                    margin: 20px 0;
                    font-family: monospace;
                    font-size: 14px;
                    word-break: break-all;
                    border-radius: 5px;
                }}
                .instructions {{
                    background: #e3f2fd;
                    border-left: 4px solid #2196F3;
                    padding: 15px;
                    margin: 20px 0;
                }}
                .command {{
                    background: #263238;
                    color: #aed581;
                    padding: 15px;
                    margin: 10px 0;
                    font-family: monospace;
                    border-radius: 5px;
                    overflow-x: auto;
                }}
                button {{
                    background: #4CAF50;
                    color: white;
                    border: none;
                    padding: 10px 20px;
                    font-size: 16px;
                    cursor: pointer;
                    border-radius: 5px;
                    margin: 10px 5px 10px 0;
                }}
                button:hover {{
                    background: #45a049;
                }}
            </style>
        </head>
        <body>
            <div class="success">
                <h1>✅ Authorization Successful!</h1>

                <p>AliExpress has authorized your application. Here's your authorization code:</p>

                <div class="code-box" id="code">
                    {code}
                </div>

                <button onclick="copyCode()">📋 Copy Code</button>

                <div class="instructions">
                    <h3>📋 Next Steps:</h3>
                    <ol>
                        <li>Copy the authorization code above</li>
                        <li>Open your terminal</li>
                        <li>Run this command:</li>
                    </ol>

                    <div class="command">
                        cd "/Users/stephenponce/Documents/Ospra OS/Bots/Ospra OS"<br>
                        uv run python scripts/aliexpress_oauth_helper.py {code}
                    </div>

                    <p><strong>Or manually:</strong></p>
                    <div class="command">
                        python scripts/aliexpress_oauth_helper.py YOUR_CODE_HERE
                    </div>
                </div>

                <p><small>State: {state}</small></p>
            </div>

            <script>
                function copyCode() {{
                    const code = document.getElementById('code').textContent;
                    navigator.clipboard.writeText(code.trim()).then(() => {{
                        alert('✅ Code copied to clipboard!');
                    }});
                }}
            </script>
        </body>
        </html>
        """
    )
