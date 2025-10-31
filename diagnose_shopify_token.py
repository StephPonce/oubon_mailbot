#!/usr/bin/env python3
"""Diagnose Shopify API token issues."""

import os
import requests

print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("SHOPIFY TOKEN DIAGNOSTIC")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print()

store = os.getenv('SHOPIFY_STORE')
token = os.getenv('SHOPIFY_API_TOKEN')

print(f"Store: {store}")
print(f"Token: {token[:15]}...{token[-10:]}")
print(f"Token Length: {len(token)} chars")
print(f"Token Format: {'✅ Valid (shpat_)' if token.startswith('shpat_') else '❌ Invalid format'}")
print()

# Test with multiple API versions
versions = ['2025-01', '2024-10', '2024-07', '2024-04']
headers = {'X-Shopify-Access-Token': token}

print("Testing multiple API versions:")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

any_success = False
for version in versions:
    url = f'https://{store}/admin/api/{version}/shop.json'
    try:
        resp = requests.get(url, headers=headers, timeout=5)

        if resp.status_code == 200:
            print(f"✅ {version}: SUCCESS")
            shop = resp.json()['shop']
            print(f"   Store: {shop.get('name')}")
            print(f"   Email: {shop.get('email')}")
            any_success = True
            break
        elif resp.status_code == 401:
            print(f"❌ {version}: 401 UNAUTHORIZED - Token is invalid or revoked")
        elif resp.status_code == 403:
            print(f"❌ {version}: 403 FORBIDDEN - Missing API scopes")
        elif resp.status_code == 404:
            print(f"❌ {version}: 404 NOT FOUND")
        else:
            print(f"⚠️  {version}: {resp.status_code}")
    except Exception as e:
        print(f"❌ {version}: {str(e)}")

print()
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

if not any_success:
    print("🚨 DIAGNOSIS: Token is NOT WORKING")
    print()
    print("The Admin API Access Token is either:")
    print("1. ❌ Revoked/Deleted")
    print("2. ❌ Never properly generated")
    print("3. ❌ Missing required API scopes")
    print("4. ❌ App is not installed")
    print()
    print("SOLUTION:")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()
    print("Go to Shopify Admin:")
    print("https://oubonshop.myshopify.com/admin/settings/apps/development")
    print()
    print("Then:")
    print("1. Click on your app (or create new one)")
    print("2. Configuration tab → Add ALL these scopes:")
    print("")
    print("   Product Management:")
    print("   ✅ read_products")
    print("   ✅ write_products")
    print("   ✅ read_inventory")
    print("   ✅ write_inventory")
    print("   ✅ read_product_listings")
    print("   ✅ write_product_listings")
    print("")
    print("   Order Management:")
    print("   ✅ read_orders")
    print("   ✅ write_orders")
    print("   ✅ read_fulfillments")
    print("")
    print("3. Click SAVE")
    print("4. API credentials tab → Install app (if not installed)")
    print("5. Reveal token once → COPY THE NEW TOKEN")
    print("6. Paste it here and I'll update .env")
    print()
    print("Current token that's NOT working:")
    print(f"   {token}")
else:
    print("✅ Token is working!")
    print()
    print("Everything is configured correctly.")
