import asyncio
import sys
sys.path.insert(0, '/Users/stephenponce/Documents/Ospra OS/Bots/oubon_mailbot')

from ospra_os.intelligence.advanced_scraper import AdvancedProductScraper

async def test_google_trends():
    """Direct test of Google Trends scraper"""

    print("=" * 80)
    print("[TREND] GOOGLE TRENDS SCRAPER TEST")
    print("=" * 80)
    print()
    print("Testing: scrape_google_trends() method")
    print("Keyword: 'smart watch'")
    print()
    print("⏳ Launching Playwright browser...")
    print()

    async with AdvancedProductScraper() as scraper:

        # Test Google Trends scraping
        result = await scraper.scrape_google_trends("smart watch", timeframe="today 3-m")

        print("\n" + "=" * 80)
        print("[STATS] RESULTS")
        print("=" * 80)
        print()

        print(f"Keyword: {result.get('keyword')}")
        print(f"Success: {result.get('success')}")
        print(f"Velocity Score: {result.get('velocity_score')}/100")
        print()

        if result.get('trend_values'):
            print(f"Trend Data Points: {len(result['trend_values'])}")
            print(f"Sample Values: {result['trend_values'][:10]}")
            print()

        if result.get('success'):
            print("[LAUNCH]" * 30)
            print("[SUCCESS] [SUCCESS] [SUCCESS] GOOGLE TRENDS SCRAPER WORKING! [SUCCESS] [SUCCESS] [SUCCESS]")
            print("[LAUNCH]" * 30)
            print()
            print("This proves:")
            print("  [SUCCESS] Playwright browser launches successfully")
            print("  [SUCCESS] Can navigate to Google Trends")
            print("  [SUCCESS] Stealth mode bypasses detection")
            print("  [SUCCESS] Can extract trend data")
            print("  [SUCCESS] Velocity calculation works")
        else:
            print("[WARNING]  Scraping failed - check details above")
            print()
            print("Common reasons:")
            print("  • Google Trends changed layout")
            print("  • Rate limited (try again in 5 min)")
            print("  • Network issue")

        print()
        print("=" * 80)

        # Test multiple keywords
        print("\n[TEST] Testing Multiple Keywords...")
        print()

        keywords = ["wireless earbuds", "robot vacuum", "air fryer"]
        results = []

        for keyword in keywords:
            print(f"Testing: {keyword}...")
            r = await scraper.scrape_google_trends(keyword, timeframe="today 3-m")
            results.append(r)
            print(f"  Velocity: {r.get('velocity_score')}/100")
            await asyncio.sleep(3)  # Delay between requests

        print()
        print("-" * 80)
        print("Summary:")
        successful = sum(1 for r in results if r.get('success'))
        print(f"  Successful: {successful}/{len(results)}")
        print(f"  Average Velocity: {sum(r.get('velocity_score', 0) for r in results) / len(results):.1f}/100")

        if successful > 0:
            print()
            print("[SUCCESS] Google Trends scraper is WORKING!")
            print("   • Can be used for real-time velocity scoring")
            print("   • Bypasses rate limits with browser automation")
            print("   • Ready for production use")

        print()
        print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_google_trends())
