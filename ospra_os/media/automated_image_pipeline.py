"""
Automated Image Pipeline for Product Photos
Downloads, enhances, and uploads product images automatically
"""

import os
import asyncio
import logging
from typing import List, Dict, Optional
from pathlib import Path
import requests
from io import BytesIO

logger = logging.getLogger(__name__)


class AutomatedImagePipeline:
    """
    End-to-end automated image processing pipeline

    Flow:
    1. Download product images from AliExpress
    2. Enhance images (remove background, add branding)
    3. Upload to Shopify
    4. Generate lifestyle/marketing images with AI
    5. Update product listings with new images
    """

    def __init__(self):
        self.temp_dir = Path("temp_images")
        self.temp_dir.mkdir(exist_ok=True)

        # Import processor and generator
        try:
            from ospra_os.media.image_processor import ImageProcessor
            self.processor = ImageProcessor()
        except ImportError:
            logger.warning("ImageProcessor not available")
            self.processor = None

        try:
            from ospra_os.media.ai_image_generator import AIImageGenerator
            self.generator = AIImageGenerator()
        except ImportError:
            logger.warning("AIImageGenerator not available")
            self.generator = None

    async def process_product_images(
        self,
        product: Dict,
        options: Optional[Dict] = None
    ) -> Dict:
        """
        Process all images for a product

        Args:
            product: Product dict with image URLs
            options: Processing options
                - enhance_quality: bool
                - remove_background: bool
                - add_lifestyle: bool
                - lifestyle_count: int

        Returns:
            Dict with processed image URLs and metadata
        """
        logger.info(f"🎨 Processing images for: {product.get('name', 'Unknown')[:50]}")

        options = options or {}
        enhance_quality = options.get('enhance_quality', True)
        remove_background = options.get('remove_background', False)
        add_lifestyle = options.get('add_lifestyle', False)
        lifestyle_count = options.get('lifestyle_count', 2)

        results = {
            'product_id': product.get('product_id'),
            'product_name': product.get('name'),
            'original_images': [],
            'enhanced_images': [],
            'lifestyle_images': [],
            'success': False
        }

        try:
            # Step 1: Download original images
            original_urls = self._extract_image_urls(product)
            results['original_images'] = original_urls

            if not original_urls:
                logger.warning("No images found for product")
                return results

            # Step 2: Enhance primary product images
            enhanced_images = []
            for i, url in enumerate(original_urls[:3]):  # Process top 3 images
                try:
                    logger.info(f"Processing image {i+1}/{min(3, len(original_urls))}")

                    # Download image
                    image_data = await self._download_image(url)
                    if not image_data:
                        continue

                    # Enhance if processor available
                    if self.processor and enhance_quality:
                        enhanced_data = await self.processor.process_product_image(url)
                        if enhanced_data:
                            image_data = enhanced_data

                    # Upload to temporary storage or Shopify
                    upload_url = await self._upload_image(
                        image_data,
                        f"{product.get('product_id', 'unknown')}_enhanced_{i}.png"
                    )

                    if upload_url:
                        enhanced_images.append(upload_url)

                except Exception as e:
                    logger.error(f"Error processing image {i}: {e}")
                    continue

            results['enhanced_images'] = enhanced_images

            # Step 3: Generate lifestyle/marketing images if requested
            if add_lifestyle and self.generator and enhanced_images:
                lifestyle_images = await self._generate_lifestyle_images(
                    product,
                    enhanced_images[0],  # Use first enhanced image
                    count=lifestyle_count
                )
                results['lifestyle_images'] = lifestyle_images

            results['success'] = len(enhanced_images) > 0
            logger.info(f"✅ Processed {len(enhanced_images)} images successfully")

        except Exception as e:
            logger.error(f"Image pipeline error: {e}")
            results['error'] = str(e)

        return results

    def _extract_image_urls(self, product: Dict) -> List[str]:
        """Extract image URLs from product data"""
        urls = []

        # Check various possible image fields
        if 'image_url' in product:
            urls.append(product['image_url'])

        if 'images' in product:
            if isinstance(product['images'], list):
                urls.extend(product['images'])
            elif isinstance(product['images'], str):
                urls.append(product['images'])

        if 'aliexpress_match' in product:
            ali = product['aliexpress_match']
            if 'image_url' in ali:
                urls.append(ali['image_url'])

        if 'amazon_data' in product:
            amz = product['amazon_data']
            if 'image_url' in amz:
                urls.append(amz['image_url'])

        # Filter out duplicates and invalid URLs
        unique_urls = []
        for url in urls:
            if url and url.startswith('http') and url not in unique_urls:
                unique_urls.append(url)

        return unique_urls

    async def _download_image(self, url: str) -> Optional[bytes]:
        """Download image from URL"""
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return response.content
        except Exception as e:
            logger.error(f"Download error: {e}")
        return None

    async def _upload_image(self, image_data: bytes, filename: str) -> Optional[str]:
        """
        Upload image to storage (Shopify or S3)

        For now, save locally. In production, upload to:
        - Shopify Files API
        - Amazon S3
        - Cloudinary
        """
        try:
            # Save locally for now
            filepath = self.temp_dir / filename
            with open(filepath, 'wb') as f:
                f.write(image_data)

            logger.info(f"Saved image: {filepath}")

            # In production, upload to Shopify:
            # shopify_url = await self._upload_to_shopify(image_data, filename)
            # return shopify_url

            # Return local path for now
            return str(filepath)

        except Exception as e:
            logger.error(f"Upload error: {e}")
            return None

    async def _generate_lifestyle_images(
        self,
        product: Dict,
        primary_image_url: str,
        count: int = 2
    ) -> List[str]:
        """Generate AI lifestyle images for product"""
        if not self.generator:
            return []

        lifestyle_images = []

        for i in range(count):
            try:
                # Generate scene description
                scene = self._create_lifestyle_scene(product, i)

                # Generate image
                image_url = await self.generator.generate_lifestyle_image(
                    product_name=product.get('name', ''),
                    product_image_url=primary_image_url,
                    scene_description=scene
                )

                if image_url:
                    lifestyle_images.append(image_url)

            except Exception as e:
                logger.error(f"Lifestyle image generation error: {e}")
                continue

        return lifestyle_images

    def _create_lifestyle_scene(self, product: Dict, variant: int = 0) -> str:
        """Create lifestyle scene description for AI image generation"""
        product_name = product.get('name', 'product')

        scenes = [
            f"Modern minimalist home setting with {product_name} on a white marble countertop, natural window light, plants in background, professional product photography",
            f"Lifestyle shot of {product_name} in use, bright airy room, happy person using the product, authentic home environment, warm lighting",
            f"Close-up detail shot of {product_name}, premium materials visible, soft dramatic lighting, luxury product photography aesthetic",
            f"Flat lay composition with {product_name} as hero product, complementary accessories, clean white background, top-down view, Instagram-style"
        ]

        return scenes[variant % len(scenes)]

    async def batch_process_products(
        self,
        products: List[Dict],
        options: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Process images for multiple products in batch

        Args:
            products: List of product dicts
            options: Processing options for all products

        Returns:
            List of results for each product
        """
        logger.info(f"📦 Batch processing {len(products)} products")

        # Process in parallel (limit concurrency to avoid overwhelming servers)
        max_concurrent = 3
        results = []

        for i in range(0, len(products), max_concurrent):
            batch = products[i:i+max_concurrent]

            batch_results = await asyncio.gather(*[
                self.process_product_images(product, options)
                for product in batch
            ], return_exceptions=True)

            results.extend([
                r if not isinstance(r, Exception) else {'success': False, 'error': str(r)}
                for r in batch_results
            ])

            # Small delay between batches
            if i + max_concurrent < len(products):
                await asyncio.sleep(1)

        successful = sum(1 for r in results if r.get('success'))
        logger.info(f"✅ Batch complete: {successful}/{len(products)} successful")

        return results

    async def cleanup_temp_files(self, max_age_hours: int = 24):
        """Clean up old temporary image files"""
        import time

        try:
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600

            for filepath in self.temp_dir.glob('*'):
                if filepath.is_file():
                    file_age = current_time - filepath.stat().st_mtime
                    if file_age > max_age_seconds:
                        filepath.unlink()
                        logger.debug(f"Deleted old temp file: {filepath}")

        except Exception as e:
            logger.error(f"Cleanup error: {e}")


# Convenience function for quick processing
async def process_product_images(product: Dict, **options) -> Dict:
    """
    Quick function to process product images

    Example:
        result = await process_product_images(
            product,
            enhance_quality=True,
            add_lifestyle=True,
            lifestyle_count=2
        )
    """
    pipeline = AutomatedImagePipeline()
    return await pipeline.process_product_images(product, options)
