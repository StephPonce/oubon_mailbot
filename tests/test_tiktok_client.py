#!/usr/bin/env python3
"""
Test TikTok Client for Product Discovery

This script demonstrates how to use the TikTok client to discover
viral products from TikTok videos.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ospra_os.integrations.tiktok_client import TikTokClient


def test_tiktok_client():
    print("")
    print(" TESTING TIKTOK PRODUCT DISCOVERY")
    print("")
    print()

    # Initialize client
    client = TikTokClient()

    if not client.enabled:
        print("[WARNING]  TikTok credentials not configured")
        print()
        print("To enable TikTok integration:")
        print("1. Add TikTok credentials to .env file")
        print("2. Restart this script")
        print()
        print("However, fallback data is available for testing...")
        print()

    # Test 1: Get trending hashtags
    print("1⃣ TRENDING HASHTAGS")
    print("")
    hashtags = client.get_trending_hashtags(limit=10)
    print(f"Found {len(hashtags)} trending product hashtags:")
    for i, tag in enumerate(hashtags[:10], 1):
        print(f"  {i}. #{tag}")
    print()

    # Test 2: Generate OAuth URL
    print("2⃣ OAUTH AUTHORIZATION")
    print("")
    auth_url = client.get_authorization_url(state="test_state_123")
    if auth_url:
        print("To authorize TikTok access, visit:")
        print(f"  {auth_url}")
    else:
        print("[WARNING]  OAuth not configured (credentials missing)")
    print()

    # Test 3: Search for trending products
    print("3⃣ SEARCHING FOR TRENDING PRODUCTS")
    print("")

    # Search multiple categories
    keywords = ["smart home", "fitness gadget", "kitchen tool"]
    print(f"Searching for: {', '.join(keywords)}")
    print()

    products = client.search_trending_products(keywords=keywords, limit=10)

    print(f"[SUCCESS] Found {len(products)} viral products")
    print()

    # Display top 5 products
    print("")
    print("[PACKAGE] TOP 5 VIRAL PRODUCTS")
    print("")
    print()

    for i, product in enumerate(products[:5], 1):
        print(f"{i}. {product['name']}")
        print(f"   [PRICE] Price: ${product['price']:.2f}")
        print(f"   [TREND] Viral Score: {product['viral_score']}/100")
        print(f"   [FAST] Velocity: {product['velocity_score']}/100")
        print(f"   [STAR] Estimated Rating: {product['rating']}/5.0")
        print(f"   [MONEY] Profit: ${product['estimated_profit']:.2f} ({product['profit_margin']:.1f}% margin)")

        stats = product.get('statistics', {})
        print(f"   [STATS] Engagement: {stats.get('engagement_rate', 0):.2f}%")
        print(f"      • Views: {stats.get('views', 0):,}")
        print(f"      • Likes: {stats.get('likes', 0):,}")
        print(f"      • Comments: {stats.get('comments', 0):,}")
        print(f"      • Shares: {stats.get('shares', 0):,}")
        print(f"   [LINK] Source: {product.get('source_url', 'N/A')}")
        print()

    # Test 4: Show integration examples
    print("")
    print("[TIP] INTEGRATION EXAMPLES")
    print("")
    print()

    print("1. Add to Product Discovery:")
    print("   ```python")
    print("   from ospra_os.integrations.tiktok_client import TikTokClient")
    print("   ")
    print("   client = TikTokClient()")
    print("   products = client.search_trending_products(")
    print("       keywords=['smart home', 'fitness'],")
    print("       limit=50")
    print("   )")
    print("   ```")
    print()

    print("2. Save to Database:")
    print("   ```python")
    print("   from ospra_os.database.product_history import ProductHistoryDB")
    print("   ")
    print("   db = ProductHistoryDB()")
    print("   for product in products:")
    print("       db.add_product(product)")
    print("   ```")
    print()

    print("3. Deploy to Shopify:")
    print("   ```python")
    print("   from ospra_os.integrations.shopify_client import ShopifyClient")
    print("   ")
    print("   shopify = ShopifyClient()")
    print("   for product in products[:10]:")
    print("       shopify.create_product(product)")
    print("   ```")
    print()

    print("4. Schedule Daily Discovery:")
    print("   ```python")
    print("   import schedule")
    print("   ")
    print("   def discover_daily():")
    print("       client = TikTokClient()")
    print("       products = client.search_trending_products(limit=50)")
    print("       # Save to database...")
    print("   ")
    print("   schedule.every().day.at('09:00').do(discover_daily)")
    print("   ```")
    print()

    print("")
    print("[NEW] NEXT STEPS")
    print("")
    print()
    print("1. Get TikTok API access:")
    print("   • Visit: https://developers.tiktok.com")
    print("   • Create app")
    print("   • Add credentials to .env")
    print()
    print("2. Authorize app:")
    print("   • Visit OAuth URL above")
    print("   • Grant permissions")
    print("   • Save access token")
    print()
    print("3. Integrate with product discovery:")
    print("   • Add to ospra_os/intelligence/product_intelligence.py")
    print("   • Run daily discovery jobs")
    print("   • Auto-deploy top products")
    print()
    print("")


if __name__ == "__main__":
    test_tiktok_client()
