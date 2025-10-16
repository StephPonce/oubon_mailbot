from __future__ import annotations

from typing import Dict, Tuple
from app.settings import get_settings
from app.time_utils import is_quiet_hours
from app.ai_client import ai_client, extract_message_content

SETTINGS = get_settings()

TEMPLATES: Dict[str, str] = {
    "order_status": (
        "Hello — thanks for reaching out! "
        "Here’s the latest on your order {{ORDER_NO}}: {{TRACKING_OR_NEXT_STEP}}. "
        "If anything looks off, reply to this email and we’ll make it right."
    ),
    "refund": (
        "Hello — we’ve started your refund for order {{ORDER_NO}}. "
        "You’ll see the credit in 3–5 business days. If you need anything else, just reply here."
    ),
    "complaint": (
        "Hello — we’re sorry about the trouble. "
        "We’ll make this right. Please confirm your order number and a clear photo if applicable. "
        "We’ll send next steps promptly."
    ),
    "general": (
        "Hello — thanks for contacting Oubon. We’ve received your message and we’ll help right away."
    ),
}


def _classify_intent(subject: str, body: str) -> str:
    s = f"{subject} {body}".lower()
    if any(k in s for k in ["refund", "return", "money back"]):
        return "refund"
    if any(k in s for k in ["track", "tracking", "where is", "status", "arrive", "missing order"]):
        return "order_status"
    if any(k in s for k in ["broken", "damaged", "upset", "disappointed", "complaint"]):
        return "complaint"
    return "general"


def _fill(template: str, order_no: str | None = None, tracking: str | None = None) -> str:
    out = template.replace("{{ORDER_NO}}", order_no or "(pending)")
    out = out.replace("{{TRACKING_OR_NEXT_STEP}}", tracking or "we’ll confirm tracking shortly")
    return out


async def generate_reply(*, subject: str, body: str, order_no: str | None = None, tracking: str | None = None) -> Tuple[str, str]:
    intent = _classify_intent(subject, body)

    # Quiet hours: short acknowledgement, no AI call.
    if is_quiet_hours():
        msg = "Hello — thanks for reaching out! Our team is offline right now. We've logged your message and will follow up during business hours (7am–10pm CT)."
        return msg, intent

    # Daytime: template -> AI personalize
    base = _fill(TEMPLATES[intent], order_no=order_no, tracking=tracking)

    # AI PROVIDER strictly openai via ai_client()
    client = ai_client()
    model = getattr(SETTINGS, "AI_MODEL", "gpt-4o-mini")
    system = (
        "You are Oubon's customer support assistant. Keep replies concise (80–120 words), friendly, and helpful. "
        "Never invent order info; if missing, ask for it. Keep brand tone: calm, human, and clear."
    )
    user = f"Subject: {subject}\n\nCustomer message:\n{body}\n\nDraft to personalize:\n{base}"

    # Retry up to 2 times on transient errors; never expose raw errors to customers
    last_err = None
    for _ in range(2):
        try:
            completion = client.chat.completions.create(
                model=model,
                temperature=0.4,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            text = extract_message_content(completion).strip()
            if text:
                return text, intent
        except Exception as e:
            last_err = e

    # Fallback: never leak error messages to customers
    safe = base + " If you can share your order number, we’ll speed this up."
    return safe, intent
