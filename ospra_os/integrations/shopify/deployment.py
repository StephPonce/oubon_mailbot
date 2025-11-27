"""
Product Deployment Service - Deploy discovered products to Shopify with AI
"""
import os
from typing import Dict, List
from .client import ShopifyClient
from anthropic import Anthropic
from ospra_os.intelligence.ai_pricing_generator import generate_product_pricing


class ProductDeploymentService:
    """Service for deploying products to Shopify with AI-powered content generation"""

    def __init__(self, shopify_client: ShopifyClient = None):
        self.shopify = shopify_client or ShopifyClient()

        # Initialize AI client for content generation
        self.ai_client = None
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key:
            try:
                self.ai_client = Anthropic(api_key=anthropic_key)
                print("✅ AI-powered deployment enabled (Claude)")
            except Exception as e:
                print(f"⚠️  AI initialization failed: {e}")
        else:
            print("⚠️  ANTHROPIC_API_KEY not set - using template descriptions")

    async def deploy_product(
        self,
        product_data: Dict,
        generate_description: bool = True
    ) -> Dict:
        """
        Deploy a discovered product to Shopify

        Args:
            product_data: Product from discovery system
            generate_description: Use AI to enhance description

        Returns:
            Deployment result with Shopify product ID
        """
        try:
            print(f"\n{'='*70}")
            print(f"🚀 DEPLOYING TO SHOPIFY")
            print(f"{'='*70}")
            print(f"Product: {product_data.get('name', 'Unknown')[:50]}")
            print()

            # Prepare product for Shopify
            title = self._generate_title(product_data)
            description = await self._generate_description(product_data, generate_description)
            price = self._calculate_price(product_data)
            images = self._get_images(product_data)
            tags = self._generate_tags(product_data)

            # Metafields for internal tracking
            meta_fields = {
                'ospra_product_id': product_data.get('id', ''),
                'trend_score': product_data.get('trend_score', 0),
                'discovery_source': product_data.get('discovery_source', ''),
                'aliexpress_url': product_data.get('fulfillment_url', ''),
                'amazon_url': product_data.get('source_url', ''),
                'deployed_at': str(product_data.get('created_at', ''))
            }

            # Create in Shopify
            shopify_product = await self.shopify.create_product(
                title=title,
                description=description,
                price=price,
                images=images,
                tags=tags,
                meta_fields=meta_fields,
                inventory_quantity=100  # Default stock
            )

            if not shopify_product:
                print("❌ Deployment failed")
                return {
                    'success': False,
                    'error': 'Shopify API error'
                }

            result = {
                'success': True,
                'shopify_product_id': shopify_product.get('id'),
                'shopify_url': f"https://{self.shopify.store_name}.myshopify.com/products/{shopify_product.get('handle')}",
                'admin_url': f"https://{self.shopify.store_name}.myshopify.com/admin/products/{shopify_product.get('id')}",
                'title': title,
                'price': price,
                'images_count': len(images)
            }

            print(f"\n{'='*70}")
            print(f"✅ DEPLOYMENT SUCCESSFUL")
            print(f"{'='*70}")
            print(f"Shopify ID: {result['shopify_product_id']}")
            print(f"Store URL: {result['shopify_url']}")
            print(f"Price: ${price:.2f}")
            print(f"Images: {len(images)}")
            print(f"{'='*70}\n")

            return result

        except Exception as e:
            print(f"❌ Deployment error: {e}")
            import traceback
            traceback.print_exc()

            return {
                'success': False,
                'error': str(e)
            }

    def _generate_title(self, product_data: Dict) -> str:
        """Generate SEO-optimized title"""
        name = product_data.get('name', 'Product')

        # Clean up title
        title = name.strip()

        # Remove excessive punctuation
        title = title.replace('!!!', '').replace('...', '')

        # Limit length
        if len(title) > 70:
            title = title[:67] + "..."

        return title

    async def _generate_description(
        self,
        product_data: Dict,
        use_ai: bool
    ) -> str:
        """Generate AI-powered product description using Claude"""
        if use_ai and self.ai_client:
            try:
                print("🤖 Generating AI description with Claude...")

                # Get multi-source data for context
                source_count = product_data.get('source_count', 0)
                primary_sources = product_data.get('primary_sources', [])
                tiktok_sales = product_data.get('tiktok_sales', 0)
                amazon_bestseller = product_data.get('amazon_bestseller', False)
                amazon_rank = product_data.get('amazon_rank', 0)
                trend_score = product_data.get('trend_score', 0)

                # Build validation context
                validation_context = ""
                if source_count >= 2:
                    validation_context = f"\n- Validated by {source_count} independent sources: {', '.join(primary_sources)}"
                if tiktok_sales > 0:
                    validation_context += f"\n- TikTok Shop: {tiktok_sales:,} sales"
                if amazon_bestseller:
                    validation_context += f"\n- Amazon Bestseller: Rank #{amazon_rank}"

                prompt = f"""Generate a compelling Shopify product description for this product:

Product Name: {product_data.get('name')}
Niche: {product_data.get('niche', 'general')}
Trend Score: {trend_score}/100

Multi-Source Validation:{validation_context if validation_context else " Single source"}

Generate an HTML-formatted Shopify product description that:
1. Opens with a compelling hook that highlights why this is trending
2. Includes 3-5 key benefits/features (use <ul> lists)
3. Emphasizes the multi-source validation if applicable (social proof)
4. Uses persuasive e-commerce copywriting
5. Includes a clear call-to-action
6. Is 150-250 words
7. Uses proper HTML tags: <h3>, <p>, <ul>, <li>, <strong>

Make it conversion-focused and SEO-friendly. Return ONLY the HTML description, no markdown code blocks."""

                response = self.ai_client.messages.create(
                    model="claude-sonnet-4-5-20250929",  # Latest Sonnet 4.5
                    max_tokens=800,
                    temperature=0.7,
                    messages=[{"role": "user", "content": prompt}]
                )

                description = response.content[0].text.strip()

                # Remove markdown code blocks if present
                if description.startswith("```"):
                    lines = description.split("\n")
                    description = "\n".join(lines[1:-1])

                print(f"✅ AI description generated ({len(description)} chars)")
                return description

            except Exception as e:
                print(f"⚠️  AI description failed, using template: {e}")
                # Fall through to template

        # Use existing description or create basic one
        description = product_data.get('description', '')

        if not description:
            name = product_data.get('name', 'Product')
            description = f"""
            <h3>Introducing {name}</h3>

            <p>Discover the perfect addition to your home with this trending product.</p>

            <h3>Key Features:</h3>
            <ul>
                <li>High quality construction</li>
                <li>Easy to use and install</li>
                <li>Perfect for everyday use</li>
                <li>Durable and long-lasting</li>
            </ul>

            <h3>Why Choose This Product:</h3>
            <p>This product has been carefully selected based on current market trends and customer satisfaction ratings.</p>

            <p><strong>Fast shipping available! Order now while supplies last.</strong></p>
            """

        return description.strip()

    def _calculate_price(self, product_data: Dict) -> float:
        """Calculate competitive pricing using AI analysis"""
        # Try AI-powered pricing first
        if self.ai_client:
            try:
                print("🤖 Calculating competitive pricing with AI...")
                pricing_data = generate_product_pricing(
                    product_name=product_data.get('name', ''),
                    niche=product_data.get('niche', 'general')
                )

                # Use AI-generated price
                ai_price = pricing_data.get('price', 0)
                if ai_price > 0:
                    print(f"✅ AI pricing: ${ai_price:.2f} (margin: {pricing_data.get('profit_margin')}%)")
                    return ai_price

            except Exception as e:
                print(f"⚠️  AI pricing failed, using rule-based: {e}")

        # Fallback: Rule-based pricing
        cost = product_data.get('cost', 0) or product_data.get('price', 0)

        # Check if we have pricing from discovery sources
        if product_data.get('tiktok_price', 0) > 0:
            # Use TikTok Shop price as reference
            return self._psychological_pricing(product_data['tiktok_price'] * 0.95)  # Slightly undercut

        if product_data.get('amazon_price', 0) > 0:
            # Use Amazon price as reference
            return self._psychological_pricing(product_data['amazon_price'] * 0.92)  # Competitive pricing

        if product_data.get('shopify_price', 0) > 0:
            # Match competitor Shopify pricing
            return self._psychological_pricing(product_data['shopify_price'])

        if cost == 0:
            # Default price if no cost data
            return 29.99

        # Apply markup (120% = 2.2x)
        price = cost * 2.2

        # Psychological pricing
        price = self._psychological_pricing(price)

        return round(price, 2)

    def _psychological_pricing(self, price: float) -> float:
        """Apply psychological pricing (.99, .97, etc.)"""
        # Round to nearest dollar
        rounded = round(price)

        # Apply .99 ending
        if rounded < 10:
            return rounded - 0.01  # $9.99
        elif rounded < 50:
            return rounded - 0.01  # $29.99
        elif rounded < 100:
            return rounded - 3  # $97
        else:
            return rounded - 5  # $195

    def _get_images(self, product_data: Dict) -> List[str]:
        """Get product images"""
        images = []

        # Single image URL
        if product_data.get('image_url'):
            images.append(product_data['image_url'])

        # Multiple images
        if product_data.get('images'):
            images.extend(product_data['images'])

        # Amazon images (usually best quality)
        if product_data.get('amazon_data', {}).get('images'):
            images.extend(product_data['amazon_data']['images'][:5])

        # Deduplicate
        images = list(dict.fromkeys(images))

        return images[:10]  # Max 10 images

    def _generate_tags(self, product_data: Dict) -> List[str]:
        """Generate product tags"""
        tags = []

        # Niche
        if product_data.get('niche'):
            tags.append(product_data['niche'])

        # Priority
        if product_data.get('priority'):
            tags.append(product_data['priority'])

        # Trending
        if product_data.get('trend_score', 0) >= 80:
            tags.append('trending')

        # New arrival
        tags.append('new-arrival')

        return tags

    async def bulk_deploy(
        self,
        products: List[Dict],
        max_concurrent: int = 3
    ) -> List[Dict]:
        """Deploy multiple products"""
        import asyncio

        print(f"\n🚀 Bulk deploying {len(products)} products...")

        results = []

        # Deploy in batches to avoid rate limits
        for i in range(0, len(products), max_concurrent):
            batch = products[i:i + max_concurrent]

            tasks = [
                self.deploy_product(product)
                for product in batch
            ]

            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)

            # Rate limit pause
            if i + max_concurrent < len(products):
                print(f"   Pausing 2s to avoid rate limits...")
                await asyncio.sleep(2)

        successful = sum(1 for r in results if r.get('success'))
        print(f"\n✅ Deployed {successful}/{len(products)} products successfully")

        return results
