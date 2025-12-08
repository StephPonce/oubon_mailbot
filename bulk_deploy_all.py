"""
Bulk Deploy All Discovered Products to Shopify
================================================
This script deploys ALL products from the product_history database to Shopify
to test the Stratosphere tier's unlimited deployment capabilities.

Author: OspraOS
Date: December 7, 2025
"""

import httpx
import asyncio
import sqlite3
import json
from datetime import datetime
from typing import List, Dict
import sys


# Backend API base URL
API_BASE = "http://localhost:8001"


async def fetch_all_products() -> List[Dict]:
    """Fetch all products from the product_history database."""
    print("📊 Fetching products from database...")

    db_path = "data/product_history.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id, name, niche, price, cost, image_url,
            aliexpress_url, description, features
        FROM products
        ORDER BY velocity_score DESC
    """)

    products = []
    for row in cursor.fetchall():
        product = {
            "id": row[0],
            "name": row[1],
            "niche": row[2] or "general",
            "price": row[3] or 0,
            "cost": row[4] or 0,
            "image_url": row[5],
            "supplier_url": row[6],
            "description": row[7],
            "features": json.loads(row[8]) if row[8] else []
        }
        products.append(product)

    conn.close()

    print(f"✅ Found {len(products)} products")
    return products


async def deploy_all_products(products: List[Dict], batch_size: int = 5) -> Dict:
    """
    Deploy all products to Shopify in batches.

    Args:
        products: List of products to deploy
        batch_size: Number of products to deploy concurrently (default 5)

    Returns:
        Dict with deployment statistics
    """
    print(f"\n🚀 Starting bulk deployment of {len(products)} products...")
    print(f"   Batch size: {batch_size} concurrent deployments")
    print(f"   Estimated time: {len(products) * 30 / batch_size / 60:.1f} minutes\n")

    stats = {
        "total": len(products),
        "successful": 0,
        "failed": 0,
        "total_cost": 0.0,
        "total_time": 0.0,
        "results": []
    }

    start_time = datetime.now()

    async with httpx.AsyncClient(timeout=120.0) as client:
        # Deploy in batches
        for i in range(0, len(products), batch_size):
            batch = products[i:i+batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(products) + batch_size - 1) // batch_size

            print(f"📦 Batch {batch_num}/{total_batches} ({len(batch)} products):")

            # Create deployment tasks for this batch
            tasks = []
            for product in batch:
                task = deploy_single_product(client, product)
                tasks.append(task)

            # Execute batch concurrently
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for idx, result in enumerate(batch_results):
                product = batch[idx]

                if isinstance(result, Exception):
                    print(f"   ❌ {product['name'][:40]}: {str(result)[:50]}")
                    stats["failed"] += 1
                    stats["results"].append({
                        "product_id": product["id"],
                        "name": product["name"],
                        "success": False,
                        "error": str(result)
                    })
                elif result.get("success"):
                    print(f"   ✅ {product['name'][:40]}: ${result.get('price', 0):.2f} | AI Cost: ${result.get('total_cost', 0):.3f}")
                    stats["successful"] += 1
                    stats["total_cost"] += result.get("total_cost", 0)
                    stats["total_time"] += result.get("processing_time_seconds", 0)
                    stats["results"].append({
                        "product_id": product["id"],
                        "name": product["name"],
                        "success": True,
                        "shopify_url": result.get("shopify_url"),
                        "admin_url": result.get("admin_url"),
                        "price": result.get("price"),
                        "ai_cost": result.get("total_cost"),
                        "processing_time": result.get("processing_time_seconds")
                    })
                else:
                    print(f"   ❌ {product['name'][:40]}: {result.get('error', 'Unknown error')[:50]}")
                    stats["failed"] += 1
                    stats["results"].append({
                        "product_id": product["id"],
                        "name": product["name"],
                        "success": False,
                        "error": result.get("error", "Unknown error")
                    })

            print()  # Blank line between batches

    end_time = datetime.now()
    elapsed = (end_time - start_time).total_seconds()

    stats["elapsed_seconds"] = elapsed

    return stats


async def deploy_single_product(client: httpx.AsyncClient, product: Dict) -> Dict:
    """Deploy a single product to Shopify."""

    # Build deployment request
    request = {
        "product_id": product["id"],
        "name": product["name"],
        "niche": product["niche"],
        "supplier_cost": product["cost"],
        "supplier_url": product["supplier_url"],
        "images": [product["image_url"]] if product["image_url"] else [],
        "description": product["description"],
        "features": product["features"],

        # AI Flags (all enabled for full experience)
        "ai_content": True,
        "ai_images": True,
        "ai_pricing": True,
        "ai_seo": True,
        "publish": False,  # Keep as draft for now

        # Deployment options
        "target_margin": 0.4,  # 40% profit margin
        "add_branding": True,
        "max_images": 5
    }

    # Call deployment endpoint
    response = await client.post(
        f"{API_BASE}/api/shopify/deploy",
        json=request
    )

    response.raise_for_status()
    return response.json()


async def main():
    """Main execution flow."""
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("🚀 STRATOSPHERE TIER STRESS TEST - BULK DEPLOYMENT")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()

    # Step 1: Fetch products
    products = await fetch_all_products()

    if not products:
        print("❌ No products found in database. Run discovery first.")
        return

    # Step 2: Confirm deployment
    print(f"\n⚠️  You are about to deploy {len(products)} products to Shopify:")
    print(f"   • Estimated AI cost: ${len(products) * 0.04:.2f} - ${len(products) * 0.06:.2f}")
    print(f"   • Estimated time: ~{len(products) * 6:.0f} minutes")
    print()

    confirm = input("Continue? (yes/no): ")
    if confirm.lower() != "yes":
        print("❌ Deployment cancelled.")
        return

    # Step 3: Deploy all products
    stats = await deploy_all_products(products, batch_size=5)

    # Step 4: Print summary
    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("📊 DEPLOYMENT SUMMARY")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"Total Products:     {stats['total']}")
    print(f"✅ Successful:      {stats['successful']}")
    print(f"❌ Failed:          {stats['failed']}")
    print(f"Success Rate:       {stats['successful'] / stats['total'] * 100:.1f}%")
    print()
    print(f"💰 Total AI Cost:   ${stats['total_cost']:.2f}")
    print(f"⏱️  Total Time:      {stats['elapsed_seconds']:.1f}s ({stats['elapsed_seconds'] / 60:.1f} min)")
    print(f"⚡ Avg Time/Product: {stats['total_time'] / max(stats['successful'], 1):.1f}s")
    print()

    # Save detailed results to file
    result_file = f"deployment_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(result_file, 'w') as f:
        json.dump(stats, f, indent=2)

    print(f"📄 Detailed results saved to: {result_file}")
    print()

    if stats['successful'] > 0:
        print("🎉 SUCCESS! All products deployed to Shopify.")
        print(f"   View them at: https://rxxj7d-1i.myshopify.com/admin/products")

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n❌ Deployment interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
