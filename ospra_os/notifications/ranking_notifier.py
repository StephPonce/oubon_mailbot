"""
Ranking Notification System

Sends email notifications when products enter Top 10 rankings.

Author: OspraOS
Date: November 2025
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime, timezone
import os

logger = logging.getLogger(__name__)


class RankingNotifier:
    """
    Send notifications for ranking milestones.
    """

    def __init__(self, smtp_config: Optional[Dict] = None):
        """
        Initialize ranking notifier.

        Args:
            smtp_config: SMTP configuration for email sending
                {
                    'host': 'smtp.gmail.com',
                    'port': 587,
                    'username': 'user@gmail.com',
                    'password': 'app_password',
                    'from_email': 'notifications@example.com'
                }
        """
        self.smtp_config = smtp_config or self._load_smtp_config()
        logger.info("RankingNotifier initialized")

    def _load_smtp_config(self) -> Dict:
        """Load SMTP configuration from environment variables."""
        return {
            'host': os.getenv('SMTP_HOST', 'smtp.gmail.com'),
            'port': int(os.getenv('SMTP_PORT', '587')),
            'username': os.getenv('SMTP_USERNAME', ''),
            'password': os.getenv('SMTP_PASSWORD', ''),
            'from_email': os.getenv('NOTIFICATION_FROM_EMAIL', 'rankings@ospraos.com')
        }

    def notify_top_10_entry(
        self,
        product: Dict,
        previous_rank: Optional[int],
        to_emails: List[str]
    ):
        """
        Send notification when a product enters Top 10.

        Args:
            product: Product data including rank, name, score
            previous_rank: Previous rank (None if new to top 20)
            to_emails: List of recipient email addresses
        """
        try:
            # Check if email is configured
            if not self.smtp_config.get('username') or not self.smtp_config.get('password'):
                logger.warning("SMTP not configured, skipping email notification")
                return

            rank = product.get('rank')
            product_name = product.get('product_name', f"Product #{product.get('product_id')}")
            composite_score = product.get('composite_score', 0)

            # Create email subject
            subject = f"[TOP] {product_name} entered Top 10 at rank #{rank}!"

            # Create email body
            body = self._create_email_body(product, previous_rank)

            # Send email
            self._send_email(
                to_emails=to_emails,
                subject=subject,
                body=body
            )

            logger.info(f"Sent Top 10 notification for product {product.get('product_id')} to {len(to_emails)} recipients")

        except Exception as e:
            logger.error(f"Failed to send Top 10 notification: {e}")

    def notify_elite_entry(
        self,
        product: Dict,
        to_emails: List[str]
    ):
        """
        Send notification when a product enters ELITE tier (Top 3).

        Args:
            product: Product data
            to_emails: List of recipient email addresses
        """
        try:
            if not self.smtp_config.get('username') or not self.smtp_config.get('password'):
                logger.warning("SMTP not configured, skipping email notification")
                return

            rank = product.get('rank')
            product_name = product.get('product_name', f"Product #{product.get('product_id')}")

            # Emoji for each elite rank
            rank_emoji = {1: '[FIRST]', 2: '[SECOND]', 3: '[THIRD]'}

            subject = f"{rank_emoji.get(rank, '[TOP]')} ELITE: {product_name} reached #{rank}!"

            body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .header {{ background: linear-gradient(135deg, #FFD700 0%, #FFA500 100%); color: white; padding: 30px; text-align: center; }}
        .content {{ padding: 30px; background: #f9fafb; }}
        .stat-box {{ background: white; border-left: 4px solid #FFD700; padding: 15px; margin: 10px 0; border-radius: 8px; }}
        .footer {{ padding: 20px; text-align: center; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{rank_emoji.get(rank, '[TOP]')} ELITE TIER ACHIEVEMENT</h1>
        <p style="font-size: 18px;">Product has entered the elite top 3 rankings!</p>
    </div>

    <div class="content">
        <h2>{product_name}</h2>

        <div class="stat-box">
            <strong>Current Rank:</strong> #{rank} {product.get('tier', {}).get('emoji', '')}
        </div>

        <div class="stat-box">
            <strong>Composite Score:</strong> {product.get('composite_score', 0):.1f}/100
        </div>

        <h3>Score Breakdown:</h3>
        <ul>
            <li>Trend Score: {product.get('score_breakdown', {}).get('trend_score', 0):.1f}</li>
            <li>Sales Velocity: {product.get('score_breakdown', {}).get('sales_velocity', 0):.1f}</li>
            <li>Social Sentiment: {product.get('score_breakdown', {}).get('social_sentiment', 0):.1f}</li>
            <li>Profit Margin: {product.get('score_breakdown', {}).get('profit_margin', 0):.1f}</li>
            <li>Competition Score: {product.get('score_breakdown', {}).get('competition_score', 0):.1f}</li>
        </ul>

        <p><strong>Selling Price:</strong> ${product.get('selling_price', 0):.2f}</p>
        <p><strong>Profit Margin:</strong> {product.get('profit_margin', 0):.1f}%</p>

        <p style="margin-top: 30px; padding: 15px; background: #fffbeb; border-radius: 8px; border-left: 4px solid #f59e0b;">
            [TARGET] <strong>Action Required:</strong> This is an elite-performing product. Consider increasing inventory,
            optimizing listings, and maximizing advertising budget for this product.
        </p>
    </div>

    <div class="footer">
        <p>OspraOS Product Rankings | {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>
    </div>
</body>
</html>
            """

            self._send_email(to_emails, subject, body, is_html=True)

            logger.info(f"Sent ELITE tier notification for product {product.get('product_id')}")

        except Exception as e:
            logger.error(f"Failed to send ELITE notification: {e}")

    def _create_email_body(
        self,
        product: Dict,
        previous_rank: Optional[int]
    ) -> str:
        """Create HTML email body for Top 10 notification."""

        rank = product.get('rank')
        product_name = product.get('product_name', f"Product #{product.get('product_id')}")

        # Determine rank change message
        if previous_rank is None:
            rank_change_msg = "[NEW] <strong>Brand new entry</strong> to the rankings!"
        elif previous_rank > 20:
            rank_change_msg = f"[TREND] <strong>Jumped from #{previous_rank}</strong> (outside top 20)"
        else:
            positions_gained = previous_rank - rank
            rank_change_msg = f"[TREND] <strong>Rose {positions_gained} positions</strong> from #{previous_rank}"

        return f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .header {{ background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%); color: white; padding: 30px; text-align: center; }}
        .content {{ padding: 30px; background: #f9fafb; }}
        .stat-box {{ background: white; border-left: 4px solid #3b82f6; padding: 15px; margin: 10px 0; border-radius: 8px; }}
        .tier-badge {{ display: inline-block; padding: 5px 15px; background: #3b82f6; color: white; border-radius: 20px; font-weight: bold; }}
        .footer {{ padding: 20px; text-align: center; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>[TOP] Top 10 Achievement!</h1>
        <p style="font-size: 18px;">A product has entered the Top 10 rankings</p>
    </div>

    <div class="content">
        <h2>{product_name}</h2>

        <p style="font-size: 16px; margin: 20px 0;">{rank_change_msg}</p>

        <div class="stat-box">
            <strong>Current Rank:</strong> #{rank} <span class="tier-badge">{product.get('tier', {}).get('name', 'TOP')}</span>
        </div>

        <div class="stat-box">
            <strong>Composite Score:</strong> {product.get('composite_score', 0):.1f}/100
        </div>

        <h3>Performance Metrics:</h3>
        <ul>
            <li><strong>Trend Score:</strong> {product.get('score_breakdown', {}).get('trend_score', 0):.1f}/100</li>
            <li><strong>Sales Velocity:</strong> {product.get('score_breakdown', {}).get('sales_velocity', 0):.1f}/100</li>
            <li><strong>Social Sentiment:</strong> {product.get('score_breakdown', {}).get('social_sentiment', 0):.1f}/100</li>
            <li><strong>Profit Margin:</strong> {product.get('score_breakdown', {}).get('profit_margin', 0):.1f}/100</li>
            <li><strong>Competition:</strong> {product.get('score_breakdown', {}).get('competition_score', 0):.1f}/100</li>
        </ul>

        <p><strong>Product ID:</strong> {product.get('product_id')}</p>
        <p><strong>Store ID:</strong> {product.get('store_id')}</p>
        <p><strong>Selling Price:</strong> ${product.get('selling_price', 0):.2f}</p>

        <p style="margin-top: 30px;">
            <a href="{product.get('source_url', '#')}"
               style="display: inline-block; padding: 12px 24px; background: #3b82f6; color: white; text-decoration: none; border-radius: 6px;">
                View Product Details
            </a>
        </p>
    </div>

    <div class="footer">
        <p>OspraOS Product Rankings | {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>
        <p><a href="http://localhost:5173/rankings" style="color: #3b82f6;">View Full Rankings Dashboard</a></p>
    </div>
</body>
</html>
        """

    def _send_email(
        self,
        to_emails: List[str],
        subject: str,
        body: str,
        is_html: bool = True
    ):
        """Send email via SMTP."""
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            msg = MIMEMultipart('alternative')
            msg['From'] = self.smtp_config['from_email']
            msg['To'] = ', '.join(to_emails)
            msg['Subject'] = subject

            content_type = 'html' if is_html else 'plain'
            msg.attach(MIMEText(body, content_type))

            # Connect and send
            with smtplib.SMTP(self.smtp_config['host'], self.smtp_config['port']) as server:
                server.starttls()
                server.login(self.smtp_config['username'], self.smtp_config['password'])
                server.send_message(msg)

            logger.info(f"Email sent successfully to {len(to_emails)} recipients")

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            raise


logger.info("[SUCCESS] RankingNotifier module loaded")
