#!/usr/bin/env python3
"""
Seed Learning System from Shopify Historical Data
==================================================

This script populates the learning database with historical Shopify orders and products.

Usage:
    uv run python scripts/seed_learning_from_shopify.py

What it does:
1. Fetches all Shopify orders from the past 12 months
2. Fetches all Shopify products
3. Inserts learning_events for each sale (event_type: 'historical_sale')
4. Calculates initial global_learning_weights based on historical performance
5. Creates personal_learning_weights for user 1 (if data exists)

After running this, Claude will have REAL historical data to reference when making recommendations.
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Dict, Any
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ospra_os.platforms.shopify import ShopifyAdapter
from ospra_os.database.connection import SessionLocal, engine as db_engine
from ospra_os.learning.hybrid_learning_engine import (
    LearningEvent,
    GlobalLearningWeights,
    PersonalLearningWeights,
    DEFAULT_SCORING_WEIGHTS,
    Base
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def fetch_shopify_data(months_back: int = 12):
    """
    Fetch historical orders and products from Shopify.

    Args:
        months_back: How many months of history to fetch (default: 12)

    Returns:
        Tuple of (orders, products)
    """
    # Load credentials from environment
    credentials = {
        "store_domain": os.getenv("SHOPIFY_STORE_DOMAIN", "rxxj7d-1i.myshopify.com"),
        "admin_api_token": os.getenv("SHOPIFY_ACCESS_TOKEN", ""),
        "api_version": "2024-01"
    }

    if not credentials["admin_api_token"]:
        logger.error("[ERROR] SHOPIFY_ACCESS_TOKEN not found in environment")
        return [], []

    adapter = ShopifyAdapter(credentials)

    # Test connection
    logger.info("[PLUGIN] Testing Shopify connection...")
    conn_result = await adapter.test_connection()
    if not conn_result.get("success"):
        logger.error(f"[ERROR] Shopify connection failed: {conn_result}")
        return [], []

    logger.info(f"[SUCCESS] Connected to {conn_result.get('store_name')}")

    # Fetch orders from past N months
    since_date = datetime.utcnow() - timedelta(days=months_back * 30)
    logger.info(f"[PACKAGE] Fetching orders since {since_date.strftime('%Y-%m-%d')}...")

    orders_result = await adapter.get_orders(limit=250, status="any", since=since_date)
    orders = orders_result.get("orders", [])
    logger.info(f"   Found {len(orders)} orders")

    # Fetch products
    logger.info("[PACKAGE] Fetching products...")
    products_result = await adapter.get_products(limit=250, published_status="any")
    products = products_result.get("products", [])
    logger.info(f"   Found {len(products)} products")

    return orders, products


def extract_niche_from_product(product: Dict[str, Any]) -> str:
    """
    Extract niche from product metadata (tags, product_type, etc.)

    Args:
        product: Shopify product dict

    Returns:
        Niche string (defaults to 'unknown')
    """
    # Check tags first
    tags = product.get("tags", [])
    for tag in tags:
        tag_lower = tag.lower()
        if "smart_home" in tag_lower or "home" in tag_lower:
            return "smart_home"
        elif "fitness" in tag_lower or "gym" in tag_lower:
            return "fitness"
        elif "kitchen" in tag_lower or "cooking" in tag_lower:
            return "kitchen"
        elif "tech" in tag_lower or "gadget" in tag_lower:
            return "tech"
        elif "beauty" in tag_lower or "skincare" in tag_lower:
            return "beauty"
        elif "pet" in tag_lower:
            return "pets"

    # Check product_type
    product_type = product.get("product_type", "").lower()
    if "home" in product_type:
        return "smart_home"
    elif "fitness" in product_type:
        return "fitness"
    elif "kitchen" in product_type:
        return "kitchen"

    # Default
    return "unknown"


async def seed_learning_events(orders: List[Dict], products: List[Dict], db: SessionLocal):
    """
    Create learning_events from Shopify orders.

    Args:
        orders: List of Shopify orders
        products: List of Shopify products (for metadata)
        db: Database session
    """
    logger.info("[NOTE] Creating learning events from order history...")

    # Build product lookup by ID
    product_lookup = {p["platform_product_id"]: p for p in products}

    events_created = 0
    total_revenue = 0.0

    for order in orders:
        # Process each line item
        for item in order.get("line_items", []):
            product_id = item["product_id"]
            product = product_lookup.get(product_id)

            # Extract niche
            niche = extract_niche_from_product(product) if product else "unknown"

            # Calculate revenue for this line item
            item_revenue = float(item["price"]) * int(item["quantity"])
            total_revenue += item_revenue

            # Create learning event
            event = LearningEvent(
                user_id=1,  # Default to user 1
                event_type="historical_sale",
                product_id=product_id,
                details={
                    "product_name": item["title"],
                    "niche": niche,
                    "price": float(item["price"]),
                    "quantity": item["quantity"],
                    "revenue": item_revenue,
                    "order_id": order["platform_order_id"],
                    "order_date": order["created_at"],
                    "sku": item.get("sku", ""),
                    # Note: We don't have AI predicted_score for historical data
                    # These were organic sales, not AI-driven deployments
                    "predicted_score": None,
                    "source": "shopify_historical"
                },
                accuracy_before=None,
                accuracy_after=None,
                timestamp=datetime.fromisoformat(order["created_at"].replace("Z", "+00:00"))
            )

            db.add(event)
            events_created += 1

    db.commit()

    logger.info(f"[SUCCESS] Created {events_created} learning events")
    logger.info(f"[PRICE] Total historical revenue: ${total_revenue:,.2f}")

    return events_created, total_revenue


async def calculate_global_weights(db: SessionLocal):
    """
    Calculate initial global_learning_weights from historical events.

    Args:
        db: Database session
    """
    logger.info("[BRAIN] Calculating global learning weights...")

    # Fetch all learning events
    events = db.query(LearningEvent).filter(
        LearningEvent.event_type == "historical_sale"
    ).all()

    if not events:
        logger.warning("[WARNING] No learning events found - skipping weight calculation")
        return

    # Aggregate stats by niche
    niche_stats = defaultdict(lambda: {"revenue": 0.0, "units": 0, "count": 0})
    price_ranges = defaultdict(lambda: {"revenue": 0.0, "units": 0, "count": 0})

    total_revenue = 0.0
    total_units = 0

    for event in events:
        details = event.details
        niche = details.get("niche", "unknown")
        price = details.get("price", 0)
        quantity = details.get("quantity", 0)
        revenue = details.get("revenue", 0)

        # Niche aggregation
        niche_stats[niche]["revenue"] += revenue
        niche_stats[niche]["units"] += quantity
        niche_stats[niche]["count"] += 1

        # Price range aggregation
        if price < 20:
            price_range = "under_20"
        elif price < 40:
            price_range = "20_to_40"
        elif price < 60:
            price_range = "40_to_60"
        else:
            price_range = "over_60"

        price_ranges[price_range]["revenue"] += revenue
        price_ranges[price_range]["units"] += quantity
        price_ranges[price_range]["count"] += 1

        total_revenue += revenue
        total_units += quantity

    # Calculate niche confidence (revenue-weighted)
    niche_confidence = {}
    for niche, stats in niche_stats.items():
        confidence = stats["revenue"] / total_revenue if total_revenue > 0 else 0
        niche_confidence[niche] = round(confidence, 4)

    # Calculate price confidence
    price_confidence = {}
    for price_range, stats in price_ranges.items():
        confidence = stats["revenue"] / total_revenue if total_revenue > 0 else 0
        price_confidence[price_range] = round(confidence, 4)

    # Sort niches by confidence
    top_niches = sorted(niche_confidence.items(), key=lambda x: x[1], reverse=True)[:5]

    # Create or update global weights
    global_weights = db.query(GlobalLearningWeights).first()

    if not global_weights:
        global_weights = GlobalLearningWeights(
            version="1.0",
            learning_cycles=1,
            scoring_weights=DEFAULT_SCORING_WEIGHTS,
            niche_confidence=niche_confidence,
            price_confidence=price_confidence,
            trend_velocity={
                "fast_trending_threshold": 0.7,
                "moderate_trending_threshold": 0.4,
                "slow_trending_threshold": 0.2
            },
            accuracy={
                "total_predictions": 0,
                "correct_predictions": 0,
                "accuracy_rate": 0.0,
                "note": "No AI predictions yet (historical data only)"
            },
            total_users_contributing=1,
            total_sales_analyzed=len(events),
            total_revenue_analyzed=total_revenue
        )
        db.add(global_weights)
    else:
        # Update existing
        global_weights.learning_cycles += 1
        global_weights.niche_confidence = niche_confidence
        global_weights.price_confidence = price_confidence
        global_weights.total_sales_analyzed = len(events)
        global_weights.total_revenue_analyzed = total_revenue
        global_weights.updated_at = datetime.utcnow()

    db.commit()

    logger.info("[SUCCESS] Global learning weights calculated:")
    logger.info(f"   Top niches: {', '.join([f'{n}({c:.1%})' for n, c in top_niches])}")
    logger.info(f"   Total sales analyzed: {len(events)}")
    logger.info(f"   Total revenue: ${total_revenue:,.2f}")


async def calculate_personal_weights(user_id: int, db: SessionLocal):
    """
    Calculate personal_learning_weights for a specific user.

    Args:
        user_id: User ID
        db: Database session
    """
    logger.info(f" Calculating personal weights for user {user_id}...")

    # Fetch user's learning events
    events = db.query(LearningEvent).filter(
        LearningEvent.user_id == user_id,
        LearningEvent.event_type == "historical_sale"
    ).all()

    if not events:
        logger.warning(f"[WARNING] No learning events for user {user_id} - skipping personal weights")
        return

    # Aggregate user's niche performance
    niche_performance = defaultdict(lambda: {"revenue": 0.0, "units": 0})
    price_stats = []

    total_revenue = 0.0

    for event in events:
        details = event.details
        niche = details.get("niche", "unknown")
        price = details.get("price", 0)
        revenue = details.get("revenue", 0)
        quantity = details.get("quantity", 0)

        niche_performance[niche]["revenue"] += revenue
        niche_performance[niche]["units"] += quantity
        price_stats.append(price)
        total_revenue += revenue

    # Find best performing niches
    best_niches = sorted(
        niche_performance.items(),
        key=lambda x: x[1]["revenue"],
        reverse=True
    )[:5]

    best_niche_names = [niche for niche, _ in best_niches]

    # Calculate optimal price range
    if price_stats:
        min_price = min(price_stats)
        max_price = max(price_stats)
        optimal_price_range = {"min": round(min_price, 2), "max": round(max_price, 2)}
    else:
        optimal_price_range = {}

    # Create or update personal weights
    personal = db.query(PersonalLearningWeights).filter_by(user_id=user_id).first()

    if not personal:
        personal = PersonalLearningWeights(
            user_id=user_id,
            version="1.0",
            learning_cycles=1,
            scoring_adjustments={},
            niche_adjustments={},
            price_adjustments={},
            best_performing_niches=best_niche_names,
            optimal_price_range=optimal_price_range,
            peak_selling_days=[],
            predictions_made=0,
            predictions_correct=0,
            accuracy_rate=0.0,
            sales_analyzed=len(events),
            revenue_analyzed=total_revenue
        )
        db.add(personal)
    else:
        # Update existing
        personal.learning_cycles += 1
        personal.best_performing_niches = best_niche_names
        personal.optimal_price_range = optimal_price_range
        personal.sales_analyzed = len(events)
        personal.revenue_analyzed = total_revenue
        personal.updated_at = datetime.utcnow()

    db.commit()

    logger.info(f"[SUCCESS] Personal weights calculated:")
    logger.info(f"   Best niches: {', '.join(best_niche_names)}")
    logger.info(f"   Optimal price range: ${optimal_price_range.get('min', 0):.2f} - ${optimal_price_range.get('max', 0):.2f}")
    logger.info(f"   Sales analyzed: {len(events)}")


async def main():
    """Main seeding function"""
    print("=" * 80)
    print(" SEEDING LEARNING SYSTEM FROM SHOPIFY")
    print("=" * 80)
    print()

    # Create tables if they don't exist
    logger.info("[PACKAGE] Creating database tables...")
    Base.metadata.create_all(bind=db_engine)

    # Fetch Shopify data
    orders, products = await fetch_shopify_data(months_back=12)

    if not orders:
        logger.warning("[WARNING] No orders found - nothing to seed")
        print()
        print("=" * 80)
        print("[TIP] TIP: Make sure you have Shopify orders in the past 12 months")
        print("=" * 80)
        return

    # Create database session
    db = SessionLocal()

    try:
        # Seed learning events
        events_count, total_revenue = await seed_learning_events(orders, products, db)

        # Calculate global weights
        await calculate_global_weights(db)

        # Calculate personal weights for user 1
        await calculate_personal_weights(user_id=1, db=db)

        print()
        print("=" * 80)
        print("[SUCCESS] SEEDING COMPLETE")
        print("=" * 80)
        print()
        print(f"[STATS] Summary:")
        print(f"   - Learning events created: {events_count}")
        print(f"   - Total revenue analyzed: ${total_revenue:,.2f}")
        print(f"   - Global weights: [SUCCESS] Calculated")
        print(f"   - Personal weights (user 1): [SUCCESS] Calculated")
        print()
        print("[TEST] Verification:")
        print()
        print("   1. Check database:")
        print(f"      sqlite3 multi_store.db \"SELECT COUNT(*) FROM learning_events;\"")
        print()
        print("   2. Test Claude chat:")
        print("      curl -X POST http://localhost:8001/api/dashboard/v2/claude/chat \\")
        print("        -H \"Content-Type: application/json\" \\")
        print("        -d '{\"message\": \"What should I sell?\", \"user_id\": 1}'")
        print()
        print("   3. Get learning insights:")
        print("      curl http://localhost:8001/api/learning/insights/1")
        print()
        print("=" * 80)

    except Exception as e:
        logger.error(f"[ERROR] Seeding failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
