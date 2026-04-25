"""
Pytest configuration and shared fixtures.
"""

import os
import pytest
import asyncio
from typing import Generator
from unittest.mock import MagicMock, AsyncMock, patch

# Exclude archived legacy tests from collection. Files in tests/archive/ are
# preserved for git-blame / reference only — they must never execute.
# Pass 6 moved the old test_tenant_isolation.py here (superseded by
# tests/integration/test_tenant_isolation_scaffold.py).
collect_ignore_glob = ["archive/*"]

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# Set test environment before importing app
import tempfile
os.environ["APP_ENV"] = "testing"


def _pick_writable_tmp_dir() -> str:
    """Return the first writable scratch directory we find.

    `tempfile.gettempdir()` can resolve to a read-only path in some sandboxed
    or container environments (e.g. mounted FS without RW for the current
    user). When that happens, every test that touches the SQLite file dies
    with `disk I/O error` even though the code is fine. Probe a short list
    of candidates and pick the first one we can actually write to.
    """
    candidates = [
        tempfile.gettempdir(),
        "/tmp",
        "/var/tmp",
        os.path.expanduser("~/.cache/ospra_tests"),
    ]
    for path in candidates:
        if not path:
            continue
        try:
            os.makedirs(path, exist_ok=True)
            probe = os.path.join(path, ".ospra_test_write_probe")
            with open(probe, "w") as fh:
                fh.write("ok")
            os.remove(probe)
            return path
        except OSError:
            continue
    # Last-ditch fallback: the cwd. If even that fails, the tests will
    # surface a clear DB error at fixture-setup time.
    return os.getcwd()


# Use file-based test database instead of :memory: to avoid per-connection isolation issues.
#
# Under pytest-xdist (`-n auto` in pytest.ini) each worker imports this module
# in its own subprocess. If they all hammer the same DB file they race on
# `os.remove(TEST_DB_PATH)` and `Base.metadata.create_all` during session
# setup, which surfaces as `FileNotFoundError` / `OperationalError: no such
# table` storms. Append the worker id (set by xdist as PYTEST_XDIST_WORKER,
# e.g. "gw0", "gw1", "master" when not parallel) so every worker gets its
# own isolated SQLite file.
TEST_DB_DIR = _pick_writable_tmp_dir()
_WORKER_ID = os.environ.get("PYTEST_XDIST_WORKER", "master")
TEST_DB_PATH = os.path.join(TEST_DB_DIR, f"test_database_{_WORKER_ID}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"

# Provide stable test-only secrets BEFORE importing the app. Without these,
# pytest.ini's `filterwarnings = error` promotes the app's startup
# "JWT_SECRET_KEY not set" and "token blacklist in-memory" warnings into
# ImportErrors during conftest collection (see Pass 6 notes). These values
# are ONLY used for tests — never in real envs.
os.environ.setdefault(
    "JWT_SECRET_KEY", "test-only-jwt-secret-do-not-use-in-production-ever"
)

# Import from main database package (not multi_store_models) to use consistent Base class
from ospra_os.database.base import Base, ProductStatus
from ospra_os.database import User, Store, Product, Action, AutoPilotLog
from ospra_os.database.action_models import ActionLog


# ==================== DATABASE FIXTURES ====================

@pytest.fixture(scope="session")
def engine():
    """Create test database engine."""
    # Ensure all models are imported before creating tables
    # This is critical for pytest-xdist parallel execution
    from ospra_os.database import (
        User, Store, Product, Action, AutoPilotLog,
        UserSettings, UserProductRecommendation, UserEmailAccount,
        ProductDeployment, ProductSaturation, ProductVelocity,
        ProductSnapshot, ProductIntelligence,
        AdCampaign, Email, EmailAutomationRule, EmailTemplate,
        EmailLabel, EmailFollowup, ABTest, ABTestEvent,
        ABTestAssignment, ABTestVariant, AIUsage,
        RankingHistory, Niche, NicheSnapshot, CrossStoreLearning
    )
    from ospra_os.database.action_models import ActionLog
    from ospra_os.database.job_models import Job  # Background job storage
    from ospra_os.learning.hybrid_learning_engine import GlobalLearningWeights, PersonalLearningWeights

    # Use file-based test database to avoid :memory: per-connection issues
    import atexit

    # Clean up old test database if it exists
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

    engine = create_engine(
        f"sqlite:///{TEST_DB_PATH}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)

    print(f"[TEST] Test database created at: {TEST_DB_PATH}")
    print(f"   DATABASE_URL: {os.environ['DATABASE_URL']}")

    # Register cleanup
    def cleanup():
        if os.path.exists(TEST_DB_PATH):
            try:
                os.remove(TEST_DB_PATH)
            except:
                pass
    atexit.register(cleanup)

    return engine


@pytest.fixture(scope="function")
def db_session(engine) -> Generator[Session, None, None]:
    """Create a fresh database session for each test.

    Uses the basic external-transaction pattern: open a Connection, start a
    transaction on it, give the Session a Connection-scoped binding so the
    Session's ``commit()`` flushes through but the outer transaction
    survives, then roll back on teardown.

    Some tests deliberately trigger an IntegrityError (e.g. UNIQUE-constraint
    tests). When that happens SQLAlchemy invalidates the outer transaction;
    the teardown rollback then warns "transaction already deassociated from
    connection". Swallow that — at that point the connection is being closed
    anyway and the data never reaches disk.
    """
    connection = engine.connect()
    transaction = connection.begin()

    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=connection,
    )
    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()
        if transaction.is_active:
            try:
                transaction.rollback()
            except Exception:
                pass
        connection.close()


@pytest.fixture(scope="function")
def db(db_session: Session) -> Generator[Session, None, None]:
    """Alias for db_session."""
    yield db_session


# ==================== APP FIXTURES ====================

@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Create test client with database override."""
    from ospra_os.main import app
    from ospra_os.database import get_db

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


# ==================== USER FIXTURES ====================

@pytest.fixture
def test_user(db_session: Session) -> User:
    """Create a test user."""
    user = User(
        email="test@example.com",
        password_hash="$2b$12$test_hash",
        name="Test User",
        subscription_tier="nest",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_user_premium(db_session: Session) -> User:
    """Create a premium tier test user."""
    user = User(
        email="premium@example.com",
        password_hash="$2b$12$test_hash",
        name="Premium User",
        subscription_tier="soar",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user: User) -> dict:
    """Create authentication headers for test user."""
    return {"Authorization": f"Bearer test_token_{test_user.id}"}


@pytest.fixture
def auth_client(client: TestClient, auth_headers: dict, test_user: User) -> TestClient:
    """Test client with authentication headers and mocked auth dependency."""
    from ospra_os.main import app
    from ospra_os.auth.jwt_auth import get_current_user

    # Override get_current_user to return test_user directly (bypass JWT validation in tests)
    async def override_get_current_user():
        return test_user

    app.dependency_overrides[get_current_user] = override_get_current_user
    client.headers.update(auth_headers)
    return client


# ==================== STORE FIXTURES ====================

@pytest.fixture
def test_store(db_session: Session, test_user: User) -> Store:
    """Create a test store."""
    store = Store(
        user_id=test_user.id,
        store_name="Test Store",
        platform="shopify",
        store_url="test-store.myshopify.com",
        credentials={"shop_url": "test-store.myshopify.com", "access_token": "test_token"},
        is_active=True,
    )
    db_session.add(store)
    db_session.commit()
    db_session.refresh(store)
    return store


# ==================== PRODUCT FIXTURES ====================

@pytest.fixture
def test_product(db_session: Session, test_user: User, test_store: Store) -> Product:
    """Create a test product."""
    # Note: 'niche' field removed from Product model - use product_intelligence for niche tracking
    product = Product(
        store_id=test_store.id,
        product_name="Test Product",
        status=ProductStatus.DISCOVERED,
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)
    return product


# ==================== MOCK FIXTURES ====================

@pytest.fixture
def mock_shopify_client():
    """Mock Shopify API client."""
    with patch('ospra_os.integrations.shopify.client.ShopifyClient') as mock:
        client = AsyncMock()
        client.create_product.return_value = {
            "product": {"id": 12345, "handle": "test-product"}
        }
        mock.return_value = client
        yield client


@pytest.fixture
def mock_anthropic():
    """Mock Anthropic API client."""
    with patch('anthropic.Anthropic') as mock:
        client = MagicMock()
        client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="AI response")]
        )
        mock.return_value = client
        yield client


# ==================== ASYNC SUPPORT ====================
#
# Note: Event loop fixture removed - pytest-asyncio handles this automatically
# when asyncio_mode = auto is set in pytest.ini
