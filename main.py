from __future__ import annotations
print("--- LOADING LATEST main.py ---")

# Runs Gmail inbox automation with cooldowns, hybrid hours, and AI auto-replies.
# Adds Shopify order lookup when an order ID is detected in the email.

import os
import re
import json
import base64
import datetime as dt
import time
import asyncio
import traceback, logging
from datetime import datetime
from threading import Thread
from urllib import request as urlreq
from urllib.parse import urlencode
from typing import Any, Dict, Optional

import schedule
from fastapi import APIRouter, Body, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr

from app.gmail_client import GmailClient, send_plain_email
from app.rules import match_label_for_message
from app.cooldown import is_on_cooldown, mark_replied
from app.ai_client import ai_client
from app.ai_reply import generate_reply
from app.time_utils import is_quiet_hours
from app.settings import get_settings
from app.shopify_client import (
    cancel_unfulfilled_order,
    get_order_by_name,
    update_order_address,
)
from app.store_registry import StoreCreate, add_store
from app.database import conn
from app.slack_notifier import send_slack_alert
import email.utils

logger = logging.getLogger("uvicorn.error")

app = FastAPI(title="Oubon MailBot", version="1.2")

SETTINGS = get_settings()
gmail = GmailClient(SETTINGS)

# Ensure AI usage tracking table exists (prevents quota overspending)
conn.execute(
    "CREATE TABLE IF NOT EXISTS ai_usage (date DATE PRIMARY KEY, used INT DEFAULT 0)"
)
today = datetime.now().date()
date_key = today.isoformat()
row = conn.execute("SELECT used FROM ai_usage WHERE date = ?", (date_key,)).fetchone()
if row is None:
    conn.execute("INSERT INTO ai_usage (date, used) VALUES (?, 0)", (date_key,))
    used_today = 0
else:
    used_today = row["used"] if hasattr(row, "__getitem__") else row[0]
conn.commit()

# ---- Helpers ---------------------------------------------------------------

ORDER_ID_RE = re.compile(r"\b(?:OU)?\d{5,}\b", re.IGNORECASE)
SIMPLE_QUIET_REPLY = (
    "Hello — thanks for reaching out! Our team is offline right now. "
    "We’ve got your message and will reply during business hours (7am–10pm CT)."
)


def _get_or_create_label_id(svc, name: str) -> str:
    """Fetch or create Gmail label by name."""
    resp = svc.users().labels().list(userId="me").execute()
    for lab in resp.get("labels", []):
        if lab["name"].lower() == name.lower():
            return lab["id"]
    body = {"name": name, "labelListVisibility": "labelShow", "messageListVisibility": "show"}
    lab = svc.users().labels().create(userId="me", body=body).execute()
    return lab["id"]


def _extract_text_from_payload(payload: Dict[str, Any]) -> str:
    """Best-effort plain text extraction from Gmail 'payload'."""
    if not payload:
        return ""
    # Simple body
    body = payload.get("body", {})
    data = body.get("data")
    if data:
        try:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
        except Exception:
            pass
    # Multipart text/plain
    for p in payload.get("parts", []) or []:
        mt = p.get("mimeType", "")
        if mt.startswith("text/plain"):
            try:
                return base64.urlsafe_b64decode(p.get("body", {}).get("data", "")).decode("utf-8", errors="ignore")
            except Exception:
                continue
    # Fallback to stripped HTML
    for p in payload.get("parts", []) or []:
        mt = p.get("mimeType", "")
        if mt.startswith("text/html"):
            try:
                html = base64.urlsafe_b64decode(p.get("body", {}).get("data", "")).decode("utf-8", errors="ignore")
                return re.sub(r"<[^>]+>", " ", html)
            except Exception:
                continue
    return ""


def _extract_order_id(subject: str, body: str) -> Optional[str]:
    """Find an order-like token (e.g., OU10001). Tweak the regex to your format."""
    text = f"{subject}\n{body}"
    m = ORDER_ID_RE.search(text)
    return m.group(0).upper() if m else None


def _shopify_lookup(order_name: str) -> Optional[Dict[str, Any]]:
    """
    Query Shopify Admin REST for an order by name (e.g., '#1001' or 'OU10001').
    Requires:
      - SETTINGS.SHOPIFY_STORE (e.g., 'rxxj7d-1i.myshopify.com')
      - SETTINGS.SHOPIFY_API_TOKEN (Admin API access token)
    """
    store = str(getattr(SETTINGS, "SHOPIFY_STORE", "") or "").strip()
    token = str(getattr(SETTINGS, "SHOPIFY_API_TOKEN", "") or "").strip()
    if not store or not token:
        logger.error("Shopify config missing: SHOPIFY_STORE or SHOPIFY_API_TOKEN")
        return None

    # Shopify 'name' typically includes leading '#'. Try both.
    candidates = [order_name, order_name.lstrip("#")] if order_name.startswith("#") else [order_name, f"#{order_name}"]

    for name in candidates:
        try:
            qs = urlencode({"name": name})
            url = f"https://{store}/admin/api/2024-10/orders.json?{qs}"
            req = urlreq.Request(url, headers={
                "X-Shopify-Access-Token": token,
                "Content-Type": "application/json",
                "Accept": "application/json",
            })
            with urlreq.urlopen(req, timeout=15) as resp:
                payload = json.loads(resp.read().decode("utf-8", errors="ignore"))
            orders = payload.get("orders", [])
            if not orders:
                continue
            o = orders[0]

            fulfillments = o.get("fulfillments", []) or []
            tracking = []
            for f in fulfillments:
                for t in f.get("tracking_numbers", []) or []:
                    tracking.append({
                        "number": t,
                        "url": (f.get("tracking_urls") or [None])[0] if f.get("tracking_urls") else None,
                        "company": f.get("tracking_company"),
                    })

            shipping_addr = o.get("shipping_address") or {}
            line_items = [
                {"title": li.get("title"), "sku": li.get("sku"), "qty": li.get("quantity")}
                for li in (o.get("line_items") or [])
            ]

            info = {
                "name": o.get("name"),  # e.g., #1001
                "id": o.get("id"),
                "email": o.get("email"),
                "created_at": o.get("created_at"),
                "financial_status": o.get("financial_status"),
                "fulfillment_status": o.get("fulfillment_status"),
                "current_total_price": o.get("current_total_price"),
                "shipping_address": {
                    "city": shipping_addr.get("city"),
                    "province": shipping_addr.get("province"),
                    "country": shipping_addr.get("country"),
                    "zip": shipping_addr.get("zip"),
                },
                "line_items": line_items,
                "tracking": tracking,
            }
            return info
        except Exception:
            # Keep mail flow resilient
            continue
    return None


# ---- Endpoints -------------------------------------------------------------


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


async def gmail_process_inbox(payload: Dict[str, Any]) -> JSONResponse:
    # Respect payload & REPLY_ALWAYS flag (no hard-coded True)
    auto_reply = bool(payload.get("auto_reply", False)) or bool(getattr(SETTINGS, "REPLY_ALWAYS", False))
    max_messages = int(payload.get("max_messages", 5))
    cooldown_hours = int(payload.get("cooldown_hours", 24))

    result = {"processed": 0, "labeled": 0, "replied": 0, "errors": [], "last_label": None}

    try:
        svc = gmail.service()
        replied_label_id = _get_or_create_label_id(svc, "Replied")

        resp = svc.users().messages().list(
            userId="me", q="in:inbox -label:Replied", maxResults=max_messages
        ).execute()
        messages = resp.get("messages", [])

        for msg in messages:
            msg_id = msg["id"]
            try:
                full_msg = svc.users().messages().get(userId="me", id=msg_id, format="full").execute()
                thread_id = full_msg.get("threadId")
                headers = {h["name"].lower(): h["value"] for h in full_msg.get("payload", {}).get("headers", [])}
                subject = headers.get("subject", "(no subject)")
                sender = headers.get("from", "unknown")
                msg_label_ids = set(full_msg.get("labelIds", []))
                if replied_label_id in msg_label_ids:
                    logger.info(f"[Skip] Already replied to msg {msg_id}")
                    continue
                # --- Skip rules ---
                parsed = email.utils.parseaddr(sender or "")[1].lower()
                if any(x in parsed for x in ["no-reply", "donotreply", "noreply"]):
                    logger.info(f"[Skip] Ignoring auto sender: {parsed}")
                    continue

                # Skip messages that are replies (e.g., Re:, Fwd:, etc.)
                if subject.lower().startswith(("re:", "fw:", "fwd:")):
                    logger.info(f"[Skip] Ignoring reply thread: {subject}")
                    continue
                text_content = _extract_text_from_payload(full_msg.get("payload", {}))

                result["processed"] += 1

                # Label based on rules
                label = match_label_for_message(subject, text_content)
                if label:
                    label_id = _get_or_create_label_id(svc, label)
                    svc.users().messages().modify(
                        userId="me", id=msg_id, body={"addLabelIds": [label_id]}
                    ).execute()
                    result["labeled"] += 1
                    result["last_label"] = label
                    logger.info(f"[Label] Applied {label} to msg {msg_id}")

                if not auto_reply:
                    logger.info(f"[Reply Skip] Auto-reply off for msg {msg_id}")
                    continue

                if is_on_cooldown(sender, cooldown_hours, thread_id=thread_id):
                    logger.info(f"[Reply Skip] Cooldown for sender {sender} for msg {msg_id}")
                    continue

                try:
                    reply_body, detected_intent = await generate_reply(subject=subject, body=text_content)
                except Exception as exc:
                    tb = traceback.format_exc()
                    err = f"AI generation failed for {sender}: {exc}\n{tb}"
                    logger.error(err)
                    send_slack_alert("#ai-alerts", err)
                    reply_body = None
                    detected_intent = None

                if detected_intent:
                    result["last_intent"] = detected_intent

                if reply_body:
                    reply_subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"
                    gmail.send_simple_email(to=sender, subject=reply_subject, body=reply_body)
                    logger.info(f"[Reply] Sent AI-crafted reply for msg {msg_id}")
                else:
                    # Fall back to soft reply if AI failed
                    reply_body = SIMPLE_QUIET_REPLY
                    reply_subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"
                    gmail.send_simple_email(to=sender, subject=reply_subject, body=reply_body)
                    logger.info(f"[Reply] Sent fallback soft reply for msg {msg_id} after AI error")

                # Mark replied + label
                svc.users().messages().modify(
                    userId="me", id=msg_id, body={"addLabelIds": [replied_label_id]}
                ).execute()
                mark_replied(sender, thread_id=thread_id)
                result["replied"] += 1

            except Exception as e:
                tb = traceback.format_exc()
                logger.error(f"[Process Error] msg={msg_id} {e}\n{tb}")
                result["errors"].append(str(e))

        return JSONResponse(content=dict(result))

    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"[Endpoint Error] {e}\n{tb}")
        result["errors"].append(str(e))
        return JSONResponse(content=dict(result), status_code=500)


@app.post("/gmail/process-inbox")
async def process_inbox(payload: dict = Body(default={})):
    try:
        return await gmail_process_inbox(payload)
    except Exception as e:
        logging.exception("process_inbox failed: %s", e)
        return {"processed": 0, "labeled": 0, "replied": 0, "errors": [repr(e)]}


@app.post("/stores/add", status_code=201)
def stores_add(payload: StoreCreate):
    try:
        public = add_store(payload)
        return public.model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


router_public = APIRouter(prefix="/public", tags=["public"])


class SupportPayload(BaseModel):
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


def _normalize_order_no(s: str) -> str:
    return s.strip().upper()


def _looks_like_no_reply(email: str) -> bool:
    return bool(re.search(r"(no[-_]?reply|do[-_]?not[-_]?reply)", email, re.I))


@router_public.post("/support-request")
async def support_request(p: SupportPayload, request: Request):
    client_ip = request.client.host if request.client else "unknown"

    if _looks_like_no_reply(p.email):
        return {"ok": False, "error": "no-reply addresses are not accepted"}

    order_name = _normalize_order_no(p.order_no)
    order = await get_order_by_name(order_name)

    if not order:
        return {"ok": False, "error": "order_not_found"}

    order_email = (order.get("email") or "").strip().lower()
    if order_email != p.email.strip().lower():
        return {"ok": False, "error": "email_mismatch"}

    fulfillment_status = order.get("fulfillment_status")
    performed = None
    details: Dict[str, Any] = {}

    try:
        if p.action == "cancel":
            if fulfillment_status in (None, "unfulfilled"):
                details = await cancel_unfulfilled_order(order)
                performed = "cancelled"
            else:
                performed = "needs_human"
        elif p.action == "address_change":
            if fulfillment_status in (None, "unfulfilled"):
                details = await update_order_address(
                    order,
                    {
                        "address1": p.address1,
                        "address2": p.address2,
                        "city": p.city,
                        "province": p.province,
                        "zip": p.zip,
                        "country": p.country or "US",
                    },
                )
                performed = "address_updated"
            else:
                performed = "needs_human"
        elif p.action == "refund":
            performed = "needs_human"
        else:
            performed = "queued"
    except Exception as e:
        logging.exception("support_request error", exc_info=e)
        return {"ok": False, "error": str(e)}

    subject = f"Oubon Support — {order_name} — {p.action.replace('_', ' ').title()}"
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
            to=p.email,
            subject=subject,
            body=body + ("\n\nNote: " + p.note if p.note else ""),
        )
    except Exception:
        logging.exception("Failed to send confirmation email")

    logging.info(
        "[support_request] action=%s performed=%s order=%s ip=%s",
        p.action,
        performed,
        order_name,
        client_ip,
    )

    return {"ok": True, "performed": performed, "order": order_name, "details": details}


app.include_router(router_public)


@app.get("/ai/provider")
def ai_provider_probe():
    s = get_settings()
    p = getattr(s, "AI_PROVIDER", "openai")
    # Try to instantiate client so we catch missing keys early
    try:
        _ = ai_client()
        ok = True
        error = None
    except Exception as e:
        ok = False
        error = str(e)
    return {"provider": p, "ok": ok, "error": error}


class PreviewPayload(BaseModel):
    subject: str
    body: str
    order_no: str | None = None
    tracking: str | None = None


@app.post("/ai/preview")
async def ai_preview(p: PreviewPayload):
    text, intent = await generate_reply(
        subject=p.subject,
        body=p.body,
        order_no=p.order_no,
        tracking=p.tracking,
    )
    return {"ok": True, "reply": text, "intent": intent}


@app.get("/time/quiet")
def time_quiet_probe():
    return {"quiet_now": is_quiet_hours(), "tz": getattr(SETTINGS, "STORE_TIMEZONE", "America/Chicago")}


def daily_research() -> None:
    """Placeholder daily research routine with AI quota enforcement."""
    quota = getattr(SETTINGS, "AI_DAILY_QUOTA", 0) or 0
    if quota:
        today = datetime.now().date()
        date_key = today.isoformat()
        row = conn.execute("SELECT used FROM ai_usage WHERE date = ?", (date_key,)).fetchone()
        used = (row["used"] if hasattr(row, "__getitem__") else row[0]) if row else 0
        if used >= quota:
            return
        used += 1
        conn.execute("UPDATE ai_usage SET used = ? WHERE date = ?", (used, date_key))
        conn.commit()
    # Future: fetch trends, notify Slack, etc.


def poll_inbox() -> None:
    """Background task to poll Gmail and auto-reply on a schedule."""
    try:
        logger.info(f"[Poll Start] Checking inbox at {datetime.now()}. Quiet={is_quiet_hours()}")
        payload = {"auto_reply": True, "max_messages": 10, "cooldown_hours": 24}
        response = asyncio.run(process_inbox(payload))
        if isinstance(response, JSONResponse):
            content = json.loads(response.body.decode("utf-8"))
        elif isinstance(response, dict):
            content = response
        else:
            content = {}
        logger.info(
            "[Poll Result] Processed: {processed}, Labeled: {labeled}, Replied: {replied}, Errors: {errors}".format(
                processed=content.get("processed", 0),
                labeled=content.get("labeled", 0),
                replied=content.get("replied", 0),
                errors=content.get("errors", []),
            )
        )
        errors = content.get("errors") or []
        if errors:
            send_slack_alert("#ai-alerts", f"Gmail poll errors: {errors}")
    except Exception as exc:
        tb = traceback.format_exc()
        logger.error(f"[Poll Error] {exc}\n{tb}")
        send_slack_alert("#ai-alerts", f"Gmail poll fail: {exc}")


def run_scheduler() -> None:
    schedule.every(5).minutes.do(poll_inbox)
    while True:
        schedule.run_pending()
        time.sleep(1)


_SCHEDULER_STARTED = False


# ---- Lifecycle logs --------------------------------------------------------


@app.on_event("startup")
def on_startup():
    global _SCHEDULER_STARTED
    print(f"[{dt.datetime.now()}] Oubon MailBot API started.")
    # Start scheduler only once (avoids duplicates under --reload)
    if not _SCHEDULER_STARTED:
        Thread(daemon=True, target=run_scheduler).start()
        _SCHEDULER_STARTED = True


@app.on_event("shutdown")
def on_shutdown():
    print(f"[{dt.datetime.now()}] Oubon MailBot API shutting down.")
