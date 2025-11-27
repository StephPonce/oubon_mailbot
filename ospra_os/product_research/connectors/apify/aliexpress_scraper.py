"""
AliExpress Product Scraper using Apify

Scrapes AliExpress to find dropshipping products with:
- Direct product URLs for dropshipping
- Real supplier pricing
- Product images
- Ratings and reviews
- Shipping information
- Supplier ratings

Perfect for dropshipping - gets the actual product links you need!
"""
from typing import List, Dict, Optional
import logging
from .base_apify import ApifyConnector

logger = logging.getLogger(__name__)


class AliExpressScraper(ApifyConnector):
    """Scrape AliExpress for dropshipping product URLs and data"""

    # Apify actor for AliExpress scraping
    # Updated 2025: Using FREE actor (no monthly rental required)
    ACTOR_ID = "logical_scrapers/aliexpress-scraper"
    FALLBACK_ACTOR_ID = "epctex/aliexpress-scraper"  # Fallback to paid if needed

    async def search_products(
        self,
        keyword: str,
        max_products: int = 20,
        min_rating: float = 4.0,
        min_orders: int = 100,
        ship_from: str = "CN",
        currency: str = "USD"
    ) -> List[Dict]:
        """
        Search AliExpress products by keyword

        Args:
            keyword: Product search keyword
            max_products: Maximum number of products to scrape
            min_rating: Minimum seller rating (0-5)
            min_orders: Minimum number of orders
            ship_from: Shipping location (CN, US, etc.)
            currency: Price currency (USD, EUR, etc.)

        Returns:
            List of product dictionaries with dropship URLs
        """
        if not self.is_available():
            logger.warning("AliExpress scraper not available - Apify not configured")
            return []

        logger.info(f"🔍 Searching AliExpress: keyword={keyword}, max={max_products}")

        # Build search URL
        search_url = f"https://www.aliexpress.com/wholesale?SearchText={keyword.replace(' ', '+')}"

        run_input = {
            "startUrls": [{"url": search_url}],
            "maxItems": max_products,
            "language": "en_US",
            "currency": currency,
            "shipFrom": ship_from,
            "minRating": min_rating,
            "proxy": {
                "useApifyProxy": True,
                "apifyProxyGroups": ["RESIDENTIAL"]
            }
        }

        try:
            items = await self.run_actor(
                actor_id=self.ACTOR_ID,
                run_input=run_input,
                timeout_secs=300
            )

            products = []
            for item in items:
                try:
                    product = self._parse_product_item(item, keyword)
                    if product and product.get('orders', 0) >= min_orders:
                        products.append(product)
                except Exception as e:
                    logger.error(f"Error parsing AliExpress product: {e}")
                    continue

            logger.info(f"✅ Found {len(products)} AliExpress products")
            return products

        except Exception as e:
            logger.error(f"❌ AliExpress search failed: {e}")
            # Try fallback actor
            try:
                logger.info("🔄 Trying fallback AliExpress actor...")
                items = await self.run_actor(
                    actor_id=self.FALLBACK_ACTOR_ID,
                    run_input=run_input,
                    timeout_secs=300
                )
                products = []
                for item in items:
                    product = self._parse_product_item(item, keyword)
                    if product and product.get('orders', 0) >= min_orders:
                        products.append(product)
                return products
            except Exception as fallback_error:
                logger.error(f"❌ Fallback actor also failed: {fallback_error}")
                return []

    async def get_product_details(
        self,
        product_url: str
    ) -> Optional[Dict]:
        """
        Get detailed product information from AliExpress product page

        Args:
            product_url: Direct AliExpress product URL

        Returns:
            Detailed product dictionary or None
        """
        if not self.is_available():
            logger.warning("AliExpress scraper not available")
            return None

        logger.info(f"📦 Getting AliExpress product details: {product_url}")

        run_input = {
            "startUrls": [{"url": product_url}],
            "maxItems": 1,
            "language": "en_US",
            "currency": "USD",
            "includeDescription": True,
            "includeReviews": True,
            "proxy": {
                "useApifyProxy": True
            }
        }

        try:
            items = await self.run_actor(
                actor_id=self.ACTOR_ID,
                run_input=run_input,
                timeout_secs=180
            )

            if items and len(items) > 0:
                return self._parse_product_item(items[0], None)

            return None

        except Exception as e:
            logger.error(f"❌ Failed to get product details: {e}")
            return None

    async def find_trending_products(
        self,
        category: str = "consumer-electronics",
        max_products: int = 30
    ) -> List[Dict]:
        """
        Find trending/hot products on AliExpress

        Args:
            category: AliExpress category slug
            max_products: Maximum number of products

        Returns:
            List of trending products with URLs
        """
        if not self.is_available():
            logger.warning("AliExpress scraper not available")
            return []

        logger.info(f"🔥 Finding trending AliExpress products: category={category}")

        # URL for category page sorted by orders
        trending_url = f"https://www.aliexpress.com/category/{category}/products.html?sort=orders"

        run_input = {
            "startUrls": [{"url": trending_url}],
            "maxItems": max_products,
            "language": "en_US",
            "currency": "USD",
            "proxy": {
                "useApifyProxy": True
            }
        }

        try:
            items = await self.run_actor(
                actor_id=self.ACTOR_ID,
                run_input=run_input,
                timeout_secs=300
            )

            products = []
            for item in items:
                product = self._parse_product_item(item, category, is_trending=True)
                if product:
                    products.append(product)

            logger.info(f"✅ Found {len(products)} trending products")
            return products

        except Exception as e:
            logger.error(f"❌ Failed to find trending products: {e}")
            return []

    def _parse_product_item(
        self,
        item: Dict,
        keyword: Optional[str] = None,
        is_trending: bool = False
    ) -> Optional[Dict]:
        """
        Parse AliExpress product item into standardized format

        Args:
            item: Raw item from Apify scraper
            keyword: Search keyword used
            is_trending: Whether this is a trending product

        Returns:
            Standardized product dict or None
        """
        try:
            # Parse price - handle various formats
            price = self._parse_price(item.get('price', item.get('salePrice', '0')))
            original_price = self._parse_price(item.get('originalPrice', price))

            # Calculate discount
            discount_percent = 0
            if original_price > 0 and price < original_price:
                discount_percent = round(((original_price - price) / original_price) * 100, 1)

            # Parse orders count
            orders = self._parse_orders(item.get('orders', item.get('totalOrders', '0')))

            # Parse rating
            rating = float(item.get('rating', item.get('averageRating', 0)))

            # Build product URL (ensure it's complete)
            product_url = item.get('url', item.get('productUrl', ''))
            if product_url and not product_url.startswith('http'):
                product_url = f"https://www.aliexpress.com{product_url}"

            # Get product ID
            product_id = item.get('productId', item.get('id', ''))

            product = {
                # Basic Info
                'name': item.get('title', item.get('name', 'Unknown')),
                'aliexpress_url': product_url,
                'product_id': product_id,
                'source': 'aliexpress_apify',

                # Pricing
                'price': price,
                'original_price': original_price,
                'discount_percent': discount_percent,
                'currency': item.get('currency', 'USD'),

                # Images
                'image_url': item.get('image', item.get('imageUrl', item.get('thumbnail', ''))),
                'images': item.get('images', []),

                # Sales & Reviews
                'orders': orders,
                'rating': rating,
                'reviews_count': int(item.get('reviews', item.get('reviewsCount', 0))),

                # Supplier Info
                'seller_name': item.get('sellerName', item.get('storeName', 'Unknown')),
                'seller_rating': float(item.get('sellerRating', item.get('storeRating', 0))),
                'seller_url': item.get('sellerUrl', item.get('storeUrl', '')),

                # Shipping
                'shipping_cost': self._parse_price(item.get('shippingPrice', '0')),
                'free_shipping': item.get('freeShipping', False),
                'ships_from': item.get('shipFrom', item.get('shipsFrom', 'CN')),
                'delivery_time': item.get('deliveryTime', item.get('estimatedDelivery', '')),

                # Categorization
                'category': item.get('category', keyword if keyword else 'Unknown'),
                'is_trending': is_trending,

                # Additional Data
                'attributes': item.get('attributes', {}),
                'variations': item.get('variations', []),
                'in_stock': item.get('inStock', True),
            }

            # Only return if we have minimum required data
            if product['name'] and product['aliexpress_url'] and product['price'] > 0:
                return product

            return None

        except Exception as e:
            logger.error(f"Error parsing AliExpress product: {e}")
            return None

    def _parse_price(self, price_str: str) -> float:
        """
        Parse price string to float

        Handles formats like:
        - '$29.99'
        - 'US $29.99'
        - '29.99'
        - '$1,299.99'
        """
        if isinstance(price_str, (int, float)):
            return float(price_str)

        try:
            # Remove currency symbols and commas
            clean_price = ''.join(c for c in str(price_str) if c.isdigit() or c == '.')
            return float(clean_price) if clean_price else 0.0
        except:
            return 0.0

    def _parse_orders(self, orders_str: str) -> int:
        """
        Parse orders string to integer

        Handles formats like:
        - '1000+'
        - '5k+'
        - '10K'
        - '1500'
        """
        if isinstance(orders_str, int):
            return orders_str

        try:
            # Remove '+' and convert k/K to thousands
            clean_orders = str(orders_str).replace('+', '').replace(',', '').strip()

            if 'k' in clean_orders.lower():
                # Handle '5k' or '5.5k'
                num = float(clean_orders.lower().replace('k', ''))
                return int(num * 1000)

            return int(float(clean_orders)) if clean_orders else 0
        except:
            return 0
