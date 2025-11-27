"""
Order Fulfillment Service - Automate AliExpress order placement
"""
from typing import Dict, List
from .client import AliExpressClient, AliExpressDropshipping


class OrderFulfillmentService:
    """Service for fulfilling Shopify orders via AliExpress"""

    def __init__(self):
        self.client = AliExpressClient()
        self.dropship = AliExpressDropshipping(self.client)

    async def fulfill_order(
        self,
        shopify_order: Dict,
        aliexpress_product_id: str
    ) -> Dict:
        """
        Fulfill a Shopify order by placing AliExpress order

        Args:
            shopify_order: Shopify order data
            aliexpress_product_id: AliExpress product ID for fulfillment

        Returns:
            Fulfillment result with tracking
        """
        try:
            print(f"\n{'='*70}")
            print(f"📦 FULFILLING ORDER")
            print(f"{'='*70}")
            print(f"Shopify Order: {shopify_order.get('id')}")
            print(f"AliExpress Product: {aliexpress_product_id}")
            print()

            # Extract shipping address
            shipping_address = self._extract_shipping_address(shopify_order)

            # Get quantity
            quantity = self._get_order_quantity(shopify_order)

            # Check product availability
            availability = await self.client.check_product_availability(
                aliexpress_product_id
            )

            if not availability['available']:
                print("❌ Product not available on AliExpress")
                return {
                    'success': False,
                    'error': 'Product out of stock'
                }

            # Place order on AliExpress
            order_result = await self.dropship.place_order(
                product_id=aliexpress_product_id,
                quantity=quantity,
                shipping_address=shipping_address
            )

            if not order_result['success']:
                print(f"❌ Order placement failed: {order_result.get('error')}")
                return order_result

            result = {
                'success': True,
                'shopify_order_id': shopify_order.get('id'),
                'aliexpress_order_id': order_result['order_id'],
                'total_cost': order_result['total_amount'],
                'tracking_pending': True
            }

            print(f"\n{'='*70}")
            print(f"✅ ORDER FULFILLED")
            print(f"{'='*70}")
            print(f"AliExpress Order ID: {result['aliexpress_order_id']}")
            print(f"Cost: ${result['total_cost']:.2f}")
            print(f"{'='*70}\n")

            return result

        except Exception as e:
            print(f"❌ Fulfillment error: {e}")
            import traceback
            traceback.print_exc()

            return {
                'success': False,
                'error': str(e)
            }

    def _extract_shipping_address(self, shopify_order: Dict) -> Dict:
        """Extract shipping address from Shopify order"""
        shipping = shopify_order.get('shipping_address', {})

        return {
            'name': shipping.get('name', ''),
            'address1': shipping.get('address1', ''),
            'address2': shipping.get('address2', ''),
            'city': shipping.get('city', ''),
            'province': shipping.get('province', ''),
            'country': shipping.get('country_code', 'US'),
            'country_code': shipping.get('country_code', 'US'),
            'zip': shipping.get('zip', ''),
            'phone': shipping.get('phone', '')
        }

    def _get_order_quantity(self, shopify_order: Dict) -> int:
        """Get total quantity from Shopify order"""
        line_items = shopify_order.get('line_items', [])

        if not line_items:
            return 1

        # Sum all quantities
        total = sum(item.get('quantity', 1) for item in line_items)

        return total

    async def update_tracking(
        self,
        shopify_order_id: str,
        aliexpress_order_id: str
    ) -> Dict:
        """
        Get tracking from AliExpress and update Shopify

        Returns tracking info
        """
        try:
            print(f"📍 Updating tracking for order {shopify_order_id}")

            # Get tracking from AliExpress
            tracking = await self.dropship.get_order_status(aliexpress_order_id)

            if not tracking:
                return {
                    'success': False,
                    'error': 'Tracking not available yet'
                }

            # TODO: Update Shopify with tracking
            # This requires Shopify fulfillment API

            return {
                'success': True,
                'tracking_number': tracking['tracking_number'],
                'carrier': tracking['shipping_carrier'],
                'status': tracking['status']
            }

        except Exception as e:
            print(f"❌ Tracking update error: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    async def bulk_fulfill(
        self,
        orders: List[Dict]
    ) -> List[Dict]:
        """Fulfill multiple orders"""
        import asyncio

        print(f"\n📦 Bulk fulfilling {len(orders)} orders...")

        results = []

        for order in orders:
            result = await self.fulfill_order(
                order['shopify_order'],
                order['aliexpress_product_id']
            )
            results.append(result)

            # Rate limit
            await asyncio.sleep(2)

        successful = sum(1 for r in results if r.get('success'))
        print(f"\n✅ Fulfilled {successful}/{len(orders)} orders")

        return results
