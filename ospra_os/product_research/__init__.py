"""
Product Research Engine

Automated product discovery, trend analysis, and supplier sourcing.
Integrates with multiple platforms to find winning products.
"""

from .scorer import ProductScorer
from .routes import router

__all__ = ["ProductScorer", "router"]
