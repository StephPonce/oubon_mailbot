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
            print(f"[SHOP]  Creating Shopify product: {title[:50]}")

            # Build product data
            product_data = {
                "product": {
                    "title": title,
                    "body_html": description,
                    "vendor": vendor,
                    "product_type": "",  # Empty - 'Physical' shows as ugly link on storefront
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
                    print(f"[ERROR] Shopify API error: {response.status_code}")
                    print(response.text)
                    return None

                result = response.json()
                product = result.get('product', {})

                print(f"[SUCCESS] Product created! ID: {product.get('id')}")

                # Add metafields if provided
                if meta_fields and product.get('id'):
                    await self._add_metafields(product['id'], meta_fields)

                return product

        except Exception as e:
            print(f"[ERROR] Error creating product: {e}")
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
            print(f"[NOTE] Updating product {product_id}")

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.put(
                    f"{self.base_url}/products/{product_id}.json",
                    headers=self.headers,
                    json={"product": updates}
                )

                if response.status_code != 200:
                    print(f"[ERROR] Update failed: {response.status_code}")
                    return None

                result = response.json()
                print(f"[SUCCESS] Product updated!")
                return result.get('product')

        except Exception as e:
            print(f"[ERROR] Error updating product: {e}")
            return None

    async def delete_product(self, product_id: int) -> bool:
        """Delete a product from Shopify"""
        try:
            print(f"  Deleting product {product_id}")

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.delete(
                    f"{self.base_url}/products/{product_id}.json",
                    headers=self.headers
                )

                if response.status_code == 200:
                    print(f"[SUCCESS] Product deleted!")
                    return True
                else:
                    print(f"[ERROR] Delete failed: {response.status_code}")
                    return False

        except Exception as e:
            print(f"[ERROR] Error deleting product: {e}")
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
            print(f"[ERROR] Error getting product: {e}")
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
            print(f"[ERROR] Error listing products: {e}")
            return []

    async def get_shop_info(self) -> Dict:
        """Get shop information from Shopify"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/shop.json",
                    headers=self.headers
                )

                if response.status_code == 200:
                    result = response.json()
                    return result.get('shop', {})
                return {}

        except Exception as e:
            print(f"[ERROR] Error getting shop info: {e}")
            return {}

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
                        print(f"[WARNING]  Failed to add metafield {key}")

            return True

        except Exception as e:
            print(f"[WARNING]  Error adding metafields: {e}")
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
                    print(f"[SUCCESS] Inventory updated to {quantity}")
                    return True

                return False

        except Exception as e:
            print(f"[ERROR] Error updating inventory: {e}")
            return False

    async def publish_to_online_store(self, product_id: int) -> bool:
        """
        Publish a product to the Online Store sales channel using GraphQL.

        Products created via API are often not visible on the storefront
        until explicitly published to the Online Store channel.

        Requires: write_publications scope
        """
        try:
            print(f" Publishing product {product_id} to Online Store...")

            graphql_url = f"{self.base_url}/graphql.json"
            gid = f"gid://shopify/Product/{product_id}"

            async with httpx.AsyncClient(timeout=30.0) as client:
                # Step 1: Get Online Store publication ID
                pubs_query = """
                {
                  publications(first: 10) {
                    edges {
                      node {
                        id
                        name
                      }
                    }
                  }
                }
                """

                pubs_resp = await client.post(
                    graphql_url,
                    headers=self.headers,
                    json={"query": pubs_query}
                )

                if pubs_resp.status_code != 200:
                    print(f"[ERROR] Failed to fetch publications: {pubs_resp.status_code}")
                    return False

                result = pubs_resp.json()
                if 'errors' in result:
                    print(f"[WARNING]  GraphQL errors: {result['errors']}")
                    return False

                # Find Online Store publication
                online_store_pub_id = None
                if 'data' in result and 'publications' in result['data']:
                    pubs = result['data']['publications']['edges']
                    for edge in pubs:
                        pub = edge['node']
                        if 'Online Store' in pub['name']:
                            online_store_pub_id = pub['id']
                            break

                if not online_store_pub_id:
                    print(f"[WARNING]  Could not find Online Store publication")
                    return False

                # Step 2: Publish product to Online Store
                publish_mutation = """
                mutation publishProduct($id: ID!, $input: [PublicationInput!]!) {
                  publishablePublish(id: $id, input: $input) {
                    publishable {
                      ... on Product {
                        id
                        title
                      }
                    }
                    userErrors {
                      field
                      message
                    }
                  }
                }
                """

                mutation_data = {
                    "query": publish_mutation,
                    "variables": {
                        "id": gid,
                        "input": [{"publicationId": online_store_pub_id}]
                    }
                }

                pub_resp = await client.post(
                    graphql_url,
                    headers=self.headers,
                    json=mutation_data
                )

                if pub_resp.status_code != 200:
                    print(f"[ERROR] Publish mutation failed: {pub_resp.status_code}")
                    return False

                result = pub_resp.json()
                if 'errors' in result:
                    print(f"[WARNING]  GraphQL errors: {result['errors']}")
                    return False

                data = result['data']['publishablePublish']
                errors = data.get('userErrors', [])

                if errors:
                    print(f"[WARNING]  User errors: {errors}")
                    return False

                print(f"[SUCCESS] Product published to Online Store!")
                return True

        except Exception as e:
            print(f"[ERROR] Error publishing product: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def create_and_publish_product(
        self,
        title: str,
        description: str,
        price: float,
        images: List[str],
        vendor: str = "Oubon Shop",
        tags: List[str] = None,
        variants: List[Dict] = None,
        inventory_quantity: int = 100,
        meta_fields: Dict = None,
        add_to_featured: bool = True
    ) -> Dict:
        """
        Create a product AND publish it to the Online Store.

        This is the recommended method for deploying products that
        should be immediately visible on your storefront.

        Args:
            add_to_featured: If True, adds product to "Featured Products" collection (default: True)
        """
        # Create the product first
        product = await self.create_product(
            title=title,
            description=description,
            price=price,
            images=images,
            vendor=vendor,
            tags=tags,
            variants=variants,
            inventory_quantity=inventory_quantity,
            meta_fields=meta_fields
        )

        if product and product.get('id'):
            product_id = product['id']

            # Publish it to the Online Store
            await self.publish_to_online_store(product_id)

            # Add to Featured Products collection for immediate visibility
            if add_to_featured:
                await self.add_to_featured_collection(product_id)

        return product

    async def add_to_featured_collection(self, product_id: int) -> bool:
        """
        Add product to the 'Featured Products' custom collection.

        This ensures the product appears on the storefront immediately.
        If the collection doesn't exist, it will be created.
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Try to find or create the "Featured Products" collection
                colls_resp = await client.get(
                    f"{self.base_url}/custom_collections.json",
                    headers=self.headers
                )

                featured_collection_id = None

                if colls_resp.status_code == 200:
                    collections = colls_resp.json().get('custom_collections', [])
                    featured = [c for c in collections if 'Featured' in c.get('title', '')]

                    if featured:
                        featured_collection_id = featured[0]['id']
                    else:
                        # Create the collection
                        collection_data = {
                            'custom_collection': {
                                'title': 'Featured Products',
                                'body_html': '<p>Our hand-picked featured products - trending now!</p>',
                                'published': True,
                                'published_scope': 'global'
                            }
                        }

                        coll_resp = await client.post(
                            f"{self.base_url}/custom_collections.json",
                            headers=self.headers,
                            json=collection_data
                        )

                        if coll_resp.status_code in [200, 201]:
                            featured_collection_id = coll_resp.json()['custom_collection']['id']

                # Add product to the collection
                if featured_collection_id:
                    collect_data = {
                        'collect': {
                            'product_id': product_id,
                            'collection_id': featured_collection_id
                        }
                    }

                    collect_resp = await client.post(
                        f"{self.base_url}/collects.json",
                        headers=self.headers,
                        json=collect_data
                    )

                    if collect_resp.status_code in [200, 201]:
                        print(f"[SUCCESS] Added product to 'Featured Products' collection")
                        return True

                return False

        except Exception as e:
            print(f"[WARNING]  Could not add to featured collection: {e}")
            return False
