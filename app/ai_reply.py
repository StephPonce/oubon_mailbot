from __future__ import annotations

from app.settings import get_settings
from app.time_utils import is_quiet_hours


async def generate_reply(*, subject: str, body: str, order_no: str | None = None, tracking: str | None = None):
    """
    Generate a contextual reply and an intent string.
    Quiet hours -> short safe reply.
    Daytime -> intent-aware reply with Help link.
    """
    s = get_settings()
    # Public-facing domain
    store_domain = (
        getattr(s, "STORE_DOMAIN", None)
        or getattr(s, "SHOPIFY_STORE", "").replace("https://", "").replace("http://", "")
    )
    help_url = f"https://{store_domain}/pages/help" if store_domain else "https://example.com/pages/help"

    # Quiet-hours short reply
    if is_quiet_hours():
        msg = (
            "Hello — thanks for reaching out! Our team is currently offline.\n"
            "We’ve received your message and will follow up during business hours (7am–10pm CT).\n\n"
            f"For faster service you can also use our Help With Orders form:\n{help_url}\n\n"
            "– Team Oubon"
        )
        return msg, "quiet_hours"

    text = (subject or "").lower() + "\n" + (body or "").lower()
    intent = "general"

    if any(k in text for k in ["refund", "return", "money back"]):
        intent = "refund"
        reply = (
            "Hello — we can help with your refund request.\n\n"
            "Please confirm your order number and details. If the order hasn’t shipped yet we’ll process it immediately; "
            "otherwise we’ll share the return instructions.\n\n"
            f"For faster processing you can submit here:\n{help_url}\n\n"
            "– Team Oubon"
        )
        return reply, intent

    if any(k in text for k in ["address", "wrong address", "change address", "update address"]):
        intent = "address_change"
        reply = (
            "Hello — we can update your shipping address if the order is not yet fulfilled.\n\n"
            "Please share the new address (street, city, state, zip). We’ll confirm once it’s applied.\n\n"
            f"You can also use our Help With Orders form:\n{help_url}\n\n"
            "– Team Oubon"
        )
        return reply, intent

    if any(k in text for k in ["track", "tracking", "where is", "not received", "missing", "status"]):
        intent = "order_status"
        extra = f" Order {order_no}." if order_no else ""
        reply = (
            f"Hello — thanks for reaching out! We’re checking the latest tracking on your order.{extra}\n\n"
            f"You can share your order number to speed this up, or use our Help With Orders page:\n{help_url}\n\n"
            "– Team Oubon"
        )
        return reply, intent

    # Default
    reply = (
        "Hello — thanks for contacting Oubon Support!\n\n"
        "We’ve received your message and will follow up shortly. "
        f"For faster service, you can also use our Help With Orders page:\n{help_url}\n\n"
        "– Team Oubon"
    )
    return reply, intent
