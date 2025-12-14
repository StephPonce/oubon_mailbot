"""
Test data factories for creating test objects.
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from ospra_os.database import User, Store, Product, Action, AdCampaign


class UserFactory:
    """Factory for creating test users."""

    @staticmethod
    def create(
        email: str = "test@example.com",
        name: str = "Test User",
        subscription_tier: str = "nest",
        **kwargs
    ) -> User:
        """Create a test user with default or custom attributes."""
        return User(
            email=email,
            name=name,
            password_hash="$2b$12$test_hash",
            subscription_tier=subscription_tier,
            **kwargs
        )

    @staticmethod
    def create_premium(email: str = "premium@example.com") -> User:
        """Create a premium tier user."""
        return UserFactory.create(
            email=email,
            name="Premium User",
            subscription_tier="soar"
        )

    @staticmethod
    def create_inactive(email: str = "inactive@example.com") -> User:
        """Create an inactive user."""
        return UserFactory.create(
            email=email,
            name="Inactive User"
        )


class StoreFactory:
    """Factory for creating test stores."""

    @staticmethod
    def create(
        user_id: int,
        store_name: str = "Test Store",
        platform: str = "shopify",
        store_url: str = "test-store.myshopify.com",
        is_active: bool = True,
        credentials: dict = None,
        **kwargs
    ) -> Store:
        """Create a test store with default or custom attributes."""
        if credentials is None:
            credentials = {"shop_url": store_url, "access_token": "test_token"}
        return Store(
            user_id=user_id,
            store_name=store_name,
            platform=platform,
            store_url=store_url,
            credentials=credentials,
            is_active=is_active,
            **kwargs
        )

    @staticmethod
    def create_woocommerce(user_id: int) -> Store:
        """Create a WooCommerce store."""
        return StoreFactory.create(
            user_id=user_id,
            store_name="WooCommerce Store",
            platform="woocommerce",
            store_url="example.com"
        )


class ProductFactory:
    """Factory for creating test products."""

    @staticmethod
    def create(
        store_id: int,
        name: str = "Test Product",
        status: str = "draft",
        **kwargs
    ) -> Product:
        """Create a test product with default or custom attributes."""
        # Note: 'niche' field was removed from Product model in modular architecture
        # Niche information is now tracked separately in product_intelligence
        return Product(
            store_id=store_id,
            product_name=name,
            status=status,
            **kwargs
        )

    @staticmethod
    def create_deployed(store_id: int) -> Product:
        """Create a deployed product."""
        return ProductFactory.create(
            store_id=store_id,
            name="Deployed Product",
            status="deployed",
            shopify_product_id=12345,
            shopify_handle="deployed-product"
        )

    @staticmethod
    def create_with_confidence(
        store_id: int,
        confidence_score: float = 0.85
    ) -> Product:
        """Create a product with specific confidence score."""
        return ProductFactory.create(
            store_id=store_id,
            name="High Confidence Product",
            confidence_score=confidence_score,
            status="ready"
        )


class ActionFactory:
    """Factory for creating test actions."""

    @staticmethod
    def create(
        user_id: int,
        store_id: int,
        action_type: str = "DEPLOY_PRODUCT",
        status: str = "PENDING",
        confidence: float = 80.0,
        title: str = None,
        rationale: str = None,
        payload: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Action:
        """Create a test action with default or custom attributes."""
        if payload is None:
            payload = {"product_id": 1, "niche": "smart_home"}

        if title is None:
            title = f"Test {action_type}"

        if rationale is None:
            rationale = f"AI recommends this {action_type} action based on market analysis"

        # Ensure factors is set to empty list if not provided
        if "factors" not in kwargs:
            kwargs["factors"] = []

        return Action(
            user_id=user_id,
            store_id=store_id,
            action_type=action_type,
            title=title,
            rationale=rationale,
            status=status,
            confidence=confidence,
            payload=payload,
            **kwargs
        )

    @staticmethod
    def create_completed(user_id: int, store_id: int) -> Action:
        """Create a completed action."""
        return ActionFactory.create(
            user_id=user_id,
            store_id=store_id,
            status="EXECUTING",
            executed_at=datetime.utcnow() - timedelta(hours=1),
            execution_result={"success": True, "product_id": 12345}
        )

    @staticmethod
    def create_failed(user_id: int, store_id: int) -> Action:
        """Create a failed action."""
        return ActionFactory.create(
            user_id=user_id,
            store_id=store_id,
            status="FAILED",
            executed_at=datetime.utcnow() - timedelta(hours=1),
            execution_result={"success": False, "error": "API rate limit exceeded"},
            error_message="API rate limit exceeded"
        )


class CampaignFactory:
    """Factory for creating test ad campaigns."""

    @staticmethod
    def create(
        user_id: int,
        store_id: int,
        product_id: int,
        campaign_name: str = "Test Campaign",
        campaign_id: str = None,
        platform: str = "meta",
        status: str = "draft",
        **kwargs
    ) -> AdCampaign:
        """Create a test ad campaign with default or custom attributes."""
        if campaign_id is None:
            import random
            campaign_id = f"test_campaign_{random.randint(100000, 999999)}"

        return AdCampaign(
            user_id=user_id,
            store_id=store_id,
            product_id=product_id,
            campaign_id=campaign_id,
            campaign_name=campaign_name,
            platform=platform,
            status=status,
            **kwargs
        )

    @staticmethod
    def create_active(user_id: int, store_id: int, product_id: int) -> AdCampaign:
        """Create an active campaign."""
        return CampaignFactory.create(
            user_id=user_id,
            store_id=store_id,
            product_id=product_id,
            campaign_name="Active Campaign",
            status="active",
            daily_budget=50.0
        )

    @staticmethod
    def create_with_metrics(
        user_id: int,
        store_id: int,
        product_id: int,
        impressions: int = 1000,
        clicks: int = 50,
        conversions: int = 5
    ) -> AdCampaign:
        """Create a campaign with specific metrics."""
        return CampaignFactory.create(
            user_id=user_id,
            store_id=store_id,
            product_id=product_id,
            campaign_name="Campaign with Metrics",
            status="active",
            impressions=impressions,
            clicks=clicks,
            conversions=conversions,
            total_spend=25.0
        )
