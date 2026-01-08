"""
[EMAIL] EMAIL NOTIFIER
Send product change alerts via email using Gmail SMTP
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import List, Dict
import os

logger = logging.getLogger(__name__)


class EmailNotifier:
    """Send email notifications for product changes"""

    def __init__(self):
        """Initialize email notifier with Gmail SMTP"""
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587

        # Get credentials from environment
        self.sender_email = os.getenv("NOTIFICATION_EMAIL")
        self.sender_password = os.getenv("NOTIFICATION_EMAIL_PASSWORD")
        self.recipient_email = os.getenv("ALERT_RECIPIENT_EMAIL")

        # Check if configured
        self.is_configured = all([
            self.sender_email,
            self.sender_password,
            self.recipient_email
        ])

        if not self.is_configured:
            logger.warning("[WARNING]  Email notifications not configured. Set NOTIFICATION_EMAIL, NOTIFICATION_EMAIL_PASSWORD, and ALERT_RECIPIENT_EMAIL in .env")
        else:
            logger.info("[SUCCESS] Email notifier initialized")

    def send_change_alert(self, changes: List[Dict]) -> bool:
        """
        Send email alert for product changes

        Args:
            changes: List of detected changes

        Returns:
            True if email sent successfully, False otherwise
        """
        if not self.is_configured:
            logger.warning("Email not configured, skipping notification")
            return False

        if not changes:
            return False

        try:
            # Create email
            message = MIMEMultipart("alternative")
            message["Subject"] = f" Product Alert: {len(changes)} Changes Detected"
            message["From"] = self.sender_email
            message["To"] = self.recipient_email

            # Create HTML and plain text versions
            text_body = self._format_text_body(changes)
            html_body = self._format_html_body(changes)

            # Attach both versions
            part1 = MIMEText(text_body, "plain")
            part2 = MIMEText(html_body, "html")

            message.attach(part1)
            message.attach(part2)

            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(message)

            logger.info(f"[SUCCESS] Email sent to {self.recipient_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    def _format_text_body(self, changes: List[Dict]) -> str:
        """Format plain text email body"""

        # Group by severity
        high = [c for c in changes if c.get('severity') == 'high']
        medium = [c for c in changes if c.get('severity') == 'medium']
        low = [c for c in changes if c.get('severity') == 'low']

        body = f"""
Product Change Alert


Detected {len(changes)} product changes at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

"""

        if high:
            body += f"\n HIGH PRIORITY ({len(high)}):\n"
            for change in high:
                body += f"\n• {change['product_name']}\n"
                body += f"  {change['message']}\n"

        if medium:
            body += f"\n MEDIUM PRIORITY ({len(medium)}):\n"
            for change in medium[:5]:
                body += f"• {change['product_name']}: {change['message']}\n"
            if len(medium) > 5:
                body += f"  ... and {len(medium) - 5} more\n"

        if low:
            body += f"\n LOW PRIORITY ({len(low)}):\n"
            for change in low[:3]:
                body += f"• {change['product_name']}: {change['message']}\n"
            if len(low) > 3:
                body += f"  ... and {len(low) - 3} more\n"

        body += "\n\n"
        body += "View your dashboard for full details.\n"

        return body

    def _format_html_body(self, changes: List[Dict]) -> str:
        """Format HTML email body"""

        # Group by severity
        high = [c for c in changes if c.get('severity') == 'high']
        medium = [c for c in changes if c.get('severity') == 'medium']
        low = [c for c in changes if c.get('severity') == 'low']

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
        }}
        .header h1 {{
            margin: 0;
            font-size: 24px;
        }}
        .timestamp {{
            font-size: 14px;
            opacity: 0.9;
            margin-top: 5px;
        }}
        .section {{
            background: #f8f9fa;
            border-left: 4px solid #667eea;
            padding: 15px;
            margin-bottom: 15px;
            border-radius: 4px;
        }}
        .high {{
            border-left-color: #dc3545;
        }}
        .medium {{
            border-left-color: #ffc107;
        }}
        .low {{
            border-left-color: #28a745;
        }}
        .change-item {{
            padding: 10px 0;
            border-bottom: 1px solid #e9ecef;
        }}
        .change-item:last-child {{
            border-bottom: none;
        }}
        .product-name {{
            font-weight: bold;
            color: #2c3e50;
        }}
        .change-message {{
            color: #555;
            font-size: 14px;
            margin-top: 4px;
        }}
        .footer {{
            text-align: center;
            padding: 20px;
            color: #666;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1> Product Change Alert</h1>
        <div class="timestamp">{len(changes)} changes detected at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
    </div>
"""

        if high:
            html += f"""
    <div class="section high">
        <h2 style="margin-top:0;"> HIGH PRIORITY ({len(high)})</h2>
"""
            for change in high:
                html += f"""
        <div class="change-item">
            <div class="product-name">{change['product_name']}</div>
            <div class="change-message">{change['message']}</div>
        </div>
"""
            html += "    </div>\n"

        if medium:
            html += f"""
    <div class="section medium">
        <h2 style="margin-top:0;"> MEDIUM PRIORITY ({len(medium)})</h2>
"""
            for change in medium[:5]:
                html += f"""
        <div class="change-item">
            <div class="product-name">{change['product_name']}</div>
            <div class="change-message">{change['message']}</div>
        </div>
"""
            if len(medium) > 5:
                html += f"        <div style='text-align:center; padding:10px; color:#666;'>... and {len(medium) - 5} more</div>\n"
            html += "    </div>\n"

        if low:
            html += f"""
    <div class="section low">
        <h2 style="margin-top:0;"> LOW PRIORITY ({len(low)})</h2>
"""
            for change in low[:3]:
                html += f"""
        <div class="change-item">
            <div class="product-name">{change['product_name']}</div>
            <div class="change-message">{change['message']}</div>
        </div>
"""
            if len(low) > 3:
                html += f"        <div style='text-align:center; padding:10px; color:#666;'>... and {len(low) - 3} more</div>\n"
            html += "    </div>\n"

        html += """
    <div class="footer">
        View your dashboard for full details and AI-powered insights.
    </div>
</body>
</html>
"""
        return html

    def send_test_email(self) -> bool:
        """Send a test email to verify configuration"""
        if not self.is_configured:
            logger.error("Email not configured")
            return False

        test_changes = [{
            'product_name': 'Test Product',
            'message': '[TREND] Test notification',
            'severity': 'high'
        }]

        return self.send_change_alert(test_changes)
