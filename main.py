# main.py — Oubon MailBot
from __future__ import annotations
import base64, json, os, re
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import Depends, FastAPI
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from app.ai_reply import draft_reply
from app.db import init_db
from app.gmail_client import GmailClient
from app.rules import classify_message, get_rule_for_tags
from app.settings import Settings, get_settings
from ospra_os.tiktok.routes import router as tiktok_router

# use app/.env via Settings()
settings = Settings()

app = FastAPI(title="Oubon MailBot", version="0.1.0")
app.include_router(tiktok_router)

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

@app.get("/health")
async def health():
    return {"status": "ok"}

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
        "body": ("<p>Hi there,</p><p>We’ve received your message and opened a ticket "
                 "(#{{ticket_id}}). A team member will reply within 1 business day.</p>"
                 "<p>— <b>Oubon Support</b></p>")
    },
    "order_missing": {
        "subject": "We’re on it – order {{order_id}}",
        "body": ("<p>Hi {{name}},</p><p>Sorry your package hasn’t arrived. "
                 "Please reply with your order number and we’ll investigate right away.</p>"
                 "<p>— Oubon Support</p>")
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

def lookup_order(order_id: str) -> Optional[dict]:
    import requests

    base = f"https://{settings.SHOPIFY_STORE_DOMAIN}/admin/api/{settings.SHOPIFY_API_VERSION}"
    url = f"{base}/orders.json?name={order_id}"
    headers = {"X-Shopify-Access-Token": settings.SHOPIFY_ADMIN_ACCESS_TOKEN}

    res = requests.get(url, headers=headers, timeout=20)
    res.raise_for_status()
    data = res.json()

    orders = data.get("orders") or []
    if not orders:
        return None

    order = orders[0]
    shipping_lines = order.get("shipping_lines") or [{}]
    return {
        "order_id": order.get("name"),
        "status": order.get("fulfillment_status") or "Processing",
        "carrier": shipping_lines[0].get("title", ""),
        "tracking": shipping_lines[0].get("tracking_number", "") or "",
        "last_update": order.get("updated_at", ""),
    }

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
                    lines += ["", "— Oubon Support"]
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

class ProcessPayload(BaseModel):
    auto_reply: bool = False
    max_messages: int = 25

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
