"""
Saturation Tracker - Prevents AutoDS Problem

Tracks which products are recommended to which users and enforces caps
to prevent too many users from selling the same products.

Key Features:
- Product usage tracking across all users
- Configurable saturation thresholds (default: 100 users per product)
- Automatic product filtering when saturated
- Discovery timestamp tracking
- Performance metrics (success rate, revenue)
- Rotation recommendations when products saturate

This prevents the "AutoDS problem" where everyone sells the same viral products,
leading to market saturation and reduced profitability.
"""

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple
import logging

from ospra_os.database import (
    ProductSaturation,
    UserProductRecommendation,
    User
)

logger = logging.getLogger(__name__)


class SaturationTracker:
    """
    Manages product saturation to prevent too many users from selling the same products.

    Core Philosophy:
    - Each product can be recommended to a maximum number of users (default: 100)
    - Once saturated, product is automatically filtered from future recommendations
    - Tracks performance metrics to identify truly successful products
    - Enables product rotation to maintain freshness
    """

    def __init__(self, database_url: str):
        """
        Initialize the SaturationTracker.

        Args:
            database_url: Database connection string (SQLite or PostgreSQL)
        """
        self.database_url = database_url

        # Convert sqlite:// to sqlite+aiosqlite:// for async support
        if database_url.startswith("sqlite://"):
            async_url = database_url.replace("sqlite://", "sqlite+aiosqlite://")
        elif database_url.startswith("postgresql://"):
            async_url = database_url.replace("postgresql://", "postgresql+asyncpg://")
        else:
            async_url = database_url

        self.engine = create_async_engine(async_url, echo=False)
        self.async_session = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def track_product_discovery(
        self,
        product_name: str,
        source_url: Optional[str] = None,
        source_product_id: Optional[str] = None,
        niche: Optional[str] = None,
        saturation_threshold: int = 100
    ) -> ProductSaturation:
        """
        Track a newly discovered product or update existing product record.

        Args:
            product_name: Name of the product
            source_url: Original product URL (e.g., AliExpress)
            source_product_id: Platform-specific product ID
            niche: Product niche/category
            saturation_threshold: Max users before saturation (default: 100)

        Returns:
            ProductSaturation object
        """
        async with self.async_session() as session:
            # Check if product already exists
            stmt = select(ProductSaturation).where(
                ProductSaturation.product_name == product_name
            )
            result = await session.execute(stmt)
            product = result.scalar_one_or_none()

            if product:
                # Update existing product
                product.last_recommended_at = datetime.now(timezone.utc)
                product.updated_at = datetime.now(timezone.utc)
                logger.info(f"Updated existing product: {product_name}")
            else:
                # Create new product
                product = ProductSaturation(
                    product_name=product_name,
                    source_url=source_url,
                    source_product_id=source_product_id,
                    niche=niche,
                    saturation_threshold=saturation_threshold,
                    first_discovered_at=datetime.now(timezone.utc)
                )
                session.add(product)
                logger.info(f"Tracked new product discovery: {product_name}")

            await session.commit()
            await session.refresh(product)
            return product

    async def recommend_to_user(
        self,
        user_id: int,
        product_saturation_id: int,
        recommendation_score: float,
        was_deployed: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """
        Recommend a product to a user and track the recommendation.

        Args:
            user_id: User ID
            product_saturation_id: ProductSaturation ID
            recommendation_score: AI-generated score for the recommendation
            was_deployed: Whether the product was actually deployed to the store

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        async with self.async_session() as session:
            # Check if product is saturated
            stmt = select(ProductSaturation).where(
                ProductSaturation.id == product_saturation_id
            )
            result = await session.execute(stmt)
            product = result.scalar_one_or_none()

            if not product:
                return False, "Product not found"

            if product.is_saturated:
                return False, f"Product '{product.product_name}' is saturated ({product.total_users_count} users)"

            # Check if already recommended to this user
            stmt = select(UserProductRecommendation).where(
                UserProductRecommendation.user_id == user_id,
                UserProductRecommendation.product_saturation_id == product_saturation_id
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                return False, "Product already recommended to this user"

            # Create recommendation record
            recommendation = UserProductRecommendation(
                user_id=user_id,
                product_saturation_id=product_saturation_id,
                recommendation_score=recommendation_score,
                was_deployed=was_deployed,
                deployed_at=datetime.now(timezone.utc) if was_deployed else None
            )
            session.add(recommendation)

            # Update product counts
            product.total_users_count += 1
            if was_deployed:
                product.active_users_count += 1
            product.last_recommended_at = datetime.now(timezone.utc)
            product.updated_at = datetime.now(timezone.utc)

            # Check if product is now saturated
            if product.total_users_count >= product.saturation_threshold:
                product.is_saturated = True
                logger.warning(f"Product '{product.product_name}' has reached saturation threshold ({product.total_users_count}/{product.saturation_threshold})")

            await session.commit()
            logger.info(f"Recommended product '{product.product_name}' to user {user_id} (count: {product.total_users_count}/{product.saturation_threshold})")
            return True, None

    async def is_product_saturated(
        self,
        product_name: Optional[str] = None,
        product_saturation_id: Optional[int] = None
    ) -> bool:
        """
        Check if a product has reached its saturation threshold.

        Args:
            product_name: Name of the product (alternative to ID)
            product_saturation_id: ProductSaturation ID (alternative to name)

        Returns:
            True if saturated, False otherwise
        """
        async with self.async_session() as session:
            if product_saturation_id:
                stmt = select(ProductSaturation.is_saturated).where(
                    ProductSaturation.id == product_saturation_id
                )
            elif product_name:
                stmt = select(ProductSaturation.is_saturated).where(
                    ProductSaturation.product_name == product_name
                )
            else:
                return False

            result = await session.execute(stmt)
            is_saturated = result.scalar_one_or_none()
            return is_saturated or False

    async def get_saturation_count(self, product_name: str) -> Tuple[int, int]:
        """
        Get current user count and threshold for a product.

        Args:
            product_name: Name of the product

        Returns:
            Tuple of (current_count, threshold)
        """
        async with self.async_session() as session:
            stmt = select(
                ProductSaturation.total_users_count,
                ProductSaturation.saturation_threshold
            ).where(ProductSaturation.product_name == product_name)

            result = await session.execute(stmt)
            row = result.one_or_none()

            if row:
                return row[0], row[1]
            return 0, 100  # Default threshold

    async def filter_saturated_products(
        self,
        products: List[Dict],
        product_name_key: str = "product_name"
    ) -> List[Dict]:
        """
        Filter out saturated products from a list of product dictionaries.

        Args:
            products: List of product dictionaries
            product_name_key: Dictionary key containing product name

        Returns:
            Filtered list with saturated products removed
        """
        if not products:
            return []

        async with self.async_session() as session:
            # Get all product names from the input list
            product_names = [p.get(product_name_key) for p in products if p.get(product_name_key)]

            if not product_names:
                return products

            # Query saturated products
            stmt = select(ProductSaturation.product_name).where(
                ProductSaturation.product_name.in_(product_names),
                ProductSaturation.is_saturated == True
            )
            result = await session.execute(stmt)
            saturated_names = {row[0] for row in result.all()}

            # Filter out saturated products
            filtered = [
                p for p in products
                if p.get(product_name_key) not in saturated_names
            ]

            removed_count = len(products) - len(filtered)
            if removed_count > 0:
                logger.info(f"Filtered out {removed_count} saturated products from {len(products)} total")

            return filtered

    async def get_saturation_stats(self, niche: Optional[str] = None) -> Dict:
        """
        Get overall saturation statistics.

        Args:
            niche: Optional niche filter

        Returns:
            Dictionary with saturation statistics
        """
        async with self.async_session() as session:
            # Base query
            stmt = select(ProductSaturation)
            if niche:
                stmt = stmt.where(ProductSaturation.niche == niche)

            result = await session.execute(stmt)
            products = result.scalars().all()

            total_products = len(products)
            saturated_products = sum(1 for p in products if p.is_saturated)
            total_users = sum(p.total_users_count for p in products)
            active_users = sum(p.active_users_count for p in products)
            total_revenue = sum(p.total_revenue_generated or 0 for p in products)

            # Calculate average success rate
            success_rates = [p.avg_success_rate for p in products if p.avg_success_rate]
            avg_success_rate = sum(success_rates) / len(success_rates) if success_rates else 0.0

            # Find most saturated products
            most_saturated = sorted(
                products,
                key=lambda p: p.total_users_count,
                reverse=True
            )[:10]

            stats = {
                "total_products": total_products,
                "saturated_products": saturated_products,
                "unsaturated_products": total_products - saturated_products,
                "saturation_rate": (saturated_products / total_products * 100) if total_products > 0 else 0,
                "total_user_recommendations": total_users,
                "active_deployments": active_users,
                "total_revenue_generated": total_revenue,
                "avg_success_rate": avg_success_rate,
                "most_saturated": [
                    {
                        "product_name": p.product_name,
                        "total_users": p.total_users_count,
                        "active_users": p.active_users_count,
                        "threshold": p.saturation_threshold,
                        "is_saturated": p.is_saturated,
                        "revenue": p.total_revenue_generated or 0,
                        "success_rate": p.avg_success_rate or 0
                    }
                    for p in most_saturated
                ]
            }

            return stats

    async def update_product_performance(
        self,
        product_saturation_id: int,
        user_id: int,
        total_sales: int,
        total_revenue: float,
        was_successful: bool
    ) -> bool:
        """
        Update performance metrics for a product recommendation.

        Args:
            product_saturation_id: ProductSaturation ID
            user_id: User ID
            total_sales: Total sales count
            total_revenue: Total revenue generated
            was_successful: Whether the product was successful for this user

        Returns:
            True if updated successfully
        """
        async with self.async_session() as session:
            # Update user recommendation
            stmt = select(UserProductRecommendation).where(
                UserProductRecommendation.product_saturation_id == product_saturation_id,
                UserProductRecommendation.user_id == user_id
            )
            result = await session.execute(stmt)
            recommendation = result.scalar_one_or_none()

            if not recommendation:
                return False

            recommendation.total_sales = total_sales
            recommendation.total_revenue = total_revenue
            recommendation.was_successful = was_successful

            # Recalculate product-level metrics
            stmt = select(UserProductRecommendation).where(
                UserProductRecommendation.product_saturation_id == product_saturation_id
            )
            result = await session.execute(stmt)
            all_recommendations = result.scalars().all()

            # Update product saturation metrics
            stmt = select(ProductSaturation).where(
                ProductSaturation.id == product_saturation_id
            )
            result = await session.execute(stmt)
            product = result.scalar_one_or_none()

            if product:
                # Calculate average success rate
                successful_count = sum(1 for r in all_recommendations if r.was_successful)
                product.avg_success_rate = (successful_count / len(all_recommendations) * 100) if all_recommendations else 0

                # Calculate total revenue
                product.total_revenue_generated = sum(r.total_revenue for r in all_recommendations)
                product.updated_at = datetime.now(timezone.utc)

            await session.commit()
            logger.info(f"Updated performance for product {product_saturation_id}, user {user_id}")
            return True

    async def get_product_recommendations_for_user(self, user_id: int) -> List[Dict]:
        """
        Get all product recommendations for a specific user.

        Args:
            user_id: User ID

        Returns:
            List of product recommendation dictionaries
        """
        async with self.async_session() as session:
            stmt = select(
                UserProductRecommendation,
                ProductSaturation
            ).join(
                ProductSaturation,
                UserProductRecommendation.product_saturation_id == ProductSaturation.id
            ).where(
                UserProductRecommendation.user_id == user_id,
                UserProductRecommendation.is_active == True
            ).order_by(UserProductRecommendation.recommended_at.desc())

            result = await session.execute(stmt)
            rows = result.all()

            recommendations = []
            for rec, product in rows:
                recommendations.append({
                    "product_name": product.product_name,
                    "source_url": product.source_url,
                    "niche": product.niche,
                    "recommended_at": rec.recommended_at.isoformat(),
                    "recommendation_score": rec.recommendation_score,
                    "was_deployed": rec.was_deployed,
                    "deployed_at": rec.deployed_at.isoformat() if rec.deployed_at else None,
                    "total_sales": rec.total_sales,
                    "total_revenue": rec.total_revenue,
                    "was_successful": rec.was_successful,
                    "saturation_count": product.total_users_count,
                    "saturation_threshold": product.saturation_threshold,
                    "is_saturated": product.is_saturated
                })

            return recommendations

    async def rotate_saturated_products(
        self,
        niche: str,
        min_success_rate: float = 50.0,
        days_old: int = 30
    ) -> List[ProductSaturation]:
        """
        Find saturated products that should be rotated out based on performance.

        Products are candidates for rotation if:
        - They are saturated
        - Success rate is below threshold
        - They were discovered more than X days ago

        Args:
            niche: Product niche to check
            min_success_rate: Minimum success rate to keep product (default: 50%)
            days_old: Minimum days since discovery (default: 30)

        Returns:
            List of products recommended for rotation
        """
        async with self.async_session() as session:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)

            stmt = select(ProductSaturation).where(
                ProductSaturation.niche == niche,
                ProductSaturation.is_saturated == True,
                ProductSaturation.avg_success_rate < min_success_rate,
                ProductSaturation.first_discovered_at < cutoff_date
            ).order_by(ProductSaturation.avg_success_rate.asc())

            result = await session.execute(stmt)
            rotation_candidates = result.scalars().all()

            logger.info(f"Found {len(rotation_candidates)} products in {niche} ready for rotation")
            return rotation_candidates

    async def close(self):
        """Close database connections."""
        await self.engine.dispose()
