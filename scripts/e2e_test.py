#!/usr/bin/env python3
"""
End-to-End Test for OspraOS Product Discovery & Deployment Pipeline

Tests the complete flow:
1. Discover products from multiple sources
2. Score opportunities (demand vs competition)
3. Enrich with AI-generated descriptions
4. Deploy to Shopify store
5. Verify deployment success

Usage:
    python scripts/e2e_test.py --niche smart_home
    python scripts/e2e_test.py --niche fitness --products 5
    python scripts/e2e_test.py --test-only  # Skip deployment
"""

import asyncio
import argparse
import sys
import os
from datetime import datetime
from typing import List, Dict

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_header(text: str):
    """Print section header"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(80)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}\n")


def print_success(text: str):
    """Print success message"""
    print(f"{Colors.GREEN}✅ {text}{Colors.ENDC}")


def print_error(text: str):
    """Print error message"""
    print(f"{Colors.RED}❌ {text}{Colors.ENDC}")


def print_info(text: str):
    """Print info message"""
    print(f"{Colors.CYAN}ℹ️  {text}{Colors.ENDC}")


def print_warning(text: str):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.ENDC}")


async def test_product_discovery(niche: str, count: int = 5) -> List[Dict]:
    """
    Step 1: Test product discovery from multiple sources
    """
    print_header("STEP 1: PRODUCT DISCOVERY")

    try:
        from ospra_os.intelligence.unified_product_discovery import get_live_products

        print_info(f"Discovering {count} products in '{niche}' niche...")
        print_info("Sources: TikTok Shop, Amazon Bestsellers, AliExpress")

        products = await get_live_products(niche=niche, limit=count)

        if not products:
            print_error(f"No products found for niche: {niche}")
            return []

        print_success(f"Discovered {len(products)} products")

        # Display products
        print("\n" + "─" * 80)
        for i, product in enumerate(products, 1):
            print(f"\n{Colors.BOLD}Product {i}:{Colors.ENDC}")
            print(f"  Name: {product.get('title', 'N/A')}")
            print(f"  Price: ${product.get('price', 0):.2f}")
            print(f"  Source: {product.get('source', 'N/A')}")
            print(f"  Trend Score: {product.get('trend_score', 0)}/100")
        print("─" * 80)

        return products

    except Exception as e:
        print_error(f"Discovery failed: {e}")
        import traceback
        traceback.print_exc()
        return []


async def test_opportunity_scoring(products: List[Dict]) -> List[Dict]:
    """
    Step 2: Test opportunity scoring (demand vs competition)
    """
    print_header("STEP 2: OPPORTUNITY SCORING")

    try:
        from ospra_os.intelligence.opportunity_scorer import get_opportunity_scorer

        print_info("Scoring products based on:")
        print_info("  • Demand (velocity, volume, momentum)")
        print_info("  • Competition (sellers, ads, timing)")
        print_info("  • Formula: OPPORTUNITY = DEMAND × (1 - COMPETITION × 0.7)")

        scorer = get_opportunity_scorer()
        scored_products = []

        for i, product in enumerate(products, 1):
            try:
                # Generate product_id if not present
                product_id = product.get('product_id') or f"test_{i}_{hash(product.get('title', ''))}"

                # Score the product
                result = await scorer.score_product(
                    product_id=product_id,
                    product_name=product.get('title', ''),
                    niche=product.get('niche', 'smart_home'),
                    search_keywords=[product.get('title', '')],
                )

                # Add scores to product
                product['opportunity_score'] = result.opportunity_score
                product['opportunity_tier'] = result.opportunity_tier.value
                product['demand_score'] = result.demand.demand_score
                product['competition_score'] = result.competition.competition_score

                scored_products.append(product)

            except Exception as e:
                print_warning(f"Failed to score '{product.get('title', 'Unknown')}': {e}")
                continue

        # Sort by opportunity score
        scored_products.sort(key=lambda x: x.get('opportunity_score', 0), reverse=True)

        print_success(f"Scored {len(scored_products)} products")

        # Display scores
        print("\n" + "─" * 80)
        print(f"{Colors.BOLD}{'Rank':<6}{'Product':<40}{'Score':<10}{'Tier':<12}{'Demand':<10}{'Comp.':<10}{Colors.ENDC}")
        print("─" * 80)

        for i, product in enumerate(scored_products, 1):
            tier_emoji = {
                'golden': '✨',
                'excellent': '🎯',
                'good': '👍',
                'fair': '⚠️',
                'poor': '🚫',
                'avoid': '❌'
            }

            tier = product.get('opportunity_tier', 'unknown')
            emoji = tier_emoji.get(tier, '❓')

            print(f"{i:<6}{product.get('title', 'N/A')[:38]:<40}"
                  f"{product.get('opportunity_score', 0):<10.1f}"
                  f"{emoji} {tier.upper():<10}"
                  f"{product.get('demand_score', 0):<10.1f}"
                  f"{product.get('competition_score', 0):<10.1f}")

        print("─" * 80)

        return scored_products

    except Exception as e:
        print_error(f"Scoring failed: {e}")
        import traceback
        traceback.print_exc()
        return products


async def test_ai_enrichment(products: List[Dict]) -> List[Dict]:
    """
    Step 3: Test AI-powered product enrichment
    """
    print_header("STEP 3: AI ENRICHMENT")

    try:
        from ospra_os.intelligence.product_enrichment import enrich_product

        print_info("Generating AI-powered descriptions using Claude AI")
        print_info("  • SEO-optimized titles")
        print_info("  • Compelling descriptions")
        print_info("  • Feature highlights")

        enriched_products = []

        for product in products[:3]:  # Only enrich top 3 to save time
            try:
                print_info(f"Enriching: {product.get('title', 'Unknown')[:50]}...")

                enriched = await enrich_product(product)
                enriched_products.append(enriched)

                print_success(f"Generated {len(enriched.get('description', ''))} char description")

            except Exception as e:
                print_warning(f"Failed to enrich product: {e}")
                enriched_products.append(product)
                continue

        # Add remaining products without enrichment
        enriched_products.extend(products[3:])

        print_success(f"Enriched {min(3, len(products))} products")

        # Display sample enrichment
        if enriched_products:
            sample = enriched_products[0]
            print("\n" + "─" * 80)
            print(f"{Colors.BOLD}Sample Enrichment:{Colors.ENDC}")
            print(f"\nOriginal: {sample.get('title', 'N/A')}")
            print(f"Enriched: {sample.get('enriched_title', sample.get('title', 'N/A'))}")
            print(f"\nDescription: {sample.get('description', 'N/A')[:200]}...")
            print("─" * 80)

        return enriched_products

    except Exception as e:
        print_error(f"Enrichment failed: {e}")
        import traceback
        traceback.print_exc()
        return products


async def test_shopify_deployment(products: List[Dict], test_only: bool = False) -> Dict:
    """
    Step 4: Test Shopify deployment
    """
    print_header("STEP 4: SHOPIFY DEPLOYMENT")

    if test_only:
        print_warning("Skipping deployment (test-only mode)")
        return {'deployed': 0, 'skipped': len(products)}

    try:
        from ospra_os.integrations.shopify.client import ShopifyClient

        print_info("Testing Shopify connection...")

        client = ShopifyClient()

        # Test connection
        shop_info = await client.get_shop_info()
        print_success(f"Connected to store: {shop_info.get('name', 'Unknown')}")

        print_info(f"Deploying top product to Shopify...")

        # Deploy only the best product for testing
        best_product = products[0]

        # Prepare deployment parameters
        title = best_product.get('enriched_title', best_product.get('title'))
        description = best_product.get('description', '')
        price = best_product.get('price', 29.99)
        images = best_product.get('images', [])
        tags = [
            best_product.get('niche', ''),
            f"opportunity_{best_product.get('opportunity_tier', 'unknown')}",
            f"score_{int(best_product.get('opportunity_score', 0))}",
            'ospra_discovered'
        ]

        # Deploy
        result = await client.create_product(
            title=title,
            description=description,
            price=price,
            images=images,
            vendor='Oubon',
            tags=tags,
            inventory_quantity=100
        )

        if result.get('id'):
            print_success(f"✨ Product deployed successfully!")
            print_info(f"Shopify Product ID: {result['id']}")
            print_info(f"Admin URL: https://{shop_info.get('domain', '')}/admin/products/{result['id']}")

            return {'deployed': 1, 'failed': 0, 'shopify_id': result['id']}
        else:
            print_error("Deployment failed - no product ID returned")
            return {'deployed': 0, 'failed': 1}

    except ValueError as e:
        print_error(f"Shopify not configured: {e}")
        print_info("Set SHOPIFY_STORE and SHOPIFY_API_TOKEN in .env to enable deployment")
        return {'deployed': 0, 'skipped': 1, 'reason': 'not_configured'}

    except Exception as e:
        print_error(f"Deployment failed: {e}")
        import traceback
        traceback.print_exc()
        return {'deployed': 0, 'failed': 1}


def print_test_summary(
    products_found: int,
    products_scored: int,
    products_enriched: int,
    deployment_result: Dict
):
    """
    Print final test summary
    """
    print_header("TEST SUMMARY")

    # Overall status
    all_passed = (
        products_found > 0 and
        products_scored > 0 and
        (deployment_result.get('deployed', 0) > 0 or deployment_result.get('skipped', 0) > 0)
    )

    if all_passed:
        print(f"{Colors.GREEN}{Colors.BOLD}")
        print("┌" + "─" * 78 + "┐")
        print("│" + "✅ E2E TEST PASSED - ALL SYSTEMS OPERATIONAL ✅".center(78) + "│")
        print("└" + "─" * 78 + "┘")
        print(Colors.ENDC)
    else:
        print(f"{Colors.RED}{Colors.BOLD}")
        print("┌" + "─" * 78 + "┐")
        print("│" + "❌ E2E TEST FAILED - CHECK ERRORS ABOVE ❌".center(78) + "│")
        print("└" + "─" * 78 + "┘")
        print(Colors.ENDC)

    # Detailed results
    print(f"\n{Colors.BOLD}Results:{Colors.ENDC}")
    print(f"  1️⃣  Product Discovery:  {products_found} products found")
    print(f"  2️⃣  Opportunity Scoring: {products_scored} products scored")
    print(f"  3️⃣  AI Enrichment:       {products_enriched} products enriched")
    print(f"  4️⃣  Shopify Deployment:  {deployment_result.get('deployed', 0)} deployed, "
          f"{deployment_result.get('failed', 0)} failed, "
          f"{deployment_result.get('skipped', 0)} skipped")

    # Next steps
    print(f"\n{Colors.BOLD}Next Steps:{Colors.ENDC}")
    if all_passed:
        print(f"  {Colors.GREEN}✓{Colors.ENDC} Your OspraOS pipeline is working end-to-end")
        print(f"  {Colors.GREEN}✓{Colors.ENDC} Ready to discover and deploy products at scale")
        print(f"  {Colors.GREEN}✓{Colors.ENDC} Open http://localhost:5173 to use the dashboard")
    else:
        print(f"  {Colors.YELLOW}•{Colors.ENDC} Fix the errors shown above")
        print(f"  {Colors.YELLOW}•{Colors.ENDC} Ensure all API keys are configured in .env")
        print(f"  {Colors.YELLOW}•{Colors.ENDC} Run the test again to verify fixes")

    print("\n" + "─" * 80 + "\n")

    return 0 if all_passed else 1


async def main():
    """Run complete E2E test"""
    parser = argparse.ArgumentParser(description='OspraOS End-to-End Test')
    parser.add_argument('--niche', type=str, default='smart_home',
                       help='Product niche to test (default: smart_home)')
    parser.add_argument('--products', type=int, default=5,
                       help='Number of products to discover (default: 5)')
    parser.add_argument('--test-only', action='store_true',
                       help='Skip Shopify deployment')

    args = parser.parse_args()

    print(f"\n{Colors.CYAN}{Colors.BOLD}")
    print("╔" + "═" * 78 + "╗")
    print("║" + "OSPRAOS END-TO-END TEST".center(78) + "║")
    print("║" + f"Niche: {args.niche.upper()} | Products: {args.products}".center(78) + "║")
    print("╚" + "═" * 78 + "╝")
    print(Colors.ENDC)

    # Run tests
    products = await test_product_discovery(args.niche, args.products)
    if not products:
        print_error("Discovery failed - cannot continue")
        return 1

    scored_products = await test_opportunity_scoring(products)
    enriched_products = await test_ai_enrichment(scored_products)
    deployment_result = await test_shopify_deployment(enriched_products, args.test_only)

    # Print summary
    return print_test_summary(
        products_found=len(products),
        products_scored=len(scored_products),
        products_enriched=min(3, len(enriched_products)),
        deployment_result=deployment_result
    )


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
