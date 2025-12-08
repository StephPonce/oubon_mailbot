"""
Mass Product Discovery v2 for Stratosphere Tier
================================================
Uses the MODERN UnifiedProductDiscoveryV2 engine directly (not the old API).

This leverages:
- Apify TikTok Shop (viral products)
- Apify Amazon Bestsellers (proven demand)
- AliExpress Affiliate API (dropship ready)
- Google Trends validation (proxy-based)

Author: OspraOS
Date: December 7, 2025
"""

import asyncio
from typing import List, Dict
import json
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ospra_os.intelligence.unified_product_discovery import get_discovery_engine


# Comprehensive niche list (40+ niches)
NICHES = [
    # Home & Living
    "smart_home", "home_decor", "lighting", "organization", "cleaning",

    # Kitchen & Dining
    "kitchen", "coffee_tea", "barware",

    # Health & Wellness
    "fitness", "wellness", "health",

    # Beauty & Personal Care
    "beauty", "skincare", "haircare", "grooming",

    # Tech & Electronics
    "tech", "phone_accessories", "audio", "computer", "gaming", "camera",

    # Outdoor & Travel
    "outdoor", "travel", "automotive", "cycling",

    # Pets
    "pet", "dog", "cat",

    # Family & Kids
    "baby", "kids", "parenting",

    # Office & Work
    "office", "desk_setup", "stationery",

    # Fashion & Accessories
    "fashion_accessories", "jewelry", "watches",

    # Hobbies & Crafts
    "crafts", "garden", "music",

    # Special Categories
    "gifts", "seasonal", "eco_friendly", "luxury",

    # Trending
    "tiktok_viral", "amazon_finds"
]


async def discover_niche(niche: str, max_products: int = 500) -> Dict:
    """
    Discover products for a single niche using UnifiedProductDiscoveryV2.

    Args:
        niche: Product niche
        max_products: Maximum products to discover per niche

    Returns:
        Discovery results with products list
    """
    print(f"\n🔍 Discovering {niche}...")

    try:
        engine = get_discovery_engine()

        products = await engine.discover_products(
            niche=niche,
            max_products=max_products,
            min_score=40.0  # Lower threshold for more results
        )

        products_found = len(products)
        print(f"   ✅ {niche}: {products_found} products discovered")

        return {
            "niche": niche,
            "products": products,
            "products_found": products_found,
            "success": True
        }

    except Exception as e:
        print(f"   ❌ {niche}: {str(e)[:100]}")
        return {
            "niche": niche,
            "products": [],
            "products_found": 0,
            "success": False,
            "error": str(e)
        }


async def mass_discover(max_per_niche: int = 500, batch_size: int = 3, niches: List[str] = None):
    """
    Discover products across ALL niches using modern discovery engine.

    Args:
        max_per_niche: Max products per niche
        batch_size: Number of concurrent niche discoveries
        niches: Optional list of specific niches (defaults to all)
    """
    target_niches = niches or NICHES

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("🚀 STRATOSPHERE TIER - MASS PRODUCT DISCOVERY V2")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"   Engine: UnifiedProductDiscoveryV2 (Apify + AliExpress)")
    print(f"   Niches: {len(target_niches)}")
    print(f"   Max per niche: {max_per_niche}")
    print(f"   Expected total: ~{len(target_niches) * max_per_niche:,} products")
    print()

    results = []
    all_products = []

    # Process niches in batches to avoid overwhelming the system
    for i in range(0, len(target_niches), batch_size):
        batch = target_niches[i:i+batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(target_niches) + batch_size - 1) // batch_size

        print(f"📦 Batch {batch_num}/{total_batches} ({', '.join(batch)})")

        # Run discoveries concurrently within batch
        tasks = [discover_niche(niche, max_per_niche) for niche in batch]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in batch_results:
            if isinstance(result, Exception):
                print(f"   ❌ Error: {result}")
            else:
                results.append(result)
                all_products.extend(result.get("products", []))

    # Print summary
    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("📊 DISCOVERY SUMMARY")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    successful = [r for r in results if r.get("success")]
    failed = [r for r in results if not r.get("success")]
    total_products = sum(r.get("products_found", 0) for r in results)

    print(f"Total Niches Processed: {len(results)}")
    print(f"✅ Successful:          {len(successful)}")
    print(f"❌ Failed:              {len(failed)}")
    print(f"📦 Total Products:      {total_products:,}")
    print()

    # Top niches by product count
    sorted_results = sorted(successful, key=lambda x: x.get("products_found", 0), reverse=True)
    print("🏆 Top 10 Niches:")
    for i, r in enumerate(sorted_results[:10], 1):
        print(f"   {i}. {r['niche']}: {r['products_found']:,} products")

    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # Save results
    output_file = "mass_discovery_results_v2.json"
    with open(output_file, "w") as f:
        json.dump({
            "total_products": total_products,
            "niches_processed": len(results),
            "successful": len(successful),
            "failed": len(failed),
            "results": [
                {
                    "niche": r["niche"],
                    "products_found": r["products_found"],
                    "success": r["success"],
                    "error": r.get("error")
                } for r in results
            ],
            "products": all_products[:1000]  # Save first 1000 products
        }, f, indent=2)

    print(f"📄 Results saved to: {output_file}")
    print()

    return {
        "total_products": total_products,
        "successful": len(successful),
        "failed": len(failed),
        "products": all_products
    }


if __name__ == "__main__":
    max_per_niche = int(sys.argv[1]) if len(sys.argv) > 1 else 500

    try:
        result = asyncio.run(mass_discover(max_per_niche=max_per_niche))

        if result["total_products"] > 0:
            print(f"\n✅ SUCCESS: Discovered {result['total_products']:,} products!")
            sys.exit(0)
        else:
            print(f"\n⚠️  WARNING: No products discovered. Check Apify credentials and API status.")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n❌ Discovery interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
