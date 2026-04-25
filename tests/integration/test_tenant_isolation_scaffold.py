"""
Tenant Isolation — Integration Test Scaffold (Pass 4c)
=======================================================

Verifies that TenantScopedSession prevents cross-tenant data access using the
*actual* current schema (Store -> User via user_id, Product scoped via Store).

This file replaces the old `tests/test_tenant_isolation.py` which was skipped
because it assumed a non-existent `Product.user_id` column. The canonical
tenancy helpers in `ospra_os.tenancy.queries` filter by `user_id` and the set
of USER_SCOPED_MODELS now includes Store (and Product via its store_id).

Run standalone:
    uv run pytest tests/integration/test_tenant_isolation_scaffold.py -v

These tests use an in-memory SQLite DB so they're safe to run in CI without
touching dev data.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ospra_os.database.base import Base
from ospra_os.database import User, Store, Product
from ospra_os.tenancy.context import TenantContext, tenant_scope, get_current_tenant
from ospra_os.tenancy.queries import TenantScopedSession, TenantQueryError

# NOTE: Product has only a `store_id` column (no `user_id`), so it is scoped
# *indirectly* via Store. Pass 4d added INDIRECT_VIA_STORE_MODELS to
# tenancy.queries so that `tenant_db.query(Product)` joins Store and filters
# by Store.user_id; the Product-level test below exercises that path.


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_session():
    """In-memory SQLite session with all tables created."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def two_tenants(db_session):
    """Create two independent tenants (users) each with a store and a product."""
    alice = User(
        email="alice@example.com",
        name="Alice",
        password_hash="x",
        subscription_tier="nest",
    )
    bob = User(
        email="bob@example.com",
        name="Bob",
        password_hash="x",
        subscription_tier="nest",
    )
    db_session.add_all([alice, bob])
    db_session.commit()
    db_session.refresh(alice)
    db_session.refresh(bob)

    # NOTE: Store's ownership column is `store_name`, not `name` — the latter
    # doesn't exist on the model. `store_url` has a NOT NULL constraint so we
    # always set it. Passing name= here silently worked during earlier
    # scaffolding but broke under strict __init__ validation once the model
    # grew more columns. Always use the real column names.
    alice_store = Store(
        user_id=alice.id,
        store_name="Alice's Store",
        store_url="https://alice.example.com",
        platform="shopify",
        credentials={},
        status="active",
    )
    bob_store = Store(
        user_id=bob.id,
        store_name="Bob's Store",
        store_url="https://bob.example.com",
        platform="shopify",
        credentials={},
        status="active",
    )
    db_session.add_all([alice_store, bob_store])
    db_session.commit()
    db_session.refresh(alice_store)
    db_session.refresh(bob_store)

    # Seed one product per store so the Product-level indirect-join tests
    # have something to filter on. Product has no user_id — ownership flows
    # through store_id -> Store.user_id.
    alice_product = Product(
        store_id=alice_store.id,
        product_name="Alice's Widget",
        title="Alice's Widget",
        selling_price=29.99,
    )
    bob_product = Product(
        store_id=bob_store.id,
        product_name="Bob's Gadget",
        title="Bob's Gadget",
        selling_price=39.99,
    )
    db_session.add_all([alice_product, bob_product])
    db_session.commit()
    db_session.refresh(alice_product)
    db_session.refresh(bob_product)

    return {
        "alice": {"user": alice, "store": alice_store, "product": alice_product},
        "bob": {"user": bob, "store": bob_store, "product": bob_product},
    }


# ---------------------------------------------------------------------------
# Tests — the five invariants that must hold for a multi-tenant SaaS
# ---------------------------------------------------------------------------


def test_query_without_context_raises(db_session):
    """A query without tenant context must fail loudly, not return all rows."""
    with pytest.raises(TenantQueryError):
        TenantScopedSession(db_session)


def test_alice_only_sees_her_own_stores(db_session, two_tenants):
    alice = two_tenants["alice"]["user"]
    ctx = TenantContext(tenant_id=alice.id, user_id=alice.id)

    with tenant_scope(ctx):
        scoped = TenantScopedSession(db_session, ctx)
        stores = scoped.query(Store).all()

    assert len(stores) == 1
    assert stores[0].store_name == "Alice's Store"
    assert stores[0].user_id == alice.id


def test_alice_cannot_fetch_bobs_store_by_id(db_session, two_tenants):
    alice = two_tenants["alice"]["user"]
    bob_store_id = two_tenants["bob"]["store"].id

    ctx = TenantContext(tenant_id=alice.id, user_id=alice.id)
    with tenant_scope(ctx):
        scoped = TenantScopedSession(db_session, ctx)
        result = scoped.get(Store, bob_store_id)

    assert result is None, "Alice must not be able to fetch Bob's store by ID"


def test_tenant_scope_is_cleared_on_exit(db_session, two_tenants):
    assert get_current_tenant() is None

    alice = two_tenants["alice"]["user"]
    with tenant_scope(TenantContext(tenant_id=alice.id, user_id=alice.id)):
        assert get_current_tenant() is not None
        assert get_current_tenant().user_id == alice.id

    assert get_current_tenant() is None


def test_superuser_sees_all_stores(db_session, two_tenants):
    ctx = TenantContext(tenant_id=999, user_id=999, is_superuser=True)
    with tenant_scope(ctx):
        scoped = TenantScopedSession(db_session, ctx)
        stores = scoped.query(Store).all()

    # Both Alice's and Bob's stores should be visible to a superuser.
    assert len(stores) >= 2


# ---------------------------------------------------------------------------
# Pass 4d — Product-level isolation through the Store->user_id join
# ---------------------------------------------------------------------------


def test_alice_only_sees_her_own_products(db_session, two_tenants):
    """Product.store_id -> Store.user_id must be auto-joined by the wrapper."""
    alice = two_tenants["alice"]["user"]
    ctx = TenantContext(tenant_id=alice.id, user_id=alice.id)

    with tenant_scope(ctx):
        scoped = TenantScopedSession(db_session, ctx)
        products = scoped.query(Product).all()

    assert len(products) == 1, (
        "Alice must see exactly her one product; the join through Store "
        "should filter out Bob's."
    )
    assert products[0].product_name == "Alice's Widget"


def test_alice_cannot_fetch_bobs_product_by_id(db_session, two_tenants):
    """TenantScopedSession.get() must verify ownership via the parent Store."""
    alice = two_tenants["alice"]["user"]
    bob_product_id = two_tenants["bob"]["product"].id

    ctx = TenantContext(tenant_id=alice.id, user_id=alice.id)
    with tenant_scope(ctx):
        scoped = TenantScopedSession(db_session, ctx)
        result = scoped.get(Product, bob_product_id)

    assert result is None, "Alice must not be able to fetch Bob's product by ID"
