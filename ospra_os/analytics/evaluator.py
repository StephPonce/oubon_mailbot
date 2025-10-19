"""Evaluate candidate products for profitability and trend strength."""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class Evaluator:
    """Placeholder scoring engine for candidate products."""

    def score(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """Return a stubbed score for the provided product payload."""
        logger.info("Scoring product %s", product.get("id", "unknown"))
        return {"score": 0.8, "reason": "stub"}
