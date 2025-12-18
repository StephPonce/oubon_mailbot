"""
Ospra Intelligence - AI-Powered Image Processing Service

LEGACY: ImageProcessor - Basic DALL-E generation + optimization
NEW: ProductImageProcessor - Complete transformation pipeline with background removal

Features:
- Background removal (free, local via rembg)
- AI-generated lifestyle backgrounds (DALL-E 3)
- Intelligent compositing and branding
- Cost tracking and optimization

Usage:
    # New advanced processor
    processor = ProductImageProcessor()
    result = await processor.process_product_image(
        aliexpress_image_url="https://ae01.alicdn.com/...",
        product_name="Smart LED Strip Lights",
        niche="smart_home"
    )

    # Legacy processor (backward compatible)
    legacy = ImageProcessor()
    await legacy.generate_lifestyle_image("LED Lights", "smart_home")
"""

import os
import io
import base64
import logging
import aiohttp
from typing import Dict, Optional, List, Any
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from openai import OpenAI, AsyncOpenAI

# Configure logging FIRST
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Make rembg optional - it's a heavy dependency
try:
    from rembg import remove as rembg_remove
    REMBG_AVAILABLE = True
except ImportError:
    REMBG_AVAILABLE = False
    rembg_remove = None
    logger.warning("rembg not installed - background removal disabled. Install with: pip install rembg")


# ============================================================================
# LEGACY IMAGE PROCESSOR (Backward Compatible)
# ============================================================================

class ImageProcessor:
    """
    Process product images with AI generation and optimization.

    LEGACY CLASS - Maintained for backward compatibility.
    Use ProductImageProcessor for new features.
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
        """Generate AI lifestyle image using DALL-E."""
        if not self.openai:
            logger.warning("DALL-E not available, skipping lifestyle image")
            return None

        try:
            prompt = self._create_lifestyle_prompt(product_name, product_category)
            logger.info(f"🎨 Generating DALL-E image for: {product_name[:50]}...")

            response = self.openai.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1024",
                quality="standard",
                n=1,
            )

            image_url = response.data[0].url
            logger.info(f"✅ Generated lifestyle image")
            return image_url

        except Exception as e:
            logger.error(f"DALL-E generation failed: {e}")
            return None

    def _create_lifestyle_prompt(self, product_name: str, category: str) -> str:
        """Create optimized DALL-E prompt for product lifestyle image."""
        name_lower = product_name.lower()

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
        """Download image and optimize for web."""
        try:
            logger.info(f"📥 Downloading image from: {image_url[:60]}...")

            async with aiohttp.ClientSession() as session:
                async with session.get(image_url, timeout=15) as response:
                    if response.status != 200:
                        logger.error(f"Failed to download: HTTP {response.status}")
                        return None

                    image_data = await response.read()

            img = Image.open(io.BytesIO(image_data))

            if img.mode != 'RGB':
                if img.mode == 'RGBA':
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[3])
                    img = background
                else:
                    img = img.convert('RGB')

            target_size = self.SHOPIFY_SIZES['medium']
            img = self._resize_maintain_aspect(img, target_size)

            output = io.BytesIO()
            quality = 90
            while quality > 60:
                output.seek(0)
                output.truncate()

                img.save(
                    output,
                    format='JPEG',
                    quality=quality,
                    optimize=True,
                    progressive=True
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
        """Resize image maintaining aspect ratio, centered."""
        img_ratio = img.width / img.height
        target_ratio = target_size[0] / target_size[1]

        if img_ratio > target_ratio:
            new_width = target_size[0]
            new_height = int(new_width / img_ratio)
        else:
            new_height = target_size[1]
            new_width = int(new_height * img_ratio)

        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        canvas = Image.new('RGB', target_size, (255, 255, 255))
        x_offset = (target_size[0] - new_width) // 2
        y_offset = (target_size[1] - new_height) // 2
        canvas.paste(img, (x_offset, y_offset))

        return canvas


# ============================================================================
# NEW ADVANCED PRODUCT IMAGE PROCESSOR
# ============================================================================

# Style presets for different product niches
NICHE_STYLE_PRESETS = {
    "smart_home": {
        "prompt": "Professional product photography of a modern minimalist living room with wooden surfaces, soft natural lighting, indoor plants, and Scandinavian design aesthetic. Clean, bright, inviting atmosphere. High-end interior design magazine style.",
        "description": "Modern minimalist living room"
    },
    "tech_gadgets": {
        "prompt": "Professional product photography of a clean white desk workspace with minimal tech setup, soft diffused lighting from above, professional studio environment. Apple-style product photography aesthetic. Pristine and modern.",
        "description": "Clean modern workspace"
    },
    "home_security": {
        "prompt": "Professional product photography of a modern home entryway with warm lighting, safe and welcoming atmosphere, contemporary architecture. Clean lines, natural materials, secure feeling.",
        "description": "Modern home entryway"
    },
    "kitchen": {
        "prompt": "Professional product photography of a bright modern kitchen counter with marble surface, natural daylight streaming in, clean aesthetic, high-end kitchen design. Minimalist and elegant.",
        "description": "Bright modern kitchen"
    },
    "bedroom": {
        "prompt": "Professional product photography of a cozy modern bedroom with neutral tones, soft morning light, minimal decor. Scandinavian-inspired, peaceful, serene atmosphere.",
        "description": "Cozy modern bedroom"
    },
    "outdoor": {
        "prompt": "Professional product photography of a modern patio or garden setting with natural greenery, golden hour lighting, contemporary outdoor furniture. Warm, inviting, natural ambiance.",
        "description": "Modern patio setting"
    },
    "fitness": {
        "prompt": "Professional product photography of a clean modern home gym or yoga studio with natural light, minimalist design, wooden floors. Motivating and energizing atmosphere.",
        "description": "Modern fitness space"
    },
    "office": {
        "prompt": "Professional product photography of a sophisticated home office with natural light, modern furniture, organized workspace. Professional yet comfortable aesthetic.",
        "description": "Modern home office"
    }
}


class ProductImageProcessor:
    """
    AI-powered product image transformation service.

    Converts basic AliExpress product photos into professional lifestyle imagery
    suitable for premium e-commerce stores.

    Features:
    - FREE background removal (rembg)
    - AI lifestyle backgrounds (DALL-E 3, ~$0.04 per image)
    - Smart compositing with shadows
    - Watermarking/branding
    - Cost tracking
    """

    def __init__(self, openai_api_key: Optional[str] = None):
        """
        Initialize the image processor.

        Args:
            openai_api_key: OpenAI API key. If None, loads from OPENAI_API_KEY env var.
        """
        self.api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning("No OpenAI API key found. Background generation will fail.")

        self.client = AsyncOpenAI(api_key=self.api_key) if self.api_key else None
        self.output_dir = Path("data/processed_images")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        logger.info("ProductImageProcessor initialized")

    async def remove_background(self, image_url: str) -> Image.Image:
        """
        Download image from URL and remove background using rembg (free, local AI).

        Args:
            image_url: URL of the product image

        Returns:
            PIL Image with transparent background
        """
        logger.info(f"Removing background from: {image_url}")

        if not REMBG_AVAILABLE:
            logger.warning("rembg not installed - returning original image without background removal")
            # Just download and return the original image
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(image_url)
                    response.raise_for_status()
                    image_bytes = response.content
                return Image.open(io.BytesIO(image_bytes)).convert('RGBA')
            except Exception as e:
                logger.error(f"Failed to download image: {e}")
                raise

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(image_url)
                response.raise_for_status()
                image_bytes = response.content

            input_image = Image.open(io.BytesIO(image_bytes))
            output_image = rembg_remove(input_image)

            logger.info(f"Background removed successfully. Size: {output_image.size}")
            return output_image

        except Exception as e:
            logger.error(f"Background removal failed: {e}")
            raise

    async def generate_lifestyle_background(
        self,
        product_name: str,
        niche: str = "smart_home",
        custom_prompt: Optional[str] = None
    ) -> Image.Image:
        """
        Generate a professional lifestyle background using DALL-E 3.

        Args:
            product_name: Name of the product (for context)
            niche: Product niche (smart_home, tech_gadgets, etc.)
            custom_prompt: Optional custom prompt override

        Returns:
            PIL Image of the generated background
        """
        if not self.client:
            raise ValueError("OpenAI client not initialized. Provide API key.")

        if custom_prompt:
            prompt = custom_prompt
            description = "Custom background"
        elif niche in NICHE_STYLE_PRESETS:
            preset = NICHE_STYLE_PRESETS[niche]
            prompt = preset["prompt"]
            description = preset["description"]
        else:
            logger.warning(f"Unknown niche '{niche}', using smart_home preset")
            preset = NICHE_STYLE_PRESETS["smart_home"]
            prompt = preset["prompt"]
            description = preset["description"]

        logger.info(f"Generating {description} background for: {product_name}")

        try:
            response = await self.client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1024",
                quality="standard",
                n=1
            )

            image_url = response.data[0].url
            async with httpx.AsyncClient(timeout=30.0) as client:
                img_response = await client.get(image_url)
                img_response.raise_for_status()
                image_bytes = img_response.content

            background = Image.open(io.BytesIO(image_bytes))
            logger.info(f"Background generated successfully. Cost: ~$0.04")

            return background

        except Exception as e:
            logger.error(f"DALL-E generation failed: {e}")
            raise

    def composite_product(
        self,
        product_image: Image.Image,
        background: Image.Image,
        position: str = "center",
        scale: float = 0.6
    ) -> Image.Image:
        """
        Composite the product (with transparent background) onto the lifestyle background.

        Args:
            product_image: Product image with transparent background
            background: Lifestyle background image
            position: Where to place product ("center", "left", "right")
            scale: How much to scale the product (0.0-1.0)

        Returns:
            Composited final image
        """
        logger.info(f"Compositing product onto background (position: {position}, scale: {scale})")

        if background.mode != "RGB":
            background = background.convert("RGB")

        if product_image.mode != "RGBA":
            product_image = product_image.convert("RGBA")

        bg_width, bg_height = background.size
        prod_width, prod_height = product_image.size

        max_width = int(bg_width * scale)
        max_height = int(bg_height * scale)

        aspect_ratio = prod_width / prod_height
        if prod_width > prod_height:
            new_width = max_width
            new_height = int(new_width / aspect_ratio)
        else:
            new_height = max_height
            new_width = int(new_height * aspect_ratio)

        product_resized = product_image.resize((new_width, new_height), Image.Resampling.LANCZOS)

        if position == "center":
            x = (bg_width - new_width) // 2
            y = (bg_height - new_height) // 2
        elif position == "left":
            x = bg_width // 6
            y = (bg_height - new_height) // 2
        elif position == "right":
            x = bg_width - new_width - (bg_width // 6)
            y = (bg_height - new_height) // 2
        else:
            x = (bg_width - new_width) // 2
            y = (bg_height - new_height) // 2

        result = background.copy()

        # Add subtle shadow
        shadow = Image.new("RGBA", product_resized.size, (0, 0, 0, 0))
        shadow_alpha = product_resized.split()[3]
        shadow_alpha = ImageEnhance.Brightness(shadow_alpha).enhance(0.3)
        shadow_alpha = shadow_alpha.filter(ImageFilter.GaussianBlur(radius=10))
        shadow.putalpha(shadow_alpha)

        shadow_offset = 10
        result.paste(shadow, (x + shadow_offset, y + shadow_offset), shadow)
        result.paste(product_resized, (x, y), product_resized)

        logger.info("Product composited successfully")
        return result

    def add_branding(
        self,
        image: Image.Image,
        logo_path: Optional[str] = None,
        watermark_text: str = "OUBON SHOP",
        position: str = "bottom-right"
    ) -> Image.Image:
        """Add watermark or logo to the image."""
        logger.info(f"Adding branding: {watermark_text}")

        result = image.copy()
        width, height = result.size

        if logo_path and Path(logo_path).exists():
            try:
                logo = Image.open(logo_path)
                if logo.mode != "RGBA":
                    logo = logo.convert("RGBA")

                logo_width = width // 10
                aspect = logo.height / logo.width
                logo_height = int(logo_width * aspect)
                logo = logo.resize((logo_width, logo_height), Image.Resampling.LANCZOS)

                if position == "bottom-right":
                    x = width - logo_width - 20
                    y = height - logo_height - 20
                elif position == "bottom-left":
                    x = 20
                    y = height - logo_height - 20
                else:
                    x = width - logo_width - 20
                    y = height - logo_height - 20

                result.paste(logo, (x, y), logo)
                logger.info("Logo added successfully")
                return result

            except Exception as e:
                logger.warning(f"Failed to add logo: {e}, falling back to text watermark")

        # Text watermark
        draw = ImageDraw.Draw(result)

        try:
            font_size = max(width // 50, 16)
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
        except:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), watermark_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        if position == "bottom-right":
            x = width - text_width - 30
            y = height - text_height - 30
        elif position == "bottom-left":
            x = 30
            y = height - text_height - 30
        else:
            x = width - text_width - 30
            y = height - text_height - 30

        padding = 10
        draw.rectangle(
            [x - padding, y - padding, x + text_width + padding, y + text_height + padding],
            fill=(255, 255, 255, 180)
        )
        draw.text((x, y), watermark_text, fill=(0, 0, 0, 200), font=font)
        logger.info("Text watermark added successfully")

        return result

    async def process_product_image(
        self,
        aliexpress_image_url: str,
        product_name: str,
        niche: str = "smart_home",
        add_branding: bool = True,
        save_to_disk: bool = True,
        position: str = "center",
        scale: float = 0.6
    ) -> Dict[str, Any]:
        """
        Complete pipeline: Transform AliExpress product image into professional lifestyle photo.

        Returns:
            {
                "success": bool,
                "image_base64": str,
                "image_path": str,
                "cost_estimate": float,
                "error": str (if failed)
            }
        """
        logger.info(f"Starting image processing for: {product_name}")
        cost_estimate = 0.0

        try:
            product_no_bg = await self.remove_background(aliexpress_image_url)
            background = await self.generate_lifestyle_background(product_name, niche)
            cost_estimate += 0.04

            composited = self.composite_product(product_no_bg, background, position, scale)

            if add_branding:
                final_image = self.add_branding(composited)
            else:
                final_image = composited

            buffer = io.BytesIO()
            final_image.save(buffer, format="PNG", optimize=True)
            image_base64 = base64.b64encode(buffer.getvalue()).decode()

            image_path = None
            if save_to_disk:
                safe_name = "".join(c for c in product_name if c.isalnum() or c in (' ', '-', '_')).strip()
                safe_name = safe_name.replace(' ', '_')[:50]

                filename = f"{safe_name}_{niche}.png"
                image_path = self.output_dir / filename

                final_image.save(image_path, format="PNG", optimize=True)
                logger.info(f"Image saved to: {image_path}")

            logger.info(f"Image processing complete! Cost: ${cost_estimate:.2f}")

            return {
                "success": True,
                "image_base64": image_base64,
                "image_path": str(image_path) if image_path else None,
                "cost_estimate": cost_estimate,
                "dimensions": {
                    "width": final_image.width,
                    "height": final_image.height
                }
            }

        except Exception as e:
            logger.error(f"Image processing failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "cost_estimate": cost_estimate
            }

    def get_available_niches(self) -> list:
        """Get list of available niche style presets."""
        return list(NICHE_STYLE_PRESETS.keys())

    def get_niche_description(self, niche: str) -> str:
        """Get description of a niche style preset."""
        if niche in NICHE_STYLE_PRESETS:
            return NICHE_STYLE_PRESETS[niche]["description"]
        return "Unknown niche"


# ============================================================================
# LEGACY COMPATIBILITY FUNCTIONS
# ============================================================================

async def enhance_product_images(product: Dict) -> Dict:
    """
    Enhance product with AI-generated and optimized images.

    LEGACY FUNCTION - Uses old ImageProcessor for backward compatibility.
    """
    processor = ImageProcessor()

    images = await processor.process_product_image(
        product=product,
        generate_lifestyle=True,
        optimize_original=True
    )

    if images.get('lifestyle_url'):
        product['lifestyle_image_url'] = images['lifestyle_url']

    if images.get('original_optimized'):
        product['image_optimized'] = True

    return product


# Example usage
if __name__ == "__main__":
    import asyncio

    async def demo():
        processor = ProductImageProcessor()

        print("Available niches:", processor.get_available_niches())
        print("\nNiche descriptions:")
        for niche in processor.get_available_niches():
            print(f"  {niche}: {processor.get_niche_description(niche)}")

    asyncio.run(demo())
