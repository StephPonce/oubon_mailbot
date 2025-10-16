from pathlib import Path
import json
from typing import Dict

# Built-in defaults used if no external file overrides them.
DEFAULT_TPLS: Dict[str, Dict[str, str]] = {
    # Daytime default (no name, starts with "Hello")
    "support_default": {
        "subject": "Thanks for reaching out -- we're on it",
        "body": (
            "Hello,<br><br>"
            "Thanks for reaching out to Oubon. We've received your message and opened a ticket "
            "(#{{ticket_id}}). A team member will follow up within 1 business day.<br><br>"
            "If this is about an order, please include your order number so we can check status and tracking.<br><br>"
            "-- Oubon Support"
        ),
    },

    # Quiet-hours acknowledgement used by main.py when is_quiet_hours() is True
    "quiet_hours_ack": {
        "subject": "We received your message",
        "body": (
            "Hello,<br><br>"
            "We've received your message and our support team will follow up first thing in the morning.<br><br>"
            "-- Oubon Support"
        ),
    },

    # Orders fallback if we didn't find a live order in Shopify
    "order_missing": {
        "subject": "We're on it -- order {{order_id}}",
        "body": (
            "Hello,<br><br>"
            "Thanks for reaching out. Please reply with your order number so we can check the status and tracking.<br><br>"
            "-- Oubon Support"
        ),
    },

    # Optional extras you may already use
    "vip_welcome": {
        "subject": "Thanks for reaching out",
        "body": (
            "Hello,<br><br>"
            "We've received your message and will jump on this right away.<br><br>"
            "-- Oubon VIP Support"
        ),
    },
}


def _load_templates() -> Dict[str, Dict[str, str]]:
    """
    Load templates from data/templates.json if present, overlaying DEFAULT_TPLS.
    File format:
      {
        "template_id": {"subject": "...", "body": "..."},
        ...
      }
    """
    tpls = dict(DEFAULT_TPLS)
    fp = Path("data") / "templates.json"
    if fp.exists():
        try:
            user_tpls = json.loads(fp.read_text(encoding="utf-8"))
            if isinstance(user_tpls, dict):
                for k, v in user_tpls.items():
                    if isinstance(v, dict):
                        subj = v.get("subject", tpls.get(k, {}).get("subject", ""))
                        body = v.get("body", tpls.get(k, {}).get("body", ""))
                        tpls[k] = {"subject": subj, "body": body}
        except Exception:
            # If malformed, fall back silently to defaults
            pass
    return tpls
