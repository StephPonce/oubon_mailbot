"""
AI Image Generator for Product Lifestyle Photos
Uses DALL-E, Stable Diffusion, or other AI models to generate marketing images
"""

import os
import asyncio
import logging
from typing import Optional, List, Dict
from pathlib import Path
import requests
from io import BytesIO

logger = logging.getLogger(__name__)


class AIImageGenerator:
    """
    AI-powered image generation for product marketing

    Capabilities:
    - Generate lifestyle product photos
    - Create scene compositions with products
    - Generate marketing banners and ads
    - Product in different environments/contexts
    """

    def __init__(self):
        self.openai_key = os.getenv('OPENAI_API_KEY')
        self.stability_key = os.getenv('STABILITY_API_KEY')

        # Output directory
        self.output_dir = Path("generated_images")
        self.output_dir.mkdir(exist_ok=True)

        # Preferred provider (dalle, stability, or mock)
        self.provider = self._detect_provider()

    def _detect_provider(self) -> str:
        """Detect which AI provider to use"""
        if self.openai_key:
            return 'dalle'
        elif self.stability_key:
            return 'stability'
        else:
            logger.warning("No AI image API keys configured, using mock generation")
            return 'mock'

    async def generate_lifestyle_image(
        self,
        product_name: str,
        product_image_url: Optional[str] = None,
        scene_description: Optional[str] = None,
        style: str = 'professional'
    ) -> Optional[str]:
        """
        Generate a lifestyle image featuring the product

        Args:
            product_name: Name of the product
            product_image_url: URL to original product image (for compositing)
            scene_description: Custom scene description
            style: Image style (professional, minimal, luxury, lifestyle)

        Returns:
            URL or path to generated image
        """
        logger.info(f"🎨 Generating lifestyle image for: {product_name}")

        # Build prompt
        if not scene_description:
            scene_description = self._create_default_scene(product_name, style)

        prompt = self._build_prompt(product_name, scene_description, style)

        # Generate based on provider
        if self.provider == 'dalle':
            return await self._generate_with_dalle(prompt)
        elif self.provider == 'stability':
            return await self._generate_with_stability(prompt)
        else:
            return await self._generate_mock(product_name)

    def _create_default_scene(self, product_name: str, style: str) -> str:
        """Create default scene description based on style"""
        scenes = {
            'professional': f"Professional product photography of {product_name}, clean white background, studio lighting, high-end commercial photography, 8K resolution",
            'minimal': f"Minimalist scene with {product_name} on marble surface, soft natural lighting, plants in background, clean aesthetic, modern home",
            'luxury': f"Luxury lifestyle shot featuring {product_name}, premium materials visible, dramatic lighting, elegant composition, high-end magazine quality",
            'lifestyle': f"Authentic lifestyle photo of {product_name} in modern home, bright and airy, person using product naturally, Instagram aesthetic, warm tones"
        }

        return scenes.get(style, scenes['professional'])

    def _build_prompt(self, product_name: str, scene: str, style: str) -> str:
        """Build optimized prompt for AI generation"""
        quality_modifiers = [
            "professional photography",
            "high resolution",
            "sharp focus",
            "studio quality",
            "commercial grade",
            "photorealistic"
        ]

        # Add style-specific modifiers
        if style == 'minimal':
            quality_modifiers.extend(["clean composition", "negative space", "simple background"])
        elif style == 'luxury':
            quality_modifiers.extend(["premium aesthetic", "elegant lighting", "sophisticated"])
        elif style == 'lifestyle':
            quality_modifiers.extend(["natural lighting", "authentic", "relatable"])

        prompt = f"{scene}. {', '.join(quality_modifiers[:4])}."

        # Add negative prompt elements
        negative_elements = "blurry, low quality, distorted, amateur, watermark, text"

        return prompt

    async def _generate_with_dalle(self, prompt: str) -> Optional[str]:
        """Generate image using OpenAI DALL-E"""
        try:
            from openai import OpenAI

            client = OpenAI(api_key=self.openai_key)

            logger.info("Generating with DALL-E 3...")

            response = client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1024",
                quality="standard",
                n=1
            )

            image_url = response.data[0].url

            # Download and save locally
            local_path = await self._download_and_save(image_url, 'dalle')

            logger.info(f"✅ Generated image: {local_path}")
            return local_path

        except Exception as e:
            logger.error(f"DALL-E generation error: {e}")
            return None

    async def _generate_with_stability(self, prompt: str) -> Optional[str]:
        """Generate image using Stability AI"""
        try:
            import stability_sdk.interfaces.gooseai.generation.generation_pb2 as generation
            from stability_sdk import client

            logger.info("Generating with Stability AI...")

            stability_api = client.StabilityInference(
                key=self.stability_key,
                verbose=True,
            )

            answers = stability_api.generate(
                prompt=prompt,
                steps=50,
                cfg_scale=8.0,
                width=1024,
                height=1024,
                samples=1,
            )

            # Save first result
            for resp in answers:
                for artifact in resp.artifacts:
                    if artifact.type == generation.ARTIFACT_IMAGE:
                        img_data = artifact.binary

                        # Save to file
                        filename = f"stability_{int(time.time())}.png"
                        filepath = self.output_dir / filename

                        with open(filepath, 'wb') as f:
                            f.write(img_data)

                        logger.info(f"✅ Generated image: {filepath}")
                        return str(filepath)

            return None

        except Exception as e:
            logger.error(f"Stability AI generation error: {e}")
            return None

    async def _generate_mock(self, product_name: str) -> str:
        """Generate mock image (placeholder)"""
        # Create a simple placeholder
        filename = f"mock_{product_name.lower().replace(' ', '_')[:30]}.jpg"
        filepath = self.output_dir / filename

        # Use a placeholder image service
        placeholder_url = f"https://via.placeholder.com/1024x1024/667eea/ffffff?text={product_name[:20]}"

        try:
            response = requests.get(placeholder_url, timeout=10)
            if response.status_code == 200:
                with open(filepath, 'wb') as f:
                    f.write(response.content)

                logger.info(f"✅ Created placeholder image: {filepath}")
                return str(filepath)
        except:
            pass

        return str(filepath)

    async def _download_and_save(self, url: str, prefix: str = 'generated') -> str:
        """Download image from URL and save locally"""
        import time

        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                filename = f"{prefix}_{int(time.time())}.png"
                filepath = self.output_dir / filename

                with open(filepath, 'wb') as f:
                    f.write(response.content)

                return str(filepath)
        except Exception as e:
            logger.error(f"Download error: {e}")

        return url  # Return original URL if download fails

    async def generate_product_carousel(
        self,
        product_name: str,
        product_image_url: str,
        count: int = 4
    ) -> List[str]:
        """
        Generate a carousel of lifestyle images for product listing

        Args:
            product_name: Product name
            product_image_url: Original product image
            count: Number of images to generate

        Returns:
            List of image paths/URLs
        """
        logger.info(f"📸 Generating {count}-image carousel for {product_name}")

        styles = ['professional', 'minimal', 'luxury', 'lifestyle']
        scenes = [
            f"Close-up detail shot of {product_name}, premium materials, soft lighting",
            f"{product_name} in modern minimalist home setting, clean aesthetic",
            f"Lifestyle photo showing {product_name} in use, natural environment",
            f"Flat lay composition featuring {product_name}, top-down view, Instagram style"
        ]

        # Generate images in parallel
        tasks = []
        for i in range(min(count, 4)):
            style = styles[i % len(styles)]
            scene = scenes[i % len(scenes)]

            tasks.append(
                self.generate_lifestyle_image(
                    product_name=product_name,
                    product_image_url=product_image_url,
                    scene_description=scene,
                    style=style
                )
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out errors
        images = [r for r in results if isinstance(r, str) and r]

        logger.info(f"✅ Generated {len(images)}/{count} carousel images")
        return images

    async def generate_marketing_banner(
        self,
        product_name: str,
        campaign_type: str = 'social',
        dimensions: tuple = (1080, 1080)
    ) -> Optional[str]:
        """
        Generate marketing banner for ads

        Args:
            product_name: Product name
            campaign_type: Type of campaign (social, email, banner)
            dimensions: Image dimensions (width, height)

        Returns:
            Path to generated banner
        """
        logger.info(f"🎯 Generating {campaign_type} banner for {product_name}")

        # Different prompts for different campaign types
        prompts = {
            'social': f"Eye-catching social media post featuring {product_name}, vibrant colors, modern design, Instagram-ready, engaging composition",
            'email': f"Professional email header featuring {product_name}, clean layout, e-commerce aesthetic, promotional design",
            'banner': f"Web banner showcasing {product_name}, compelling visual, call-to-action ready, modern web design"
        }

        prompt = prompts.get(campaign_type, prompts['social'])

        # For now, use standard size (would need different API calls for custom dimensions)
        return await self._generate_with_dalle(prompt) if self.provider == 'dalle' else await self._generate_mock(product_name)

    async def enhance_product_photo(
        self,
        image_path: str,
        enhancements: List[str] = None
    ) -> Optional[str]:
        """
        Enhance existing product photo using AI

        Args:
            image_path: Path to original image
            enhancements: List of enhancements (upscale, denoise, relight)

        Returns:
            Path to enhanced image
        """
        enhancements = enhancements or ['upscale', 'denoise']

        logger.info(f"✨ Enhancing image: {image_path}")

        # This would use AI upscaling/enhancement services
        # For now, return original path
        logger.warning("Image enhancement not yet implemented")
        return image_path

    def cleanup_old_images(self, max_age_hours: int = 48):
        """Remove generated images older than specified age"""
        import time

        try:
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600

            count = 0
            for filepath in self.output_dir.glob('*'):
                if filepath.is_file():
                    file_age = current_time - filepath.stat().st_mtime
                    if file_age > max_age_seconds:
                        filepath.unlink()
                        count += 1

            if count > 0:
                logger.info(f"🗑️ Cleaned up {count} old generated images")

        except Exception as e:
            logger.error(f"Cleanup error: {e}")


# Convenience function
async def generate_product_images(
    product_name: str,
    product_image_url: str = None,
    count: int = 3,
    style: str = 'professional'
) -> List[str]:
    """
    Quick function to generate product lifestyle images

    Example:
        images = await generate_product_images(
            "Smart LED Strip Lights",
            count=3,
            style='lifestyle'
        )
    """
    generator = AIImageGenerator()

    if count == 1:
        image = await generator.generate_lifestyle_image(
            product_name=product_name,
            product_image_url=product_image_url,
            style=style
        )
        return [image] if image else []
    else:
        return await generator.generate_product_carousel(
            product_name=product_name,
            product_image_url=product_image_url or "",
            count=count
        )
