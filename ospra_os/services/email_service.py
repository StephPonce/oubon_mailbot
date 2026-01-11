"""
EMAIL SERVICE - RESEND INTEGRATION
==================================

Send transactional emails using Resend API.

Setup:
1. Get API key from resend.com
2. Set RESEND_API_KEY environment variable
3. Verify your domain in Resend dashboard

Author: OspraOS
Date: January 2026
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Try to import resend, handle if not installed
try:
    import resend
    RESEND_AVAILABLE = True
except ImportError:
    RESEND_AVAILABLE = False
    logger.warning("Resend not installed. Run: pip install resend")


def init_resend():
    """Initialize Resend with API key."""
    api_key = os.getenv("RESEND_API_KEY")
    if api_key and RESEND_AVAILABLE:
        resend.api_key = api_key
        return True
    return False


def send_email(
    to: str,
    subject: str,
    html: str,
    from_email: Optional[str] = None,
    text: Optional[str] = None
) -> dict:
    """
    Send an email via Resend.
    
    Args:
        to: Recipient email address
        subject: Email subject
        html: HTML content
        from_email: Sender email (defaults to RESEND_FROM_EMAIL env var)
        text: Plain text fallback
        
    Returns:
        dict with 'success' and 'id' or 'error'
    """
    if not RESEND_AVAILABLE:
        logger.error("Resend not available - pip install resend")
        return {"success": False, "error": "Resend not installed"}
    
    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        logger.error("RESEND_API_KEY not set")
        return {"success": False, "error": "RESEND_API_KEY not configured"}
    
    # Initialize resend
    resend.api_key = api_key
    
    # Default from email
    sender = from_email or os.getenv("RESEND_FROM_EMAIL", "noreply@ospra.io")
    
    try:
        params = {
            "from": sender,
            "to": [to],
            "subject": subject,
            "html": html,
        }
        
        if text:
            params["text"] = text
            
        result = resend.Emails.send(params)
        
        logger.info(f"Email sent to {to}: {subject}")
        return {"success": True, "id": result.get("id")}
        
    except Exception as e:
        logger.error(f"Failed to send email to {to}: {e}")
        return {"success": False, "error": str(e)}


def send_password_reset_email(to: str, reset_link: str, user_name: Optional[str] = None) -> dict:
    """
    Send password reset email.
    
    Args:
        to: User's email address
        reset_link: Full URL with reset token
        user_name: Optional user's name for personalization
    """
    name = user_name or to.split("@")[0]
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #0f172a;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #0f172a; padding: 40px 20px;">
            <tr>
                <td align="center">
                    <table width="100%" max-width="600" cellpadding="0" cellspacing="0" style="max-width: 600px; background: linear-gradient(135deg, rgba(139, 92, 246, 0.1), rgba(6, 182, 212, 0.1)); border-radius: 24px; border: 1px solid rgba(255, 255, 255, 0.1); overflow: hidden;">
                        <!-- Header -->
                        <tr>
                            <td style="padding: 40px 40px 20px; text-align: center;">
                                <div style="display: inline-block; width: 60px; height: 60px; background: linear-gradient(135deg, #8b5cf6, #06b6d4); border-radius: 16px; line-height: 60px; font-size: 28px;">⚡</div>
                                <h1 style="color: #ffffff; font-size: 24px; margin: 20px 0 0; font-weight: 600;">Reset Your Password</h1>
                            </td>
                        </tr>
                        
                        <!-- Content -->
                        <tr>
                            <td style="padding: 20px 40px;">
                                <p style="color: rgba(255, 255, 255, 0.7); font-size: 16px; line-height: 1.6; margin: 0 0 20px;">
                                    Hi {name},
                                </p>
                                <p style="color: rgba(255, 255, 255, 0.7); font-size: 16px; line-height: 1.6; margin: 0 0 30px;">
                                    We received a request to reset your password for your Ospra Intelligence account. Click the button below to create a new password.
                                </p>
                                
                                <!-- CTA Button -->
                                <table width="100%" cellpadding="0" cellspacing="0">
                                    <tr>
                                        <td align="center" style="padding: 10px 0 30px;">
                                            <a href="{reset_link}" style="display: inline-block; padding: 16px 40px; background: linear-gradient(135deg, #8b5cf6, #06b6d4); color: #ffffff; text-decoration: none; font-weight: 600; font-size: 16px; border-radius: 12px;">
                                                Reset Password
                                            </a>
                                        </td>
                                    </tr>
                                </table>
                                
                                <p style="color: rgba(255, 255, 255, 0.5); font-size: 14px; line-height: 1.6; margin: 0 0 10px;">
                                    This link will expire in <strong style="color: rgba(255, 255, 255, 0.7);">1 hour</strong>.
                                </p>
                                <p style="color: rgba(255, 255, 255, 0.5); font-size: 14px; line-height: 1.6; margin: 0;">
                                    If you didn't request this password reset, you can safely ignore this email.
                                </p>
                            </td>
                        </tr>
                        
                        <!-- Footer -->
                        <tr>
                            <td style="padding: 30px 40px; border-top: 1px solid rgba(255, 255, 255, 0.1);">
                                <p style="color: rgba(255, 255, 255, 0.4); font-size: 12px; line-height: 1.5; margin: 0; text-align: center;">
                                    Ospra Intelligence • AI-Powered E-Commerce Automation<br>
                                    <a href="https://ospra.io" style="color: #8b5cf6; text-decoration: none;">ospra.io</a>
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    
    text = f"""
    Hi {name},
    
    We received a request to reset your password for your Ospra Intelligence account.
    
    Click here to reset your password: {reset_link}
    
    This link will expire in 1 hour.
    
    If you didn't request this password reset, you can safely ignore this email.
    
    - Ospra Intelligence Team
    """
    
    return send_email(
        to=to,
        subject="Reset Your Ospra Intelligence Password",
        html=html,
        text=text
    )
