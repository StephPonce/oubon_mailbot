#!/usr/bin/env python3
"""Test Intelligence Engine directly without HTTP layer"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

async def test_intelligence():
    try:
        from ospra_os.intelligence.product_intelligence_v2 import ProductIntelligenceEngine

        print('⏳ Initializing engine...')
        engine = ProductIntelligenceEngine()

        print('⏳ Discovering 2 smart home products...')
        products = await engine.discover_winning_products(
            niches=['smart home'],
            max_per_niche=2
        )

        if not products:
            print('❌ No products returned!')
            return

        print(f'\n✅ Got {len(products)} products!')

        for i, p in enumerate(products, 1):
            d = p.get('display_data', {})
            print(f'\n{i}. {d.get("name", "Unknown")}')
            print(f'   Score: {p.get("score", 0):.1f}/10')
            print(f'   Cost: ${d.get("supplier_cost", 0):.2f}')
            print(f'   Price: ${d.get("market_price", 0):.2f}')
            print(f'   Profit: ${d.get("estimated_profit", 0):.2f}')

    except Exception as e:
        print(f'❌ ERROR: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(test_intelligence())
