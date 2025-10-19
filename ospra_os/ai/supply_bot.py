"""Supplier + restock automation via AliExpress/CJ APIs."""

import logging

logger = logging.getLogger(__name__)


class SupplyBot:
    """Stub restock automation agent."""

    async def restock(self, product_id: str) -> None:
        """Trigger a restock workflow for the given product identifier."""
        logger.info("Restocking %s", product_id)
