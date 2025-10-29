"""Temporary AliExpress product scraper until OAuth is approved."""

import re
from typing import Dict, Optional


class AliExpressScraper:
    """
    Scrape AliExpress product details from URL.

    Temporary solution until AliExpress Seller API OAuth is approved.
    Currently returns mock data - implement actual scraping when needed.
    """

    def scrape_product(self, url: str) -> Dict:
        """
        Scrape product details from AliExpress URL.

        Args:
            url: AliExpress product URL

        Returns:
            {
                "success": True,
                "product": {
                    "title": "Product name",
                    "price": 12.99,
                    "image": "https://...",
                    "rating": 4.7,
                    "orders": 5234,
                    "shipping_time": "7-15 days",
                    "url": url
                }
            }
        """

        # Validate URL
        if not url or 'aliexpress' not in url.lower():
            return {
                "success": False,
                "error": "Invalid AliExpress URL"
            }

        # Extract product ID from URL
        product_id = self._extract_product_id(url)

        if not product_id:
            return {
                "success": False,
                "error": "Could not extract product ID from URL"
            }

        # TODO: Implement actual scraping with requests + BeautifulSoup
        # For now, return error asking user to enter details manually

        return {
            "success": False,
            "error": "Auto-import coming soon! Please enter product details manually for now.",
            "message": "AliExpress OAuth approval pending. Manual entry required."
        }

    def _extract_product_id(self, url: str) -> Optional[str]:
        """Extract product ID from AliExpress URL."""
        # Try to find product ID in URL
        # Format: /item/1234567890.html or /item/1234567890
        match = re.search(r'/item/(\d+)', url)
        if match:
            return match.group(1)
        return None

    def validate_url(self, url: str) -> bool:
        """Check if URL is a valid AliExpress product URL."""
        if not url:
            return False
        return 'aliexpress' in url.lower() and '/item/' in url
