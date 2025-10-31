#!/usr/bin/env python3
"""Test Shopify API connection with updated API version."""

import os
import requests

# Get credentials
store = os.getenv('SHOPIFY_STORE')
token = os.getenv('SHOPIFY_API_TOKEN')

print(f'Store: {store}')
print(f'Token: {"*" * 20 if token else "NOT SET"}')

# Test connection with NEW API version
url = f'https://{store}/admin/api/2025-01/shop.json'
headers = {'X-Shopify-Access-Token': token}

print(f'\n🧪 Testing: {url}')

try:
    response = requests.get(url, headers=headers, timeout=10)
    print(f'Status: {response.status_code}')

    if response.status_code == 200:
        shop = response.json().get('shop', {})
        print(f'✅ Connected to: {shop.get("name")}')
        print(f'   Domain: {shop.get("domain")}')
        print(f'   Email: {shop.get("email")}')
    else:
        print(f'❌ Error: {response.text[:200]}')
except Exception as e:
    print(f'❌ Exception: {e}')
