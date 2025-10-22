from __future__ import annotations
from typing import Optional, Dict, Any, List
import httpx

from ospra_os.core.settings import Settings

# -------- internal helpers --------
def _settings() -> Settings:
    return Settings()


def _base_url(s: Settings) -> str:
    store = s.SHOPIFY_STORE or s.SHOPIFY_STORE_DOMAIN
    if not store:
        raise RuntimeError("Missing SHOPIFY_STORE or SHOPIFY_STORE_DOMAIN in env")
    ver = s.SHOPIFY_API_VERSION or "2025-10"
    return f"https://{store}/admin/api/{ver}"


def _auth_headers(s: Settings) -> dict:
    token = s.SHOPIFY_ADMIN_TOKEN or s.SHOPIFY_API_TOKEN
    if not token:
        raise RuntimeError("Missing SHOPIFY_ADMIN_TOKEN or SHOPIFY_API_TOKEN")
    return {
        "X-Shopify-Access-Token": token,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


# -------- function used by Gmail worker --------
async def get_order_by_name(order_no: str) -> Optional[Dict[str, Any]]:
    """
    Look up a Shopify order by its 'name' (e.g. '#1234').
    Returns a minimal dict used by the Gmail worker.
    """
    s = _settings()
    base = _base_url(s)
    headers = _auth_headers(s)

    name = order_no if order_no.startswith("#") else f"#{order_no}"

    timeout = httpx.Timeout(10.0, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(
            f"{base}/orders.json",
            headers=headers,
            params={"name": name, "status": "any", "limit": "1"},
        )
        resp.raise_for_status()
        data = resp.json() or {}
        orders = data.get("orders") or []
        if not orders:
            return None
        o = orders[0]
        return {
            "name": o.get("name"),
            "financial_status": o.get("financial_status"),
            "fulfillment_status": o.get("fulfillment_status"),
            "fulfillments": o.get("fulfillments") or [],
        }


# -------- minimal class shim expected by catalog/routes.py --------
class Shopify:
    """
    Minimal shim so `from ospra_os.integrations.shopify import Shopify` works.

    We’ll flesh this out when we wire the product research & dashboard.
    For now, endpoints that might call these will return safe defaults.
    """

    def __init__(self, settings: Optional[Settings] = None):
        self.s = settings or _settings()
        self.base = _base_url(self.s)
        self.headers = _auth_headers(self.s)

    # common reads (return safe defaults for now)
    async def list_products(self, limit: int = 10) -> List[Dict[str, Any]]:
        return []

    async def get_product(self, product_id: int | str) -> Optional[Dict[str, Any]]:
        return None

    # placeholder writers (not yet used here)
    async def create_product(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("create_product not implemented yet")

    async def update_product(self, product_id: int | str, payload: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("update_product not implemented yet")

    async def publish_product(self, product_id: int | str) -> Dict[str, Any]:
        raise NotImplementedError("publish_product not implemented yet")


__all__ = ["Shopify", "get_order_by_name"]
