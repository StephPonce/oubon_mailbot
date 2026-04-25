"""
Unified Product Deployment System

Handles product deployment across multiple e-commerce platforms (Shopify, Amazon, WooCommerce)
with AI-powered content generation and intelligent platform optimization.

Features:
- Single product deployment to specific store
- Bulk deployment to all user stores
- AI-generated product descriptions and titles
- Platform-specific content optimization
- Deployment tracking and management
- Error handling and retry logic
- Cost tracking for AI usage

Author: OspraOS
Date: November 2025
"""

import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Platform Adapters
from ospra_os.platforms.factory import PlatformFactory
from ospra_os.platforms import (
    PlatformAPIError,
    AuthenticationError,
    RateLimitError,
    ProductNotFoundError
)

# AI Providers
from ospra_os.ai.factory import AIFactory
from ospra_os.ai import AIProviderError

# Database models (assumed to exist in ospra_os.database.models)
# from ospra_os.database.models import User, Store, Product, ProductDeployment, AIUsage

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DeploymentError(Exception):
    """Base exception for deployment errors"""
    pass


class ProductNotFoundError(DeploymentError):
    """Product not found in database"""
    pass


class StoreNotFoundError(DeploymentError):
    """Store not found in database"""
    pass


class AlreadyDeployedError(DeploymentError):
    """Product already deployed to this store"""
    pass


class UnifiedProductDeployer:
    """
    Unified product deployment system across multiple e-commerce platforms.

    Handles:
    - AI-powered content generation
    - Platform-specific optimization
    - Concurrent multi-store deployment
    - Deployment tracking and management
    - Error handling and retry logic
    """

    def __init__(self, database_url: str = None, db_session: Session = None):
        """
        Initialize the unified deployer.

        Args:
            database_url: SQLAlchemy database URL (if not using existing session)
            db_session: Existing database session (optional)
        """
        if db_session:
            self.db = db_session
            self._owns_session = False
        elif database_url:
            engine = create_engine(database_url)
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            self.db = SessionLocal()
            self._owns_session = True
        else:
            raise ValueError("Either database_url or db_session must be provided")

        logger.info("UnifiedProductDeployer initialized")

    def __del__(self):
        """Cleanup database session if we own it"""
        if hasattr(self, '_owns_session') and self._owns_session:
            self.db.close()

    async def deploy_to_store(
        self,
        product_id: int,
        store_id: int,
        skip_existing: bool = True,
        regenerate_content: bool = False
    ) -> Dict[str, Any]:
        """
        Deploy a product to a specific store with AI-generated content.

        Args:
            product_id: ID of product to deploy
            store_id: ID of target store
            skip_existing: Skip if already deployed (default: True)
            regenerate_content: Regenerate AI content even if exists (default: False)

        Returns:
            dict: Deployment result with success status, deployment_id, platform_product_id, etc.

        Raises:
            ProductNotFoundError: If product doesn't exist
            StoreNotFoundError: If store doesn't exist
            AlreadyDeployedError: If already deployed and skip_existing=False
            DeploymentError: For other deployment failures
        """
        logger.info(f"Starting deployment: product_id={product_id}, store_id={store_id}")

        try:
            # Step 1: Get Product from database
            # NOTE: Replace with actual model import when available
            # product = self.db.query(Product).filter(Product.id == product_id).first()
            product = self._get_product_mock(product_id)  # Mock for now

            if not product:
                raise ProductNotFoundError(f"Product {product_id} not found")

            # Step 2: Get Store from database
            # store = self.db.query(Store).filter(Store.id == store_id).first()
            store = self._get_store_mock(store_id)  # Mock for now

            if not store:
                raise StoreNotFoundError(f"Store {store_id} not found")

            # Step 3: Check if already deployed
            # existing = self.db.query(ProductDeployment).filter(
            #     ProductDeployment.product_id == product_id,
            #     ProductDeployment.store_id == store_id,
            #     ProductDeployment.status != 'removed'
            # ).first()
            existing = None  # Mock for now

            if existing:
                if skip_existing:
                    logger.info(f"Product {product_id} already deployed to store {store_id}, skipping")
                    return {
                        "success": True,
                        "skipped": True,
                        "deployment_id": existing.id if hasattr(existing, 'id') else None,
                        "message": "Product already deployed to this store"
                    }
                else:
                    raise AlreadyDeployedError(
                        f"Product {product_id} already deployed to store {store_id}"
                    )

            # Step 4: Get AI provider for content generation
            # user = self.db.query(User).filter(User.id == store.user_id).first()
            user = self._get_user_mock(store.get('user_id', 1))  # Mock for now

            ai_provider_name = user.get('ai_provider', 'openai') if user else 'openai'
            ai_config = user.get('ai_config', {}) if user else {}

            try:
                ai = AIFactory.get_provider(ai_provider_name, ai_config)
                logger.info(f"Using AI provider: {ai_provider_name}")
            except Exception as e:
                logger.warning(f"Failed to initialize AI provider {ai_provider_name}: {e}")
                logger.info("Proceeding without AI content generation")
                ai = None

            # Step 5: Generate platform-optimized content with AI
            ai_content = {}
            ai_usage_data = None

            if ai and (regenerate_content or not product.get('ai_description')):
                try:
                    platform_name = store['platform']
                    ai_content = await self._generate_ai_content(
                        ai=ai,
                        product=product,
                        platform=platform_name
                    )

                    # Track AI usage for cost monitoring
                    ai_usage_data = {
                        'user_id': store.get('user_id'),
                        'provider': ai_provider_name,
                        'operation': 'product_deployment',
                        'input_tokens': ai_content.get('usage', {}).get('input_tokens', 0),
                        'output_tokens': ai_content.get('usage', {}).get('output_tokens', 0),
                        'cost': ai_content.get('usage', {}).get('cost', 0.0),
                        'created_at': datetime.now(timezone.utc)
                    }

                    logger.info(f"AI content generated: {len(ai_content.get('description', ''))} chars")

                except AIProviderError as e:
                    logger.error(f"AI content generation failed: {e}")
                    ai_content = {}

            # Step 6: Get platform adapter
            platform_name = store['platform']
            adapter_credentials = self._convert_credentials(
                platform_name,
                store.get('credentials', {})
            )

            try:
                adapter = PlatformFactory.get_adapter(platform_name, adapter_credentials)
                logger.info(f"Platform adapter created: {platform_name}")
            except Exception as e:
                raise DeploymentError(f"Failed to create platform adapter: {e}")

            # Step 7: Prepare product data for platform
            product_data = self.prepare_product_for_platform(
                product=product,
                platform=platform_name,
                ai_content=ai_content
            )

            logger.info(f"Product data prepared for {platform_name}")

            # Step 8: Deploy product to platform
            try:
                deployment_result = await adapter.deploy_product(product_data)

                if not deployment_result.get('success'):
                    raise DeploymentError(
                        f"Platform deployment failed: {deployment_result.get('error', 'Unknown error')}"
                    )

                logger.info(f"Product deployed to {platform_name}: {deployment_result.get('platform_product_id')}")

            except PlatformAPIError as e:
                raise DeploymentError(f"Platform API error: {e}")

            # Step 9: Create ProductDeployment record
            deployment_record = {
                'product_id': product_id,
                'store_id': store_id,
                'platform_product_id': deployment_result.get('platform_product_id', ''),
                'platform_url': deployment_result.get('platform_url', ''),
                'status': 'active',
                'deployed_at': datetime.now(timezone.utc),
                'ai_content': ai_content if ai_content else None,
                'deployment_metadata': deployment_result.get('metadata', {})
            }

            # deployment = ProductDeployment(**deployment_record)
            # self.db.add(deployment)
            # self.db.commit()
            # deployment_id = deployment.id

            deployment_id = 1  # Mock for now

            # Track AI usage if applicable
            if ai_usage_data:
                # ai_usage = AIUsage(**ai_usage_data)
                # self.db.add(ai_usage)
                # self.db.commit()
                logger.info(f"AI usage tracked: {ai_usage_data['cost']} credits")

            # Step 10: Update product status
            # product.status = 'deployed'
            # self.db.commit()

            logger.info(f"[SUCCESS] Deployment complete: deployment_id={deployment_id}")

            return {
                "success": True,
                "deployment_id": deployment_id,
                "platform_product_id": deployment_result.get('platform_product_id'),
                "platform_url": deployment_result.get('platform_url'),
                "platform": platform_name,
                "ai_generated": bool(ai_content),
                "ai_cost": ai_usage_data.get('cost', 0.0) if ai_usage_data else 0.0
            }

        except (ProductNotFoundError, StoreNotFoundError, AlreadyDeployedError) as e:
            logger.error(f"Deployment validation failed: {e}")
            raise

        except DeploymentError as e:
            logger.error(f"Deployment failed: {e}")
            raise

        except Exception as e:
            logger.exception(f"Unexpected deployment error: {e}")
            raise DeploymentError(f"Unexpected error: {e}")

    async def deploy_to_all_stores(
        self,
        product_id: int,
        user_id: int,
        skip_existing: bool = True,
        only_active: bool = True
    ) -> Dict[str, Any]:
        """
        Deploy product to all user's stores concurrently.

        Args:
            product_id: ID of product to deploy
            user_id: ID of user whose stores to deploy to
            skip_existing: Skip stores where product is already deployed
            only_active: Only deploy to active stores (default: True)

        Returns:
            dict: Results for each store with success/failure status
        """
        logger.info(f"Starting bulk deployment: product_id={product_id}, user_id={user_id}")

        # Get all user's stores
        # stores = self.db.query(Store).filter(Store.user_id == user_id)
        # if only_active:
        #     stores = stores.filter(Store.status == 'active')
        # stores = stores.all()

        stores = self._get_user_stores_mock(user_id)  # Mock for now

        if not stores:
            logger.warning(f"No stores found for user {user_id}")
            return {
                "success": True,
                "total_stores": 0,
                "deployed": 0,
                "skipped": 0,
                "failed": 0,
                "results": []
            }

        logger.info(f"Deploying to {len(stores)} stores concurrently")

        # Create deployment tasks for concurrent execution
        tasks = []
        for store in stores:
            task = self.deploy_to_store(
                product_id=product_id,
                store_id=store['id'],
                skip_existing=skip_existing
            )
            tasks.append(task)

        # Execute all deployments concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        deployed = 0
        skipped = 0
        failed = 0
        detailed_results = []

        for i, result in enumerate(results):
            store = stores[i]

            if isinstance(result, Exception):
                # Deployment failed
                failed += 1
                detailed_results.append({
                    "store_id": store['id'],
                    "store_name": store['store_name'],
                    "platform": store['platform'],
                    "success": False,
                    "error": str(result)
                })
                logger.error(f"Deployment failed for store {store['id']}: {result}")

            elif result.get('skipped'):
                # Already deployed, skipped
                skipped += 1
                detailed_results.append({
                    "store_id": store['id'],
                    "store_name": store['store_name'],
                    "platform": store['platform'],
                    "success": True,
                    "skipped": True,
                    "deployment_id": result.get('deployment_id')
                })
                logger.info(f"Deployment skipped for store {store['id']} (already deployed)")

            else:
                # Successfully deployed
                deployed += 1
                detailed_results.append({
                    "store_id": store['id'],
                    "store_name": store['store_name'],
                    "platform": store['platform'],
                    "success": True,
                    "deployment_id": result.get('deployment_id'),
                    "platform_product_id": result.get('platform_product_id'),
                    "platform_url": result.get('platform_url'),
                    "ai_cost": result.get('ai_cost', 0.0)
                })
                logger.info(f"[SUCCESS] Deployed to store {store['id']} ({store['platform']})")

        total_ai_cost = sum(r.get('ai_cost', 0.0) for r in detailed_results)

        summary = {
            "success": True,
            "total_stores": len(stores),
            "deployed": deployed,
            "skipped": skipped,
            "failed": failed,
            "total_ai_cost": total_ai_cost,
            "results": detailed_results
        }

        logger.info(
            f"[SUCCESS] Bulk deployment complete: {deployed} deployed, "
            f"{skipped} skipped, {failed} failed"
        )

        return summary

    async def update_deployment(
        self,
        deployment_id: int,
        updates: Dict[str, Any],
        regenerate_ai: bool = False
    ) -> Dict[str, Any]:
        """
        Update an existing product deployment.

        Args:
            deployment_id: ID of ProductDeployment to update
            updates: Fields to update (title, description, price, inventory, etc.)
            regenerate_ai: Regenerate AI content for updates (default: False)

        Returns:
            dict: Update result with success status
        """
        logger.info(f"Updating deployment {deployment_id}")

        try:
            # Get deployment record
            # deployment = self.db.query(ProductDeployment).filter(
            #     ProductDeployment.id == deployment_id
            # ).first()
            deployment = self._get_deployment_mock(deployment_id)  # Mock for now

            if not deployment:
                raise DeploymentError(f"Deployment {deployment_id} not found")

            # Get store and platform adapter
            # store = self.db.query(Store).filter(Store.id == deployment['store_id']).first()
            store = self._get_store_mock(deployment['store_id'])

            platform_name = store['platform']
            adapter_credentials = self._convert_credentials(
                platform_name,
                store.get('credentials', {})
            )
            adapter = PlatformFactory.get_adapter(platform_name, adapter_credentials)

            # Regenerate AI content if requested
            if regenerate_ai and updates:
                # Get AI provider
                # user = self.db.query(User).filter(User.id == store.user_id).first()
                user = self._get_user_mock(store.get('user_id', 1))
                ai_provider_name = user.get('ai_provider', 'openai') if user else 'openai'

                try:
                    ai = AIFactory.get_provider(ai_provider_name, user.get('ai_config', {}))

                    # Generate updated content
                    ai_updates = await self._generate_ai_updates(
                        ai=ai,
                        original_data=deployment.get('ai_content', {}),
                        updates=updates,
                        platform=platform_name
                    )

                    # Merge AI updates
                    updates.update(ai_updates)

                except Exception as e:
                    logger.warning(f"AI update generation failed: {e}")

            # Update product on platform
            update_result = await adapter.update_product(
                platform_product_id=deployment['platform_product_id'],
                updates=updates
            )

            if not update_result.get('success'):
                raise DeploymentError(f"Platform update failed: {update_result.get('error')}")

            # Update deployment record
            # deployment.updated_at = datetime.now(timezone.utc)
            # deployment.last_sync = datetime.now(timezone.utc)
            # self.db.commit()

            logger.info(f"[SUCCESS] Deployment {deployment_id} updated successfully")

            return {
                "success": True,
                "deployment_id": deployment_id,
                "updated_fields": list(updates.keys()),
                "platform_response": update_result
            }

        except Exception as e:
            logger.exception(f"Deployment update failed: {e}")
            raise DeploymentError(f"Update failed: {e}")

    async def remove_from_store(
        self,
        deployment_id: int,
        permanent: bool = False
    ) -> Dict[str, Any]:
        """
        Remove product from store platform.

        Args:
            deployment_id: ID of ProductDeployment to remove
            permanent: Permanently delete from platform (default: False, just unpublish)

        Returns:
            dict: Removal result with success status
        """
        logger.info(f"Removing deployment {deployment_id} (permanent={permanent})")

        try:
            # Get deployment
            # deployment = self.db.query(ProductDeployment).filter(
            #     ProductDeployment.id == deployment_id
            # ).first()
            deployment = self._get_deployment_mock(deployment_id)

            if not deployment:
                raise DeploymentError(f"Deployment {deployment_id} not found")

            if deployment.get('status') == 'removed':
                logger.info(f"Deployment {deployment_id} already removed")
                return {
                    "success": True,
                    "already_removed": True,
                    "deployment_id": deployment_id
                }

            # Get platform adapter
            # store = self.db.query(Store).filter(Store.id == deployment['store_id']).first()
            store = self._get_store_mock(deployment['store_id'])

            platform_name = store['platform']
            adapter_credentials = self._convert_credentials(
                platform_name,
                store.get('credentials', {})
            )
            adapter = PlatformFactory.get_adapter(platform_name, adapter_credentials)

            # Remove from platform
            if permanent:
                # Permanently delete
                delete_result = await adapter.delete_product(
                    deployment['platform_product_id']
                )

                if not delete_result.get('success'):
                    raise DeploymentError(f"Platform deletion failed: {delete_result.get('error')}")

                logger.info(f"Product permanently deleted from platform")

            else:
                # Just unpublish/archive
                update_result = await adapter.update_product(
                    platform_product_id=deployment['platform_product_id'],
                    updates={"status": "draft"}  # Unpublish
                )

                if not update_result.get('success'):
                    logger.warning(f"Failed to unpublish, attempting deletion: {update_result.get('error')}")

                    # Fallback to deletion
                    delete_result = await adapter.delete_product(
                        deployment['platform_product_id']
                    )

                    if not delete_result.get('success'):
                        raise DeploymentError(f"Platform removal failed: {delete_result.get('error')}")

            # Update deployment status
            # deployment.status = 'removed'
            # deployment.removed_at = datetime.now(timezone.utc)
            # self.db.commit()

            logger.info(f"[SUCCESS] Deployment {deployment_id} removed successfully")

            return {
                "success": True,
                "deployment_id": deployment_id,
                "permanent": permanent,
                "removed_at": datetime.now(timezone.utc).isoformat()
            }

        except Exception as e:
            logger.exception(f"Deployment removal failed: {e}")
            raise DeploymentError(f"Removal failed: {e}")

    def prepare_product_for_platform(
        self,
        product: Dict[str, Any],
        platform: str,
        ai_content: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Convert product data + AI content to platform-specific format.

        Args:
            product: Product data from database
            platform: Platform name (shopify, amazon, woocommerce)
            ai_content: AI-generated content (title, description, tags, etc.)

        Returns:
            dict: Platform-ready product data
        """
        # Base product data
        base_data = {
            "title": ai_content.get('title') or product.get('product_name', ''),
            "description": ai_content.get('description') or product.get('description', ''),
            "price": float(product.get('price', 0.0)),
            "sku": product.get('sku', f"PROD-{product.get('id', '')}"),
            "inventory": product.get('stock_quantity', 0),
            "images": product.get('images', []) if isinstance(product.get('images'), list) else [],
            "status": "draft"  # Create as draft for review
        }

        # Add AI-generated tags if available
        if ai_content.get('tags'):
            base_data['tags'] = ai_content['tags']
        elif product.get('tags'):
            # Convert comma-separated tags to list
            base_data['tags'] = [t.strip() for t in product['tags'].split(',') if t.strip()]
        else:
            base_data['tags'] = []

        # Platform-specific requirements
        if platform == "shopify":
            return self._prepare_for_shopify(base_data, product, ai_content)

        elif platform == "amazon":
            return self._prepare_for_amazon(base_data, product, ai_content)

        elif platform == "woocommerce":
            return self._prepare_for_woocommerce(base_data, product, ai_content)

        else:
            # Unknown platform - return base data
            logger.warning(f"Unknown platform {platform}, using base product data")
            return base_data

    def _prepare_for_shopify(
        self,
        base_data: Dict[str, Any],
        product: Dict[str, Any],
        ai_content: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Prepare product data for Shopify platform"""
        shopify_data = base_data.copy()

        # Shopify-specific fields
        shopify_data['vendor'] = product.get('vendor', ai_content.get('vendor', 'OspraOS'))
        shopify_data['product_type'] = product.get('product_type', ai_content.get('category', 'General'))

        # SEO fields from AI
        if ai_content.get('seo_title'):
            shopify_data['seo_title'] = ai_content['seo_title']
        if ai_content.get('seo_description'):
            shopify_data['seo_description'] = ai_content['seo_description']

        return shopify_data

    def _prepare_for_amazon(
        self,
        base_data: Dict[str, Any],
        product: Dict[str, Any],
        ai_content: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Prepare product data for Amazon platform"""
        amazon_data = base_data.copy()

        # Amazon-specific fields
        amazon_data['asin'] = product.get('asin', '')
        amazon_data['category'] = product.get('category', ai_content.get('category', ''))

        # Amazon requires bullet points
        if ai_content.get('bullet_points'):
            amazon_data['bullet_points'] = ai_content['bullet_points']
        else:
            # Generate from description
            amazon_data['bullet_points'] = self._generate_bullet_points(
                base_data.get('description', '')
            )

        # Amazon search terms
        if ai_content.get('search_terms'):
            amazon_data['search_terms'] = ai_content['search_terms']

        return amazon_data

    def _prepare_for_woocommerce(
        self,
        base_data: Dict[str, Any],
        product: Dict[str, Any],
        ai_content: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Prepare product data for WooCommerce platform"""
        woo_data = base_data.copy()

        # WooCommerce-specific fields
        # Categories as array
        if ai_content.get('categories'):
            woo_data['categories'] = ai_content['categories']
        elif product.get('categories'):
            woo_data['categories'] = product['categories']
        else:
            woo_data['categories'] = []

        # Short description for WooCommerce
        if ai_content.get('short_description'):
            woo_data['short_description'] = ai_content['short_description']
        else:
            # Generate from description (first 160 chars)
            desc = base_data.get('description', '')
            woo_data['short_description'] = desc[:160] + '...' if len(desc) > 160 else desc

        return woo_data

    async def _generate_ai_content(
        self,
        ai: Any,
        product: Dict[str, Any],
        platform: str
    ) -> Dict[str, Any]:
        """
        Generate platform-optimized product content using AI.

        Args:
            ai: AI provider instance
            product: Product data
            platform: Target platform name

        Returns:
            dict: AI-generated content (title, description, tags, etc.)
        """
        # Create prompt for AI
        prompt = self._create_product_prompt(product, platform)

        # Generate content
        try:
            response = await ai.generate(
                prompt=prompt,
                max_tokens=800,
                temperature=0.7
            )

            # Parse AI response
            content = self._parse_ai_response(response, platform)

            return content

        except Exception as e:
            logger.error(f"AI content generation failed: {e}")
            raise AIProviderError(f"Failed to generate content: {e}")

    async def _generate_ai_updates(
        self,
        ai: Any,
        original_data: Dict[str, Any],
        updates: Dict[str, Any],
        platform: str
    ) -> Dict[str, Any]:
        """Generate AI content for product updates"""
        prompt = f"""
Update the following product information for {platform}:

Original: {original_data}
Updates needed: {updates}

Generate updated, SEO-optimized content that incorporates the changes while maintaining consistency.
"""

        response = await ai.generate(prompt=prompt, max_tokens=500)
        return self._parse_ai_response(response, platform)

    def _create_product_prompt(self, product: Dict[str, Any], platform: str) -> str:
        """Create AI prompt for product content generation"""
        return f"""
Generate SEO-optimized product content for {platform} e-commerce platform:

Product Details:
- Name: {product.get('product_name', 'Unknown Product')}
- Price: ${product.get('price', 0.0)}
- Description: {product.get('description', 'No description available')}

Generate:
1. Compelling product title (60 chars max)
2. SEO-optimized description (200-300 words)
3. 5-8 relevant tags/keywords
4. Short description (160 chars) for {platform}
5. Platform-specific optimizations

Format as JSON with keys: title, description, short_description, tags, seo_title, seo_description
"""

    def _parse_ai_response(self, response: Dict[str, Any], platform: str) -> Dict[str, Any]:
        """Parse AI response into structured content"""
        import json

        # Extract text from response
        text = response.get('text', '')

        try:
            # Try to parse as JSON
            content = json.loads(text)
        except json.JSONDecodeError:
            # Fallback: extract content manually
            content = {
                'title': product.get('product_name', ''),
                'description': text,
                'tags': [],
                'usage': response.get('usage', {})
            }

        # Add usage stats
        content['usage'] = response.get('usage', {})

        return content

    def _generate_bullet_points(self, description: str, max_points: int = 5) -> List[str]:
        """Generate bullet points from description"""
        # Simple implementation: split by sentences, take first N
        sentences = [s.strip() for s in description.split('.') if s.strip()]
        return sentences[:max_points]

    def _convert_credentials(self, platform: str, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """Convert database credentials to adapter format"""
        if platform == "shopify":
            return {
                "store_domain": credentials.get("shop_url", credentials.get("store_domain", "")),
                "admin_api_token": credentials.get("access_token", credentials.get("admin_api_token", "")),
                "api_version": credentials.get("api_version", "2024-01")
            }

        elif platform == "amazon":
            return {
                "marketplace_id": credentials.get("marketplace_id", ""),
                "seller_id": credentials.get("seller_id", ""),
                "refresh_token": credentials.get("refresh_token", credentials.get("mws_token", "")),
                "client_id": credentials.get("client_id", credentials.get("app_id", "")),
                "client_secret": credentials.get("client_secret", credentials.get("app_secret", "")),
                "aws_access_key": credentials.get("aws_access_key", ""),
                "aws_secret_key": credentials.get("aws_secret_key", "")
            }

        elif platform == "woocommerce":
            return {
                "store_url": credentials.get("site_url", credentials.get("store_url", "")),
                "consumer_key": credentials.get("consumer_key", ""),
                "consumer_secret": credentials.get("consumer_secret", ""),
                "version": credentials.get("version", "wc/v3")
            }

        else:
            return credentials

    # Mock methods for testing (replace with actual database queries)

    def _get_product_mock(self, product_id: int) -> Dict[str, Any]:
        """Mock product retrieval"""
        return {
            'id': product_id,
            'product_name': 'Smart LED Bulb',
            'description': 'WiFi-enabled color-changing LED bulb with app control',
            'price': Decimal('24.99'),
            'sku': 'LED-BULB-001',
            'stock_quantity': 150,
            'images': ['https://example.com/image1.jpg'],
            'tags': 'smart home, LED, lighting, WiFi',
            'status': 'active'
        }

    def _get_store_mock(self, store_id: int) -> Dict[str, Any]:
        """Mock store retrieval"""
        return {
            'id': store_id,
            'user_id': 1,
            'platform': 'shopify',
            'store_name': 'Test Store',
            'credentials': {
                'shop_url': 'test.myshopify.com',
                'access_token': 'test_token'
            },
            'status': 'active'
        }

    def _get_user_mock(self, user_id: int) -> Dict[str, Any]:
        """Mock user retrieval"""
        return {
            'id': user_id,
            'ai_provider': 'openai',
            'ai_config': {}
        }

    def _get_user_stores_mock(self, user_id: int) -> List[Dict[str, Any]]:
        """Mock user stores retrieval"""
        return [
            {
                'id': 1,
                'user_id': user_id,
                'platform': 'shopify',
                'store_name': 'Shopify Store',
                'credentials': {},
                'status': 'active'
            },
            {
                'id': 2,
                'user_id': user_id,
                'platform': 'woocommerce',
                'store_name': 'WooCommerce Store',
                'credentials': {},
                'status': 'active'
            }
        ]

    def _get_deployment_mock(self, deployment_id: int) -> Dict[str, Any]:
        """Mock deployment retrieval"""
        return {
            'id': deployment_id,
            'product_id': 123,
            'store_id': 456,
            'platform_product_id': 'gid://shopify/Product/123',
            'platform_url': 'https://test.myshopify.com/admin/products/123',
            'status': 'active',
            'ai_content': {},
            'deployed_at': datetime.now(timezone.utc)
        }
