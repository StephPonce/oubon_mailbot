"""
Shopify API Client - Product deployment and management
"""
import os
import httpx
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()


class ShopifyClient:
    """Client for Shopify Admin API"""

    def __init__(self, store_name: str = None, access_token: str = None):
        """
        Initialize Shopify client

        Args:
            store_name: Your Shopify store name (e.g., 'oubon-shop')
            access_token: Shopify Admin API access token
        """
        self.store_name = store_name or os.getenv('SHOPIFY_STORE_NAME')
        self.access_token = access_token or os.getenv('SHOPIFY_ACCESS_TOKEN')

        if not self.store_name or not self.access_token:
            raise ValueError("Shopify credentials not found in environment")

        self.base_url = f"https://{self.store_name}.myshopify.com/admin/api/2024-10"
        self.headers = {
            'X-Shopify-Access-Token': self.access_token,
            'Content-Type': 'application/json'
        }

    async def create_product(
        self,
        title: str,
        description: str,
        price: float,
        images: List[str],
        vendor: str = "Oubon Shop",
        tags: List[str] = None,
        variants: List[Dict] = None,
        inventory_quantity: int = 100,
        meta_fields: Dict = None
    ) -> Dict:
        """
        Create a new product in Shopify

        Returns:
            Product data with Shopify product ID
        """
        try:
            print(f"🛍️  Creating Shopify product: {title[:50]}")

            # Build product data
            product_data = {
                "product": {
                    "title": title,
                    "body_html": description,
                    "vendor": vendor,
                    "product_type": "Physical",
                    "tags": ",".join(tags) if tags else "",
                    "published": True,
                    "status": "active"
                }
            }

            # Add variants (pricing/inventory)
            if variants:
                product_data["product"]["variants"] = variants
            else:
                product_data["product"]["variants"] = [{
                    "price": str(price),
                    "inventory_management": "shopify",
                    "inventory_quantity": inventory_quantity,
                    "requires_shipping": True
                }]

            # Add images
            if images:
                product_data["product"]["images"] = [
                    {"src": img_url} for img_url in images
                ]

            # Create product
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/products.json",
                    headers=self.headers,
                    json=product_data
                )

                if response.status_code not in [200, 201]:
                    print(f"❌ Shopify API error: {response.status_code}")
                    print(response.text)
                    return None

                result = response.json()
                product = result.get('product', {})

                print(f"✅ Product created! ID: {product.get('id')}")

                # Add metafields if provided
                if meta_fields and product.get('id'):
                    await self._add_metafields(product['id'], meta_fields)

                return product

        except Exception as e:
            print(f"❌ Error creating product: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def update_product(
        self,
        product_id: int,
        updates: Dict
    ) -> Dict:
        """Update an existing Shopify product"""
        try:
            print(f"📝 Updating product {product_id}")

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.put(
                    f"{self.base_url}/products/{product_id}.json",
                    headers=self.headers,
                    json={"product": updates}
                )

                if response.status_code != 200:
                    print(f"❌ Update failed: {response.status_code}")
                    return None

                result = response.json()
                print(f"✅ Product updated!")
                return result.get('product')

        except Exception as e:
            print(f"❌ Error updating product: {e}")
            return None

    async def delete_product(self, product_id: int) -> bool:
        """Delete a product from Shopify"""
        try:
            print(f"🗑️  Deleting product {product_id}")

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.delete(
                    f"{self.base_url}/products/{product_id}.json",
                    headers=self.headers
                )

                if response.status_code == 200:
                    print(f"✅ Product deleted!")
                    return True
                else:
                    print(f"❌ Delete failed: {response.status_code}")
                    return False

        except Exception as e:
            print(f"❌ Error deleting product: {e}")
            return False

    async def get_product(self, product_id: int) -> Dict:
        """Get product details from Shopify"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/products/{product_id}.json",
                    headers=self.headers
                )

                if response.status_code == 200:
                    result = response.json()
                    return result.get('product')
                return None

        except Exception as e:
            print(f"❌ Error getting product: {e}")
            return None

    async def list_products(
        self,
        limit: int = 50,
        published_status: str = "any"
    ) -> List[Dict]:
        """List products from Shopify store"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/products.json",
                    headers=self.headers,
                    params={
                        "limit": limit,
                        "published_status": published_status
                    }
                )

                if response.status_code == 200:
                    result = response.json()
                    return result.get('products', [])
                return []

        except Exception as e:
            print(f"❌ Error listing products: {e}")
            return []

    async def _add_metafields(
        self,
        product_id: int,
        meta_fields: Dict
    ) -> bool:
        """
        Add metafields to product for tracking

        Metafields store hidden data like:
        - AliExpress fulfillment URL
        - Original Amazon URL
        - Trend scores
        - Discovery date
        """
        try:
            for key, value in meta_fields.items():
                metafield_data = {
                    "metafield": {
                        "namespace": "ospra",
                        "key": key,
                        "value": str(value),
                        "type": "single_line_text_field"
                    }
                }

                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        f"{self.base_url}/products/{product_id}/metafields.json",
                        headers=self.headers,
                        json=metafield_data
                    )

                    if response.status_code not in [200, 201]:
                        print(f"⚠️  Failed to add metafield {key}")

            return True

        except Exception as e:
            print(f"⚠️  Error adding metafields: {e}")
            return False

    async def update_inventory(
        self,
        variant_id: int,
        quantity: int,
        location_id: int = None
    ) -> bool:
        """Update inventory quantity for a product variant"""
        try:
            # Get inventory item ID
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/variants/{variant_id}.json",
                    headers=self.headers
                )

                if response.status_code != 200:
                    return False

                variant = response.json().get('variant', {})
                inventory_item_id = variant.get('inventory_item_id')

                if not inventory_item_id:
                    return False

                # Get location if not provided
                if not location_id:
                    loc_response = await client.get(
                        f"{self.base_url}/locations.json",
                        headers=self.headers
                    )

                    if loc_response.status_code == 200:
                        locations = loc_response.json().get('locations', [])
                        if locations:
                            location_id = locations[0]['id']

                # Update inventory
                inventory_data = {
                    "location_id": location_id,
                    "inventory_item_id": inventory_item_id,
                    "available": quantity
                }

                inv_response = await client.post(
                    f"{self.base_url}/inventory_levels/set.json",
                    headers=self.headers,
                    json=inventory_data
                )

                if inv_response.status_code == 200:
                    print(f"✅ Inventory updated to {quantity}")
                    return True

                return False

        except Exception as e:
            print(f"❌ Error updating inventory: {e}")
            return False
