"""
💬 SLACK NOTIFIER
Send product change alerts to Slack via webhooks
"""

import requests
import logging
from datetime import datetime
from typing import List, Dict
import os

logger = logging.getLogger(__name__)


class SlackNotifier:
    """Send Slack notifications for product changes"""

    def __init__(self):
        """Initialize Slack notifier with webhook URL"""
        self.webhook_url = os.getenv("SLACK_WEBHOOK_URL")

        # Check if configured
        self.is_configured = bool(self.webhook_url)

        if not self.is_configured:
            logger.warning("⚠️  Slack notifications not configured. Set SLACK_WEBHOOK_URL in .env")
        else:
            logger.info("✅ Slack notifier initialized")

    def send_change_alert(self, changes: List[Dict]) -> bool:
        """
        Send Slack alert for product changes

        Args:
            changes: List of detected changes

        Returns:
            True if message sent successfully, False otherwise
        """
        if not self.is_configured:
            logger.warning("Slack not configured, skipping notification")
            return False

        if not changes:
            return False

        try:
            # Build Slack message
            message = self._build_slack_message(changes)

            # Send to webhook
            response = requests.post(
                self.webhook_url,
                json=message,
                timeout=10
            )

            if response.status_code == 200:
                logger.info("✅ Slack message sent")
                return True
            else:
                logger.error(f"Slack webhook failed: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"Failed to send Slack message: {e}")
            return False

    def _build_slack_message(self, changes: List[Dict]) -> Dict:
        """Build Slack message with blocks"""

        # Group by severity
        high = [c for c in changes if c.get('severity') == 'high']
        medium = [c for c in changes if c.get('severity') == 'medium']
        low = [c for c in changes if c.get('severity') == 'low']

        blocks = []

        # Header block
        blocks.append({
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"🚨 Product Change Alert",
                "emoji": True
            }
        })

        # Context block with timestamp
        blocks.append({
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": f"Detected *{len(changes)} changes* at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            }]
        })

        blocks.append({"type": "divider"})

        # High priority changes
        if high:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*🔴 HIGH PRIORITY ({len(high)})*"
                }
            })

            for change in high:
                emoji = self._get_emoji(change['type'])
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{emoji} *{change['product_name']}*\n{change['message']}"
                    }
                })

            blocks.append({"type": "divider"})

        # Medium priority changes
        if medium:
            changes_text = "\n".join([
                f"• {c['product_name']}: {c['message']}"
                for c in medium[:5]
            ])

            if len(medium) > 5:
                changes_text += f"\n_... and {len(medium) - 5} more_"

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*🟡 MEDIUM PRIORITY ({len(medium)})*\n{changes_text}"
                }
            })

            blocks.append({"type": "divider"})

        # Low priority changes (summary only)
        if low:
            changes_text = "\n".join([
                f"• {c['product_name']}: {c['message']}"
                for c in low[:3]
            ])

            if len(low) > 3:
                changes_text += f"\n_... and {len(low) - 3} more_"

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*🟢 LOW PRIORITY ({len(low)})*\n{changes_text}"
                }
            })

        # Footer
        blocks.append({
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": "View your dashboard for full details and AI-powered insights."
            }]
        })

        return {"blocks": blocks}

    def _get_emoji(self, change_type: str) -> str:
        """Get emoji for change type"""
        emoji_map = {
            'velocity': '⚡',
            'price': '💰',
            'score': '⭐'
        }
        return emoji_map.get(change_type, '📊')

    def send_test_message(self) -> bool:
        """Send a test message to verify configuration"""
        if not self.is_configured:
            logger.error("Slack not configured")
            return False

        test_changes = [{
            'product_name': 'Test Product',
            'type': 'velocity',
            'message': '📈 Test notification',
            'severity': 'high'
        }]

        return self.send_change_alert(test_changes)

    def send_simple_message(self, text: str) -> bool:
        """Send a simple text message to Slack"""
        if not self.is_configured:
            return False

        try:
            response = requests.post(
                self.webhook_url,
                json={"text": text},
                timeout=10
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to send Slack message: {e}")
            return False
