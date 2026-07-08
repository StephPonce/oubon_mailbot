"""
Product Research Engine

Automated product discovery, trend analysis, and supplier sourcing.
Integrates with multiple platforms to find winning products.
"""

# T121: scorer.py removed. It was imported only by the deleted v0 engines
# (discovery.py / pipeline.py) and re-exported here; nothing outside this package
# ever imported ProductScorer. routes.py — the live router registered in main.py —
# depends only on the connectors, not on any of the deleted modules.

# Make FastAPI routes import optional
try:
    from .routes import router
    __all__ = ["router"]
except ImportError:
    # FastAPI not installed - skip routes
    router = None
    __all__ = []
