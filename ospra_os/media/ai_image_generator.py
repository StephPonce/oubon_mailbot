"""
AI Image Generator for Product Lifestyle Photos

HYBRID APPROACH:
- DALL-E (OpenAI): Premium hero images, highest quality
- Gemini Imagen: Bulk carousel images, cost-effective
- Stability AI: Fallback option

Author: OspraOS
Date: December 2024
"""

import os
import asyncio
import logging
import time
from typing import Optional, List, Dict
from pathlib import Path
import requests
from enum import Enum

logger = logging.getLogger(__name__)


class ImageProvider(Enum):
    """Available image generation providers."""
    DALLE = "dalle"           # OpenAI DALL-E 3 - highest quality
    GEMINI = "gemini"         # Google Imagen - cost-effective
    STABILITY = "stability"   # Stability AI - good quality
    MOCK = "mock"             # Placeholder for testing


class ImageQuality(Enum):
    """Image quality tiers for smart provider selection."""
    PREMIUM = "premium"       # Hero images, main product photo
    STANDARD = "standard"     # Carousel images, secondary photos
    BULK = "bulk"             # High volume, marketing materials


# Provider costs (approximate per image)
PROVIDER_COSTS = {
    ImageProvider.DALLE: 0.04,      # $0.04 per 1024x1024
    ImageProvider.GEMINI: 0.01,     # ~$0.01 per image (estimated)
    ImageProvider.STABILITY: 0.02,  # ~$0.02 per image
    ImageProvider.MOCK: 0.00,
}


class AIImageGenerator:
    """
    AI-powered image generation with HYBRID provider selection.
    
    Strategy:
    - Premium quality → DALL-E (best quality, higher cost)
    - Standard/Bulk → Gemini Imagen (good quality, much cheaper)
    - Fallback → Stability AI or mock
    
    Usage:
        generator = AIImageGenerator()
        
        # Auto-select provider based on quality
        hero = await generator.generate_lifestyle_image(product, quality="premium")
        carousel = await generator.generate_product_carousel(product, count=4)  # Uses bulk
    """

    def __init__(self, default_provider: Optional[str] = None):
        """Initialize with available providers."""
        self.openai_key = os.getenv('OPENAI_API_KEY')
        self.google_key = os.getenv('GOOGLE_API_KEY')
        self.stability_key = os.getenv('STABILITY_API_KEY')

        # Output directory
        self.output_dir = Path("generated_images")
        self.output_dir.mkdir(exist_ok=True)

        # Available providers (in preference order)
        self.available_providers = self._detect_providers()
        
        # Default provider override
        self.default_provider = default_provider
        
        logger.info(f"Image Generator initialized. Available: {[p.value for p in self.available_providers]}")

    @property
    def provider(self) -> Optional[str]:
        """Get current default provider name (for backward compatibility)."""
        if self.default_provider:
            return self.default_provider
        if self.available_providers:
            return self.available_providers[0].value
        return None

    def _detect_providers(self) -> List[ImageProvider]:
        """Detect which providers are configured."""
        providers = []
        
        if self.openai_key:
            providers.append(ImageProvider.DALLE)
            
        if self.google_key:
            providers.append(ImageProvider.GEMINI)
            
        if self.stability_key:
            providers.append(ImageProvider.STABILITY)
        
        # Always have mock as fallback
        providers.append(ImageProvider.MOCK)
        
        return providers

    def _select_provider(self, quality: ImageQuality) -> ImageProvider:
        """
        Select best provider based on quality tier.
        
        HYBRID LOGIC:
        - Premium → DALL-E (if available)
        - Standard → Gemini (if available), else DALL-E
        - Bulk → Gemini (cheapest), else whatever's available
        """
        if self.default_provider:
            # Override with user preference
            for p in self.available_providers:
                if p.value == self.default_provider:
                    return p
        
        if quality == ImageQuality.PREMIUM:
            # Best quality - prefer DALL-E
            for p in [ImageProvider.DALLE, ImageProvider.GEMINI, ImageProvider.STABILITY]:
                if p in self.available_providers:
                    return p
                    
        elif quality == ImageQuality.STANDARD:
            # Good quality, cost-conscious - prefer Gemini
            for p in [ImageProvider.GEMINI, ImageProvider.DALLE, ImageProvider.STABILITY]:
                if p in self.available_providers:
                    return p
                    
        elif quality == ImageQuality.BULK:
            # Cost-first - definitely Gemini
            for p in [ImageProvider.GEMINI, ImageProvider.STABILITY, ImageProvider.DALLE]:
                if p in self.available_providers:
                    return p
        
        return ImageProvider.MOCK

    async def generate_lifestyle_image(
        self,
        product_name: str,
        product_image_url: Optional[str] = None,
        scene_description: Optional[str] = None,
        style: str = 'professional',
        quality: str = 'standard'
    ) -> Optional[str]:
        """
        Generate a lifestyle image featuring the product.
        
        Args:
            product_name: Name of the product
            product_image_url: URL to original product image
            scene_description: Custom scene description
            style: Image style (professional, minimal, luxury, lifestyle)
            quality: Quality tier (premium, standard, bulk)

        Returns:
            Path to generated image
        """
        quality_enum = ImageQuality(quality) if quality in [q.value for q in ImageQuality] else ImageQuality.STANDARD
        provider = self._select_provider(quality_enum)
        
        logger.info(f" Generating {quality} image for '{product_name}' using {provider.value}")

        # Build prompt
        if not scene_description:
            scene_description = self._create_default_scene(product_name, style)

        prompt = self._build_prompt(product_name, scene_description, style)

        # Generate based on provider
        if provider == ImageProvider.DALLE:
            return await self._generate_with_dalle(prompt)
        elif provider == ImageProvider.GEMINI:
            return await self._generate_with_gemini(prompt)
        elif provider == ImageProvider.STABILITY:
            return await self._generate_with_stability(prompt)
        else:
            return await self._generate_mock(product_name)

    def _create_default_scene(self, product_name: str, style: str) -> str:
        """Create default scene description based on style."""
        scenes = {
            'professional': f"Professional product photography of {product_name}, clean white background, studio lighting, high-end commercial photography, 8K resolution",
            'minimal': f"Minimalist scene with {product_name} on marble surface, soft natural lighting, plants in background, clean aesthetic, modern home",
            'luxury': f"Luxury lifestyle shot featuring {product_name}, premium materials visible, dramatic lighting, elegant composition, high-end magazine quality",
            'lifestyle': f"Authentic lifestyle photo of {product_name} in modern home, bright and airy, person using product naturally, Instagram aesthetic, warm tones"
        }
        return scenes.get(style, scenes['professional'])

    def _build_prompt(self, product_name: str, scene: str, style: str) -> str:
        """Build optimized prompt for AI generation."""
        quality_modifiers = [
            "professional photography",
            "high resolution",
            "sharp focus",
            "studio quality",
            "commercial grade",
            "photorealistic"
        ]

        if style == 'minimal':
            quality_modifiers.extend(["clean composition", "negative space"])
        elif style == 'luxury':
            quality_modifiers.extend(["premium aesthetic", "elegant lighting"])
        elif style == 'lifestyle':
            quality_modifiers.extend(["natural lighting", "authentic"])

        return f"{scene}. {', '.join(quality_modifiers[:4])}."

    async def _generate_with_dalle(self, prompt: str) -> Optional[str]:
        """Generate image using OpenAI DALL-E 3."""
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
            local_path = await self._download_and_save(image_url, 'dalle')

            logger.info(f"[SUCCESS] DALL-E image: {local_path}")
            return local_path

        except Exception as e:
            logger.error(f"DALL-E error: {e}")
            return None

    async def _generate_with_gemini(self, prompt: str) -> Optional[str]:
        """
        Generate image using Google Gemini Imagen.
        
        Note: Uses Imagen 3 via Vertex AI or Gemini API.
        """
        try:
            import google.generativeai as genai
            
            genai.configure(api_key=self.google_key)
            logger.info("Generating with Gemini Imagen...")

            # Use Imagen model for image generation
            # Note: This requires the imagen model to be available
            model = genai.ImageGenerationModel("imagen-3.0-generate-001")
            
            response = model.generate_images(
                prompt=prompt,
                number_of_images=1,
                aspect_ratio="1:1",
                safety_filter_level="block_only_high",
                person_generation="allow_adult"
            )

            if response.images:
                # Save the image
                filename = f"gemini_{int(time.time())}.png"
                filepath = self.output_dir / filename
                
                response.images[0].save(filepath)
                
                logger.info(f"[SUCCESS] Gemini image: {filepath}")
                return str(filepath)
            
            return None

        except ImportError:
            logger.warning("google-generativeai not installed, trying REST API...")
            return await self._generate_with_gemini_rest(prompt)
        except Exception as e:
            logger.error(f"Gemini Imagen error: {e}")
            # Fallback to REST API
            return await self._generate_with_gemini_rest(prompt)

    async def _generate_with_gemini_rest(self, prompt: str) -> Optional[str]:
        """
        Generate image using Gemini REST API.
        
        Fallback if google-generativeai package has issues.
        """
        try:
            import httpx
            
            url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-001:generateImage"
            
            headers = {
                "Content-Type": "application/json",
            }
            
            params = {
                "key": self.google_key
            }
            
            payload = {
                "prompt": prompt,
                "number_of_images": 1,
                "aspect_ratio": "1:1"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers, params=params, timeout=60)
                
                if response.status_code == 200:
                    data = response.json()
                    if "images" in data and data["images"]:
                        # Decode base64 image
                        import base64
                        
                        image_data = base64.b64decode(data["images"][0]["bytesBase64Encoded"])
                        
                        filename = f"gemini_{int(time.time())}.png"
                        filepath = self.output_dir / filename
                        
                        with open(filepath, 'wb') as f:
                            f.write(image_data)
                        
                        logger.info(f"[SUCCESS] Gemini REST image: {filepath}")
                        return str(filepath)
                else:
                    logger.error(f"Gemini REST error: {response.status_code} - {response.text}")
            
            return None
            
        except Exception as e:
            logger.error(f"Gemini REST error: {e}")
            return None

    async def _generate_with_stability(self, prompt: str) -> Optional[str]:
        """Generate image using Stability AI."""
        try:
            logger.info("Generating with Stability AI...")
            
            # Using REST API for Stability
            import httpx
            
            url = "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image"
            
            headers = {
                "Authorization": f"Bearer {self.stability_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "text_prompts": [{"text": prompt, "weight": 1}],
                "cfg_scale": 8,
                "height": 1024,
                "width": 1024,
                "steps": 50,
                "samples": 1
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers, timeout=60)
                
                if response.status_code == 200:
                    data = response.json()
                    if "artifacts" in data and data["artifacts"]:
                        import base64
                        
                        image_data = base64.b64decode(data["artifacts"][0]["base64"])
                        
                        filename = f"stability_{int(time.time())}.png"
                        filepath = self.output_dir / filename
                        
                        with open(filepath, 'wb') as f:
                            f.write(image_data)
                        
                        logger.info(f"[SUCCESS] Stability image: {filepath}")
                        return str(filepath)
            
            return None

        except Exception as e:
            logger.error(f"Stability AI error: {e}")
            return None

    async def _generate_mock(self, product_name: str) -> str:
        """Generate placeholder image."""
        filename = f"mock_{product_name.lower().replace(' ', '_')[:30]}.jpg"
        filepath = self.output_dir / filename

        placeholder_url = f"https://via.placeholder.com/1024x1024/667eea/ffffff?text={product_name[:20]}"

        try:
            response = requests.get(placeholder_url, timeout=10)
            if response.status_code == 200:
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                logger.info(f"[SUCCESS] Mock image: {filepath}")
                return str(filepath)
        except:
            pass

        return str(filepath)

    async def _download_and_save(self, url: str, prefix: str = 'generated') -> str:
        """Download image from URL and save locally."""
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

        return url

    async def generate_product_carousel(
        self,
        product_name: str,
        product_image_url: str = "",
        count: int = 4,
        quality: str = "bulk"  # Default to bulk for carousel
    ) -> List[str]:
        """
        Generate a carousel of lifestyle images - uses BULK quality (Gemini) by default.
        
        This is where the cost savings happen!
        """
        logger.info(f" Generating {count}-image carousel for {product_name} (quality: {quality})")

        styles = ['professional', 'minimal', 'luxury', 'lifestyle']
        scenes = [
            f"Close-up detail shot of {product_name}, premium materials, soft lighting",
            f"{product_name} in modern minimalist home setting, clean aesthetic",
            f"Lifestyle photo showing {product_name} in use, natural environment",
            f"Flat lay composition featuring {product_name}, top-down view, Instagram style"
        ]

        tasks = []
        for i in range(min(count, 4)):
            style = styles[i % len(styles)]
            scene = scenes[i % len(scenes)]

            tasks.append(
                self.generate_lifestyle_image(
                    product_name=product_name,
                    product_image_url=product_image_url,
                    scene_description=scene,
                    style=style,
                    quality=quality  # Uses bulk by default
                )
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)
        images = [r for r in results if isinstance(r, str) and r]

        logger.info(f"[SUCCESS] Generated {len(images)}/{count} carousel images")
        return images

    async def generate_hero_image(
        self,
        product_name: str,
        product_image_url: str = "",
        style: str = "professional"
    ) -> Optional[str]:
        """
        Generate a premium hero image - uses DALL-E for best quality.
        """
        return await self.generate_lifestyle_image(
            product_name=product_name,
            product_image_url=product_image_url,
            style=style,
            quality="premium"  # Forces DALL-E
        )

    def estimate_cost(self, hero_count: int = 1, carousel_count: int = 4) -> Dict[str, float]:
        """
        Estimate cost for image generation.
        
        Returns breakdown by provider and total.
        """
        hero_provider = self._select_provider(ImageQuality.PREMIUM)
        bulk_provider = self._select_provider(ImageQuality.BULK)
        
        hero_cost = hero_count * PROVIDER_COSTS.get(hero_provider, 0.04)
        carousel_cost = carousel_count * PROVIDER_COSTS.get(bulk_provider, 0.01)
        
        return {
            "hero_provider": hero_provider.value,
            "hero_count": hero_count,
            "hero_cost": hero_cost,
            "carousel_provider": bulk_provider.value,
            "carousel_count": carousel_count,
            "carousel_cost": carousel_cost,
            "total_cost": hero_cost + carousel_cost,
            "vs_all_dalle": (hero_count + carousel_count) * 0.04,
            "savings": ((hero_count + carousel_count) * 0.04) - (hero_cost + carousel_cost)
        }

    def cleanup_old_images(self, max_age_hours: int = 48):
        """Remove generated images older than specified age."""
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
                logger.info(f" Cleaned up {count} old generated images")

        except Exception as e:
            logger.error(f"Cleanup error: {e}")


# Convenience function
async def generate_product_images(
    product_name: str,
    product_image_url: str = None,
    count: int = 3,
    style: str = 'professional',
    quality: str = 'standard'
) -> List[str]:
    """
    Quick function to generate product lifestyle images.
    
    Example:
        images = await generate_product_images(
            "Smart LED Strip Lights",
            count=3,
            style='lifestyle',
            quality='bulk'  # Uses Gemini for cost savings
        )
    """
    generator = AIImageGenerator()

    if count == 1:
        image = await generator.generate_lifestyle_image(
            product_name=product_name,
            product_image_url=product_image_url,
            style=style,
            quality=quality
        )
        return [image] if image else []
    else:
        return await generator.generate_product_carousel(
            product_name=product_name,
            product_image_url=product_image_url or "",
            count=count,
            quality=quality
        )
