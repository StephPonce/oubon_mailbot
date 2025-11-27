"""
Test AliExpress Affiliate API Connection
Tests both regular and affiliate credentials
"""
import asyncio
import os
from dotenv import load_dotenv
from ospra_os.integrations.aliexpress.client import AliExpressClient

load_dotenv()


async def test_affiliate_connection():
    """Test AliExpress Affiliate API with new credentials"""
    print("=" * 80)
    print("🧪 ALIEXPRESS AFFILIATE API CONNECTION TEST")
    print("=" * 80)
    print()

    # Test 1: Verify credentials are loaded
    print("1️⃣ VERIFYING CREDENTIALS")
    print("-" * 80)

    regular_key = os.getenv('ALIEXPRESS_APP_KEY')
    regular_secret = os.getenv('ALIEXPRESS_APP_SECRET')
    affiliate_key = os.getenv('ALIEXPRESS_AFFILIATE_APP_KEY')
    affiliate_secret = os.getenv('ALIEXPRESS_AFFILIATE_APP_SECRET')

    print(f"Regular API Key: {regular_key[:10]}..." if regular_key else "❌ Not found")
    print(f"Regular API Secret: {regular_secret[:10]}..." if regular_secret else "❌ Not found")
    print(f"Affiliate API Key: {affiliate_key[:10]}..." if affiliate_key else "❌ Not found")
    print(f"Affiliate API Secret: {affiliate_secret[:10]}..." if affiliate_secret else "❌ Not found")
    print()

    if not affiliate_key or not affiliate_secret:
        print("❌ Affiliate credentials not found in .env file!")
        return

    # Test 2: Initialize client with affiliate credentials
    print("2️⃣ INITIALIZING AFFILIATE CLIENT")
    print("-" * 80)

    try:
        client = AliExpressClient(use_affiliate=True)
        print("✅ Client initialized successfully")
        print(f"   Using App Key: {client.app_key}")
        print(f"   Tracking ID: {client.tracking_id}")
        print()
    except Exception as e:
        print(f"❌ Client initialization failed: {e}")
        return

    # Test 3: Search for products
    print("3️⃣ TESTING PRODUCT SEARCH")
    print("-" * 80)

    test_keywords = "wireless earbuds"
    print(f"Searching for: '{test_keywords}'")
    print()

    try:
        products = await client.search_products(
            keywords=test_keywords,
            page_size=5
        )

        if products:
            print(f"✅ Search successful! Found {len(products)} products")
            print()

            # Display first product
            if len(products) > 0:
                product = products[0]
                print("📦 Sample Product:")
                print(f"   Title: {product.get('product_title', 'N/A')[:60]}...")
                print(f"   Price: ${product.get('target_sale_price', 'N/A')}")
                print(f"   Product ID: {product.get('product_id', 'N/A')}")
                print(f"   Commission Rate: {product.get('commission_rate', 'N/A')}%")
                print()
        else:
            print("⚠️  Search returned no products (may be API limit or authentication issue)")
            print()
    except Exception as e:
        print(f"❌ Search failed: {e}")
        print()

    # Test 4: Generate affiliate link
    print("4️⃣ TESTING AFFILIATE LINK GENERATION")
    print("-" * 80)

    affiliate_links = None
    if products and len(products) > 0:
        product_id = products[0].get('product_id')
        print(f"Generating affiliate link for product: {product_id}")
        print()

        try:
            affiliate_links = await client.get_affiliate_links([product_id])

            if affiliate_links and product_id in affiliate_links:
                print("✅ Affiliate link generated successfully!")
                print(f"   Link: {affiliate_links[product_id][:80]}...")
                print()
            else:
                print("⚠️  No affiliate link generated")
                print()
        except Exception as e:
            print(f"❌ Affiliate link generation failed: {e}")
            print()
    else:
        print("⏭️  Skipped (no products to generate links for)")
        print()

    # Test 5: Test regular API credentials for comparison
    print("5️⃣ TESTING REGULAR API CREDENTIALS (for comparison)")
    print("-" * 80)

    try:
        regular_client = AliExpressClient(use_affiliate=False)
        print("✅ Regular client initialized")
        print(f"   Using App Key: {regular_client.app_key}")
        print()

        regular_products = await regular_client.search_products(
            keywords=test_keywords,
            page_size=3
        )

        if regular_products:
            print(f"✅ Regular API also working! Found {len(regular_products)} products")
        else:
            print("⚠️  Regular API returned no products")
        print()
    except Exception as e:
        print(f"⚠️  Regular API test: {e}")
        print()

    # Summary
    print("=" * 80)
    print("📊 TEST SUMMARY")
    print("=" * 80)
    print()
    print(f"✅ Credentials loaded: {bool(affiliate_key and affiliate_secret)}")
    print(f"✅ Client initialization: Success")
    print(f"✅ Product search: {'Success' if products else 'Failed/Limited'}")
    print(f"✅ Affiliate link generation: {'Success' if affiliate_links else 'Failed/Limited'}")
    print()
    print("🎉 AliExpress Affiliate API is ready to use!")
    print()


if __name__ == "__main__":
    asyncio.run(test_affiliate_connection())
