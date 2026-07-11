"""
Ospra Intelligence - Image Storage Service

Handles local and cloud storage of product images.

Features:
- Local file system storage with organized directory structure
- Multiple format support (PNG, JPEG, WebP)
- Unique timestamped filenames
- Cloud upload support (Cloudinary, S3) - ready for implementation
- Image retrieval and deletion
"""

import os
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from PIL import Image
import hashlib

logger = logging.getLogger(__name__)


class ImageStorage:
    """
    Manages storage of product images locally and optionally in the cloud.

    Directory structure:
    data/images/
     products/
        {product_id}/
           original_20241206_143022.png
           enhanced_20241206_143023.png
           thumbnail_20241206_143024.jpg
        {another_product_id}/
     temp/
    """

    def __init__(
        self,
        base_path: str = "data/images",
        enable_cloud_upload: Optional[bool] = None,
        cloudinary_config: Optional[Dict[str, str]] = None,
        s3_config: Optional[Dict[str, str]] = None
    ):
        """
        Initialize image storage service.

        T160: local disk (``data/images``) is wiped on every Render deploy, so a
        generated/processed product image vanishes on the next release. Cloud
        upload was fully implemented but gated behind ``enable_cloud_upload=False``
        and every caller used ``ImageStorage()`` with the default — so nothing
        ever persisted to the cloud. This now AUTO-ENABLES cloud upload when cloud
        credentials are present in the environment: prod persists images with zero
        caller changes, while local dev (no creds) transparently stays on disk.

        Args:
            base_path: Base directory for local storage.
            enable_cloud_upload: ``None`` = auto (enabled when cloud env creds
                exist); pass ``True``/``False`` to force.
            cloudinary_config: explicit Cloudinary creds; falls back to env.
            s3_config: explicit S3 creds; falls back to env.
        """
        self.base_path = Path(base_path)
        self.products_path = self.base_path / "products"
        self.temp_path = self.base_path / "temp"

        # Create directories
        self._ensure_directories()

        # Cloud storage configs — fall back to the environment when not passed.
        self.cloudinary_config = cloudinary_config or self._cloudinary_config_from_env()
        self.s3_config = s3_config or self._s3_config_from_env()

        # Resolve whether cloud upload is on. None => auto: enable when a usable
        # cloud config exists for either provider.
        if enable_cloud_upload is None:
            self.enable_cloud_upload = bool(self.cloudinary_config or self.s3_config)
        else:
            self.enable_cloud_upload = enable_cloud_upload

        # Initialize cloud clients if enabled
        self.cloudinary_client = None
        self.s3_client = None

        if self.enable_cloud_upload:
            self._init_cloud_clients()

        logger.info(f"[SUCCESS] ImageStorage initialized: {self.base_path.absolute()}")
        logger.info(f"   Cloud upload: {'enabled' if self.enable_cloud_upload else 'disabled'}")

    @staticmethod
    def _cloudinary_config_from_env() -> Optional[Dict[str, str]]:
        """Cloudinary creds from env, or None unless all three are present."""
        import os
        cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME")
        api_key = os.getenv("CLOUDINARY_API_KEY")
        api_secret = os.getenv("CLOUDINARY_API_SECRET")
        if cloud_name and api_key and api_secret:
            return {"cloud_name": cloud_name, "api_key": api_key, "api_secret": api_secret}
        return None

    @staticmethod
    def _s3_config_from_env() -> Optional[Dict[str, str]]:
        """S3 creds from env, or None unless bucket + keys are present."""
        import os
        bucket = os.getenv("AWS_S3_BUCKET") or os.getenv("S3_BUCKET")
        access_key = os.getenv("AWS_ACCESS_KEY_ID")
        secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"
        if bucket and access_key and secret_key:
            return {
                "bucket": bucket,
                "region": region,
                "access_key": access_key,
                "secret_key": secret_key,
            }
        return None

    def _ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.products_path.mkdir(parents=True, exist_ok=True)
        self.temp_path.mkdir(parents=True, exist_ok=True)
        logger.debug(f" Ensured directories exist: {self.base_path}")

    def _init_cloud_clients(self) -> None:
        """Initialize cloud storage clients (Cloudinary, S3)."""
        # Cloudinary initialization
        if self.cloudinary_config:
            try:
                import cloudinary
                import cloudinary.uploader

                cloudinary.config(
                    cloud_name=self.cloudinary_config.get("cloud_name"),
                    api_key=self.cloudinary_config.get("api_key"),
                    api_secret=self.cloudinary_config.get("api_secret")
                )
                self.cloudinary_client = cloudinary
                logger.info("[SUCCESS] Cloudinary client initialized")
            except ImportError:
                logger.warning("[WARNING]  Cloudinary not installed: pip install cloudinary")
            except Exception as e:
                logger.error(f"[ERROR] Cloudinary initialization failed: {e}")

        # S3 initialization
        if self.s3_config:
            try:
                import boto3

                self.s3_client = boto3.client(
                    's3',
                    region_name=self.s3_config.get("region"),
                    aws_access_key_id=self.s3_config.get("access_key"),
                    aws_secret_access_key=self.s3_config.get("secret_key")
                )
                logger.info("[SUCCESS] S3 client initialized")
            except ImportError:
                logger.warning("[WARNING]  boto3 not installed: pip install boto3")
            except Exception as e:
                logger.error(f"[ERROR] S3 initialization failed: {e}")

    def _generate_filename(
        self,
        product_id: str,
        image_type: str,
        format: str
    ) -> str:
        """
        Generate unique filename with timestamp.

        Args:
            product_id: Product identifier
            image_type: Type of image (original, enhanced, thumbnail)
            format: Image format (png, jpeg, webp)

        Returns:
            Filename like "enhanced_20241206_143022_abc123.png"
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Add first 6 chars of product_id hash for uniqueness
        id_hash = hashlib.md5(product_id.encode()).hexdigest()[:6]

        filename = f"{image_type}_{timestamp}_{id_hash}.{format.lower()}"
        return filename

    def _get_product_directory(self, product_id: str) -> Path:
        """Get or create product-specific directory."""
        product_dir = self.products_path / product_id
        product_dir.mkdir(parents=True, exist_ok=True)
        return product_dir

    def save_product_image(
        self,
        image: Image.Image,
        product_id: str,
        image_type: str = "enhanced",
        format: str = "png",
        quality: int = 95,
        optimize: bool = True
    ) -> Dict[str, Any]:
        """
        Save image to disk and optionally upload to cloud.

        Args:
            image: PIL Image object to save
            product_id: Unique product identifier
            image_type: Type of image (original, enhanced, thumbnail)
            format: Image format (png, jpeg, webp)
            quality: JPEG/WebP quality (1-100)
            optimize: Whether to optimize the image

        Returns:
            {
                "success": bool,
                "local_path": str,           # Full absolute path
                "relative_path": str,        # Relative to base_path
                "url": str,                  # URL for serving
                "cloud_url": str (optional), # Cloudinary/S3 URL
                "filename": str,
                "format": str,
                "size_bytes": int,
                "dimensions": {"width": int, "height": int}
            }
        """
        try:
            # Generate filename
            filename = self._generate_filename(product_id, image_type, format)

            # Get product directory
            product_dir = self._get_product_directory(product_id)

            # Full local path
            local_path = product_dir / filename

            # Save locally
            save_kwargs = {"optimize": optimize}

            if format.lower() in ["jpeg", "jpg"]:
                save_kwargs["quality"] = quality
                # Convert RGBA to RGB for JPEG
                if image.mode == "RGBA":
                    rgb_image = Image.new("RGB", image.size, (255, 255, 255))
                    rgb_image.paste(image, mask=image.split()[3])
                    image = rgb_image
            elif format.lower() == "webp":
                save_kwargs["quality"] = quality

            image.save(local_path, format=format.upper(), **save_kwargs)

            # Get file size
            file_size = local_path.stat().st_size

            # Relative path for URLs
            relative_path = local_path.relative_to(self.base_path)

            # Generate serving URL
            url = f"/static/images/{relative_path.as_posix()}"

            result = {
                "success": True,
                "local_path": str(local_path.absolute()),
                "relative_path": str(relative_path),
                "url": url,
                "filename": filename,
                "format": format.lower(),
                "size_bytes": file_size,
                "dimensions": {
                    "width": image.width,
                    "height": image.height
                }
            }

            # Upload to cloud if enabled
            if self.enable_cloud_upload:
                cloud_result = self._upload_to_cloud(
                    local_path=str(local_path),
                    product_id=product_id,
                    image_type=image_type
                )
                if cloud_result:
                    result["cloud_url"] = cloud_result["url"]
                    result["cloud_public_id"] = cloud_result.get("public_id")

            logger.info(f"[SUCCESS] Saved image: {filename} ({file_size:,} bytes)")
            return result

        except Exception as e:
            logger.error(f"[ERROR] Failed to save image: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _upload_to_cloud(
        self,
        local_path: str,
        product_id: str,
        image_type: str
    ) -> Optional[Dict[str, str]]:
        """
        Upload image to cloud storage (Cloudinary or S3).

        Args:
            local_path: Path to local file
            product_id: Product identifier
            image_type: Type of image

        Returns:
            {"url": str, "public_id": str} or None
        """
        # Try Cloudinary first
        if self.cloudinary_client:
            return self._upload_to_cloudinary(local_path, product_id, image_type)

        # Try S3 second
        if self.s3_client:
            return self._upload_to_s3(local_path, product_id, image_type)

        return None

    def _upload_to_cloudinary(
        self,
        local_path: str,
        product_id: str,
        image_type: str
    ) -> Optional[Dict[str, str]]:
        """Upload image to Cloudinary."""
        try:
            # Public ID format: products/{product_id}/{image_type}_{timestamp}
            public_id = f"products/{product_id}/{image_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            result = self.cloudinary_client.uploader.upload(
                local_path,
                public_id=public_id,
                folder="ospra_products",
                resource_type="image"
            )

            logger.info(f"[SUCCESS] Uploaded to Cloudinary: {public_id}")

            return {
                "url": result["secure_url"],
                "public_id": result["public_id"]
            }

        except Exception as e:
            logger.error(f"[ERROR] Cloudinary upload failed: {e}")
            return None

    def _upload_to_s3(
        self,
        local_path: str,
        product_id: str,
        image_type: str
    ) -> Optional[Dict[str, str]]:
        """Upload image to S3."""
        try:
            bucket = self.s3_config["bucket"]
            region = self.s3_config["region"]

            # S3 key format: products/{product_id}/{filename}
            filename = Path(local_path).name
            s3_key = f"products/{product_id}/{filename}"

            # Upload
            self.s3_client.upload_file(
                local_path,
                bucket,
                s3_key,
                ExtraArgs={"ACL": "public-read", "ContentType": self._get_content_type(local_path)}
            )

            # Generate URL
            url = f"https://{bucket}.s3.{region}.amazonaws.com/{s3_key}"

            logger.info(f"[SUCCESS] Uploaded to S3: {s3_key}")

            return {
                "url": url,
                "public_id": s3_key
            }

        except Exception as e:
            logger.error(f"[ERROR] S3 upload failed: {e}")
            return None

    def _get_content_type(self, file_path: str) -> str:
        """Get MIME type for file."""
        extension = Path(file_path).suffix.lower()
        content_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".gif": "image/gif"
        }
        return content_types.get(extension, "application/octet-stream")

    def get_product_images(self, product_id: str) -> List[Dict[str, Any]]:
        """
        Get all images for a product.

        Args:
            product_id: Product identifier

        Returns:
            List of image info dictionaries
        """
        product_dir = self.products_path / product_id

        if not product_dir.exists():
            logger.warning(f"[WARNING]  Product directory not found: {product_id}")
            return []

        images = []

        for image_file in product_dir.glob("*"):
            if image_file.is_file() and image_file.suffix.lower() in [".png", ".jpg", ".jpeg", ".webp"]:
                relative_path = image_file.relative_to(self.base_path)

                # Parse filename: {type}_{timestamp}_{hash}.{ext}
                parts = image_file.stem.split("_")
                image_type = parts[0] if parts else "unknown"

                images.append({
                    "filename": image_file.name,
                    "image_type": image_type,
                    "local_path": str(image_file.absolute()),
                    "relative_path": str(relative_path),
                    "url": f"/static/images/{relative_path.as_posix()}",
                    "size_bytes": image_file.stat().st_size,
                    "created_at": datetime.fromtimestamp(image_file.stat().st_ctime).isoformat()
                })

        logger.debug(f" Found {len(images)} images for product {product_id}")
        return sorted(images, key=lambda x: x["created_at"], reverse=True)

    def get_latest_image(
        self,
        product_id: str,
        image_type: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get the latest image for a product.

        Args:
            product_id: Product identifier
            image_type: Filter by image type (optional)

        Returns:
            Image info dictionary or None
        """
        images = self.get_product_images(product_id)

        if image_type:
            images = [img for img in images if img["image_type"] == image_type]

        return images[0] if images else None

    def delete_product_images(self, product_id: str) -> Dict[str, Any]:
        """
        Delete all images for a product.

        Args:
            product_id: Product identifier

        Returns:
            {"success": bool, "deleted_count": int, "errors": list}
        """
        product_dir = self.products_path / product_id

        if not product_dir.exists():
            return {
                "success": True,
                "deleted_count": 0,
                "message": f"No images found for product {product_id}"
            }

        deleted_count = 0
        errors = []

        try:
            # Delete all files in directory
            for image_file in product_dir.glob("*"):
                try:
                    image_file.unlink()
                    deleted_count += 1
                except Exception as e:
                    errors.append(f"Failed to delete {image_file.name}: {e}")

            # Remove directory
            product_dir.rmdir()

            logger.info(f"[SUCCESS] Deleted {deleted_count} images for product {product_id}")

            return {
                "success": len(errors) == 0,
                "deleted_count": deleted_count,
                "errors": errors
            }

        except Exception as e:
            logger.error(f"[ERROR] Failed to delete images: {e}")
            return {
                "success": False,
                "deleted_count": deleted_count,
                "errors": errors + [str(e)]
            }

    def delete_image(self, product_id: str, filename: str) -> Dict[str, Any]:
        """
        Delete a specific image.

        Args:
            product_id: Product identifier
            filename: Image filename

        Returns:
            {"success": bool, "message": str}
        """
        product_dir = self.products_path / product_id
        image_path = product_dir / filename

        if not image_path.exists():
            return {
                "success": False,
                "message": f"Image not found: {filename}"
            }

        try:
            image_path.unlink()
            logger.info(f"[SUCCESS] Deleted image: {filename}")

            # Remove directory if empty
            if not any(product_dir.iterdir()):
                product_dir.rmdir()

            return {
                "success": True,
                "message": f"Deleted {filename}"
            }

        except Exception as e:
            logger.error(f"[ERROR] Failed to delete image: {e}")
            return {
                "success": False,
                "message": str(e)
            }

    def create_thumbnail(
        self,
        image: Image.Image,
        product_id: str,
        size: tuple = (300, 300),
        format: str = "jpeg"
    ) -> Dict[str, Any]:
        """
        Create and save a thumbnail version of an image.

        Args:
            image: PIL Image object
            product_id: Product identifier
            size: Thumbnail size (width, height)
            format: Image format

        Returns:
            Image storage result
        """
        # Create thumbnail
        thumbnail = image.copy()
        thumbnail.thumbnail(size, Image.Resampling.LANCZOS)

        # Save thumbnail
        return self.save_product_image(
            image=thumbnail,
            product_id=product_id,
            image_type="thumbnail",
            format=format,
            quality=85
        )

    def get_storage_stats(self) -> Dict[str, Any]:
        """
        Get storage statistics.

        Returns:
            Statistics about stored images
        """
        total_size = 0
        total_files = 0
        product_count = 0

        for product_dir in self.products_path.iterdir():
            if product_dir.is_dir():
                product_count += 1
                for image_file in product_dir.glob("*"):
                    if image_file.is_file():
                        total_files += 1
                        total_size += image_file.stat().st_size

        return {
            "total_products": product_count,
            "total_images": total_files,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / 1024 / 1024, 2),
            "base_path": str(self.base_path.absolute()),
            "cloud_enabled": self.enable_cloud_upload
        }


# Convenience function for easy import
def get_image_storage() -> ImageStorage:
    """Get a configured ImageStorage instance."""
    return ImageStorage()


if __name__ == "__main__":
    # Demo usage
    print("  Image Storage Service Demo\n")

    storage = ImageStorage()

    # Create a test image
    test_image = Image.new("RGB", (1024, 1024), color=(73, 109, 137))

    # Save it
    result = storage.save_product_image(
        image=test_image,
        product_id="test-product-123",
        image_type="enhanced",
        format="png"
    )

    print("[SUCCESS] Saved image:")
    print(f"   Local: {result['local_path']}")
    print(f"   URL: {result['url']}")
    print(f"   Size: {result['size_bytes']:,} bytes")

    # Get all images for product
    images = storage.get_product_images("test-product-123")
    print(f"\n Found {len(images)} images for product")

    # Get stats
    stats = storage.get_storage_stats()
    print(f"\n[STATS] Storage stats:")
    print(f"   Products: {stats['total_products']}")
    print(f"   Images: {stats['total_images']}")
    print(f"   Size: {stats['total_size_mb']} MB")

    # Cleanup
    storage.delete_product_images("test-product-123")
    print("\n  Cleaned up test images")
