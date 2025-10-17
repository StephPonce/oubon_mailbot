"""
AI Reply Generator with intent templates, Shopify enrichment, and guardrails.
"""

from __future__ import annotations
import html
from typing import Tuple, Optional

from app.ai_client import ai_client
from app.time_utils import is_quiet_hours
from app.shopify_client import get_order_by_name
from app.settings import get_settings

# ---------------------------------------------------------------------------
# Intent templates
# ---------------------------------------------------------------------------
# Keep these short, factual, and policy-safe. We optionally let the LLM refine
# tone, but these are the authoritative fallbacks and guardrails.
TEMPLATES = {
    "order_status_fulfilled": (
        "Hi there — your order {order_no} has shipped. "
        "Tracking: {tracking_url}. Latest status: {tracking_status}. "
        "If it hasn’t arrived within 48 hours after the expected date, reach us here: {help_url}"
    ),
    "order_status_unfulfilled": (
        "Hi — we’ve received your order {order_no} and it’s being prepared. "
        "You’ll get tracking details as soon as it ships. You can check updates here: {help_url}"
    ),
    "refund": (
        "Hello — we’ve received your refund request for order {order_no}. "
        "Our team will review within 24 hours. Once approved, funds typically return in 3–5 business days."
    ),
    "address_change": (
        "Got it — your shipping address for {order_no} has been updated to:\n"
        "{address1}, {city}, {province}, {zip}. If you need further edits, please submit them at {help_url}"
    ),
    "complaint": (
        "Hi — thank you for letting us know. We take feedback seriously and will review this immediately. "
        "A specialist will follow up shortly."
    ),
    "vip": (
        "Hey {first_name}! We’ve got your message — our VIP team will handle this personally. Expect an update soon."
    ),
    "other": (
        "Hello — thanks for reaching out! We’ve received your message and will follow up soon. "
        "In the meantime, you can find answers or contact us here: {help_url}"
    ),
}

# Hard-stops: if the LLM suggests any of these, ignore and use template.
SAFE_STOP_PHRASES = [
    "refund approved",
    "discount code",
    "guarantee delivery",
    "free replacement",
]

def _support_link() -> str:
    """
    Returns a clean help URL with no accidental quotes/slashes, preferring SUPPORT_FORM_URL,
    falling back to https://{STORE_DOMAIN}/pages/help-with-orders, then a safe default.
    """
    from app.settings import get_settings  # local import to avoid import cycles
    s = get_settings()
    if getattr(s, "SUPPORT_FORM_URL", None):
        return s.SUPPORT_FORM_URL
    if getattr(s, "STORE_DOMAIN", None):
        return f"https://{s.STORE_DOMAIN}/pages/help-with-orders"
    return "https://example.com/pages/help-with-orders"



def _detect_intent(text: str) -> str:
    """Very lightweight intent detection (keywords, fallback 'other')."""
    t = (text or "").lower()
    if "refund" in t or "return" in t:
        return "refund"
    if "address" in t or "ship to" in t or "change my address" in t:
        return "address_change"
    if ("where" in t and "order" in t) or "wheres my" in t:
        return "order_status"
    if "status" in t or "track" in t or "tracking" in t:
        return "order_status"
    if "complain" in t or "angry" in t or "disappointed" in t or "issue" in t:
        return "complaint"
    if "vip" in t or "priority" in t:
        return "vip"
    return "other"


async def _shopify_enrich(context: dict) -> None:
    """
    Best-effort Shopify enrichment. Non-blocking: any failure keeps safe defaults.
    Populates tracking_url/tracking_status and a simple fulfillment marker.
    """
    order_no = context.get("order_no")
    if not order_no or order_no == "your recent order":
        return
    try:
        order = await get_order_by_name(order_no)
        if not order:
            return
        # Tracking
        tracking_items = order.get("tracking") or []
        if tracking_items:
            url = tracking_items[0].get("url")
            if url:
                context["tracking_url"] = url
            company = tracking_items[0].get("company") or ""
            context["tracking_status"] = f"in transit via {company}" if company else "in transit"
        # Fulfillment status marker
        fs = (order.get("fulfillment_status") or "").strip() or "processing"
        context["fulfilled_at"] = fs
    except Exception:
        # Keep defaults; enrichment is optional.
        pass


async def generate_reply(
    subject: str,
    body: str,
    order_no: Optional[str] = None,
    tracking: Optional[str] = None,
) -> Tuple[str, str]:
    """
    AI-augmented template generator.
    Returns (reply_text, detected_intent).
    """
    # --- Quiet hours fallback (authoritative) ---
    if is_quiet_hours():
        help_url = _support_link()
        reply = (
            "Hello — thanks for reaching out! Our team is offline right now. "
            f"We’ll reply during business hours.\n\nYou can check help here: {help_url}"
        )
        return html.escape(reply[:1800]), "quiet_hours"

    # --- Intent detection ---
    merged = f"{subject or ''}\n{body or ''}"
    intent = _detect_intent(merged)

    # --- Context defaults ---
    help_url = _support_link()
    context = {
        "order_no": (order_no or "your recent order"),
        "help_url": help_url,
        "first_name": "there",
        "address1": "",
        "city": "",
        "province": "",
        "zip": "",
        "tracking_url": tracking or "tracking link will be sent soon",
        "tracking_status": "in transit",
        "fulfilled_at": "",
    }

    # --- Shopify enrichment (best-effort) ---
    await _shopify_enrich(context)

    # --- Choose a base template ---
    # For order_status, pick fulfilled/unfulfilled variant when we have a marker.
    base_key = intent
    if intent == "order_status":
        if (context.get("fulfilled_at") or "").lower() in ("fulfilled", "shipped", "delivered"):
            base_key = "order_status_fulfilled"
        else:
            base_key = "order_status_unfulfilled"
    base_text = TEMPLATES.get(base_key, TEMPLATES["other"])
    templated = base_text.format(**context)

    # --- Optional AI tone refinement (guarded) ---
    final_text = templated
    try:
        client = ai_client()
        prompt = (
            "Rewrite the following customer support reply in a concise, friendly, brand-neutral tone. "
            "Do not promise refunds, discounts, or guaranteed delivery dates. Keep policy-safe language. "
            "Reply text:\n"
            f"{templated}\n"
        )
        ai_out = await client.chat(prompt)
        if ai_out:
            low = ai_out.lower()
            if not any(stop in low for stop in SAFE_STOP_PHRASES):
                final_text = ai_out.strip()
    except Exception:
        pass

    # --- Length guard + HTML escape ---
    return html.escape(final_text[:1800]), intent
