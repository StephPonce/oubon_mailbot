"""
Quick Script to Populate Real Products from AliExpress
=======================================================
Uses the working UnifiedProductDiscoveryV2 engine and saves products to database.
"""

import asyncio
import sys
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Use the discovery engine that's already working
try:
    from ospra_os.intelligence.unified_product_discovery import get_discovery_engine
except ImportError:
    print("❌ Discovery engine not available")
    sys.exit(1)

DATABASE_URL = "sqlite:///data/product_history.db"

# Niches to populate
NICHES = [
    "smart_home",
    "lighting",
    "kitchen",
    "fitness",
    "beauty",
    "pet",
    "tech",
    "office",
]

async def fetch_and_save_products(niche_id: str, max_products: int = 20):
    """Fetch real products using discovery engine and save to database"""

    print(f"\n🔍 Discovering {niche_id}...")

    # Get discovery engine
    engine = get_discovery_engine()

    try:
        # Discover products
        results = await engine.discover_products(
            niche=niche_id,
            max_products=max_products,
            min_score=0  # Accept all products
        )

        if not results:
            print(f"   ⚠️  No products found for {niche_id}")
            return 0

        print(f"   ✅ Found {len(results)} products")

        # Create database session
        engine = create_engine(DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()

        saved_count = 0

        for product in results:
            try:
                # Extract data from discovery results (using correct field names!)
                product_id = product.get("product_id", product.get("id", f"temp_{niche_id}_{saved_count}"))
                title = product.get("title", product.get("name", "Unknown Product"))[:200]
                price = float(product.get("price", 0))
                cost = float(product.get("original_price", price)) * 0.6  # Estimate cost as 60% of original
                image_url = product.get("main_image", product.get("image_url", ""))  # CORRECT: main_image
                product_url = product.get("affiliate_link", product.get("source_url", product.get("url", "")))  # CORRECT: affiliate_link
                score = float(product.get("final_score", product.get("score", 5.0)))

                # Calculate margin
                margin = ((price - cost) / price * 100) if price > 0 else 0

                # Insert or update product
                query = text("""
                    INSERT OR REPLACE INTO products
                    (id, name, niche, price, cost, score, profit_margin, estimated_profit,
                     image_url, aliexpress_url, source, last_updated)
                    VALUES
                    (:id, :name, :niche, :price, :cost, :score, :profit_margin, :profit,
                     :image_url, :url, 'aliexpress', :updated)
                """)

                session.execute(query, {
                    "id": product_id,
                    "name": title,
                    "niche": niche_id,
                    "price": price,
                    "cost": cost,
                    "score": score,
                    "profit_margin": margin,
                    "profit": price - cost,
                    "image_url": image_url,
                    "url": product_url,
                    "updated": datetime.now().isoformat()
                })

                saved_count += 1

            except Exception as e:
                print(f"   ⚠️  Failed to save product: {e}")
                continue

        # Commit all changes
        session.commit()
        session.close()

        print(f"   💾 Saved {saved_count}/{len(results)} products to database")
        return saved_count

    except Exception as e:
        print(f"   ❌ Error fetching products: {e}")
        return 0


async def main():
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("🚀 POPULATING REAL PRODUCTS FROM ALIEXPRESS")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"   Target: {len(NICHES)} niches")
    print(f"   Products per niche: 20")
    print(f"   Expected total: ~{len(NICHES) * 20} products")
    print()

    total_saved = 0

    for niche_id in NICHES:
        count = await fetch_and_save_products(niche_id, max_products=15)
        total_saved += count
        await asyncio.sleep(2)  # Rate limiting

    print()
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"✅ DONE! Saved {total_saved} real products")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()
    print("Now refresh your dashboard to see real products!")
    print("   → http://localhost:5173/products")


if __name__ == "__main__":
    asyncio.run(main())
