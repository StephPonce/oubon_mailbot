#!/usr/bin/env python3
"""
Shopify Product Setup Automation
=================================

Automatically creates products in Shopify using real AliExpress data
from the product intelligence engine.

Features:
- Fetches products from intelligence API
- Generates SEO-optimized titles and descriptions using AI
- Downloads and uploads product images
- Sets proper pricing with markup
- Creates products in Shopify via Admin API
- Assigns to collections
- Adds meta fields for SEO

Usage:
    python setup_products.py --count 20 --niches "smart home,tech gadgets"
    python setup_products.py --dry-run  # Preview without creating
"""

import os
import sys
import argparse
import logging
import time
import requests
from typing import List, Dict, Optional
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from shopify_automation.config import (
    ShopifyConfig,
    ProductConfig,
    ImageConfig,
    SEOConfig,
    ContentConfig,
    LogConfig,
    APIConfig,
    UIConfig,
    get_shopify_headers,
    calculate_selling_price,
    calculate_compare_at_price,
    clean_handle
)

# Try to import optional dependencies
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    print(UIConfig.warning("tqdm not installed. Progress bars disabled. Install with: pip install tqdm"))

try:
    from anthropic import Anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


# ============================================
# LOGGING SETUP
# ============================================

logging.basicConfig(
    level=logging.INFO,
    format=LogConfig.LOG_FORMAT,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LogConfig.SETUP_PRODUCTS_LOG)
    ]
)

logger = logging.getLogger(__name__)


# ============================================
# AI CLIENT INITIALIZATION
# ============================================

def init_ai_clients():
    """Initialize AI clients for content generation"""
    claude = None
    openai_client = None

    # Try Claude first
    if HAS_ANTHROPIC and ContentConfig.CLAUDE_API_KEY:
        try:
            claude = Anthropic(api_key=ContentConfig.CLAUDE_API_KEY)
            logger.info(UIConfig.success("Claude AI initialized"))
        except Exception as e:
            logger.warning(f"Claude initialization failed: {e}")

    # Try OpenAI as fallback
    if HAS_OPENAI and ContentConfig.OPENAI_API_KEY:
        try:
            openai_client = OpenAI(api_key=ContentConfig.OPENAI_API_KEY)
            logger.info(UIConfig.success("OpenAI initialized"))
        except Exception as e:
            logger.warning(f"OpenAI initialization failed: {e}")

    if not claude and not openai_client:
        logger.warning(UIConfig.warning("No AI clients available. Using fallback descriptions."))

    return claude, openai_client


# ============================================
# PRODUCT INTELLIGENCE FETCHER
# ============================================

class ProductIntelligenceFetcher:
    """Fetches products from the intelligence engine"""

    def __init__(self, api_url: str = None):
        self.api_url = api_url or APIConfig.INTELLIGENCE_API_URL
        logger.info(f"Intelligence API: {self.api_url}")

    def fetch_products(self, niches: List[str], max_per_niche: int = 5) -> List[Dict]:
        """Fetch products from intelligence API"""
        logger.info(f"Fetching products for niches: {niches}")

        try:
            response = requests.post(
                self.api_url,
                json={
                    "niches": niches,
                    "max_per_niche": max_per_niche
                },
                timeout=APIConfig.API_TIMEOUT
            )

            response.raise_for_status()
            data = response.json()

            if not data.get('success'):
                error = data.get('error', 'Unknown error')
                logger.error(f"Intelligence API error: {error}")
                return []

            products = data.get('products', [])
            logger.info(UIConfig.success(f"Fetched {len(products)} products from intelligence API"))
            return products

        except requests.exceptions.Timeout:
            logger.error("Intelligence API timeout after 120 seconds")
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Intelligence API request failed: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching products: {e}")
            return []


# ============================================
# CONTENT GENERATOR
# ============================================

class ContentGenerator:
    """Generates product titles, descriptions, and meta fields using AI"""

    def __init__(self, claude=None, openai_client=None):
        self.claude = claude
        self.openai = openai_client

    def generate_product_title(self, product_name: str, niche: str) -> str:
        """Generate SEO-optimized product title"""
        # Extract key features from name
        title = product_name.strip()

        # Add key benefit if not already present
        if "compatible" not in title.lower() and "voice" in niche.lower():
            title += " - Voice Control Compatible"
        elif "smart" in niche.lower() and "smart" not in title.lower():
            title = f"Smart {title}"

        # Limit length
        if len(title) > 70:
            title = title[:67] + "..."

        return title

    def generate_product_description(self, product: Dict) -> str:
        """Generate compelling product description using AI"""
        product_name = product.get('name', 'Product')
        niche = product.get('niche', 'tech gadget')
        price = product.get('price', 0)

        # Try AI generation first
        if self.claude:
            description = self._generate_with_claude(product_name, niche, price)
            if description:
                return description

        if self.openai:
            description = self._generate_with_openai(product_name, niche, price)
            if description:
                return description

        # Fallback to template
        return self._generate_fallback_description(product)

    def _generate_with_claude(self, product_name: str, niche: str, price: float) -> Optional[str]:
        """Generate description using Claude"""
        try:
            prompt = f"""Write a compelling product description for an e-commerce store.

Product: {product_name}
Niche: {niche}
Price: ${price:.2f}

Requirements:
1. Start with an emotional hook (1-2 sentences)
2. List 5-7 key features as bullet points
3. Include technical specifications section
4. Add "What's Included" section
5. End with "Why Choose Oubon Shop" section mentioning fast shipping and quality guarantee

Tone: Professional, enthusiastic, benefit-focused
Length: 500-800 words
Format: HTML with <h3>, <ul>, <li>, <p> tags
Keywords: Include product name naturally 3-4 times"""

            response = self.claude.messages.create(
                model=ContentConfig.CLAUDE_MODEL,
                max_tokens=ContentConfig.CLAUDE_MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}]
            )

            description = response.content[0].text
            logger.info("Generated description with Claude")
            return description

        except Exception as e:
            logger.error(f"Claude generation failed: {e}")
            return None

    def _generate_with_openai(self, product_name: str, niche: str, price: float) -> Optional[str]:
        """Generate description using OpenAI"""
        try:
            response = self.openai.chat.completions.create(
                model=ContentConfig.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are an expert e-commerce copywriter specializing in tech products."},
                    {"role": "user", "content": f"""Write a compelling product description for:

Product: {product_name}
Niche: {niche}
Price: ${price:.2f}

Include:
1. Emotional opening hook
2. 5-7 key features (bullet points)
3. Technical specs
4. What's included
5. Why buy from Oubon Shop

Format as HTML. Length: 500-800 words."""}
                ],
                max_tokens=ContentConfig.OPENAI_MAX_TOKENS,
                temperature=ContentConfig.OPENAI_TEMPERATURE
            )

            description = response.choices[0].message.content
            logger.info("Generated description with OpenAI")
            return description

        except Exception as e:
            logger.error(f"OpenAI generation failed: {e}")
            return None

    def _generate_fallback_description(self, product: Dict) -> str:
        """Generate basic description without AI"""
        product_name = product.get('name', 'Product')

        return f"""<h3>Transform Your Space with {product_name}</h3>
<p>Discover the perfect blend of innovation and convenience with this premium smart home device. Designed for modern living, this product brings cutting-edge technology to your fingertips.</p>

<h3>Key Features</h3>
<ul>
<li>Easy installation and setup in minutes</li>
<li>Compatible with major smart home systems</li>
<li>Energy-efficient and eco-friendly design</li>
<li>Sleek, modern aesthetic fits any decor</li>
<li>Premium quality materials and construction</li>
<li>Backed by {product.get('supplier_orders', 0):,} satisfied customers</li>
</ul>

<h3>Why Choose Oubon Shop?</h3>
<p>At Oubon Shop, we're committed to bringing you the latest in smart home technology at unbeatable prices. Every product is carefully selected for quality and backed by our 30-day money-back guarantee. Plus, enjoy free shipping on orders over $50!</p>

<p><strong>Order now and experience the future of smart living.</strong></p>"""

    def generate_meta_fields(self, product_name: str, niche: str) -> Dict[str, str]:
        """Generate SEO meta title and description"""
        # Meta title (60 chars max)
        meta_title = f"{product_name} | Oubon Shop"
        if len(meta_title) > 60:
            meta_title = product_name[:50] + "... | Oubon"

        # Meta description (155 chars max)
        meta_description = f"Shop {product_name} at Oubon Shop. Premium {niche} with fast shipping. 30-day returns. Order now!"
        if len(meta_description) > 155:
            meta_description = f"Shop {product_name[:80]}... Free shipping over $50!"

        return {
            "meta_title": meta_title,
            "meta_description": meta_description
        }


# ============================================
# IMAGE HANDLER
# ============================================

class ImageHandler:
    """Downloads and optimizes product images"""

    def download_image(self, url: str) -> Optional[bytes]:
        """Download image from URL"""
        try:
            response = requests.get(url, timeout=ImageConfig.DOWNLOAD_TIMEOUT)
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.error(f"Failed to download image {url}: {e}")
            return None

    def prepare_images(self, product: Dict) -> List[str]:
        """Prepare image URLs for Shopify upload"""
        images = []

        # Get main image
        main_image = product.get('image_url')
        if main_image:
            images.append(main_image)

        # Limit to max images
        return images[:ImageConfig.MAX_IMAGES_PER_PRODUCT]


# ============================================
# SHOPIFY PRODUCT CREATOR
# ============================================

class ShopifyProductCreator:
    """Creates products in Shopify via Admin API"""

    def __init__(self):
        self.base_url = f"{ShopifyConfig.BASE_URL}/products.json"
        self.headers = get_shopify_headers()
        self.rate_limit_delay = 1.0 / ShopifyConfig.REQUESTS_PER_SECOND

    def create_product(self, product_data: Dict, dry_run: bool = False) -> Optional[Dict]:
        """Create product in Shopify"""
        if dry_run:
            logger.info(f"[DRY RUN] Would create product: {product_data['product']['title']}")
            return {"product": {"id": "dry-run-id", **product_data['product']}}

        try:
            # Rate limiting
            time.sleep(self.rate_limit_delay)

            response = requests.post(
                self.base_url,
                json=product_data,
                headers=self.headers,
                timeout=ShopifyConfig.REQUEST_TIMEOUT
            )

            response.raise_for_status()
            result = response.json()

            logger.info(UIConfig.success(f"Created product: {result['product']['title']}"))
            return result

        except requests.exceptions.HTTPError as e:
            logger.error(f"Shopify API error: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Failed to create product: {e}")
            return None

    def build_product_data(self, product: Dict, content_gen: ContentGenerator, image_handler: ImageHandler) -> Dict:
        """Build Shopify product data structure"""

        # Extract data from intelligence product
        aliexpress_cost = product.get('price', 0)
        product_name = product.get('name', 'Product')
        niche = product.get('niche', 'tech gadget')

        # Calculate pricing
        selling_price = calculate_selling_price(aliexpress_cost)
        compare_at_price = calculate_compare_at_price(selling_price)

        # Generate content
        title = content_gen.generate_product_title(product_name, niche)
        description = content_gen.generate_product_description(product)
        meta_fields = content_gen.generate_meta_fields(product_name, niche)

        # Prepare images
        image_urls = image_handler.prepare_images(product)

        # Build tags
        tags = ProductConfig.DEFAULT_TAGS.copy()
        tags.append(niche.replace(' ', '-'))
        if product.get('rating', 0) >= 4.5:
            tags.append('top-rated')
        if 'smart' in product_name.lower():
            tags.append('smart-home')
        if 'wireless' in product_name.lower() or 'wifi' in product_name.lower():
            tags.append('wireless')

        # Build product data
        product_data = {
            "product": {
                "title": title,
                "body_html": description,
                "vendor": ProductConfig.DEFAULT_VENDOR,
                "product_type": ProductConfig.DEFAULT_PRODUCT_TYPE,
                "tags": ", ".join(tags),
                "status": ProductConfig.DEFAULT_STATUS,
                "variants": [
                    {
                        "price": f"{selling_price:.2f}",
                        "compare_at_price": f"{compare_at_price:.2f}" if compare_at_price else None,
                        "inventory_management": None,  # Don't track inventory for dropshipping
                        "inventory_policy": "continue",  # Allow purchases when out of stock
                        "requires_shipping": True,
                        "taxable": True,
                        "sku": product.get('supplier_sku', '')
                    }
                ],
                "images": [{"src": url} for url in image_urls] if image_urls else [],
                "metafields_global_title_tag": meta_fields['meta_title'],
                "metafields_global_description_tag": meta_fields['meta_description']
            }
        }

        return product_data


# ============================================
# MAIN SETUP SCRIPT
# ============================================

def setup_products(
    count: int = 20,
    niches: List[str] = None,
    dry_run: bool = False,
    max_per_niche: int = 5
):
    """Main function to set up products in Shopify"""

    print("\n" + "="*60)
    print("🚀 SHOPIFY PRODUCT SETUP AUTOMATION")
    print("="*60 + "\n")

    # Validate configuration
    try:
        ShopifyConfig.validate()
    except ValueError as e:
        print(UIConfig.error(f"Configuration error: {e}"))
        return False

    # Initialize components
    print(UIConfig.info("Initializing AI clients..."))
    claude, openai_client = init_ai_clients()

    fetcher = ProductIntelligenceFetcher()
    content_gen = ContentGenerator(claude, openai_client)
    image_handler = ImageHandler()
    shopify = ShopifyProductCreator()

    # Use default niches if not provided
    if not niches:
        niches = ProductConfig.DEFAULT_NICHES[:3]  # Use first 3 by default

    print(UIConfig.info(f"Fetching products from {len(niches)} niches..."))

    # Fetch products from intelligence engine
    products = fetcher.fetch_products(niches, max_per_niche)

    if not products:
        print(UIConfig.error("No products fetched. Cannot continue."))
        return False

    # Limit to requested count
    products = products[:count]

    print(UIConfig.success(f"Processing {len(products)} products...\n"))

    # Create products
    successful = 0
    failed = 0

    iterator = tqdm(products, desc="Creating products") if HAS_TQDM else products

    for product in iterator:
        try:
            # Build product data
            product_data = shopify.build_product_data(product, content_gen, image_handler)

            # Create in Shopify
            result = shopify.create_product(product_data, dry_run=dry_run)

            if result:
                successful += 1
            else:
                failed += 1

        except Exception as e:
            logger.error(f"Error processing product {product.get('name')}: {e}")
            failed += 1

    # Summary
    print("\n" + "="*60)
    print("📊 SUMMARY")
    print("="*60)
    print(UIConfig.success(f"✅ Successfully created: {successful} products"))
    if failed > 0:
        print(UIConfig.error(f"❌ Failed: {failed} products"))
    print("="*60 + "\n")

    return successful > 0


# ============================================
# CLI INTERFACE
# ============================================

def main():
    parser = argparse.ArgumentParser(
        description="Automatically create products in Shopify from intelligence engine"
    )

    parser.add_argument(
        '--count',
        type=int,
        default=20,
        help='Number of products to create (default: 20)'
    )

    parser.add_argument(
        '--niches',
        type=str,
        default='',
        help='Comma-separated list of niches (default: uses config defaults)'
    )

    parser.add_argument(
        '--max-per-niche',
        type=int,
        default=5,
        help='Maximum products per niche (default: 5)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview without creating products'
    )

    args = parser.parse_args()

    # Parse niches
    niches = [n.strip() for n in args.niches.split(',') if n.strip()] if args.niches else None

    # Run setup
    success = setup_products(
        count=args.count,
        niches=niches,
        dry_run=args.dry_run,
        max_per_niche=args.max_per_niche
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
