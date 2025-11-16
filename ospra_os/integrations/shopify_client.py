import os
import requests
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    from ospra_os.utils.image_handler import ImageHandler
except ImportError:
    ImageHandler = None
    logger.warning("ImageHandler not available - images will use direct URLs")

class ShopifyClient:
    """Shopify API client for product management"""

    def __init__(self):
        self.store_url = os.getenv("SHOPIFY_STORE_URL")  # e.g., "oubon-shop.myshopify.com"
        self.access_token = os.getenv("SHOPIFY_ACCESS_TOKEN")
        self.api_version = "2024-01"  # Lock version to prevent breaking changes

        if not self.store_url or not self.access_token:
            logger.warning("Shopify credentials not configured")
            self.enabled = False
        else:
            self.enabled = True
            self.base_url = f"https://{self.store_url}/admin/api/{self.api_version}"

        # Initialize AI description generator
        try:
            from ospra_os.intelligence.product_description_generator import ProductDescriptionGenerator
            self.description_generator = ProductDescriptionGenerator()
            logger.info("✅ AI Description Generator initialized")
        except Exception as e:
            logger.warning(f"AI Description Generator not available: {e}")
            self.description_generator = None

        # Initialize Image Handler
        if ImageHandler:
            self.image_handler = ImageHandler()
            logger.info("✅ Image Handler initialized")
        else:
            self.image_handler = None
            logger.warning("Image Handler not available")

    def _make_request(self, method: str, endpoint: str, data: Dict = None) -> Optional[Dict]:
        """Make authenticated request to Shopify API"""

        if not self.enabled:
            logger.error("Shopify not configured")
            return None

        url = f"{self.base_url}/{endpoint}.json"
        headers = {
            "X-Shopify-Access-Token": self.access_token,
            "Content-Type": "application/json"
        }

        try:
            if method == "GET":
                response = requests.get(url, headers=headers, timeout=30)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=data, timeout=30)
            elif method == "PUT":
                response = requests.put(url, headers=headers, json=data, timeout=30)
            elif method == "DELETE":
                response = requests.delete(url, headers=headers, timeout=30)

            if response.status_code in [200, 201]:
                return response.json()
            else:
                logger.error(f"Shopify API error: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            logger.error(f"Shopify request failed: {e}")
            return None

    def create_product(self, product_data: Dict) -> Optional[Dict]:
        """
        Create product on Shopify from Ospra product data

        Returns Shopify product ID if successful
        """

        # Process images BEFORE creating product
        if self.image_handler and product_data.get("image_url"):
            try:
                logger.info(f"📸 Processing images for: {product_data['name']}")
                product_data = self.image_handler.process_product_images(product_data, self)
            except Exception as e:
                logger.warning(f"Image processing failed: {e}")

        # Get AI-generated content if available
        ai_content = None
        if self.description_generator:
            try:
                ai_content = self.description_generator.generate_shopify_description(product_data)
                logger.info(f"✅ AI content generated for: {product_data['name']}")
            except Exception as e:
                logger.warning(f"AI content generation failed: {e}")

        # Use AI title if available, otherwise use original name
        title = ai_content["title"] if ai_content else product_data["name"]

        # Use AI description if available, otherwise generate basic one
        description = ai_content["description"] if ai_content else self._generate_description(product_data)

        # Use AI keywords for tags if available
        if ai_content and ai_content.get("seo_keywords"):
            tags = ", ".join(ai_content["seo_keywords"])
        else:
            tags = f"{product_data.get('niche', '')}, dropshipping, trending"

        # Convert Ospra format to Shopify format
        shopify_product = {
            "product": {
                "title": title,
                "body_html": description,
                "vendor": "AliExpress",
                "product_type": product_data.get("category", "General"),
                "tags": tags,
                "variants": [
                    {
                        "price": str(product_data["price"]),
                        "compare_at_price": str(product_data["price"] * 1.3),  # Show discount
                        "inventory_management": None,  # Don't track inventory for dropshipping
                        "fulfillment_service": "manual"
                    }
                ],
                "images": []
            }
        }

        # Add image (use processed image if available)
        if product_data.get("shopify_image"):
            shopify_product["product"]["images"] = [product_data["shopify_image"]]
            logger.info("✅ Using processed Shopify image")
        elif product_data.get("image_url"):
            # Fallback: use direct URL (might break later)
            shopify_product["product"]["images"] = [{"src": product_data["image_url"]}]
            logger.warning("⚠️ Using direct image URL (may break if source blocks)")

        logger.info(f"Creating product on Shopify: {title}")
        result = self._make_request("POST", "products", shopify_product)

        if result and "product" in result:
            shopify_id = result["product"]["id"]
            logger.info(f"✅ Product created on Shopify: ID {shopify_id}")
            return result["product"]

        return None

    def _generate_description(self, product_data: Dict) -> str:
        """Generate SEO-optimized product description using AI"""

        # Try AI generation first
        if self.description_generator:
            try:
                ai_result = self.description_generator.generate_shopify_description(product_data)
                logger.info(f"✅ AI-generated description for: {product_data['name']}")
                return ai_result["description"]
            except Exception as e:
                logger.warning(f"AI generation failed, using fallback: {e}")

        # Fallback to basic description
        description = product_data.get("description", "")

        if not description:
            # Basic description if none provided
            description = f"<h2>{product_data['name']}</h2>"

        # Add features if available
        features = product_data.get("features", [])
        if features:
            description += "<h3>Key Features:</h3><ul>"
            for feature in features:
                description += f"<li>{feature}</li>"
            description += "</ul>"

        # Add use cases
        use_cases = product_data.get("use_cases", [])
        if use_cases:
            description += "<h3>Perfect For:</h3><ul>"
            for use_case in use_cases:
                description += f"<li>{use_case}</li>"
            description += "</ul>"

        # Add shipping info
        description += """
        <h3>Shipping & Delivery:</h3>
        <p>Free worldwide shipping. Estimated delivery: 10-25 business days.</p>

        <h3>Quality Guarantee:</h3>
        <p>30-day money-back guarantee. If you're not satisfied, return it for a full refund.</p>
        """

        return description

    def get_product(self, shopify_id: str) -> Optional[Dict]:
        """Get product from Shopify"""
        result = self._make_request("GET", f"products/{shopify_id}")
        return result.get("product") if result else None

    def product_exists(self, shopify_id: str) -> bool:
        """Check if product still exists on Shopify"""
        product = self.get_product(shopify_id)
        return product is not None

    def update_product_price(self, shopify_id: str, new_price: float) -> bool:
        """Update product price on Shopify"""

        # Get current product
        product = self.get_product(shopify_id)
        if not product:
            return False

        # Update variant price
        variant_id = product["variants"][0]["id"]

        update_data = {
            "variant": {
                "id": variant_id,
                "price": str(new_price)
            }
        }

        result = self._make_request("PUT", f"variants/{variant_id}", update_data)
        return result is not None

    def delete_product(self, shopify_id: str) -> bool:
        """Delete product from Shopify"""
        result = self._make_request("DELETE", f"products/{shopify_id}")
        return result is not None

    def list_products(self, limit: int = 50) -> List[Dict]:
        """List all products on Shopify"""
        result = self._make_request("GET", f"products?limit={limit}")
        return result.get("products", []) if result else []

    def fulfill_order(self, order_id: str, tracking_number: str, tracking_url: str, tracking_company: str = "Other") -> bool:
        """
        Fulfill order in Shopify with tracking info

        Args:
            order_id: Shopify order ID
            tracking_number: Tracking number
            tracking_url: Tracking URL
            tracking_company: Carrier name (UPS, USPS, FedEx, DHL, Other)

        Returns:
            True if fulfillment created successfully
        """

        if not self.enabled:
            logger.error("Shopify not configured")
            return False

        try:
            # Get order to find fulfillment details
            order = self._make_request("GET", f"orders/{order_id}")

            if not order or "order" not in order:
                logger.error(f"Order {order_id} not found")
                return False

            order_data = order["order"]
            line_items = order_data.get("line_items", [])

            if not line_items:
                logger.error("No line items in order")
                return False

            # Create fulfillment
            fulfillment_data = {
                "fulfillment": {
                    "location_id": order_data.get("location_id"),
                    "tracking_number": tracking_number,
                    "tracking_url": tracking_url,
                    "tracking_company": tracking_company,
                    "notify_customer": True,  # Shopify sends email
                    "line_items": [
                        {
                            "id": item["id"],
                            "quantity": item["quantity"]
                        }
                        for item in line_items
                    ]
                }
            }

            # Create fulfillment
            result = self._make_request(
                "POST",
                f"orders/{order_id}/fulfillments",
                fulfillment_data
            )

            if result and "fulfillment" in result:
                logger.info(f"✅ Order {order_id} fulfilled in Shopify")
                return True
            else:
                logger.error(f"Failed to create fulfillment: {result}")
                return False

        except Exception as e:
            logger.error(f"Shopify fulfillment failed: {e}")
            return False
