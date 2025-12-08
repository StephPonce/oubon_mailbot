"""
Mass Product Discovery for Stratosphere Tier
==============================================
Discovers THOUSANDS of products from ALL data sources for unlimited tier access.

Author: OspraOS
Date: December 7, 2025
"""

import asyncio
import httpx
from typing import List
import json


API_BASE = "http://localhost:8001"

# Comprehensive niche list
NICHES = [
    "smart_home",
    "fitness",
    "kitchen",
    "beauty",
    "pet",
    "home_office",
    "tech_accessories",
    "outdoor",
    "baby",
    "automotive",
    "gaming",
    "health",
    "jewelry",
    "toys",
    "sports",
    "garden",
    "travel",
    "fashion",
    "electronics",
    "home_decor"
]


async def discover_niche(client: httpx.AsyncClient, niche: str, max_products: int = 500) -> dict:
    """
    Discover products for a single niche.

    Args:
        client: HTTP client
        niche: Product niche
        max_products: Maximum products to discover per niche

    Returns:
        Discovery results
    """
    print(f"\n🔍 Discovering {niche}...")

    try:
        response = await client.post(
            f"{API_BASE}/research/find-products",
            json={
                "query": niche,
                "max_results": max_products,
                "sources": [
                    "aliexpress",
                    "google_trends",
                    "meta_ads",
                    "tiktok",
                    "reddit"
                ],
                "min_score": 50  # Lower threshold for more results
            },
            timeout=300.0  # 5 minute timeout per niche
        )

        response.raise_for_status()
        data = response.json()

        products_found = len(data.get("products", []))
        print(f"   ✅ {niche}: {products_found} products discovered")

        return {
            "niche": niche,
            "products_found": products_found,
            "success": True
        }

    except Exception as e:
        print(f"   ❌ {niche}: {str(e)[:100]}")
        return {
            "niche": niche,
            "products_found": 0,
            "success": False,
            "error": str(e)
        }


async def mass_discover(max_per_niche: int = 500, batch_size: int = 3):
    """
    Discover products across ALL niches.

    Args:
        max_per_niche: Max products per niche
        batch_size: Number of concurrent niche discoveries
    """
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("🚀 STRATOSPHERE TIER - MASS PRODUCT DISCOVERY")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"   Niches: {len(NICHES)}")
    print(f"   Max per niche: {max_per_niche}")
    print(f"   Expected total: ~{len(NICHES) * max_per_niche:,} products")
    print()

    results = []

    async with httpx.AsyncClient(timeout=300.0) as client:
        # Process niches in batches to avoid overwhelming the system
        for i in range(0, len(NICHES), batch_size):
            batch = NICHES[i:i+batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(NICHES) + batch_size - 1) // batch_size

            print(f"📦 Batch {batch_num}/{total_batches} ({', '.join(batch)})")

            # Run discoveries concurrently within batch
            tasks = [discover_niche(client, niche, max_per_niche) for niche in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in batch_results:
                if isinstance(result, Exception):
                    print(f"   ❌ Error: {result}")
                else:
                    results.append(result)

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
    with open("mass_discovery_results.json", "w") as f:
        json.dump({
            "total_products": total_products,
            "niches_processed": len(results),
            "successful": len(successful),
            "failed": len(failed),
            "results": results
        }, f, indent=2)

    print(f"📄 Results saved to: mass_discovery_results.json")
    print()


if __name__ == "__main__":
    import sys

    max_per_niche = int(sys.argv[1]) if len(sys.argv) > 1 else 500

    try:
        asyncio.run(mass_discover(max_per_niche=max_per_niche))
    except KeyboardInterrupt:
        print("\n\n❌ Discovery interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
