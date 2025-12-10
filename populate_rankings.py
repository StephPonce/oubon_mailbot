#!/usr/bin/env python3
"""
Populate product rankings by ensuring products have correct status
"""

import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from ospra_os.database.multi_store_models import Product, ProductStatus, Store, User, Platform, SubscriptionTier
from ospra_os.intelligence.ranking_engine import RankingEngine
import random

DATABASE_URL = "sqlite:///./multi_store.db"

def setup_database():
    """Initialize database and session"""
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}
    )

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()


async def populate_rankings():
    """Check and populate product rankings"""
    db = setup_database()

    try:
        # Check if we have a user and store
        user = db.query(User).first()
        if not user:
            print("📝 Creating demo user...")
            user = User(
                email="demo@ospraos.com",
                name="Demo User",
                subscription_tier=SubscriptionTier.SOAR
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        store = db.query(Store).filter(Store.user_id == user.id).first()
        if not store:
            print("📝 Creating demo store...")
            store = Store(
                user_id=user.id,
                store_name="Demo Store",
                store_url="demo.myshopify.com",
                platform=Platform.SHOPIFY,
                credentials={"shop_url": "demo.myshopify.com", "access_token": "demo"},
                is_active=True
            )
            db.add(store)
            db.commit()
            db.refresh(store)

        # Check existing products
        all_products = db.query(Product).all()
        print(f"\n📊 Found {len(all_products)} total products")

        # Count by status
        statuses = {}
        for p in all_products:
            status = p.status if hasattr(p, 'status') else 'unknown'
            statuses[status] = statuses.get(status, 0) + 1

        print(f"   Status breakdown: {statuses}")

        # Update products to have correct status for ranking
        active_count = 0
        for product in all_products[:50]:  # Update top 50 products
            if product.status not in [ProductStatus.ACTIVE, ProductStatus.DEPLOYED]:
                product.status = ProductStatus.ACTIVE

                # Ensure product has a store_id
                if not product.store_id:
                    product.store_id = store.id

                # Ensure product has some scoring data
                if not product.trend_score or product.trend_score == 0:
                    product.trend_score = random.uniform(40, 95)

                if not product.discovery_score or product.discovery_score == 0:
                    product.discovery_score = random.uniform(5, 9.5)

                if not product.profit_margin or product.profit_margin == 0:
                    product.profit_margin = random.uniform(20, 60)

                if not product.total_sales:
                    product.total_sales = random.randint(0, 500)

                active_count += 1

        db.commit()
        print(f"✅ Updated {active_count} products to ACTIVE status with scoring data")

        # Now test the ranking engine
        print("\n🔍 Testing RankingEngine...")
        engine = RankingEngine(db)

        rankings = await engine.get_current_rankings(limit=20)

        print(f"\n🏆 TOP 20 RANKINGS:")
        print("=" * 80)

        if not rankings:
            print("❌ No rankings generated - may need more products with ACTIVE/DEPLOYED status")
        else:
            for product in rankings:
                tier = product.get('tier', {})
                tier_emoji = tier.get('emoji', '📊')
                tier_name = tier.get('name', 'N/A')

                print(f"{product['rank']:2d}. {tier_emoji} {product['product_name'][:50]}")
                print(f"    Score: {product['composite_score']:.1f} | Tier: {tier_name}")
                print(f"    Breakdown: Trend={product['score_breakdown']['trend_score']:.1f}, "
                      f"Sales={product['score_breakdown']['sales_velocity']:.1f}, "
                      f"Social={product['score_breakdown']['social_sentiment']:.1f}")
                print()

        print("=" * 80)
        print(f"✅ Rankings populated! {len(rankings)} products ranked")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(populate_rankings())
