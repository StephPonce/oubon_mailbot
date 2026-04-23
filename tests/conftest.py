"""
Pytest configuration and shared fixtures.
"""

import os
import pytest
import asyncio
from typing import Generator
from unittest.mock import MagicMock, AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# Set test environment before importing app
import tempfile
os.environ["APP_ENV"] = "testing"
# Use file-based test database instead of :memory: to avoid per-connection isolation issues
TEST_DB_PATH = os.path.join(tempfile.gettempdir(), "test_database.db")
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"

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
    """Create a fresh database session for each test."""
    connection = engine.connect()
    transaction = connection.begin()

    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=connection
    )
    session = TestingSessionLocal()

    yield session

    session.close()
    transaction.rollback()
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
