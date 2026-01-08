"""
Test Apify scrapers directly
"""
from ospra_os.product_research.connectors.apify import TikTokShopScraper, AmazonBestsellersScraper

print("="*70)
print("[TEST] TESTING APIFY SCRAPERS")
print("="*70)
print()

# Test TikTok Shop Scraper
print("1⃣  Testing TikTok Shop Scraper...")
tiktok = TikTokShopScraper()
print(f"   Initialized: [SUCCESS]")
print(f"   Available: {'[SUCCESS] Yes' if tiktok.is_available() else '[ERROR] No (APIFY_API_TOKEN not set)'}")
print(f"   Actor ID: {tiktok.TIKTOK_SHOP_ACTOR}")
print()

# Test Amazon Bestsellers Scraper
print("2⃣  Testing Amazon Bestsellers Scraper...")
amazon_bs = AmazonBestsellersScraper()
print(f"   Initialized: [SUCCESS]")
print(f"   Available: {'[SUCCESS] Yes' if amazon_bs.is_available() else '[ERROR] No (APIFY_API_TOKEN not set)'}")
print(f"   Actor ID: {amazon_bs.ACTOR_ID}")
print()

print("="*70)
print("[SUCCESS] APIFY SCRAPERS TEST COMPLETE")
print("="*70)
print()
print("Summary:")
print("  [SUCCESS] TikTok Shop Scraper: Imported and initialized")
print("  [SUCCESS] Amazon Bestsellers Scraper: Imported and initialized")
print()
print("Next Steps:")
print("  1. Add APIFY_API_TOKEN to .env to enable scrapers")
print("  2. Update actor IDs with real actors from Apify Store")
print("  3. Run product discovery to test full integration")
print()
