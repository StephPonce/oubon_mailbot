"""
Premium Product Image Processing
Transform AliExpress images into premium Oubon aesthetic
"""

import io
import logging
from typing import Optional
from PIL import Image, ImageEnhance, ImageFilter
import requests

logger = logging.getLogger(__name__)


class ImageProcessor:
    """
    Transform product images to premium Oubon brand aesthetic
    """

    def __init__(self):
        self.brand_colors = {
            'primary': '#000000',  # Black
            'accent': '#3b82f6',  # Electric blue
            'background': '#FFFFFF'  # White
        }
        self.target_size = (800, 800)

    async def process_product_image(self, image_url: str) -> Optional[bytes]:
        """
        Transform product image to premium Oubon aesthetic

        Args:
            image_url: URL of original product image

        Returns:
            Processed image as bytes (PNG format)
        """
        try:
            logger.info(f"🎨 Processing image: {image_url[:50]}...")

            # Download original image
            response = requests.get(image_url, timeout=10)
            if response.status_code != 200:
                logger.error(f"Failed to download image: {response.status_code}")
                return None

            original = Image.open(io.BytesIO(response.content))

            # Apply transformations
            processed = self._transform_image(original)

            # Convert to bytes
            output = io.BytesIO()
            processed.save(output, format='PNG', quality=95, optimize=True)

            logger.info("✅ Image processed successfully")
            return output.getvalue()

        except Exception as e:
            logger.error(f"Image processing error: {e}")
            return None

    def _transform_image(self, image: Image.Image) -> Image.Image:
        """
        Apply all transformations to image
        """
        # Convert to RGB if needed
        if image.mode != 'RGB':
            # Handle RGBA images
            if image.mode == 'RGBA':
                background = Image.new('RGB', image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[3])  # Use alpha channel as mask
                image = background
            else:
                image = image.convert('RGB')

        # 1. Enhance quality
        image = self._enhance_image(image)

        # 2. Center crop to square
        image = self._center_crop_square(image)

        # 3. Resize to target dimensions
        image = image.resize(self.target_size, Image.LANCZOS)

        # 4. Add subtle white border
        image = self._add_border(image)

        return image

    def _enhance_image(self, image: Image.Image) -> Image.Image:
        """
        Enhance image quality for premium look
        """
        # Increase sharpness slightly
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(1.2)

        # Increase contrast slightly
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.1)

        # Slightly reduce saturation (more premium/minimalist look)
        enhancer = ImageEnhance.Color(image)
        image = enhancer.enhance(0.95)

        # Increase brightness slightly
        enhancer = ImageEnhance.Brightness(image)
        image = enhancer.enhance(1.05)

        return image

    def _center_crop_square(self, image: Image.Image) -> Image.Image:
        """
        Crop to perfect square with product centered
        """
        width, height = image.size
        size = min(width, height)

        left = (width - size) // 2
        top = (height - size) // 2
        right = left + size
        bottom = top + size

        return image.crop((left, top, right, bottom))

    def _add_border(self, image: Image.Image, border_size: int = 10) -> Image.Image:
        """
        Add subtle white border
        """
        width, height = image.size
        new_size = (width + border_size * 2, height + border_size * 2)

        bordered = Image.new('RGB', new_size, (255, 255, 255))
        bordered.paste(image, (border_size, border_size))

        return bordered

    def _remove_background(self, image: Image.Image) -> Image.Image:
        """
        Remove background using rembg (AI-powered)
        Requires: pip install rembg
        """
        try:
            from rembg import remove

            # Remove background
            output = remove(image)

            # Create white background
            white_bg = Image.new('RGB', output.size, (255, 255, 255))
            if output.mode == 'RGBA':
                white_bg.paste(output, mask=output.split()[3])
            else:
                white_bg = output.convert('RGB')

            return white_bg

        except ImportError:
            logger.warning("rembg not installed, skipping background removal")
            return image
        except Exception as e:
            logger.error(f"Background removal failed: {e}")
            return image
