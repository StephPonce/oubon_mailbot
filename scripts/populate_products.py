#!/usr/bin/env python3
"""
Populate product database with discovered products from live APIs.

This script discovers products using Google Trends, Reddit, and AliExpress,
then saves them to the database for niche analysis.
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from ospra_os.database.multi_store_models import Product, ProductSaturation, Base
from datetime import datetime
import requests

# Database setup
DATABASE_URL = "sqlite:///./oubon_store.db"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

# Ensure tables exist
Base.metadata.create_all(engine)

# Niches to discover
NICHES = [
    ("smart_home", "smart home gadgets"),
    ("fitness", "fitness equipment"),
    ("health", "health wellness products"),
    ("trending", "trending products 2025")
]

def discover_products_for_niche(niche_id: str, search_query: str) -> list:
    """Discover products using the product research API."""
    print(f"\n🔍 Discovering products for: {niche_id}")

    url = "http://localhost:8001/research/discover"
    payload = {
        "niche": search_query,
        "max_results": 25,
        "min_score": 3.0,
        "include_reddit": True,
        "include_aliexpress": True,
        "include_trends": True
    }

    try:
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()

        products = data.get("products", [])
        print(f"✅ Found {len(products)} products for {niche_id}")
        return products
    except Exception as e:
        print(f"❌ Error discovering products for {niche_id}: {e}")
        return []

def import_products_to_database(niche_id: str, discovered_products: list):
    """Import discovered products into Product and ProductSaturation tables."""
    session = Session()
    imported_count = 0

    try:
        for item in discovered_products:
            product_data = item.get("product", {})
            score = item.get("score", 0)

            # Extract product details
            product_name = product_data.get("name", "Unknown Product")
            source = product_data.get("source", "unknown")
            price = product_data.get("price")
            url = product_data.get("url")
            trend_score = product_data.get("trend_score", 0)
            social_mentions = product_data.get("social_mentions", 0)

            # Check if product already exists
            existing_product = session.query(Product).filter_by(
                product_name=product_name,
                source_platform=source
            ).first()

            if not existing_product:
                # Create new product
                new_product = Product(
                    store_id=1,  # Default store
                    product_name=product_name,
                    source_platform=source,
                    source_url=url,
                    selling_price=price if price else 0.0,
                    discovery_score=score,
                    trend_score=trend_score,
                    status="discovered"
                )
                session.add(new_product)
                session.flush()  # Get the ID
                product_id = new_product.id
                imported_count += 1
            else:
                product_id = existing_product.id
                # Update scores
                existing_product.discovery_score = max(existing_product.discovery_score or 0, score)
                existing_product.trend_score = max(existing_product.trend_score or 0, trend_score)

            # Create or update ProductSaturation record
            existing_saturation = session.query(ProductSaturation).filter_by(
                product_name=product_name,
                niche=niche_id
            ).first()

            if not existing_saturation:
                saturation = ProductSaturation(
                    product_name=product_name,
                    niche=niche_id,
                    total_users_count=int(social_mentions) if social_mentions else 1,
                    active_users_count=int(social_mentions * 0.3) if social_mentions else 0,
                    source_url=url
                )
                session.add(saturation)
            else:
                existing_saturation.total_users_count = max(
                    existing_saturation.total_users_count,
                    int(social_mentions) if social_mentions else 1
                )

        session.commit()
        print(f"✅ Imported {imported_count} new products for {niche_id}")

    except Exception as e:
        session.rollback()
        print(f"❌ Error importing products for {niche_id}: {e}")
    finally:
        session.close()

def main():
    """Main execution function."""
    print("🚀 Starting product discovery and database population...")
    print(f"📊 Target niches: {len(NICHES)}")

    total_products = 0

    for niche_id, search_query in NICHES:
        # Discover products
        products = discover_products_for_niche(niche_id, search_query)

        if products:
            # Import to database
            import_products_to_database(niche_id, products)
            total_products += len(products)

        # Small delay between niches
        import time
        time.sleep(2)

    print(f"\n✅ COMPLETE! Total products discovered: {total_products}")
    print(f"📊 Database populated with real data from:")
    print(f"   • Google Trends")
    print(f"   • Reddit (live discussions)")
    print(f"   • AliExpress (product marketplace)")
    print(f"\n🎯 You can now run niche analysis with real data!")

if __name__ == "__main__":
    main()
