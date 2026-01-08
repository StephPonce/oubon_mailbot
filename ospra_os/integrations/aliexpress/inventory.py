"""
Inventory Sync Service - Monitor AliExpress stock and prices
"""
from typing import Dict, List
from .client import AliExpressClient


class InventorySyncService:
    """Service for syncing inventory and prices from AliExpress"""

    def __init__(self):
        self.client = AliExpressClient()

    async def sync_product(
        self,
        aliexpress_product_id: str,
        shopify_product_id: str
    ) -> Dict:
        """
        Sync single product inventory and price

        Returns updated stock and price info
        """
        try:
            print(f"[REFRESH] Syncing product {aliexpress_product_id}")

            # Check AliExpress availability
            availability = await self.client.check_product_availability(
                aliexpress_product_id
            )

            if not availability['available']:
                print("[WARNING]  Product no longer available on AliExpress")

                # TODO: Disable product in Shopify

                return {
                    'success': True,
                    'action': 'disabled',
                    'reason': 'out_of_stock'
                }

            # Check for price changes
            current_price = availability['price']

            # TODO: Compare with stored price
            # TODO: Update Shopify if price changed

            result = {
                'success': True,
                'action': 'synced',
                'stock': availability['stock_quantity'],
                'price': current_price,
                'available': True
            }

            print(f"[SUCCESS] Synced - Stock: {result['stock']}, Price: ${result['price']:.2f}")

            return result

        except Exception as e:
            print(f"[ERROR] Sync error: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    async def bulk_sync(
        self,
        products: List[Dict]
    ) -> List[Dict]:
        """Sync inventory for multiple products"""
        import asyncio

        print(f"\n[REFRESH] Syncing {len(products)} products...")

        results = []

        for product in products:
            result = await self.sync_product(
                product['aliexpress_id'],
                product['shopify_id']
            )
            results.append(result)

            await asyncio.sleep(1)  # Rate limit

        print(f"\n[SUCCESS] Synced {len(results)} products")

        return results

    async def monitor_price_changes(
        self,
        products: List[Dict],
        threshold_percent: float = 10.0
    ) -> List[Dict]:
        """
        Monitor for significant price changes

        Args:
            products: List of products to monitor
            threshold_percent: Alert if price changes by this %

        Returns:
            List of products with significant changes
        """
        print(f"\n[PRICE] Monitoring prices for {len(products)} products...")

        alerts = []

        for product in products:
            availability = await self.client.check_product_availability(
                product['aliexpress_id']
            )

            if not availability['available']:
                continue

            current_price = availability['price']
            old_price = product.get('last_known_price', current_price)

            # Calculate change
            if old_price > 0:
                change_percent = ((current_price - old_price) / old_price) * 100

                if abs(change_percent) >= threshold_percent:
                    alerts.append({
                        'product_id': product['aliexpress_id'],
                        'old_price': old_price,
                        'new_price': current_price,
                        'change_percent': change_percent
                    })

                    print(f"[WARNING]  Price change alert: {product.get('name', 'Unknown')}")
                    print(f"   ${old_price:.2f} → ${current_price:.2f} ({change_percent:+.1f}%)")

        print(f"\n[STATS] Found {len(alerts)} significant price changes")

        return alerts
