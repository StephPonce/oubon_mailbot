#!/usr/bin/env python3
"""Test multiple Shopify API versions to find working one."""

import os
import requests

store = os.getenv('SHOPIFY_STORE')
token = os.getenv('SHOPIFY_API_TOKEN')

print(f'Store: {store}')
print(f'Token: {"*" * 20 if token else "NOT SET"}\n')

# Test multiple API versions
versions = ['2025-01', '2024-10', '2024-07', '2024-04', '2024-01', 'unstable']

for version in versions:
    url = f'https://{store}/admin/api/{version}/shop.json'
    headers = {'X-Shopify-Access-Token': token}

    try:
        response = requests.get(url, headers=headers, timeout=5)
        status = '✅' if response.status_code == 200 else '❌'
        print(f'{status} {version}: {response.status_code}')

        if response.status_code == 200:
            shop = response.json().get('shop', {})
            print(f'   SUCCESS! Store: {shop.get("name")}')
            break
        elif response.status_code == 401:
            print(f'   Token unauthorized - check API scopes')
        elif response.status_code == 404:
            print(f'   Version not found or endpoint wrong')
    except Exception as e:
        print(f'❌ {version}: {e}')
