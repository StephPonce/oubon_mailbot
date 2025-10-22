from __future__ import annotations

import asyncio
import logging
import re
from textwrap import dedent

from ospra_os.core.settings import Settings
from .ai_client import ai_client, extract_message_content

logger = logging.getLogger(__name__)

INTENT_LABELS = [
    "ORDER_STATUS",
    "CANCELLATION",
    "RETURN_EXCHANGE",
    "GENERAL_SUPPORT",
    "SPAM_NEWSLETTER",
]

AD_SENDER_HINTS = [
    r"(no[-_. ]?reply|donotreply|mailer-daemon|postmaster)@",
    r"news(?:letter)?@",
    r"\bmarketing\b",
    r"\badvertis(?:e|ing)\b",
    r"\bpartnership\b",
    r"\bcollab\b",
]

AD_SUBJECT_HINTS = [
    r"\bnewsletter\b",
    r"\bdiscount\b",
    r"\bpromo\b",
    r"\bpartnership\b",
    r"\bcollab\b",
    r"\bseo\b",
    r"\bbacklink\b",
    r"\bguest post\b",
    r"\bleads?\b",
]

SAFE_STOPS = [
    "refund approved",
    "guarantee delivery",
    "free replacement",
    "discount code",
]


async def ai_preview(subject: str, body: str, order_info=None) -> dict:
    st = Settings()
    if not _openai_enabled(st):
        text = _stub(subject, body, order_info)
        return {"summary": text, "auto_reply_suggestion": text}

    system = (
        "You are OspraOS support. Summarize the inbound message and produce a concise reply. "
        "If order info is provided, include current status and next steps."
    )
    user = f"Subject: {subject}\n\nBody:\n{body}\n\nOrderInfo:\n{order_info or 'None'}"
    text = await asyncio.to_thread(
        _openai_chat,
        st,
        system,
        user,
        300,
        0.2,
    )
    return {"summary": text, "auto_reply_suggestion": text}


def _looks_like_ad(sender: str, subject: str, body: str) -> bool:
    sender = (sender or "").lower()
    subject_l = (subject or "").lower()
    body_l = (body or "").lower()
    for pattern in AD_SENDER_HINTS:
        if re.search(pattern, sender, flags=re.IGNORECASE):
            return True
    for pattern in AD_SUBJECT_HINTS:
        if re.search(pattern, subject_l, flags=re.IGNORECASE) or re.search(pattern, body_l, flags=re.IGNORECASE):
            return True
    return False


async def classify_intent(subject: str, body: str, sender: str = "") -> str:
    if _looks_like_ad(sender, subject, body):
        return "SPAM_NEWSLETTER"

    text = f"{subject or ''}\n{body or ''}".lower()
    if re.search(r"\b(refund|chargeback|return|rma)\b", text, re.I):
        return "REFUND"
    if any(token in text for token in ["order", "tracking", "where is my", "wheres my", "shipment", "delivered"]):
        return "ORDER_STATUS"
    if any(token in text for token in ["refund", "return", "exchange", "cancel order"]):
        return "RETURN_EXCHANGE"
    if any(token in text for token in ["help", "issue", "problem", "support", "question"]):
        return "GENERAL_SUPPORT"

    return "GENERAL_SUPPORT"


async def smart_reply(
    *,
    subject: str,
    body: str,
    order_status: dict | None,
    brand: str,
    signature: str,
    concise: bool = True,
) -> dict:
    st = Settings()
    help_link = f"https://{brand.replace(' ', '').lower()}/pages/help-with-orders"
    if not order_status:
        base = dedent(
            f"""
            Hello — thanks for reaching out to {brand}! We’ve received your message.
            We’ll check your order and follow up shortly.
            In the meantime you can find help here: {help_link}
            {signature}
            """
        ).strip()
    else:
        status = order_status.get("status", "processing")
        tracking = order_status.get("tracking")
        carrier = order_status.get("carrier")
        eta = order_status.get("eta")
        parts = [
            f"Hello — thanks for reaching out to {brand}!",
            f"Current status: {status}.",
        ]
        if tracking:
            parts.append(f"Tracking: {tracking}")
        if carrier:
            parts.append(f"Carrier: {carrier}")
        if eta:
            parts.append(f"Estimated delivery: {eta}")
        parts.append(f"If you need anything else, see: {help_link}")
        parts.append(signature)
        base = "\n".join(parts)

    prompt = dedent(
        f"""
        You are an Oubon Shop customer support agent.
        Rewrite the reply below in a concise, friendly, professional tone.
        - Do NOT promise refunds, discounts, or guaranteed delivery dates.
        - Keep it factual and empathetic.
        - Preserve any tracking links and order details exactly.
        - Maximum 150 words.
        Reply to customer:

        Subject: {subject or '(no subject)'}
        ---
        {body[:2000]}
        ---
        Draft reply to refine:
        {base}
        """
    ).strip()

    if not st.OPENAI_API_KEY:
        return {"reply": base}

    try:
        client = ai_client()
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        text = extract_message_content(completion).strip()
        low = text.lower()
        if not text or any(stop in low for stop in SAFE_STOPS):
            return {"reply": base}
        return {"reply": text}
    except Exception:
        return {"reply": base}


def _stub(subject: str, body: str, order_info=None) -> str:
    base = f"Subject: {subject}. Summary: {body[:140]}"
    if order_info:
        base += f" | Order: {order_info.get('name') or order_info.get('id')}"
    return base + " | Thanks for reaching out — we’ll keep you updated."


def _stub_classification(subject: str, body: str) -> str:
    text = f"{subject} {body}".lower()
    if any(word in text for word in ("unsubscribe", "newsletter", "win money", "promotion")):
        return "SPAM_NEWSLETTER"
    if "cancel" in text:
        return "CANCELLATION"
    if "return" in text or "exchange" in text or "refund" in text:
        return "RETURN_EXCHANGE"
    if "order" in text and ("status" in text or "where" in text or "tracking" in text):
        return "ORDER_STATUS"
    return "GENERAL_SUPPORT"


def _openai_enabled(st: Settings) -> bool:
    provider = (st.AI_PROVIDER or "").lower()
    return provider == "openai" and bool(st.OPENAI_API_KEY)


def _openai_chat(st: Settings, system: str, user: str, max_tokens: int, temperature: float) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=st.OPENAI_API_KEY)
    resp = client.chat.completions.create(
        model=st.AI_MODEL or "gpt-4o-mini",
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content.strip()


def _openai_complete(st: Settings, prompt: str, max_tokens: int) -> str:
    system = "You draft concise ecommerce support replies."
    return _openai_chat(st, system, prompt, max_tokens, 0.2)
