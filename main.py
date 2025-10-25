# main.py — Oubon MailBot
from __future__ import annotations
import base64, json, os, re
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import Depends, FastAPI
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from app.ai_reply import draft_reply
from app.db import init_db
from app.gmail_client import GmailClient
from app.rules import classify_message, get_rule_for_tags
from app.settings import Settings, get_settings

app = FastAPI(title="Oubon MailBot", version="0.1.0")

# ---------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------
def get_gmail_client() -> GmailClient:
    return GmailClient(Settings())

def _svc(gc: GmailClient):
    cand = getattr(gc, "_service", None)
    if callable(cand):
        return cand()
    cand = getattr(gc, "service", None)
    return cand() if callable(cand) else cand

# ---------------------------------------------------------------
# Startup / Health
# ---------------------------------------------------------------
@app.on_event("startup")
async def startup_event():
    await init_db()

    # Initialize follow-up tracking database
    from app.models import init_followup_db
    settings = get_settings()
    init_followup_db(settings.database_url)

    # Initialize analytics database
    from app.analytics import init_analytics_db
    init_analytics_db(settings.database_url)

    # Start background email checker
    from app.scheduler import start_scheduler
    start_scheduler()

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/dashboard")
async def dashboard():
    """Analytics dashboard with charts and visualizations."""
    return FileResponse("static/dashboard.html")

# ---------------------------------------------------------------
# Analytics Dashboard
# ---------------------------------------------------------------
@app.get("/analytics/daily")
def analytics_daily(settings: Settings = Depends(get_settings)):
    """Get today's email processing statistics."""
    from app.analytics import Analytics
    analytics = Analytics(settings.database_url)
    return analytics.get_daily_stats()

@app.get("/analytics/weekly")
def analytics_weekly(settings: Settings = Depends(get_settings)):
    """Get last 7 days of statistics."""
    from app.analytics import Analytics
    analytics = Analytics(settings.database_url)
    return analytics.get_weekly_stats()

@app.get("/analytics/costs")
def analytics_costs(days: int = 30, settings: Settings = Depends(get_settings)):
    """Get AI cost breakdown for the last N days."""
    from app.analytics import Analytics
    analytics = Analytics(settings.database_url)
    return analytics.get_cost_breakdown(days=days)

@app.get("/analytics/labels")
def analytics_labels(days: int = 7, settings: Settings = Depends(get_settings)):
    """Get most common email categories."""
    from app.analytics import Analytics
    analytics = Analytics(settings.database_url)
    return analytics.get_top_labels(days=days)

@app.get("/analytics/cache-stats")
def cache_stats():
    """Get response cache statistics."""
    from app.response_cache import get_cache_stats
    return get_cache_stats()

# ---------------------------------------------------------------
# OAuth (if reauthorization needed)
# ---------------------------------------------------------------
@app.get("/auth/url")
def auth_url(settings: Settings = Depends(get_settings)):
    gc = GmailClient(settings)
    return {"auth_url": gc.build_auth_url()}

@app.get("/oauth2callback")
def oauth_callback(code: str, settings: Settings = Depends(get_settings)):
    gc = GmailClient(settings)
    gc.exchange_code_for_tokens(code)
    return RedirectResponse(url="/docs")

# ---------------------------------------------------------------
# Gmail ingest + send demo
# ---------------------------------------------------------------
class IngestRequest(BaseModel):
    max_results: int = 5

@app.post("/gmail/ingest")
def gmail_ingest(req: IngestRequest, settings: Settings = Depends(get_settings)):
    gc = GmailClient(settings)
    threads = gc.fetch_threads(max_results=req.max_results)
    return {"ingested_threads": len(threads)}

class SendRequest(BaseModel):
    to: str
    subject: str
    body: str

@app.post("/gmail/send-demo")
def gmail_send_demo(req: SendRequest, settings: Settings = Depends(get_settings)):
    gc = GmailClient(settings)
    gc.send_simple_email(to=req.to, subject=req.subject, body=req.body)
    return {"status": "sent"}

# ---------------------------------------------------------------
# Data files (rules/templates)
# ---------------------------------------------------------------
DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
RULES_PATH = DATA_DIR / "rules.json"
TPL_PATH = DATA_DIR / "templates.json"

class RuleItem(BaseModel):
    if_any: List[str]
    apply_label: str
    auto_reply_template: Optional[str] = None
    auto_reply: Optional[bool] = None

class RulesPayload(BaseModel):
    rules: List[RuleItem]

class TemplatePayload(BaseModel):
    id: str
    subject: str
    body: str

DEFAULT_RULES: Dict[str, Any] = {
    "rules": [
        {"if_any": ["refund", "return", "broken", "damaged", "warranty", "complaint"],
         "apply_label": "Support", "auto_reply_template": "support_default", "auto_reply": True},
        {"if_any": ["order","package","delivery","tracking","shipment","arrived",
                    "missing","unreceived","not received","not arrived","delayed"],
         "apply_label": "Orders", "auto_reply_template": "order_missing", "auto_reply": True},
        {"if_any": ["press","investor","wholesale","partnership"],
         "apply_label": "VIP"},
        {"if_any": ["mailer-daemon","delivery status notification","failure notice",
                    "postmaster","no-reply","do-not-reply"],
         "apply_label": "Admin"}
    ]
}

DEFAULT_TPLS: Dict[str, Any] = {
    "support_default": {
        "subject": "We received your message",
        "body": ("<p>Hi there,</p><p>We've received your message and opened a ticket "
                 "(#{{ticket_id}}). A team member will reply within 1 business day.</p>"
                 "<p>— <b>Oubon Shop Support</b></p>")
    },
    "order_missing": {
        "subject": "We're on it – order {{order_id}}",
        "body": ("<p>Hi {{name}},</p><p>Sorry your package hasn't arrived. "
                 "Please reply with your order number and we'll investigate right away.</p>"
                 "<p>— Oubon Shop Support</p>")
    },
}

def _load_rules() -> Dict[str, Any]:
    if RULES_PATH.exists():
        return json.loads(RULES_PATH.read_text(encoding="utf-8"))
    return DEFAULT_RULES

def _save_rules(data: Dict[str, Any]) -> None:
    RULES_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def _load_templates() -> Dict[str, Any]:
    if TPL_PATH.exists():
        return json.loads(TPL_PATH.read_text(encoding="utf-8"))
    return DEFAULT_TPLS

def _save_templates(data: Dict[str, Any]) -> None:
    TPL_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

# ---------------------------------------------------------------
# Template + Rules endpoints
# ---------------------------------------------------------------
@app.post("/templates/upsert")
def templates_upsert(payload: TemplatePayload):
    tpls = _load_templates()
    tpls[payload.id] = {"subject": payload.subject, "body": payload.body}
    _save_templates(tpls)
    return {"saved": payload.id}

@app.get("/templates/list")
def templates_list():
    return _load_templates()

@app.post("/rules/set")
def set_rules(payload: RulesPayload):
    data = {"rules": [r.dict() for r in payload.rules]}
    _save_rules(data)
    return {"saved": len(payload.rules)}

@app.get("/rules/preview")
def rules_preview(subject: str, body: str):
    return {"tags": classify_message(subject, body)}

# ---------------------------------------------------------------
# Gmail label management
# ---------------------------------------------------------------
class EnsureLabelsPayload(BaseModel):
    labels: List[str]

@app.post("/gmail/ensure-labels")
def ensure_labels(payload: EnsureLabelsPayload):
    gc = get_gmail_client()
    svc = _svc(gc)
    existing = svc.users().labels().list(userId="me").execute().get("labels", [])
    have = {l["name"] for l in existing}
    to_create = [n for n in payload.labels if n not in have]
    for name in to_create:
        svc.users().labels().create(
            userId="me",
            body={"name": name, "labelListVisibility": "labelShow", "messageListVisibility": "show"},
        ).execute()
    return {"created": to_create, "have": sorted(list(have | set(to_create)))}

# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------
def _text_from_message(msg: Dict[str, Any]) -> str:
    payload = msg.get("payload", {}) or {}
    parts = payload.get("parts") or []
    chunks = []
    for p in parts:
        if p.get("mimeType") == "text/plain" and p.get("body", {}).get("data"):
            chunks.append(base64.urlsafe_b64decode(p["body"]["data"]).decode("utf-8", errors="ignore"))
    return "\n".join(chunks) if chunks else msg.get("snippet", "")

def parse_order_id(subject: str, body: str) -> Optional[str]:
    text = f"{subject}\n{body}"
    m = re.search(r"\bOU\d{5,}\b", text, flags=re.I)
    if m: return m.group(0).upper()
    m = re.search(r"\border\s*#\s*(\d{5,})\b", text, flags=re.I) or re.search(r"#\s*(\d{5,})\b", text, flags=re.I)
    if m: return m.group(1)
    m = re.search(r"\b(\d{5,})\b", text)
    return m.group(1) if m else None

def lookup_order(order_id: str, settings: Settings = None) -> Optional[dict]:
    if settings is None:
        settings = get_settings()

    # Return None if Shopify not configured
    if not settings.SHOPIFY_STORE or not settings.SHOPIFY_API_TOKEN:
        return None

    import requests
    url = f"https://{settings.SHOPIFY_STORE}/admin/api/2024-10/orders.json?name={order_id}"
    headers = {"X-Shopify-Access-Token": settings.SHOPIFY_API_TOKEN}
    res = requests.get(url, headers=headers)
    data = res.json()
    if data.get("orders"):
        order = data["orders"][0]
        return {
            "order_id": order["name"],
            "status": order["fulfillment_status"] or "Processing",
            "carrier": order.get("shipping_lines", [{}])[0].get("title", ""),
            "tracking": order.get("shipping_lines", [{}])[0].get("tracking_number", ""),
            "last_update": order["updated_at"],
        }
    return None

def _match_label(body: str, subject: str, rules: Dict[str, Any]) -> Optional[RuleItem]:
    text = f"{subject}\n{body}".lower()
    for r in rules.get("rules", []):
        for kw in r.get("if_any", []):
            if kw.lower() in text:
                return RuleItem(**r)
    return None

def _extract_name(from_hdr: str) -> str:
    m = re.match(r'^\s*"?(?P<name>[^"<]+?)"?\s*<(?P<email>[^>]+)>', from_hdr or "")
    if m:
        nm = (m.group("name") or "").strip()
        if nm: return nm.split()[0]
        return (m.group("email") or "").split("@", 1)[0]
    return (from_hdr or "").split("@", 1)[0].replace("<","").replace(">","").strip() or "there"

# ---------------------------------------------------------------
# Clean endpoint (no 'from_hdr' bug)
# ---------------------------------------------------------------
class ProcessPayload(BaseModel):
    auto_reply: bool = False
    max_messages: int = 25

@app.post("/gmail/process-inbox2")
def process_inbox2(payload: ProcessPayload):
    gc = get_gmail_client()
    svc = _svc(gc)
    rules = _load_rules()
    tpls  = _load_templates()

    q = ('in:inbox (is:unread OR "order" OR "package" OR "delivery" OR "tracking" '
         'OR "shipment" OR "arrived" OR "missing" OR "unreceived" OR "not received" OR "not arrived")')
    res = svc.users().messages().list(userId="me", q=q, maxResults=payload.max_messages).execute()
    msgs = res.get("messages", []) or []
    processed = labeled = replied = 0

    labels = svc.users().labels().list(userId="me").execute().get("labels", [])
    name_to_id = {l["name"]: l["id"] for l in labels}

    def _ensure_label(name: str) -> str:
        if name in name_to_id:
            return name_to_id[name]
        created = svc.users().labels().create(
            userId="me",
            body={"name": name, "labelListVisibility": "labelShow", "messageListVisibility": "show"},
        ).execute()
        name_to_id[name] = created["id"]
        return created["id"]

    for m in msgs:
        full = svc.users().messages().get(userId="me", id=m["id"], format="full").execute()
        headers  = {h["name"].lower(): h["value"] for h in full.get("payload", {}).get("headers", [])}
        subj, from_hdr = headers.get("subject", ""), headers.get("from", "")
        body = _text_from_message(full)
        rule = _match_label(body, subj, rules)
        if not rule:
            processed += 1
            continue

        lid = _ensure_label(rule.apply_label)
        svc.users().messages().modify(userId="me", id=m["id"],
            body={"addLabelIds": [lid], "removeLabelIds": []}).execute()
        labeled += 1

        if payload.auto_reply and (rule.auto_reply or rule.auto_reply_template):
            maddr = re.search(r"<([^>]+)>", from_hdr)
            to_addr = maddr.group(1) if maddr else from_hdr
            friendly = _extract_name(from_hdr)

            if rule.apply_label.lower() == "orders":
                order_id = parse_order_id(subj, body)
                info = lookup_order(order_id) if order_id else None
                if info:
                    subject_out = f"Update on order {info['order_id']}"
                    lines = [f"Hi {friendly},", "", f"Status: {info.get('status','Unknown')}"]
                    if info.get("carrier") and info.get("tracking"):
                        lines += [f"Carrier: {info['carrier']}", f"Tracking: {info['tracking']}"]
                    if info.get("last_update"): lines.append(f"Last update: {info['last_update']}")
                    lines += ["", "— Oubon Shop Support"]
                    try:
                        gc.send_simple_email(to=to_addr, subject=subject_out, body="\n".join(lines))
                        replied += 1
                    except Exception: pass
                else:
                    tpl = tpls.get(rule.auto_reply_template) or DEFAULT_TPLS.get(rule.auto_reply_template or "")
                    if tpl:
                        try:
                            gc.send_simple_email(
                                to=to_addr,
                                subject=f"Re: {subj}" if subj else "Thanks for your message",
                                body=tpl["body"]
                                    .replace("{{ticket_id}}", full.get("id",""))
                                    .replace("{{name}}", friendly),
                            )
                            replied += 1
                        except Exception: pass
            else:
                tpl = tpls.get(rule.auto_reply_template) or DEFAULT_TPLS.get(rule.auto_reply_template or "")
                if tpl:
                    try:
                        gc.send_simple_email(
                            to=to_addr,
                            subject=f"Re: {subj}" if subj else "Thanks for your message",
                            body=tpl["body"]
                                .replace("{{ticket_id}}", full.get("id",""))
                                .replace("{{name}}", friendly),
                        )
                        replied += 1
                    except Exception: pass
        processed += 1

    return {"processed": processed, "labeled": labeled, "replied": replied}

# ---------------------------------------------------------------
# Debug Peek
# ---------------------------------------------------------------
@app.get("/debug/peek")
def debug_peek(limit: int = 5):
    gc = get_gmail_client()
    svc = _svc(gc)
    q = ('in:inbox (is:unread OR "order" OR "package" OR "delivery" OR "tracking" '
         'OR "shipment" OR "arrived" OR "missing" OR "unreceived" OR "not received" OR "not arrived")')
    res = svc.users().messages().list(userId="me", q=q, maxResults=limit).execute()
    msgs = res.get("messages", []) or []
    labels = svc.users().labels().list(userId="me").execute().get("labels", [])
    name_to_id = {l["name"]: l["id"] for l in labels}
    out = []
    for m in msgs:
        full = svc.users().messages().get(userId="me", id=m["id"], format="full").execute()
        headers = {h["name"].lower(): h["value"] for h in full.get("payload", {}).get("headers", [])}
        subj, body = headers.get("subject", ""), _text_from_message(full).strip()[:400]
        rule = _match_label(body, subj, _load_rules())
        out.append({
            "id": m["id"], "subject": subj, "preview": body,
            "rule": None if not rule else {
                "apply_label": rule.apply_label,
                "auto_reply_template": rule.auto_reply_template,
                "auto_reply": rule.auto_reply},
            "orders_label_id": name_to_id.get("Orders"),
        })
    return {"q": q, "count": len(out), "items": out}

# ---------------------------------------------------------------
# AI reply draft
# ---------------------------------------------------------------
class DraftReq(BaseModel):
    subject: str
    body: str

# -------------------------------------------------------------------
# Gmail inbox processor (fixed JSON-body version)
# -------------------------------------------------------------------
@app.post("/gmail/process-inbox")
def process_inbox(payload: ProcessPayload):
    gc = get_gmail_client()
    svc = _svc(gc)
    rules = _load_rules()
    tpls  = _load_templates()

    q = (
        'in:inbox (is:unread OR "order" OR "package" OR "delivery" OR "tracking" '
        'OR "shipment" OR "arrived" OR "missing" OR "unreceived" OR "not received" OR "not arrived")'
    )

    res = svc.users().messages().list(userId="me", q=q, maxResults=payload.max_messages).execute()
    msgs = res.get("messages", []) or []

    processed = labeled = replied = 0
    labels = svc.users().labels().list(userId="me").execute().get("labels", [])
    name_to_id = {l["name"]: l["id"] for l in labels}

    def _ensure_label(name: str) -> str:
        if name in name_to_id:
            return name_to_id[name]
        created = svc.users().labels().create(
            userId="me",
            body={"name": name, "labelListVisibility": "labelShow", "messageListVisibility": "show"},
        ).execute()
        name_to_id[name] = created["id"]
        return created["id"]

    for m in msgs:
        full = svc.users().messages().get(userId="me", id=m["id"], format="full").execute()
        headers = {h["name"].lower(): h["value"] for h in full.get("payload", {}).get("headers", [])}
        subj = headers.get("subject", "")
        from_hdr = headers.get("from", "")
        body = _text_from_message(full)

        rule = _match_label(body, subj, rules)
        if rule:
            lid = _ensure_label(rule.apply_label)
            svc.users().messages().modify(
                userId="me", id=m["id"], body={"addLabelIds": [lid], "removeLabelIds": []}
            ).execute()
            labeled += 1

            if payload.auto_reply:
                maddr = re.search(r"<([^>]+)>", from_hdr)
                to_addr = maddr.group(1) if maddr else from_hdr
                friendly = _extract_name(from_hdr)

                if rule.apply_label.lower() == "orders":
                    order_id = parse_order_id(subj, body)
                    info = lookup_order(order_id) if order_id else None
                    if info:
                        subject_out = f"Update on order {info['order_id']}"
                        lines = [f"Hi {friendly},", "", f"Status: {info.get('status', 'Unknown')}"]
                        if info.get("carrier") and info.get("tracking"):
                            lines.append(f"Carrier: {info['carrier']}")
                            lines.append(f"Tracking: {info['tracking']}")
                        if info.get("last_update"):
                            lines.append(f"Last update: {info['last_update']}")
                        lines.append("")
                        lines.append("— Oubon Support")
                        try:
                            gc.send_simple_email(to=to_addr, subject=subject_out, body="\n".join(lines))
                            replied += 1
                        except Exception:
                            pass
                    else:
                        tpl = tpls.get(rule.auto_reply_template) or DEFAULT_TPLS.get(rule.auto_reply_template or "")
                        if tpl:
                            try:
                                gc.send_simple_email(
                                    to=to_addr,
                                    subject=f"Re: {subj}" if subj else "Thanks for your message",
                                    body=tpl["body"]
                                        .replace("{{ticket_id}}", full.get("id", ""))
                                        .replace("{{name}}", friendly),
                                )
                                replied += 1
                            except Exception:
                                pass
                else:
                    tpl = tpls.get(rule.auto_reply_template) or DEFAULT_TPLS.get(rule.auto_reply_template or "")
                    if tpl:
                        try:
                            gc.send_simple_email(
                                to=to_addr,
                                subject=f"Re: {subj}" if subj else "Thanks for your message",
                                body=tpl["body"]
                                    .replace("{{ticket_id}}", full.get("id", ""))
                                    .replace("{{name}}", friendly),
                            )
                            replied += 1
                        except Exception:
                            pass
        processed += 1

    return {"processed": processed, "labeled": labeled, "replied": replied}
@app.post("/ai/reply-draft")
def ai_reply_draft(req: DraftReq, settings: Settings = Depends(get_settings)):
    reply = draft_reply(req.subject, req.body, settings=settings)
    return {"draft": reply}

# ---------------------------------------------------------------
# Smart Reply System (TEST ENDPOINT)
# ---------------------------------------------------------------
@app.post("/gmail/smart-process")
def smart_process_inbox(payload: ProcessPayload, settings: Settings = Depends(get_settings)):
    """
    SMART auto-reply system with:
    - Operating hours detection (AI during hours, templates off-hours)
    - Automatic order lookup via Shopify
    - Automated refund processing
    - Enhanced tracking responses
    """
    from app.email_processor import EmailProcessor

    processor = EmailProcessor(settings)
    rules = _load_rules()
    templates = _load_templates()

    result = processor.process_inbox(
        auto_reply=payload.auto_reply,
        max_messages=payload.max_messages,
        rules=rules,
        templates=templates,
    )

    return result


# ---------------------------------------------------------------
# Gmail Push Notifications (Pub/Sub Webhook)
# ---------------------------------------------------------------
from fastapi import Request, BackgroundTasks
from app.gmail_watch import GmailWatchManager

@app.post("/gmail/pubsub/webhook")
async def gmail_pubsub_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    settings: Settings = Depends(get_settings)
):
    """
    Webhook endpoint for Gmail Pub/Sub push notifications.

    Google Cloud Pub/Sub calls this endpoint when new emails arrive.
    This triggers automatic email processing in the background.
    """
    try:
        # Parse Pub/Sub message
        body = await request.json()

        # Pub/Sub sends messages in this format:
        # {
        #   "message": {
        #     "data": "base64-encoded-data",
        #     "messageId": "...",
        #     "publishTime": "..."
        #   },
        #   "subscription": "..."
        # }

        message = body.get("message", {})
        message_id = message.get("messageId", "unknown")

        print(f"📧 Gmail push notification received: {message_id}")

        # Process emails in background (don't block the webhook response)
        background_tasks.add_task(process_emails_background, settings)

        # Return 200 immediately so Pub/Sub knows we received it
        return {"status": "received", "message_id": message_id}

    except Exception as e:
        print(f"❌ Error processing Pub/Sub webhook: {e}")
        # Still return 200 to avoid Pub/Sub retries
        return {"status": "error", "error": str(e)}


def process_emails_background(settings: Settings):
    """Background task to process new emails."""
    try:
        from app.email_processor import EmailProcessor

        processor = EmailProcessor(settings)
        rules = _load_rules()
        templates = _load_templates()

        result = processor.process_inbox(
            auto_reply=True,
            max_messages=10,  # Process recent emails
            rules=rules,
            templates=templates,
        )

        print(f"✅ Processed {result['processed']} emails, replied to {result['replied']}")

    except Exception as e:
        print(f"❌ Error in background email processing: {e}")


@app.post("/gmail/watch/start")
def start_gmail_watch(settings: Settings = Depends(get_settings)):
    """Start Gmail push notifications (set up watch)."""
    manager = GmailWatchManager(settings)
    return manager.start_watch()


@app.post("/gmail/watch/stop")
def stop_gmail_watch(settings: Settings = Depends(get_settings)):
    """Stop Gmail push notifications."""
    manager = GmailWatchManager(settings)
    return manager.stop_watch()


@app.get("/gmail/watch/status")
def gmail_watch_status(settings: Settings = Depends(get_settings)):
    """Check Gmail watch configuration status."""
    manager = GmailWatchManager(settings)
    return manager.get_watch_status()

# ---------------------------------------------------------------
# Mount static files (must be last)
# ---------------------------------------------------------------
app.mount("/static", StaticFiles(directory="static"), name="static")
