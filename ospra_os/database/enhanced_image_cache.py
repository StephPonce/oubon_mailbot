"""
Enhanced Image Cache Database Model
====================================
Caches Stability AI enhanced images to avoid duplicate API costs.

Maps original_image_url -> enhanced_image_url with product association.

Tables:
- enhanced_image_cache: Individual image URL mappings
- product_enhanced_images: Product-level aggregated enhanced images
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Index
from datetime import datetime
from typing import Optional, Dict, List
import hashlib
import json

# Import the shared Base from the main database module
from ospra_os.database.base import Base


class EnhancedImageCache(Base):
    """
    Cache enhanced images from Stability AI to avoid re-processing.

    Key features:
    - Maps original image URL to enhanced image URL
    - Associates with product_id for easy lookup
    - Stores enhancement type (background_removal, etc.)
    - Never expires (enhanced images are permanent)
    """
    __tablename__ = "enhanced_image_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Cache key (hash of original URL for consistent lookups)
    original_url_hash = Column(String(64), nullable=False, index=True)
    original_url = Column(Text, nullable=False)

    # Result
    enhanced_url = Column(Text, nullable=False)

    # Product association (optional - for bulk lookups)
    product_id = Column(String(255), index=True)

    # Enhancement type for future flexibility
    enhancement_type = Column(String(50), default="background_removal")

    # Metadata
    niche = Column(String(100))
    cost_usd = Column(String(20), default="0.06")  # Store cost for tracking

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<EnhancedImage(product={self.product_id}, type={self.enhancement_type})>"

    @staticmethod
    def normalize_url(url: str) -> str:
        """Normalize image URL for consistent hashing."""
        if not url:
            return url
        from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
        try:
            parsed = urlparse(url)
            hostname = parsed.netloc.lower()
            query_params = parse_qs(parsed.query)
            # Remove cache-busting params
            params_to_remove = ['_', 't', 'timestamp', 'v', 'version', 'cb', 'cache', 'nocache', 'rand', 'random']
            filtered_params = {k: v for k, v in query_params.items() if k.lower() not in params_to_remove}
            return urlunparse((
                'https', hostname, parsed.path, parsed.params,
                urlencode(filtered_params, doseq=True) if filtered_params else '', ''
            ))
        except:
            return url

    @staticmethod
    def hash_url(url: str) -> str:
        """Generate consistent hash for URL lookups (with normalization)."""
        normalized = EnhancedImageCache.normalize_url(url)
        return hashlib.sha256(normalized.encode()).hexdigest()

    def to_dict(self) -> Dict:
        """Convert to dictionary for API response."""
        return {
            "original_url": self.original_url,
            "enhanced_url": self.enhanced_url,
            "product_id": self.product_id,
            "enhancement_type": self.enhancement_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ProductEnhancedImages(Base):
    """
    Quick lookup table: product_id -> all enhanced images.

    Stores JSON array of enhanced image URLs for a product.
    Used for fast product-level queries without joining.
    """
    __tablename__ = "product_enhanced_images"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Product identifier (from discovery/CJ/AliExpress)
    product_id = Column(String(255), unique=True, nullable=False, index=True)

    # Primary enhanced image (first/main)
    primary_enhanced_url = Column(Text)

    # All enhanced images (JSON array)
    enhanced_urls_json = Column(Text)  # JSON array of URLs

    # Original images that were enhanced (JSON array)
    original_urls_json = Column(Text)  # JSON array for reference

    # Count
    image_count = Column(Integer, default=0)

    # Total cost for this product
    total_cost_usd = Column(String(20), default="0.00")

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<ProductEnhanced(product={self.product_id}, count={self.image_count})>"

    def get_enhanced_urls(self) -> List[str]:
        """Parse enhanced URLs from JSON."""
        if not self.enhanced_urls_json:
            return []
        import json
        try:
            return json.loads(self.enhanced_urls_json)
        except:
            return []

    def set_enhanced_urls(self, urls: List[str]):
        """Store enhanced URLs as JSON."""
        import json
        self.enhanced_urls_json = json.dumps(urls)
        self.image_count = len(urls)
        if urls:
            self.primary_enhanced_url = urls[0]

    def get_original_urls(self) -> List[str]:
        """Parse original URLs from JSON."""
        if not self.original_urls_json:
            return []
        import json
        try:
            return json.loads(self.original_urls_json)
        except:
            return []

    def set_original_urls(self, urls: List[str]):
        """Store original URLs as JSON."""
        import json
        self.original_urls_json = json.dumps(urls)

    def to_dict(self) -> Dict:
        """Convert to dictionary for API response."""
        return {
            "product_id": self.product_id,
            "primary_enhanced_url": self.primary_enhanced_url,
            "enhanced_urls": self.get_enhanced_urls(),
            "original_urls": self.get_original_urls(),
            "image_count": self.image_count,
            "total_cost_usd": self.total_cost_usd,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# Create indexes for common queries
Index('idx_enhanced_original_hash', EnhancedImageCache.original_url_hash)
Index('idx_enhanced_product', EnhancedImageCache.product_id)
Index('idx_product_enhanced_id', ProductEnhancedImages.product_id)
