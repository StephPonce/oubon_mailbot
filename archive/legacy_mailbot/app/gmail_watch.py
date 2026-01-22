"""Gmail Push Notification Manager - Sets up and manages Gmail watch."""
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from app.gmail_client import GmailClient
from app.settings import Settings


class GmailWatchManager:
    """
    Manages Gmail push notifications via Google Cloud Pub/Sub.

    How it works:
    1. Set up a "watch" on Gmail inbox
    2. Gmail sends notifications to Pub/Sub topic when new emails arrive
    3. Pub/Sub pushes to your webhook endpoint
    4. Webhook triggers email processing
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.gmail_client = GmailClient(settings)

    def start_watch(self) -> Dict[str, Any]:
        """
        Start watching Gmail inbox for changes.

        Returns watch information including expiration time.
        Gmail watches expire after 7 days, so you need to renew them.
        """
        if not self.settings.GOOGLE_CLOUD_PROJECT_ID:
            raise ValueError("GOOGLE_CLOUD_PROJECT_ID not configured")

        if not self.settings.GMAIL_PUBSUB_TOPIC:
            raise ValueError("GMAIL_PUBSUB_TOPIC not configured")

        service = self.gmail_client.service()

        # Topic format: projects/{project}/topics/{topic}
        topic_name = f"projects/{self.settings.GOOGLE_CLOUD_PROJECT_ID}/topics/{self.settings.GMAIL_PUBSUB_TOPIC}"

        request_body = {
            "labelIds": ["INBOX"],  # Watch inbox only
            "topicName": topic_name,
        }

        try:
            result = service.users().watch(
                userId="me",
                body=request_body
            ).execute()

            # Calculate expiration (Gmail watches expire in 7 days)
            expiration_ms = int(result.get("expiration", 0))
            expiration_dt = datetime.fromtimestamp(expiration_ms / 1000.0) if expiration_ms else None

            return {
                "success": True,
                "history_id": result.get("historyId"),
                "expiration": result.get("expiration"),
                "expiration_date": expiration_dt.isoformat() if expiration_dt else None,
                "topic": topic_name,
                "message": f"Gmail watch started. Expires: {expiration_dt}",
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to start Gmail watch. Check Pub/Sub permissions.",
            }

    def stop_watch(self) -> Dict[str, Any]:
        """Stop watching Gmail inbox."""
        try:
            service = self.gmail_client.service()
            service.users().stop(userId="me").execute()

            return {
                "success": True,
                "message": "Gmail watch stopped successfully",
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def get_watch_status(self) -> Dict[str, Any]:
        """
        Check if watch is active.
        Note: Gmail API doesn't provide a direct way to check watch status,
        so we return general info.
        """
        return {
            "configured": bool(
                self.settings.GOOGLE_CLOUD_PROJECT_ID and
                self.settings.GMAIL_PUBSUB_TOPIC
            ),
            "project_id": self.settings.GOOGLE_CLOUD_PROJECT_ID,
            "topic": self.settings.GMAIL_PUBSUB_TOPIC,
            "note": "Watches expire after 7 days. Renew regularly.",
        }
