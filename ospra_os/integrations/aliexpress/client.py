"""
AliExpress API Client - Affiliate and Dropshipping Integration
"""
import os
import hmac
import hashlib
import logging
import time
import httpx
from typing import Dict, List, Optional
from urllib.parse import urlencode
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Diagnostic: log the RAW 200 body of the FIRST affiliate.product.query per
# process so we can see exactly what AliExpress says (tracking_id error vs
# genuinely-empty results) without spamming every keyword call.
_ae_raw_logged = False


class AliExpressClient:
    """Client for AliExpress Affiliate and Dropshipping API"""

    def __init__(self, app_key: str = None, app_secret: str = None, use_affiliate: bool = True):
        """
        Initialize AliExpress client

        Args:
            app_key: AliExpress API app key (overrides env)
            app_secret: AliExpress API app secret (overrides env)
            use_affiliate: If True, prefer AFFILIATE credentials for affiliate methods
        """
        # Try affiliate credentials first if requested, fallback to regular
        if use_affiliate:
            self.app_key = app_key or os.getenv('ALIEXPRESS_AFFILIATE_APP_KEY') or os.getenv('ALIEXPRESS_APP_KEY')
            self.app_secret = app_secret or os.getenv('ALIEXPRESS_AFFILIATE_APP_SECRET') or os.getenv('ALIEXPRESS_APP_SECRET')
        else:
            self.app_key = app_key or os.getenv('ALIEXPRESS_APP_KEY')
            self.app_secret = app_secret or os.getenv('ALIEXPRESS_APP_SECRET')

        if not self.app_key or not self.app_secret:
            raise ValueError("AliExpress API credentials not found in environment")

        self.base_url = "https://api-sg.aliexpress.com/sync"
        # tracking_id is MANDATORY for aliexpress.affiliate.product.query and must
        # be a REAL tracking_id registered in the affiliate account. Default empty
        # (not a bogus placeholder) so a missing value surfaces AE's explicit
        # "tracking_id mandatory" error instead of silently returning 0 products.
        self.tracking_id = os.getenv('ALIEXPRESS_TRACKING_ID', '').strip()
        if not self.tracking_id:
            logger.warning(
                "[AE] ALIEXPRESS_TRACKING_ID not set — affiliate.product.query "
                "will likely return 0 products (tracking_id is mandatory)."
            )

        print(f"[SUCCESS] AliExpress Client initialized (App Key: {self.app_key[:6]}...)")

    def _sign_request(self, params: Dict) -> str:
        """Generate API signature"""
        # Sort parameters
        sorted_params = sorted(params.items())

        # Create signature string
        sign_str = self.app_secret
        for k, v in sorted_params:
            sign_str += f"{k}{v}"
        sign_str += self.app_secret

        # Generate signature
        signature = hashlib.md5(sign_str.encode('utf-8')).hexdigest().upper()

        return signature

    async def _make_request(self, method: str, params: Dict) -> Dict:
        """Make signed API request"""
        try:
            # Add required parameters
            params.update({
                'app_key': self.app_key,
                'method': method,
                'timestamp': str(int(time.time() * 1000)),
                'format': 'json',
                'v': '2.0',
                'sign_method': 'md5'
            })

            # Sign request
            params['sign'] = self._sign_request(params)

            # Make request
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.base_url,
                    data=params
                )

                if response.status_code != 200:
                    print(f"[ERROR] AliExpress API error: {response.status_code}")
                    print(response.text)
                    return None

                # DIAGNOSTIC: dump the RAW 200 body of the first
                # affiliate.product.query so we see exactly what AE returns.
                global _ae_raw_logged
                if method == 'aliexpress.affiliate.product.query' and not _ae_raw_logged:
                    _ae_raw_logged = True
                    logger.warning(
                        f"[AE RAW] affiliate.product.query 200 body (first call this "
                        f"process, tracking_id={self.tracking_id!r}): {response.text[:2000]}"
                    )

                result = response.json()

                # Top-level API error (auth/signature/etc.)
                if 'error_response' in result:
                    error = result['error_response']
                    print(f"[ERROR] AliExpress error: {error.get('msg')}")
                    logger.warning(f"[AE] error_response: {error}")
                    return None

                # AE affiliate errors ALSO come back inside a 200 body as
                # resp_result.resp_code / resp_msg (e.g. "tracking_id mandatory")
                # — surface them instead of silently yielding 0 products.
                try:
                    resp_key = f"{method.replace('.', '_')}_response"
                    rr = (result.get(resp_key, {}) or {}).get('resp_result', {}) or {}
                    code = rr.get('resp_code')
                    if code is not None and str(code) != '200':
                        logger.warning(
                            f"[AE] {method} resp_code={code} resp_msg={rr.get('resp_msg')!r}"
                        )
                except Exception:
                    pass

                return result

        except Exception as e:
            print(f"[ERROR] Request error: {e}")
            return None

    async def search_products(
        self,
        keywords: str,
        category_id: str = None,
        min_price: float = None,
        max_price: float = None,
        page_size: int = 20
    ) -> List[Dict]:
        """
        Search for products on AliExpress

        Returns list of products with affiliate links
        """
        try:
            print(f"[SEARCH] Searching AliExpress: {keywords}")

            params = {
                'keywords': keywords,
                'page_size': page_size,
                'tracking_id': self.tracking_id
            }

            if category_id:
                params['category_ids'] = category_id
            if min_price:
                params['min_price'] = min_price
            if max_price:
                params['max_price'] = max_price

            result = await self._make_request(
                'aliexpress.affiliate.product.query',
                params
            )

            if not result:
                return []

            products = result.get('aliexpress_affiliate_product_query_response', {}).get('resp_result', {}).get('result', {}).get('products', {}).get('product', [])

            print(f"[SUCCESS] Found {len(products)} AliExpress products")

            return products

        except Exception as e:
            print(f"[ERROR] Search error: {e}")
            return []

    async def get_affiliate_links(
        self,
        product_ids: List[str],
        promotion_link_type: int = 0
    ) -> Dict:
        """
        Generate affiliate tracking links for products

        Args:
            product_ids: List of AliExpress product IDs
            promotion_link_type: 0 = normal, 2 = search link

        Returns:
            Dict of product_id -> affiliate_url
        """
        try:
            print(f"[LINK] Generating affiliate links for {len(product_ids)} products")

            params = {
                'product_ids': ','.join(product_ids),
                'promotion_link_type': promotion_link_type,
                'tracking_id': self.tracking_id
            }

            result = await self._make_request(
                'aliexpress.affiliate.link.generate',
                params
            )

            if not result:
                return {}

            links_data = result.get('aliexpress_affiliate_link_generate_response', {}).get('resp_result', {}).get('result', {}).get('promotion_links', {}).get('promotion_link', [])

            # Build dict of product_id -> url
            affiliate_links = {}
            for link in links_data:
                product_id = link.get('product_id')
                url = link.get('promotion_link')
                affiliate_links[product_id] = url

            print(f"[SUCCESS] Generated {len(affiliate_links)} affiliate links")

            return affiliate_links

        except Exception as e:
            print(f"[ERROR] Affiliate link error: {e}")
            return {}

    async def get_product_details(
        self,
        product_ids: List[str]
    ) -> List[Dict]:
        """Get detailed product information"""
        try:
            print(f"[PACKAGE] Getting details for {len(product_ids)} products")

            params = {
                'product_ids': ','.join(product_ids),
                'target_currency': 'USD',
                'target_language': 'EN',
                'tracking_id': self.tracking_id
            }

            result = await self._make_request(
                'aliexpress.affiliate.productdetail.get',
                params
            )

            if not result:
                return []

            products = result.get('aliexpress_affiliate_productdetail_get_response', {}).get('resp_result', {}).get('result', {}).get('products', {}).get('product', [])

            print(f"[SUCCESS] Got details for {len(products)} products")

            return products

        except Exception as e:
            print(f"[ERROR] Product details error: {e}")
            return []

    async def get_order_tracking(
        self,
        order_id: str
    ) -> Dict:
        """
        Get tracking information for an order

        Returns tracking number and shipping status
        """
        try:
            print(f"[LOCATION] Getting tracking for order {order_id}")

            params = {
                'order_id': order_id
            }

            result = await self._make_request(
                'aliexpress.logistics.redefining.getlogisticsselleraddresses',
                params
            )

            if not result:
                return None

            tracking_info = result.get('aliexpress_logistics_redefining_getlogisticsselleraddresses_response', {})

            return tracking_info

        except Exception as e:
            print(f"[ERROR] Tracking error: {e}")
            return None

    async def check_product_availability(
        self,
        product_id: str
    ) -> Dict:
        """
        Check if product is in stock and available

        Returns:
            {
                'available': bool,
                'stock_quantity': int,
                'price': float
            }
        """
        try:
            products = await self.get_product_details([product_id])

            if not products:
                return {
                    'available': False,
                    'stock_quantity': 0,
                    'price': 0
                }

            product = products[0]

            return {
                'available': product.get('product_status_type') == 'onSelling',
                'stock_quantity': product.get('stock_quantity', 0),
                'price': float(product.get('target_sale_price', 0))
            }

        except Exception as e:
            print(f"[ERROR] Availability check error: {e}")
            return {
                'available': False,
                'stock_quantity': 0,
                'price': 0
            }


class AliExpressDropshipping:
    """AliExpress Dropshipping-specific features"""

    def __init__(self, client: AliExpressClient):
        self.client = client

    async def place_order(
        self,
        product_id: str,
        quantity: int,
        shipping_address: Dict,
        variant_id: str = None
    ) -> Dict:
        """
        Place a dropshipping order

        Args:
            product_id: AliExpress product ID
            quantity: Order quantity
            shipping_address: Customer shipping address
            variant_id: Optional variant/SKU ID

        Returns:
            Order details with tracking
        """
        try:
            print(f"[CART] Placing order for product {product_id}")

            # Build order params
            params = {
                'product_id': product_id,
                'quantity': quantity,
                'country': shipping_address.get('country'),
                'province': shipping_address.get('province', ''),
                'city': shipping_address.get('city'),
                'address': shipping_address.get('address1'),
                'address2': shipping_address.get('address2', ''),
                'zip': shipping_address.get('zip'),
                'contact_person': shipping_address.get('name'),
                'mobile_no': shipping_address.get('phone', ''),
                'phone_country': shipping_address.get('country_code', '1')
            }

            if variant_id:
                params['sku_attr'] = variant_id

            result = await self.client._make_request(
                'aliexpress.trade.buy.placeorder',
                params
            )

            if not result:
                return {
                    'success': False,
                    'error': 'Order placement failed'
                }

            order_data = result.get('aliexpress_trade_buy_placeorder_response', {})

            order_info = {
                'success': True,
                'order_id': order_data.get('order_id'),
                'total_amount': order_data.get('total_amount'),
                'payment_url': order_data.get('payment_url')
            }

            print(f"[SUCCESS] Order placed! ID: {order_info['order_id']}")

            return order_info

        except Exception as e:
            print(f"[ERROR] Order placement error: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    async def get_order_status(self, order_id: str) -> Dict:
        """Get current order status and tracking"""
        try:
            params = {
                'order_id': order_id
            }

            result = await self.client._make_request(
                'aliexpress.trade.order.get',
                params
            )

            if not result:
                return None

            order_data = result.get('aliexpress_trade_order_get_response', {})

            return {
                'order_id': order_id,
                'status': order_data.get('order_status'),
                'tracking_number': order_data.get('logistics_info', {}).get('tracking_number'),
                'shipping_carrier': order_data.get('logistics_info', {}).get('shipping_carrier'),
                'estimated_delivery': order_data.get('estimated_delivery_time')
            }

        except Exception as e:
            print(f"[ERROR] Order status error: {e}")
            return None
