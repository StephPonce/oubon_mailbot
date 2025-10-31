"""
Official AliExpress Dropshipping API Client
Uses the AliExpress Open Platform API for product search
"""

import os
import time
import hashlib
import hmac
import json
import httpx
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class AliExpressAPIClient:
    """
    Official AliExpress Dropshipping API client
    Docs: https://developers.aliexpress.com/en/doc.htm
    """

    def __init__(self):
        self.app_key = os.getenv('ALIEXPRESS_APP_KEY')
        self.app_secret = os.getenv('ALIEXPRESS_APP_SECRET')
        self.api_url = 'https://api-sg.aliexpress.com/sync'

        if not self.app_key or not self.app_secret:
            logger.warning("⚠️  AliExpress API credentials not found in environment")
        else:
            logger.info(f"✅ AliExpress API initialized (App Key: {self.app_key[:10]}...)")

    def _generate_signature(self, params: Dict) -> str:
        """
        Generate HMAC-MD5 signature for API request
        """
        # Sort parameters alphabetically
        sorted_params = sorted(params.items())

        # Concatenate into string
        param_string = ''.join(f'{k}{v}' for k, v in sorted_params)

        # Add secret at beginning and end
        sign_string = self.app_secret + param_string + self.app_secret

        # Calculate MD5 hash
        return hashlib.md5(sign_string.encode('utf-8')).hexdigest().upper()

    async def search_products(
        self,
        query: str,
        min_orders: int = 1000,
        min_rating: float = 4.5,
        limit: int = 20
    ) -> List[Dict]:
        """
        Search AliExpress products using official Dropshipping API

        Tries multiple feed types to find available products
        """
        if not self.app_key or not self.app_secret:
            logger.error("❌ AliExpress API credentials missing")
            return []

        # Try different feed types (app may have access to specific feeds)
        feed_names = [
            'DS_bestselling',
            'DS_new_arrival',
            'DS_featured',
            'DS_hot_product'
        ]

        for feed_name in feed_names:
            try:
                logger.info(f"🔍 Trying AliExpress Dropshipping API with feed: {feed_name}")
                products = await self._try_feed(feed_name, query, min_orders, min_rating, limit)

                if products:
                    logger.info(f"✅ Got {len(products)} products from feed: {feed_name}")
                    return products

            except Exception as e:
                logger.warning(f"⚠️  Feed {feed_name} failed: {e}")
                continue

        logger.error("❌ All feed types failed")
        return []

    async def _try_feed(
        self,
        feed_name: str,
        query: str,
        min_orders: int,
        min_rating: float,
        limit: int
    ) -> List[Dict]:
        """Try a specific feed type"""
        timestamp = str(int(time.time() * 1000))

        params = {
            'app_key': self.app_key,
            'format': 'json',
            'method': 'aliexpress.ds.recommend.feed.get',
            'sign_method': 'md5',
            'timestamp': timestamp,
            'v': '2.0',
            # Feed parameters
            'feed_name': feed_name,
            'page_no': '1',
            'page_size': str(min(limit * 2, 50)),  # Request more to allow filtering
            'target_currency': 'USD',
            'target_language': 'EN',
            'country': 'US'
        }

        # Generate signature
        params['sign'] = self._generate_signature(params)

        try:
            # Make API request
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self.api_url, data=params)
                response.raise_for_status()

                data = response.json()

                # Check for API errors
                if 'error_response' in data:
                    error = data['error_response']
                    logger.debug(f"Feed {feed_name} error: {error.get('msg', 'Unknown')}")
                    return []

                # Parse successful response
                if 'aliexpress_ds_recommend_feed_get_response' in data:
                    result = data['aliexpress_ds_recommend_feed_get_response']['result']
                    products_data = result.get('products', {}).get('product', [])

                    if not products_data:
                        logger.debug(f"Feed {feed_name} returned 0 products")
                        return []

                    # Convert to standardized format
                    products = []
                    for item in products_data:
                        # Filter by minimum criteria (relaxed for feeds)
                        orders = int(item.get('lastest_volume', 0))
                        if orders < min_orders // 2:  # Relaxed criteria for feed
                            continue

                        # Rating is in percentage format (e.g., "96%" = 4.8 stars)
                        rating_str = item.get('evaluate_rate', '80%')
                        try:
                            rating = float(rating_str.rstrip('%')) / 20.0
                        except:
                            rating = 4.0

                        if rating < min_rating - 0.5:  # Relaxed criteria
                            continue

                        products.append({
                            'product_id': str(item.get('product_id', '')),
                            'name': item.get('product_title', ''),
                            'price': float(item.get('target_sale_price', 0)),
                            'original_price': float(item.get('target_original_price', 0)),
                            'orders': orders,
                            'rating': rating,
                            'image_url': item.get('product_main_image_url', ''),
                            'url': item.get('promotion_link', '') or f"https://www.aliexpress.com/item/{item.get('product_id')}.html",
                            'shipping_days': int(item.get('ship_to_days', 15)),
                            'supplier_rating': 95.0,
                            'store_name': item.get('shop_title', 'AliExpress Store'),
                            'store_id': item.get('shop_id', '')
                        })

                        if len(products) >= limit:
                            break

                    return products

                logger.warning(f"⚠️  Unexpected API response format for feed {feed_name}")
                return []

        except httpx.TimeoutException:
            logger.error("❌ AliExpress API timeout")
            return []
        except Exception as e:
            logger.error(f"❌ AliExpress API error: {e}")
            return []

    async def get_product_details(self, product_ids: List[str]) -> List[Dict]:
        """
        Get detailed product information by IDs

        API Method: aliexpress.ds.product.get
        """
        if not self.app_key or not self.app_secret:
            return []

        try:
            timestamp = str(int(time.time() * 1000))

            params = {
                'app_key': self.app_key,
                'format': 'json',
                'method': 'aliexpress.ds.product.get',
                'partner_id': 'apidoc',
                'session': '',
                'sign_method': 'md5',
                'timestamp': timestamp,
                'v': '2.0',
                'product_id': ','.join(product_ids),
                'target_currency': 'USD',
                'target_language': 'EN'
            }

            params['sign'] = self._generate_signature(params)

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self.api_url, data=params)
                response.raise_for_status()

                data = response.json()

                if 'error_response' in data:
                    logger.error(f"❌ Product details error: {data['error_response']}")
                    return []

                # Parse product details
                if 'aliexpress_ds_product_get_response' in data:
                    result = data['aliexpress_ds_product_get_response']['result']
                    return [result]  # Details for single product

                return []

        except Exception as e:
            logger.error(f"❌ Product details error: {e}")
            return []
