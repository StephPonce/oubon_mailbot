#!/usr/bin/env python3
"""Test multi-niche product discovery."""

import asyncio
from ospra_os.core.settings import get_settings
from ospra_os.product_research.niche_discovery import MultiNicheDiscovery


async def test_multi_niche_discovery():
    """Test discovering products across all niches."""
    print("\n" + "="*70)
    print("TESTING MULTI-NICHE PRODUCT DISCOVERY")
    print("="*70)

    settings = get_settings()

    # Initialize discovery
    discovery = MultiNicheDiscovery(
        reddit_client_id=settings.REDDIT_CLIENT_ID,
        reddit_secret=settings.REDDIT_SECRET,
        aliexpress_api_key=settings.ALIEXPRESS_API_KEY,
        aliexpress_app_secret=settings.ALIEXPRESS_APP_SECRET,
    )

    print(f"\n📋 Configured Niches: {len(MultiNicheDiscovery.NICHES)}")
    for niche_key, niche_data in MultiNicheDiscovery.NICHES.items():
        print(f"   • {niche_key}: {len(niche_data['subreddits'])} subreddits")

    print("\n🚀 Starting parallel discovery...")
    print("   This will search 10+ niches simultaneously!\n")

    # Run discovery
    niche_products = await discovery.discover_all_niches(
        min_score=7.0,
        max_per_niche=3  # Limit to 3 per niche for testing
    )

    # Get top products
    top_products = discovery.get_top_products_overall(
        niche_products=niche_products,
        limit=10
    )

    # Get stats
    stats = discovery.get_stats(niche_products)

    # Display results
    print("\n" + "="*70)
    print("RESULTS SUMMARY")
    print("="*70)
    print(f"Total Products: {stats['total_products']}")
    print(f"Niches with Products: {stats['niches_with_products']}/{stats['niches_searched']}")
    print(f"High Priority: {stats['high_priority']}")
    print(f"Medium Priority: {stats['medium_priority']}")
    print(f"Low Priority: {stats['low_priority']}")

    if top_products:
        print("\n" + "="*70)
        print("TOP 10 PRODUCTS OVERALL")
        print("="*70)
        for i, product in enumerate(top_products[:10], 1):
            p = product.get('product', product)
            score = product.get('score', 0)
            priority = product.get('priority', 'LOW')
            name = p.get('name', 'Unknown')
            niche = p.get('niche', 'N/A')

            print(f"\n{i}. {name}")
            print(f"   Score: {score}/10 | Priority: {priority} | Niche: {niche}")

    # Show by niche
    print("\n" + "="*70)
    print("PRODUCTS BY NICHE")
    print("="*70)
    for niche_key, products in niche_products.items():
        if len(products) > 0:
            print(f"\n{niche_key.upper()}: {len(products)} products")
            for product in products[:2]:  # Show first 2
                p = product.get('product', product)
                score = product.get('score', 0)
                name = p.get('name', 'Unknown')
                print(f"   • {name} ({score}/10)")

    print("\n" + "="*70)
    print("✅ MULTI-NICHE DISCOVERY TEST COMPLETE!")
    print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(test_multi_niche_discovery())
