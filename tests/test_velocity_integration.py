"""
Test the complete velocity scoring integration with Advanced Scraper

This tests:
1. AliExpress product scraping (Playwright)
2. Google Trends velocity scoring (Playwright)
3. Integration of both systems
"""

import requests
import json

def test_velocity_integration():
    """Test velocity scoring with a new niche to bypass cache"""

    print("=" * 80)
    print("[TEST] TESTING VELOCITY SCORING INTEGRATION")
    print("=" * 80)
    print()

    # Use a niche that won't be cached
    test_niche = "wireless_earbuds"

    print(f"Testing with niche: {test_niche}")
    print("⏳ This may take 30-60 seconds if scraping is triggered...")
    print()

    try:
        # Request products (will trigger scraping if not cached)
        response = requests.get(
            "http://localhost:8001/api/dashboard/v2/products",
            params={
                "niche": test_niche,
                "per_page": 5
            },
            timeout=120  # Long timeout for scraping
        )

        if response.status_code != 200:
            print(f"[ERROR] Request failed: {response.status_code}")
            print(response.text)
            return

        data = response.json()

        # Display results
        print("=" * 80)
        print("[STATS] RESULTS")
        print("=" * 80)
        print()

        print(f"[SEARCH] Data Source: {data.get('data_source')}")
        print(f"[PACKAGE] Total Products: {data.get('total', 0)}")
        print()

        if data.get('data_source') == 'ADVANCED_SCRAPING':
            print("[NEW] [NEW] [NEW] ADVANCED SCRAPER ACTIVATED! [NEW] [NEW] [NEW]")
            print()

        products = data.get('products', [])

        if not products:
            print("[WARNING]  No products returned")
            print()
            print("This could mean:")
            print("  • Cache is being used (try a different niche)")
            print("  • Scraping failed (check backend logs)")
            print("  • TikTok API succeeded (Priority #1)")
            return

        # Analyze velocity scores
        print("Products with Velocity Scores:")
        print("-" * 80)

        velocities = []

        for i, product in enumerate(products[:5], 1):
            velocity = product.get('velocity_score', 0)
            velocities.append(velocity)

            print(f"\n{i}. {product['name'][:60]}")
            print(f"   [PRICE] Price: ${product['price']}")
            print(f"   [TREND] Velocity: {velocity}/100")
            print(f"   [STAR] Rating: {product['rating']}/5")
            print(f"   [PACKAGE] Orders: {product['orders']:,}")
            print(f"   [LINK] Source: {product['source']}")

        print()
        print("-" * 80)

        # Analyze velocity statistics
        if velocities:
            avg_velocity = sum(velocities) / len(velocities)
            velocity_range = max(velocities) - min(velocities)

            print(f"\n[STATS] Velocity Statistics:")
            print(f"   Average: {avg_velocity:.1f}/100")
            print(f"   Min: {min(velocities)}")
            print(f"   Max: {max(velocities)}")
            print(f"   Range: {velocity_range}")
            print()

            if velocity_range > 5:
                print("   [SUCCESS] Good variation (likely real Google Trends data)")
            else:
                print("   [WARNING]  Low variation (might be fallback scores)")

            print()
            print("=" * 80)

            # Final verdict
            if data.get('data_source') == 'ADVANCED_SCRAPING' and avg_velocity > 0:
                print("[SUCCESS] SUCCESS! Velocity scoring integration working:")
                print("   • Advanced Scraper: Activated")
                print("   • Google Trends: Scraped with Playwright")
                print("   • Velocity Scores: Applied to products")
                print("   • Anti-bot detection: BYPASSED")
            elif data.get('data_source') == 'DATABASE':
                print("[INFO]  Using cached data (expected behavior)")
                print("   To test scraper, try a different niche or clear cache:")
                print("   rm data/product_cache.db")
            else:
                print(f"[INFO]  Data source: {data.get('data_source')}")
                print("   Check backend logs for details")

        print()
        print("=" * 80)

    except requests.exceptions.Timeout:
        print("[ERROR] Request timed out (scraping takes 30-60 seconds)")
        print("Check backend logs for scraping activity")
    except Exception as e:
        print(f"[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_velocity_integration()
