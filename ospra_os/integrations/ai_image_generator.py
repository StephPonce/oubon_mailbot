"""
AI Image Enhancer for Oubon Shop
=================================
Single Purpose: Remove ugly backgrounds, add clean professional ones.

HOW IT WORKS:
1. Stability AI removes the background (returns transparent PNG)
2. We composite onto Oubon Shop branded background
3. Product stays EXACTLY the same - only background changes

Cost: ~6 credits per image (~$0.06)
Time: ~3-5 seconds

OUBON SHOP AESTHETIC:
- Clean white or soft gradient backgrounds
- Minimalist, premium feel
- Professional e-commerce ready
"""

import os
import logging
import base64
import aiohttp
import asyncio
from typing import Optional, Dict, List
from datetime import datetime
from io import BytesIO

# Image processing
try:
    from PIL import Image, ImageDraw, ImageFilter
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logging.warning("PIL not available - install Pillow for image processing")

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

def get_stability_key() -> str:
    """Get Stability API key at runtime"""
    return os.getenv('STABILITY_API_KEY', '')

# Oubon Shop brand backgrounds
BACKGROUND_STYLES = {
    "clean_white": {
        "name": "Clean White",
        "description": "Pure white background - classic e-commerce",
        "color": (255, 255, 255),
        "gradient": None
    },
    "soft_gray": {
        "name": "Soft Gray",
        "description": "Light gray for subtle contrast",
        "color": (245, 245, 247),
        "gradient": None
    },
    "warm_gradient": {
        "name": "Warm Gradient",
        "description": "Soft warm gradient - premium feel",
        "color": None,
        "gradient": {
            "top": (255, 253, 250),
            "bottom": (250, 245, 240)
        }
    },
    "cool_gradient": {
        "name": "Cool Gradient",
        "description": "Cool subtle gradient - tech/modern feel",
        "color": None,
        "gradient": {
            "top": (250, 252, 255),
            "bottom": (240, 245, 250)
        }
    },
    "lifestyle_shadow": {
        "name": "White with Shadow",
        "description": "White background with soft product shadow",
        "color": (255, 255, 255),
        "gradient": None,
        "add_shadow": True
    }
}

# Niche to background mapping
NICHE_BACKGROUNDS = {
    "smart_home": "cool_gradient",
    "tech": "cool_gradient",
    "kitchen": "warm_gradient",
    "home_decor": "warm_gradient",
    "beauty": "soft_gray",
    "fitness": "clean_white",
    "outdoor": "clean_white",
    "pet": "warm_gradient",
    "lighting": "soft_gray",
    "organization": "clean_white",
    "default": "clean_white"
}


class AIImageEnhancer:
    """
    Product image enhancer for Oubon Shop.
    
    Single responsibility: Remove ugly supplier backgrounds,
    add clean professional backgrounds. Product stays intact.
    """
    
    def __init__(self):
        self.stability_key = get_stability_key()
        self._session = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        """Close the session"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    # =========================================================================
    # MAIN PUBLIC METHOD
    # =========================================================================
    
    async def enhance_product_image(
        self,
        image_url: str,
        niche: str = "smart_home",
        background_style: str = None,
        add_shadow: bool = True
    ) -> Dict:
        """
        Enhance a product image by removing background and adding clean one.
        
        Args:
            image_url: URL of the original product image
            niche: Product category (determines default background)
            background_style: Override background style (optional)
            add_shadow: Whether to add subtle shadow under product
            
        Returns:
            Dict with enhanced_image_url (base64), metadata, etc.
        """
        start_time = datetime.now()
        
        # Validate
        if not self.stability_key:
            return {
                "success": False,
                "error": "Stability API key not configured",
                "original_url": image_url
            }
        
        if not PIL_AVAILABLE:
            return {
                "success": False,
                "error": "Pillow not installed - required for image processing",
                "original_url": image_url
            }
        
        try:
            # Step 1: Download original image
            logger.info(f"[ENHANCE] Downloading original image...")
            original_image = await self._download_image(image_url)
            if not original_image:
                return {
                    "success": False,
                    "error": "Failed to download original image",
                    "original_url": image_url
                }
            
            # Step 2: Remove background using Stability AI
            logger.info(f"[ENHANCE] Removing background with Stability AI...")
            transparent_image = await self._remove_background(original_image)
            if not transparent_image:
                return {
                    "success": False,
                    "error": "Background removal failed - check Stability API credits",
                    "original_url": image_url
                }
            
            # Step 3: Determine background style
            if background_style and background_style in BACKGROUND_STYLES:
                bg_style = background_style
            else:
                bg_style = NICHE_BACKGROUNDS.get(niche, NICHE_BACKGROUNDS["default"])
            
            # Step 4: Create final image with new background
            logger.info(f"[ENHANCE] Compositing with {bg_style} background...")
            final_image = self._composite_on_background(
                transparent_image, 
                bg_style,
                add_shadow=add_shadow
            )
            
            # Step 5: Convert to base64
            enhanced_base64 = self._image_to_base64(final_image)
            
            elapsed = (datetime.now() - start_time).total_seconds()
            
            logger.info(f"[ENHANCE] ✅ Complete in {elapsed:.2f}s")
            
            return {
                "success": True,
                "enhanced_image_url": f"data:image/png;base64,{enhanced_base64}",
                "original_url": image_url,
                "background_style": bg_style,
                "background_name": BACKGROUND_STYLES[bg_style]["name"],
                "processing_time": round(elapsed, 2),
                "estimated_cost": "$0.06",
                "method": "stability_bg_removal"
            }
            
        except Exception as e:
            logger.error(f"[ENHANCE] Failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "original_url": image_url
            }
    
    # =========================================================================
    # BATCH PROCESSING
    # =========================================================================
    
    async def enhance_batch(
        self,
        images: List[Dict],
        niche: str = "smart_home",
        max_concurrent: int = 3
    ) -> List[Dict]:
        """
        Enhance multiple images with concurrency control.
        
        Args:
            images: List of dicts with 'url' and optionally 'id'
            niche: Default niche for all images
            max_concurrent: Max parallel requests (respect rate limits)
            
        Returns:
            List of results matching input order
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_one(img_data: Dict) -> Dict:
            async with semaphore:
                url = img_data.get('url') or img_data.get('image_url')
                img_niche = img_data.get('niche', niche)
                
                result = await self.enhance_product_image(url, img_niche)
                result['id'] = img_data.get('id')
                result['title'] = img_data.get('title')
                return result
        
        tasks = [process_one(img) for img in images]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle any exceptions
        processed = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed.append({
                    "success": False,
                    "error": str(result),
                    "id": images[i].get('id'),
                    "original_url": images[i].get('url') or images[i].get('image_url')
                })
            else:
                processed.append(result)
        
        return processed
    
    # =========================================================================
    # STABILITY AI - BACKGROUND REMOVAL
    # =========================================================================
    
    async def _remove_background(self, image: Image.Image) -> Optional[Image.Image]:
        """
        Remove background using Stability AI's remove-background API.
        Returns image with transparent background (RGBA).
        
        API: https://api.stability.ai/v2beta/stable-image/edit/remove-background
        Cost: ~2 credits
        """
        try:
            # Convert image to bytes
            img_bytes = BytesIO()
            # Convert to RGB if needed (API doesn't like RGBA input sometimes)
            if image.mode == 'RGBA':
                image = image.convert('RGB')
            image.save(img_bytes, format='PNG')
            img_bytes.seek(0)
            
            session = await self._get_session()
            
            # Prepare multipart form data
            form = aiohttp.FormData()
            form.add_field(
                'image',
                img_bytes.getvalue(),
                filename='product.png',
                content_type='image/png'
            )
            form.add_field('output_format', 'png')
            
            async with session.post(
                "https://api.stability.ai/v2beta/stable-image/edit/remove-background",
                headers={
                    "Authorization": f"Bearer {self.stability_key}",
                    "Accept": "image/*"
                },
                data=form,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                if response.status == 200:
                    result_bytes = await response.read()
                    result_image = Image.open(BytesIO(result_bytes))
                    # Ensure RGBA for transparency
                    if result_image.mode != 'RGBA':
                        result_image = result_image.convert('RGBA')
                    logger.info("[STABILITY] Background removed successfully")
                    return result_image
                else:
                    error_text = await response.text()
                    logger.error(f"[STABILITY] Background removal failed ({response.status}): {error_text[:300]}")
                    return None
                    
        except Exception as e:
            logger.error(f"[STABILITY] Background removal error: {e}")
            return None
    
    # =========================================================================
    # IMAGE COMPOSITING
    # =========================================================================
    
    def _composite_on_background(
        self, 
        product_image: Image.Image, 
        bg_style: str,
        add_shadow: bool = True
    ) -> Image.Image:
        """
        Composite transparent product image onto clean background.
        """
        style = BACKGROUND_STYLES.get(bg_style, BACKGROUND_STYLES["clean_white"])
        
        # Target size (square for e-commerce)
        target_size = (1024, 1024)
        
        # Create background
        if style.get("gradient"):
            background = self._create_gradient_background(
                target_size,
                style["gradient"]["top"],
                style["gradient"]["bottom"]
            )
        else:
            background = Image.new('RGB', target_size, style["color"])
        
        # Resize product to fit nicely (80% of canvas, centered)
        product_resized = self._fit_product_to_canvas(product_image, target_size, padding=0.1)
        
        # Calculate center position
        x = (target_size[0] - product_resized.width) // 2
        y = (target_size[1] - product_resized.height) // 2
        
        # Add shadow if requested
        if add_shadow or style.get("add_shadow"):
            background = self._add_product_shadow(background, product_resized, (x, y))
        
        # Composite product onto background
        background.paste(product_resized, (x, y), product_resized)
        
        return background
    
    def _create_gradient_background(
        self, 
        size: tuple, 
        top_color: tuple, 
        bottom_color: tuple
    ) -> Image.Image:
        """Create a vertical gradient background"""
        width, height = size
        background = Image.new('RGB', size)
        
        for y in range(height):
            ratio = y / height
            r = int(top_color[0] * (1 - ratio) + bottom_color[0] * ratio)
            g = int(top_color[1] * (1 - ratio) + bottom_color[1] * ratio)
            b = int(top_color[2] * (1 - ratio) + bottom_color[2] * ratio)
            
            for x in range(width):
                background.putpixel((x, y), (r, g, b))
        
        return background
    
    def _fit_product_to_canvas(
        self, 
        product: Image.Image, 
        canvas_size: tuple,
        padding: float = 0.1
    ) -> Image.Image:
        """
        Resize product to fit within canvas with padding.
        Maintains aspect ratio.
        """
        canvas_w, canvas_h = canvas_size
        max_w = int(canvas_w * (1 - 2 * padding))
        max_h = int(canvas_h * (1 - 2 * padding))
        
        # Calculate scale to fit
        scale = min(max_w / product.width, max_h / product.height)
        
        new_w = int(product.width * scale)
        new_h = int(product.height * scale)
        
        # Use high-quality resampling
        return product.resize((new_w, new_h), Image.Resampling.LANCZOS)
    
    def _add_product_shadow(
        self, 
        background: Image.Image, 
        product: Image.Image,
        position: tuple
    ) -> Image.Image:
        """Add a subtle shadow under the product"""
        # Create shadow from product alpha channel
        if product.mode != 'RGBA':
            return background
        
        # Extract alpha as shadow base
        alpha = product.split()[3]
        
        # Create shadow (dark, semi-transparent)
        shadow = Image.new('RGBA', product.size, (0, 0, 0, 0))
        shadow_alpha = alpha.point(lambda x: min(x, 40))  # Max 40 alpha for subtle shadow
        shadow.putalpha(shadow_alpha)
        
        # Blur the shadow
        shadow = shadow.filter(ImageFilter.GaussianBlur(radius=15))
        
        # Offset shadow down and slightly right
        shadow_offset = (position[0] + 10, position[1] + 20)
        
        # Convert background to RGBA for compositing
        bg_rgba = background.convert('RGBA')
        
        # Paste shadow first (behind product)
        bg_rgba.paste(shadow, shadow_offset, shadow)
        
        # Convert back to RGB
        return bg_rgba.convert('RGB')
    
    # =========================================================================
    # UTILITIES
    # =========================================================================
    
    async def _download_image(self, url: str) -> Optional[Image.Image]:
        """Download image from URL"""
        try:
            session = await self._get_session()
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    data = await response.read()
                    return Image.open(BytesIO(data))
                else:
                    logger.error(f"Failed to download image: HTTP {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Image download error: {e}")
            return None
    
    def _image_to_base64(self, image: Image.Image) -> str:
        """Convert PIL Image to base64 string"""
        buffer = BytesIO()
        image.save(buffer, format='PNG', optimize=True)
        return base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    # =========================================================================
    # STATUS CHECK
    # =========================================================================
    
    async def check_status(self) -> Dict:
        """Check if the enhancer is properly configured"""
        return {
            "available": bool(self.stability_key),
            "stability_configured": bool(self.stability_key),
            "pil_available": PIL_AVAILABLE,
            "background_styles": list(BACKGROUND_STYLES.keys()),
            "default_backgrounds_by_niche": NICHE_BACKGROUNDS,
            "estimated_cost_per_image": "$0.06",
            "method": "Stability AI Background Removal + Custom Compositing"
        }


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_enhancer_instance: Optional[AIImageEnhancer] = None

def get_image_enhancer() -> AIImageEnhancer:
    """Get or create the singleton image enhancer instance"""
    global _enhancer_instance
    if _enhancer_instance is None:
        _enhancer_instance = AIImageEnhancer()
    return _enhancer_instance


# ============================================================================
# SIMPLE FUNCTION API
# ============================================================================

async def enhance_product_image(
    image_url: str,
    niche: str = "smart_home",
    background_style: str = None
) -> Dict:
    """
    Simple function to enhance a single product image.
    
    Usage:
        result = await enhance_product_image(
            "https://aliexpress.com/ugly-product.jpg",
            niche="smart_home"
        )
        if result["success"]:
            enhanced_url = result["enhanced_image_url"]
    """
    enhancer = get_image_enhancer()
    return await enhancer.enhance_product_image(image_url, niche, background_style)


async def enhance_product_batch(
    images: List[Dict],
    niche: str = "smart_home"
) -> List[Dict]:
    """
    Enhance multiple product images.
    
    Usage:
        results = await enhance_product_batch([
            {"url": "https://...", "id": "prod1", "title": "Widget"},
            {"url": "https://...", "id": "prod2", "title": "Gadget"},
        ])
    """
    enhancer = get_image_enhancer()
    return await enhancer.enhance_batch(images, niche)
