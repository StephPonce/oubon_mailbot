from __future__ import annotations

import asyncio
import base64
import contextlib
import datetime as dt
import json
import logging
import os
import re
import sqlite3
import time
import urllib.request
from email.utils import parseaddr
from pathlib import Path
from typing import Any, Dict, Optional

from zoneinfo import ZoneInfo

from ospra_os.core.branding import get_branding
from ospra_os.core.settings import Settings
from ospra_os.gmail.templates import quiet_hours_ack
from ospra_os.integrations.ai import classify_intent, smart_reply
from ospra_os.integrations.shopify import get_order_by_name
from ospra_os.learning.rules import RuleStore

from .util import GmailClient, GmailMessage

logger = logging.getLogger(__name__)


def _slack(text: str, *, emoji: str = "✉️") -> None:
    url = os.getenv("SLACK_WEBHOOK_URL", "").strip()
    if not url:
        return
    payload = {"text": f"{emoji} {text}"}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=3).read()
    except Exception:
        pass


class ActionStore:
    def __init__(self, db_path: str):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_table()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, check_same_thread=False)

    def _ensure_table(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS message_actions (
                    message_id TEXT PRIMARY KEY,
                    acted_at TEXT NOT NULL,
                    action TEXT NOT NULL,
                    metadata TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS thread_replies (
                    thread_id TEXT PRIMARY KEY,
                    replied_at TEXT NOT NULL
                )
                """
            )

    def has_processed(self, message_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT 1 FROM message_actions WHERE message_id = ? LIMIT 1", (message_id,)
            )
            return cur.fetchone() is not None

    def record(self, message_id: str, action: str, metadata: Dict[str, Any]) -> None:
        payload = json.dumps(metadata, ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO message_actions (message_id, acted_at, action, metadata)
                VALUES (?, ?, ?, ?)
                """,
                (message_id, dt.datetime.utcnow().isoformat(), action, payload),
            )

    def record_reply(self, thread_id: str) -> None:
        timestamp = dt.datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO thread_replies (thread_id, replied_at)
                VALUES (?, ?)
                """,
                (thread_id, timestamp),
            )

    def recent_reply(self, thread_id: str, cooldown_hours: int) -> bool:
        if cooldown_hours <= 0:
            return False
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT replied_at FROM thread_replies WHERE thread_id = ?",
                (thread_id,),
            )
            row = cur.fetchone()
        if not row:
            return False
        try:
            replied_at = dt.datetime.fromisoformat(row[0])
        except ValueError:
            return False
        return dt.datetime.utcnow() - replied_at < dt.timedelta(hours=cooldown_hours)


class InboxWorker:
    def __init__(self, st: Settings):
        self.st = st
        self._client: Optional[GmailClient] = None
        self._running = False
        self._task: Optional[asyncio.Task] = None
        db_path = self.st.GMAIL_SQLITE_PATH or self.st.GMAIL_STATE_DB_PATH
        self._store = ActionStore(db_path)
        self._rules = RuleStore(db_path)
        branding = get_branding()
        self.brand_name = (
            self.st.GMAIL_BRAND_NAME
            or self.st.BRAND_NAME
            or getattr(branding, "OS_BRAND", "OspraOS")
        )
        self.support_from_name = self.st.SUPPORT_FROM_NAME
        self.signature = self.st.GMAIL_SIGNATURE or f"— {self.support_from_name}"
        self.reply_from = self.st.GMAIL_REPLY_FROM or str(self.st.SUPPORT_FROM_EMAIL)
        self.quiet_hours_brand = self.st.QUIET_HOURS_BRAND or self.brand_name
        self.label_prefix = (self.st.GMAIL_LABEL_PREFIX or "").strip()
        self.label_support = self._label_name(self.st.LABEL_SUPPORT)
        self.label_orders = self._label_name(self.st.LABEL_ORDERS)
        self.label_billing = self._label_name(self.st.LABEL_BILLING)
        self.label_marketing = self._label_name(self.st.LABEL_MARKETING)
        self.label_vip = self._label_name(self.st.LABEL_VIP)
        self.label_admin = self._label_name(self.st.LABEL_ADMIN)
        self.label_auto_replied = self._label_name(self.st.LABEL_AUTO_REPLIED)
        self.label_auto_ignored = self._label_name(self.st.LABEL_AUTO_IGNORED)
        self.label_processed = self.st.GMAIL_LABEL_PROCESSED
        self.label_error = self.st.GMAIL_LABEL_ERROR or self.label_admin
        self.auto_reply_label_name = (
            self.st.GMAIL_AUTO_REPLY_LABEL
            or self.st.GMAIL_LABEL_AUTO_REPLY
            or self.label_auto_replied
        )
        self._auto_reply_label_id: Optional[str] = None
        self.metrics: Dict[str, Any] = {
            "processed_total": 0,
            "replied_total": 0,
            "errors_total": 0,
            "last_tick": None,
            "last_error": None,
        }

    def is_running(self) -> bool:
        return self._running and self._task is not None and not self._task.done()

    def status(self) -> Dict[str, Any]:
        return {
            "running": self.is_running(),
            "poll_seconds": self.st.GMAIL_POLL_SECONDS,
            "processed_total": self.metrics["processed_total"],
            "replied_total": self.metrics["replied_total"],
            "errors_total": self.metrics["errors_total"],
            "last_tick": self.metrics["last_tick"],
            "last_error": self.metrics["last_error"],
        }

    async def start(self) -> None:
        if self.is_running():
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def run_once(self) -> None:
        await self._tick()

    async def _loop(self) -> None:
        while self._running:
            await self._tick()
            await asyncio.sleep(self.st.GMAIL_POLL_SECONDS)

    def _ensure_client(self) -> GmailClient:
        if not self._client:
            self._client = GmailClient(
                user_email=self.st.GMAIL_USER_EMAIL,
                token_path=self.st.GMAIL_TOKEN_PATH,
                credentials_path=self.st.GMAIL_CREDENTIALS_PATH,
            )
        return self._client

    def _label_name(self, canonical: Optional[str]) -> str:
        prefix = self.label_prefix
        name = (canonical or "").strip()
        if prefix and name:
            return f"{prefix} {name}".strip()
        if name:
            return name
        return prefix

    def _now_local(self) -> dt.datetime:
        tz = self.st.QUIET_HOURS_TIMEZONE
        if tz:
            try:
                return dt.datetime.now(ZoneInfo(tz))
            except Exception:  # pragma: no cover - timezone misconfig
                logger.warning("Invalid timezone '%s', falling back to naive time.", tz)
        return dt.datetime.now()

    def _in_quiet_hours(self) -> bool:
        now_local = self._now_local().time()
        start = self.st.QUIET_HOURS_START
        end = self.st.QUIET_HOURS_END
        if start > end:
            return now_local >= start or now_local < end
        return start <= now_local < end

    async def _tick(self) -> None:
        tick_started = dt.datetime.utcnow().isoformat()
        self.metrics["last_tick"] = tick_started
        client = self._ensure_client()
        if self._auto_reply_label_id is None and self.auto_reply_label_name:
            try:
                self._auto_reply_label_id = await self._retry_sync(
                    client.ensure_label, self.auto_reply_label_name
                )
            except Exception as exc:  # pragma: no cover - label creation fallback
                logger.warning(
                    "gmail_worker.ensure_label_failed label=%s error=%s",
                    self.auto_reply_label_name,
                    exc,
                )
        try:
            messages = await self._retry_sync(
                client.list_unprocessed_messages,
                self.st.GMAIL_LABEL_PROCESSED,
                limit=25,
            )
        except Exception as exc:
            self.metrics["errors_total"] += 1
            self.metrics["last_error"] = str(exc)
            logger.exception("gmail_worker.tick_failed", exc_info=exc)
            return

        for message in messages:
            await self._process_message(client, message)

        try:
            if int(time.time()) % 180 == 0:
                self._rules.promote()
        except Exception:
            pass

    async def _process_message(self, client: GmailClient, message: GmailMessage) -> None:
        started = time.perf_counter()
        headers = message.raw.get("payload", {}).get("headers", [])
        header_map = {
            (h.get("name") or "").lower(): h.get("value") or ""
            for h in headers
            if h.get("name")
        }
        subject = header_map.get("subject") or "(no subject)"
        from_header = header_map.get("from") or ""
        reply_to = parseaddr(from_header)[1]
        message_id_header = header_map.get("message-id") or message.id
        message_key = message_id_header or message.id

        if message_key and self._store.has_processed(message_key):
            logger.debug("gmail_worker.skip_idempotent", extra={"message_id": message_key})
            return

        try:
            thread = await self._retry_sync(client.get_thread, message.thread_id, "full")
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.warning("gmail_worker.thread_fetch_failed thread=%s error=%s", message.thread_id, exc)
            thread = {"messages": []}

        if not reply_to:
            logger.info("gmail_worker.skip_no_reply_to", extra={"message_id": message.id})
            if message_key:
                self._store.record(
                    message_key,
                    "skipped_no_reply_to",
                    {"thread_id": message.thread_id},
                )
            try:
                await self._retry_sync(
                    client.modify_labels,
                    message.id,
                    labels_to_add=[self.label_processed] if self.label_processed else [],
                    labels_to_remove=["UNREAD"],
                )
            except Exception as exc:  # pragma: no cover - label fallback
                logger.warning(
                    "gmail_worker.label_skip_failed message=%s error=%s",
                    message.id,
                    exc,
                    )
            self.metrics["processed_total"] += 1
            return

        if _is_no_reply(from_header, header_map):
            logger.info(
                "gmail_worker.skip_auto_message",
                extra={"message_id": message.id, "from": from_header},
            )
            if message_key:
                self._store.record(
                    message_key,
                    "skipped_auto_message",
                    {"thread_id": message.thread_id, "from": from_header},
                )
            try:
                await self._retry_sync(
                    client.modify_labels,
                    message.id,
                    labels_to_add=[name for name in (self.label_processed, self.label_auto_ignored) if name],
                    labels_to_remove=["UNREAD"],
                )
            except Exception as exc:  # pragma: no cover - label fallback
                logger.warning(
                    "gmail_worker.label_skip_failed message=%s error=%s",
                    message.id,
                    exc,
                )
            self.metrics["processed_total"] += 1
            return

        if self._auto_reply_label_id:
            try:
                already_auto = await self._retry_sync(
                    client.thread_has_label,
                    message.thread_id,
                    label_id=self._auto_reply_label_id,
                )
            except Exception as exc:  # pragma: no cover - label check fallback
                logger.warning(
                    "gmail_worker.thread_label_check_failed thread=%s error=%s",
                    message.thread_id,
                    exc,
                )
                already_auto = False
            if already_auto:
                logger.debug(
                    "gmail_worker.skip_thread_already_auto_replied",
                    extra={"thread_id": message.thread_id, "message_id": message.id},
                )
                if message_key:
                    self._store.record(
                        message_key,
                        "skipped_existing_auto_reply",
                        {"thread_id": message.thread_id},
                    )
                try:
                    await self._retry_sync(
                        client.modify_labels,
                        message.id,
                        labels_to_add=[self.label_processed] if self.label_processed else [],
                        labels_to_remove=["UNREAD"],
                    )
                except Exception as exc:  # pragma: no cover - label fallback
                    logger.warning(
                        "gmail_worker.label_skip_failed message=%s error=%s",
                        message.id,
                        exc,
                    )
                self.metrics["processed_total"] += 1
                return

        sender_email = reply_to or parseaddr(from_header)[1]
        subject_text = subject or ""

        learned = self._rules.best_guess(sender_email, subject_text)
        if learned == "ignore":
            labels_to_add = [name for name in (self.label_auto_ignored, self.label_processed) if name]
            if labels_to_add:
                await self._retry_sync(
                    client.modify_labels,
                    message.id,
                    labels_to_add=labels_to_add,
                    labels_to_remove=["UNREAD"],
                )
            if message_key:
                self._store.record(
                    message_key,
                    "learned_ignore",
                    {"email": sender_email, "subject": subject_text},
                )
                self._rules.record_outcome(sender_email, subject_text, "ignored")
            self.metrics["processed_total"] += 1
            return

        ignore_sender = GmailClient.is_ignored_sender(
            sender_email,
            self.st.IGNORE_DOMAINS,
            self.st.IGNORE_SENDER_PATTERNS,
        )
        if not ignore_sender:
            for pattern in self.st.IGNORE_SUBJECT_PATTERNS:
                if pattern and re.search(pattern, subject_text, re.IGNORECASE):
                    ignore_sender = True
                    break

        if ignore_sender:
            labels_to_add = [name for name in (self.label_auto_ignored, self.label_processed) if name]
            if labels_to_add:
                await self._retry_sync(
                    client.modify_labels,
                    message.id,
                    labels_to_add=labels_to_add,
                    labels_to_remove=["UNREAD"],
                )
            if message_key:
                self._store.record(
                    message_key,
                    "ignored_sender",
                    {"email": sender_email, "subject": subject_text},
                )
            _slack(
                f"Ignored sender {sender_email} · subject='{subject_text[:80]}'",
                emoji="🚫",
            )
            self._rules.record_outcome(sender_email, subject_text, "ignored")
            self.metrics["processed_total"] += 1
            return

        if self.reply_from and GmailClient.thread_has_outgoing_from(thread, self.reply_from):
            labels_to_add = [self.label_processed] if self.label_processed else []
            if labels_to_add:
                await self._retry_sync(
                    client.modify_labels,
                    message.id,
                    labels_to_add=labels_to_add,
                    labels_to_remove=["UNREAD"],
                )
            if message_key:
                self._store.record(
                    message_key,
                    "skipped_existing_reply",
                    {"thread_id": message.thread_id},
                )
            self.metrics["processed_total"] += 1
            return

        if self._store.recent_reply(message.thread_id, self.st.REPLY_COOLDOWN_HOURS):
            labels_to_add = [self.label_processed] if self.label_processed else []
            if labels_to_add:
                await self._retry_sync(
                    client.modify_labels,
                    message.id,
                    labels_to_add=labels_to_add,
                    labels_to_remove=["UNREAD"],
                )
            if message_key:
                self._store.record(
                    message_key,
                    "skipped_cooldown",
                    {"thread_id": message.thread_id},
                )
            self.metrics["processed_total"] += 1
            return

        body = _extract_plain_text(message.raw.get("payload", {}))
        order_no = _extract_order_number(subject, body)
        classification = "ORDER_STATUS" if order_no else None
        order_info = None

        try:
            if order_no:
                order_info = await self._retry_async(get_order_by_name, order_no)
        except Exception as exc:
            logger.warning("shopify_lookup_failed order=%s error=%s", order_no, exc)

        if not classification:
            merged_text = f"{subject} {body}".lower()
            if any(
                keyword in merged_text
                for keyword in (
                    "unsubscribe",
                    "newsletter",
                    "promo code",
                    "sponsored",
                    "mailchimp",
                    "constant contact",
                    "clickfunnels",
                )
            ):
                classification = "SPAM_NEWSLETTER"

        if not classification:
            classification = await classify_intent(subject, body, sender=sender_email)

        classification = (classification or "").upper()

        labels = self._labels_for_intent(classification)

        support_like = classification in {
            "GENERAL_SUPPORT",
            "ORDER_STATUS",
            "CANCELLATION",
            "RETURN_EXCHANGE",
        }

        if not support_like:
            labels = {self.label_auto_ignored}
            await self._retry_sync(
                client.modify_labels,
                message.id,
                labels_to_add=[name for name in labels if name],
                labels_to_remove=["UNREAD"],
            )
            if message_key:
                self._store.record(
                    message_key,
                    "ignored_non_support",
                    {"classification": classification},
                )
            self._rules.record_outcome(sender_email, subject_text, "ignored")
            self.metrics["processed_total"] += 1
            return

        if self.label_processed and self.label_processed.strip():
            labels.add(self.label_processed)

        quiet_hours = self._in_quiet_hours()
        reply_text = None
        action = "labeled"
        reply_message_id: Optional[str] = None

        order_status_payload = _extract_order_status(order_info)

        allowed_for_auto = classification in {
            "GENERAL_SUPPORT",
            "ORDER_STATUS",
            "CANCELLATION",
            "RETURN_EXCHANGE",
            "REFUND",
            "ADDRESS_CHANGE",
        }

        if classification != "SPAM_NEWSLETTER" and self.st.AUTO_REPLY_ENABLED and allowed_for_auto:
            if quiet_hours:
                reply_text = quiet_hours_ack(self.quiet_hours_brand, self.signature)
                action = "quiet_ack"
                if self.label_auto_replied:
                    labels.add(self.label_auto_replied)
            else:
                reply_payload = await smart_reply(
                    subject=subject,
                    body=body,
                    order_status=order_status_payload,
                    brand=self.brand_name,
                    signature=self.signature,
                    concise=True,
                )
                reply_text = (reply_payload or {}).get("reply")
                if reply_text:
                    if self.label_auto_replied:
                        labels.add(self.label_auto_replied)
                    action = "replied"
                else:
                    action = "labeled"
        else:
            action = "labeled"

        try:
            if reply_text:
                reply_message_id = await self._retry_sync(
                    client.reply_to_thread,
                    message.thread_id,
                    reply_text,
                    self.reply_from,
                    self.support_from_name,
                    subject,
                )
                if reply_message_id and self._auto_reply_label_id:
                    try:
                        await self._retry_sync(
                            client.add_label_to_thread,
                            message.thread_id,
                            label_id=self._auto_reply_label_id,
                        )
                    except Exception as exc:  # pragma: no cover - label add fallback
                        logger.warning(
                            "gmail_worker.thread_label_add_failed thread=%s error=%s",
                            message.thread_id,
                            exc,
                        )
                if reply_message_id:
                    self.metrics["replied_total"] += 1
                    self._store.record_reply(message.thread_id)
                    if action == "quiet_ack":
                        _slack(
                            f"Quiet-hours ack sent to {reply_to} · intent={classification}",
                            emoji="🌙",
                        )
                    elif action == "replied":
                        _slack(
                            f"AI reply sent to {reply_to} · intent={classification}",
                            emoji="✉️",
                        )

            await self._retry_sync(
                client.modify_labels,
                message.id,
                labels_to_add=[label for label in labels if label],
                labels_to_remove=["UNREAD"],
            )
            self.metrics["processed_total"] += 1
            duration_ms = int((time.perf_counter() - started) * 1000)
            metadata = {
                "classification": classification,
                "order_no": order_no,
                "order_status": order_status_payload,
                "labels": list(labels),
                "quiet_hours": quiet_hours,
                "duration_ms": duration_ms,
                "action": action,
                "reply_message_id": reply_message_id,
            }
            store_key = message_key or message.id
            if store_key:
                self._store.record(store_key, action, metadata)
            logger.info(
                "gmail_worker.processed",
                extra={
                    "email": reply_to,
                    "message_id": message_key,
                    "classification": classification,
                    "action": action,
                    "duration_ms": duration_ms,
                },
            )
            final_action = "ignored"
            if action in {"replied", "quiet_ack"}:
                final_action = "orders" if self.label_orders in labels else "support"
            elif self.label_auto_ignored in labels:
                final_action = "ignored"
            self._rules.record_outcome(sender_email, subject_text, final_action)
        except Exception as exc:
            self.metrics["errors_total"] += 1
            self.metrics["last_error"] = str(exc)
            logger.exception("gmail_worker.message_failed", exc_info=exc)
            _slack(f"Gmail worker error: {exc}", emoji=":warning:")
            with contextlib.suppress(Exception):
                await self._retry_sync(
                    client.modify_labels,
                    message.id,
                    labels_to_add=[self.label_error],
                )

    def _labels_for_intent(self, intent: str) -> set[str]:
        """
        Map classifier intent -> Gmail labels. Keep this conservative:
        Only Support/Orders get replies; everything else is ignored.
        """
        intent = (intent or "").upper()

        if intent in {
            "SPAM_NEWSLETTER",
            "MARKETING_AD",
            "AFFILIATE_PITCH",
            "VENDOR_OUTREACH",
            "LINK_EXCHANGE",
            "PRESS_OUTREACH",
            "PARTNERSHIP_PITCH",
        }:
            return {self.label_auto_ignored}

        if intent in {"ORDER_STATUS", "CANCELLATION", "RETURN_EXCHANGE", "REFUND", "ADDRESS_CHANGE"}:
            return {self.label_support, self.label_orders}

        if intent in {"GENERAL_SUPPORT", "ACCOUNT_SUPPORT", "PRODUCT_QUESTION"}:
            return {self.label_support}

        return {self.label_auto_ignored}

    async def _retry_sync(self, func, *args, **kwargs):
        delay = 1
        for attempt in range(3):
            try:
                return await asyncio.to_thread(func, *args, **kwargs)
            except Exception as exc:
                if attempt == 2:
                    raise
                await asyncio.sleep(delay)
                delay *= 2

    async def _retry_async(self, func, *args, **kwargs):
        delay = 1
        for attempt in range(3):
            try:
                return await func(*args, **kwargs)
            except Exception as exc:
                if attempt == 2:
                    raise
                await asyncio.sleep(delay)
                delay *= 2


def _extract_plain_text(payload: dict) -> str:
    if not payload:
        return ""
    mime_type = payload.get("mimeType", "")
    if mime_type == "text/plain":
        data = payload.get("body", {}).get("data")
        if data:
            padding = "=" * (-len(data) % 4)
            return base64.urlsafe_b64decode(data + padding).decode("utf-8", errors="ignore")
        return ""
    if mime_type.startswith("multipart/"):
        parts = payload.get("parts") or []
        texts = [_extract_plain_text(part) for part in parts]
        return "\n".join(filter(None, texts))
    return ""


def _extract_order_number(subject: str, body: str) -> Optional[str]:
    text = f"{subject}\n{body}"
    match = re.search(r"(?:order\s*#?\s*|#)(\d{4,8})", text, re.IGNORECASE)
    return match.group(1) if match else None


def _extract_order_status(order_info: Optional[dict]) -> Optional[dict]:
    if not order_info:
        return None

    status = order_info.get("fulfillment_status") or order_info.get("financial_status")
    fulfillments = order_info.get("fulfillments") or []
    tracking = None
    eta = None
    carrier = None
    if fulfillments:
        info = fulfillments[0] or {}
        tracking = info.get("tracking_url") or info.get("tracking_number")
        if not tracking:
            tracking_info = info.get("tracking_info") or []
            if isinstance(tracking_info, list) and tracking_info:
                tracking = tracking_info[0].get("url") or tracking_info[0].get("tracking_url")
                carrier = tracking_info[0].get("company") or carrier
                eta = tracking_info[0].get("estimated_delivery_at") or eta
        eta = eta or info.get("estimated_delivery_at")
        carrier = carrier or info.get("tracking_company")

    payload = {
        "name": order_info.get("name"),
        "status": status,
        "tracking": tracking,
        "carrier": carrier,
        "eta": eta,
    }
    cleaned = {k: v for k, v in payload.items() if v}
    return cleaned or None


_NO_REPLY_PATTERN = re.compile(r"(no[-_. ]?reply|do[-_. ]?not[-_. ]?reply)", re.IGNORECASE)


def _is_no_reply(from_addr: str, headers: dict[str, str]) -> bool:
    if _NO_REPLY_PATTERN.search(from_addr or ""):
        return True
    auto_submitted = headers.get("auto-submitted", "").lower()
    if auto_submitted and auto_submitted != "no":
        return True
    precedence = headers.get("precedence", "").lower()
    if precedence in {"bulk", "list", "junk"}:
        return True
    x_ars = headers.get("x-auto-response-suppress", "").lower()
    if "all" in x_ars or "autoreply" in x_ars:
        return True
    return False


_shared_worker: Optional[InboxWorker] = None


def get_worker(settings: Optional[Settings] = None) -> InboxWorker:
    global _shared_worker
    if _shared_worker is None:
        settings = settings or Settings()
        _shared_worker = InboxWorker(settings)
    return _shared_worker
