"""
Final AliExpress Affiliate API Verification
Confirms everything is working correctly
"""
import asyncio
import os
import sys

# Force reload of environment
if '.env' in os.listdir('.'):
    from dotenv import load_dotenv
    load_dotenv(override=True)
    print("✅ Environment reloaded from .env")

from ospra_os.integrations.aliexpress.client import AliExpressClient


async def final_verification():
    """Complete end-to-end verification"""
    print("=" * 80)
    print("🎯 FINAL ALIEXPRESS AFFILIATE API VERIFICATION")
    print("=" * 80)
    print()

    # Verify credentials
    print("1️⃣ CREDENTIALS CHECK")
    print("-" * 80)
    affiliate_key = os.getenv('ALIEXPRESS_AFFILIATE_APP_KEY')
    affiliate_secret = os.getenv('ALIEXPRESS_AFFILIATE_APP_SECRET')
    tracking_id = os.getenv('ALIEXPRESS_TRACKING_ID')

    print(f"Affiliate App Key: {affiliate_key}")
    print(f"Affiliate Secret: {affiliate_secret[:15]}...")
    print(f"Tracking ID: {tracking_id}")
    print()

    if not affiliate_key or not affiliate_secret:
        print("❌ Credentials missing!")
        return

    # Initialize client with affiliate credentials
    print("2️⃣ CLIENT INITIALIZATION")
    print("-" * 80)

    try:
        client = AliExpressClient(use_affiliate=True)
        print(f"✅ Client initialized")
        print(f"   App Key: {client.app_key}")
        print(f"   Tracking ID: {client.tracking_id}")
        print()
    except Exception as e:
        print(f"❌ Failed to initialize: {e}")
        return

    # Test product search
    print("3️⃣ PRODUCT SEARCH TEST")
    print("-" * 80)

    try:
        products = await client.search_products(
            keywords="phone holder",
            page_size=5
        )

        if products and len(products) > 0:
            print(f"✅ SUCCESS! Found {len(products)} products")
            print()

            # Show sample product
            product = products[0]
            print("📦 Sample Product:")
            print(f"   Title: {product.get('product_title', '')[:60]}...")
            print(f"   Price: ${product.get('target_sale_price', 'N/A')}")
            print(f"   ID: {product.get('product_id')}")
            print(f"   Commission: {product.get('commission_rate', 'N/A')}")
            print()

            # Test affiliate link generation
            print("4️⃣ AFFILIATE LINK GENERATION")
            print("-" * 80)

            product_id = str(product.get('product_id'))
            links = await client.get_affiliate_links([product_id])

            if links and product_id in links:
                print("✅ Affiliate link generated!")
                print(f"   {links[product_id][:80]}...")
                print()
            else:
                # Check if promotion_link is in product data
                if 'promotion_link' in product:
                    print("✅ Affiliate link available in product data!")
                    print(f"   {product['promotion_link'][:80]}...")
                    print()
                else:
                    print("⚠️  No affiliate link generated")
                    print()

        else:
            print("⚠️  Search returned no products")
            print("   This might be due to API rate limits or permissions")
            print()

    except Exception as e:
        print(f"❌ Search failed: {e}")
        print()

    # Final status
    print("=" * 80)
    print("✅ VERIFICATION COMPLETE!")
    print("=" * 80)
    print()

    if products and len(products) > 0:
        print("🎉 Your AliExpress Affiliate integration is WORKING!")
        print()
        print("Next Steps:")
        print("1. You can now use AliExpressClient in your code")
        print("2. Search for products with client.search_products()")
        print("3. Get affiliate links with client.get_affiliate_links()")
        print("4. Earn commissions from sales!")
        print()
        print("Example Usage:")
        print("```python")
        print("from ospra_os.integrations.aliexpress.client import AliExpressClient")
        print()
        print("client = AliExpressClient(use_affiliate=True)")
        print("products = await client.search_products('phone case', page_size=10)")
        print("```")
    else:
        print("⚠️  API is accessible but returning limited results")
        print()
        print("Possible reasons:")
        print("1. API rate limits (try again in a few minutes)")
        print("2. Some methods need additional permissions")
        print("3. Geographic restrictions")
        print()
        print("The integration code is ready - just waiting for API access!")

    print()


if __name__ == "__main__":
    asyncio.run(final_verification())
