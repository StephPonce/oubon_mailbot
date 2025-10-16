"""
Custom sourcing utilities for importing products and fulfilling orders without third-party apps.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from app.settings import get_settings
from app.shopify_client import _shopify_graphql

ALIEXPRESS_SEARCH_URL = "https://api.aliexpress.com/v1/products/search"


def _fetch_aliexpress_product(product_name: str, api_key: str) -> Dict[str, Any]:
    headers = {"Authorization": f"Bearer {api_key}"}
    params = {"query": product_name, "limit": 1}
    try:
        response = requests.get(ALIEXPRESS_SEARCH_URL, headers=headers, params=params, timeout=15)
        response.raise_for_status()
        payload = response.json()
    except requests.exceptions.RequestException as exc:  # pragma: no cover - network issues
        raise RuntimeError(f"AliExpress API request failed: {exc}") from exc
    except ValueError as exc:
        raise RuntimeError("AliExpress API returned invalid JSON.") from exc

    products = payload.get("products") or []
    if not products:
        raise ValueError(f"No AliExpress products found for '{product_name}'.")
    return products[0]


def _ensure_price(value: Any) -> str:
    try:
        price_float = float(value)
    except (TypeError, ValueError):
        price_float = 10.0
    return f"{price_float:.2f}"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=4, max=10))
def custom_import_products(product_name: str, store_token: Optional[str] = None) -> str:
    """
    Look up a product on AliExpress and create it in Shopify via GraphQL.
    """
    if not product_name:
        raise ValueError("product_name is required.")

    settings = get_settings()
    if not settings.ALIEXPRESS_API_KEY:
        raise ValueError("ALIEXPRESS_API_KEY missing in .env—signup developer.aliexpress.com for keys")

    ali_product = _fetch_aliexpress_product(product_name, settings.ALIEXPRESS_API_KEY)
    price = _ensure_price(ali_product.get("price") or ali_product.get("sale_price"))
    inventory = int(ali_product.get("stock") or 100)

    mutation = """
    mutation productCreate($input: ProductInput!) {
      productCreate(input: $input) {
        product { id }
        userErrors { field message }
      }
    }
    """
    variables = {
        "input": {
            "title": product_name,
            "variants": [
                {
                    "price": price,
                    "inventoryQuantity": inventory,
                }
            ],
        }
    }
    data = _shopify_graphql(mutation, variables=variables, access_token=store_token or None)
    if not data:
        raise RuntimeError("Shopify GraphQL productCreate returned no data.")

    errors = (data.get("productCreate") or {}).get("userErrors") or []
    if errors:
        raise RuntimeError(f"Shopify productCreate error: {errors}")

    product = (data.get("productCreate") or {}).get("product") or {}
    return product.get("id", "Failed—check logs")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=4, max=10))
def custom_fulfill_order(order_id: str, tracking: str, store_token: Optional[str] = None) -> str:
    """
    Fulfill a Shopify order via GraphQL Fulfillment API using a custom supplier.
    """
    if not order_id or not tracking:
        raise ValueError("order_id and tracking are required.")

    mutation = """
    mutation fulfillmentCreate($fulfillment: FulfillmentV2Input!, $orderId: ID!) {
      fulfillmentCreateV2(fulfillment: $fulfillment, orderId: $orderId) {
        fulfillment { id }
        userErrors { field message }
      }
    }
    """
    variables = {
        "orderId": order_id,
        "fulfillment": {
            "notifyCustomer": True,
            "trackingInfo": {"number": tracking, "company": "Custom Supplier"},
        },
    }
    data = _shopify_graphql(mutation, variables=variables, access_token=store_token or None)
    if not data:
        raise RuntimeError("Shopify GraphQL fulfillmentCreateV2 returned no data.")

    errors = (data.get("fulfillmentCreateV2") or {}).get("userErrors") or []
    if errors:
        raise RuntimeError(f"Shopify fulfillmentCreateV2 error: {errors}")

    fulfillment = (data.get("fulfillmentCreateV2") or {}).get("fulfillment") or {}
    return fulfillment.get("id", "Failed—check logs")


__all__ = ["custom_import_products", "custom_fulfill_order"]
