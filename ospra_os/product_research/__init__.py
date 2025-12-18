"""
Product Research Engine

Automated product discovery, trend analysis, and supplier sourcing.
Integrates with multiple platforms to find winning products.
"""

from .scorer import ProductScorer

# Make FastAPI routes import optional
try:
    from .routes import router
    __all__ = ["ProductScorer", "router"]
except ImportError:
    # FastAPI not installed - skip routes
    router = None
    __all__ = ["ProductScorer"]
