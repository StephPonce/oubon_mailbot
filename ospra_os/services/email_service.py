"""
Email Service using Resend
Handles password reset and other transactional emails

FIXED: Environment variables are now loaded at RUNTIME, not import time.
This ensures .env is properly loaded before reading EMAIL_FROM_ADDRESS.
"""
import os
from typing import Optional
from dotenv import load_dotenv

# Force load .env at import (belt and suspenders)
load_dotenv()

import resend


def _get_email_config():
    """
    Get email configuration at RUNTIME.
    
    This ensures environment variables are read after .env is loaded,
    not at module import time when they might not be available yet.
    """
    # Re-load to be safe
    load_dotenv()
    
    api_key = os.getenv("RESEND_API_KEY")
    from_address = os.getenv("EMAIL_FROM_ADDRESS", "noreply@ospra.io")
    from_name = os.getenv("EMAIL_FROM_NAME", "Ospra Intelligence")
    app_url = os.getenv("APP_URL", "http://localhost:5173")
    
    # Debug logging
    print(f"[EMAIL] Email Config: from={from_address}, app_url={app_url}")
    
    return {
        "api_key": api_key,
        "from_address": from_address,
        "from_name": from_name,
        "app_url": app_url,
    }


async def send_password_reset_email(
    to_email: str,
    reset_token: str,
    user_name: Optional[str] = None
) -> dict:
    """
    Send password reset email with reset link

    Args:
        to_email: Recipient email address
        reset_token: Password reset token
        user_name: Optional user name for personalization

    Returns:
        dict with success status and message/error
    """
    try:
        # Get config at RUNTIME
        config = _get_email_config()
        resend.api_key = config["api_key"]
        
        # Build reset URL
        reset_url = f"{config['app_url']}/reset-password?token={reset_token}"
        
        # Format from address with name
        from_address = f"{config['from_name']} <{config['from_address']}>"

        # Email content
        greeting = f"Hi {user_name}," if user_name else "Hi,"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9fafb; padding: 30px; border-radius: 0 0 10px 10px; }}
                .button {{ display: inline-block; padding: 12px 30px; background: #667eea; color: white; text-decoration: none; border-radius: 6px; margin: 20px 0; }}
                .footer {{ text-align: center; margin-top: 30px; font-size: 12px; color: #6b7280; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Password Reset Request</h1>
                </div>
                <div class="content">
                    <p>{greeting}</p>
                    <p>We received a request to reset your password for your Ospra Intelligence account.</p>
                    <p>Click the button below to reset your password:</p>
                    <p style="text-align: center;">
                        <a href="{reset_url}" class="button">Reset Password</a>
                    </p>
                    <p>Or copy and paste this link into your browser:</p>
                    <p style="word-break: break-all; color: #6b7280; font-size: 14px;">{reset_url}</p>
                    <p><strong>This link will expire in 1 hour.</strong></p>
                    <p>If you didn't request this password reset, you can safely ignore this email.</p>
                </div>
                <div class="footer">
                    <p>© 2025 Ospra Intelligence. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        # Send via Resend
        params = {
            "from": from_address,
            "to": [to_email],
            "subject": "Reset Your Password - Ospra Intelligence",
            "html": html_content
        }
        
        print(f"[EMAIL] Sending password reset email to {to_email} from {from_address}")

        email_response = resend.Emails.send(params)
        
        print(f"[SUCCESS] Password reset email sent: {email_response}")

        return {
            "success": True,
            "message": "Password reset email sent successfully",
            "email_id": email_response.get("id") if isinstance(email_response, dict) else str(email_response)
        }

    except Exception as e:
        print(f"[ERROR] Failed to send password reset email: {e}")
        return {
            "success": False,
            "error": f"Failed to send email: {str(e)}"
        }


async def send_welcome_email(
    to_email: str,
    user_name: str
) -> dict:
    """
    Send welcome email to new users

    Args:
        to_email: Recipient email address
        user_name: User's name

    Returns:
        dict with success status and message/error
    """
    try:
        # Get config at RUNTIME
        config = _get_email_config()
        resend.api_key = config["api_key"]
        
        # Format from address with name
        from_address = f"{config['from_name']} <{config['from_address']}>"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9fafb; padding: 30px; border-radius: 0 0 10px 10px; }}
                .button {{ display: inline-block; padding: 12px 30px; background: #667eea; color: white; text-decoration: none; border-radius: 6px; margin: 20px 0; }}
                .feature {{ background: white; padding: 15px; border-radius: 8px; margin: 10px 0; border-left: 4px solid #667eea; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1> Welcome to Ospra Intelligence!</h1>
                </div>
                <div class="content">
                    <p>Hi {user_name},</p>
                    <p>Welcome to <strong>Ospra Intelligence</strong> - your AI-powered e-commerce automation platform!</p>
                    
                    <div class="feature">
                        <strong>[SEARCH] Product Discovery</strong><br>
                        AI-powered product recommendations based on real-time market data
                    </div>
                    
                    <div class="feature">
                        <strong>[START] One-Click Deploy</strong><br>
                        Deploy products to Shopify instantly with AI-generated content
                    </div>
                    
                    <div class="feature">
                        <strong>[STATS] Smart Analytics</strong><br>
                        Track trends, sales, and market opportunities in real-time
                    </div>
                    
                    <p style="text-align: center; margin-top: 30px;">
                        <a href="{config['app_url']}" class="button">Go to Dashboard →</a>
                    </p>
                    <p style="color: #6b7280; font-size: 14px;">If you have any questions, just reply to this email. We're here to help!</p>
                </div>
            </div>
        </body>
        </html>
        """

        params = {
            "from": from_address,
            "to": [to_email],
            "subject": " Welcome to Ospra Intelligence!",
            "html": html_content
        }

        print(f"[EMAIL] Sending welcome email to {to_email} from {from_address}")
        
        email_response = resend.Emails.send(params)

        print(f"[SUCCESS] Welcome email sent: {email_response}")

        return {
            "success": True,
            "message": "Welcome email sent successfully",
            "email_id": email_response.get("id") if isinstance(email_response, dict) else str(email_response)
        }

    except Exception as e:
        print(f"[ERROR] Failed to send welcome email: {e}")
        return {
            "success": False,
            "error": f"Failed to send email: {str(e)}"
        }
