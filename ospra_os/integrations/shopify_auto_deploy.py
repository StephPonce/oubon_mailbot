"""Automatically deploy products to Shopify with AI-generated content."""

from typing import Dict, Optional
from ospra_os.core.settings import get_settings
from ospra_os.product_research.ai_content import AIContentGenerator
from ospra_os.product_research.price_optimizer import PriceOptimizer
import httpx
import json


class ShopifyAutoDeployer:
    """Automatically list products to Shopify with AI optimization."""

    def __init__(self):
        self.settings = get_settings()
        self.content_generator = AIContentGenerator()
        self.price_optimizer = PriceOptimizer()

    async def deploy_product(
        self,
        product_name: str,
        niche: str,
        score: float,
        trend_score: float = 0,
        aliexpress_cost: Optional[float] = None,
        product_images: Optional[list] = None
    ) -> Dict:
        """
        Complete product deployment pipeline:
        1. Generate AI content
        2. Optimize pricing
        3. Create Shopify product listing
        4. Return deployment status

        Args:
            product_name: Product name
            niche: Product category
            score: Discovery score (0-10)
            trend_score: Google Trends score (0-100)
            aliexpress_cost: Cost from supplier (default: estimate from score)
            product_images: List of image URLs (optional)

        Returns:
            {
                "success": True,
                "shopify_product_id": "8234567890",
                "shopify_admin_url": "https://admin.shopify.com/...",
                "product_title": "...",
                "price": 29.99,
                "profit_margin": 65.5,
                "content_generated": True,
                "pricing_optimized": True
            }
        """

        print(f"\n{'='*70}")
        print(f"🚀 SHOPIFY AUTO-DEPLOY: {product_name}")
        print(f"{'='*70}")

        # Estimate cost if not provided (based on typical dropshipping margins)
        if aliexpress_cost is None:
            if score >= 8:
                aliexpress_cost = 15.0  # High-quality trending product
            elif score >= 6:
                aliexpress_cost = 10.0  # Medium-quality product
            else:
                aliexpress_cost = 5.0   # Low-cost product
            print(f"💵 Estimated cost: ${aliexpress_cost} (based on score {score}/10)")

        # Step 1: Generate AI content
        print(f"\n📝 Step 1/3: Generating AI content...")
        try:
            content = await self.content_generator.generate_product_content(
                product_name=product_name,
                niche=niche,
                trend_score=trend_score
            )
            print(f"✅ Content generated: {content['title'][:50]}...")
            content_generated = True
        except Exception as e:
            print(f"⚠️  Content generation failed: {e}")
            # Use fallback content
            content = {
                "title": f"{product_name} - Premium Quality",
                "description": f"<p>Discover the amazing <strong>{product_name}</strong>!</p>",
                "bullet_points": ["Premium quality", "Fast shipping", "Money-back guarantee"],
                "meta_description": f"Buy {product_name} - Premium quality product",
                "tags": [product_name.lower(), niche, "trending"],
                "headline": f"Get Your {product_name} Today!"
            }
            content_generated = False

        # Step 2: Optimize pricing
        print(f"\n💰 Step 2/3: Optimizing pricing...")
        try:
            pricing = await self.price_optimizer.analyze_pricing(
                product_name=product_name,
                aliexpress_cost=aliexpress_cost,
                niche=niche,
                trend_score=trend_score
            )
            print(f"✅ Price optimized: ${pricing['suggested_price']} ({pricing['profit_margin']}% margin)")
            pricing_optimized = True
        except Exception as e:
            print(f"⚠️  Pricing optimization failed: {e}")
            # Use fallback pricing
            pricing = {
                "suggested_price": round(aliexpress_cost * 3, 2),
                "compare_at_price": round(aliexpress_cost * 4, 2),
                "profit_margin": 66.7,
                "profit_per_sale": round(aliexpress_cost * 2, 2),
                "pricing_strategy": "value"
            }
            pricing_optimized = False

        # Step 3: Create Shopify product
        print(f"\n🛍️  Step 3/3: Creating Shopify listing...")
        try:
            shopify_result = await self._create_shopify_product(
                title=content["title"],
                description=content["description"],
                price=pricing["suggested_price"],
                compare_at_price=pricing["compare_at_price"],
                tags=content["tags"],
                vendor="Ospra Store",
                product_type=niche,
                images=product_images or []
            )

            print(f"✅ Product created on Shopify!")
            print(f"   Product ID: {shopify_result['product_id']}")
            print(f"   Admin URL: {shopify_result['admin_url']}")

            print(f"\n{'='*70}")
            print(f"🎉 DEPLOYMENT COMPLETE!")
            print(f"{'='*70}")
            print(f"Product: {content['title']}")
            print(f"Price: ${pricing['suggested_price']} (was ${pricing['compare_at_price']})")
            print(f"Profit: ${pricing['profit_per_sale']}/sale ({pricing['profit_margin']}% margin)")
            print(f"Shopify: {shopify_result['admin_url']}")
            print(f"{'='*70}\n")

            return {
                "success": True,
                "shopify_product_id": shopify_result["product_id"],
                "shopify_admin_url": shopify_result["admin_url"],
                "shopify_storefront_url": shopify_result.get("storefront_url"),
                "product_title": content["title"],
                "price": pricing["suggested_price"],
                "compare_at_price": pricing["compare_at_price"],
                "profit_margin": pricing["profit_margin"],
                "profit_per_sale": pricing["profit_per_sale"],
                "cost": aliexpress_cost,
                "content_generated": content_generated,
                "pricing_optimized": pricing_optimized,
                "tags": content["tags"],
                "niche": niche
            }

        except Exception as e:
            print(f"❌ Shopify product creation failed: {e}")
            print(f"\n{'='*70}")
            print(f"⚠️  DEPLOYMENT FAILED")
            print(f"{'='*70}\n")

            return {
                "success": False,
                "error": str(e),
                "product_title": content["title"],
                "price": pricing["suggested_price"],
                "profit_margin": pricing["profit_margin"],
                "content_generated": content_generated,
                "pricing_optimized": pricing_optimized
            }

    async def _create_shopify_product(
        self,
        title: str,
        description: str,
        price: float,
        compare_at_price: float,
        tags: list,
        vendor: str,
        product_type: str,
        images: list
    ) -> Dict:
        """
        Create product on Shopify using Admin API.

        Returns:
            {
                "product_id": "8234567890",
                "admin_url": "https://admin.shopify.com/store/...",
                "storefront_url": "https://yourstore.com/products/..."
            }
        """

        if not self.settings.SHOPIFY_ACCESS_TOKEN or not self.settings.SHOPIFY_STORE_DOMAIN:
            raise ValueError("Shopify credentials not configured. Set SHOPIFY_ACCESS_TOKEN and SHOPIFY_STORE_DOMAIN in .env")

        # Prepare Shopify API request
        url = f"https://{self.settings.SHOPIFY_STORE_DOMAIN}/admin/api/2024-01/products.json"
        headers = {
            "X-Shopify-Access-Token": self.settings.SHOPIFY_ACCESS_TOKEN,
            "Content-Type": "application/json"
        }

        # Build product payload
        product_data = {
            "product": {
                "title": title,
                "body_html": description,
                "vendor": vendor,
                "product_type": product_type,
                "tags": ", ".join(tags),
                "status": "active",  # Publish immediately
                "variants": [
                    {
                        "price": str(price),
                        "compare_at_price": str(compare_at_price),
                        "inventory_management": None,  # Don't track inventory (dropshipping)
                        "fulfillment_service": "manual"
                    }
                ]
            }
        }

        # Add images if provided
        if images:
            product_data["product"]["images"] = [
                {"src": img_url} for img_url in images[:10]  # Max 10 images
            ]

        # Create product on Shopify
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=product_data, headers=headers)

            if response.status_code not in [200, 201]:
                error_detail = response.text
                raise Exception(f"Shopify API error {response.status_code}: {error_detail}")

            result = response.json()
            product = result["product"]
            product_id = product["id"]
            product_handle = product["handle"]

            # Construct URLs
            store_name = self.settings.SHOPIFY_STORE_DOMAIN.replace(".myshopify.com", "")
            admin_url = f"https://admin.shopify.com/store/{store_name}/products/{product_id}"
            storefront_url = f"https://{self.settings.SHOPIFY_STORE_DOMAIN}/products/{product_handle}"

            return {
                "product_id": str(product_id),
                "admin_url": admin_url,
                "storefront_url": storefront_url
            }

    async def bulk_deploy(
        self,
        products: list,
        delay_between: int = 5
    ) -> Dict:
        """
        Deploy multiple products to Shopify with delay between each.

        Args:
            products: List of product dicts with name, niche, score, etc.
            delay_between: Seconds to wait between deployments (avoid rate limits)

        Returns:
            {
                "total": 10,
                "successful": 8,
                "failed": 2,
                "results": [...]
            }
        """
        import asyncio

        print(f"\n{'='*70}")
        print(f"📦 BULK DEPLOY: {len(products)} products")
        print(f"{'='*70}\n")

        results = []
        successful = 0
        failed = 0

        for i, product in enumerate(products, 1):
            print(f"\n[{i}/{len(products)}] Deploying: {product.get('name', 'Unknown')}")

            try:
                result = await self.deploy_product(
                    product_name=product.get("name", "Unknown Product"),
                    niche=product.get("niche", "general"),
                    score=product.get("score", 5.0),
                    trend_score=product.get("trend_score", 50),
                    aliexpress_cost=product.get("cost")
                )

                results.append(result)

                if result["success"]:
                    successful += 1
                else:
                    failed += 1

            except Exception as e:
                print(f"❌ Deployment {i} failed: {e}")
                results.append({
                    "success": False,
                    "error": str(e),
                    "product_title": product.get("name", "Unknown")
                })
                failed += 1

            # Wait between deployments (avoid Shopify rate limits: 2 requests/second)
            if i < len(products):
                print(f"⏳ Waiting {delay_between}s before next deployment...")
                await asyncio.sleep(delay_between)

        print(f"\n{'='*70}")
        print(f"✅ BULK DEPLOY COMPLETE")
        print(f"{'='*70}")
        print(f"Total: {len(products)}")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        print(f"{'='*70}\n")

        return {
            "total": len(products),
            "successful": successful,
            "failed": failed,
            "results": results
        }
