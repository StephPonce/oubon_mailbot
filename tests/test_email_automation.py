"""
Email automation tests (task #53) — first coverage for ospra_os/email_automation/.

All Gmail/Shopify/AI surfaces are faked; no network, no real credentials.
Covers: rule classification, auto-ignore rules, the anti-loop guard, the
quiet-hours template/follow-up path, the end-to-end send path with a fake
Gmail client, and RefundProcessor limits + refusal cases — including the
ownership check that stops refunds/leaks on other customers' orders.
"""

import base64

import pytest

from ospra_os.core.settings import Settings
from ospra_os.email_automation import email_processor as ep_mod
from ospra_os.email_automation.ai_responder import AIEmailResponder
from ospra_os.email_automation.refund_processor import RefundProcessor
from ospra_os.email_automation.rules import classify_message, get_rule_for_tags
from ospra_os.email_automation.smart_reply import SmartReplySystem


# =========================================================================
# Fakes
# =========================================================================

def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode()


def make_gmail_message(msg_id, subject, from_header, body_text,
                       label_ids=None, in_reply_to=None, references=None):
    headers = [
        {"name": "Subject", "value": subject},
        {"name": "From", "value": from_header},
    ]
    if in_reply_to:
        headers.append({"name": "In-Reply-To", "value": in_reply_to})
    if references:
        headers.append({"name": "References", "value": references})
    return {
        "id": msg_id,
        "labelIds": label_ids or [],
        "snippet": body_text[:80],
        "payload": {"headers": headers, "body": {"data": _b64(body_text)}},
    }


class _Call:
    """Terminal fake for googleapiclient's request objects."""

    def __init__(self, result):
        self._result = result

    def execute(self):
        return self._result


class FakeGmailService:
    """Just enough of the Gmail API surface for EmailProcessor."""

    def __init__(self, messages, labels):
        self._messages = {m["id"]: m for m in messages}
        self._labels = dict(labels)  # name -> id
        self.modify_calls = []
        self.created_labels = []

    # users().messages() / users().labels() chain
    def users(self):
        return self

    def messages(self):
        return self

    def labels(self):
        return self

    def list(self, userId=None, q=None, maxResults=None):
        if q is not None or maxResults is not None:
            return _Call({"messages": [{"id": mid} for mid in self._messages]})
        return _Call({"labels": [{"name": n, "id": i} for n, i in self._labels.items()]})

    def get(self, userId=None, id=None, format=None):
        return _Call(self._messages[id])

    def modify(self, userId=None, id=None, body=None):
        self.modify_calls.append({"id": id, "body": body})
        return _Call({"id": id})

    def create(self, userId=None, body=None):
        label_id = f"Label_{len(self._labels) + 1}"
        self._labels[body["name"]] = label_id
        self.created_labels.append(body["name"])
        return _Call({"id": label_id})


class FakeGmailClient:
    def __init__(self, service, fail_send=False):
        self._service = service
        self.fail_send = fail_send
        self.sent = []

    def service(self):
        return self._service

    def send_simple_email(self, to, subject, body):
        if self.fail_send:
            raise RuntimeError("SMTP exploded")
        self.sent.append({"to": to, "subject": subject, "body": body})


class FakeSmartReply:
    def __init__(self, response_mode="ai"):
        self.response_mode = response_mode
        self.calls = []

    def generate_reply(self, subject, body, from_email, from_name, rule, templates):
        self.calls.append({"subject": subject, "from_email": from_email})
        return {
            "subject": f"Re: {subject}",
            "body": f"Hi {from_name or 'there'}, we're on it.",
            "metadata": {
                "response_mode": self.response_mode,
                "used_ai": self.response_mode == "ai",
            },
        }


class FakeAnalytics:
    def __init__(self):
        self.tracked = []

    def track_email(self, **kwargs):
        self.tracked.append(kwargs)


class FakeFollowupSession:
    """Mimics get_followup_session().query(EmailFollowup).filter_by(...).first()."""

    def __init__(self, followup=None):
        self._followup = followup

    def query(self, *args, **kwargs):
        return self

    def filter_by(self, **kwargs):
        return self

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._followup

    def close(self):
        pass


RULES = {
    "rules": [
        {
            "if_any": ["refund", "broken", "order"],
            "apply_label": "Orders",
            "auto_reply": True,
            "auto_reply_template": "order_missing",
        },
    ]
}

AUTO_REPLIED_LABEL_ID = "Label_AR"


@pytest.fixture()
def settings():
    return Settings()


def build_processor(monkeypatch, settings, messages, *, extra_labels=None,
                    response_mode="ai", followup=None, fail_send=False):
    """EmailProcessor with every external surface faked."""
    labels = {settings.LABEL_AUTO_REPLIED: AUTO_REPLIED_LABEL_ID}
    labels.update(extra_labels or {})
    service = FakeGmailService(messages, labels)
    gmail = FakeGmailClient(service, fail_send=fail_send)
    reply = FakeSmartReply(response_mode=response_mode)
    analytics = FakeAnalytics()

    monkeypatch.setattr(ep_mod, "GmailClient", lambda s: gmail)
    monkeypatch.setattr(ep_mod, "SmartReplySystem", lambda *a, **k: reply)
    monkeypatch.setattr(ep_mod, "Analytics", lambda url: analytics)
    monkeypatch.setattr(
        ep_mod, "get_followup_session", lambda url: FakeFollowupSession(followup)
    )

    processor = ep_mod.EmailProcessor(settings)
    return processor, gmail, service, reply, analytics


# =========================================================================
# Classification (rules.py)
# =========================================================================

class TestClassification:
    def test_vip_beats_orders_and_important(self):
        tags = classify_message("Wholesale bulk order", "want a refund too")
        assert tags == ["VIP"]

    def test_order_keywords(self):
        assert classify_message("Where is my package", "") == ["Orders"]

    def test_important_keywords(self):
        assert classify_message("I want a refund", "") == ["Important"]

    def test_routine_fallback(self):
        assert classify_message("Hello", "just saying hi") == ["Routine"]

    def test_rule_mapping_priority(self):
        assert get_rule_for_tags(["VIP", "Orders"])["apply_label"] == "VIP"
        assert get_rule_for_tags(["Orders"])["auto_reply"] is True

    def test_routine_rule_or_none_never_explodes(self):
        # Whatever the mapping returns for Routine, it must be a dict or None
        rule = get_rule_for_tags(["Routine"])
        assert rule is None or isinstance(rule, dict)


# =========================================================================
# Auto-ignore rules (ai_responder.py)
# =========================================================================

class TestAutoIgnore:
    @pytest.fixture()
    def responder(self):
        return AIEmailResponder()

    @pytest.mark.parametrize("sender", [
        "noreply@shop.com",
        "no-reply@service.io",
        "donotreply@bank.com",
        "MAILER-DAEMON@google.com",
        "newsletter@brand.com",
        "marketing@spam.biz",
    ])
    def test_ignores_automated_senders(self, responder, sender):
        assert responder.should_auto_ignore(sender, "Hello") is True

    @pytest.mark.parametrize("subject", [
        "Your confirmation code is 482913",
        "Please verify your email",
        "Password reset requested",
        "Order Confirmation #5512",
        "Your receipt from Acme",
    ])
    def test_ignores_automated_subjects(self, responder, subject):
        assert responder.should_auto_ignore("jane@gmail.com", subject) is True

    def test_real_customer_not_ignored(self, responder):
        assert responder.should_auto_ignore(
            "jane.doe@gmail.com", "My order arrived broken"
        ) is False


# =========================================================================
# End-to-end send path with fake Gmail (email_processor.py)
# =========================================================================

class TestProcessInbox:
    def test_reply_sent_and_labeled_end_to_end(self, monkeypatch, settings):
        msg = make_gmail_message(
            "m1", "My order is broken", "Jane Doe <jane@gmail.com>",
            "Order #12345 arrived broken, please help",
        )
        processor, gmail, service, reply, analytics = build_processor(
            monkeypatch, settings, [msg]
        )

        result = processor.process_inbox(auto_reply=True, rules=RULES, templates={})

        assert result["processed"] == 1
        assert result["replied"] == 1
        assert result["labeled"] == 1
        # the reply went to the customer, not anyone else
        assert gmail.sent == [
            {"to": "jane@gmail.com", "subject": "Re: My order is broken",
             "body": gmail.sent[0]["body"]},
        ]
        # the message got BOTH the rule label and the Auto Replied label
        applied = [c["body"]["addLabelIds"][0] for c in service.modify_calls]
        assert AUTO_REPLIED_LABEL_ID in applied
        # analytics recorded a successful AI reply
        assert analytics.tracked and analytics.tracked[0]["success"] is True
        assert analytics.tracked[0]["response_mode"] == "ai"

    def test_unmatched_message_gets_no_reply(self, monkeypatch, settings):
        msg = make_gmail_message(
            "m1", "Love your store!", "Fan <fan@gmail.com>", "Just saying hi"
        )
        processor, gmail, *_ = build_processor(monkeypatch, settings, [msg])

        result = processor.process_inbox(auto_reply=True, rules=RULES, templates={})

        assert result["replied"] == 0
        assert result["labeled"] == 0
        assert gmail.sent == []

    def test_auto_reply_disabled_sends_nothing(self, monkeypatch, settings):
        msg = make_gmail_message(
            "m1", "Refund please", "Jane <jane@gmail.com>", "broken item"
        )
        processor, gmail, *_ = build_processor(monkeypatch, settings, [msg])

        result = processor.process_inbox(auto_reply=False, rules=RULES, templates={})

        assert result["replied"] == 0
        assert gmail.sent == []

    def test_send_failure_is_tracked_not_raised(self, monkeypatch, settings):
        msg = make_gmail_message(
            "m1", "Refund please", "Jane <jane@gmail.com>", "broken item"
        )
        processor, gmail, service, reply, analytics = build_processor(
            monkeypatch, settings, [msg], fail_send=True
        )

        result = processor.process_inbox(auto_reply=True, rules=RULES, templates={})

        assert result["replied"] == 0
        assert analytics.tracked and analytics.tracked[0]["success"] is False
        assert "SMTP exploded" in analytics.tracked[0]["error_message"]


class TestAntiLoopGuard:
    def _already_replied_msg(self, **kwargs):
        return make_gmail_message(
            "m1", "Re: your order", "Jane <jane@gmail.com>",
            "any order text refund", label_ids=[AUTO_REPLIED_LABEL_ID], **kwargs
        )

    def test_skips_message_already_replied_to(self, monkeypatch, settings):
        """Core anti-loop: same message, no new customer activity → no 2nd reply."""
        processor, gmail, *_ = build_processor(
            monkeypatch, settings, [self._already_replied_msg()], followup=None
        )

        result = processor.process_inbox(auto_reply=True, rules=RULES, templates={})

        assert result["replied"] == 0
        assert gmail.sent == []

    def test_allows_reply_when_customer_responds_in_thread(self, monkeypatch, settings):
        """In-Reply-To/References headers mean the CUSTOMER wrote back."""
        msg = self._already_replied_msg(in_reply_to="<abc@mail.gmail.com>")
        processor, gmail, *_ = build_processor(
            monkeypatch, settings, [msg], followup=None
        )

        result = processor.process_inbox(auto_reply=True, rules=RULES, templates={})

        assert result["replied"] == 1
        assert len(gmail.sent) == 1

    def test_allows_followup_after_quiet_hours_template(self, monkeypatch, settings):
        """A pending quiet-hours follow-up unlocks exactly one more reply."""
        processor, gmail, *_ = build_processor(
            monkeypatch, settings, [self._already_replied_msg()],
            followup=object(),  # any non-None row
        )

        result = processor.process_inbox(auto_reply=True, rules=RULES, templates={})

        assert result["replied"] == 1


class TestQuietHours:
    def test_template_reply_saved_for_followup(self, monkeypatch, settings):
        """Quiet-hours template replies must queue a business-hours follow-up."""
        msg = make_gmail_message(
            "m1", "Refund please", "Jane <jane@gmail.com>", "broken item"
        )
        processor, gmail, service, reply, analytics = build_processor(
            monkeypatch, settings, [msg], response_mode="template"
        )
        saved = []
        monkeypatch.setattr(
            processor, "_save_for_followup", lambda **kw: saved.append(kw)
        )

        result = processor.process_inbox(auto_reply=True, rules=RULES, templates={})

        assert result["replied"] == 1
        assert len(saved) == 1
        assert saved[0]["from_email"] == "jane@gmail.com"
        assert analytics.tracked[0]["followup_needed"] is True

    def test_ai_reply_not_saved_for_followup(self, monkeypatch, settings):
        msg = make_gmail_message(
            "m1", "Refund please", "Jane <jane@gmail.com>", "broken item"
        )
        processor, *_ = build_processor(
            monkeypatch, settings, [msg], response_mode="ai"
        )
        saved = []
        monkeypatch.setattr(
            processor, "_save_for_followup", lambda **kw: saved.append(kw)
        )

        processor.process_inbox(auto_reply=True, rules=RULES, templates={})

        assert saved == []


# =========================================================================
# RefundProcessor limits + refusal cases
# =========================================================================

def order(total="49.99", days_ago=3, email="jane@gmail.com"):
    from datetime import datetime, timedelta, timezone
    created = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return {
        "id": 111,
        "total_price": total,
        "created_at": created.isoformat(),
        "customer": {"email": email},
    }


GOOD_BODY = "My item arrived broken. I will ship it back tomorrow, order #12345."


class TestRefundProcessor:
    @pytest.fixture()
    def rp(self):
        return RefundProcessor()

    def test_eligible_path(self, rp):
        decision = rp.should_auto_refund(order(), GOOD_BODY)
        assert decision["eligible"] is True
        assert decision["action"] == "auto_refund"
        assert decision["refund_amount"] == pytest.approx(49.99)

    def test_missing_order_refused(self, rp):
        decision = rp.should_auto_refund({}, GOOD_BODY)
        assert decision["eligible"] is False
        assert decision["action"] == "manual_review"
        assert "not found" in decision["reason"].lower()

    def test_amount_over_limit_goes_to_manual_review(self, rp):
        decision = rp.should_auto_refund(order(total="249.00"), GOOD_BODY)
        assert decision["eligible"] is False
        assert decision["action"] == "manual_review"
        assert "exceeds" in decision["reason"]
        assert decision["refund_amount"] == 0.0

    def test_order_too_old_goes_to_manual_review(self, rp):
        decision = rp.should_auto_refund(order(days_ago=30), GOOD_BODY)
        assert decision["eligible"] is False
        assert "days old" in decision["reason"]

    def test_no_valid_reason_refused(self, rp):
        decision = rp.should_auto_refund(
            order(), "I changed my mind, I will ship it back."
        )
        assert decision["eligible"] is False
        assert "reason" in decision["reason"].lower()

    def test_no_shipback_confirmation_refused(self, rp):
        decision = rp.should_auto_refund(order(), "The item arrived broken.")
        assert decision["eligible"] is False
        assert "shipped back" in decision["reason"]

    def test_invalid_order_date_refused(self, rp):
        bad = order()
        bad["created_at"] = "not-a-date"
        decision = rp.should_auto_refund(bad, GOOD_BODY)
        assert decision["eligible"] is False
        assert "date" in decision["reason"].lower()

    @pytest.mark.parametrize("subject,body,expected", [
        ("Order OU12345 broken", "", "OU12345"),
        ("help", "my order # 56789 never arrived", "56789"),
        ("help", "issue with #4321 please", "#4321"),
        ("no order here", "just text", None),
    ])
    def test_order_id_extraction(self, rp, subject, body, expected):
        assert rp.extract_order_id_from_message(subject, body) == expected

    def test_response_brand_parameterized(self, rp):
        decision = rp.should_auto_refund(order(), GOOD_BODY)
        html = rp.generate_refund_response("Jane", "12345", decision, brand_name="Acme")
        assert "— Acme Support" in html
        assert "$49.99" in html

    def test_manual_review_response_has_no_amount(self, rp):
        decision = rp.should_auto_refund(order(total="500"), GOOD_BODY)
        html = rp.generate_refund_response("Jane", "12345", decision)
        assert "Refund Approved" not in html


# =========================================================================
# Ownership check — refunds/tracking must never touch a stranger's order
# =========================================================================

class FakeShopify:
    def __init__(self, order_data):
        self.order_data = order_data
        self.refunds = []

    def lookup_order(self, order_id):
        return self.order_data

    def process_refund(self, order_id, amount, reason, notify_customer):
        self.refunds.append({"order_id": order_id, "amount": amount})
        return {"success": True, "refund_id": "r1"}

    def get_order_status(self, order_data):
        return {"order_id": order_data["id"], "status": "shipped"}

    def format_tracking_response(self, order_status, customer_name):
        return f"<p>Hi {customer_name}, order {order_status['order_id']} status: shipped</p>"


@pytest.fixture()
def smart_reply_with_shopify(monkeypatch):
    """SmartReplySystem with a faked Shopify client attached."""
    def _build(order_data):
        settings = Settings()
        system = SmartReplySystem(settings)
        system.shopify = FakeShopify(order_data)
        return system
    return _build


class TestRefundOwnership:
    TEMPLATES = {
        "refund_request": {
            "subject": "Your refund request",
            "body": "<p>Hi {{name}}, our team will review order {{order_id}}.</p>",
        }
    }

    def test_own_order_gets_auto_refund(self, smart_reply_with_shopify):
        system = smart_reply_with_shopify(order(email="jane@gmail.com"))
        reply = system._handle_refund_request(
            "Refund order #12345", GOOD_BODY, "Jane", "jane@gmail.com",
            self.TEMPLATES, {"used_shopify": False, "refund_attempted": False},
        )
        assert "Refund Approved" in reply["body"]
        assert system.shopify.refunds  # refund actually processed

    def test_strangers_order_is_never_refunded_or_revealed(self, smart_reply_with_shopify):
        """Attacker emails about an order that belongs to someone else."""
        system = smart_reply_with_shopify(order(total="49.99", email="victim@gmail.com"))
        metadata = {"used_shopify": False, "refund_attempted": False}
        reply = system._handle_refund_request(
            "Refund order #12345", GOOD_BODY, "Mallory", "attacker@evil.com",
            self.TEMPLATES, metadata,
        )
        # no refund processed on the victim's order
        assert system.shopify.refunds == []
        # nothing about the victim's order leaks: no amount, no approval
        assert "49.99" not in reply["body"]
        assert "Refund Approved" not in reply["body"]
        assert "victim@gmail.com" not in reply["body"]
        assert metadata["ownership_check_failed"] is True

    def test_order_without_email_fails_closed(self, smart_reply_with_shopify):
        data = order()
        data["customer"] = {}
        system = smart_reply_with_shopify(data)
        reply = system._handle_refund_request(
            "Refund order #12345", GOOD_BODY, "Jane", "jane@gmail.com",
            self.TEMPLATES, {"used_shopify": False, "refund_attempted": False},
        )
        assert system.shopify.refunds == []
        assert "Refund Approved" not in reply["body"]

    def test_tracking_never_reveals_strangers_order(self, smart_reply_with_shopify):
        system = smart_reply_with_shopify(order(email="victim@gmail.com"))
        reply = system._handle_order_tracking(
            "Where is order #12345", "where is my package", "Mallory",
            "attacker@evil.com",
            {"tracking_lookup": {"subject": "Re: Your order", "body": "<p>Hi {{name}}</p>"}},
            {"used_shopify": False},
        )
        assert "shipped" not in reply["body"]
        assert reply["subject"] == "Re: Your order"
