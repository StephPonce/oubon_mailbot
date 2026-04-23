"""
Ospra Intelligence - Unified Product Deployer

Complete end-to-end product deployment pipeline:
1. AI content generation (Claude)
2. Image enhancement (DALL-E 3 + rembg)
3. Shopify deployment
4. SEO optimization
5. Pricing optimization

Orchestrates all services into a single deployment flow.
"""

import os
import time
import logging
import asyncio
from typing import Dict, List, Optional
from datetime import datetime

from ospra_os.services.product_content_generator import ProductContentGenerator
from ospra_os.services.image_processor import ProductImageProcessor
from ospra_os.services.image_storage import ImageStorage
from ospra_os.platforms.shopify import ShopifyAdapter

logger = logging.getLogger(__name__)


class DeploymentOptions:
    """Configuration for product deployment"""

    def __init__(
        self,
        enhance_images: bool = True,
        generate_content: bool = True,
        generate_seo: bool = True,
        generate_pricing: bool = True,
        publish_immediately: bool = False,
        add_branding: bool = True,
        target_margin: float = 0.4,
        max_images: int = 5
    ):
        self.enhance_images = enhance_images
        self.generate_content = generate_content
        self.generate_seo = generate_seo
        self.generate_pricing = generate_pricing
        self.publish_immediately = publish_immediately
        self.add_branding = add_branding
        self.target_margin = target_margin
        self.max_images = max_images


class ProductDeployer:
    """
    Unified product deployment orchestrator

    Coordinates AI content generation, image enhancement, and Shopify deployment
    into a single streamlined pipeline.
    """

    def __init__(
        self,
        shopify_store: Optional[str] = None,
        shopify_token: Optional[str] = None
    ):
        """
        Initialize product deployer

        Args:
            shopify_store: Shopify store name (or from env)
            shopify_token: Shopify API token (or from env)
        """
        # Initialize services
        logger.info("[START] Initializing ProductDeployer...")

        # Content generation
        try:
            self.content_generator = ProductContentGenerator()
            logger.info("   [SUCCESS] Content generator ready (Claude Sonnet 4.5)")
        except Exception as e:
            logger.warning(f"   [WARNING]  Content generator unavailable: {e}")
            self.content_generator = None

        # Image enhancement
        try:
            self.image_processor = ProductImageProcessor()
            self.image_storage = ImageStorage()
            logger.info("   [SUCCESS] Image processor ready (DALL-E 3 + rembg)")
        except Exception as e:
            logger.warning(f"   [WARNING]  Image processor unavailable: {e}")
            self.image_processor = None
            self.image_storage = None

        # Shopify client
        try:
            store = shopify_store or os.getenv("SHOPIFY_STORE")
            token = shopify_token or os.getenv("SHOPIFY_API_TOKEN")

            if not store or not token:
                raise ValueError("Shopify credentials not configured")

            # ShopifyAdapter expects credentials dict
            credentials = {
                "store_domain": store,
                "admin_api_token": token,
                "api_version": os.getenv("SHOPIFY_API_VERSION", "2025-01")
            }
            self.shopify = ShopifyAdapter(credentials)
            logger.info(f"   [SUCCESS] Shopify client ready ({store})")
        except Exception as e:
            logger.warning(f"   [WARNING]  Shopify client unavailable: {e}")
            self.shopify = None

        logger.info("[SUCCESS] ProductDeployer initialized")

    async def prepare_product(
        self,
        aliexpress_product: Dict = None,
        niche: str = None,
        auto_enhance_images: bool = True,
        auto_generate_content: bool = True,
        source_product: Dict = None,  # Task #21: source-agnostic alias
    ) -> Dict:
        """
        Prepare product for deployment WITHOUT deploying

        Good for preview/review before going live.

        Args:
            source_product (or aliexpress_product): Raw product data from ANY supplier
                                                    (AliExpress, CJ Dropshipping, etc.).
                                                    Both args are accepted for back-compat.
            niche: Product niche
            auto_enhance_images: Enhance images with AI
            auto_generate_content: Generate content with AI

        Returns:
            Complete product data ready for Shopify
        """
        # Task #21: accept either arg name. The legacy name "aliexpress_product"
        # was misleading — CJ Dropshipping products flow through this same path.
        product_data = source_product if source_product is not None else aliexpress_product
        if product_data is None:
            raise ValueError("prepare_product requires either source_product or aliexpress_product")
        # Keep the legacy local name so downstream code continues to work.
        aliexpress_product = product_data

        logger.info(f"\n{'='*70}")
        logger.info(f"[FIX] PREPARING PRODUCT")
        logger.info(f"{'='*70}")

        start_time = time.time()
        costs = {"content": 0.0, "images": 0.0}

        # Extract data — support CJ + AliExpress + generic shapes.
        # AliExpress uses: title, price, images
        # CJ Dropshipping uses: title, price (also cost_price/supplier_cost), all_images
        # Generic discovery payload may use: name instead of title
        product_name = (
            aliexpress_product.get("title")
            or aliexpress_product.get("name")
            or "Product"
        )
        cost_price = (
            aliexpress_product.get("price")
            or aliexpress_product.get("cost_price")
            or aliexpress_product.get("supplier_cost")
            or 0
        )
        # CJ normalized products store URLs in `all_images`; AliExpress uses `images`.
        # Accept both so CJ-only products don't deploy with zero images.
        images = (
            aliexpress_product.get("images")
            or aliexpress_product.get("all_images")
            or ([aliexpress_product.get("image_url")] if aliexpress_product.get("image_url") else [])
        )
        # Normalize: strip falsy entries
        images = [url for url in (images or []) if url]

        logger.info(f"Product: {product_name[:50]}")
        logger.info(f"Niche: {niche}")
        logger.info(f"Cost: ${cost_price:.2f}")
        logger.info(f"Images: {len(images)}")
        logger.info("")

        result = {
            "original_data": aliexpress_product,
            "niche": niche,
            "prepared_at": datetime.now().isoformat()
        }

        # Step 1: Generate AI content
        if auto_generate_content and self.content_generator:
            logger.info("[NOTE] Step 1: Generating AI content...")
            try:
                content = await self.content_generator.generate_complete_listing(
                    aliexpress_data=aliexpress_product,
                    niche=niche
                )

                result["content"] = content

                # Track content generation cost
                stats = self.content_generator.get_usage_stats(last_n_hours=1)
                costs["content"] = stats.get("total_cost", 0.02)

                logger.info(f"   [SUCCESS] Content generated (cost: ${costs['content']:.4f})")
                logger.info(f"   Title: {content['title'][:50]}")

            except Exception as e:
                logger.error(f"   [ERROR] Content generation failed: {e}")
                result["content"] = self._create_fallback_content(aliexpress_product, niche)
        else:
            logger.info("[NOTE] Step 1: Using fallback content (AI disabled)")
            result["content"] = self._create_fallback_content(aliexpress_product, niche)

        # Step 2: Enhance images
        if auto_enhance_images and self.image_processor and images:
            logger.info("\n Step 2: Enhancing images with AI...")
            enhanced_images = []

            try:
                # Process first image (primary)
                image_url = images[0]
                logger.info(f"   Processing primary image...")

                enhancement_result = await self.image_processor.process_product_image(
                    aliexpress_image_url=image_url,
                    product_name=result["content"]["title"],
                    niche=niche,
                    add_branding=True,
                    save_to_disk=False
                )

                if enhancement_result.get("success"):
                    # Save enhanced image
                    import base64
                    import io
                    from PIL import Image

                    image_data = base64.b64decode(enhancement_result["image_base64"])
                    enhanced_image = Image.open(io.BytesIO(image_data))

                    # Generate unique product ID
                    product_id = f"ae_{hash(product_name) % 1000000}"

                    storage_result = self.image_storage.save_product_image(
                        image=enhanced_image,
                        product_id=product_id,
                        image_type="enhanced",
                        format="png"
                    )

                    if storage_result.get("success"):
                        # Convert to absolute URL
                        base_url = os.getenv("BASE_URL", "http://localhost:8001")
                        full_url = f"{base_url}{storage_result['url']}"
                        enhanced_images.append(full_url)

                        costs["images"] += enhancement_result.get("cost_estimate", 0.04)
                        logger.info(f"   [SUCCESS] Primary image enhanced (cost: $0.04)")

                # Add remaining original images
                enhanced_images.extend(images[1:5])  # Max 5 total

                result["images"] = enhanced_images
                logger.info(f"    Total images: {len(enhanced_images)}")

            except Exception as e:
                logger.error(f"   [ERROR] Image enhancement failed: {e}")
                result["images"] = images[:5]
        else:
            logger.info("\n Step 2: Using original images (enhancement disabled)")
            result["images"] = images[:5]

        # Step 3: Calculate final pricing
        logger.info("\n[PRICE] Step 3: Calculating pricing...")
        pricing = result["content"].get("pricing", {})
        result["pricing"] = {
            "cost_price": cost_price,
            "suggested_price": pricing.get("suggested_price", cost_price * 2.5),
            "min_viable_price": pricing.get("min_viable_price", cost_price * 1.5),
            "premium_price": pricing.get("premium_price", cost_price * 3.0),
            "margin": pricing.get("margin_at_suggested", 0.4)
        }
        logger.info(f"   Suggested: ${result['pricing']['suggested_price']:.2f}")
        logger.info(f"   Margin: {result['pricing']['margin'] * 100:.1f}%")

        # Summary
        processing_time = time.time() - start_time
        result["meta"] = {
            "processing_time_seconds": round(processing_time, 2),
            "ai_costs": costs,
            "total_cost": round(sum(costs.values()), 4),
            "services_used": {
                "content_generation": auto_generate_content and self.content_generator is not None,
                "image_enhancement": auto_enhance_images and self.image_processor is not None
            }
        }

        logger.info(f"\n{'='*70}")
        logger.info(f"[SUCCESS] PREPARATION COMPLETE")
        logger.info(f"{'='*70}")
        logger.info(f"Processing time: {processing_time:.2f}s")
        logger.info(f"AI costs: ${result['meta']['total_cost']:.4f}")
        logger.info(f"{'='*70}\n")

        return result

    async def deploy_product(
        self,
        aliexpress_product: Dict = None,
        niche: str = None,
        shopify_store_id: Optional[str] = None,
        options: Optional[Dict] = None,
        source_product: Dict = None,  # Task #21: source-agnostic alias
    ) -> Dict:
        """
        Full deployment pipeline to Shopify

        Args:
            source_product (or aliexpress_product): Raw product data from ANY
                                                    supplier (AliExpress, CJ Dropshipping, etc.)
            niche: Product niche
            shopify_store_id: Optional specific store
            options: Deployment options

        Returns:
            Deployment result with Shopify product ID and URLs
        """
        # Task #21: accept both arg names for back-compat with callers that
        # still pass the legacy name.
        product_data = source_product if source_product is not None else aliexpress_product
        if product_data is None:
            raise ValueError("deploy_product requires either source_product or aliexpress_product")

        logger.info(f"\n{'='*70}")
        logger.info(f"[START] DEPLOYING PRODUCT TO SHOPIFY")
        source_tag = product_data.get("source") or "unknown"
        logger.info(f"[SOURCE] {source_tag}")
        logger.info(f"{'='*70}")

        if not self.shopify:
            raise ValueError("Shopify client not configured")

        start_time = time.time()

        # Parse options
        opts = DeploymentOptions(**(options or {}))

        # Step 1-3: Prepare product
        prepared = await self.prepare_product(
            source_product=product_data,
            niche=niche,
            auto_enhance_images=opts.enhance_images,
            auto_generate_content=opts.generate_content
        )

        # Step 4: Create Shopify product
        logger.info(" Step 4: Creating product on Shopify...")

        content = prepared["content"]
        pricing = prepared["pricing"]
        images = prepared["images"]

        try:
            # Build product dictionary for ShopifyAdapter.deploy_product()
            seo = content.get("seo", {})
            product_dict = {
                "title": content["title"],
                "description": content["description_html"],
                "vendor": content.get("vendor", "Oubon Shop"),
                "product_type": content.get("product_type", niche),
                "tags": content.get("tags", []),
                "price": pricing["suggested_price"],
                "compare_at_price": pricing.get("premium_price"),
                # Task #21: SKU prefix reflects actual source.
                # AliExpress → AE-, CJ Dropshipping → CJ-, otherwise PROD-.
                "sku": (
                    f"{'CJ' if product_data.get('source') == 'cj_dropshipping' else ('AE' if product_data.get('source') == 'aliexpress' else 'PROD')}"
                    f"-{hash(content['title']) % 1000000}"
                ),
                "inventory": 100,
                "images": images,
                "weight": 0.5,
                "weight_unit": "kg"
            }

            # Deploy product using ShopifyAdapter
            deploy_result = await self.shopify.deploy_product(product_dict)

            if not deploy_result.get("success"):
                raise Exception(f"Shopify deployment failed: {deploy_result.get('error', 'Unknown error')}")

            product_id = deploy_result["platform_product_id"]
            shopify_url = deploy_result["platform_url"]
            admin_url = deploy_result["admin_url"]

            logger.info(f"   [SUCCESS] Product created: {product_id}")
            logger.info(f"   [SUCCESS] Pricing set: ${pricing['suggested_price']:.2f}")
            logger.info(f"   [SUCCESS] Images uploaded: {len(images)}")
            logger.info("   [SUCCESS] SEO metadata set")

            # Build result
            processing_time = time.time() - start_time

            result = {
                "success": True,
                "shopify_product_id": product_id,
                "shopify_url": shopify_url,
                "admin_url": admin_url,
                "content_generated": {
                    "title": content["title"],
                    "description_length": len(content["description_html"]),
                    "seo_keywords": seo.get("keywords", {}).get("primary", "")
                },
                "images_enhanced": len([img for img in images if "localhost" in img or "static/images" in img]),
                "pricing": pricing,
                "processing_time_seconds": round(processing_time, 2),
                "ai_costs": prepared["meta"]["ai_costs"],
                "total_cost": prepared["meta"]["total_cost"],
                "published": opts.publish_immediately
            }

            logger.info(f"\n{'='*70}")
            logger.info(f"[SUCCESS] DEPLOYMENT SUCCESSFUL")
            logger.info(f"{'='*70}")
            logger.info(f"Product ID: {product_id}")
            logger.info(f"URL: {result['shopify_url']}")
            logger.info(f"Processing: {processing_time:.2f}s")
            logger.info(f"AI Costs: ${result['total_cost']:.4f}")
            logger.info(f"Published: {'Yes' if opts.publish_immediately else 'Draft'}")
            logger.info(f"{'='*70}\n")

            return result

        except Exception as e:
            logger.error(f"[ERROR] Deployment failed: {e}")
            import traceback
            traceback.print_exc()

            return {
                "success": False,
                "error": str(e),
                "processing_time_seconds": round(time.time() - start_time, 2),
                "ai_costs": prepared["meta"]["ai_costs"]
            }

    async def bulk_deploy(
        self,
        products: List[Dict],
        niche: str,
        options: Optional[Dict] = None
    ) -> Dict:
        """
        Deploy multiple products with progress tracking

        Args:
            products: List of AliExpress products
            niche: Product niche
            options: Deployment options

        Returns:
            Bulk deployment summary
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"[START] BULK DEPLOYMENT: {len(products)} products")
        logger.info(f"{'='*70}\n")

        start_time = time.time()
        results = []
        successful = 0
        failed = 0
        total_cost = 0.0

        for idx, product in enumerate(products, 1):
            logger.info(f"[PACKAGE] [{idx}/{len(products)}] Processing: {product.get('title', 'Unknown')[:50]}")

            try:
                result = await self.deploy_product(
                    aliexpress_product=product,
                    niche=niche,
                    options=options
                )

                if result.get("success"):
                    successful += 1
                    total_cost += result.get("total_cost", 0)
                    results.append({
                        "product": product.get("title"),
                        "success": True,
                        "shopify_product_id": result.get("shopify_product_id"),
                        "shopify_url": result.get("shopify_url"),
                        "cost": result.get("total_cost")
                    })
                else:
                    failed += 1
                    results.append({
                        "product": product.get("title"),
                        "success": False,
                        "error": result.get("error")
                    })

            except Exception as e:
                failed += 1
                logger.error(f"   [ERROR] Deployment failed: {e}")
                results.append({
                    "product": product.get("title"),
                    "success": False,
                    "error": str(e)
                })

            # Rate limiting pause between products
            if idx < len(products):
                await asyncio.sleep(2)

        processing_time = time.time() - start_time

        summary = {
            "total": len(products),
            "successful": successful,
            "failed": failed,
            "results": results,
            "total_cost": round(total_cost, 2),
            "processing_time_seconds": round(processing_time, 2),
            "average_time_per_product": round(processing_time / len(products), 2) if products else 0
        }

        logger.info(f"\n{'='*70}")
        logger.info(f"[SUCCESS] BULK DEPLOYMENT COMPLETE")
        logger.info(f"{'='*70}")
        logger.info(f"Successful: {successful}/{len(products)}")
        logger.info(f"Failed: {failed}/{len(products)}")
        logger.info(f"Total cost: ${total_cost:.2f}")
        logger.info(f"Total time: {processing_time:.2f}s")
        logger.info(f"{'='*70}\n")

        return summary

    async def preview_deployment(
        self,
        aliexpress_product: Dict,
        niche: str
    ) -> Dict:
        """
        Generate deployment preview without deploying

        Good for admin review before going live.

        Args:
            aliexpress_product: Product data
            niche: Product niche

        Returns:
            Preview of what would be deployed
        """
        logger.info("  Generating deployment preview...")

        prepared = await self.prepare_product(
            aliexpress_product=aliexpress_product,
            niche=niche,
            auto_enhance_images=True,
            auto_generate_content=True
        )

        preview = {
            "title": prepared["content"]["title"],
            "description_html": prepared["content"]["description_html"],
            "short_description": prepared["content"]["short_description"],
            "bullet_points": prepared["content"]["bullet_points"],
            "images": prepared["images"],
            "pricing": prepared["pricing"],
            "seo": prepared["content"]["seo"],
            "tags": prepared["content"]["tags"],
            "estimated_deployment_cost": prepared["meta"]["total_cost"],
            "processing_time": prepared["meta"]["processing_time_seconds"]
        }

        logger.info("[SUCCESS] Preview generated")

        return preview

    def _create_fallback_content(self, product: Dict, niche: str) -> Dict:
        """Create basic content when AI is unavailable"""
        title = product.get("title", "Product")

        # Clean title
        title = title.replace("2024", "").replace("New", "").replace("Hot Sale", "").strip()
        title = " ".join(title.split()[:12])  # Limit words

        return {
            "title": title,
            "description_html": f"<p>{product.get('description', 'High quality product.')}</p>",
            "short_description": product.get("description", "Quality product")[:100],
            "bullet_points": product.get("features", ["High quality", "Fast shipping", "Great value"]),
            "seo": {
                "meta_title": title,
                "meta_description": product.get("description", "")[:155],
                "url_slug": title.lower().replace(" ", "-"),
                "keywords": {"primary": niche, "secondary": []},
                "image_alt_text": title
            },
            "pricing": {
                "suggested_price": product.get("price", 0) * 2.5,
                "min_viable_price": product.get("price", 0) * 1.5,
                "premium_price": product.get("price", 0) * 3.0,
                "margin_at_suggested": 0.6
            },
            "tags": [niche],
            "product_type": niche,
            "vendor": "Oubon Shop"
        }
