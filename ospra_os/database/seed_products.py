"""
🌱 PRODUCT SEEDING SCRIPT
Fetch products from discovery service and store in database
"""

import logging
from ospra_os.database.product_history import ProductHistoryDB
from ospra_os.intelligence.product_intelligence import ProductIntelligenceEngine
from ospra_os.intelligence.product_enrichment import enrich_product

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def seed_products(niches=None, per_page=20):
    """
    Fetch products once and store in database

    Args:
        niches: List of niches to fetch (default: smart_home, fitness, kitchen, beauty, pet)
        per_page: Number of products per niche (default: 20)
    """

    if niches is None:
        niches = ['smart_home', 'fitness', 'kitchen', 'beauty', 'pet']

    db = ProductHistoryDB()
    discovery = ProductIntelligenceEngine()

    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("🌱 SEEDING PRODUCTS DATABASE")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

    all_products = []

    for niche in niches:
        print(f"📦 Fetching {niche} products...")

        try:
            products = discovery.discover_products_by_niche(niche=niche, count=per_page)

            print(f"   Found {len(products)} products")

            # Enrich each product
            for i, product in enumerate(products, 1):
                try:
                    enriched = enrich_product(product)
                    all_products.append(enriched)
                    print(f"   ✓ Enriched: {enriched['name']}")
                except Exception as e:
                    logger.error(f"   ✗ Failed to enrich product {i}: {e}")
                    # Add non-enriched product as fallback
                    all_products.append(product)

            print()

        except Exception as e:
            logger.error(f"Failed to fetch {niche}: {e}")
            continue

    # Save to database
    if all_products:
        print(f"💾 Saving {len(all_products)} products to database...")
        db.save_products(all_products)

        # Verify
        saved_count = len(db.get_all_products())

        print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"✅ Seeded {len(all_products)} products")
        print(f"✅ Database now contains {saved_count} total products")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

        # Show breakdown by niche
        print("📊 Products by niche:")
        for niche in niches:
            niche_products = db.get_all_products(niche=niche)
            print(f"   • {niche}: {len(niche_products)} products")
        print()

    else:
        print("\n❌ No products to seed")

    return all_products


def reseed_niche(niche: str, per_page=20):
    """
    Reseed products for a specific niche

    Args:
        niche: Niche to reseed
        per_page: Number of products to fetch
    """
    print(f"\n🔄 Reseeding {niche} niche...")
    return seed_products(niches=[niche], per_page=per_page)


def clear_database():
    """Clear all products from database"""
    db = ProductHistoryDB()

    import sqlite3
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM products")
    deleted_count = cursor.rowcount

    conn.commit()
    conn.close()

    print(f"🗑️  Cleared {deleted_count} products from database")


if __name__ == "__main__":
    import sys

    # Parse command line arguments
    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "clear":
            clear_database()
        elif command == "reseed":
            if len(sys.argv) > 2:
                niche = sys.argv[2]
                reseed_niche(niche)
            else:
                print("Usage: python seed_products.py reseed <niche>")
        else:
            print("Unknown command. Usage:")
            print("  python seed_products.py          - Seed all niches")
            print("  python seed_products.py clear    - Clear database")
            print("  python seed_products.py reseed <niche> - Reseed specific niche")
    else:
        # Default: seed all products
        seed_products()
