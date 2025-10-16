"""Main FastAPI application for the Oubon MailBot service.

This module wires Gmail automation, Shopify enrichment, public support endpoints,
and background scheduling into a cohesive API surface for customer operations.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
import time
from datetime import datetime
from threading import Thread
from typing import Any, Dict, Optional
from urllib import request as urlreq
from urllib.parse import urlencode

from email.utils import parseaddr

import schedule
from fastapi import APIRouter, Body, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr

from app.ai_client import ai_client
from app.ai_reply import generate_reply
from app.cooldown import is_on_cooldown, mark_replied
from app.database import conn
from app.gmail_client import GmailClient, send_plain_email
from app.rules import match_label_for_message
from app.settings import get_settings
from app.shopify_client import cancel_unfulfilled_order, get_order_by_name, update_order_address
from app.slack_notifier import send_slack_alert
from app.store_registry import StoreCreate, add_store
from app.time_utils import is_quiet_hours

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("oubun_mailbot")

app = FastAPI(title="Oubon MailBot", version="1.2")
SETTINGS = get_settings()
gmail = GmailClient(SETTINGS)

ORDER_ID_RE = re.compile(r"\b(?:OU)?\d{5,}\b", re.IGNORECASE)
SIMPLE_QUIET_REPLY = (
    "Hello — thanks for reaching out! Our team is offline right now. "
    "We’ve got your message and will reply during business hours (7am–10pm CT)."
)
AUTO_IGNORE_LABEL = "Auto/Ignored"
REPLIED_LABEL = "Replied"


def _ensure_ai_usage_table() -> None:
    """Create the AI usage tracking table if it does not yet exist."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS ai_usage (date DATE PRIMARY KEY, used INT DEFAULT 0)"
    )
    today = datetime.now().date().isoformat()
    row = conn.execute("SELECT used FROM ai_usage WHERE date = ?", (today,)).fetchone()
    if row is None:
        conn.execute("INSERT INTO ai_usage (date, used) VALUES (?, 0)", (today,))
    conn.commit()


_ensure_ai_usage_table()


def _get_or_create_label_id(service: Any, name: str) -> str:
    """Return a Gmail label ID, creating the label if it does not exist."""
    resp = service.users().labels().list(userId="me").execute()
    for label in resp.get("labels", []):
        if label["name"].lower() == name.lower():
            return label["id"]
    payload = {"name": name, "labelListVisibility": "labelShow", "messageListVisibility": "show"}
    created = service.users().labels().create(userId="me", body=payload).execute()
    return created["id"]


def _extract_text_from_payload(payload: Dict[str, Any]) -> str:
    """Extract best-effort plaintext from a Gmail message payload."""
    if not payload:
        return ""

    body = payload.get("body", {})
    data = body.get("data")
    if data:
        try:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Failed to decode primary payload body: %s", exc)

    for part in payload.get("parts", []) or []:
        mime_type = part.get("mimeType", "")
        if mime_type.startswith("text/plain"):
            try:
                encoded = part.get("body", {}).get("data", "")
                return base64.urlsafe_b64decode(encoded).decode("utf-8", errors="ignore")
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Failed to decode text/plain part: %s", exc)

    for part in payload.get("parts", []) or []:
        mime_type = part.get("mimeType", "")
        if mime_type.startswith("text/html"):
            try:
                encoded = part.get("body", {}).get("data", "")
                html = base64.urlsafe_b64decode(encoded).decode("utf-8", errors="ignore")
                return re.sub(r"<[^>]+>", " ", html)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Failed to decode text/html part: %s", exc)

    return ""


def _extract_order_id(subject: str, body: str) -> Optional[str]:
    """Return the detected order identifier from a subject/body pair."""
    text = f"{subject}\n{body}"
    match = ORDER_ID_RE.search(text)
    return match.group(0).upper() if match else None


def _shopify_lookup(order_name: str) -> Optional[Dict[str, Any]]:
    """Fetch order metadata from Shopify REST using the configured credentials."""
    store = str(getattr(SETTINGS, "SHOPIFY_STORE", "") or "").strip()
    token = str(getattr(SETTINGS, "SHOPIFY_API_TOKEN", "") or "").strip()
    if not store or not token:
        logger.warning("Shopify lookup requested but store or token is missing.")
        return None

    candidates = (
        [order_name, order_name.lstrip("#")]
        if order_name.startswith("#")
        else [order_name, f"#{order_name}"]
    )

    for candidate in candidates:
        try:
            querystring = urlencode({"name": candidate})
            url = f"https://{store}/admin/api/2024-10/orders.json?{querystring}"
            request = urlreq.Request(
                url,
                headers={
                    "X-Shopify-Access-Token": token,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
            with urlreq.urlopen(request, timeout=15) as response:
                payload = json.loads(response.read().decode("utf-8", errors="ignore"))
        except Exception as exc:  # pragma: no cover - network safety
            logger.exception("Shopify lookup failed for %s", candidate)
            continue

        orders = payload.get("orders", [])
        if not orders:
            continue

        order = orders[0]
        tracking_items = []
        for fulfillment in order.get("fulfillments", []) or []:
            for number in fulfillment.get("tracking_numbers", []) or []:
                tracking_items.append(
                    {
                        "number": number,
                        "url": (fulfillment.get("tracking_urls") or [None])[0],
                        "company": fulfillment.get("tracking_company"),
                    }
                )

        shipping = order.get("shipping_address") or {}
        return {
            "name": order.get("name"),
            "id": order.get("id"),
            "email": order.get("email"),
            "created_at": order.get("created_at"),
            "financial_status": order.get("financial_status"),
            "fulfillment_status": order.get("fulfillment_status"),
            "current_total_price": order.get("current_total_price"),
            "shipping_address": {
                "city": shipping.get("city"),
                "province": shipping.get("province"),
                "country": shipping.get("country"),
                "zip": shipping.get("zip"),
            },
            "line_items": [
                {
                    "title": item.get("title"),
                    "sku": item.get("sku"),
                    "qty": item.get("quantity"),
                }
                for item in order.get("line_items", []) or []
            ],
            "tracking": tracking_items,
        }

    return None


class PreviewPayload(BaseModel):
    """Body schema for previewing an AI reply."""

    subject: str
    body: str
    order_no: str | None = None
    tracking: str | None = None


class SupportPayload(BaseModel):
    """Incoming payload for public support automation requests."""

    action: str
    order_no: str
    email: EmailStr
    note: str | None = None
    address1: str | None = None
    address2: str | None = None
    city: str | None = None
    province: str | None = None
    zip: str | None = None
    country: str | None = None
    store_domain: str | None = None


router_public = APIRouter(prefix="/public", tags=["public"])


@app.get("/health")
def health() -> Dict[str, str]:
    """Return a simple health indicator for upstream probes."""
    return {"status": "ok"}


async def gmail_process_inbox(payload: Dict[str, Any]) -> JSONResponse:
    """Process Gmail inbox messages, labeling and responding as required."""
    auto_reply = bool(payload.get("auto_reply", False)) or bool(getattr(SETTINGS, "REPLY_ALWAYS", False))
    max_messages = int(payload.get("max_messages", 5))
    cooldown_hours = int(payload.get("cooldown_hours", 24))
    result: Dict[str, Any] = {"processed": 0, "labeled": 0, "replied": 0, "errors": [], "last_label": None}

    try:
        service = gmail.service()
        replied_label_id = _get_or_create_label_id(service, REPLIED_LABEL)

        response = service.users().messages().list(
            userId="me", q="in:inbox -label:Replied", maxResults=max_messages
        ).execute()
        messages = response.get("messages", [])

        for message in messages:
            message_id = message["id"]
            try:
                full_message = service.users().messages().get(userId="me", id=message_id, format="full").execute()
                thread_id = full_message.get("threadId")
                headers = {header["name"].lower(): header["value"] for header in full_message.get("payload", {}).get("headers", [])}
                subject = headers.get("subject", "(no subject)")
                sender = headers.get("from", "unknown")
                existing_labels = set(full_message.get("labelIds", []))
                if replied_label_id in existing_labels:
                    logger.info("Skipping message %s: already contains Replied label.", message_id)
                    continue

                parsed_sender = parseaddr(sender or "")[1].lower()
                auto_markers = (
                    "no-reply",
                    "donotreply",
                    "noreply",
                    "mailer-daemon",
                    "bounce",
                    "notification",
                )
                if any(marker in parsed_sender for marker in auto_markers):
                    logger.info("Skipping automated sender %s for message %s.", parsed_sender, message_id)
                    auto_label_id = _get_or_create_label_id(service, AUTO_IGNORE_LABEL)
                    service.users().messages().modify(
                        userId="me", id=message_id, body={"addLabelIds": [auto_label_id]}
                    ).execute()
                    continue

                if subject.lower().startswith(("re:", "fw:", "fwd:")):
                    logger.info("Skipping reply thread %s (%s).", message_id, subject)
                    continue

                body_text = _extract_text_from_payload(full_message.get("payload", {}))
                result["processed"] += 1

                label = match_label_for_message(subject, body_text)
                if label:
                    label_id = _get_or_create_label_id(service, label)
                    service.users().messages().modify(
                        userId="me", id=message_id, body={"addLabelIds": [label_id]}
                    ).execute()
                    result["labeled"] += 1
                    result["last_label"] = label
                    logger.info("Applied label '%s' to message %s.", label, message_id)

                if not auto_reply:
                    logger.info("Auto-reply disabled; skipping message %s.", message_id)
                    continue

                if is_on_cooldown(sender, cooldown_hours, thread_id=thread_id):
                    logger.info("Sender %s is on cooldown; skipping message %s.", sender, message_id)
                    continue

                try:
                    reply_body, detected_intent = await generate_reply(subject=subject, body=body_text)
                except Exception as exc:  # pragma: no cover - AI provider failures
                    logger.exception("AI generation failed for sender %s.", sender)
                    send_slack_alert("#ai-alerts", f"AI generation failed for {sender}: {exc}")
                    reply_body = None
                    detected_intent = None

                if detected_intent:
                    result["last_intent"] = detected_intent

                if reply_body:
                    final_subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"
                    gmail.send_simple_email(to=sender, subject=final_subject, body=reply_body)
                    logger.info("Sent AI-crafted reply for message %s.", message_id)
                else:
                    if replied_label_id in existing_labels:
                        logger.info("Skipping quiet-hours fallback; message %s already labeled as replied.", message_id)
                        continue
                    final_subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"
                    gmail.send_simple_email(to=sender, subject=final_subject, body=SIMPLE_QUIET_REPLY)
                    logger.info("Sent fallback quiet-hours style reply for message %s.", message_id)

                service.users().messages().modify(
                    userId="me", id=message_id, body={"addLabelIds": [replied_label_id]}
                ).execute()
                if is_on_cooldown(sender, 24, thread_id=thread_id):
                    logger.info("Sender %s still in cooldown, skipping follow-up.", sender)
                    continue
                mark_replied(sender, thread_id=thread_id)
                result["replied"] += 1

            except Exception as exc:  # pragma: no cover - defensive loop guard
                logger.exception("Failed processing Gmail message %s.", message_id)
                result["errors"].append(str(exc))

        return JSONResponse(content=dict(result))

    except Exception as exc:  # pragma: no cover - unexpected Gmail failures
        logger.exception("Gmail inbox processing failed.")
        result["errors"].append(str(exc))
        return JSONResponse(content=dict(result), status_code=500)


@app.post("/gmail/process-inbox", response_model=None)
async def process_inbox(payload: Dict[str, Any] = Body(default_factory=dict)) -> JSONResponse | Dict[str, Any]:
    """Process the Gmail inbox via API invocation."""
    try:
        return await gmail_process_inbox(payload)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("process_inbox endpoint failed.")
        return {"processed": 0, "labeled": 0, "replied": 0, "errors": [repr(exc)]}


@app.post("/stores/add", status_code=201)
def stores_add(payload: StoreCreate):
    """Register a new store within the workspace registry."""
    try:
        public = add_store(payload)
        return public.model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _normalize_order_no(value: str) -> str:
    """Normalize an order number for consistent comparison."""
    return value.strip().upper()


def _looks_like_no_reply(email: str) -> bool:
    """Return True when the sender address looks like a no-reply inbox."""
    return bool(re.search(r"(no[-_]?reply|do[-_]?not[-_]?reply)", email, re.I))


@router_public.post("/support-request")
async def support_request(payload: SupportPayload, request: Request) -> Dict[str, Any]:
    """Handle a public support request with guarded automation paths."""
    client_ip = request.client.host if request.client else "unknown"

    if request.headers.get("referer", "").endswith("/pages/help"):
        logger.info("Support request originated from Shopify help form.")

    if _looks_like_no_reply(payload.email):
        logger.warning("Rejected support request from no-reply address %s.", payload.email)
        return {"ok": False, "error": "no-reply addresses are not accepted"}

    order_name = _normalize_order_no(payload.order_no)
    order = await get_order_by_name(order_name)
    if not order:
        logger.warning("Support request referenced missing order %s.", order_name)
        return {"ok": False, "error": "order_not_found"}

    order_email = (order.get("email") or "").strip().lower()
    if order_email != payload.email.strip().lower():
        logger.warning(
            "Email mismatch for order %s (payload %s vs order %s).",
            order_name,
            payload.email,
            order_email,
        )
        return {"ok": False, "error": "email_mismatch"}

    fulfillment_status = order.get("fulfillment_status")
    performed: Optional[str] = None
    details: Dict[str, Any] = {}

    try:
        if payload.action == "cancel":
            if fulfillment_status in (None, "unfulfilled"):
                details = await cancel_unfulfilled_order(order)
                performed = "cancelled"
            else:
                performed = "needs_human"
        elif payload.action == "address_change":
            if fulfillment_status in (None, "unfulfilled"):
                details = await update_order_address(
                    order,
                    {
                        "address1": payload.address1,
                        "address2": payload.address2,
                        "city": payload.city,
                        "province": payload.province,
                        "zip": payload.zip,
                        "country": payload.country or "US",
                    },
                )
                performed = "address_updated"
            else:
                performed = "needs_human"
        elif payload.action == "refund":
            performed = "needs_human"
        else:
            performed = "queued"
    except Exception as exc:  # pragma: no cover - Shopify actions
        logger.exception("Support request automation failed for order %s.", order_name)
        return {"ok": False, "error": str(exc)}

    subject = f"Oubon Support — {order_name} — {payload.action.replace('_', ' ').title()}"
    if performed == "cancelled":
        body = f"Hello — we’ve cancelled order {order_name}. You’ll see a void/refund confirmation shortly."
    elif performed == "address_updated":
        body = f"Hello — we’ve updated the shipping address for {order_name}."
    elif performed == "needs_human":
        body = f"Hello — thanks for your request about {order_name}. A specialist will review and follow up shortly."
    else:
        body = f"Hello — we’ve received your request for {order_name}. We’ll follow up shortly."

    try:
        await send_plain_email(
            to=payload.email,
            subject=subject,
            body=body + ("\n\nNote: " + payload.note if payload.note else ""),
        )
    except Exception as exc:  # pragma: no cover - Gmail edge cases
        logger.exception("Failed to send confirmation email for order %s.", order_name)

    logger.info(
        "Support request processed: action=%s performed=%s order=%s ip=%s",
        payload.action,
        performed,
        order_name,
        client_ip,
    )

    return {"ok": True, "performed": performed, "order": order_name, "details": details}


app.include_router(router_public)


@app.get("/ai/provider")
def ai_provider_probe() -> Dict[str, Any]:
    """Return the configured AI provider and a readiness probe."""
    settings = get_settings()
    provider = getattr(settings, "AI_PROVIDER", "openai")
    try:
        ai_client()
        return {"provider": provider, "ok": True, "error": None}
    except Exception as exc:  # pragma: no cover - provider failures
        logger.exception("AI provider probe failed.")
        return {"provider": provider, "ok": False, "error": str(exc)}


@app.post("/ai/preview")
async def ai_preview(payload: PreviewPayload) -> Dict[str, Any]:
    """Return a preview AI reply for manual inspection."""
    text, intent = await generate_reply(
        subject=payload.subject,
        body=payload.body,
        order_no=payload.order_no,
        tracking=payload.tracking,
    )
    return {"ok": True, "reply": text, "intent": intent}


@app.get("/time/quiet")
def time_quiet_probe() -> Dict[str, Any]:
    """Expose the quiet-hours state for observability and diagnostics."""
    return {"quiet_now": is_quiet_hours(), "tz": getattr(SETTINGS, "STORE_TIMEZONE", "America/Chicago")}


def daily_research() -> None:
    """Placeholder for daily research routines while enforcing AI quota usage."""
    quota = getattr(SETTINGS, "AI_DAILY_QUOTA", 0) or 0
    if not quota:
        return

    today = datetime.now().date().isoformat()
    row = conn.execute("SELECT used FROM ai_usage WHERE date = ?", (today,)).fetchone()
    used = (row["used"] if hasattr(row, "__getitem__") else row[0]) if row else 0
    if used >= quota:
        logger.info("Daily research skipped; quota %s already consumed.", quota)
        return

    conn.execute("UPDATE ai_usage SET used = ? WHERE date = ?", (used + 1, today))
    conn.commit()


def poll_inbox() -> None:
    """Worker executed by the scheduler to process the inbox at intervals."""
    try:
        logger.info("Polling inbox at %s (quiet=%s).", datetime.now(), is_quiet_hours())
        payload = {"auto_reply": True, "max_messages": 10, "cooldown_hours": 24}
        response = asyncio.run(process_inbox(payload))

        if isinstance(response, JSONResponse):
            content = json.loads(response.body.decode("utf-8"))
        elif isinstance(response, dict):
            content = response
        else:
            content = {}

        logger.info(
            "Poll result: processed=%s labeled=%s replied=%s errors=%s",
            content.get("processed", 0),
            content.get("labeled", 0),
            content.get("replied", 0),
            content.get("errors", []),
        )

        errors = content.get("errors") or []
        if errors:
            send_slack_alert("#ai-alerts", f"Gmail poll errors: {errors}")
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Inbox poll failed.")
        send_slack_alert("#ai-alerts", f"Gmail poll fail: {exc}")


def run_scheduler() -> None:
    """Run the schedule loop that triggers periodic inbox polling."""
    schedule.every(5).minutes.do(poll_inbox)
    while True:
        schedule.run_pending()
        time.sleep(1)


_SCHEDULER_STARTED = False


@app.on_event("startup")
def on_startup() -> None:
    """Initialize background workers when the API process launches."""
    global _SCHEDULER_STARTED
    logger.info("Oubon MailBot API starting.")
    if not _SCHEDULER_STARTED:
        Thread(daemon=True, target=run_scheduler).start()
        _SCHEDULER_STARTED = True


@app.on_event("shutdown")
def on_shutdown() -> None:
    """Log shutdown events for operational visibility."""
    logger.info("Oubon MailBot API shutting down.")
