#!/usr/bin/env python3
"""Test different Shopify endpoints to diagnose token/permission issues."""

import os
import requests

store = os.getenv('SHOPIFY_STORE')
token = os.getenv('SHOPIFY_API_TOKEN')

print(f'Store: {store}')
print(f'Token: {token[:10] if token else "NOT SET"}...{token[-10:] if token else ""}\n')

version = '2024-10'  # Use stable version

# Test different endpoints with different permission requirements
endpoints = [
    ('/shop.json', 'read_shop_data'),
    ('/products.json?limit=1', 'read_products'),
    ('/products/count.json', 'read_products'),
    ('/themes.json', 'read_themes'),
    ('/orders.json?limit=1', 'read_orders'),
]

for endpoint, required_scope in endpoints:
    url = f'https://{store}/admin/api/{version}{endpoint}'
    headers = {'X-Shopify-Access-Token': token}

    try:
        response = requests.get(url, headers=headers, timeout=5)

        if response.status_code == 200:
            print(f'✅ {endpoint}')
            print(f'   SUCCESS! Has {required_scope} permission')
            data = response.json()
            print(f'   Data keys: {list(data.keys())}')
        elif response.status_code == 401:
            print(f'❌ {endpoint}: 401 UNAUTHORIZED')
            print(f'   Token is invalid or missing {required_scope}')
        elif response.status_code == 403:
            print(f'❌ {endpoint}: 403 FORBIDDEN')
            print(f'   Token lacks {required_scope} permission')
        elif response.status_code == 404:
            print(f'❌ {endpoint}: 404 NOT FOUND')
            print(f'   Endpoint doesn\'t exist or token completely invalid')
        else:
            print(f'⚠️  {endpoint}: {response.status_code}')
            print(f'   {response.text[:100]}')

    except Exception as e:
        print(f'❌ {endpoint}: {e}')

    print()
