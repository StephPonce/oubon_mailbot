"""
Section C band 1 — IDOR regression tests (T42/T43/T33/T45/T46/T47/T49).

The pattern across the app was: authentication mostly fine, AUTHORIZATION
missing — user_id taken from the client, ownership never verified. Every test
here fails if a route goes back to trusting client-supplied identity.
"""

from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-idor")


# ---------------------------------------------------------------------------
# T42 — intelligence action routes
# ---------------------------------------------------------------------------

class TestT42IntelligenceActions:
    def test_action_execute_requires_auth(self, client):
        response = client.post(
            "/api/intelligence/action/execute",
            json={"action_type": "adjust_price", "params": {}},
        )
        assert response.status_code in (401, 403)

    def test_action_preview_requires_auth(self, client):
        response = client.post(
            "/api/intelligence/action/preview",
            json={"action_type": "adjust_price", "params": {}},
        )
        assert response.status_code in (401, 403)

    def test_action_undo_requires_auth(self, client):
        response = client.post("/api/intelligence/action/undo/act-123")
        assert response.status_code in (401, 403)

    def test_tier_upgrade_route_is_gone(self, client):
        """T42/T44: the unauthenticated tier-setter must not exist at all."""
        response = client.post(
            "/api/intelligence/tier/upgrade?user_id=1",
            json={"new_tier": "stratosphere"},
        )
        assert response.status_code in (404, 405)

    def test_undo_of_another_users_action_404s(self, auth_client, test_user, monkeypatch):
        """Ownership: undoing someone else's action must look like 'not found'."""
        from ospra_os.intelligence import intelligence_core_routes as icr

        fake_executor = MagicMock()
        fake_executor.action_history.get_action.return_value = SimpleNamespace(
            user_id=test_user.id + 999,  # someone else's action
        )
        monkeypatch.setattr(icr, "get_action_executor", lambda db: fake_executor)

        response = auth_client.post("/api/intelligence/action/undo/act-1")

        assert response.status_code == 404
        fake_executor.undo_action.assert_not_called()


# ---------------------------------------------------------------------------
# T43 — payments subscription routes
# ---------------------------------------------------------------------------

class TestT43Payments:
    @pytest.mark.parametrize("method,path,body", [
        ("post", "/api/payments/checkout", {"tier": "soar"}),
        ("get", "/api/payments/subscription/123", None),
        ("post", "/api/payments/subscription/123/cancel", None),
        ("post", "/api/payments/subscription/123/resume", None),
        ("post", "/api/payments/subscription/change-tier",
         {"subscription_id": "123", "new_tier": "soar"}),
        ("get", "/api/payments/customer/9/portal", None),
    ])
    def test_payment_routes_require_auth(self, client, method, path, body):
        response = getattr(client, method)(path, json=body) if body is not None \
            else getattr(client, method)(path)
        assert response.status_code in (401, 403), f"{path} not gated"

    def test_change_tier_on_someone_elses_subscription_404s(
        self, auth_client, test_user, monkeypatch
    ):
        """The headline T43 hole: re-tiering another customer's subscription."""
        from ospra_os.payments import routes as pay_routes

        class FakeLS:
            async def get_subscription(self, subscription_id):
                return {"data": {"attributes": {"user_email": "someone-else@example.com"}}}, None

            async def change_subscription_tier(self, subscription_id, tier):
                raise AssertionError("must never be reached for a non-owner")

        monkeypatch.setattr(pay_routes, "LemonSqueezyClient", FakeLS)

        response = auth_client.post(
            "/api/payments/subscription/change-tier",
            json={"subscription_id": "sub-victim", "new_tier": "nest"},
        )

        assert response.status_code == 404

    def test_owner_can_change_their_own_subscription(self, auth_client, test_user, monkeypatch):
        from ospra_os.payments import routes as pay_routes

        calls = []

        class FakeLS:
            async def get_subscription(self, subscription_id):
                return {"data": {"attributes": {"user_email": test_user.email}}}, None

            async def change_subscription_tier(self, subscription_id, tier):
                calls.append((subscription_id, tier))
                return True, None

        monkeypatch.setattr(pay_routes, "LemonSqueezyClient", FakeLS)

        response = auth_client.post(
            "/api/payments/subscription/change-tier",
            json={"subscription_id": "sub-mine", "new_tier": "soar"},
        )

        assert response.status_code == 200
        assert len(calls) == 1

    def test_checkout_identity_comes_from_jwt(self, auth_client, test_user, monkeypatch):
        """Client-supplied user_id/user_email must be ignored."""
        from ospra_os.payments import routes as pay_routes

        seen = {}

        class FakeLS:
            async def create_checkout(self, tier, user_email, user_id, **kw):
                seen["email"], seen["user_id"] = user_email, user_id
                return "https://checkout.example", None

        monkeypatch.setattr(pay_routes, "LemonSqueezyClient", FakeLS)

        response = auth_client.post(
            "/api/payments/checkout",
            json={"tier": "soar", "user_email": "attacker@example.com", "user_id": "999"},
        )

        assert response.status_code == 200
        assert seen["email"] == test_user.email
        assert seen["user_id"] == str(test_user.id)


# ---------------------------------------------------------------------------
# T33 — task trigger routes
# ---------------------------------------------------------------------------

class TestT33TaskTriggers:
    def test_triggers_require_auth(self, client):
        for path in (
            "/api/tasks/trigger/discover-products",
            "/api/tasks/trigger/analyze-performance",
            "/api/tasks/trigger/daily-brief",
        ):
            assert client.post(path).status_code in (401, 403), f"{path} not gated"

    def test_discovery_runs_as_caller_even_if_user_id_smuggled(
        self, auth_client, test_user, monkeypatch
    ):
        """The old ?user_id=N is gone; a smuggled param must not change the target."""
        import ospra_os.tasks.product_tasks as pt

        captured = []
        monkeypatch.setattr(
            pt.discover_products_for_user, "delay",
            lambda uid: (captured.append(uid), SimpleNamespace(id="tid"))[1],
        )

        response = auth_client.post("/api/tasks/trigger/discover-products?user_id=424242")

        assert response.status_code == 200
        assert captured == [test_user.id]

    def test_sync_store_cross_tenant_404s(self, auth_client, test_user):
        """Syncing a store you don't own must 404 (store 999999 isn't yours)."""
        response = auth_client.post("/api/tasks/trigger/sync-store?store_id=999999")
        assert response.status_code == 404

    def test_send_email_only_to_self(self, auth_client, test_user, monkeypatch):
        """The open-relay form (arbitrary `to`) is dead: recipient == caller."""
        import ospra_os.tasks.email_tasks as et

        captured = []
        monkeypatch.setattr(
            et.send_email, "delay",
            lambda to, subject, body: (captured.append(to), SimpleNamespace(id="tid"))[1],
        )

        response = auth_client.post(
            "/api/tasks/trigger/send-email"
            "?subject=hi&body=test&to=victim@example.com"
        )

        assert response.status_code == 200
        assert captured == [test_user.email]


# ---------------------------------------------------------------------------
# T45/T46/T47 — analytics / reports / A/B testing
# ---------------------------------------------------------------------------

class TestT45T46T47RouterAuth:
    @pytest.mark.parametrize("method,path", [
        ("get", "/api/customers/overview"),          # T45
        ("get", "/api/customers/at-risk"),           # T45 (PII)
        ("post", "/api/customers/sync/shopify?store_id=1"),  # T45
        ("get", "/api/reports/templates"),           # T46
        ("get", "/api/reports/history"),             # T46
        ("get", "/api/abtesting/tests"),             # T47
        ("post", "/api/abtesting/tests/1/start"),    # T47
    ])
    def test_routes_require_auth(self, client, method, path):
        response = getattr(client, method)(path)
        assert response.status_code in (401, 403), f"{path} not gated"

    def test_sync_no_longer_accepts_token_in_query(self, auth_client):
        """T45: the shopify_token query param is GONE — old-style calls fail
        validation instead of shipping credentials through access logs."""
        response = auth_client.post(
            "/api/customers/sync/shopify"
            "?shopify_store=x.myshopify.com&shopify_token=shpat_secret"
        )
        assert response.status_code == 422  # store_id is required now

    def test_storefront_event_tracking_stays_public(self, client):
        """T47: /events/* is visitor tracking from shop pages — it must NOT
        demand a JWT (a 401 here would break storefront tracking)."""
        response = client.post(
            "/api/abtesting/events/variant",
            json={"test_id": 999999, "visitor_id": "v-1"},
        )
        assert response.status_code != 401


# ---------------------------------------------------------------------------
# T49 — federated insight outcome ownership
# ---------------------------------------------------------------------------

class TestT49FederatedOwnership:
    @pytest.fixture()
    def fed_db(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool
        from ospra_os.database.base import Base
        from ospra_os.database import User
        from ospra_os.database.federated_models import AggregateInsight, InsightApplication

        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(engine, tables=[
            User.__table__, AggregateInsight.__table__, InsightApplication.__table__
        ])
        session = sessionmaker(bind=engine)()

        session.add(User(id=1, email="alice@example.com", password_hash="x", name="Alice"))
        session.add(User(id=2, email="bob@example.com", password_hash="x", name="Bob"))
        insight = AggregateInsight(id=5, insight_type="niche", title="Smart home works", data={})
        session.add(insight)
        session.add(InsightApplication(id=77, user_id=1, insight_id=5))
        session.commit()
        yield session
        session.close()

    def test_non_owner_cannot_record_outcome(self, fed_db):
        from ospra_os.federated.service import FederatedLearningService

        service = FederatedLearningService(fed_db)
        result = service.record_insight_outcome(
            application_id=77, outcome="failure", user_id=2  # Bob, not owner
        )

        assert result is None
        from ospra_os.database.federated_models import InsightApplication
        row = fed_db.query(InsightApplication).get(77)
        assert row.outcome is None  # untouched

    def test_owner_records_outcome(self, fed_db):
        from ospra_os.federated.service import FederatedLearningService

        service = FederatedLearningService(fed_db)
        result = service.record_insight_outcome(
            application_id=77, outcome="success", user_id=1
        )

        assert result is not None
        assert result.outcome == "success"
