"""Amazon Product Advertising API (PA-API 5.0) connector for product research."""

import logging
from typing import List, Optional, Dict, Any
from amazon.paapi import AmazonAPI
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
        if access_key and secret_key and partner_tag:
            try:
                self.client = AmazonAPI(
                    access_key=access_key,
                    secret_key=secret_key,
                    tag=partner_tag,
                    country=country
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
            # Build search parameters
            search_params = {
                "Keywords": query,
                "ItemCount": min(limit, 10),  # PA-API max is 10 per request
                "Resources": [
                    "ItemInfo.Title",
                    "ItemInfo.Features",
                    "ItemInfo.ProductInfo",
                    "Images.Primary.Large",
                    "Offers.Listings.Price",
                    "Offers.Listings.Availability",
                    "BrowseNodeInfo.BrowseNodes",
                ]
            }

            # Add optional filters
            if category:
                search_params["SearchIndex"] = category
            if min_price:
                search_params["MinPrice"] = int(min_price)
            if max_price:
                search_params["MaxPrice"] = int(max_price)

            # Execute search
            logger.info(f"Searching Amazon for: {query} (limit={limit})")
            response = self.client.search_items(**search_params)

            # Parse results
            products = []
            if response and hasattr(response, 'items'):
                for item in response.items:
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
            response = self.client.get_items(
                item_ids=[asin],
                resources=[
                    "ItemInfo.Title",
                    "ItemInfo.Features",
                    "ItemInfo.ProductInfo",
                    "Images.Primary.Large",
                    "Offers.Listings.Price",
                    "Offers.Listings.Availability",
                    "BrowseNodeInfo.BrowseNodes",
                ]
            )

            if response and hasattr(response, 'items') and response.items:
                return self._parse_item(response.items[0])

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
            # Extract basic info
            name = None
            if hasattr(item, 'item_info') and hasattr(item.item_info, 'title'):
                name = item.item_info.title.display_value

            if not name:
                logger.warning("Skipping item without name")
                return None

            # Extract price
            price = None
            currency = "USD"
            if hasattr(item, 'offers') and hasattr(item.offers, 'listings'):
                if item.offers.listings and len(item.offers.listings) > 0:
                    listing = item.offers.listings[0]
                    if hasattr(listing, 'price'):
                        price = listing.price.amount
                        currency = listing.price.currency

            # Extract image
            image_url = None
            if hasattr(item, 'images') and hasattr(item.images, 'primary'):
                if hasattr(item.images.primary, 'large'):
                    image_url = item.images.primary.large.url

            # Extract ASIN and build URL
            asin = item.asin if hasattr(item, 'asin') else None
            url = f"https://www.amazon.com/dp/{asin}" if asin else None

            # Extract category
            category = None
            if hasattr(item, 'browse_node_info') and hasattr(item.browse_node_info, 'browse_nodes'):
                if item.browse_node_info.browse_nodes and len(item.browse_node_info.browse_nodes) > 0:
                    category = item.browse_node_info.browse_nodes[0].display_name

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
                # Amazon doesn't provide trend scores directly
                trend_score=None,
                search_volume=None,
                supplier_name="Amazon",
                supplier_rating=None,  # Would need additional API call
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
