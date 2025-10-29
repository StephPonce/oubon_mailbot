#!/usr/bin/env python3
"""
One-Click Shopify Store Setup for Oubon Shop
Complete automation: theme setup, product import, policies, and more
"""

import asyncio
import os
import sys
import logging
from pathlib import Path
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from shopify_setup.auto_configure_dawn import DawnThemeConfigurator
from ospra_os.intelligence.product_intelligence import ProductIntelligenceEngine
from ospra_os.media.automated_image_pipeline import AutomatedImagePipeline

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ShopifyStoreSetup:
    """
    Complete Shopify store setup automation

    Features:
    1. Configure Dawn theme with branding
    2. Import winning products
    3. Set up collections
    4. Create store policies
    5. Configure payment/shipping
    6. Optimize for SEO
    """

    def __init__(self):
        # Load environment
        load_dotenv()

        self.shop_url = os.getenv('SHOPIFY_SHOP_URL')
        self.access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
        self.api_version = '2024-01'

        if not self.shop_url or not self.access_token:
            raise ValueError(
                "Missing Shopify credentials. Set SHOPIFY_SHOP_URL and SHOPIFY_ACCESS_TOKEN"
            )

        # Initialize Shopify session
        self._init_shopify()

        # Initialize modules
        self.theme_config = DawnThemeConfigurator(self.shop_url, self.access_token)
        self.product_intelligence = ProductIntelligenceEngine()
        self.image_pipeline = AutomatedImagePipeline()

    def _init_shopify(self):
        """Initialize Shopify API"""
        try:
            import shopify
        except ImportError:
            raise ImportError("ShopifyAPI not installed. Run: pip install ShopifyAPI")

        session = shopify.Session(self.shop_url, self.api_version, self.access_token)
        shopify.ShopifyResource.activate_session(session)
        logger.info(f"✅ Connected to Shopify: {self.shop_url}")

    async def setup_complete_store(
        self,
        import_products: bool = True,
        product_count: int = 20,
        setup_policies: bool = True,
        configure_theme: bool = True
    ) -> Dict:
        """
        Complete one-click store setup

        Args:
            import_products: Import products from intelligence engine
            product_count: Number of products to import
            setup_policies: Create store policies
            configure_theme: Configure Dawn theme

        Returns:
            Setup results summary
        """
        logger.info("🚀 Starting complete Shopify store setup...")

        results = {
            'success': False,
            'steps_completed': [],
            'errors': [],
            'products_imported': 0,
            'collections_created': 0,
            'theme_configured': False
        }

        try:
            # Step 1: Configure Theme
            if configure_theme:
                logger.info("\n📝 Step 1/5: Configuring Dawn theme...")
                theme_result = await self.theme_config.configure_theme()

                if theme_result['success']:
                    results['steps_completed'].append('theme_configuration')
                    results['theme_configured'] = True
                    logger.info(f"✅ Theme configured: {len(theme_result['steps_completed'])} sub-steps")
                else:
                    results['errors'].append(f"Theme config failed: {theme_result.get('errors')}")

            # Step 2: Create Collections
            logger.info("\n📚 Step 2/5: Creating collections...")
            collections_result = await self._create_collections()

            if collections_result['success']:
                results['steps_completed'].append('collections')
                results['collections_created'] = collections_result['count']
                logger.info(f"✅ Created {collections_result['count']} collections")
            else:
                results['errors'].append(f"Collection creation failed: {collections_result.get('error')}")

            # Step 3: Import Winning Products
            if import_products:
                logger.info(f"\n🎯 Step 3/5: Importing {product_count} winning products...")
                import_result = await self._import_winning_products(product_count)

                if import_result['success']:
                    results['steps_completed'].append('product_import')
                    results['products_imported'] = import_result['count']
                    logger.info(f"✅ Imported {import_result['count']} products")
                else:
                    results['errors'].append(f"Product import failed: {import_result.get('error')}")

            # Step 4: Set up Store Policies
            if setup_policies:
                logger.info("\n📋 Step 4/5: Creating store policies...")
                policy_result = await self._setup_policies()

                if policy_result['success']:
                    results['steps_completed'].append('policies')
                    logger.info(f"✅ Created store policies")
                else:
                    results['errors'].append(f"Policy setup failed: {policy_result.get('error')}")

            # Step 5: Configure Store Settings
            logger.info("\n⚙️ Step 5/5: Configuring store settings...")
            settings_result = await self._configure_store_settings()

            if settings_result['success']:
                results['steps_completed'].append('store_settings')
                logger.info("✅ Store settings configured")
            else:
                results['errors'].append(f"Settings failed: {settings_result.get('error')}")

            # Final summary
            results['success'] = len(results['steps_completed']) >= 3

            logger.info("\n" + "="*60)
            logger.info("🎉 STORE SETUP COMPLETE!")
            logger.info("="*60)
            logger.info(f"✅ Steps completed: {len(results['steps_completed'])}/5")
            logger.info(f"📦 Products imported: {results['products_imported']}")
            logger.info(f"📚 Collections created: {results['collections_created']}")
            logger.info(f"🎨 Theme configured: {'Yes' if results['theme_configured'] else 'No'}")

            if results['errors']:
                logger.warning(f"\n⚠️ Errors encountered: {len(results['errors'])}")
                for error in results['errors']:
                    logger.warning(f"  - {error}")

            logger.info(f"\n🌐 Your store: https://{self.shop_url}")
            logger.info("="*60)

        except Exception as e:
            logger.error(f"Setup error: {e}")
            results['errors'].append(str(e))

        return results

    async def _create_collections(self) -> Dict:
        """Create product collections"""
        try:
            collections_to_create = [
                {
                    'title': 'Trending Products',
                    'handle': 'trending',
                    'body_html': 'The hottest products everyone is buying right now'
                },
                {
                    'title': 'New Arrivals',
                    'handle': 'new',
                    'body_html': 'Fresh picks just added to our store'
                },
                {
                    'title': 'Best Sellers',
                    'handle': 'best-sellers',
                    'body_html': 'Our most popular products'
                },
                {
                    'title': 'Smart Home',
                    'handle': 'smart-home',
                    'body_html': 'Upgrade your home with smart technology'
                },
                {
                    'title': 'Tech Gadgets',
                    'handle': 'tech-gadgets',
                    'body_html': 'Cool gadgets and innovative tech products'
                },
                {
                    'title': 'Home & Kitchen',
                    'handle': 'home-kitchen',
                    'body_html': 'Essential items for your home and kitchen'
                }
            ]

            created = 0
            for collection_data in collections_to_create:
                try:
                    # Check if exists
                    existing = shopify.CustomCollection.find(
                        handle=collection_data['handle']
                    )

                    if not existing:
                        collection = shopify.CustomCollection()
                        collection.title = collection_data['title']
                        collection.handle = collection_data['handle']
                        collection.body_html = collection_data['body_html']
                        collection.published = True

                        if collection.save():
                            created += 1
                            logger.info(f"  ✅ Created collection: {collection_data['title']}")
                    else:
                        logger.info(f"  ℹ️  Collection exists: {collection_data['title']}")

                except Exception as e:
                    logger.warning(f"  ⚠️ Failed to create {collection_data['title']}: {e}")

            return {'success': True, 'count': created}

        except Exception as e:
            logger.error(f"Collection creation error: {e}")
            return {'success': False, 'error': str(e)}

    async def _import_winning_products(self, count: int) -> Dict:
        """Discover and import winning products"""
        try:
            # Discover products
            logger.info("  🔍 Discovering winning products...")
            products = await self.product_intelligence.discover_winning_products(
                niches=['smart home', 'tech gadgets', 'home & kitchen'],
                max_per_niche=count // 3 + 1
            )

            # Take top products
            products = sorted(products, key=lambda x: x['score'], reverse=True)[:count]

            logger.info(f"  📊 Found {len(products)} products to import")

            # Import each product
            imported = 0
            for i, product_data in enumerate(products, 1):
                try:
                    logger.info(f"  📦 Importing {i}/{len(products)}: {product_data['name'][:50]}...")

                    # Create Shopify product
                    product = shopify.Product()

                    # Basic info
                    product.title = product_data['name']
                    product.body_html = self._generate_product_description(product_data)
                    product.vendor = 'Oubon Shop'
                    product.product_type = self._categorize_product(product_data['name'])

                    # Pricing
                    ali_data = product_data.get('aliexpress_match', {})
                    amazon_data = product_data.get('amazon_data', {})

                    cost_price = ali_data.get('price', 0)
                    sell_price = amazon_data.get('price', cost_price * 2.5)

                    # Create variant
                    variant = shopify.Variant()
                    variant.price = str(round(sell_price, 2))
                    variant.compare_at_price = str(round(sell_price * 1.3, 2))  # Show discount
                    variant.inventory_management = 'shopify'
                    variant.inventory_quantity = 100
                    product.variants = [variant]

                    # Images
                    display_data = product_data.get('display_data', {})
                    image_url = display_data.get('image_url')

                    if image_url:
                        image = shopify.Image()
                        image.src = image_url
                        product.images = [image]

                    # Tags
                    tags = ['trending', 'new']
                    if product_data.get('priority') == 'HIGH':
                        tags.append('best-seller')

                    product.tags = ', '.join(tags)

                    # Status
                    product.status = 'active'

                    # Save
                    if product.save():
                        imported += 1
                        logger.info(f"    ✅ Imported: {product.title[:50]}")

                        # Add to collections
                        await self._add_to_collections(product.id, tags)
                    else:
                        logger.warning(f"    ⚠️ Failed to save: {product.errors.full_messages()}")

                except Exception as e:
                    logger.warning(f"    ⚠️ Product import error: {e}")
                    continue

            return {'success': True, 'count': imported}

        except Exception as e:
            logger.error(f"Product import error: {e}")
            return {'success': False, 'error': str(e)}

    def _generate_product_description(self, product_data: Dict) -> str:
        """Generate compelling product description"""
        ai_explanation = product_data.get('ai_explanation', '')
        display_data = product_data.get('display_data', {})

        description = f"""
<div class="product-description">
  <h2>Why You'll Love This</h2>
  <p>{ai_explanation if ai_explanation else 'A trending product with excellent reviews and proven sales performance.'}</p>

  <h3>Key Features</h3>
  <ul>
    <li>⭐ Rated {display_data.get('supplier_rating', 4.5)}/5 by thousands of customers</li>
    <li>🚚 Fast & Free Shipping</li>
    <li>✅ 30-Day Money-Back Guarantee</li>
    <li>💯 Authentic & Quality Guaranteed</li>
  </ul>

  <h3>Product Details</h3>
  <p>This is one of our trending products, carefully selected for quality and value.</p>
</div>
"""
        return description

    def _categorize_product(self, product_name: str) -> str:
        """Categorize product based on name"""
        name_lower = product_name.lower()

        categories = {
            'Smart Home': ['smart', 'wifi', 'alexa', 'google home', 'iot', 'automated'],
            'Tech Gadgets': ['gadget', 'tech', 'electronic', 'device', 'bluetooth'],
            'Home & Kitchen': ['kitchen', 'home', 'cooking', 'storage', 'organizer'],
            'Lighting': ['light', 'led', 'lamp', 'bulb'],
            'Security': ['camera', 'security', 'doorbell', 'lock'],
            'Wellness': ['health', 'fitness', 'wellness', 'air purifier']
        }

        for category, keywords in categories.items():
            if any(keyword in name_lower for keyword in keywords):
                return category

        return 'General'

    async def _add_to_collections(self, product_id: int, tags: List[str]):
        """Add product to appropriate collections"""
        try:
            # Map tags to collection handles
            tag_to_collection = {
                'trending': 'trending',
                'new': 'new',
                'best-seller': 'best-sellers'
            }

            for tag in tags:
                if tag in tag_to_collection:
                    handle = tag_to_collection[tag]

                    # Find collection
                    collections = shopify.CustomCollection.find(handle=handle)
                    if collections:
                        collection = collections[0]

                        # Add product to collection
                        collect = shopify.Collect()
                        collect.collection_id = collection.id
                        collect.product_id = product_id
                        collect.save()

        except Exception as e:
            logger.debug(f"Collection assignment error: {e}")

    async def _setup_policies(self) -> Dict:
        """Create store policies"""
        try:
            policies = {
                'refund_policy': self._get_refund_policy(),
                'privacy_policy': self._get_privacy_policy(),
                'terms_of_service': self._get_terms_of_service(),
                'shipping_policy': self._get_shipping_policy()
            }

            # Update shop policies
            shop = shopify.Shop.current()

            for policy_type, policy_content in policies.items():
                setattr(shop, policy_type, policy_content)

            shop.save()

            logger.info("  ✅ Store policies created")
            return {'success': True}

        except Exception as e:
            logger.error(f"Policy setup error: {e}")
            return {'success': False, 'error': str(e)}

    def _get_refund_policy(self) -> str:
        return """
<h2>30-Day Money-Back Guarantee</h2>
<p>We stand behind our products 100%. If you're not completely satisfied with your purchase, return it within 30 days for a full refund.</p>

<h3>Return Process:</h3>
<ol>
  <li>Contact our support team</li>
  <li>Ship the item back (unused & in original packaging)</li>
  <li>Receive your full refund within 5-7 business days</li>
</ol>
"""

    def _get_privacy_policy(self) -> str:
        return """
<h2>Privacy Policy</h2>
<p>We respect your privacy and protect your personal information. We only collect data necessary to process your orders and improve your shopping experience.</p>

<h3>Information We Collect:</h3>
<ul>
  <li>Name, email, and shipping address</li>
  <li>Payment information (securely processed)</li>
  <li>Order history</li>
</ul>

<p>We never sell your data to third parties.</p>
"""

    def _get_terms_of_service(self) -> str:
        return """
<h2>Terms of Service</h2>
<p>By using our store, you agree to these terms. Please read carefully.</p>

<h3>Product Information:</h3>
<p>We strive for accuracy in product descriptions and images. Actual products may vary slightly.</p>

<h3>Pricing:</h3>
<p>All prices are in USD and subject to change without notice.</p>
"""

    def _get_shipping_policy(self) -> str:
        return """
<h2>Shipping Policy</h2>

<h3>Free Shipping</h3>
<p>Free standard shipping on orders over $50!</p>

<h3>Delivery Times:</h3>
<ul>
  <li>Standard Shipping: 7-14 business days</li>
  <li>Express Shipping: 3-5 business days</li>
</ul>

<h3>Tracking:</h3>
<p>You'll receive tracking information via email once your order ships.</p>
"""

    async def _configure_store_settings(self) -> Dict:
        """Configure general store settings"""
        try:
            shop = shopify.Shop.current()

            # Update basic settings
            shop.email = os.getenv('STORE_EMAIL', 'support@oubonshop.com')
            shop.customer_email = os.getenv('STORE_EMAIL', 'support@oubonshop.com')
            shop.phone = os.getenv('STORE_PHONE', '+1-800-OUBON-SHOP')

            shop.save()

            logger.info("  ✅ Store settings configured")
            return {'success': True}

        except Exception as e:
            logger.error(f"Settings configuration error: {e}")
            return {'success': False, 'error': str(e)}


async def main():
    """Run complete store setup"""
    print("""
╔════════════════════════════════════════════════════════════╗
║                                                            ║
║      🎉  OUBON SHOP - SHOPIFY STORE SETUP  🎉              ║
║                                                            ║
║  One-click setup for your complete Shopify store          ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
    """)

    try:
        setup = ShopifyStoreSetup()

        # Run complete setup
        results = await setup.setup_complete_store(
            import_products=True,
            product_count=20,
            setup_policies=True,
            configure_theme=True
        )

        if results['success']:
            print("\n✅ SUCCESS! Your Shopify store is ready to launch!")
            print(f"🌐 Visit: https://{setup.shop_url}")
        else:
            print("\n⚠️ Setup completed with some errors. Check logs above.")

        return results

    except Exception as e:
        logger.error(f"Fatal setup error: {e}")
        print(f"\n❌ Setup failed: {e}")
        return {'success': False, 'error': str(e)}


if __name__ == '__main__':
    asyncio.run(main())
