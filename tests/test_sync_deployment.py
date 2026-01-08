#!/usr/bin/env python3
"""
Test the sync deployment endpoint

This endpoint checks if a deployed product still exists on Shopify
and updates the deployment status accordingly.
"""

import requests

API_BASE = "http://localhost:8001/api/dashboard/v2"

def test_sync_deployment():
    print("")
    print("[REFRESH] TESTING DEPLOYMENT SYNC")
    print("")
    print()

    # Step 1: Get a deployed product
    print("1⃣ Getting deployed products...")
    response = requests.get(f"{API_BASE}/deployments")

    if not response.ok:
        print(f"[ERROR] Failed to get deployments: {response.status_code}")
        return

    deployments = response.json().get("deployments", [])

    if not deployments:
        print("[WARNING]  No deployed products found")
        print()
        print("To test:")
        print("1. Deploy a product first: uv run python deploy_with_ai.py")
        print("2. Then run this test again")
        return

    # Get the first deployed product
    deployment = deployments[0]
    product_id = deployment['product_id']
    shopify_id = deployment['shopify_product_id']

    print(f"[SUCCESS] Found deployed product:")
    print(f"   Product ID: {product_id}")
    print(f"   Shopify ID: {shopify_id}")
    print(f"   Shopify URL: {deployment['shopify_url']}")
    print()

    # Step 2: Sync deployment status
    print("2⃣ Syncing deployment status with Shopify...")
    print(f"   (Checking if product {shopify_id} still exists)")
    print()

    sync_response = requests.post(f"{API_BASE}/products/{product_id}/sync-deployment")

    if not sync_response.ok:
        print(f"[ERROR] Sync failed: {sync_response.status_code}")
        print(sync_response.text)
        return

    result = sync_response.json()

    print("")
    print("[STATS] SYNC RESULTS")
    print("")
    print()

    if result.get("synced"):
        if result.get("deployed"):
            print("[SUCCESS] Product still exists on Shopify")
            print(f"   Shopify ID: {result['shopify_product_id']}")
            print(f"   Shopify URL: {result['shopify_url']}")
            print()
            print("Status: Deployment record is accurate")
        else:
            print("[WARNING]  Product no longer exists on Shopify")
            print(f"   Message: {result.get('message')}")
            print()
            print("Action: Deployment record has been marked as removed")
            print()
            print("The product can now be redeployed if needed")
    else:
        print(f"[WARNING]  Could not sync: {result.get('message')}")

    print()
    print("")

    # Step 3: Show how to use this in practice
    print()
    print("[TIP] PRACTICAL USE CASES:")
    print()
    print("1. Periodic Sync Job:")
    print("   Run this endpoint every hour to detect manual deletions")
    print()
    print("2. Before Price Updates:")
    print("   Sync before updating prices to avoid errors")
    print()
    print("3. Dashboard Status:")
    print("   Show accurate deployment status in the UI")
    print()
    print("4. Cleanup Script:")
    print("   Remove stale deployment records from database")

    print()
    print("")

if __name__ == "__main__":
    test_sync_deployment()
