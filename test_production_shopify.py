#!/usr/bin/env python3
"""Test production (Render) Shopify connection."""

import requests

print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("TESTING PRODUCTION SHOPIFY (Render)")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print()

# Test the production API's Shopify integration endpoint
url = "https://oubon-mailbot.onrender.com"

print(f"Testing: {url}")
print()

# First check if service is up
print("1. Checking if service is online...")
try:
    resp = requests.get(f"{url}/", timeout=30)
    if resp.status_code == 200:
        print("   ✅ Service is online")
    else:
        print(f"   ⚠️  Service returned {resp.status_code}")
except Exception as e:
    print(f"   ❌ Service is offline: {e}")
    exit(1)

print()

# Check if we have a Shopify test endpoint
print("2. Looking for Shopify test endpoint...")
endpoints_to_try = [
    "/api/shopify/test",
    "/api/test-shopify",
    "/api/shopify/products",
    "/health"
]

for endpoint in endpoints_to_try:
    try:
        print(f"   Trying: {endpoint}")
        resp = requests.get(f"{url}{endpoint}", timeout=15)
        print(f"   Status: {resp.status_code}")
        if resp.status_code in [200, 404, 405]:
            print(f"   Response: {resp.text[:200]}")
    except Exception as e:
        print(f"   Error: {e}")
    print()

print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("RECOMMENDATION:")
print()
print("If you updated the Shopify token on Render:")
print("1. ✅ Token is active in production")
print("2. ❌ Local .env still has old token")
print()
print("To sync local with production:")
print("  - Copy the NEW token from Render Environment Variables")
print("  - Paste it here and I'll update your local .env")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
