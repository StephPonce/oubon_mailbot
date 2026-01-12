"""
Shopify Integration for A/B Testing

Applies winning test variants to Shopify stores.
"""

from typing import Dict, Any, Optional
import httpx
from sqlalchemy.orm import Session
from sqlalchemy import select

from ospra_os.database import Store, Product


class ShopifyABTestIntegration:
    """
    Integrates A/B test winners with Shopify stores

    Handles:
    - Updating product prices
    - Updating product titles
    - Updating product descriptions
    - Updating product images
    """

    def __init__(self, db_session: Session):
        self.db = db_session

    def get_shopify_credentials(self, store_id: str) -> Optional[Dict[str, str]]:
        """Get Shopify API credentials for a store"""
        result = self.db.execute(
            select(Store).where(Store.id == int(store_id))
        )
        store = result.scalar_one_or_none()

        if not store:
            raise ValueError(f"Store {store_id} not found")

        if store.platform != "shopify":
            raise ValueError(f"Store {store_id} is not a Shopify store")

        # Extract Shopify credentials from store.credentials JSON
        creds = store.get_credentials()

        return {
            "shop_url": creds.get("shop_url"),
            "access_token": creds.get("access_token"),
            "api_version": creds.get("api_version", "2025-01")
        }

    def update_product_price(
        self,
        store_id: str,
        product_id: str,
        new_price: float
    ) -> Dict[str, Any]:
        """
        Update product price in Shopify

        Args:
            store_id: Store ID
            product_id: Product ID (Shopify product ID)
            new_price: New price to set

        Returns:
            Result dict with success status
        """
        try:
            creds = self.get_shopify_credentials(store_id)

            # Shopify Admin API endpoint
            url = f"https://{creds['shop_url']}/admin/api/{creds['api_version']}/products/{product_id}.json"

            headers = {
                "X-Shopify-Access-Token": creds["access_token"],
                "Content-Type": "application/json"
            }

            # Update product variants with new price
            # First, get current product to update variants
            with httpx.Client() as client:
                # Get product
                get_response = client.get(url, headers=headers)
                get_response.raise_for_status()
                product_data = get_response.json()

                # Update all variant prices
                for variant in product_data["product"]["variants"]:
                    variant["price"] = str(new_price)

                # Update product
                update_payload = {
                    "product": {
                        "id": product_id,
                        "variants": product_data["product"]["variants"]
                    }
                }

                put_response = client.put(
                    url,
                    headers=headers,
                    json=update_payload
                )
                put_response.raise_for_status()

            return {
                "success": True,
                "message": f"Price updated to ${new_price:.2f}",
                "product_id": product_id,
                "new_price": new_price
            }

        except httpx.HTTPStatusError as e:
            return {
                "success": False,
                "error": f"Shopify API error: {e.response.status_code}",
                "message": str(e)
            }
        except Exception as e:
            return {
                "success": False,
                "error": "Update failed",
                "message": str(e)
            }

    def update_product_title(
        self,
        store_id: str,
        product_id: str,
        new_title: str
    ) -> Dict[str, Any]:
        """
        Update product title in Shopify

        Args:
            store_id: Store ID
            product_id: Product ID (Shopify product ID)
            new_title: New title to set

        Returns:
            Result dict with success status
        """
        try:
            creds = self.get_shopify_credentials(store_id)

            url = f"https://{creds['shop_url']}/admin/api/{creds['api_version']}/products/{product_id}.json"

            headers = {
                "X-Shopify-Access-Token": creds["access_token"],
                "Content-Type": "application/json"
            }

            payload = {
                "product": {
                    "id": product_id,
                    "title": new_title
                }
            }

            with httpx.Client() as client:
                response = client.put(url, headers=headers, json=payload)
                response.raise_for_status()

            return {
                "success": True,
                "message": f"Title updated to: {new_title}",
                "product_id": product_id,
                "new_title": new_title
            }

        except httpx.HTTPStatusError as e:
            return {
                "success": False,
                "error": f"Shopify API error: {e.response.status_code}",
                "message": str(e)
            }
        except Exception as e:
            return {
                "success": False,
                "error": "Update failed",
                "message": str(e)
            }

    def update_product_description(
        self,
        store_id: str,
        product_id: str,
        new_description: str
    ) -> Dict[str, Any]:
        """
        Update product description in Shopify

        Args:
            store_id: Store ID
            product_id: Product ID (Shopify product ID)
            new_description: New description (HTML supported)

        Returns:
            Result dict with success status
        """
        try:
            creds = self.get_shopify_credentials(store_id)

            url = f"https://{creds['shop_url']}/admin/api/{creds['api_version']}/products/{product_id}.json"

            headers = {
                "X-Shopify-Access-Token": creds["access_token"],
                "Content-Type": "application/json"
            }

            payload = {
                "product": {
                    "id": product_id,
                    "body_html": new_description
                }
            }

            with httpx.Client() as client:
                response = client.put(url, headers=headers, json=payload)
                response.raise_for_status()

            return {
                "success": True,
                "message": "Description updated successfully",
                "product_id": product_id
            }

        except httpx.HTTPStatusError as e:
            return {
                "success": False,
                "error": f"Shopify API error: {e.response.status_code}",
                "message": str(e)
            }
        except Exception as e:
            return {
                "success": False,
                "error": "Update failed",
                "message": str(e)
            }

    def update_product_image(
        self,
        store_id: str,
        product_id: str,
        new_image_url: str
    ) -> Dict[str, Any]:
        """
        Update product primary image in Shopify

        Args:
            store_id: Store ID
            product_id: Product ID (Shopify product ID)
            new_image_url: New image URL

        Returns:
            Result dict with success status
        """
        try:
            creds = self.get_shopify_credentials(store_id)

            # First, get product to get image ID
            get_url = f"https://{creds['shop_url']}/admin/api/{creds['api_version']}/products/{product_id}.json"

            headers = {
                "X-Shopify-Access-Token": creds["access_token"],
                "Content-Type": "application/json"
            }

            with httpx.Client() as client:
                # Get product
                get_response = client.get(get_url, headers=headers)
                get_response.raise_for_status()
                product_data = get_response.json()

                # Create new image (Shopify will download from URL)
                images_url = f"https://{creds['shop_url']}/admin/api/{creds['api_version']}/products/{product_id}/images.json"

                image_payload = {
                    "image": {
                        "src": new_image_url,
                        "position": 1  # Make it the primary image
                    }
                }

                post_response = client.post(
                    images_url,
                    headers=headers,
                    json=image_payload
                )
                post_response.raise_for_status()

            return {
                "success": True,
                "message": "Image updated successfully",
                "product_id": product_id,
                "new_image_url": new_image_url
            }

        except httpx.HTTPStatusError as e:
            return {
                "success": False,
                "error": f"Shopify API error: {e.response.status_code}",
                "message": str(e)
            }
        except Exception as e:
            return {
                "success": False,
                "error": "Update failed",
                "message": str(e)
            }

    def verify_shopify_connection(self, store_id: str) -> Dict[str, Any]:
        """
        Verify Shopify API connection

        Args:
            store_id: Store ID to verify

        Returns:
            Connection status
        """
        try:
            creds = self.get_shopify_credentials(store_id)

            url = f"https://{creds['shop_url']}/admin/api/{creds['api_version']}/shop.json"

            headers = {
                "X-Shopify-Access-Token": creds["access_token"]
            }

            with httpx.Client() as client:
                response = client.get(url, headers=headers)
                response.raise_for_status()
                shop_data = response.json()

            return {
                "success": True,
                "connected": True,
                "shop_name": shop_data["shop"]["name"],
                "shop_domain": shop_data["shop"]["domain"]
            }

        except Exception as e:
            return {
                "success": False,
                "connected": False,
                "error": str(e)
            }

    def apply_test_winner(
        self,
        test_type: str,
        store_id: str,
        product_id: str,
        winning_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Apply winning test variant to Shopify product

        Args:
            test_type: Type of test (price, product_title, product_description, product_image)
            store_id: Store ID
            product_id: Product ID
            winning_config: Winning variant configuration

        Returns:
            Result dict with success status
        """
        if test_type == "price":
            return self.update_product_price(
                store_id,
                product_id,
                winning_config.get("price")
            )

        elif test_type == "product_title":
            return self.update_product_title(
                store_id,
                product_id,
                winning_config.get("title")
            )

        elif test_type == "product_description":
            return self.update_product_description(
                store_id,
                product_id,
                winning_config.get("description")
            )

        elif test_type == "product_image":
            return self.update_product_image(
                store_id,
                product_id,
                winning_config.get("image_url")
            )

        else:
            return {
                "success": False,
                "error": f"Unsupported test type: {test_type}"
            }


print("[SUCCESS] Shopify A/B Testing integration loaded successfully")
