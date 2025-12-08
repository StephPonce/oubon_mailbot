#!/usr/bin/env python3
"""
Test saturation scoring system.

This demonstrates OspraOS's anti-saturation intelligence that uses
Amazon Bestsellers data instead of needing to scrape Shopify stores.
"""

import asyncio
from ospra_os.intelligence.saturation_scorer import SaturationScorer


async def main():
    """Test saturation scoring for various products."""

    print("\n" + "="*70)
    print("🎯 OSPRA OS SATURATION SCORER - TEST")
    print("="*70)
    print("\nUsing Amazon Bestsellers data for saturation analysis")
    print("(No Shopify scraping needed - more reliable!)")
    print()

    scorer = SaturationScorer()

    # Test products (examples)
    test_products = [
        "wireless earbuds",           # Likely saturated
        "LED strip lights RGB",       # Moderate competition
        "smart door lock WiFi",       # Could be blue ocean
        "fidget spinner",             # Very saturated (old trend)
        "portable blender USB",       # Moderate
    ]

    print(f"Testing {len(test_products)} products...\n")

    for product_name in test_products:
        print("-" * 70)
        print(f"🔍 Product: {product_name}")
        print("-" * 70)

        try:
            result = await scorer.calculate_saturation_score(product_name)

            # Display results
            print(f"✅ Saturation Score: {result['saturation_score']}/100")
            print(f"📊 Opportunity Score: {result['opportunity_score']}/100")
            print(f"👥 Competitors: {result['competitor_count']} sellers")
            print(f"⚡ Review Velocity: {result['review_velocity']:.1f} reviews/day")
            print(f"🏆 Best Seller Rank: #{result['bsr']:,}")
            print(f"📈 BSR Trend: {result['bsr_trend']}")

            # Price range
            price_min = result['price_range']['min']
            price_max = result['price_range']['max']
            if price_min > 0 and price_max > 0:
                print(f"💰 Price Range: ${price_min:.2f} - ${price_max:.2f}")

            # Recommendation
            rec = result['recommendation']
            if rec == "deploy":
                emoji = "✅"
                color = "GREEN"
            elif rec == "caution":
                emoji = "⚠️"
                color = "YELLOW"
            else:  # skip
                emoji = "❌"
                color = "RED"

            print(f"\n{emoji} RECOMMENDATION: {rec.upper()} ({color})")
            print("\nReasons:")
            for reason in result['reasons']:
                print(f"  {reason}")

        except Exception as e:
            print(f"❌ Error: {e}")

        print()

    print("="*70)
    print("✅ TEST COMPLETE")
    print("="*70)
    print("\nNOTE: This uses Amazon data (more reliable than Shopify scraping)")
    print("      Saved $5-10/month by not needing Shopify Competitor scraper!")
    print()


if __name__ == "__main__":
    asyncio.run(main())
