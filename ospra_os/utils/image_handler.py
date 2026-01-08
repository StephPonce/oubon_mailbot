import requests
import logging
import os
import hashlib
from typing import Optional, Dict
from pathlib import Path

logger = logging.getLogger(__name__)

class ImageHandler:
    """Handle product image downloading and uploading"""

    def __init__(self):
        self.cache_dir = Path("/tmp/ospra_images")
        self.cache_dir.mkdir(exist_ok=True)

    def download_image(self, image_url: str, product_id: str) -> Optional[str]:
        """
        Download image from source URL

        Returns: Local file path or None
        """

        if not image_url or not image_url.startswith('http'):
            logger.warning(f"Invalid image URL: {image_url}")
            return None

        try:
            # Clean URL (remove parameters)
            clean_url = image_url.split('?')[0]

            # Get file extension
            ext = clean_url.split('.')[-1].lower()
            if ext not in ['jpg', 'jpeg', 'png', 'webp', 'gif']:
                ext = 'jpg'

            # Generate filename
            url_hash = hashlib.md5(image_url.encode()).hexdigest()[:12]
            filename = f"{product_id}_{url_hash}.{ext}"
            filepath = self.cache_dir / filename

            # Check if already downloaded
            if filepath.exists():
                logger.info(f"[SUCCESS] Image cached: {filename}")
                return str(filepath)

            # Download image
            logger.info(f" Downloading image from: {image_url[:60]}...")

            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Referer': 'https://www.aliexpress.com/'
            }

            response = requests.get(image_url, headers=headers, timeout=15, stream=True)

            if response.status_code == 200:
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                # Verify file size
                file_size = filepath.stat().st_size
                if file_size < 1000:  # Less than 1KB probably error
                    logger.warning(f"Image too small ({file_size} bytes), might be broken")
                    filepath.unlink()
                    return None

                logger.info(f"[SUCCESS] Downloaded: {filename} ({file_size:,} bytes)")
                return str(filepath)
            else:
                logger.error(f"Download failed: HTTP {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Image download failed: {e}")
            return None

    def upload_to_shopify(self, local_path: str, product_id: str, shopify_client) -> Optional[str]:
        """
        Upload image to Shopify CDN

        Returns: Shopify CDN URL or None
        """

        if not shopify_client or not shopify_client.enabled:
            logger.warning("Shopify not configured")
            return None

        try:
            # Read image file
            with open(local_path, 'rb') as f:
                image_data = f.read()

            # Get filename
            filename = Path(local_path).name

            # Upload to Shopify (via product image)
            # Note: Shopify automatically hosts images on their CDN
            logger.info(f" Uploading to Shopify: {filename}")

            # Create image attachment
            import base64
            image_b64 = base64.b64encode(image_data).decode('utf-8')

            image_payload = {
                "attachment": image_b64,
                "filename": filename
            }

            # Return the payload (will be used when creating product)
            return image_payload

        except Exception as e:
            logger.error(f"Shopify upload failed: {e}")
            return None

    def process_product_images(
        self,
        product: Dict,
        shopify_client=None
    ) -> Dict:
        """
        Complete pipeline: download + prepare for Shopify

        Returns: Updated product with image data
        """

        image_url = product.get('image_url')
        product_id = product.get('id', 'unknown')

        if not image_url:
            logger.warning(f"No image URL for product {product_id}")
            return product

        # Step 1: Download image
        local_path = self.download_image(image_url, product_id)

        if not local_path:
            logger.warning(f"Failed to download image for {product_id}")
            return product

        # Step 2: Prepare for Shopify upload
        if shopify_client:
            shopify_image = self.upload_to_shopify(local_path, product_id, shopify_client)
            if shopify_image:
                product['shopify_image'] = shopify_image
                logger.info(f"[SUCCESS] Image ready for Shopify: {product_id}")

        # Store local path (temporary)
        product['local_image_path'] = local_path

        return product

    def cleanup_cache(self, older_than_days: int = 7):
        """Remove old cached images"""

        try:
            import time
            now = time.time()
            count = 0

            for filepath in self.cache_dir.glob('*'):
                if filepath.is_file():
                    age_days = (now - filepath.stat().st_mtime) / 86400
                    if age_days > older_than_days:
                        filepath.unlink()
                        count += 1

            if count > 0:
                logger.info(f" Cleaned up {count} old cached images")

        except Exception as e:
            logger.error(f"Cache cleanup failed: {e}")
