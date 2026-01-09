"""
AI Image Generator for Oubon Shop
==================================
Generates brand-consistent product images using AI (OpenAI DALL-E 3)

IMPORTANT LIMITATION:
DALL-E 3 is TEXT-TO-IMAGE only. It cannot see or refine the original product image.
The AI generates a NEW image based on the product title and category, styled for
the Oubon Shop aesthetic. This is NOT image-to-image transformation.

To get true image refinement, you would need:
- Stability AI img2img
- Midjourney (no API)
- GPT-4 Vision + DALL-E combo (expensive)

Current approach: Generate professional lifestyle shots based on product description
that match the Oubon Shop brand aesthetic.

Features:
- E-commerce ready product shots
- Oubon Shop brand aesthetic (clean, modern, minimalist)
- Automatic prompt engineering based on product data
- Caching to avoid regenerating same products
- Fallback handling
"""

import os
import logging
import hashlib
import json
import aiohttp
import asyncio
from typing import Optional, Dict
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
STABILITY_API_KEY = os.getenv('STABILITY_API_KEY')  # Fallback option
GOOGLE_AI_API_KEY = os.getenv('GOOGLE_AI_API_KEY') or os.getenv('GEMINI_API_KEY')

# Cache directory for generated images
CACHE_DIR = Path(__file__).parent.parent.parent / "generated_images"
CACHE_DIR.mkdir(exist_ok=True)

# Oubon Shop Brand Aesthetic
BRAND_STYLE = """
Professional e-commerce product photography.
Clean white or soft neutral background.
Soft diffused studio lighting.
Modern minimalist aesthetic.
High-end lifestyle product shot.
Product clearly visible and centered.
Sharp focus, high detail.
No text, logos, watermarks, or people.
Photorealistic, 8K quality.
"""


class AIImageGenerator:
    """
    AI-powered product image generator for Oubon Shop brand consistency.
    
    NOTE: This generates NEW images based on product descriptions.
    It does NOT refine or modify the original supplier images.
    The original image URL is stored for comparison but not used in generation.
    """
    
    def __init__(self):
        self.openai_available = bool(OPENAI_API_KEY)
        self.stability_available = bool(STABILITY_API_KEY)
        self.gemini_available = bool(GOOGLE_AI_API_KEY)
        self.cache = {}
        self._load_cache()
        
        if self.openai_available:
            logger.info("[SUCCESS] AI Image Generator ready (OpenAI DALL-E 3)")
        elif self.gemini_available:
            logger.info("[SUCCESS] AI Image Generator ready (Google Gemini Imagen 3)")
        elif self.stability_available:
            logger.info("[SUCCESS] AI Image Generator ready (Stability AI)")
        else:
            logger.warning("[WARNING] AI Image Generator: No API keys found (OPENAI_API_KEY, GEMINI_API_KEY, or STABILITY_API_KEY)")
    
    def _load_cache(self):
        """Load image cache from disk"""
        cache_file = CACHE_DIR / "image_cache.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    self.cache = json.load(f)
                logger.info(f" Loaded {len(self.cache)} cached images")
            except Exception as e:
                logger.warning(f"Cache load failed: {e}")
                self.cache = {}
    
    def _save_cache(self):
        """Save image cache to disk"""
        cache_file = CACHE_DIR / "image_cache.json"
        try:
            with open(cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            logger.warning(f"Cache save failed: {e}")
    
    def _get_cache_key(self, product_title: str, niche: str) -> str:
        """Generate unique cache key for product"""
        content = f"{product_title}:{niche}".lower().strip()
        return hashlib.md5(content.encode()).hexdigest()[:16]
    
    def _build_prompt(self, product_title: str, niche: str, tags: list = None) -> str:
        """
        Build SPECIFIC prompt for product image generation.
        
        Key: Extract the actual product type from the title for accurate generation.
        """
        # Clean and extract product type from title
        clean_title = product_title.lower()
        
        # Remove marketing fluff
        fluff_words = ['hot sale', 'new', '2024', '2025', 'premium', 'quality', 
                       'best', 'cheap', 'fashion', 'free shipping', 'wholesale',
                       'dropshipping', 'for home', 'for kitchen', 'portable']
        for word in fluff_words:
            clean_title = clean_title.replace(word, '')
        
        # Clean up
        clean_title = ' '.join(clean_title.split())
        
        # Extract key product words (nouns)
        # This is a simplified extraction - ideally would use NLP
        product_words = [w for w in clean_title.split() if len(w) > 3]
        product_type = ' '.join(product_words[:5]) if product_words else clean_title
        
        # Category-specific settings
        settings = {
            "smart_home": "on a minimalist wooden desk in a modern home office",
            "lighting": "glowing softly in a cozy living room at dusk",
            "kitchen": "on a clean marble countertop in a bright modern kitchen",
            "fitness": "on a yoga mat in a bright home gym space",
            "beauty": "on a vanity with soft pink ambient lighting",
            "tech": "on a sleek desk setup with subtle RGB ambient lighting",
            "home_decor": "styled in a modern minimalist interior",
            "organization": "showing organized items in a clean space",
            "outdoor": "in natural outdoor setting with soft daylight",
            "pet": "with soft natural lighting in a cozy home",
        }
        
        setting = settings.get(niche, "in a clean modern home environment")
        
        # Build very specific prompt
        prompt = f"""Create a professional e-commerce product photograph of:

PRODUCT: {product_type}

SETTING: {setting}

STYLE REQUIREMENTS:
- Clean, uncluttered background
- Soft diffused lighting from the left
- Product is the clear focal point
- Modern, premium aesthetic matching a high-end home store
- No people, hands, or faces
- No text, watermarks, or logos
- Photorealistic style, not illustration
- Sharp product detail, slight depth of field blur on background

This is for Oubon Shop, a premium smart home and lifestyle e-commerce store.
The image should make customers want to purchase this product immediately."""

        return prompt
    
    async def generate_product_image(
        self,
        product_title: str,
        niche: str = "smart_home",
        original_image_url: str = None,
        tags: list = None,
        force_regenerate: bool = False
    ) -> Dict:
        """
        Generate AI product image for Oubon Shop aesthetic.
        
        NOTE: The original_image_url is stored but NOT used in generation.
        DALL-E 3 cannot do image-to-image. The AI creates a new image
        based purely on the text description.
        
        Args:
            product_title: Product name/title (CRITICAL for good generation)
            niche: Product category (smart_home, kitchen, etc.)
            original_image_url: Original supplier image (for reference/fallback)
            tags: Product tags for context
            force_regenerate: Skip cache and regenerate
            
        Returns:
            {
                "ai_image_url": str,  # Generated image URL
                "original_image_url": str,  # Original supplier image (unchanged)
                "prompt_used": str,  # Prompt for transparency
                "generated_at": str,
                "source": "openai" | "stability" | "cache" | "fallback",
                "note": str  # Important info about the generation
            }
        """
        cache_key = self._get_cache_key(product_title, niche)
        
        # Check cache first
        if not force_regenerate and cache_key in self.cache:
            cached = self.cache[cache_key]
            logger.info(f" Using cached image for: {product_title[:40]}...")
            return {
                **cached,
                "source": "cache",
                "original_image_url": original_image_url,
                "note": "AI-generated lifestyle image (cached). Toggle to see original."
            }
        
        # Generate prompt
        prompt = self._build_prompt(product_title, niche, tags)
        
        # Try OpenAI DALL-E 3 (Primary)
        if self.openai_available:
            result = await self._generate_openai(prompt, product_title)
            if result:
                result["original_image_url"] = original_image_url
                result["prompt_used"] = prompt
                result["note"] = "AI-generated lifestyle image. May differ from actual product. Toggle to see original."
                # Cache the result
                self.cache[cache_key] = {
                    "ai_image_url": result["ai_image_url"],
                    "generated_at": result["generated_at"],
                }
                self._save_cache()
                return result
        
        # Try Google Gemini Imagen 3 (Fallback 1)
        if self.gemini_available:
            result = await self._generate_gemini(prompt, product_title)
            if result:
                result["original_image_url"] = original_image_url
                result["prompt_used"] = prompt
                result["note"] = "AI-generated lifestyle image. May differ from actual product."
                self.cache[cache_key] = {
                    "ai_image_url": result["ai_image_url"],
                    "generated_at": result["generated_at"],
                }
                self._save_cache()
                return result
        
        # Try Stability AI as fallback (Fallback 2)
        if self.stability_available:
            result = await self._generate_stability(prompt, product_title)
            if result:
                result["original_image_url"] = original_image_url
                result["prompt_used"] = prompt
                result["note"] = "AI-generated lifestyle image."
                self.cache[cache_key] = {
                    "ai_image_url": result["ai_image_url"],
                    "generated_at": result["generated_at"],
                }
                self._save_cache()
                return result
        
        # Fallback to original image
        logger.warning(f"[WARNING] AI generation failed, using original image for: {product_title[:40]}...")
        return {
            "ai_image_url": original_image_url,  # Use original as fallback
            "original_image_url": original_image_url,
            "prompt_used": prompt,
            "generated_at": datetime.now().isoformat(),
            "source": "fallback",
            "note": "AI generation unavailable. Showing original supplier image."
        }
    
    async def _generate_openai(self, prompt: str, product_title: str) -> Optional[Dict]:
        """Generate image using OpenAI DALL-E 3"""
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
                        "style": "natural"  # More photorealistic
                    },
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        image_url = data["data"][0]["url"]
                        logger.info(f"[SUCCESS] Generated AI image (OpenAI): {product_title[:40]}...")
                        return {
                            "ai_image_url": image_url,
                            "generated_at": datetime.now().isoformat(),
                            "source": "openai"
                        }
                    else:
                        error = await response.text()
                        logger.error(f"OpenAI error ({response.status}): {error[:200]}")
                        return None
                        
        except asyncio.TimeoutError:
            logger.error("OpenAI timeout - image generation took too long")
            return None
        except Exception as e:
            logger.error(f"OpenAI generation failed: {e}")
            return None
    
    async def _generate_gemini(self, prompt: str, product_title: str) -> Optional[Dict]:
        """Generate image using Google Gemini Imagen 3"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-001:predict?key={GOOGLE_AI_API_KEY}",
                    headers={"Content-Type": "application/json"},
                    json={
                        "instances": [{"prompt": prompt}],
                        "parameters": {
                            "sampleCount": 1,
                            "aspectRatio": "1:1",
                            "safetyFilterLevel": "block_some",
                            "personGeneration": "dont_allow"
                        }
                    },
                    timeout=aiohttp.ClientTimeout(total=90)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        predictions = data.get("predictions", [])
                        if predictions and predictions[0].get("bytesBase64Encoded"):
                            import base64
                            image_data = base64.b64decode(predictions[0]["bytesBase64Encoded"])
                            
                            safe_title = product_title[:30].replace(' ', '_').replace('/', '_')
                            filename = f"gemini_{safe_title}_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
                            filepath = CACHE_DIR / filename
                            
                            with open(filepath, 'wb') as f:
                                f.write(image_data)
                            
                            logger.info(f"[SUCCESS] Generated AI image (Gemini): {product_title[:40]}...")
                            return {
                                "ai_image_url": f"/generated_images/{filename}",
                                "generated_at": datetime.now().isoformat(),
                                "source": "gemini"
                            }
                        return None
                    else:
                        error = await response.text()
                        logger.error(f"Gemini error ({response.status}): {error[:200]}")
                        return None
                        
        except asyncio.TimeoutError:
            logger.error("Gemini timeout")
            return None
        except Exception as e:
            logger.error(f"Gemini generation failed: {e}")
            return None
    
    async def _generate_stability(self, prompt: str, product_title: str) -> Optional[Dict]:
        """Generate image using Stability AI"""
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
                            {"text": "blurry, low quality, distorted, watermark, text, cartoon, illustration", "weight": -1}
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
                        import base64
                        image_data = base64.b64decode(data['artifacts'][0]['base64'])
                        
                        safe_title = product_title[:30].replace(' ', '_').replace('/', '_')
                        filename = f"stability_{safe_title}_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
                        filepath = CACHE_DIR / filename
                        
                        with open(filepath, 'wb') as f:
                            f.write(image_data)
                        
                        logger.info(f"[SUCCESS] Generated AI image (Stability): {product_title[:40]}...")
                        return {
                            "ai_image_url": f"/generated_images/{filename}",
                            "generated_at": datetime.now().isoformat(),
                            "source": "stability"
                        }
                    else:
                        error = await response.text()
                        logger.error(f"Stability error ({response.status}): {error[:200]}")
                        return None
                        
        except Exception as e:
            logger.error(f"Stability generation failed: {e}")
            return None
    
    async def generate_batch(
        self,
        products: list,
        max_concurrent: int = 3
    ) -> list:
        """Generate AI images for multiple products"""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_product(product: dict) -> dict:
            async with semaphore:
                result = await self.generate_product_image(
                    product_title=product.get('title', 'Product'),
                    niche=product.get('niche', 'smart_home'),
                    original_image_url=product.get('image_url') or product.get('main_image'),
                    tags=product.get('tags', [])
                )
                product['ai_image_url'] = result['ai_image_url']
                product['original_image_url'] = result['original_image_url']
                product['image_source'] = result['source']
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
    original_image_url: str = None
) -> str:
    """Quick function to generate a single product image"""
    generator = get_image_generator()
    result = await generator.generate_product_image(
        product_title=product_title,
        niche=niche,
        original_image_url=original_image_url
    )
    return result['ai_image_url']


async def enhance_products_with_ai_images(products: list) -> list:
    """Enhance a list of products with AI-generated images"""
    generator = get_image_generator()
    return await generator.generate_batch(products)
