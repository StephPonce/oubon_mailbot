"""
Image Processing Service
- DALL-E lifestyle image generation
- Auto resize/optimize for Shopify
"""

import os
import io
import logging
import aiohttp
import base64
from typing import Dict, Optional, List
from PIL import Image
from openai import OpenAI

logger = logging.getLogger(__name__)


class ImageProcessor:
    """
    Process product images with AI generation and optimization
    """

    # Shopify optimal image sizes
    SHOPIFY_SIZES = {
        'large': (2048, 2048),      # Product page main image
        'medium': (1024, 1024),     # Gallery thumbnail
        'small': (480, 480),        # Mobile view
        'thumbnail': (200, 200),    # Cart/checkout
    }

    def __init__(self):
        """Initialize image processor with OpenAI DALL-E."""
        api_key = os.getenv('OPENAI_API_KEY')

        if api_key:
            self.openai = OpenAI(api_key=api_key)
            logger.info("✅ Image Processor initialized with DALL-E")
        else:
            self.openai = None
            logger.warning("⚠️  OPENAI_API_KEY not set - DALL-E disabled")

    async def generate_lifestyle_image(
        self,
        product_name: str,
        product_category: str = "product"
    ) -> Optional[str]:
        """
        Generate AI lifestyle image using DALL-E.

        Args:
            product_name: Name of the product
            product_category: Category (smart home, fitness, etc.)

        Returns:
            URL of generated image or None if failed
        """
        if not self.openai:
            logger.warning("DALL-E not available, skipping lifestyle image")
            return None

        try:
            # Create compelling prompt
            prompt = self._create_lifestyle_prompt(product_name, product_category)

            logger.info(f"🎨 Generating DALL-E image for: {product_name[:50]}...")

            # Generate image with DALL-E 3
            response = self.openai.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1024",
                quality="standard",  # or "hd" for higher quality ($0.08 vs $0.04)
                n=1,
            )

            image_url = response.data[0].url
            logger.info(f"✅ Generated lifestyle image")

            return image_url

        except Exception as e:
            logger.error(f"DALL-E generation failed: {e}")
            return None

    def _create_lifestyle_prompt(self, product_name: str, category: str) -> str:
        """
        Create optimized DALL-E prompt for product lifestyle image.
        """
        # Extract key product features
        name_lower = product_name.lower()

        # Category-specific prompts for best results
        if any(word in name_lower for word in ['smart', 'wifi', 'led', 'light']):
            setting = "modern minimalist living room with soft ambient lighting"
            style = "clean, professional product photography"

        elif any(word in name_lower for word in ['fitness', 'yoga', 'workout', 'exercise']):
            setting = "bright home gym or yoga studio with natural light"
            style = "energetic lifestyle photography"

        elif any(word in name_lower for word in ['gaming', 'rgb', 'headset', 'keyboard']):
            setting = "modern gaming setup with RGB lighting and clean desk"
            style = "dramatic tech photography with neon accents"

        elif any(word in name_lower for word in ['camera', 'security', 'doorbell']):
            setting = "modern home entrance or contemporary interior"
            style = "professional security product photography"

        else:
            setting = "modern minimalist interior with natural lighting"
            style = "clean professional product photography"

        # Build prompt
        prompt = f"""
Professional e-commerce product photography: {product_name}
Setting: {setting}
Style: {style}
Requirements: Product in use or displayed elegantly, photorealistic, high-end marketing image, no text or watermarks, sharp focus on product
Lighting: Professional studio lighting with soft shadows
Mood: Aspirational, premium, inviting
Composition: Rule of thirds, product as focal point
        """.strip()

        return prompt

    async def download_and_optimize(
        self,
        image_url: str,
        max_size_kb: int = 500
    ) -> Optional[bytes]:
        """
        Download image and optimize for web.

        Args:
            image_url: URL of image to download
            max_size_kb: Maximum file size in KB

        Returns:
            Optimized image bytes (JPEG format)
        """
        try:
            logger.info(f"📥 Downloading image from: {image_url[:60]}...")

            async with aiohttp.ClientSession() as session:
                async with session.get(image_url, timeout=15) as response:
                    if response.status != 200:
                        logger.error(f"Failed to download: HTTP {response.status}")
                        return None

                    image_data = await response.read()

            # Open with PIL
            img = Image.open(io.BytesIO(image_data))

            # Convert to RGB if needed (handles RGBA, P, etc.)
            if img.mode != 'RGB':
                # Create white background for transparency
                if img.mode == 'RGBA':
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[3])  # Use alpha as mask
                    img = background
                else:
                    img = img.convert('RGB')

            # Resize to Shopify optimal (1024x1024 for main image)
            target_size = self.SHOPIFY_SIZES['medium']
            img = self._resize_maintain_aspect(img, target_size)

            # Optimize and compress
            output = io.BytesIO()

            # Start with quality 90, reduce if too large
            quality = 90
            while quality > 60:
                output.seek(0)
                output.truncate()

                img.save(
                    output,
                    format='JPEG',
                    quality=quality,
                    optimize=True,
                    progressive=True  # Progressive JPEG for faster loading
                )

                size_kb = len(output.getvalue()) / 1024

                if size_kb <= max_size_kb or quality == 60:
                    break

                quality -= 10

            logger.info(f"✅ Optimized image: {size_kb:.1f}KB at quality {quality}")

            return output.getvalue()

        except Exception as e:
            logger.error(f"Image optimization failed: {e}")
            return None

    def _resize_maintain_aspect(self, img: Image.Image, target_size: tuple) -> Image.Image:
        """
        Resize image maintaining aspect ratio, centered.
        """
        # Calculate aspect ratio
        img_ratio = img.width / img.height
        target_ratio = target_size[0] / target_size[1]

        if img_ratio > target_ratio:
            # Image is wider - fit to width
            new_width = target_size[0]
            new_height = int(new_width / img_ratio)
        else:
            # Image is taller - fit to height
            new_height = target_size[1]
            new_width = int(new_height * img_ratio)

        # Resize with high-quality resampling
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Create canvas and paste centered
        canvas = Image.new('RGB', target_size, (255, 255, 255))

        x_offset = (target_size[0] - new_width) // 2
        y_offset = (target_size[1] - new_height) // 2

        canvas.paste(img, (x_offset, y_offset))

        return canvas

    async def process_product_image(
        self,
        product: Dict,
        generate_lifestyle: bool = True,
        optimize_original: bool = True
    ) -> Dict:
        """
        Complete image processing pipeline for a product.

        Args:
            product: Product dict with 'name', 'image_url', etc.
            generate_lifestyle: Whether to generate DALL-E lifestyle image
            optimize_original: Whether to optimize the original image

        Returns:
            {
                'original_optimized': bytes or None,
                'lifestyle_url': str or None,
                'lifestyle_optimized': bytes or None
            }
        """
        result = {
            'original_optimized': None,
            'lifestyle_url': None,
            'lifestyle_optimized': None
        }

        # 1. Optimize original image
        if optimize_original and product.get('image_url'):
            logger.info(f"📸 Processing original image...")
            result['original_optimized'] = await self.download_and_optimize(
                product['image_url']
            )

        # 2. Generate and optimize lifestyle image
        if generate_lifestyle:
            logger.info(f"🎨 Generating lifestyle image...")

            lifestyle_url = await self.generate_lifestyle_image(
                product_name=product.get('name', 'product'),
                product_category=product.get('niche', 'general')
            )

            if lifestyle_url:
                result['lifestyle_url'] = lifestyle_url

                # Download and optimize the lifestyle image
                result['lifestyle_optimized'] = await self.download_and_optimize(
                    lifestyle_url
                )

        return result

    def create_multiple_sizes(self, image_bytes: bytes) -> Dict[str, bytes]:
        """
        Create multiple size variants of an image.

        Args:
            image_bytes: Original image bytes

        Returns:
            Dict with size names as keys, optimized bytes as values
        """
        try:
            img = Image.open(io.BytesIO(image_bytes))

            if img.mode != 'RGB':
                img = img.convert('RGB')

            variants = {}

            for size_name, dimensions in self.SHOPIFY_SIZES.items():
                output = io.BytesIO()

                # Resize
                resized = self._resize_maintain_aspect(img, dimensions)

                # Optimize
                resized.save(
                    output,
                    format='JPEG',
                    quality=85,
                    optimize=True,
                    progressive=True
                )

                variants[size_name] = output.getvalue()

                logger.info(f"✅ Created {size_name} variant: {dimensions}")

            return variants

        except Exception as e:
            logger.error(f"Failed to create size variants: {e}")
            return {}


# Convenience function for use in product intelligence
async def enhance_product_images(product: Dict) -> Dict:
    """
    Enhance product with AI-generated and optimized images.

    Usage in product_intelligence_v2.py:
        from ospra_os.services.image_processor import enhance_product_images
        enhanced = await enhance_product_images(product)

    Returns:
        Updated product dict with image enhancements
    """
    processor = ImageProcessor()

    images = await processor.process_product_image(
        product=product,
        generate_lifestyle=True,
        optimize_original=True
    )

    # Add to product
    if images.get('lifestyle_url'):
        product['lifestyle_image_url'] = images['lifestyle_url']

    if images.get('original_optimized'):
        product['image_optimized'] = True
        # Could upload to CDN here and replace image_url

    return product
