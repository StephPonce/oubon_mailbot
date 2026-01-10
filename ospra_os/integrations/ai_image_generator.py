"""
AI Image Generator for Oubon Shop - V2 with Image-to-Image
==========================================================

THREE MODES:
1. TEXT-TO-IMAGE (DALL-E 3) - Generates new image from title only
2. VISION-TO-IMAGE (GPT-4V + DALL-E) - Analyzes original, generates matching styled image
3. IMAGE-TO-IMAGE (Stability AI) - Transforms original while keeping product structure

The VISION and IMG2IMG modes actually "see" the original product image,
resulting in much better matches to the actual product.
"""

import os
import logging
import hashlib
import json
import aiohttp
import asyncio
import base64
from typing import Optional, Dict, Literal
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
STABILITY_API_KEY = os.getenv('STABILITY_API_KEY')
GOOGLE_AI_API_KEY = os.getenv('GOOGLE_AI_API_KEY') or os.getenv('GEMINI_API_KEY')
CLIPDROP_API_KEY = os.getenv('CLIPDROP_API_KEY')  # Optional - for background removal

# Cache directory
CACHE_DIR = Path(__file__).parent.parent.parent / "generated_images"
CACHE_DIR.mkdir(exist_ok=True)

# Generation modes
GenerationMode = Literal["text_only", "vision_enhanced", "img2img"]


class AIImageGenerator:
    """
    Multi-mode AI image generator.
    
    Modes:
    - text_only: DALL-E 3 from title (fast, cheap, may not match product)
    - vision_enhanced: GPT-4V analyzes image → DALL-E generates (good match, more expensive)
    - img2img: Stability AI transforms image (best match, keeps product structure)
    """
    
    def __init__(self):
        self.openai_available = bool(OPENAI_API_KEY)
        self.stability_available = bool(STABILITY_API_KEY)
        self.gemini_available = bool(GOOGLE_AI_API_KEY)
        self.clipdrop_available = bool(CLIPDROP_API_KEY)
        self.cache = {}
        self._load_cache()
        
        # Log available modes
        modes = []
        if self.openai_available:
            modes.append("text_only")
            modes.append("vision_enhanced")  # GPT-4V + DALL-E
        if self.stability_available:
            modes.append("img2img")
        
        logger.info(f"[SUCCESS] AI Image Generator ready. Available modes: {modes}")
    
    def _load_cache(self):
        """Load image cache from disk"""
        cache_file = CACHE_DIR / "image_cache_v2.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    self.cache = json.load(f)
            except:
                self.cache = {}
    
    def _save_cache(self):
        """Save image cache to disk"""
        cache_file = CACHE_DIR / "image_cache_v2.json"
        try:
            with open(cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            logger.warning(f"Cache save failed: {e}")
    
    def _get_cache_key(self, product_title: str, niche: str, mode: str) -> str:
        """Generate unique cache key"""
        content = f"{product_title}:{niche}:{mode}".lower().strip()
        return hashlib.md5(content.encode()).hexdigest()[:16]
    
    async def _download_image_as_base64(self, image_url: str) -> Optional[str]:
        """Download image and convert to base64"""
        if not image_url:
            return None
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 200:
                        image_bytes = await response.read()
                        return base64.b64encode(image_bytes).decode('utf-8')
        except Exception as e:
            logger.warning(f"Failed to download image: {e}")
        return None
    
    # =========================================================================
    # MAIN GENERATION METHOD
    # =========================================================================
    
    async def generate_product_image(
        self,
        product_title: str,
        niche: str = "smart_home",
        original_image_url: str = None,
        tags: list = None,
        force_regenerate: bool = False,
        mode: GenerationMode = "vision_enhanced"  # Default to vision mode
    ) -> Dict:
        """
        Generate AI product image with multiple modes.
        
        Args:
            product_title: Product name
            niche: Category (smart_home, kitchen, etc.)
            original_image_url: Original supplier image URL
            tags: Product tags
            force_regenerate: Skip cache
            mode: Generation mode
                - "text_only": DALL-E from title (doesn't see original)
                - "vision_enhanced": GPT-4V analyzes → DALL-E generates (sees original)
                - "img2img": Stability transforms original (best match)
        """
        cache_key = self._get_cache_key(product_title, niche, mode)
        
        # Check cache
        if not force_regenerate and cache_key in self.cache:
            cached = self.cache[cache_key]
            return {
                **cached,
                "source": "cache",
                "mode": mode,
                "original_image_url": original_image_url,
            }
        
        # Choose generation method based on mode and availability
        result = None
        
        if mode == "img2img" and self.stability_available and original_image_url:
            # Best mode: Transform original image
            result = await self._generate_img2img_stability(
                product_title, niche, original_image_url
            )
        
        elif mode == "vision_enhanced" and self.openai_available and original_image_url:
            # Vision mode: GPT-4V analyzes → DALL-E generates
            result = await self._generate_vision_enhanced(
                product_title, niche, original_image_url
            )
        
        elif self.openai_available:
            # Fallback: Text-only DALL-E
            result = await self._generate_text_only_dalle(product_title, niche)
        
        elif self.stability_available:
            # Fallback: Text-only Stability
            result = await self._generate_text_only_stability(product_title, niche)
        
        # Handle result
        if result and result.get("ai_image_url"):
            result["original_image_url"] = original_image_url
            result["mode"] = mode
            # Cache
            self.cache[cache_key] = {
                "ai_image_url": result["ai_image_url"],
                "generated_at": result["generated_at"],
                "mode": mode,
            }
            self._save_cache()
            return result
        
        # Final fallback
        return {
            "ai_image_url": original_image_url,
            "original_image_url": original_image_url,
            "generated_at": datetime.now().isoformat(),
            "source": "fallback",
            "mode": "none",
            "note": "AI generation unavailable. Showing original."
        }
    
    # =========================================================================
    # MODE 1: VISION ENHANCED (GPT-4V → DALL-E 3)
    # =========================================================================
    
    async def _generate_vision_enhanced(
        self, 
        product_title: str, 
        niche: str, 
        original_image_url: str
    ) -> Optional[Dict]:
        """
        Two-step generation:
        1. GPT-4 Vision analyzes the original product image
        2. DALL-E 3 generates a new styled image based on that analysis
        
        This ensures the AI actually "sees" the product before generating.
        """
        logger.info(f"[VISION] Analyzing original image: {product_title[:40]}...")
        
        # Step 1: Analyze original image with GPT-4 Vision
        try:
            async with aiohttp.ClientSession() as session:
                # GPT-4 Vision analysis
                vision_response = await session.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OPENAI_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "gpt-4o",  # GPT-4 with vision
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": f"""Analyze this product image for e-commerce photography recreation.

Product Title: {product_title}
Category: {niche}

Describe the product in EXTREME detail for image generation:
1. What EXACTLY is the product? (specific type, shape, components)
2. What color(s) is it?
3. What material does it appear to be made of?
4. What is its approximate size/proportions?
5. Any distinctive features, buttons, lights, textures?
6. What makes this product unique?

Be VERY specific. I will use your description to generate a professional e-commerce photo.
Respond with ONLY the product description, no other text."""
                                    },
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": original_image_url,
                                            "detail": "high"
                                        }
                                    }
                                ]
                            }
                        ],
                        "max_tokens": 500
                    },
                    timeout=aiohttp.ClientTimeout(total=30)
                )
                
                if vision_response.status != 200:
                    error = await vision_response.text()
                    logger.error(f"GPT-4V error: {error[:200]}")
                    return None
                
                vision_data = await vision_response.json()
                product_description = vision_data["choices"][0]["message"]["content"]
                
                logger.info(f"[VISION] Got product description, generating image...")
                
                # Step 2: Generate with DALL-E using the detailed description
                dalle_prompt = f"""Create a professional e-commerce product photograph.

PRODUCT DESCRIPTION (from analysis of actual product):
{product_description}

PHOTOGRAPHY STYLE:
- Clean white or soft gradient background
- Professional studio lighting from left side
- Product centered and clearly visible
- Modern, premium aesthetic for a high-end home store
- Sharp focus on product details
- No people, hands, text, logos, or watermarks
- Photorealistic, magazine-quality image

This is for Oubon Shop, a premium smart home and lifestyle store."""

                dalle_response = await session.post(
                    "https://api.openai.com/v1/images/generations",
                    headers={
                        "Authorization": f"Bearer {OPENAI_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "dall-e-3",
                        "prompt": dalle_prompt,
                        "n": 1,
                        "size": "1024x1024",
                        "quality": "standard",
                        "style": "natural"
                    },
                    timeout=aiohttp.ClientTimeout(total=60)
                )
                
                if dalle_response.status == 200:
                    dalle_data = await dalle_response.json()
                    image_url = dalle_data["data"][0]["url"]
                    
                    logger.info(f"[SUCCESS] Vision-enhanced image generated: {product_title[:40]}...")
                    
                    return {
                        "ai_image_url": image_url,
                        "generated_at": datetime.now().isoformat(),
                        "source": "openai_vision",
                        "product_analysis": product_description[:200] + "...",
                        "note": "AI analyzed original product and generated matching styled image."
                    }
                else:
                    error = await dalle_response.text()
                    logger.error(f"DALL-E error: {error[:200]}")
                    return None
                    
        except Exception as e:
            logger.error(f"Vision-enhanced generation failed: {e}")
            return None
    
    # =========================================================================
    # MODE 2: IMAGE-TO-IMAGE (Stability AI)
    # =========================================================================
    
    async def _generate_img2img_stability(
        self, 
        product_title: str, 
        niche: str, 
        original_image_url: str
    ) -> Optional[Dict]:
        """
        True image-to-image transformation using Stability AI.
        
        This keeps the product structure but transforms the style/background.
        Best option for maintaining product accuracy.
        """
        logger.info(f"[IMG2IMG] Transforming original image: {product_title[:40]}...")
        
        # Download original image
        image_base64 = await self._download_image_as_base64(original_image_url)
        if not image_base64:
            logger.warning("Could not download original image for img2img")
            return None
        
        # Style prompt for transformation
        style_prompt = f"""Professional e-commerce product photo.
Clean white studio background.
Soft professional lighting.
Modern minimalist aesthetic.
Premium quality product shot for {niche.replace('_', ' ')} category.
Sharp focus, high detail.
Magazine quality photography."""

        try:
            async with aiohttp.ClientSession() as session:
                # Use Stability AI image-to-image endpoint
                form = aiohttp.FormData()
                form.add_field('init_image', 
                              base64.b64decode(image_base64),
                              filename='image.png',
                              content_type='image/png')
                form.add_field('init_image_mode', 'IMAGE_STRENGTH')
                form.add_field('image_strength', '0.35')  # 0.35 = keep most of original structure
                form.add_field('text_prompts[0][text]', style_prompt)
                form.add_field('text_prompts[0][weight]', '1')
                form.add_field('text_prompts[1][text]', 'blurry, low quality, distorted, watermark, text, cartoon')
                form.add_field('text_prompts[1][weight]', '-1')
                form.add_field('cfg_scale', '7')
                form.add_field('samples', '1')
                form.add_field('steps', '30')
                
                async with session.post(
                    "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/image-to-image",
                    headers={
                        "Authorization": f"Bearer {STABILITY_API_KEY}",
                        "Accept": "application/json"
                    },
                    data=form,
                    timeout=aiohttp.ClientTimeout(total=90)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Save the generated image
                        result_base64 = data['artifacts'][0]['base64']
                        image_bytes = base64.b64decode(result_base64)
                        
                        safe_title = product_title[:30].replace(' ', '_').replace('/', '_').replace('\\', '_')
                        filename = f"img2img_{safe_title}_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
                        filepath = CACHE_DIR / filename
                        
                        with open(filepath, 'wb') as f:
                            f.write(image_bytes)
                        
                        logger.info(f"[SUCCESS] Img2Img transformation complete: {product_title[:40]}...")
                        
                        return {
                            "ai_image_url": f"/generated_images/{filename}",
                            "generated_at": datetime.now().isoformat(),
                            "source": "stability_img2img",
                            "note": "Transformed original product image while keeping structure."
                        }
                    else:
                        error = await response.text()
                        logger.error(f"Stability img2img error ({response.status}): {error[:200]}")
                        return None
                        
        except Exception as e:
            logger.error(f"Img2Img generation failed: {e}")
            return None
    
    # =========================================================================
    # MODE 3: TEXT-ONLY (Original methods)
    # =========================================================================
    
    async def _generate_text_only_dalle(self, product_title: str, niche: str) -> Optional[Dict]:
        """Text-only DALL-E generation (doesn't see original image)"""
        
        # Clean title
        clean_title = product_title.lower()
        for word in ['hot sale', 'new', '2024', '2025', 'premium', 'quality', 'best', 'cheap']:
            clean_title = clean_title.replace(word, '')
        clean_title = ' '.join(clean_title.split())
        
        prompt = f"""Professional e-commerce product photograph of: {clean_title}

Category: {niche.replace('_', ' ')}

Style:
- Clean white or neutral background
- Professional studio lighting
- Product centered and clearly visible
- Modern minimalist aesthetic
- Sharp focus, high detail
- No people, text, or watermarks
- Photorealistic photography

For a premium smart home and lifestyle e-commerce store."""

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.openai.com/v1/images/generations",
                    headers={
                        "Authorization": f"Bearer {OPENAI_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "dall-e-3",
                        "prompt": prompt,
                        "n": 1,
                        "size": "1024x1024",
                        "quality": "standard",
                        "style": "natural"
                    },
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "ai_image_url": data["data"][0]["url"],
                            "generated_at": datetime.now().isoformat(),
                            "source": "openai_text",
                            "note": "Generated from product title only (didn't analyze original)."
                        }
                    return None
        except Exception as e:
            logger.error(f"DALL-E text generation failed: {e}")
            return None
    
    async def _generate_text_only_stability(self, product_title: str, niche: str) -> Optional[Dict]:
        """Text-only Stability generation"""
        
        clean_title = ' '.join(product_title.lower().split()[:10])
        
        prompt = f"""Professional e-commerce product photo of {clean_title}.
Clean white background, studio lighting, modern minimalist style.
Sharp focus, high detail, photorealistic."""

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image",
                    headers={
                        "Authorization": f"Bearer {STABILITY_API_KEY}",
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    },
                    json={
                        "text_prompts": [
                            {"text": prompt, "weight": 1},
                            {"text": "blurry, low quality, cartoon, watermark", "weight": -1}
                        ],
                        "cfg_scale": 7,
                        "height": 1024,
                        "width": 1024,
                        "samples": 1,
                        "steps": 30,
                    },
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        image_bytes = base64.b64decode(data['artifacts'][0]['base64'])
                        
                        safe_title = product_title[:30].replace(' ', '_').replace('/', '_')
                        filename = f"stability_{safe_title}_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
                        filepath = CACHE_DIR / filename
                        
                        with open(filepath, 'wb') as f:
                            f.write(image_bytes)
                        
                        return {
                            "ai_image_url": f"/generated_images/{filename}",
                            "generated_at": datetime.now().isoformat(),
                            "source": "stability_text",
                            "note": "Generated from product title only."
                        }
                    return None
        except Exception as e:
            logger.error(f"Stability text generation failed: {e}")
            return None
    
    # =========================================================================
    # BATCH GENERATION
    # =========================================================================
    
    async def generate_batch(
        self,
        products: list,
        max_concurrent: int = 2,  # Lower for vision mode (more API calls)
        mode: GenerationMode = "vision_enhanced"
    ) -> list:
        """Generate AI images for multiple products"""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_product(product: dict) -> dict:
            async with semaphore:
                result = await self.generate_product_image(
                    product_title=product.get('title', 'Product'),
                    niche=product.get('niche', 'smart_home'),
                    original_image_url=product.get('image_url') or product.get('main_image'),
                    tags=product.get('tags', []),
                    mode=mode
                )
                product['ai_image_url'] = result.get('ai_image_url')
                product['original_image_url'] = result.get('original_image_url')
                product['image_source'] = result.get('source', 'unknown')
                product['image_mode'] = result.get('mode', mode)
                return product
        
        tasks = [process_product(p) for p in products]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        successful = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Batch generation failed for product {i}: {result}")
                products[i]['ai_image_url'] = products[i].get('image_url')
                products[i]['image_source'] = 'fallback'
                successful.append(products[i])
            else:
                successful.append(result)
        
        return successful


# =============================================================================
# SINGLETON & CONVENIENCE FUNCTIONS
# =============================================================================

_image_generator = None

def get_image_generator() -> AIImageGenerator:
    """Get or create singleton image generator"""
    global _image_generator
    if _image_generator is None:
        _image_generator = AIImageGenerator()
    return _image_generator


async def generate_product_image(
    product_title: str,
    niche: str = "smart_home",
    original_image_url: str = None,
    mode: GenerationMode = "vision_enhanced"
) -> str:
    """Quick function to generate a single product image"""
    generator = get_image_generator()
    result = await generator.generate_product_image(
        product_title=product_title,
        niche=niche,
        original_image_url=original_image_url,
        mode=mode
    )
    return result.get('ai_image_url', original_image_url)


async def enhance_products_with_ai_images(
    products: list, 
    mode: GenerationMode = "vision_enhanced"
) -> list:
    """Enhance a list of products with AI-generated images"""
    generator = get_image_generator()
    return await generator.generate_batch(products, mode=mode)
