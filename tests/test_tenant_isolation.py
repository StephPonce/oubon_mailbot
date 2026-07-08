"""
Tenant isolation regression tests (audit T163 / T179).

These tests exist because ``TenantContext.can_access_store()`` once returned
``True`` unconditionally — and had *zero callers* — so nothing in the app ever
verified that a caller owned the store they were operating on. ``store_id``
arrives from a client-supplied ``?store_id=`` query param or ``X-Store-ID``
header, so any authenticated user could hand the API another tenant's store id.

If someone ever reverts that check, these tests must fail loudly.
"""

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-for-tenant-isolation-tests")

from ospra_os.database.base import Base  # noqa: E402
from ospra_os.database import Store, User  # noqa: E402
from ospra_os.tenancy.context import TenantContext  # noqa: E402


ALICE_ID, BOB_ID = 1, 2
ALICE_STORE, BOB_STORE = 10, 20


@pytest.fixture()
def db():
    """In-memory DB with two tenants, each owning exactly one store."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # one shared connection for :memory:
    )
    Base.metadata.create_all(engine, tables=[User.__table__, Store.__table__])
    session = sessionmaker(bind=engine)()

    session.add(User(id=ALICE_ID, email="alice@example.com", password_hash="x", name="Alice"))
    session.add(User(id=BOB_ID, email="bob@example.com", password_hash="x", name="Bob"))
    session.add(Store(
        id=ALICE_STORE, user_id=ALICE_ID, store_name="Alice Store",
        store_url="alice.myshopify.com", platform="shopify", credentials="{}",
    ))
    session.add(Store(
        id=BOB_STORE, user_id=BOB_ID, store_name="Bob Store",
        store_url="bob.myshopify.com", platform="shopify", credentials="{}",
    ))
    session.commit()

    yield session
    session.close()


@pytest.fixture()
def alice():
    return TenantContext(tenant_id=ALICE_ID, user_id=ALICE_ID)


@pytest.fixture()
def bob():
    return TenantContext(tenant_id=BOB_ID, user_id=BOB_ID)


def test_tenant_can_access_own_store(alice, db):
    assert alice.can_access_store(ALICE_STORE, db) is True


def test_tenant_cannot_access_other_tenants_store(alice, db):
    """THE cross-tenant leak. Must never be True."""
    assert alice.can_access_store(BOB_STORE, db) is False


def test_isolation_holds_in_both_directions(bob, db):
    assert bob.can_access_store(BOB_STORE, db) is True
    assert bob.can_access_store(ALICE_STORE, db) is False


def test_nonexistent_store_is_denied(alice, db):
    assert alice.can_access_store(999_999, db) is False


def test_none_store_id_is_denied(alice, db):
    assert alice.can_access_store(None, db) is False


def test_superuser_may_cross_tenants(db):
    """Platform admins are intentionally allowed to see all tenants."""
    root = TenantContext(tenant_id=ALICE_ID, user_id=ALICE_ID, is_superuser=True)
    assert root.can_access_store(BOB_STORE, db) is True


def test_can_access_store_requires_a_db_session(alice):
    """Ownership is a DB fact — the signature must not allow a check without one.

    Guards against re-introducing the old ``can_access_store(self, store_id)``
    that answered without ever querying.
    """
    with pytest.raises(TypeError):
        alice.can_access_store(BOB_STORE)  # type: ignore[call-arg]
