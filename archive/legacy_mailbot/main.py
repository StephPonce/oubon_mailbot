# main.py — Oubon MailBot
from __future__ import annotations
import base64, json, os, re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from app.ai_reply import draft_reply
from app.db import init_db
from app.gmail_client import GmailClient
from app.rules import classify_message, get_rule_for_tags
from app.settings import Settings, get_settings

app = FastAPI(title="Oubon MailBot", version="0.1.0")

# CORS middleware - Allow frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        # Vite dev servers (all possible ports)
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:5176",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
        "http://127.0.0.1:5176",
        # Alternative dev servers
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        # Cloudflare tunnel
        "https://blond-ross-ticket-duplicate.trycloudflare.com",
        # Production domains
        "https://ospra.io",
        "https://www.ospra.io",
        "https://app.oubonshop.com",
        "https://policies.oubonshop.com",
        # Render deployment
        "https://ospra-intelligence-api.onrender.com",
        "https://*.onrender.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],  # Allow all headers (Authorization, Content-Type, etc.)
)

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

    # Initialize Ospra OS databases (usage tracking, learning, etc.)
    try:
        from ospra_os.database.connection import init_database as init_ospra_db
        init_ospra_db()
        print("[SUCCESS] Ospra OS database tables initialized")
    except Exception as e:
        print(f"[WARNING]  Ospra DB init failed: {e}")

    # Initialize Hybrid Learning tables
    try:
        from ospra_os.learning.hybrid_learning_engine import init_hybrid_learning
        init_hybrid_learning()
        print("[SUCCESS] Hybrid Learning tables initialized")
    except Exception as e:
        print(f"[WARNING]  Learning tables init failed: {e}")

    # Start background email checker
    from app.scheduler import start_scheduler
    start_scheduler()

    # 
    #  OSPRA INTELLIGENCE SCHEDULERS
    # 
    
    # Start Intelligence Core scheduler (morning briefings, product grading)
    try:
        from ospra_os.background_jobs.intelligence_scheduler import start_intelligence_scheduler
        start_intelligence_scheduler()
        print("[SUCCESS] Intelligence Core scheduler started")
        print("    Morning briefings: Daily at 6:00 AM")
        print("    Product grading: Every 6 hours")
        print("    Progress updates: Daily at midnight")
    except Exception as e:
        print(f"[WARNING]  Intelligence scheduler failed: {e}")

    # Start Auto-Discovery scheduler (background product discovery)
    try:
        from ospra_os.background_jobs.scheduler_integration import setup_background_jobs
        await setup_background_jobs(app)
        print("[SUCCESS] Auto-Discovery scheduler started")
    except Exception as e:
        print(f"[WARNING]  Auto-Discovery scheduler failed: {e}")

    # Start Self-Learning scheduler (daily learning cycles)
    try:
        from ospra_os.learning.learning_scheduler import start_learning_scheduler
        start_learning_scheduler()
        print("[SUCCESS] Self-Learning scheduler started")
        print("    📊 Daily learning: 3:00 AM")
        print("    📦 Tracking sync: Every 6 hours")
    except Exception as e:
        print(f"[WARNING]  Learning scheduler failed: {e}")

@app.get("/health")
async def health():
    """Health check with system status"""
    import os
    
    # Check database type
    db_url = os.getenv('DATABASE_URL', 'sqlite')
    db_type = 'postgresql' if 'postgresql' in db_url or 'postgres' in db_url else 'sqlite'
    
    # Check Apify
    apify_configured = bool(os.getenv('APIFY_API_TOKEN') or os.getenv('OUBONSHOP_APIFY_API_TOKEN'))
    
    # Check database schema
    try:
        from ospra_os.database.connection import verify_database_schema
        schema_status = verify_database_schema()
        db_status = schema_status['status']
    except Exception as e:
        db_status = f"error: {str(e)[:50]}"
    
    return {
        "status": "ok" if db_status == "healthy" else "degraded",
        "version": "2026-01-14",
        "database": db_type,
        "database_status": db_status,
        "apify": "configured" if apify_configured else "not_configured"
    }


@app.get("/health/database")
async def database_health():
    """Detailed database health check"""
    try:
        from ospra_os.database.connection import verify_database_schema, check_database_connection
        
        # Connection check
        conn_status = check_database_connection()
        
        # Schema check
        schema_status = verify_database_schema()
        
        return {
            "status": "healthy" if schema_status['all_present'] else "degraded",
            "connection": conn_status,
            "schema": schema_status
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

@app.get("/debug/intelligence")
async def debug_intelligence():
    """Debug endpoint to check intelligence module status"""
    results = {}

    # Test ProductIntelligenceEngine import
    try:
        from ospra_os.intelligence.product_intelligence import ProductIntelligenceEngine
        results['product_intelligence_import'] = 'SUCCESS'
    except Exception as e:
        results['product_intelligence_import'] = f'FAILED: {str(e)}'

    # Test proxy_manager import
    try:
        from ospra_os.scraping.proxy_manager import proxy_manager
        results['proxy_manager_import'] = 'SUCCESS'
    except Exception as e:
        results['proxy_manager_import'] = f'FAILED: {str(e)}'

    # Check if routes exist
    routes = [r.path for r in app.routes]
    results['intelligence_discover_registered'] = '/api/intelligence/discover' in routes
    results['intelligence_stats_registered'] = '/api/intelligence/stats' in routes
    results['all_intelligence_routes'] = [r for r in routes if 'intelligence' in r]

    return results

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Analytics dashboard with charts and visualizations."""
    dashboard_path = Path(__file__).parent / "static" / "dashboard.html"
    if not dashboard_path.exists():
        return HTMLResponse("<h1>Dashboard not found</h1><p>Please ensure static/dashboard.html exists</p>", status_code=404)
    with open(dashboard_path, "r") as f:
        return HTMLResponse(content=f.read())

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
    url = f"https://{settings.SHOPIFY_STORE}/admin/api/2025-01/orders.json?name={order_id}"
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

        print(f"[EMAIL] Gmail push notification received: {message_id}")

        # Process emails in background (don't block the webhook response)
        background_tasks.add_task(process_emails_background, settings)

        # Return 200 immediately so Pub/Sub knows we received it
        return {"status": "received", "message_id": message_id}

    except Exception as e:
        print(f"[ERROR] Error processing Pub/Sub webhook: {e}")
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

        print(f"[SUCCESS] Processed {result['processed']} emails, replied to {result['replied']}")

    except Exception as e:
        print(f"[ERROR] Error in background email processing: {e}")


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
# AI Intelligence Engine & Claude Advisor
# ---------------------------------------------------------------

# REMOVED DUPLICATE - See line 822 for correct /api/intelligence/discover endpoint


@app.get("/api/claude/daily-briefing")
async def get_daily_briefing(date: Optional[str] = None):
    """Get Claude's daily business briefing"""
    try:
        from ospra_os.intelligence.claude_advisor import get_daily_briefing as get_briefing

        briefing = await get_briefing(date)

        return {
            'success': True,
            'briefing': briefing,
            'date': date or datetime.now().strftime('%Y-%m-%d')
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


@app.get("/api/claude/weekly-report")
async def get_weekly_report():
    """Get Claude's weekly learning report"""
    try:
        from ospra_os.intelligence.claude_advisor import get_weekly_report as get_report

        report = await get_report()

        return {
            'success': True,
            'report': report
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


class ChatMessage(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None


@app.post("/api/claude/chat")
async def chat_with_claude(chat: ChatMessage):
    """Chat with Claude about your business"""
    try:
        from ospra_os.intelligence.claude_advisor import chat_with_claude as chat_func

        response = await chat_func(chat.message, chat.context)

        return {
            'success': True,
            'response': response
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


@app.post("/api/claude/chat/reset")
async def reset_claude_chat():
    """Reset Claude conversation history"""
    try:
        from ospra_os.intelligence.claude_advisor import ClaudeBusinessAdvisor

        advisor = ClaudeBusinessAdvisor()
        advisor.reset_conversation()

        return {
            'success': True,
            'message': 'Conversation reset'
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


# ---------------------------------------------------------------
# Product Intelligence API Endpoints
# ---------------------------------------------------------------
class DiscoverRequest(BaseModel):
    niches: Optional[List[str]] = None
    max_per_niche: int = 5


@app.post("/api/intelligence/discover")
async def discover_winning_products(request: DiscoverRequest):
    """
    Discover winning products using REAL AliExpress data + Claude AI analysis

    Returns products with:
    - Real AliExpress supplier data (no mock data)
    - AI-generated analysis from Claude
    - Unique scores for each product
    - Exact supplier links with SKUs
    - Real profit calculations
    """
    try:
        from ospra_os.intelligence.product_intelligence_v2 import ProductIntelligenceEngine

        engine = ProductIntelligenceEngine()
        products = await engine.discover_winning_products(
            niches=request.niches,
            max_per_niche=request.max_per_niche
        )

        return {
            'success': True,
            'products': products,
            'count': len(products),
            'niches_searched': request.niches or engine.trending_niches[:3]
        }

    except Exception as e:
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Intelligence discovery failed: {e}\n{traceback.format_exc()}")
        return {
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }


@app.get("/api/intelligence/stats")
async def get_intelligence_stats():
    """Get intelligence engine statistics"""
    try:
        from ospra_os.scraping.proxy_manager import proxy_manager

        proxy_stats = proxy_manager.get_stats()

        return {
            'success': True,
            'stats': {
                'proxy_manager': proxy_stats,
                'apis_configured': {
                    'amazon': bool(os.getenv('AMAZON_ACCESS_KEY')),
                    'aliexpress': bool(os.getenv('ALIEXPRESS_APP_KEY')),
                    'instagram': bool(os.getenv('INSTAGRAM_ACCESS_TOKEN')),
                    'tiktok': bool(os.getenv('TIKTOK_API_KEY')),
                    'twitter': bool(os.getenv('TWITTER_BEARER_TOKEN')),
                    'claude': bool(os.getenv('ANTHROPIC_API_KEY')),
                    'scraper_api': bool(os.getenv('SCRAPERAPI_KEY'))
                }
            }
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


# ---------------------------------------------------------------
# APIFY-POWERED Discovery (NEW - Primary Data Source)
# ---------------------------------------------------------------

@app.get("/api/apify/status")
async def apify_status():
    """
    Check Apify integration status and available scrapers
    """
    apify_token = os.getenv('APIFY_API_TOKEN') or os.getenv('OUBONSHOP_APIFY_API_TOKEN')
    
    status = {
        'configured': bool(apify_token),
        'token_prefix': apify_token[:10] + '...' if apify_token else None,
        'scrapers': {
            'tiktok_shop': False,
            'amazon_bestsellers': False
        }
    }
    
    if apify_token:
        try:
            from ospra_os.product_research.connectors.apify import (
                TikTokShopScraper,
                AmazonBestsellersScraper
            )
            status['scrapers']['tiktok_shop'] = TikTokShopScraper().is_available()
            status['scrapers']['amazon_bestsellers'] = AmazonBestsellersScraper().is_available()
        except Exception as e:
            status['import_error'] = str(e)
    
    return status


class UnifiedDiscoverRequest(BaseModel):
    niche: str = "smart_home"
    max_products: int = 20
    min_score: float = 40.0


@app.post("/api/v2/discover")
async def discover_products_v2(request: UnifiedDiscoverRequest):
    """
    APIFY-FIRST Product Discovery (v2)
    
    Uses:
    1. TikTok Shop (viral products)
    2. Amazon Bestsellers (proven demand)
    3. Google Trends (validation)
    4. AliExpress (fallback only)
    
    Returns real products with scores, not mock data.
    """
    try:
        from ospra_os.intelligence.unified_product_discovery import UnifiedProductDiscoveryV2
        
        engine = UnifiedProductDiscoveryV2()
        products = await engine.discover_products(
            niche=request.niche,
            max_products=request.max_products,
            min_score=request.min_score
        )
        
        # Determine data sources used
        sources_used = set()
        for p in products:
            sources_used.add(p.get('source', 'unknown'))
        
        return {
            'success': True,
            'products': products,
            'count': len(products),
            'niche': request.niche,
            'sources_used': list(sources_used),
            'engine': 'unified_v2_apify_first'
        }
        
    except Exception as e:
        import traceback
        return {
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }


@app.get("/api/v2/trending")
async def get_trending_products(niche: str = "smart_home", limit: int = 10):
    """
    Quick endpoint for trending products (cached where possible)
    """
    try:
        from ospra_os.intelligence.unified_product_discovery import get_live_products
        
        products = await get_live_products(niche=niche, limit=limit)
        
        return {
            'success': True,
            'products': products,
            'count': len(products),
            'niche': niche
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


@app.get("/api/v2/niches")
async def get_all_niches(products_per_niche: int = 5):
    """
    Discover products across all supported niches
    """
    try:
        from ospra_os.intelligence.unified_product_discovery import discover_all_niches
        
        results = await discover_all_niches(products_per_niche=products_per_niche)
        
        total = sum(len(prods) for prods in results.values())
        
        return {
            'success': True,
            'niches': results,
            'total_products': total,
            'niches_count': len(results)
        }
        
    except Exception as e:
        import traceback
        return {
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }


# ---------------------------------------------------------------
# Mount static files (must be last)
# ---------------------------------------------------------------

# Include Authentication routes (JWT-based)
try:
    from ospra_os.auth.routes import router as auth_router
    app.include_router(auth_router)
    print("[SUCCESS] JWT Auth routes loaded (/api/auth/*)")
except Exception as e:
    print(f"[WARNING]  JWT Auth routes not loaded: {e}")
    # Fallback to old auth routes if they exist
    try:
        from ospra_os.api.auth_routes import router as auth_router_old
        app.include_router(auth_router_old)
        print("[SUCCESS] Legacy Auth routes loaded (/api/auth/*)")
    except:
        pass

# Include User Profile & Settings routes
try:
    from ospra_os.api.user_routes import router as user_router
    app.include_router(user_router)
    print("[SUCCESS] User Profile routes loaded (/api/user/*)")
except Exception as e:
    print(f"[WARNING]  User Profile routes not loaded: {e}")

# Include Subscription routes
try:
    from ospra_os.api.subscription_routes import router as subscription_router
    app.include_router(subscription_router)
    print("[SUCCESS] Subscription routes loaded (/api/subscription/*)")
except Exception as e:
    print(f"[WARNING]  Subscription routes not loaded: {e}")

# Include Tier System routes (Unified Subscription Tiers)
try:
    from ospra_os.core.routes import router as tier_router
    app.include_router(tier_router)
    print("[SUCCESS] Tier System routes loaded (/api/tiers/*)")
except Exception as e:
    print(f"[WARNING]  Tier routes not loaded: {e}")

# Include Shopify routes
try:
    from ospra_os.integrations.shopify.routes import router as shopify_router
    app.include_router(shopify_router)
    print("[SUCCESS] Shopify routes loaded")
except Exception as e:
    print(f"[WARNING]  Shopify routes not loaded: {e}")

# Include Opportunity Scoring routes (Anti-AutoDS Algorithm)
try:
    from ospra_os.intelligence.opportunity_routes import router as opportunity_router
    app.include_router(opportunity_router)
    print("[SUCCESS] Opportunity Scoring routes loaded")
except Exception as e:
    print(f"[WARNING]  Opportunity routes not loaded: {e}")

# Include Usage Tracking routes
try:
    from ospra_os.core.usage_routes import router as usage_router
    app.include_router(usage_router)
    print("[SUCCESS] Usage Tracking routes loaded (/api/usage/*)")
except Exception as e:
    print(f"[WARNING]  Usage Tracking routes not loaded: {e}")

# Include Hybrid Learning routes
try:
    from ospra_os.learning.learning_routes import router as learning_router
    app.include_router(learning_router)
    print("[SUCCESS] Hybrid Learning routes loaded (/api/learning/*)")
except Exception as e:
    print(f"[WARNING]  Learning routes not loaded: {e}")

# Include Payment/LemonSqueezy routes
try:
    from ospra_os.payments.routes import router as payments_router
    app.include_router(payments_router)
    print("[SUCCESS] Payment routes loaded (/api/payments/*)")
except Exception as e:
    print(f"[WARNING]  Payment routes not loaded: {e}")

# ============================================================================
# [START] ALL OSPRA OS ROUTES - FULL PLATFORM WIRING
# ============================================================================

# --- ALIEXPRESS ROUTES ---
try:
    from ospra_os.aliexpress.routes import router as aliexpress_core_router
    app.include_router(aliexpress_core_router)
    print("[SUCCESS] AliExpress Core routes loaded (/api/aliexpress/*)")
except Exception as e:
    print(f"[WARNING]  AliExpress Core routes not loaded: {e}")

try:
    from ospra_os.api.aliexpress_product_routes import router as aliexpress_product_router
    app.include_router(aliexpress_product_router)
    print("[SUCCESS] AliExpress Product routes loaded (/api/aliexpress/products/*)")
except Exception as e:
    print(f"[WARNING]  AliExpress Product routes not loaded: {e}")

try:
    from ospra_os.api.aliexpress_token_routes import router as aliexpress_token_router
    app.include_router(aliexpress_token_router)
    print("[SUCCESS] AliExpress Token routes loaded (/api/aliexpress/tokens/*)")
except Exception as e:
    print(f"[WARNING]  AliExpress Token routes not loaded: {e}")

# --- ADMIN ROUTES ---
try:
    from ospra_os.admin.routes import router as admin_router
    app.include_router(admin_router)
    print("[SUCCESS] Admin routes loaded (/api/admin/*)")
except Exception as e:
    print(f"[WARNING]  Admin routes not loaded: {e}")

# --- ADVERTISING ROUTES ---
try:
    from ospra_os.advertising.routes import router as advertising_router
    app.include_router(advertising_router)
    print("[SUCCESS] Advertising routes loaded (/api/ads/*)")
except Exception as e:
    print(f"[WARNING]  Advertising routes not loaded: {e}")

# --- ANALYTICS ROUTES ---
try:
    from ospra_os.analytics.routes import router as analytics_router
    app.include_router(analytics_router)
    print("[SUCCESS] Analytics routes loaded (/api/analytics/*)")
except Exception as e:
    print(f"[WARNING]  Analytics routes not loaded: {e}")

try:
    from ospra_os.analytics.customer_routes import router as customer_analytics_router
    app.include_router(customer_analytics_router)
    print("[SUCCESS] Customer Analytics routes loaded (/api/customers/*)")
except Exception as e:
    print(f"[WARNING]  Customer Analytics routes not loaded: {e}")

# --- DASHBOARD ROUTES ---
try:
    from ospra_os.dashboard.routes import router as dashboard_router
    app.include_router(dashboard_router)
    print("[SUCCESS] Dashboard routes loaded (/api/dashboard/*)")
except Exception as e:
    print(f"[WARNING]  Dashboard routes not loaded: {e}")

try:
    from ospra_os.dashboard.routes_multi_store import router as multi_store_router
    app.include_router(multi_store_router)
    print("[SUCCESS] Multi-Store routes loaded (/api/stores/*)")
except Exception as e:
    print(f"[WARNING]  Multi-Store routes not loaded: {e}")

# --- EMAIL AUTOMATION ROUTES ---
try:
    from ospra_os.email_automation.automation_routes import router as email_automation_router
    app.include_router(email_automation_router)
    print("[SUCCESS] Email Automation routes loaded (/api/email/automation/*)")
except Exception as e:
    print(f"[WARNING]  Email Automation routes not loaded: {e}")

try:
    from ospra_os.email_automation.analytics_routes import router as email_analytics_router
    app.include_router(email_analytics_router)
    print("[SUCCESS] Email Analytics routes loaded (/api/email/analytics/*)")
except Exception as e:
    print(f"[WARNING]  Email Analytics routes not loaded: {e}")

try:
    from ospra_os.email_automation.settings_routes import router as email_settings_router
    app.include_router(email_settings_router)
    print("[SUCCESS] Email Settings routes loaded (/api/email/settings/*)")
except Exception as e:
    print(f"[WARNING]  Email Settings routes not loaded: {e}")

try:
    from ospra_os.email_automation.sync_routes import router as email_sync_router
    app.include_router(email_sync_router)
    print("[SUCCESS] Email Sync routes loaded (/api/email/sync/*)")
except Exception as e:
    print(f"[WARNING]  Email Sync routes not loaded: {e}")

try:
    from ospra_os.email_automation.oauth.routes import router as email_oauth_router
    app.include_router(email_oauth_router)
    print("[SUCCESS] Email OAuth routes loaded (/api/email/oauth/*)")
except Exception as e:
    print(f"[WARNING]  Email OAuth routes not loaded: {e}")

# --- GMAIL ROUTES ---
try:
    from ospra_os.gmail.routes import router as gmail_router
    app.include_router(gmail_router)
    print("[SUCCESS] Gmail routes loaded (/api/gmail/*)")
except Exception as e:
    print(f"[WARNING]  Gmail routes not loaded: {e}")

# --- INTELLIGENCE ROUTES (THE BRAIN) ---
try:
    from ospra_os.intelligence.routes import router as intelligence_router
    app.include_router(intelligence_router)
    print("[SUCCESS] Intelligence routes loaded (/api/intelligence/*)")
except Exception as e:
    print(f"[WARNING]  Intelligence routes not loaded: {e}")

try:
    from ospra_os.intelligence.intelligence_core_routes import router as intelligence_core_router
    app.include_router(intelligence_core_router)
    print("[SUCCESS] Intelligence Core routes loaded (/api/intelligence/core/*)")
except Exception as e:
    print(f"[WARNING]  Intelligence Core routes not loaded: {e}")

# Trend Discovery routes (NEW)
try:
    from ospra_os.api.intelligence_routes import router as trend_discovery_router
    app.include_router(trend_discovery_router)
    print("[SUCCESS] Trend Discovery routes loaded (/api/intelligence/*)")
except Exception as e:
    print(f"[WARNING]  Trend Discovery routes not loaded: {e}")

try:
    from ospra_os.intelligence.niche_routes import router as niche_router
    app.include_router(niche_router)
    print("[SUCCESS] Niche Analysis routes loaded (/api/niches/*)")
except Exception as e:
    print(f"[WARNING]  Niche routes not loaded: {e}")

try:
    from ospra_os.intelligence.unified_discovery_routes import router as unified_discovery_router
    app.include_router(unified_discovery_router)
    print("[SUCCESS] Unified Discovery routes loaded (/api/discover/*)")
except Exception as e:
    print(f"[WARNING]  Unified Discovery routes not loaded: {e}")

try:
    from ospra_os.intelligence.ai_actions_routes import router as ai_actions_router
    app.include_router(ai_actions_router)
    print("[SUCCESS] AI Actions routes loaded (/api/ai/actions/*)")
except Exception as e:
    print(f"[WARNING]  AI Actions routes not loaded: {e}")

try:
    from ospra_os.api.nl_routes import router as nl_router
    app.include_router(nl_router)
    print("[SUCCESS] Natural Language routes loaded (/api/nl/*)")
except Exception as e:
    print(f"[WARNING]  Natural Language routes not loaded: {e}")

# --- INVENTORY ROUTES ---
try:
    from ospra_os.inventory.routes import router as inventory_router
    app.include_router(inventory_router)
    print("[SUCCESS] Inventory routes loaded (/api/inventory/*)")
except Exception as e:
    print(f"[WARNING]  Inventory routes not loaded: {e}")

# --- JOBS/SCHEDULER ROUTES ---
try:
    from ospra_os.jobs.routes import router as jobs_router
    app.include_router(jobs_router)
    print("[SUCCESS] Jobs/Scheduler routes loaded (/api/jobs/*)")
except Exception as e:
    print(f"[WARNING]  Jobs routes not loaded: {e}")

# --- MONITORING ROUTES ---
try:
    from ospra_os.monitoring.routes import router as monitoring_router
    app.include_router(monitoring_router)
    print("[SUCCESS] Monitoring routes loaded (/api/monitoring/*)")
except Exception as e:
    print(f"[WARNING]  Monitoring routes not loaded: {e}")

# --- ONBOARDING ROUTES ---
try:
    from ospra_os.onboarding.routes import router as onboarding_router
    app.include_router(onboarding_router)
    print("[SUCCESS] Onboarding routes loaded (/api/onboarding/*)")
except Exception as e:
    print(f"[WARNING]  Onboarding routes not loaded: {e}")

# --- PLATFORM DEPLOYMENT ROUTES ---
try:
    from ospra_os.platforms.deployment_routes import router as deployment_router
    app.include_router(deployment_router)
    print("[SUCCESS] Platform Deployment routes loaded (/api/deploy/*)")
except Exception as e:
    print(f"[WARNING]  Deployment routes not loaded: {e}")

# --- PRODUCT RESEARCH ROUTES ---
try:
    from ospra_os.product_research.routes import router as product_research_router
    app.include_router(product_research_router)
    print("[SUCCESS] Product Research routes loaded (/api/research/*)")
except Exception as e:
    print(f"[WARNING]  Product Research routes not loaded: {e}")

# --- REPORTS ROUTES ---
try:
    from ospra_os.reports.routes import router as reports_router
    app.include_router(reports_router)
    print("[SUCCESS] Reports routes loaded (/api/reports/*)")
except Exception as e:
    print(f"[WARNING]  Reports routes not loaded: {e}")

# --- NOTIFICATIONS ROUTES ---
try:
    from ospra_os.api.notification_routes import router as notification_router
    app.include_router(notification_router)
    print("[SUCCESS] Notification routes loaded (/api/notifications/*)")
except Exception as e:
    print(f"[WARNING]  Notification routes not loaded: {e}")

# --- A/B TESTING ROUTES ---
try:
    from ospra_os.testing.routes import router as testing_router
    app.include_router(testing_router)
    print("[SUCCESS] A/B Testing routes loaded (/api/testing/*)")
except Exception as e:
    print(f"[WARNING]  Testing routes not loaded: {e}")

# --- TIKTOK ROUTES ---
try:
    from ospra_os.tiktok.routes import router as tiktok_router
    app.include_router(tiktok_router)
    print("[SUCCESS] TikTok routes loaded (/api/tiktok/*)")
except Exception as e:
    print(f"[WARNING]  TikTok routes not loaded: {e}")

# --- WAITLIST ROUTES ---
try:
    from ospra_os.waitlist.routes import router as waitlist_router
    app.include_router(waitlist_router)
    print("[SUCCESS] Waitlist routes loaded (/api/waitlist/*)")
except Exception as e:
    print(f"[WARNING]  Waitlist routes not loaded: {e}")

# --- RATE LIMITER ROUTES ---
try:
    from ospra_os.api.rate_limit_routes import router as rate_limit_router
    app.include_router(rate_limit_router)
    print("[SUCCESS] Rate Limiter routes loaded (/api/rate-limit/*)")
except Exception as e:
    print(f"[WARNING]  Rate Limiter routes not loaded: {e}")

# --- SMART CACHE ROUTES ---
try:
    from ospra_os.api.cache_routes import router as cache_router
    app.include_router(cache_router)
    print("[SUCCESS] Smart Cache routes loaded (/api/cache/*)")
except Exception as e:
    print(f"[WARNING]  Cache routes not loaded: {e}")

# --- SEARCH RELEVANCE ROUTES ---
try:
    from ospra_os.api.search_relevance_routes import router as search_relevance_router
    app.include_router(search_relevance_router)
    print("[SUCCESS] Search Relevance routes loaded (/api/search-relevance/*)")
except Exception as e:
    print(f"[WARNING]  Search Relevance routes not loaded: {e}")

# --- NATURAL LANGUAGE COMMAND ROUTES ---
try:
    from ospra_os.api.nl_routes import router as nl_router
    app.include_router(nl_router)
    print("[SUCCESS] Natural Language routes loaded (/api/nl/*)")
except Exception as e:
    print(f"[WARNING]  Natural Language routes not loaded: {e}")

# --- AUTO-PILOT ROUTES ---
try:
    from ospra_os.api.autopilot_routes import router as autopilot_router
    app.include_router(autopilot_router)
    print("[SUCCESS] Auto-Pilot routes loaded (/api/autopilot/*)")
except Exception as e:
    print(f"[WARNING]  Auto-Pilot routes not loaded: {e}")

# --- OI ASSISTANT ROUTES ---
try:
    from ospra_os.api.oi_routes import router as oi_router
    app.include_router(oi_router)
    print("[SUCCESS] OI Assistant routes loaded (/api/oi/*)")
except Exception as e:
    print(f"[WARNING]  OI routes not loaded: {e}")

# --- WEBHOOK ROUTES (SECURE) ---
try:
    from ospra_os.api.webhook_routes import router as webhook_router
    app.include_router(webhook_router)
    print("[SUCCESS] Webhook routes loaded (/api/webhooks/*)")
except Exception as e:
    print(f"[WARNING]  Webhook routes not loaded: {e}")

# --- AI IMAGE GENERATION ROUTES ---
try:
    from ospra_os.api.image_generation_routes import router as image_gen_router
    app.include_router(image_gen_router)
    print("[SUCCESS] AI Image Generation routes loaded (/api/images/*)")
except Exception as e:
    print(f"[WARNING]  Image Generation routes not loaded: {e}")

# --- PRODUCT ANALYSIS ROUTES ---
try:
    from ospra_os.api.product_analysis_routes import router as product_analysis_router
    app.include_router(product_analysis_router)
    print("[SUCCESS] Product Analysis routes loaded (/api/products/analysis/*)")
except Exception as e:
    print(f"[WARNING]  Product Analysis routes not loaded: {e}")

# --- SHOPIFY WEBHOOKS (ORDER FULFILLMENT + LEARNING) ---
try:
    from ospra_os.webhooks.shopify_webhooks import router as shopify_webhook_router
    app.include_router(shopify_webhook_router)
    print("[SUCCESS] Shopify Webhook routes loaded (/webhooks/shopify/*)")
except Exception as e:
    print(f"[WARNING]  Shopify Webhook routes not loaded: {e}")

# --- AUTO-FULFILLMENT ROUTES ---
try:
    from ospra_os.fulfillment.routes import router as fulfillment_router
    app.include_router(fulfillment_router)
    print("[SUCCESS] Auto-Fulfillment routes loaded (/api/fulfillment/*)")
except Exception as e:
    print(f"[WARNING]  Fulfillment routes not loaded: {e}")

print("\n" + "="*60)
print(" OSPRA INTELLIGENCE - ALL SYSTEMS ONLINE")
print("="*60 + "\n")

# ============================================================================

# Trends API endpoint for dashboard
@app.get("/api/trends/ecommerce")
async def get_ecommerce_trends():
    """Get e-commerce trends using xAI or fallback"""
    try:
        # Try xAI first
        from ospra_os.trends.xai_twitter_trends import get_ecommerce_trends as xai_trends
        data = await xai_trends()
        return data
    except Exception as e:
        # Fallback to basic response
        return {
            'success': True,
            'trends': [
                {'topic': 'Smart Home Devices', 'score': 85},
                {'topic': 'LED Lighting', 'score': 78},
                {'topic': 'Home Organization', 'score': 72},
                {'topic': 'Wireless Chargers', 'score': 68},
                {'topic': 'Kitchen Gadgets', 'score': 65}
            ],
            'summary': 'Smart home and LED products continue to trend. Focus on energy-efficient and convenience-focused items.',
            'source': 'fallback'
        }

# AI Chat endpoint for dashboard
@app.post("/api/ai/chat")
async def ai_chat(chat: ChatMessage):
    """AI chat endpoint using model router"""
    try:
        from ospra_os.ai.model_router import ai_quick_chat
        response = await ai_quick_chat(chat.message, chat.context)
        return {'success': True, 'response': response}
    except Exception as e:
        # Fallback to Claude advisor
        try:
            from ospra_os.intelligence.claude_advisor import chat_with_claude as chat_func
            response = await chat_func(chat.message, chat.context)
            return {'success': True, 'response': response}
        except Exception as e2:
            return {'success': False, 'error': str(e2)}

# Email sync endpoint for dashboard
@app.post("/api/email/sync")
async def sync_emails(settings: Settings = Depends(get_settings)):
    """Sync emails from Gmail"""
    try:
        gc = GmailClient(settings)
        svc = _svc(gc)
        
        # Fetch recent unread
        res = svc.users().messages().list(
            userId='me',
            q='is:unread',
            maxResults=50
        ).execute()
        
        messages = res.get('messages', [])
        
        return {
            'success': True,
            'synced': len(messages),
            'message': f'Found {len(messages)} unread emails'
        }
    except Exception as e:
        return {
            'success': False,
            'synced': 0,
            'error': str(e)
        }

# Serve generated AI images
try:
    generated_images_dir = Path(__file__).parent / "generated_images"
    generated_images_dir.mkdir(exist_ok=True)
    app.mount("/generated_images", StaticFiles(directory=str(generated_images_dir)), name="generated_images")
    print("[SUCCESS] Generated images directory mounted (/generated_images)")
except Exception as e:
    print(f"[WARNING] Generated images mount failed: {e}")

app.mount("/static", StaticFiles(directory="static"), name="static")
