"""
Amazon Bestsellers Scraper using Apify

Scrapes Amazon bestseller lists to identify products with proven demand.
Bestsellers = validated market demand + proven sales velocity.
"""
from typing import List, Dict, Optional
import logging
from .base_apify import ApifyConnector

logger = logging.getLogger(__name__)


class AmazonBestsellersScraper(ApifyConnector):
    """Scrape Amazon bestseller lists for products with proven demand"""

    # Apify actors for Amazon scraping
    # Note: Update with actual actor IDs from Apify Store
    ACTOR_ID = "junglee/amazon-bestseller-scraper"
    AMAZON_SCRAPER_ACTOR = "apify/amazon-scraper"

    async def scrape_bestsellers(
        self,
        category: str = "Electronics",
        max_products: int = 50,
        country: str = "US"
    ) -> List[Dict]:
        """
        Scrape Amazon bestsellers in a specific category

        Args:
            category: Amazon category (Electronics, Home & Kitchen, etc.)
            max_products: Maximum number of products to scrape
            country: Country code (US, UK, DE, FR, JP, etc.)

        Returns:
            List of bestselling product dictionaries
        """
        if not self.is_available():
            logger.warning("Amazon bestsellers scraper not available - Apify not configured")
            return []

        logger.info(f"📊 Scraping Amazon bestsellers: category={category}, country={country}")

        run_input = {
            "category": category,
            "maxItems": max_products,
            "country": country,
            "includeReviews": True,
            "includePrice": True,
            "includeBSR": True  # Best Seller Rank
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
                    product = self._parse_bestseller_item(item, category)
                    if product:
                        products.append(product)
                except Exception as e:
                    logger.error(f"Error parsing Amazon product: {e}")
                    continue

            logger.info(f"✅ Parsed {len(products)} Amazon bestsellers")
            return products

        except Exception as e:
            logger.error(f"❌ Amazon bestsellers scraping failed: {e}")
            return []

    async def scrape_new_releases(
        self,
        category: str = "Electronics",
        max_products: int = 30,
        country: str = "US"
    ) -> List[Dict]:
        """
        Scrape Amazon's new releases (hot new products)

        New releases often indicate emerging trends before they hit bestseller lists.

        Args:
            category: Amazon category
            max_products: Maximum number of products
            country: Country code

        Returns:
            List of new release product dictionaries
        """
        if not self.is_available():
            logger.warning("Amazon new releases scraper not available")
            return []

        logger.info(f"🆕 Scraping Amazon new releases: category={category}")

        run_input = {
            "category": category,
            "maxItems": max_products,
            "country": country,
            "listType": "new-releases"
        }

        try:
            items = await self.run_actor(
                actor_id=self.ACTOR_ID,
                run_input=run_input,
                timeout_secs=240
            )

            products = []
            for item in items:
                product = self._parse_bestseller_item(item, category, is_new_release=True)
                if product:
                    products.append(product)

            logger.info(f"✅ Found {len(products)} new releases")
            return products

        except Exception as e:
            logger.error(f"❌ Amazon new releases scraping failed: {e}")
            return []

    async def scrape_movers_and_shakers(
        self,
        category: str = "Electronics",
        max_products: int = 30,
        country: str = "US"
    ) -> List[Dict]:
        """
        Scrape Amazon's Movers & Shakers (products with biggest rank gains)

        Movers & Shakers = velocity leaders = trending NOW.
        These are products gaining sales momentum rapidly.

        Args:
            category: Amazon category
            max_products: Maximum number of products
            country: Country code

        Returns:
            List of trending product dictionaries
        """
        if not self.is_available():
            logger.warning("Amazon movers & shakers scraper not available")
            return []

        logger.info(f"🚀 Scraping Amazon movers & shakers: category={category}")

        run_input = {
            "category": category,
            "maxItems": max_products,
            "country": country,
            "listType": "movers-and-shakers"
        }

        try:
            items = await self.run_actor(
                actor_id=self.ACTOR_ID,
                run_input=run_input,
                timeout_secs=240
            )

            products = []
            for item in items:
                product = self._parse_bestseller_item(item, category, is_trending=True)
                if product:
                    products.append(product)

            logger.info(f"✅ Found {len(products)} movers & shakers")
            return products

        except Exception as e:
            logger.error(f"❌ Amazon movers & shakers scraping failed: {e}")
            return []

    def _parse_bestseller_item(
        self,
        item: Dict,
        category: str,
        is_new_release: bool = False,
        is_trending: bool = False
    ) -> Optional[Dict]:
        """
        Parse Amazon bestseller item into standardized product format

        Args:
            item: Raw item from Apify scraper
            category: Product category
            is_new_release: Whether this is from new releases list
            is_trending: Whether this is from movers & shakers

        Returns:
            Standardized product dict or None if parsing fails
        """
        try:
            # Parse price
            price = self._parse_price(item.get('price', ''))

            # Calculate demand score based on rank and reviews
            rank = item.get('rank', item.get('bestSellerRank', 999))
            reviews = int(item.get('reviews', item.get('reviewsCount', 0)))

            # Lower rank = better (rank 1 is best)
            # More reviews = more demand
            demand_score = self._calculate_demand_score(rank, reviews)

            product = {
                # Basic Info
                'name': item.get('title', item.get('name', 'Unknown')),
                'price': price,
                'image_url': item.get('image', item.get('imageUrl', '')),
                'source_url': item.get('url', item.get('productUrl', '')),
                'source': 'amazon_bestsellers',
                'category': category,

                # Amazon-specific
                'asin': item.get('asin', ''),
                'bestseller_rank': rank,
                'is_bestseller': rank <= 100,  # Top 100 = bestseller

                # Ratings & Reviews
                'rating': float(item.get('stars', item.get('rating', 0))),
                'reviews_count': reviews,

                # Demand Metrics
                'demand_score': demand_score,
                'is_new_release': is_new_release,
                'is_trending': is_trending,

                # Additional data
                'brand': item.get('brand', 'Unknown'),
                'in_stock': item.get('inStock', True),
                'prime_eligible': item.get('isPrime', False)
            }

            # Only return if we have minimum required data
            if product['name'] and product['price'] > 0:
                return product

            return None

        except Exception as e:
            logger.error(f"Error parsing bestseller item: {e}")
            return None

    def _parse_price(self, price_str: str) -> float:
        """
        Parse price string like '$29.99' to float

        Handles various formats:
        - '$29.99'
        - '$1,299.99'
        - '£29.99'
        - '€29.99'
        - '29.99'

        Args:
            price_str: Price string

        Returns:
            Price as float
        """
        if not price_str:
            return 0.0

        try:
            # Remove currency symbols and spaces
            cleaned = price_str.replace('$', '').replace('£', '').replace('€', '')
            cleaned = cleaned.replace(',', '').replace(' ', '').strip()

            # Handle price ranges (take the first price)
            if '-' in cleaned:
                cleaned = cleaned.split('-')[0].strip()

            return float(cleaned)

        except (ValueError, AttributeError):
            logger.warning(f"Could not parse price: {price_str}")
            return 0.0

    def _calculate_demand_score(self, rank: int, reviews: int) -> float:
        """
        Calculate demand score based on bestseller rank and review count

        Formula combines:
        - Bestseller rank (lower = better)
        - Review count (more = better demand)

        Args:
            rank: Bestseller rank (1 = best)
            reviews: Number of reviews

        Returns:
            Demand score (higher = more demand)
        """
        try:
            # Rank score: inverse of rank (rank 1 = score 100, rank 100 = score 1)
            # Use min to cap at reasonable value
            rank_score = max(0, 100 - min(rank, 100))

            # Review score: logarithmic scale
            # 0 reviews = 0, 100 reviews = ~20, 1000 reviews = ~30, 10000 reviews = ~40
            import math
            review_score = math.log10(max(reviews, 1)) * 10

            # Combined score (rank weighted more heavily)
            demand_score = (rank_score * 0.7) + (review_score * 0.3)

            return round(demand_score, 2)

        except Exception as e:
            logger.error(f"Error calculating demand score: {e}")
            return 0.0

    async def get_category_bestsellers_batch(
        self,
        categories: List[str],
        max_per_category: int = 20,
        country: str = "US"
    ) -> Dict[str, List[Dict]]:
        """
        Scrape bestsellers from multiple categories in batch

        Efficient way to get bestsellers across multiple niches.

        Args:
            categories: List of Amazon categories
            max_per_category: Max products per category
            country: Country code

        Returns:
            Dict mapping category to list of products
        """
        logger.info(f"📊 Batch scraping {len(categories)} categories")

        results = {}

        for category in categories:
            try:
                products = await self.scrape_bestsellers(
                    category=category,
                    max_products=max_per_category,
                    country=country
                )
                results[category] = products

                logger.info(f"✅ {category}: {len(products)} products")

            except Exception as e:
                logger.error(f"❌ Failed to scrape {category}: {e}")
                results[category] = []

        total_products = sum(len(prods) for prods in results.values())
        logger.info(f"✅ Batch complete: {total_products} total products")

        return results
