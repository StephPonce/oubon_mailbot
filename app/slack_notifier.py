"""
Lightweight Slack webhook notifier utility.
"""
from __future__ import annotations

import json
from typing import Optional

import requests

from app.settings import get_settings


def send_slack_alert(channel: str, message: str) -> None:
    """
    Send a simple text alert to Slack using the configured webhook.
    If no webhook is configured, this function silently returns.
    """
    settings = get_settings()
    webhook = settings.slack_webhook_url.strip() if settings.slack_webhook_url else ""
    if not webhook:
        return

    payload = {"text": message}
    # Incoming webhooks can accept an optional channel override.
    if channel:
        payload["channel"] = channel

    try:
        resp = requests.post(webhook, data=json.dumps(payload), timeout=5)
        resp.raise_for_status()
    except Exception:
        # Slack failures should never break the main app flow.
        return
