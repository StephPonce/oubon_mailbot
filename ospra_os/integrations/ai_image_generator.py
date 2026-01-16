"""
AI Image Generator for Oubon Shop - V3 with Multi-Image Support
================================================================

THREE MODES:
1. TEXT-TO-IMAGE (DALL-E 3) - Generates new image from title only
2. VISION-TO-IMAGE (GPT-4V + DALL-E) - Analyzes original(s), generates matching styled image
3. IMAGE-TO-IMAGE (Stability AI) - Transforms original while keeping product structure

V3 IMPROVEMENTS:
- Multi-image input support (feed multiple product angles)
- Enhanced prompts with more specific style guidance
- Better error handling with detailed logging
- Niche-specific styling
"""

import os
import logging
import hashlib
import json
import aiohttp
import asyncio
import base64
from typing import Optional, Dict, List, Literal
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION - Use functions to get keys at RUNTIME, not import time
# ============================================================================

def get_openai_key() -> str:
    """Get OpenAI API key at runtime"""
    return os.getenv('OPENAI_API_KEY', '')

def get_stability_key() -> str:
    """Get Stability AI API key at runtime"""
    return os.getenv('STABILITY_API_KEY', '')

def get_google_ai_key() -> str:
    """Get Google AI API key at runtime"""
    return os.getenv('GOOGLE_AI_API_KEY') or os.getenv('GEMINI_API_KEY') or ''

def get_clipdrop_key() -> str:
    """Get ClipDrop API key at runtime"""
    return os.getenv('CLIPDROP_API_KEY', '')

# Legacy constants for backwards compatibility (will be empty at import time)
# Use the get_*_key() functions instead for reliable access
OPENAI_API_KEY = None  # Use get_openai_key()
STABILITY_API_KEY = None  # Use get_stability_key()
GOOGLE_AI_API_KEY = None  # Use get_google_ai_key()
CLIPDROP_API_KEY = None  # Use get_clipdrop_key()

# Cache directory
CACHE_DIR = Path(__file__).parent.parent.parent / "generated_images"
CACHE_DIR.mkdir(exist_ok=True)

# Generation modes
GenerationMode = Literal["text_only", "vision_enhanced", "img2img"]

# ============================================================================
# NICHE-SPECIFIC PROMPTS - The Secret Sauce
# ============================================================================

NICHE_STYLE_GUIDES = {
    "smart_home": {
        "aesthetic": "modern tech minimalist",
        "background": "clean white or soft gray gradient",
        "lighting": "cool-toned LED-style ambient glow, soft shadows",
        "props": "subtle smart home context (wooden desk, modern shelf)",
        "mood": "futuristic yet welcoming, premium tech lifestyle",
        "colors": "emphasize whites, blacks, cool blues, subtle metallics"
    },
    "kitchen": {
        "aesthetic": "warm culinary lifestyle",
        "background": "marble countertop or light wood surface",
        "lighting": "warm natural daylight from window",
        "props": "fresh ingredients, herbs, or minimal kitchenware",
        "mood": "appetizing, homey, professional chef quality",
        "colors": "warm whites, natural wood tones, fresh greens"
    },
    "fitness": {
        "aesthetic": "energetic athletic lifestyle",
        "background": "gym setting or clean studio with subtle texture",
        "lighting": "dramatic side lighting, dynamic shadows",
        "props": "workout mat, water bottle, gym floor",
        "mood": "motivating, powerful, premium athletic gear",
        "colors": "bold blacks, energetic reds/oranges, clean whites"
    },
    "beauty": {
        "aesthetic": "luxurious spa-like elegance",
        "background": "soft pink/white marble or clean vanity",
        "lighting": "soft diffused beauty lighting, no harsh shadows",
        "props": "rose petals, silk fabric, golden accents",
        "mood": "luxurious, feminine, self-care indulgence",
        "colors": "soft pinks, golds, clean whites, subtle metallics"
    },
    "home_decor": {
        "aesthetic": "cozy modern interior",
        "background": "styled living room vignette or clean shelf",
        "lighting": "warm golden hour natural light",
        "props": "plants, books, textured throws, candles",
        "mood": "inviting, Instagram-worthy, aspirational living",
        "colors": "earth tones, warm neutrals, natural textures"
    },
    "tech": {
        "aesthetic": "sleek premium electronics",
        "background": "dark gradient or clean desk setup",
        "lighting": "dramatic product lighting with subtle reflections",
        "props": "minimal - focus on product",
        "mood": "cutting-edge, premium, professional",
        "colors": "deep blacks, silver metallics, accent RGB if applicable"
    },
    "outdoor": {
        "aesthetic": "adventure lifestyle",
        "background": "natural outdoor setting or rustic wood",
        "lighting": "natural daylight, golden hour preferred",
        "props": "camping gear context, nature elements",
        "mood": "rugged yet refined, adventure-ready",
        "colors": "earth tones, forest greens, sky blues"
    },
    "pet": {
        "aesthetic": "playful pet lifestyle",
        "background": "cozy home setting or clean studio",
        "lighting": "soft natural light, warm and inviting",
        "props": "pet toys, treats, cozy bed context",
        "mood": "loving, playful, premium pet care",
        "colors": "warm neutrals, playful pops of color"
    }
}

# Default for unknown niches
DEFAULT_STYLE = {
    "aesthetic": "premium e-commerce",
    "background": "clean white studio",
    "lighting": "professional three-point lighting",
    "props": "minimal, product-focused",
    "mood": "premium quality, trustworthy",
    "colors": "clean whites, subtle shadows"
}


def get_style_guide(niche: str) -> Dict:
    """Get niche-specific style guide"""
    return NICHE_STYLE_GUIDES.get(niche.lower().replace(' ', '_'), DEFAULT_STYLE)


class AIImageGenerator:
    """
    Multi-mode AI image generator with multi-image support.
    
    V3 Features:
    - Accepts multiple product images for better context
    - Niche-specific styling prompts
    - Detailed error logging for debugging
    - Runtime API key loading (not cached at import time)
    """
    
    def __init__(self):
        # Check API keys at RUNTIME, not import time
        self._refresh_api_status()
        self.cache = {}
        self._load_cache()
        
        # Log configuration status
        logger.info(f"[AI IMAGE GENERATOR V3] Initializing...")
        logger.info(f"  OpenAI: {'✅ Available' if self.openai_available else '❌ Not configured'}")
        logger.info(f"  Stability AI: {'✅ Available' if self.stability_available else '❌ Not configured'}")
        logger.info(f"  Gemini: {'✅ Available' if self.gemini_available else '❌ Not configured'}")
        
        if self.stability_available:
            key = get_stability_key()
            logger.info(f"  Stability Key: {key[:15]}...{key[-4:]}")
    
    def _refresh_api_status(self):
        """Refresh API availability status (checks env vars at runtime)"""
        self.openai_available = bool(get_openai_key())
        self.stability_available = bool(get_stability_key())
        self.gemini_available = bool(get_google_ai_key())
        self.clipdrop_available = bool(get_clipdrop_key())
    
    def _load_cache(self):
        """Load image cache from disk"""
        cache_file = CACHE_DIR / "image_cache_v3.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    self.cache = json.load(f)
            except:
                self.cache = {}
    
    def _save_cache(self):
        """Save image cache to disk"""
        cache_file = CACHE_DIR / "image_cache_v3.json"
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
        """Download image and convert to base64 with detailed error handling"""
        if not image_url:
            logger.warning("[DOWNLOAD] No image URL provided")
            return None
            
        logger.info(f"[DOWNLOAD] Fetching image: {image_url[:80]}...")
        
        try:
            # Handle various URL formats
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Accept': 'image/*,*/*;q=0.8',
                'Referer': 'https://www.aliexpress.com/'  # Some CDNs need this
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    image_url, 
                    timeout=aiohttp.ClientTimeout(total=30),
                    headers=headers,
                    allow_redirects=True
                ) as response:
                    logger.info(f"[DOWNLOAD] Response status: {response.status}")
                    
                    if response.status == 200:
                        image_bytes = await response.read()
                        logger.info(f"[DOWNLOAD] Success! Image size: {len(image_bytes)} bytes")
                        
                        if len(image_bytes) < 1000:
                            logger.warning(f"[DOWNLOAD] Image too small, might be error page")
                            return None
                            
                        return base64.b64encode(image_bytes).decode('utf-8')
                    else:
                        error_text = await response.text()
                        logger.error(f"[DOWNLOAD] Failed with status {response.status}: {error_text[:200]}")
                        return None
                        
        except asyncio.TimeoutError:
            logger.error(f"[DOWNLOAD] Timeout downloading image")
            return None
        except Exception as e:
            logger.error(f"[DOWNLOAD] Error: {type(e).__name__}: {e}")
            return None
    
    async def _download_multiple_images(self, image_urls: List[str], max_images: int = 3) -> List[str]:
        """Download multiple images and return as base64 list"""
        valid_urls = [url for url in image_urls if url][:max_images]
        
        if not valid_urls:
            return []
        
        logger.info(f"[MULTI-IMAGE] Downloading {len(valid_urls)} images...")
        
        tasks = [self._download_image_as_base64(url) for url in valid_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter successful downloads
        images = []
        for i, result in enumerate(results):
            if isinstance(result, str) and result:
                images.append(result)
                logger.info(f"[MULTI-IMAGE] Image {i+1} downloaded successfully")
            else:
                logger.warning(f"[MULTI-IMAGE] Image {i+1} failed")
        
        logger.info(f"[MULTI-IMAGE] Successfully downloaded {len(images)}/{len(valid_urls)} images")
        return images
    
    # =========================================================================
    # ENHANCED PROMPT BUILDERS
    # =========================================================================
    
    def _build_vision_analysis_prompt(self, product_title: str, niche: str, num_images: int = 1) -> str:
        """Build detailed prompt for GPT-4V image analysis"""
        style = get_style_guide(niche)
        
        image_context = "this product image" if num_images == 1 else f"these {num_images} product images from different angles"
        
        return f"""You are an expert e-commerce product photographer preparing to recreate {image_context}.

PRODUCT: {product_title}
CATEGORY: {niche.replace('_', ' ').title()}
TARGET BRAND: Oubon Shop (premium smart home & lifestyle)

Analyze {image_context} and provide an EXTREMELY DETAILED description for image generation:

**PRODUCT IDENTIFICATION**
- What is this product exactly? (be specific: type, model style, category)
- What is its primary function/use case?

**PHYSICAL ATTRIBUTES**
- Exact colors (primary, secondary, accent)
- Materials (plastic, metal, fabric, glass, wood?)
- Shape and form factor (cylindrical, rectangular, organic?)
- Approximate dimensions/proportions
- Surface finish (matte, glossy, textured, brushed?)

**DISTINCTIVE FEATURES**
- Buttons, dials, displays, lights, indicators
- Ports, openings, vents, grilles
- Branding location (if visible)
- Any unique design elements

**COMPOSITION NOTES**
- How should this product be positioned?
- What angle shows it best?
- Any parts that should be highlighted?

Be EXTREMELY specific and visual. I will use this description to generate a professional product photo.
Write in detailed, visual language as if instructing a photographer."""

    def _build_dalle_prompt(self, product_analysis: str, niche: str, product_title: str) -> str:
        """Build DALL-E prompt using GPT-4V analysis + niche styling"""
        style = get_style_guide(niche)
        
        return f"""Create a STUNNING professional e-commerce product photograph.

**PRODUCT** (from expert analysis):
{product_analysis}

**BRAND AESTHETIC: Oubon Shop**
Style: {style['aesthetic']}
Background: {style['background']}
Lighting: {style['lighting']}
Props/Context: {style['props']}
Mood: {style['mood']}
Color Palette: {style['colors']}

**PHOTOGRAPHY REQUIREMENTS**
- Hero product shot, product is the clear star
- Product perfectly centered and in sharp focus
- Professional studio quality, magazine-worthy
- Clean composition with breathing room
- Subtle shadows adding depth and dimension
- Colors accurate and vibrant

**ABSOLUTE RESTRICTIONS**
- NO people, hands, or body parts
- NO text, watermarks, logos, or labels on image
- NO cluttered backgrounds
- NO distortions or unrealistic proportions
- NO cartoonish or AI-looking artifacts

Create an image that would make customers click "Add to Cart" immediately."""

    def _build_stability_prompt(self, product_title: str, niche: str) -> str:
        """Build Stability AI prompt for img2img transformation"""
        style = get_style_guide(niche)
        
        return f"""Transform this product photo into a premium e-commerce hero shot.

Style: {style['aesthetic']}
Background: {style['background']}
Lighting: {style['lighting']}
Mood: {style['mood']}

Keep the exact product shape and details.
Enhance the background and lighting only.
Professional studio quality.
Clean, modern, premium feel.
Magazine-quality product photography.
{niche.replace('_', ' ').title()} category aesthetic."""

    def _build_text_only_prompt(self, product_title: str, niche: str) -> str:
        """Build detailed prompt for text-only generation"""
        style = get_style_guide(niche)
        
        # Clean up title
        clean_title = product_title.lower()
        for word in ['hot sale', 'new', '2024', '2025', 'premium', 'quality', 'best', 'cheap', 'free shipping']:
            clean_title = clean_title.replace(word, '')
        clean_title = ' '.join(clean_title.split()).title()
        
        return f"""Create a professional e-commerce product photograph.

**PRODUCT**: {clean_title}
**CATEGORY**: {niche.replace('_', ' ').title()}

**BRAND AESTHETIC (Oubon Shop)**
Overall Style: {style['aesthetic']}
Background: {style['background']}
Lighting: {style['lighting']}
Props/Context: {style['props']}
Mood: {style['mood']}
Colors: {style['colors']}

**PHOTOGRAPHY STYLE**
- Hero product shot, product as the star
- Clean professional studio photography
- Product centered with perfect focus
- Subtle shadows for depth
- Premium, aspirational quality
- Magazine or catalog worthy

**RESTRICTIONS**
- NO people or hands
- NO text or watermarks
- NO cluttered composition
- NO cartoonish look

Photorealistic, premium quality product photography."""

    # =========================================================================
    # MAIN GENERATION METHOD
    # =========================================================================
    
    async def generate_product_image(
        self,
        product_title: str,
        niche: str = "smart_home",
        original_image_url: str = None,
        additional_image_urls: List[str] = None,  # NEW: Multiple images
        tags: list = None,
        force_regenerate: bool = False,
        mode: GenerationMode = "vision_enhanced"
    ) -> Dict:
        """
        Generate AI product image with multiple modes and multi-image support.
        
        Args:
            product_title: Product name
            niche: Category (smart_home, kitchen, etc.)
            original_image_url: Primary product image URL
            additional_image_urls: Additional angles/views (NEW)
            tags: Product tags
            force_regenerate: Skip cache
            mode: Generation mode
        """
        cache_key = self._get_cache_key(product_title, niche, mode)
        
        # Check cache
        if not force_regenerate and cache_key in self.cache:
            cached = self.cache[cache_key]
            logger.info(f"[CACHE HIT] Returning cached image for: {product_title[:40]}")
            return {
                **cached,
                "source": "cache",
                "mode": mode,
                "original_image_url": original_image_url,
            }
        
        # Collect all image URLs
        all_image_urls = []
        if original_image_url:
            all_image_urls.append(original_image_url)
        if additional_image_urls:
            all_image_urls.extend(additional_image_urls)
        
        logger.info(f"[GENERATE] Mode: {mode}, Product: {product_title[:40]}, Images: {len(all_image_urls)}")
        
        # Choose generation method
        result = None
        
        if mode == "img2img" and self.stability_available and original_image_url:
            result = await self._generate_img2img_stability(
                product_title, niche, original_image_url
            )
        
        elif mode == "vision_enhanced" and self.openai_available and all_image_urls:
            result = await self._generate_vision_enhanced(
                product_title, niche, all_image_urls
            )
        
        elif self.openai_available:
            result = await self._generate_text_only_dalle(product_title, niche)
        
        elif self.stability_available:
            result = await self._generate_text_only_stability(product_title, niche)
        
        # Handle result
        if result and result.get("ai_image_url"):
            result["original_image_url"] = original_image_url
            result["mode"] = mode
            result["images_analyzed"] = len(all_image_urls)
            
            # Cache successful result
            self.cache[cache_key] = {
                "ai_image_url": result["ai_image_url"],
                "generated_at": result["generated_at"],
                "mode": mode,
            }
            self._save_cache()
            return result
        
        # Final fallback
        logger.warning(f"[FALLBACK] All generation methods failed for: {product_title[:40]}")
        return {
            "ai_image_url": original_image_url,
            "original_image_url": original_image_url,
            "generated_at": datetime.now().isoformat(),
            "source": "fallback",
            "mode": "none",
            "note": "AI generation unavailable. Showing original.",
            "images_analyzed": 0
        }
    
    # =========================================================================
    # MODE 1: VISION ENHANCED (GPT-4V → DALL-E 3) - Multi-Image Support
    # =========================================================================
    
    async def _generate_vision_enhanced(
        self, 
        product_title: str, 
        niche: str, 
        image_urls: List[str]
    ) -> Optional[Dict]:
        """
        Vision-enhanced generation with multi-image support.
        
        1. GPT-4V analyzes up to 3 product images
        2. Creates detailed product description
        3. DALL-E 3 generates styled image from description
        """
        num_images = min(len(image_urls), 3)  # Max 3 images
        logger.info(f"[VISION] Analyzing {num_images} image(s): {product_title[:40]}...")
        
        # Build content array with text + multiple images
        content = [
            {
                "type": "text",
                "text": self._build_vision_analysis_prompt(product_title, niche, num_images)
            }
        ]
        
        # Add images to content
        for i, url in enumerate(image_urls[:3]):
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": url,
                    "detail": "high"
                }
            })
            logger.info(f"[VISION] Added image {i+1}: {url[:60]}...")
        
        try:
            async with aiohttp.ClientSession() as session:
                # Step 1: GPT-4V Analysis
                logger.info("[VISION] Calling GPT-4V for analysis...")
                vision_response = await session.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {get_openai_key()}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "gpt-4o",
                        "messages": [{"role": "user", "content": content}],
                        "max_tokens": 800
                    },
                    timeout=aiohttp.ClientTimeout(total=45)
                )
                
                if vision_response.status != 200:
                    error = await vision_response.text()
                    logger.error(f"[VISION] GPT-4V error {vision_response.status}: {error[:300]}")
                    return None
                
                vision_data = await vision_response.json()
                product_analysis = vision_data["choices"][0]["message"]["content"]
                logger.info(f"[VISION] Analysis complete ({len(product_analysis)} chars)")
                
                # Step 2: DALL-E Generation
                dalle_prompt = self._build_dalle_prompt(product_analysis, niche, product_title)
                logger.info("[VISION] Calling DALL-E 3 for generation...")
                
                dalle_response = await session.post(
                    "https://api.openai.com/v1/images/generations",
                    headers={
                        "Authorization": f"Bearer {get_openai_key()}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "dall-e-3",
                        "prompt": dalle_prompt,
                        "n": 1,
                        "size": "1024x1024",
                        "quality": "hd",  # Higher quality
                        "style": "natural"
                    },
                    timeout=aiohttp.ClientTimeout(total=90)
                )
                
                if dalle_response.status == 200:
                    dalle_data = await dalle_response.json()
                    image_url = dalle_data["data"][0]["url"]
                    
                    logger.info(f"[VISION] ✅ Success! Image generated")
                    
                    return {
                        "ai_image_url": image_url,
                        "generated_at": datetime.now().isoformat(),
                        "source": "openai_vision",
                        "product_analysis": product_analysis[:300] + "...",
                        "note": f"AI analyzed {num_images} image(s) and generated matching styled photo.",
                        "prompt_used": dalle_prompt[:500] + "..."
                    }
                else:
                    error = await dalle_response.text()
                    logger.error(f"[VISION] DALL-E error {dalle_response.status}: {error[:300]}")
                    return None
                    
        except Exception as e:
            logger.error(f"[VISION] Exception: {type(e).__name__}: {e}")
            return None
    
    # =========================================================================
    # MODE 2: IMAGE-TO-IMAGE (Stability AI) - Updated for Latest API
    # =========================================================================
    
    async def _generate_img2img_stability(self,  product_title: str, niche: str, original_image_url: str) -> Optional[Dict]:
        """
        Stability AI img2img with detailed error handling.
        
        Supports both:
        - Legacy v1 API (stable-diffusion-xl-1024-v1-0)
        - New Stable Image API v2beta (if v1 fails)
        """
        logger.info(f"[IMG2IMG] Starting transformation: {product_title[:40]}...")
        
        stability_key = get_stability_key()
        if not stability_key:
            logger.error("[IMG2IMG] ❌ STABILITY_API_KEY not configured!")
            logger.error("[IMG2IMG]    Get your key at: https://platform.stability.ai/account/keys")
            return None
        
        logger.info(f"[IMG2IMG] Using API key: {stability_key[:15]}...{stability_key[-4:]}")
        
        # Store for use in sub-methods
        self._current_stability_key = stability_key
        
        # Download original image
        logger.info(f"[IMG2IMG] Downloading source image...")
        image_base64 = await self._download_image_as_base64(original_image_url)
        
        if not image_base64:
            logger.error("[IMG2IMG] ❌ Failed to download source image")
            return None
        
        # Decode for size check
        image_bytes = base64.b64decode(image_base64)
        logger.info(f"[IMG2IMG] Image downloaded: {len(image_bytes):,} bytes")
        
        # Build prompt
        style_prompt = self._build_stability_prompt(product_title, niche)
        logger.info(f"[IMG2IMG] Prompt: {style_prompt[:100]}...")
        
        # Try v1 API first, then fall back to v2beta
        result = await self._try_stability_v1_img2img(image_bytes, style_prompt, product_title)
        
        if not result:
            logger.info("[IMG2IMG] v1 API failed, trying v2beta...")
            result = await self._try_stability_v2_img2img(image_bytes, style_prompt, product_title)
        
        return result
    
    async def _try_stability_v1_img2img(
        self,
        image_bytes: bytes,
        style_prompt: str,
        product_title: str
    ) -> Optional[Dict]:
        """
        Try Stability AI v1 API (legacy but still works for many use cases)
        """
        try:
            async with aiohttp.ClientSession() as session:
                form = aiohttp.FormData()
                form.add_field(
                    'init_image', 
                    image_bytes,
                    filename='image.png',
                    content_type='image/png'
                )
                form.add_field('init_image_mode', 'IMAGE_STRENGTH')
                form.add_field('image_strength', '0.35')  # Keep most of original
                form.add_field('text_prompts[0][text]', style_prompt)
                form.add_field('text_prompts[0][weight]', '1')
                form.add_field('text_prompts[1][text]', 
                              'blurry, low quality, distorted, watermark, text, logo, cartoon, illustration, drawing, painting, sketch')
                form.add_field('text_prompts[1][weight]', '-1')
                form.add_field('cfg_scale', '7')
                form.add_field('samples', '1')
                form.add_field('steps', '30')
                
                logger.info("[IMG2IMG] Calling Stability AI v1 API...")
                
                async with session.post(
                    "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/image-to-image",
                    headers={
                        "Authorization": f"Bearer {get_stability_key()}",
                        "Accept": "application/json"
                    },
                    data=form,
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as response:
                    logger.info(f"[IMG2IMG] v1 Response status: {response.status}")
                    
                    if response.status == 200:
                        data = await response.json()
                        return await self._save_stability_result(data, product_title, "v1")
                    else:
                        error_text = await response.text()
                        logger.error(f"[IMG2IMG] v1 API error {response.status}: {error_text[:300]}")
                        self._log_stability_error(response.status, error_text)
                        return None
                        
        except asyncio.TimeoutError:
            logger.error("[IMG2IMG] v1 request timed out after 120 seconds")
            return None
        except Exception as e:
            logger.error(f"[IMG2IMG] v1 exception: {type(e).__name__}: {e}")
            return None
    
    async def _try_stability_v2_img2img(
        self,
        image_bytes: bytes,
        style_prompt: str,
        product_title: str
    ) -> Optional[Dict]:
        """
        Try Stability AI v2beta API (newer, more reliable)
        Uses the image-to-image/upscale endpoints
        """
        try:
            async with aiohttp.ClientSession() as session:
                form = aiohttp.FormData()
                form.add_field(
                    'image', 
                    image_bytes,
                    filename='image.png',
                    content_type='image/png'
                )
                form.add_field('prompt', style_prompt)
                form.add_field('negative_prompt', 
                              'blurry, low quality, distorted, watermark, text, logo, cartoon')
                form.add_field('strength', '0.35')
                form.add_field('output_format', 'png')
                
                logger.info("[IMG2IMG] Calling Stability AI v2beta API...")
                
                async with session.post(
                    "https://api.stability.ai/v2beta/stable-image/generate/sd3",
                    headers={
                        "Authorization": f"Bearer {get_stability_key()}",
                        "Accept": "image/*"
                    },
                    data=form,
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as response:
                    logger.info(f"[IMG2IMG] v2beta Response status: {response.status}")
                    
                    if response.status == 200:
                        # v2beta returns raw image bytes
                        result_bytes = await response.read()
                        return await self._save_stability_bytes(result_bytes, product_title, "v2beta")
                    else:
                        error_text = await response.text()
                        logger.error(f"[IMG2IMG] v2beta API error {response.status}: {error_text[:300]}")
                        return None
                        
        except Exception as e:
            logger.error(f"[IMG2IMG] v2beta exception: {type(e).__name__}: {e}")
            return None
    
    async def _save_stability_result(self, data: dict, product_title: str, api_version: str) -> Dict:
        """Save result from v1 API (returns JSON with base64)"""
        result_base64 = data['artifacts'][0]['base64']
        image_bytes = base64.b64decode(result_base64)
        return await self._save_stability_bytes(image_bytes, product_title, api_version)
    
    async def _save_stability_bytes(self, image_bytes: bytes, product_title: str, api_version: str) -> Dict:
        """Save image bytes to file and return result dict"""
        safe_title = product_title[:30].replace(' ', '_').replace('/', '_').replace('\\', '_')
        filename = f"img2img_{safe_title}_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
        filepath = CACHE_DIR / filename
        
        with open(filepath, 'wb') as f:
            f.write(image_bytes)
        
        logger.info(f"[IMG2IMG] ✅ Success ({api_version})! Saved to: {filename}")
        
        return {
            "ai_image_url": f"/generated_images/{filename}",
            "generated_at": datetime.now().isoformat(),
            "source": f"stability_img2img_{api_version}",
            "note": "Transformed original product image with enhanced styling.",
            "api_version": api_version
        }
    
    def _log_stability_error(self, status_code: int, error_text: str):
        """Log detailed error information for debugging"""
        error_lower = error_text.lower()
        
        if status_code == 401:
            logger.error("[IMG2IMG] ❌ Invalid API key - check STABILITY_API_KEY in .env")
            logger.error("[IMG2IMG]    Get your key at: https://platform.stability.ai/account/keys")
        elif status_code == 402:
            logger.error("[IMG2IMG] ❌ Insufficient credits - add credits at:")
            logger.error("[IMG2IMG]    https://platform.stability.ai/account/credits")
        elif status_code == 403:
            logger.error("[IMG2IMG] ❌ Access denied - API key may lack permissions")
        elif "content_moderation" in error_lower or "nsfw" in error_lower:
            logger.error("[IMG2IMG] ❌ Content moderation blocked the image")
        elif "invalid" in error_lower and "image" in error_lower:
            logger.error("[IMG2IMG] ❌ Invalid image format - must be PNG/JPEG")
        elif status_code == 429:
            logger.error("[IMG2IMG] ❌ Rate limited - too many requests")
        elif status_code >= 500:
            logger.error(f"[IMG2IMG] ❌ Stability AI server error ({status_code}) - try again later")
    
    # =========================================================================
    # MODE 3: TEXT-ONLY (Enhanced prompts)
    # =========================================================================
    
    async def _generate_text_only_dalle(self, product_title: str, niche: str) -> Optional[Dict]:
        """Text-only DALL-E generation with enhanced prompts"""
        
        prompt = self._build_text_only_prompt(product_title, niche)
        logger.info(f"[TEXT-ONLY] Generating for: {product_title[:40]}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.openai.com/v1/images/generations",
                    headers={
                        "Authorization": f"Bearer {get_openai_key()}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "dall-e-3",
                        "prompt": prompt,
                        "n": 1,
                        "size": "1024x1024",
                        "quality": "hd",
                        "style": "natural"
                    },
                    timeout=aiohttp.ClientTimeout(total=90)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info("[TEXT-ONLY] ✅ Success!")
                        return {
                            "ai_image_url": data["data"][0]["url"],
                            "generated_at": datetime.now().isoformat(),
                            "source": "openai_text",
                            "note": "Generated from product title only (didn't see original).",
                            "prompt_used": prompt[:500] + "..."
                        }
                    else:
                        error = await response.text()
                        logger.error(f"[TEXT-ONLY] ❌ Error {response.status}: {error[:200]}")
                        return None
        except Exception as e:
            logger.error(f"[TEXT-ONLY] ❌ Exception: {e}")
            return None
    
    async def _generate_text_only_stability(self, product_title: str, niche: str) -> Optional[Dict]:
        """Text-only Stability generation"""
        
        prompt = self._build_text_only_prompt(product_title, niche)
        logger.info(f"[STABILITY-TEXT] Generating for: {product_title[:40]}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image",
                    headers={
                        "Authorization": f"Bearer {get_stability_key()}",
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    },
                    json={
                        "text_prompts": [
                            {"text": prompt, "weight": 1},
                            {"text": "blurry, low quality, cartoon, watermark, text, distorted", "weight": -1}
                        ],
                        "cfg_scale": 7,
                        "height": 1024,
                        "width": 1024,
                        "samples": 1,
                        "steps": 30,
                    },
                    timeout=aiohttp.ClientTimeout(total=90)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        image_bytes = base64.b64decode(data['artifacts'][0]['base64'])
                        
                        safe_title = product_title[:30].replace(' ', '_').replace('/', '_')
                        filename = f"stability_text_{safe_title}_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
                        filepath = CACHE_DIR / filename
                        
                        with open(filepath, 'wb') as f:
                            f.write(image_bytes)
                        
                        logger.info(f"[STABILITY-TEXT] ✅ Success: {filename}")
                        return {
                            "ai_image_url": f"/generated_images/{filename}",
                            "generated_at": datetime.now().isoformat(),
                            "source": "stability_text",
                            "note": "Generated from product title only.",
                            "prompt_used": prompt[:500] + "..."
                        }
                    else:
                        error = await response.text()
                        logger.error(f"[STABILITY-TEXT] ❌ Error {response.status}: {error[:200]}")
                        return None
        except Exception as e:
            logger.error(f"[STABILITY-TEXT] ❌ Exception: {e}")
            return None
    
    # =========================================================================
    # BATCH GENERATION
    # =========================================================================
    
    async def generate_batch(
        self,
        products: list,
        max_concurrent: int = 2,
        mode: GenerationMode = "vision_enhanced"
    ) -> list:
        """Generate AI images for multiple products"""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_product(product: dict) -> dict:
            async with semaphore:
                # Collect all available images for this product
                all_images = []
                main_image = product.get('image_url') or product.get('main_image')
                if main_image:
                    all_images.append(main_image)
                
                # Add additional images if available
                additional = product.get('additional_images') or product.get('images') or []
                all_images.extend(additional[:2])  # Max 2 additional
                
                result = await self.generate_product_image(
                    product_title=product.get('title', 'Product'),
                    niche=product.get('niche', 'smart_home'),
                    original_image_url=main_image,
                    additional_image_urls=additional[:2],
                    tags=product.get('tags', []),
                    mode=mode
                )
                
                product['ai_image_url'] = result.get('ai_image_url')
                product['original_image_url'] = result.get('original_image_url')
                product['image_source'] = result.get('source', 'unknown')
                product['image_mode'] = result.get('mode', mode)
                product['images_analyzed'] = result.get('images_analyzed', 0)
                return product
        
        tasks = [process_product(p) for p in products]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        successful = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"[BATCH] Failed for product {i}: {result}")
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

def get_image_generator(force_refresh: bool = False) -> AIImageGenerator:
    """
    Get or create singleton image generator.
    
    Args:
        force_refresh: If True, recreate the generator (useful if env vars changed)
    """
    global _image_generator
    if _image_generator is None or force_refresh:
        _image_generator = AIImageGenerator()
    else:
        # Always refresh API status to pick up any env var changes
        _image_generator._refresh_api_status()
    return _image_generator


def reset_image_generator():
    """Reset the singleton (forces recreation on next get_image_generator call)"""
    global _image_generator
    _image_generator = None


async def generate_product_image(
    product_title: str,
    niche: str = "smart_home",
    original_image_url: str = None,
    additional_image_urls: List[str] = None,
    mode: GenerationMode = "vision_enhanced"
) -> str:
    """Quick function to generate a single product image"""
    generator = get_image_generator()
    result = await generator.generate_product_image(
        product_title=product_title,
        niche=niche,
        original_image_url=original_image_url,
        additional_image_urls=additional_image_urls,
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
