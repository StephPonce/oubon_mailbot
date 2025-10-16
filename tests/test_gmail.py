import base64
import json

import pytest
from fastapi.responses import JSONResponse

import main
from app.ai_reply import draft_reply
from app.rules import match_label_for_message
from app.settings import Settings


class _DummyExecute:
    def __init__(self, data):
        self._data = data

    def execute(self):
        return self._data


class _FakeLabels:
    def list(self, userId):
        return _DummyExecute({"labels": [{"name": "Replied", "id": "Replied"}]})

    def create(self, userId, body):
        return _DummyExecute({"id": body.get("name", "NewLabel")})


class _FakeMessages:
    def __init__(self, payload):
        self._payload = payload

    def list(self, userId, q, maxResults):
        return _DummyExecute({"messages": [{"id": "1"}]})

    def get(self, userId, id, format):
        return _DummyExecute(self._payload)

    def modify(self, userId, id, body):
        return _DummyExecute({})


class _FakeUsers:
    def __init__(self, payload):
        self._payload = payload

    def labels(self):
        return _FakeLabels()

    def messages(self):
        return _FakeMessages(self._payload)


class _FakeService:
    def __init__(self, payload):
        self._payload = payload

    def users(self):
        return _FakeUsers(self._payload)


@pytest.fixture(autouse=True)
def _patch_common(mocker):
    mocker.patch("app.ai_reply.OpenAI", None)
    mocker.patch("main.is_on_cooldown", return_value=False)
    mocker.patch("main.is_quiet_hours", return_value=False)
    mocker.patch("main.mark_replied")
    mocker.patch("main.gmail.send_simple_email")
    mocker.patch("main._shopify_lookup", return_value={"order_id": "12345", "status": "Shipped", "tracking": "1Z"})


@pytest.fixture
def mock_gmail(mocker):
    headers = [
        {"name": "Subject", "value": "Order #12345 missing"},
        {"name": "From", "value": "customer@example.com"},
    ]
    body_text = base64.urlsafe_b64encode("Hi, order not arrived".encode()).decode()
    payload = {"payload": {"headers": headers, "body": {"data": body_text}}}
    fake_service = _FakeService(payload)
    mocker.patch.object(main.gmail, "service", return_value=fake_service)
    return fake_service


@pytest.fixture
def mock_shopify(mocker):
    return mocker.patch("app.shopify_client.lookup_order", return_value={"order_id": "12345", "status": "Shipped", "tracking": "1Z"})


def test_labeling():
    subject = "Order tracking"
    body = "Hi, where is my package?"
    label = match_label_for_message(subject, body)
    assert label == "Orders"


def test_reply(mocker):
    mocker.patch("app.ai_reply.OpenAI", None)
    settings = Settings()
    reply = draft_reply("Order #12345 missing", "Hi, order not arrived", settings)
    assert "Oubon Support" in reply


def test_quiet_hours_reply(mocker, mock_gmail, mock_shopify):
    send_mock = main.gmail.send_simple_email
    mocker.patch("main.is_quiet_hours", return_value=True)
    payload = {"auto_reply": True, "max_messages": 1, "cooldown_hours": 24}
    response = main.process_inbox(payload)
    if isinstance(response, JSONResponse):
        content = json.loads(response.body.decode("utf-8"))
    else:
        content = response
    assert content["replied"] >= 1
    args, kwargs = send_mock.call_args
    body = kwargs.get("body", "") if kwargs else args[2]
    assert "follow up soon" in body.lower()


def test_process_inbox(mocker, mock_gmail, mock_shopify):
    mocker.patch("app.ai_reply.OpenAI", None)
    payload = {"auto_reply": True, "max_messages": 1, "cooldown_hours": 24}
    response = main.process_inbox(payload)
    if isinstance(response, JSONResponse):
        content = json.loads(response.body.decode("utf-8"))
    else:
        content = response
    assert content["labeled"] >= 1
    assert content["replied"] >= 0


def test_full_flow(mocker, mock_gmail, mock_shopify):
    mocker.patch("app.ai_reply.OpenAI", None)
    payload = {"auto_reply": True, "max_messages": 1, "cooldown_hours": 24}
    response = main.process_inbox(payload)
    if isinstance(response, JSONResponse):
        content = json.loads(response.body.decode("utf-8"))
    else:
        content = response
    assert content["labeled"] >= 1
    assert content["replied"] >= 0
