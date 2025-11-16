#!/usr/bin/env python3
"""
Live test of AI description generation during Shopify deployment
"""

import requests
import json
import time

API_BASE = "http://localhost:8001/api/dashboard/v2"

def test_live_deployment():
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("🧪 LIVE AI DESCRIPTION TEST")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()

    # Step 1: Get a product from database
    print("1️⃣ Fetching product from database...")
    response = requests.get(f"{API_BASE}/products", params={
        "niche": "smart_home",
        "per_page": 1
    })

    if not response.ok:
        print(f"❌ Failed to fetch products: {response.status_code}")
        return

    products = response.json()["products"]
    if not products:
        print("❌ No products found")
        return

    product = products[0]
    print(f"✅ Found product: {product['name']}")
    print(f"   ID: {product['id']}")
    print(f"   Price: ${product['price']}")
    print(f"   Velocity: {product['velocity_score']}/100")
    print()

    # Step 2: Test AI description generation directly
    print("2️⃣ Generating AI description with Claude Sonnet 4...")
    print("   (This will take 2-3 seconds)")
    print()

    start_time = time.time()

    try:
        from ospra_os.intelligence.product_description_generator import ProductDescriptionGenerator
        from ospra_os.integrations.shopify_client import ShopifyClient

        # Test AI generator directly
        generator = ProductDescriptionGenerator()
        ai_content = generator.generate_shopify_description(product)

        elapsed = time.time() - start_time

        print(f"✅ AI description generated in {elapsed:.2f} seconds!")
        print()
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("📝 AI-GENERATED CONTENT")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print()

        print("🏷️  TITLE (SEO-Optimized):")
        print(f"   {ai_content['title']}")
        print()

        print("📄 DESCRIPTION (HTML):")
        print(ai_content['description'])
        print()

        print("✨ KEY FEATURES:")
        for i, bullet in enumerate(ai_content['bullet_points'], 1):
            print(f"   {i}. {bullet}")
        print()

        print("🔑 SEO KEYWORDS:")
        print(f"   {', '.join(ai_content['seo_keywords'])}")
        print()

        # Step 3: Test Shopify client integration
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("3️⃣ Testing Shopify Client Integration...")
        print()

        client = ShopifyClient()

        if not client.enabled:
            print("⚠️  Shopify not configured (credentials missing)")
            print("   But AI generation is working!")
        else:
            print(f"✅ Shopify client connected to: {client.store_url}")
            print(f"✅ AI generator integrated: {client.description_generator is not None}")
            print()

            if client.description_generator:
                print("🎉 READY TO DEPLOY!")
                print()
                print("When you deploy a product via the dashboard:")
                print("  1. AI generates description (2-3 seconds)")
                print("  2. Product created on Shopify with AI content")
                print("  3. Notification sent to dashboard bell")
                print("  4. User clicks 'View on Shopify'")

        print()
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("✅ TEST COMPLETE - AI DESCRIPTIONS WORKING!")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_live_deployment()
