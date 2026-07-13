"""
Auto-fulfillment safety regression tests (Section B band 2: T16-T19).

The engine used to place the supplier order BEFORE saving any record, with no
idempotency (T16), no engine-level kill switch (T17), reported FAILED even
when the CJ call may have succeeded — inviting double-order retries (T18),
and had no value ceiling / daily cap / stock check / address validation (T19).
Every test here fails if its guard is reverted.
"""

import os
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-fulfillment")

from ospra_os.fulfillment.auto_fulfillment import (
    AutoFulfillmentEngine,
    FulfillmentStatus,
)


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_factory(monkeypatch):
    """Real sqlite DB for FulfillmentRecord, patched into the engine's imports."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from ospra_os.database.base import Base
    from ospra_os.database.fulfillment_models import FulfillmentRecord

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine, tables=[FulfillmentRecord.__table__])
    factory = sessionmaker(bind=engine)

    import ospra_os.database.connection as conn
    monkeypatch.setattr(conn, "SessionLocal", factory)
    return factory


@pytest.fixture
def engine(monkeypatch, db_factory):
    """Engine with fake creds, safety settings, and auto-fulfill ENABLED
    (individual tests flip switches off as needed)."""
    monkeypatch.setenv("SHOPIFY_STORE_NAME", "test-store")
    monkeypatch.setenv("SHOPIFY_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("CJ_API_KEY", "cj-key")

    eng = AutoFulfillmentEngine()
    eng.settings = SimpleNamespace(
        AUTO_FULFILL_ENABLED=True,
        FULFILL_MAX_ORDER_VALUE=200.0,
        FULFILL_MAX_ORDERS_PER_DAY=50,
    )
    monkeypatch.setattr(eng, "_dashboard_auto_fulfill_enabled", lambda: True)

    # Pre-flight stock check passes by default; alerts recorded not sent.
    async def preflight_ok(sku, qty, cost):
        return None

    monkeypatch.setattr(eng, "_check_cj_variant", preflight_ok)
    eng._alerts = []
    monkeypatch.setattr(
        eng, "_alert",
        lambda title, message, metadata=None: eng._alerts.append((title, message)),
    )
    return eng


def good_address(**overrides):
    addr = {
        "first_name": "Jane", "last_name": "Doe",
        "address1": "1 Main St", "address2": "",
        "city": "Austin", "province": "TX", "zip": "78701",
        "country": "United States", "country_code": "US",
        "phone": "555-0100",
    }
    addr.update(overrides)
    return addr


def shopify_order(value=50.0, line_items=None, **overrides):
    order = {
        "id": 111222333,
        "order_number": "1001",
        "email": "jane@example.com",
        "total_price": str(value),
        "shipping_address": good_address(),
        "line_items": line_items or [
            {"id": 900001, "product_id": 42, "variant_id": 4242,
             "quantity": 1, "name": "Widget", "price": str(value)},
        ],
    }
    order.update(overrides)
    return order


def cj_response(json_body=None, status_code=200, raise_on_json=None):
    resp = MagicMock()
    resp.status_code = status_code
    if raise_on_json:
        resp.json.side_effect = raise_on_json
    else:
        resp.json.return_value = json_body
    return resp


def stub_cj(monkeypatch, engine, outcomes):
    """Stub _cj_api_post; `outcomes` items are responses or exceptions."""
    calls = []

    async def fake_post(url, payload):
        calls.append(payload)
        outcome = outcomes[min(len(calls) - 1, len(outcomes) - 1)]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(engine, "_cj_api_post", fake_post)
    return calls


def cj_supplier_info(monkeypatch, engine, cost=None):
    async def fake_info(product_id):
        info = {"type": "cj_dropshipping", "sku": "VID-1", "url": "https://cjdropshipping.com/p/1"}
        if cost is not None:
            info["cost"] = cost
        return info

    monkeypatch.setattr(engine, "_get_supplier_info", fake_info)


# ---------------------------------------------------------------------------
# T17 — kill switch enforced by the ENGINE
# ---------------------------------------------------------------------------

class TestT17KillSwitch:
    @pytest.mark.asyncio
    async def test_engine_hard_returns_when_env_switch_off(self, engine, monkeypatch):
        engine.settings.AUTO_FULFILL_ENABLED = False
        cj_calls = stub_cj(monkeypatch, engine, [cj_response({"result": True, "data": {"orderId": "X"}})])
        cj_supplier_info(monkeypatch, engine)

        result = await engine.process_new_order(shopify_order())

        assert result["success"] is False
        assert result["status"] == FulfillmentStatus.MANUAL_REQUIRED.value
        assert cj_calls == []  # nothing was placed

    @pytest.mark.asyncio
    async def test_dashboard_toggle_alone_is_not_enough(self, engine, monkeypatch):
        """Env master switch off + dashboard on → still OFF (default-off rule)."""
        engine.settings.AUTO_FULFILL_ENABLED = False
        monkeypatch.setattr(engine, "_dashboard_auto_fulfill_enabled", lambda: True)
        assert engine.auto_fulfill_enabled() is False

    @pytest.mark.asyncio
    async def test_env_switch_alone_is_not_enough(self, engine, monkeypatch):
        engine.settings.AUTO_FULFILL_ENABLED = True
        monkeypatch.setattr(engine, "_dashboard_auto_fulfill_enabled", lambda: False)
        assert engine.auto_fulfill_enabled() is False


# ---------------------------------------------------------------------------
# T19 — pre-flight guards
# ---------------------------------------------------------------------------

class TestT19Guards:
    @pytest.mark.asyncio
    async def test_missing_address_routes_to_manual(self, engine, monkeypatch):
        cj_calls = stub_cj(monkeypatch, engine, [cj_response({"result": True, "data": {"orderId": "X"}})])
        cj_supplier_info(monkeypatch, engine)
        order = shopify_order()
        order["shipping_address"] = good_address(address1="")

        result = await engine.process_new_order(order)

        assert result["status"] == FulfillmentStatus.MANUAL_REQUIRED.value
        assert "address" in result["error"].lower()
        assert cj_calls == []

    @pytest.mark.asyncio
    async def test_order_over_value_ceiling_routes_to_manual(self, engine, monkeypatch):
        cj_calls = stub_cj(monkeypatch, engine, [cj_response({"result": True, "data": {"orderId": "X"}})])
        cj_supplier_info(monkeypatch, engine)

        result = await engine.process_new_order(shopify_order(value=500.0))

        assert result["status"] == FulfillmentStatus.MANUAL_REQUIRED.value
        assert "ceiling" in result["error"]
        assert cj_calls == []

    @pytest.mark.asyncio
    async def test_daily_cap_routes_to_manual(self, engine, monkeypatch):
        engine.settings.FULFILL_MAX_ORDERS_PER_DAY = 0
        cj_calls = stub_cj(monkeypatch, engine, [cj_response({"result": True, "data": {"orderId": "X"}})])
        cj_supplier_info(monkeypatch, engine)

        result = await engine.process_new_order(shopify_order())

        assert result["status"] == FulfillmentStatus.MANUAL_REQUIRED.value
        assert "daily cap" in result["error"]
        assert cj_calls == []

    @pytest.mark.asyncio
    async def test_unknown_daily_count_fails_closed(self, engine, monkeypatch):
        """If the DB can't tell us today's count, do NOT place orders."""
        monkeypatch.setattr(engine, "_count_todays_auto_orders", lambda: None)
        cj_calls = stub_cj(monkeypatch, engine, [cj_response({"result": True, "data": {"orderId": "X"}})])
        cj_supplier_info(monkeypatch, engine)

        result = await engine.process_new_order(shopify_order())

        assert result["status"] == FulfillmentStatus.MANUAL_REQUIRED.value
        assert cj_calls == []

    @pytest.mark.asyncio
    async def test_failed_stock_check_blocks_placement(self, engine, monkeypatch):
        async def preflight_fail(sku, qty, cost):
            return "Insufficient CJ stock (0 < 1)"

        monkeypatch.setattr(engine, "_check_cj_variant", preflight_fail)
        cj_calls = stub_cj(monkeypatch, engine, [cj_response({"result": True, "data": {"orderId": "X"}})])

        result = await engine._fulfill_via_cj(
            order_id="111", order_number="1001", product_id=42,
            product_name="Widget", supplier_sku="VID-1", quantity=1,
            shipping_address=good_address(), line_item_id="900001",
        )

        assert result["status"] == FulfillmentStatus.MANUAL_REQUIRED.value
        assert cj_calls == []


# ---------------------------------------------------------------------------
# T16 — idempotency: a webhook retry can't double-order
# ---------------------------------------------------------------------------

class TestT16Idempotency:
    @pytest.mark.asyncio
    async def test_webhook_retry_places_exactly_one_supplier_order(self, engine, monkeypatch, db_factory):
        cj_calls = stub_cj(monkeypatch, engine, [cj_response({"result": True, "data": {"orderId": "CJ-1"}})])
        cj_supplier_info(monkeypatch, engine)

        first = await engine.process_new_order(shopify_order())
        second = await engine.process_new_order(shopify_order())  # retry, same payload

        assert first["success"] is True
        assert len(cj_calls) == 1  # ONE supplier order, not two
        assert second["success"] is False
        assert second["results"][0].get("duplicate") is True

    @pytest.mark.asyncio
    async def test_claim_is_recorded_before_supplier_call(self, engine, monkeypatch, db_factory):
        """The PROCESSING claim must exist by the time the CJ call happens."""
        from ospra_os.database.fulfillment_models import FulfillmentRecord

        seen_status = {}

        async def fake_post(url, payload):
            session = db_factory()
            row = session.query(FulfillmentRecord).filter_by(
                idempotency_key="111:900001"
            ).first()
            seen_status["at_call_time"] = row.status if row else None
            session.close()
            return cj_response({"result": True, "data": {"orderId": "CJ-1"}})

        monkeypatch.setattr(engine, "_cj_api_post", fake_post)

        await engine._fulfill_via_cj(
            order_id="111", order_number="1001", product_id=42,
            product_name="Widget", supplier_sku="VID-1", quantity=1,
            shipping_address=good_address(), line_item_id="900001",
        )

        assert seen_status["at_call_time"] == FulfillmentStatus.PROCESSING.value

    @pytest.mark.asyncio
    async def test_db_unavailable_refuses_to_place(self, engine, monkeypatch):
        monkeypatch.setattr(engine, "_claim_line_item", lambda **kw: None)
        cj_calls = stub_cj(monkeypatch, engine, [cj_response({"result": True, "data": {"orderId": "X"}})])

        result = await engine._fulfill_via_cj(
            order_id="111", order_number="1001", product_id=42,
            product_name="Widget", supplier_sku="VID-1", quantity=1,
            shipping_address=good_address(), line_item_id="900001",
        )

        assert result["success"] is False
        assert cj_calls == []


# ---------------------------------------------------------------------------
# T18 — outcome discrimination: FAILED only when the order surely wasn't placed
# ---------------------------------------------------------------------------

class TestT18OutcomeDiscrimination:
    async def _fulfill(self, engine):
        return await engine._fulfill_via_cj(
            order_id="111", order_number="1001", product_id=42,
            product_name="Widget", supplier_sku="VID-1", quantity=1,
            shipping_address=good_address(), line_item_id="900001",
        )

    def _record_status(self, db_factory):
        from ospra_os.database.fulfillment_models import FulfillmentRecord
        session = db_factory()
        row = session.query(FulfillmentRecord).filter_by(idempotency_key="111:900001").one()
        session.close()
        return row.status

    @pytest.mark.asyncio
    async def test_connect_error_is_clean_failure(self, engine, monkeypatch, db_factory):
        stub_cj(monkeypatch, engine, [httpx.ConnectError("no route to host")])

        result = await self._fulfill(engine)

        assert result["status"] == FulfillmentStatus.FAILED.value
        assert self._record_status(db_factory) == FulfillmentStatus.FAILED.value

    @pytest.mark.asyncio
    async def test_timeout_after_send_is_possibly_placed(self, engine, monkeypatch, db_factory):
        stub_cj(monkeypatch, engine, [httpx.ReadTimeout("timed out waiting for response")])

        result = await self._fulfill(engine)

        assert result["status"] == FulfillmentStatus.POSSIBLY_PLACED.value
        assert self._record_status(db_factory) == FulfillmentStatus.POSSIBLY_PLACED.value
        assert engine._alerts, "a human must be alerted to verify at CJ"

    @pytest.mark.asyncio
    async def test_unparseable_response_is_possibly_placed_not_failed(self, engine, monkeypatch, db_factory):
        """The old code reported FAILED here — combined with a retry, that
        double-ordered. Must be POSSIBLY_PLACED + alert."""
        stub_cj(monkeypatch, engine, [cj_response(raise_on_json=ValueError("not json"))])

        result = await self._fulfill(engine)

        assert result["status"] == FulfillmentStatus.POSSIBLY_PLACED.value
        assert self._record_status(db_factory) == FulfillmentStatus.POSSIBLY_PLACED.value
        assert engine._alerts

    @pytest.mark.asyncio
    async def test_clean_cj_rejection_is_failed(self, engine, monkeypatch, db_factory):
        stub_cj(monkeypatch, engine, [cj_response({"result": False, "message": "SKU not found"})])

        result = await self._fulfill(engine)

        assert result["status"] == FulfillmentStatus.FAILED.value
        assert result["error"] == "SKU not found"

    @pytest.mark.asyncio
    async def test_success_records_supplier_order_id(self, engine, monkeypatch, db_factory):
        from ospra_os.database.fulfillment_models import FulfillmentRecord

        stub_cj(monkeypatch, engine, [cj_response({"result": True, "data": {"orderId": "CJ-77"}})])

        result = await self._fulfill(engine)

        assert result["success"] is True
        session = db_factory()
        row = session.query(FulfillmentRecord).filter_by(idempotency_key="111:900001").one()
        session.close()
        assert row.status == FulfillmentStatus.ORDERED.value
        assert row.supplier_order_id == "CJ-77"

    @pytest.mark.asyncio
    async def test_possibly_placed_is_not_retried(self, engine, monkeypatch, db_factory):
        """After a POSSIBLY_PLACED outcome, a webhook retry must NOT place."""
        cj_calls = stub_cj(monkeypatch, engine, [
            httpx.ReadTimeout("timed out"),
            cj_response({"result": True, "data": {"orderId": "CJ-2"}}),
        ])

        await self._fulfill(engine)          # outcome unknown
        retry = await self._fulfill(engine)  # blind retry attempt

        assert len(cj_calls) == 1  # the retry never reached CJ
        assert retry["success"] is False
        assert retry.get("duplicate") is True
