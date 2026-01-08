"""Amazon Product Advertising API (PA-API 5.0) connector for product research."""

import logging
from typing import List, Optional, Dict, Any

try:
    from amazon_paapi import AmazonApi
    AMAZON_PAAPI_AVAILABLE = True
except ImportError:
    AMAZON_PAAPI_AVAILABLE = False
    AmazonApi = None

from ..base import BaseConnector, ProductCandidate

logger = logging.getLogger(__name__)


class AmazonPAAPIConnector(BaseConnector):
    """
    Amazon Product Advertising API connector.

    Requires:
    - Amazon Associate account
    - PA-API access credentials
    - Partner tag (tracking ID)

    Environment Variables:
    - AMAZON_ACCESS_KEY: Your PA-API access key
    - AMAZON_SECRET_KEY: Your PA-API secret key
    - AMAZON_PARTNER_TAG: Your Amazon Associate tracking ID
    """

    def __init__(
        self,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        partner_tag: Optional[str] = None,
        country: str = "US",
        **kwargs
    ):
        """
        Initialize Amazon PA-API connector.

        Args:
            access_key: PA-API access key
            secret_key: PA-API secret key
            partner_tag: Amazon Associate tracking ID
            country: Amazon marketplace country code (default: US)
        """
        super().__init__(api_key=access_key, **kwargs)

        self.access_key = access_key
        self.secret_key = secret_key
        self.partner_tag = partner_tag
        self.country = country

        # Initialize Amazon API client if credentials provided
        self.client = None
        
        if not AMAZON_PAAPI_AVAILABLE:
            self.enabled = False
            logger.warning("amazon_paapi package not installed - run: pip install python-amazon-paapi")
            return
            
        if access_key and secret_key and partner_tag:
            try:
                # python-amazon-paapi uses 'key' and 'secret' parameters
                self.client = AmazonApi(
                    key=access_key,
                    secret=secret_key,
                    tag=partner_tag,
                    country=country,
                    throttling=1.0  # 1 request per second to avoid rate limits
                )
                self.enabled = True
                logger.info(f"Amazon PA-API connector initialized for {country} marketplace")
            except Exception as e:
                logger.error(f"Failed to initialize Amazon PA-API: {e}")
                self.enabled = False
        else:
            self.enabled = False
            logger.warning("Amazon PA-API credentials not provided - connector disabled")

    @property
    def name(self) -> str:
        """Connector display name."""
        return "Amazon Product Advertising API"

    @property
    def source_id(self) -> str:
        """Short identifier for this connector."""
        return "amazon"

    async def search(
        self,
        query: str,
        limit: int = 10,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        category: Optional[str] = None,
        **kwargs
    ) -> List[ProductCandidate]:
        """
        Search for products on Amazon.

        Args:
            query: Search keyword or phrase
            limit: Maximum number of results (max 10 per API call)
            min_price: Minimum price filter (in cents, e.g., 1000 = $10)
            max_price: Maximum price filter (in cents)
            category: Amazon search index/category (e.g., "Electronics", "HomeAndKitchen")

        Returns:
            List of product candidates
        """
        if not self.is_available():
            logger.warning("Amazon PA-API connector not available")
            return []

        try:
            # Execute search using python-amazon-paapi library
            logger.info(f"Searching Amazon for: {query} (limit={limit})")
            
            # Build search kwargs
            search_kwargs = {
                "keywords": query,
                "item_count": min(limit, 10),  # PA-API max is 10 per request
            }
            
            # Add optional filters
            if category:
                search_kwargs["search_index"] = category
            if min_price:
                search_kwargs["min_price"] = int(min_price)
            if max_price:
                search_kwargs["max_price"] = int(max_price)

            # Execute search - python-amazon-paapi returns SearchResult object
            search_result = self.client.search_items(**search_kwargs)

            # Parse results
            products = []
            if search_result and hasattr(search_result, 'items') and search_result.items:
                for item in search_result.items:
                    product = self._parse_item(item)
                    if product:
                        products.append(product)

            logger.info(f"Found {len(products)} products on Amazon for '{query}'")
            return products

        except Exception as e:
            logger.error(f"Amazon search failed for '{query}': {e}")
            return []

    async def get_trending(
        self,
        category: Optional[str] = None,
        limit: int = 10
    ) -> List[ProductCandidate]:
        """
        Get trending/best-selling products from Amazon.

        Note: PA-API 5.0 doesn't have a direct "trending" endpoint.
        This method searches for "best sellers" or uses category-specific queries.

        Args:
            category: Product category (e.g., "Electronics", "HomeAndKitchen")
            limit: Maximum number of results

        Returns:
            List of trending product candidates
        """
        if not self.is_available():
            logger.warning("Amazon PA-API connector not available")
            return []

        try:
            # Use "best seller" search as proxy for trending
            search_query = "best seller"
            if category:
                search_query = f"{category} best seller"

            return await self.search(
                query=search_query,
                limit=limit,
                category=category
            )

        except Exception as e:
            logger.error(f"Failed to get trending Amazon products: {e}")
            return []

    async def get_product_by_asin(self, asin: str) -> Optional[ProductCandidate]:
        """
        Get product details by ASIN.

        Args:
            asin: Amazon Standard Identification Number

        Returns:
            Product candidate or None if not found
        """
        if not self.is_available():
            logger.warning("Amazon PA-API connector not available")
            return None

        try:
            logger.info(f"Fetching Amazon product: {asin}")
            # python-amazon-paapi uses get_items with ASIN string or list
            items = self.client.get_items(asin)

            if items and len(items) > 0:
                return self._parse_item(items[0])

            logger.warning(f"Product not found: {asin}")
            return None

        except Exception as e:
            logger.error(f"Failed to fetch product {asin}: {e}")
            return None

    def _parse_item(self, item) -> Optional[ProductCandidate]:
        """
        Parse Amazon API item into ProductCandidate.

        Args:
            item: Amazon PA-API item object

        Returns:
            ProductCandidate or None if parsing fails
        """
        try:
            # Extract basic info - python-amazon-paapi item structure
            name = None
            if hasattr(item, 'item_info') and item.item_info:
                if hasattr(item.item_info, 'title') and item.item_info.title:
                    name = item.item_info.title.display_value

            if not name:
                logger.warning("Skipping item without name")
                return None

            # Extract price
            price = None
            currency = "USD"
            if hasattr(item, 'offers') and item.offers:
                if hasattr(item.offers, 'listings') and item.offers.listings:
                    if len(item.offers.listings) > 0:
                        listing = item.offers.listings[0]
                        if hasattr(listing, 'price') and listing.price:
                            price = listing.price.amount
                            if hasattr(listing.price, 'currency'):
                                currency = listing.price.currency

            # Extract image
            image_url = None
            if hasattr(item, 'images') and item.images:
                if hasattr(item.images, 'primary') and item.images.primary:
                    if hasattr(item.images.primary, 'large') and item.images.primary.large:
                        image_url = item.images.primary.large.url

            # Extract ASIN and build URL
            asin = getattr(item, 'asin', None)
            url = f"https://www.amazon.com/dp/{asin}" if asin else None
            
            # Also try detail_page_url if available (affiliate link)
            if hasattr(item, 'detail_page_url') and item.detail_page_url:
                url = item.detail_page_url

            # Extract category
            category = None
            if hasattr(item, 'browse_node_info') and item.browse_node_info:
                if hasattr(item.browse_node_info, 'browse_nodes') and item.browse_node_info.browse_nodes:
                    if len(item.browse_node_info.browse_nodes) > 0:
                        node = item.browse_node_info.browse_nodes[0]
                        if hasattr(node, 'display_name'):
                            category = node.display_name

            # Build ProductCandidate
            return ProductCandidate(
                name=name,
                source=self.source_id,
                price=price,
                currency=currency,
                url=url,
                image_url=image_url,
                category=category,
                tags=[asin] if asin else [],
                trend_score=None,
                search_volume=None,
                supplier_name="Amazon",
                supplier_rating=None,
            )

        except Exception as e:
            logger.error(f"Failed to parse Amazon item: {e}")
            return None

    async def validate(self) -> bool:
        """
        Validate Amazon PA-API credentials.

        Returns:
            True if credentials are valid and working
        """
        if not self.is_available():
            return False

        try:
            # Try a simple search with 1 result
            results = await self.search(query="test", limit=1)
            return len(results) > 0
        except Exception as e:
            logger.error(f"Amazon PA-API validation failed: {e}")
            return False
