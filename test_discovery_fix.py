#!/usr/bin/env python3
"""
Direct test of product discovery with Apify - bypasses all the routing complexity.
This will help us:
1. Test if Apify credentials work
2. Populate the database with real products
3. Identify if the issue is with Apify or the routing/initialization
"""
import asyncio
import os
from dotenv import load_dotenv

# Load environment
load_dotenv()

print("=" * 80)
print("🧪 DIRECT PRODUCT DISCOVERY TEST")
print("=" * 80)
print()

# Check Apify credentials
apify_token = os.getenv('APIFY_API_TOKEN')
apify_user = os.getenv('APIFY_USER_ID')

print("1. CHECKING APIFY CREDENTIALS:")
print(f"   APIFY_API_TOKEN: {'✅ SET' if apify_token else '❌ NOT SET'}")
print(f"   APIFY_USER_ID: {'✅ SET' if apify_user else '❌ NOT SET'}")
print()

if not apify_token:
    print("❌ ERROR: APIFY_API_TOKEN not set in environment")
    print("   Please check your .env file")
    exit(1)

# Try to import and initialize MultiSourceDiscovery
print("2. INITIALIZING DISCOVERY ENGINE:")
try:
    from ospra_os.product_research.multi_source_discovery import MultiSourceDiscovery
    discovery = MultiSourceDiscovery()
    print("   ✅ MultiSourceDiscovery imported and initialized")
except Exception as e:
    print(f"   ❌ Failed to initialize: {e}")
    exit(1)

print()
print("3. CHECKING APIFY SCRAPERS:")
print(f"   TikTok Scraper: {'✅ Available' if discovery.tiktok else '❌ Not available'}")
print(f"   Amazon Bestsellers: {'✅ Available' if discovery.amazon_bestsellers else '❌ Not available'}")
print(f"   Reddit Scraper: {'✅ Available' if discovery.reddit else '❌ Not available'}")
print(f"   Shopify Scraper: {'✅ Available' if discovery.shopify_competitor else '❌ Not available'}")
print()

# Try to discover products for smart_home niche
print("4. RUNNING PRODUCT DISCOVERY FOR 'smart_home' NICHE:")
print("   This may take 1-2 minutes as Apify actors need to run...")
print()

async def test_discovery():
    try:
        # Use the correct method: discover_unified
        result = await discovery.discover_unified(
            niches=["smart_home"],
            max_per_niche=10
        )

        # discover_unified returns a list directly
        products = result if isinstance(result, list) else []

        print(f"   ✅ Discovery completed! Found {len(products)} products")
        print()

        if products:
            print("5. SAMPLE PRODUCTS:")
            for i, product in enumerate(products[:3], 1):
                print(f"   Product {i}:")
                print(f"      Name: {product.get('name', 'N/A')}")
                print(f"      Price: ${product.get('price', 0):.2f}")
                print(f"      Source: {product.get('source', 'unknown')}")
                print(f"      ID: {product.get('id', 'N/A')}")
                print()

            # Save to database
            print("6. SAVING TO DATABASE:")
            try:
                from ospra_os.database.product_history import ProductHistoryDB
                db = ProductHistoryDB()
                db.save_products(products)
                print(f"   ✅ Saved {len(products)} products to database")

                # Verify
                count = len(db.get_all_products())
                print(f"   ✅ Database now contains {count} products total")

            except Exception as e:
                print(f"   ❌ Failed to save to database: {e}")

        else:
            print("   ⚠️  No products found - this might be an Apify issue")
            print("   Check if Apify scrapers are working correctly")

    except Exception as e:
        print(f"   ❌ Discovery failed: {e}")
        import traceback
        traceback.print_exc()

# Run the async function
asyncio.run(test_discovery())

print()
print("=" * 80)
print("✅ TEST COMPLETE")
print("=" * 80)
