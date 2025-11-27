"""
Shopify Competitor Scraper using Apify

Scrapes competitor Shopify stores to identify winning products,
pricing strategies, and market opportunities.
"""
from typing import List, Dict, Optional
import logging
from .base_apify import ApifyConnector

logger = logging.getLogger(__name__)


class ShopifyCompetitorScraper(ApifyConnector):
    """Scrape competitor Shopify stores for product intelligence"""

    # Apify actor for Shopify scraping
    # Updated 2025: Using general web scraper (Shopify-specific actors deprecated)
    SHOPIFY_SCRAPER_ACTOR = "apify/web-scraper"

    # Known successful dropshipping stores (curated list)
    COMPETITOR_STORES = [
        "gadget-hut.myshopify.com",
        "trending-tech.myshopify.com",
        "smart-living-store.myshopify.com",
        "viral-products.myshopify.com"
    ]

    async def scrape_competitor_store(
        self,
        store_url: str,
        max_products: int = 50,
        collections: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Scrape products from a Shopify competitor store

        Args:
            store_url: Shopify store URL (e.g., "store.myshopify.com")
            max_products: Maximum number of products to scrape
            collections: Specific collections to scrape (None = all)

        Returns:
            List of competitor product dictionaries
        """
        if not self.is_available():
            logger.warning("Shopify scraper not available - Apify not configured")
            return []

        logger.info(f"🛒 Scraping competitor store: {store_url}")

        # Simple pageFunction to extract Shopify products.json
        page_function = """
        async function pageFunction(context) {
            const { request, page, log } = context;

            // Try to fetch products.json (Shopify's product API)
            try {
                const response = await fetch(request.url + '/products.json');
                const data = await response.json();

                return {
                    products: data.products || []
                };
            } catch (error) {
                log.error('Failed to fetch products.json:', error);
                return { products: [] };
            }
        }
        """

        run_input = {
            "startUrls": [{"url": f"https://{store_url}"}],
            "pageFunction": page_function,
            "maxPages": max_products,
            "proxyConfiguration": {
                "useApifyProxy": True
            }
        }

        # Add specific collections if provided
        if collections:
            run_input["collections"] = collections

        try:
            items = await self.run_actor(
                actor_id=self.SHOPIFY_SCRAPER_ACTOR,
                run_input=run_input,
                timeout_secs=300
            )

            # Parse products
            products = []
            for item in items:
                try:
                    product = self._parse_shopify_product(item, store_url)
                    if product:
                        products.append(product)
                except Exception as e:
                    logger.error(f"Error parsing Shopify product: {e}")
                    continue

            logger.info(f"✅ Scraped {len(products)} products from {store_url}")
            return products

        except Exception as e:
            logger.error(f"❌ Shopify store scraping failed: {e}")
            return []

    async def scrape_multiple_competitors(
        self,
        store_urls: Optional[List[str]] = None,
        max_per_store: int = 20
    ) -> Dict[str, List[Dict]]:
        """
        Scrape products from multiple competitor stores

        Args:
            store_urls: List of store URLs (None = use default competitors)
            max_per_store: Max products per store

        Returns:
            Dict mapping store URL to list of products
        """
        if store_urls is None:
            store_urls = self.COMPETITOR_STORES

        logger.info(f"🎯 Scraping {len(store_urls)} competitor stores")

        results = {}

        for store_url in store_urls:
            try:
                products = await self.scrape_competitor_store(
                    store_url=store_url,
                    max_products=max_per_store
                )
                results[store_url] = products

                logger.info(f"✅ {store_url}: {len(products)} products")

            except Exception as e:
                logger.error(f"❌ Failed to scrape {store_url}: {e}")
                results[store_url] = []

        total_products = sum(len(prods) for prods in results.values())
        logger.info(f"✅ Total competitor products: {total_products}")

        return results

    async def find_bestsellers(
        self,
        store_url: str,
        min_reviews: int = 10,
        max_products: int = 30
    ) -> List[Dict]:
        """
        Find bestselling products from a competitor store

        Filters for products with high reviews/ratings = proven sellers.

        Args:
            store_url: Shopify store URL
            min_reviews: Minimum number of reviews required
            max_products: Maximum products to scrape

        Returns:
            List of bestselling product dicts
        """
        if not self.is_available():
            logger.warning("Shopify scraper not available")
            return []

        logger.info(f"🏆 Finding bestsellers from {store_url}")

        # Scrape all products first
        all_products = await self.scrape_competitor_store(
            store_url=store_url,
            max_products=max_products
        )

        # Filter for bestsellers
        bestsellers = [
            p for p in all_products
            if p.get('reviews_count', 0) >= min_reviews
        ]

        # Sort by reviews count (descending)
        bestsellers.sort(key=lambda x: x.get('reviews_count', 0), reverse=True)

        logger.info(f"✅ Found {len(bestsellers)} bestsellers")
        return bestsellers

    def _parse_shopify_product(
        self,
        item: Dict,
        store_url: str
    ) -> Optional[Dict]:
        """
        Parse Shopify product into standardized format

        Args:
            item: Raw product data from scraper
            store_url: Source store URL

        Returns:
            Standardized product dict or None
        """
        try:
            # Parse price
            price = self._parse_price(item.get('price', item.get('currentPrice', 0)))
            compare_price = self._parse_price(item.get('compareAtPrice', 0))

            # Calculate discount if available
            discount_percent = 0
            if compare_price and compare_price > price:
                discount_percent = round(((compare_price - price) / compare_price) * 100, 1)

            # Parse variants
            variants = item.get('variants', [])
            variant_count = len(variants) if variants else 1

            # Extract images
            images = item.get('images', [])
            image_url = images[0] if images else item.get('image', '')

            product = {
                # Basic Info
                'name': item.get('title', item.get('name', 'Unknown')),
                'price': price,
                'compare_at_price': compare_price,
                'discount_percent': discount_percent,
                'image_url': image_url,
                'images': images,
                'source_url': item.get('url', item.get('productUrl', '')),
                'source': 'shopify_competitor',
                'competitor_store': store_url,

                # Product Details
                'product_type': item.get('productType', item.get('type', '')),
                'vendor': item.get('vendor', 'Unknown'),
                'tags': item.get('tags', []),
                'description': item.get('description', item.get('descriptionHtml', '')),

                # Variants
                'variant_count': variant_count,
                'variants': variants,
                'in_stock': item.get('inStock', item.get('availableForSale', True)),

                # Social Proof
                'reviews_count': item.get('reviewsCount', 0),
                'rating': item.get('rating', 0),

                # Metadata
                'created_at': item.get('createdAt', ''),
                'updated_at': item.get('updatedAt', ''),
                'handle': item.get('handle', '')
            }

            # Only return if we have minimum required data
            if product['name'] and product['price'] > 0:
                return product

            return None

        except Exception as e:
            logger.error(f"Error parsing Shopify product: {e}")
            return None

    def _parse_price(self, price_value) -> float:
        """
        Parse price to float

        Handles various formats:
        - "29.99"
        - "$29.99"
        - 29.99
        - "2999" (cents)

        Args:
            price_value: Price value (string, int, or float)

        Returns:
            Price as float
        """
        if not price_value:
            return 0.0

        try:
            # If already a number
            if isinstance(price_value, (int, float)):
                # Check if it's in cents (e.g., 2999 instead of 29.99)
                if price_value > 500:  # Assume values > 500 are in cents
                    return round(price_value / 100, 2)
                return float(price_value)

            # If string, clean and parse
            if isinstance(price_value, str):
                # Remove currency symbols and spaces
                cleaned = price_value.replace('$', '').replace('£', '').replace('€', '')
                cleaned = cleaned.replace(',', '').replace(' ', '').strip()

                # Handle price ranges (take first price)
                if '-' in cleaned:
                    cleaned = cleaned.split('-')[0].strip()

                price = float(cleaned)

                # Check if in cents
                if price > 500:
                    return round(price / 100, 2)
                return price

            return 0.0

        except (ValueError, AttributeError):
            logger.warning(f"Could not parse price: {price_value}")
            return 0.0

    def analyze_competitor_pricing(
        self,
        competitor_products: Dict[str, List[Dict]]
    ) -> Dict:
        """
        Analyze pricing strategies across competitors

        Args:
            competitor_products: Dict mapping store to products

        Returns:
            Pricing analysis metrics
        """
        all_products = []
        for products in competitor_products.values():
            all_products.extend(products)

        if not all_products:
            return {
                'avg_price': 0,
                'median_price': 0,
                'price_range': (0, 0),
                'avg_discount': 0
            }

        prices = [p['price'] for p in all_products if p['price'] > 0]
        discounts = [p['discount_percent'] for p in all_products if p['discount_percent'] > 0]

        avg_price = sum(prices) / len(prices) if prices else 0
        median_price = sorted(prices)[len(prices) // 2] if prices else 0
        avg_discount = sum(discounts) / len(discounts) if discounts else 0

        return {
            'total_products': len(all_products),
            'avg_price': round(avg_price, 2),
            'median_price': round(median_price, 2),
            'price_range': (round(min(prices), 2), round(max(prices), 2)) if prices else (0, 0),
            'avg_discount': round(avg_discount, 1),
            'stores_analyzed': len(competitor_products)
        }
