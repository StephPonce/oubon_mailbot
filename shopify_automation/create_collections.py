#!/usr/bin/env python3
"""
Shopify Collection Creation Automation
======================================

Automatically creates smart collections in Shopify with intelligent rules.

Features:
- Creates category-based collections (Smart Lighting, Home Security, etc.)
- Creates feature-based collections (Voice Control, Energy Efficient)
- Creates price-based collections (Under $25, $25-50, Premium)
- Creates promotional collections (Best Sellers, New Arrivals, Sale)
- Generates SEO-optimized descriptions using AI
- Sets up collection images and meta fields

Usage:
    python create_collections.py
    python create_collections.py --dry-run  # Preview without creating
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
    CollectionConfig,
    SEOConfig,
    ContentConfig,
    LogConfig,
    UIConfig,
    get_shopify_headers,
    clean_handle
)

# Try to import optional dependencies
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

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
        logging.FileHandler(LogConfig.CREATE_COLLECTIONS_LOG)
    ]
)

logger = logging.getLogger(__name__)


# ============================================
# COLLECTION CONTENT GENERATOR
# ============================================

class CollectionContentGenerator:
    """Generates collection descriptions using AI"""

    def __init__(self, claude=None, openai_client=None):
        self.claude = claude
        self.openai = openai_client

    def generate_description(self, collection_title: str, collection_type: str = "category") -> str:
        """Generate SEO-optimized collection description"""

        # Try AI generation first
        if self.claude:
            description = self._generate_with_claude(collection_title, collection_type)
            if description:
                return description

        if self.openai:
            description = self._generate_with_openai(collection_title, collection_type)
            if description:
                return description

        # Fallback to template
        return self._generate_fallback_description(collection_title, collection_type)

    def _generate_with_claude(self, title: str, collection_type: str) -> Optional[str]:
        """Generate description using Claude"""
        try:
            prompt = f"""Write an engaging collection description for an e-commerce category page.

Collection: {title}
Type: {collection_type}

Requirements:
1. Opening paragraph explaining the category (2-3 sentences)
2. Benefits of products in this category (3-4 bullet points)
3. How to choose the right product (1 paragraph)
4. Why buy from Oubon Shop (1 paragraph)

Tone: Helpful, expert, trustworthy
Length: 300-500 words
Keywords: Include "{title}" naturally 3-4 times
Format: HTML with <p>, <ul>, <li> tags"""

            response = self.claude.messages.create(
                model=ContentConfig.CLAUDE_MODEL,
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}]
            )

            description = response.content[0].text
            logger.info(f"Generated description for '{title}' with Claude")
            return description

        except Exception as e:
            logger.error(f"Claude generation failed: {e}")
            return None

    def _generate_with_openai(self, title: str, collection_type: str) -> Optional[str]:
        """Generate description using OpenAI"""
        try:
            response = self.openai.chat.completions.create(
                model=ContentConfig.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are an expert e-commerce copywriter specializing in tech products."},
                    {"role": "user", "content": f"""Write a collection description for: {title}

Include:
1. Category overview (2-3 sentences)
2. Product benefits (bullet points)
3. Buying guide
4. Why Oubon Shop

Length: 300-500 words. Format as HTML."""}
                ],
                max_tokens=800,
                temperature=0.7
            )

            description = response.choices[0].message.content
            logger.info(f"Generated description for '{title}' with OpenAI")
            return description

        except Exception as e:
            logger.error(f"OpenAI generation failed: {e}")
            return None

    def _generate_fallback_description(self, title: str, collection_type: str) -> str:
        """Generate basic description without AI"""

        descriptions = {
            "Smart Lighting": """<p>Illuminate your home with our collection of smart lighting solutions. From WiFi LED bulbs to voice-controlled light strips, transform any space with customizable colors, schedules, and voice commands.</p>

<p><strong>Why Choose Smart Lighting?</strong></p>
<ul>
<li>Energy savings up to 75% compared to traditional bulbs</li>
<li>Voice control with Alexa, Google Home, and Siri</li>
<li>Set schedules and automations for convenience</li>
<li>Create custom scenes for any mood or occasion</li>
</ul>

<p>At Oubon Shop, we carefully select only the highest-rated smart lighting products with proven reliability and customer satisfaction. Free shipping on orders over $50 and 30-day returns on all products.</p>""",

            "Home Security": """<p>Protect what matters most with our professional-grade home security solutions. Browse wireless cameras, smart locks, and security systems designed for easy installation and remote monitoring.</p>

<p><strong>Essential Security Features:</strong></p>
<ul>
<li>24/7 HD video recording with night vision</li>
<li>Instant alerts sent to your smartphone</li>
<li>Two-way audio communication</li>
<li>Cloud storage and local backup options</li>
</ul>

<p>Every security product at Oubon Shop is tested for reliability and backed by our satisfaction guarantee. Shop with confidence knowing you're getting quality home protection.</p>""",

            "default": f"""<p>Discover our curated selection of {title.lower()} at Oubon Shop. Each product is carefully selected for quality, reliability, and customer satisfaction.</p>

<p><strong>Why Shop This Collection?</strong></p>
<ul>
<li>Hand-picked products with verified reviews</li>
<li>Easy installation and setup</li>
<li>Compatible with major smart home platforms</li>
<li>Free shipping on orders over $50</li>
</ul>

<p>At Oubon Shop, we're committed to bringing you the latest in smart home technology at unbeatable prices. Every product is backed by our 30-day money-back guarantee.</p>"""
        }

        return descriptions.get(title, descriptions["default"])

    def generate_meta_fields(self, collection_title: str) -> Dict[str, str]:
        """Generate SEO meta title and description"""

        # Meta title (60 chars max)
        meta_title = f"{collection_title} - Smart Home Tech | Oubon Shop"
        if len(meta_title) > 60:
            meta_title = f"{collection_title[:40]}... | Oubon Shop"

        # Meta description (155 chars max)
        meta_description = f"Shop {collection_title} at Oubon Shop. Premium smart home products with free shipping over $50. 30-day returns. Order now!"
        if len(meta_description) > 155:
            meta_description = f"Shop {collection_title[:80]}... Free shipping over $50. 30-day returns."

        return {
            "meta_title": meta_title,
            "meta_description": meta_description
        }


# ============================================
# SHOPIFY COLLECTION CREATOR
# ============================================

class ShopifyCollectionCreator:
    """Creates collections in Shopify via Admin API"""

    def __init__(self):
        self.smart_collections_url = f"{ShopifyConfig.BASE_URL}/smart_collections.json"
        self.custom_collections_url = f"{ShopifyConfig.BASE_URL}/custom_collections.json"
        self.headers = get_shopify_headers()
        self.rate_limit_delay = 1.0 / ShopifyConfig.REQUESTS_PER_SECOND

    def create_smart_collection(self, collection_data: Dict, dry_run: bool = False) -> Optional[Dict]:
        """Create smart collection in Shopify"""
        if dry_run:
            logger.info(f"[DRY RUN] Would create collection: {collection_data['smart_collection']['title']}")
            return {"smart_collection": {"id": "dry-run-id", **collection_data['smart_collection']}}

        try:
            # Rate limiting
            time.sleep(self.rate_limit_delay)

            response = requests.post(
                self.smart_collections_url,
                json=collection_data,
                headers=self.headers,
                timeout=ShopifyConfig.REQUEST_TIMEOUT
            )

            response.raise_for_status()
            result = response.json()

            logger.info(UIConfig.success(f"Created collection: {result['smart_collection']['title']}"))
            return result

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 422:
                # Collection might already exist
                logger.warning(f"Collection might already exist: {collection_data['smart_collection']['title']}")
            else:
                logger.error(f"Shopify API error: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Failed to create collection: {e}")
            return None

    def build_collection_data(self, collection_config: Dict, content_gen: CollectionContentGenerator) -> Dict:
        """Build Shopify collection data structure"""

        title = collection_config['title']
        handle = collection_config.get('handle', clean_handle(title))
        rules = collection_config.get('rules', [])
        sort_order = collection_config.get('sort_order', 'best-selling')
        disjunctive = collection_config.get('disjunctive', False)

        # Generate content
        description = content_gen.generate_description(title)
        meta_fields = content_gen.generate_meta_fields(title)

        # Build rules
        collection_rules = []
        for rule in rules:
            collection_rules.append({
                "column": rule['column'],
                "relation": rule['relation'],
                "condition": rule['condition']
            })

        # Build collection data
        collection_data = {
            "smart_collection": {
                "title": title,
                "handle": handle,
                "body_html": description,
                "sort_order": sort_order,
                "rules": collection_rules,
                "disjunctive": disjunctive,  # True = OR, False = AND
                "metafields_global_title_tag": meta_fields['meta_title'],
                "metafields_global_description_tag": meta_fields['meta_description']
            }
        }

        return collection_data


# ============================================
# MAIN CREATION SCRIPT
# ============================================

def create_collections(dry_run: bool = False):
    """Main function to create collections in Shopify"""

    print("\n" + "="*60)
    print("📁 SHOPIFY COLLECTION CREATION AUTOMATION")
    print("="*60 + "\n")

    # Validate configuration
    try:
        ShopifyConfig.validate()
    except ValueError as e:
        print(UIConfig.error(f"Configuration error: {e}"))
        return False

    # Initialize AI clients
    print(UIConfig.info("Initializing AI clients..."))
    claude = None
    openai_client = None

    if HAS_ANTHROPIC and ContentConfig.CLAUDE_API_KEY:
        try:
            claude = Anthropic(api_key=ContentConfig.CLAUDE_API_KEY)
            logger.info(UIConfig.success("Claude AI initialized"))
        except Exception as e:
            logger.warning(f"Claude initialization failed: {e}")

    if HAS_OPENAI and ContentConfig.OPENAI_API_KEY:
        try:
            openai_client = OpenAI(api_key=ContentConfig.OPENAI_API_KEY)
            logger.info(UIConfig.success("OpenAI initialized"))
        except Exception as e:
            logger.warning(f"OpenAI initialization failed: {e}")

    # Initialize components
    content_gen = CollectionContentGenerator(claude, openai_client)
    shopify = ShopifyCollectionCreator()

    # Get collection configurations
    collections = CollectionConfig.SMART_COLLECTIONS

    print(UIConfig.info(f"Creating {len(collections)} smart collections...\n"))

    # Create collections
    successful = 0
    failed = 0

    iterator = tqdm(collections, desc="Creating collections") if HAS_TQDM else collections

    for collection_config in iterator:
        try:
            # Build collection data
            collection_data = shopify.build_collection_data(collection_config, content_gen)

            # Create in Shopify
            result = shopify.create_smart_collection(collection_data, dry_run=dry_run)

            if result:
                successful += 1
            else:
                failed += 1

        except Exception as e:
            logger.error(f"Error creating collection {collection_config.get('title')}: {e}")
            failed += 1

    # Summary
    print("\n" + "="*60)
    print("📊 SUMMARY")
    print("="*60)
    print(UIConfig.success(f"✅ Successfully created: {successful} collections"))
    if failed > 0:
        print(UIConfig.warning(f"⚠️  Failed/Skipped: {failed} collections (may already exist)"))
    print("="*60 + "\n")

    print(UIConfig.info("Collection types created:"))
    print("  • Category-based (Smart Lighting, Home Security, etc.)")
    print("  • Feature-based (Voice Control, Energy Efficient)")
    print("  • Price-based (Under $25, $25-$50, Premium)")
    print("  • Promotional (New Arrivals, Sale Items)")
    print()

    return successful > 0


# ============================================
# CLI INTERFACE
# ============================================

def main():
    parser = argparse.ArgumentParser(
        description="Automatically create smart collections in Shopify"
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview without creating collections'
    )

    args = parser.parse_args()

    # Run creation
    success = create_collections(dry_run=args.dry_run)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
