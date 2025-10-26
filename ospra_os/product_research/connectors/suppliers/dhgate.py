"""DHgate connector - alternative wholesale supplier."""

from typing import List, Optional
from ..base import BaseConnector, ProductCandidate


class DHgateConnector(BaseConnector):
    """
    DHgate integration (alternative to AliExpress).

    DHgate is a B2B marketplace with wholesale pricing.
    Often better prices than AliExpress for bulk orders.

    Setup:
    1. Register at seller.dhgate.com
    2. Get API credentials
    3. Set DHGATE_API_KEY in .env
    """

    @property
    def name(self) -> str:
        return "DHgate"

    @property
    def source_id(self) -> str:
        return "dhgate"

    async def search(self, query: str, **kwargs) -> List[ProductCandidate]:
        """Search DHgate products."""
        if not self.api_key:
            print("⚠️  DHGATE_API_KEY not configured")
            return []

        # TODO: Implement DHgate API integration
        # - Product search with wholesale pricing
        # - MOQ (Minimum Order Quantity) info
        # - Bulk discount tiers

        print(f"📦 DHgate API call: search('{query}')")
        return []

    async def get_trending(self, category: Optional[str] = None, limit: int = 10) -> List[ProductCandidate]:
        """Get trending DHgate products."""
        if not self.api_key:
            print("⚠️  DHGATE_API_KEY not configured")
            return []

        print(f"📦 DHgate API call: get_trending(category={category})")
        return []
