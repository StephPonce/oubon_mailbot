"""
Configuration File for Shopify Automation Scripts
==================================================

This file contains all constants, settings, and configuration
used across the Shopify automation package.

DO NOT hardcode secrets here - use environment variables.
"""

import os
from typing import Dict, List
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file in parent directory
# override=True ensures .env values override shell environment variables
load_dotenv(Path(__file__).parent.parent / ".env", override=True)

# ============================================
# PATHS & DIRECTORIES
# ============================================

BASE_DIR = Path(__file__).parent
LOG_DIR = BASE_DIR / "logs"
DATA_DIR = BASE_DIR / "data"

# Ensure directories exist
LOG_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

# ============================================
# SHOPIFY SETTINGS
# ============================================

class ShopifyConfig:
    """Shopify API configuration"""

    # API credentials (loaded from environment)
    STORE_DOMAIN = os.getenv('SHOPIFY_STORE_DOMAIN', 'rxxj7d-1i.myshopify.com')
    ACCESS_TOKEN = os.getenv('SHOPIFY_ADMIN_ACCESS_TOKEN') or os.getenv('SHOPIFY_API_TOKEN')
    API_VERSION = os.getenv('SHOPIFY_API_VERSION', '2024-10')

    # API endpoints
    BASE_URL = f"https://{STORE_DOMAIN}/admin/api/{API_VERSION}"

    # Rate limiting
    REQUESTS_PER_SECOND = 2  # Shopify allows 2 req/sec for REST API
    MAX_RETRIES = 3
    RETRY_BACKOFF_FACTOR = 2  # Exponential backoff: 1s, 2s, 4s

    # Timeouts
    REQUEST_TIMEOUT = 30  # seconds

    @classmethod
    def validate(cls) -> bool:
        """Validate that required Shopify credentials are set"""
        if not cls.ACCESS_TOKEN:
            raise ValueError("SHOPIFY_ADMIN_ACCESS_TOKEN not set in environment")
        if not cls.STORE_DOMAIN:
            raise ValueError("SHOPIFY_STORE_DOMAIN not set in environment")
        return True


# ============================================
# PRODUCT SETTINGS
# ============================================

class ProductConfig:
    """Product creation and pricing configuration"""

    # Pricing strategy
    MARKUP_MIN = 2.5  # Minimum markup multiplier (AliExpress cost * 2.5)
    MARKUP_MAX = 3.0  # Maximum markup multiplier (AliExpress cost * 3.0)
    MARKUP_DEFAULT = 2.7  # Default markup if not specified

    # Pricing psychology
    USE_PSYCHOLOGICAL_PRICING = True  # e.g., $29.99 instead of $30.00

    # Compare at price (for "sale" appearance)
    ADD_COMPARE_AT_PRICE = True
    COMPARE_AT_MARKUP = 1.3  # 30% higher than selling price

    # Product discovery
    DEFAULT_NICHES = [
        "smart lighting led strip",
        "wireless security camera",
        "robot vacuum cleaner",
        "portable blender bottle",
        "phone camera lens",
        "car phone holder mount",
        "gaming keyboard rgb",
        "wireless earbuds bluetooth"
    ]

    MAX_PRODUCTS_PER_NICHE = 5
    DEFAULT_PRODUCT_COUNT = 20

    # Product status
    DEFAULT_STATUS = "draft"  # "draft" or "active" - safer to start as draft

    # Inventory tracking
    TRACK_INVENTORY = False  # Dropshipping - don't track inventory
    CONTINUE_SELLING_OUT_OF_STOCK = True  # Always allow purchases

    # Product type
    DEFAULT_PRODUCT_TYPE = "Smart Home"

    # Vendor
    DEFAULT_VENDOR = "Oubon Shop"

    # Tags (always added to every product)
    DEFAULT_TAGS = [
        "smart-home",
        "tech-gadgets",
        "oubon",
        "dropship"
    ]


# ============================================
# IMAGE SETTINGS
# ============================================

class ImageConfig:
    """Image download and optimization configuration"""

    # Image dimensions
    MAX_WIDTH = 2048  # pixels
    MAX_HEIGHT = 2048  # pixels

    # Compression
    QUALITY = 85  # JPEG quality (1-100)
    OPTIMIZE = True  # Use Pillow optimization

    # File size
    MAX_FILE_SIZE_KB = 300  # Target max size in KB

    # Format
    OUTPUT_FORMAT = "JPEG"  # "JPEG" or "PNG" or "WEBP"
    WEBP_ENABLED = False  # Convert to WebP (better compression, not universally supported)

    # Alt text
    AUTO_GENERATE_ALT_TEXT = True
    ALT_TEXT_TEMPLATE = "{product_name} - {feature} - Oubon Shop"

    # Download
    DOWNLOAD_TIMEOUT = 30  # seconds
    MAX_IMAGES_PER_PRODUCT = 8
    MIN_IMAGES_PER_PRODUCT = 1

    # Placeholder
    USE_PLACEHOLDER_ON_FAILURE = True
    PLACEHOLDER_URL = "https://cdn.shopify.com/s/files/1/placeholder.jpg"


# ============================================
# COLLECTION SETTINGS
# ============================================

class CollectionConfig:
    """Collection creation configuration"""

    # Collection types
    SMART_COLLECTIONS = [
        {
            "title": "Smart Lighting",
            "handle": "smart-lighting",
            "rules": [{"column": "type", "relation": "equals", "condition": "Smart Lighting"}],
            "sort_order": "best-selling"
        },
        {
            "title": "Home Security",
            "handle": "home-security",
            "rules": [{"column": "type", "relation": "equals", "condition": "Home Security"}],
            "sort_order": "best-selling"
        },
        {
            "title": "Smart Speakers & Audio",
            "handle": "smart-audio",
            "rules": [{"column": "type", "relation": "equals", "condition": "Audio"}],
            "sort_order": "best-selling"
        },
        {
            "title": "Kitchen Tech",
            "handle": "kitchen-tech",
            "rules": [{"column": "type", "relation": "equals", "condition": "Kitchen"}],
            "sort_order": "best-selling"
        },
        {
            "title": "Voice Control Compatible",
            "handle": "voice-control",
            "rules": [
                {"column": "tag", "relation": "equals", "condition": "alexa"},
                {"column": "tag", "relation": "equals", "condition": "google-home"},
            ],
            "disjunctive": True,  # OR condition
            "sort_order": "best-selling"
        },
        {
            "title": "Under $25",
            "handle": "under-25",
            "rules": [{"column": "variant_price", "relation": "less_than", "condition": "25"}],
            "sort_order": "price-ascending"
        },
        {
            "title": "$25 - $50",
            "handle": "25-to-50",
            "rules": [
                {"column": "variant_price", "relation": "greater_than", "condition": "25"},
                {"column": "variant_price", "relation": "less_than", "condition": "50"}
            ],
            "sort_order": "price-ascending"
        },
        {
            "title": "Premium ($50+)",
            "handle": "premium",
            "rules": [{"column": "variant_price", "relation": "greater_than", "condition": "50"}],
            "sort_order": "price-descending"
        },
        {
            "title": "New Arrivals",
            "handle": "new-arrivals",
            "rules": [{"column": "created_at", "relation": "greater_than", "condition": "-30"}],  # Last 30 days
            "sort_order": "created-descending"
        },
        {
            "title": "Sale Items",
            "handle": "sale",
            "rules": [{"column": "variant_compare_at_price", "relation": "greater_than", "condition": "0"}],
            "sort_order": "best-selling"
        }
    ]

    # Description length
    MIN_DESCRIPTION_LENGTH = 300  # words
    MAX_DESCRIPTION_LENGTH = 500  # words

    # SEO
    META_TITLE_MAX_LENGTH = 60
    META_DESCRIPTION_MAX_LENGTH = 155


# ============================================
# SEO SETTINGS
# ============================================

class SEOConfig:
    """SEO optimization configuration"""

    # Meta title format
    META_TITLE_FORMAT = "{product_name} - {key_benefit} | Oubon Shop"
    COLLECTION_META_TITLE_FORMAT = "{collection_name} - Smart Home Tech | Oubon Shop"

    # Meta description format
    META_DESCRIPTION_FORMAT = "Shop {product_name} at Oubon Shop. {brief_description} Free shipping over $50. 30-day returns."

    # URL handles
    USE_CLEAN_HANDLES = True  # Remove special characters, use hyphens
    HANDLE_MAX_LENGTH = 70

    # Keywords
    TARGET_KEYWORD_DENSITY = 0.015  # 1.5% keyword density

    # Alt text
    IMAGE_ALT_REQUIRED = True


# ============================================
# CONTENT GENERATION
# ============================================

class ContentConfig:
    """AI content generation configuration"""

    # AI Provider (primary and fallback)
    PRIMARY_AI = "claude"  # "claude" or "openai"
    FALLBACK_AI = "openai"  # Used if primary fails

    # Claude settings
    CLAUDE_API_KEY = os.getenv('ANTHROPIC_API_KEY') or os.getenv('CLAUDE_API_KEY')
    CLAUDE_MODEL = "claude-3-5-sonnet-20240620"
    CLAUDE_MAX_TOKENS = 1000
    CLAUDE_TEMPERATURE = 0.7

    # OpenAI settings
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    OPENAI_MODEL = "gpt-4o-mini"
    OPENAI_MAX_TOKENS = 1000
    OPENAI_TEMPERATURE = 0.7

    # Content templates
    PRODUCT_DESCRIPTION_PROMPT = """Write a compelling product description for an e-commerce store.

Product: {product_name}
Niche: {niche}
Price: ${price}

Requirements:
1. Start with an emotional hook (1-2 sentences)
2. List 5-7 key features as bullet points
3. Include technical specifications
4. Add "What's Included" section
5. End with "Why Choose Oubon Shop" section mentioning fast shipping and quality guarantee

Tone: Professional, enthusiastic, benefit-focused
Length: 500-800 words
Format: HTML with <h3>, <ul>, <li>, <p> tags"""

    COLLECTION_DESCRIPTION_PROMPT = """Write an engaging collection description for an e-commerce category page.

Collection: {collection_name}
Products: {product_types}

Requirements:
1. Opening paragraph explaining the category (2-3 sentences)
2. Benefits of products in this category
3. How to choose the right product
4. Why buy from Oubon Shop

Tone: Helpful, expert, trustworthy
Length: 300-500 words
Keywords: Include "{primary_keyword}" naturally 3-4 times
Format: Plain text, well-structured paragraphs"""

    # Fallback templates (used if AI fails)
    FALLBACK_DESCRIPTION_TEMPLATE = """
<h3>Transform Your Space with {product_name}</h3>
<p>Discover the perfect blend of innovation and convenience with this premium smart home device. Designed for modern living, this product brings cutting-edge technology to your fingertips.</p>

<h3>Key Features</h3>
<ul>
<li>Easy installation and setup in minutes</li>
<li>Compatible with major smart home systems</li>
<li>Energy-efficient and eco-friendly design</li>
<li>Sleek, modern aesthetic fits any decor</li>
<li>Premium quality materials and construction</li>
</ul>

<h3>Why Choose Oubon Shop?</h3>
<p>At Oubon Shop, we're committed to bringing you the latest in smart home technology at unbeatable prices. Every product is carefully selected and backed by our 30-day money-back guarantee. Plus, enjoy free shipping on orders over $50!</p>

<p><strong>Order now and experience the future of smart living.</strong></p>
"""


# ============================================
# LOGGING CONFIGURATION
# ============================================

class LogConfig:
    """Logging configuration"""

    # Log levels
    CONSOLE_LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    FILE_LOG_LEVEL = "DEBUG"

    # Log format
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

    # Log files
    SETUP_PRODUCTS_LOG = LOG_DIR / "setup_products.log"
    CREATE_COLLECTIONS_LOG = LOG_DIR / "create_collections.log"
    GENERATE_CONTENT_LOG = LOG_DIR / "generate_content.log"
    DOWNLOAD_IMAGES_LOG = LOG_DIR / "download_images.log"
    VALIDATE_SETUP_LOG = LOG_DIR / "validate_setup.log"

    # Log rotation
    MAX_LOG_SIZE_MB = 10
    BACKUP_COUNT = 5  # Keep 5 old log files


# ============================================
# API CLIENT SETTINGS
# ============================================

class APIConfig:
    """External API configuration"""

    # Intelligence API (internal)
    INTELLIGENCE_API_URL = os.getenv('INTELLIGENCE_API_URL', 'http://localhost:8001/api/intelligence/discover')

    # AliExpress API (for product sourcing)
    ALIEXPRESS_API_KEY = os.getenv('ALIEXPRESS_APP_KEY')
    ALIEXPRESS_APP_SECRET = os.getenv('ALIEXPRESS_APP_SECRET')

    # Request timeouts
    API_TIMEOUT = 120  # seconds (for product discovery)
    IMAGE_DOWNLOAD_TIMEOUT = 30  # seconds


# ============================================
# PROGRESS & UI SETTINGS
# ============================================

class UIConfig:
    """User interface and progress display configuration"""

    # Progress bars
    SHOW_PROGRESS_BARS = True
    PROGRESS_BAR_FORMAT = "{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]"

    # Colors (for terminal output)
    COLOR_SUCCESS = "\033[92m"  # Green
    COLOR_ERROR = "\033[91m"    # Red
    COLOR_WARNING = "\033[93m"  # Yellow
    COLOR_INFO = "\033[94m"     # Blue
    COLOR_RESET = "\033[0m"     # Reset

    # Emojis (can disable for Windows compatibility)
    USE_EMOJIS = True
    EMOJI_SUCCESS = "✅"
    EMOJI_ERROR = "❌"
    EMOJI_WARNING = "⚠️"
    EMOJI_INFO = "ℹ️"
    EMOJI_PROGRESS = "⏳"

    @classmethod
    def success(cls, message: str) -> str:
        """Format success message"""
        emoji = cls.EMOJI_SUCCESS if cls.USE_EMOJIS else "[OK]"
        return f"{cls.COLOR_SUCCESS}{emoji} {message}{cls.COLOR_RESET}"

    @classmethod
    def error(cls, message: str) -> str:
        """Format error message"""
        emoji = cls.EMOJI_ERROR if cls.USE_EMOJIS else "[ERROR]"
        return f"{cls.COLOR_ERROR}{emoji} {message}{cls.COLOR_RESET}"

    @classmethod
    def warning(cls, message: str) -> str:
        """Format warning message"""
        emoji = cls.EMOJI_WARNING if cls.USE_EMOJIS else "[WARN]"
        return f"{cls.COLOR_WARNING}{emoji} {message}{cls.COLOR_RESET}"

    @classmethod
    def info(cls, message: str) -> str:
        """Format info message"""
        emoji = cls.EMOJI_INFO if cls.USE_EMOJIS else "[INFO]"
        return f"{cls.COLOR_INFO}{emoji} {message}{cls.COLOR_RESET}"


# ============================================
# VALIDATION CHECKS
# ============================================

class ValidationConfig:
    """Pre-launch validation configuration"""

    # Minimum requirements
    MIN_PRODUCTS_REQUIRED = 10
    MIN_COLLECTIONS_REQUIRED = 3
    MIN_IMAGES_PER_PRODUCT = 1

    # Product checks
    REQUIRE_PRODUCT_DESCRIPTIONS = True
    REQUIRE_PRODUCT_IMAGES = True
    REQUIRE_PRODUCT_PRICES = True
    REQUIRE_PRODUCT_META_FIELDS = True

    # Collection checks
    REQUIRE_COLLECTION_DESCRIPTIONS = True
    REQUIRE_COLLECTION_IMAGES = False  # Optional

    # Manual tasks (warnings, not errors)
    MANUAL_TASKS = [
        "Configure payment gateway (Shopify Payments)",
        "Set up shipping rates",
        "Configure tax settings",
        "Publish legal policies (Privacy, Refund, Terms)",
        "Install Judge.me app for reviews",
        "Install trust badge app",
        "Install email popup app (OptiMonk)",
        "Upload hero banner image",
        "Customize homepage sections",
        "Test checkout process with test card"
    ]


# ============================================
# HELPER FUNCTIONS
# ============================================

def get_shopify_headers() -> Dict[str, str]:
    """Get headers for Shopify API requests"""
    return {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": ShopifyConfig.ACCESS_TOKEN
    }


def psychological_price(price: float) -> float:
    """Convert price to psychological pricing (e.g., 29.99)"""
    if not ProductConfig.USE_PSYCHOLOGICAL_PRICING:
        return round(price, 2)

    # Round to nearest dollar, then subtract 0.01
    rounded = round(price)
    return rounded - 0.01


def calculate_selling_price(cost: float, markup: float = None) -> float:
    """Calculate selling price from cost with markup"""
    if markup is None:
        markup = ProductConfig.MARKUP_DEFAULT

    selling_price = cost * markup
    return psychological_price(selling_price)


def calculate_compare_at_price(selling_price: float) -> float:
    """Calculate compare-at price (for sale appearance)"""
    if not ProductConfig.ADD_COMPARE_AT_PRICE:
        return None

    compare_at = selling_price * ProductConfig.COMPARE_AT_MARKUP
    return psychological_price(compare_at)


def clean_handle(text: str) -> str:
    """Create clean URL handle from text"""
    import re

    # Convert to lowercase
    handle = text.lower()

    # Replace spaces with hyphens
    handle = handle.replace(' ', '-')

    # Remove special characters
    handle = re.sub(r'[^a-z0-9\-]', '', handle)

    # Remove multiple hyphens
    handle = re.sub(r'-+', '-', handle)

    # Trim hyphens from ends
    handle = handle.strip('-')

    # Limit length
    if len(handle) > SEOConfig.HANDLE_MAX_LENGTH:
        handle = handle[:SEOConfig.HANDLE_MAX_LENGTH].rstrip('-')

    return handle


# ============================================
# VALIDATE CONFIGURATION ON IMPORT
# ============================================

def validate_all():
    """Validate all configuration settings"""
    errors = []

    # Check Shopify credentials
    try:
        ShopifyConfig.validate()
    except ValueError as e:
        errors.append(str(e))

    # Check AI API keys (at least one required)
    if not ContentConfig.CLAUDE_API_KEY and not ContentConfig.OPENAI_API_KEY:
        errors.append("Neither ANTHROPIC_API_KEY nor OPENAI_API_KEY is set. AI content generation will fail.")

    # Check AliExpress credentials (warning only)
    if not APIConfig.ALIEXPRESS_API_KEY:
        print(UIConfig.warning("ALIEXPRESS_APP_KEY not set. Product sourcing may not work."))

    if errors:
        print(UIConfig.error("Configuration validation failed:"))
        for error in errors:
            print(f"  - {error}")
        raise ValueError("Invalid configuration. Check environment variables.")

    print(UIConfig.success("Configuration validated successfully"))


# Auto-validate on import (can be disabled for testing)
if os.getenv('SKIP_CONFIG_VALIDATION') != 'true':
    try:
        validate_all()
    except ValueError:
        print(UIConfig.warning("Continuing despite validation errors (for development)"))


# ============================================
# EXPORT ALL CONFIG CLASSES
# ============================================

__all__ = [
    'ShopifyConfig',
    'ProductConfig',
    'ImageConfig',
    'CollectionConfig',
    'SEOConfig',
    'ContentConfig',
    'LogConfig',
    'APIConfig',
    'UIConfig',
    'ValidationConfig',
    'get_shopify_headers',
    'psychological_price',
    'calculate_selling_price',
    'calculate_compare_at_price',
    'clean_handle',
    'validate_all'
]
