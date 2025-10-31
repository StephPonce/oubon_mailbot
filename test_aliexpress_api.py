#!/usr/bin/env python3
"""Test official AliExpress API"""

import asyncio
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

async def test_api():
    from ospra_os.integrations.aliexpress_api_client import AliExpressAPIClient

    print('⏳ Testing AliExpress Official API...\n')

    client = AliExpressAPIClient()

    if not client.app_key or not client.app_secret:
        print('❌ API credentials not configured!')
        return

    print(f'✅ Credentials loaded:')
    print(f'   App Key: {client.app_key[:10]}...')
    print(f'   Secret: {client.app_secret[:10]}...\n')

    print('📡 Fetching products from API...')

    try:
        products = await client.search_products(query='smart home', limit=5)

        if products:
            print(f'\n✅ Got {len(products)} products!\n')
            for i, p in enumerate(products[:3], 1):
                print(f'{i}. {p.get("name", "Unknown")}')
                print(f'   Price: ${p.get("price", 0):.2f}')
                print(f'   Orders: {p.get("orders", 0):,}')
                print(f'   Rating: {p.get("rating", 0):.1f}/5.0')
                print(f'   URL: {p.get("url", "")}\n')
        else:
            print('\n❌ No products returned')
    except Exception as e:
        print(f'\n❌ Error: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(test_api())
