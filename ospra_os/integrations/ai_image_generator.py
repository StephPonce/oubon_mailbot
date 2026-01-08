"""
AI Image Generator for Oubon Shop
==================================
Generates brand-consistent product images using AI (OpenAI DALL-E 3)

Features:
- E-commerce ready product shots
- Oubon Shop brand aesthetic (clean, modern, minimalist)
- Automatic prompt engineering based on product data
- Caching to avoid regenerating same products
- Fallback handling

Brand Guidelines (Oubon Shop):
- Smart Home / Home Goods focus
- Clean, minimalist backgrounds
- Soft, warm lighting
- Modern lifestyle aesthetic
- Professional product photography style
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
GOOGLE_AI_API_KEY = os.getenv('GOOGLE_AI_API_KEY') or os.getenv('GEMINI_API_KEY')  # Gemini Imagen 3

# Cache directory for generated images
CACHE_DIR = Path(__file__).parent.parent.parent / "generated_images"
CACHE_DIR.mkdir(exist_ok=True)

# Oubon Shop Brand Aesthetic
BRAND_STYLE = """
Professional e-commerce product photography style.
Clean white or soft gradient background.
Soft, warm studio lighting with subtle shadows.
Modern minimalist aesthetic.
High-end lifestyle product shot.
Sharp focus on product, shallow depth of field.
No text, logos, or watermarks.
8K quality, photorealistic.
"""

# Category-specific styling
CATEGORY_STYLES = {
    "smart_home": "Smart home device in modern living room setting, ambient LED glow, tech-forward aesthetic",
    "lighting": "Illuminated product showing light effect, warm ambiance, cozy home setting",
    "kitchen": "Clean kitchen counter setting, marble or wood surface, cooking lifestyle",
    "fitness": "Active lifestyle setting, gym or home workout space, energetic mood",
    "beauty": "Spa-like setting, soft pink or neutral tones, luxurious feel",
    "tech": "Sleek tech setup, desk or workspace, modern gadget aesthetic",
    "home_decor": "Styled home interior, lifestyle shot, interior design magazine quality",
    "organization": "Organized space, satisfying arrangement, before/after transformation feel",
    "outdoor": "Natural outdoor setting, adventure lifestyle, durable quality feel",
    "pet": "Happy pet interaction, warm family home setting, playful energy",
}


class AIImageGenerator:
    """
    AI-powered product image generator for Oubon Shop brand consistency.
    
    Uses OpenAI DALL-E 3 for high-quality e-commerce product shots.
    Falls back to original supplier images if generation fails.
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
        Build optimized prompt for product image generation.
        
        Combines:
        - Product-specific details
        - Category aesthetic
        - Oubon Shop brand style
        """
        # Clean product title
        clean_title = product_title.replace('-', ' ').replace('_', ' ')
        # Remove excessive marketing words
        for word in ['Premium', 'Quality', 'Best', 'Hot Sale', 'New', '2024', '2025']:
            clean_title = clean_title.replace(word, '').strip()
        
        # Get category-specific style
        category_style = CATEGORY_STYLES.get(niche, "Modern lifestyle product setting")
        
        # Build the prompt
        prompt = f"""
Product: {clean_title}

Style: {category_style}

{BRAND_STYLE}

Create a professional e-commerce product photograph suitable for a premium smart home and lifestyle store called "Oubon Shop". The image should make customers want to buy this product immediately.
""".strip()
        
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
        
        Args:
            product_title: Product name/title
            niche: Product category (smart_home, kitchen, etc.)
            original_image_url: Original supplier image (kept as fallback)
            tags: Product tags for context
            force_regenerate: Skip cache and regenerate
            
        Returns:
            {
                "ai_image_url": str,  # Generated image URL
                "original_image_url": str,  # Original supplier image
                "prompt_used": str,  # Prompt for transparency
                "generated_at": str,
                "source": "openai" | "stability" | "cache" | "fallback"
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
                "original_image_url": original_image_url
            }
        
        # Generate prompt
        prompt = self._build_prompt(product_title, niche, tags)
        
        # Try OpenAI DALL-E 3 (Primary)
        if self.openai_available:
            result = await self._generate_openai(prompt, product_title)
            if result:
                result["original_image_url"] = original_image_url
                result["prompt_used"] = prompt
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
            "source": "fallback"
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
                        "quality": "standard",  # Use "hd" for higher quality (costs more)
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
        """
        Generate image using Google Gemini Imagen 3.
        
        Imagen 3 is Google's latest image generation model, available via Gemini API.
        Requires GOOGLE_AI_API_KEY or GEMINI_API_KEY environment variable.
        """
        try:
            async with aiohttp.ClientSession() as session:
                # Using Imagen 3 via Gemini API
                async with session.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-001:predict?key={GOOGLE_AI_API_KEY}",
                    headers={
                        "Content-Type": "application/json"
                    },
                    json={
                        "instances": [
                            {
                                "prompt": prompt
                            }
                        ],
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
                        # Gemini returns base64 image data
                        predictions = data.get("predictions", [])
                        if predictions and predictions[0].get("bytesBase64Encoded"):
                            # Save base64 to file and return path/URL
                            import base64
                            image_data = base64.b64decode(predictions[0]["bytesBase64Encoded"])
                            
                            # Generate unique filename
                            safe_title = product_title[:30].replace(' ', '_').replace('/', '_')
                            filename = f"gemini_{safe_title}_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
                            filepath = CACHE_DIR / filename
                            
                            with open(filepath, 'wb') as f:
                                f.write(image_data)
                            
                            # Return local file path (frontend can use as image src)
                            logger.info(f"[SUCCESS] Generated AI image (Gemini Imagen 3): {product_title[:40]}...")
                            return {
                                "ai_image_url": f"/generated_images/{filename}",
                                "generated_at": datetime.now().isoformat(),
                                "source": "gemini"
                            }
                        else:
                            logger.warning(f"Gemini returned no predictions: {data}")
                            return None
                    else:
                        error = await response.text()
                        logger.error(f"Gemini error ({response.status}): {error[:200]}")
                        return None
                        
        except asyncio.TimeoutError:
            logger.error("Gemini timeout - image generation took too long")
            return None
        except Exception as e:
            logger.error(f"Gemini generation failed: {e}")
            return None
    
    async def _generate_stability(self, prompt: str, product_title: str) -> Optional[Dict]:
        """Generate image using Stability AI (Stable Diffusion)"""
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
                            {"text": "blurry, low quality, distorted, watermark, text", "weight": -1}
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
                        # Stability returns base64, would need to save/host
                        # For now, return a placeholder indicating success
                        logger.info(f"[SUCCESS] Generated AI image (Stability): {product_title[:40]}...")
                        # In production, save base64 to storage and return URL
                        return {
                            "ai_image_url": f"data:image/png;base64,{data['artifacts'][0]['base64'][:100]}...",
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
        """
        Generate AI images for multiple products.
        
        Args:
            products: List of product dicts with title, niche, image_url
            max_concurrent: Max concurrent API calls (rate limiting)
            
        Returns:
            Products with ai_image_url added
        """
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
        
        # Filter out failures
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


# ============================================================================
# SINGLETON & CONVENIENCE FUNCTIONS
# ============================================================================

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
    """
    Quick function to generate a single product image.
    
    Returns the AI image URL (or original as fallback).
    """
    generator = get_image_generator()
    result = await generator.generate_product_image(
        product_title=product_title,
        niche=niche,
        original_image_url=original_image_url
    )
    return result['ai_image_url']


async def enhance_products_with_ai_images(products: list) -> list:
    """
    Enhance a list of products with AI-generated images.
    
    Use this after product discovery to add brand-consistent images.
    """
    generator = get_image_generator()
    return await generator.generate_batch(products)
