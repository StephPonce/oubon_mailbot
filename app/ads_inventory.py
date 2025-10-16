"""
Automation helpers for inventory monitoring and ads creation.

Dependencies:
    pip install facebook-business google-ads openai
"""
from datetime import datetime
from typing import Dict, List, Optional

try:
    from facebook_business.api import FacebookAdsApi
except ImportError:  # pragma: no cover - optional dependency
    FacebookAdsApi = None  # type: ignore

try:
    from google.ads.googleads.client import GoogleAdsClient
except ImportError:  # pragma: no cover - optional dependency
    GoogleAdsClient = None  # type: ignore

from app.shopify_client import _shopify_graphql
from app.settings import get_settings


def fetch_recent_sales(hours: int = 24) -> List[Dict[str, str]]:
    """
    Pull product sales over the given time window using Shopify GraphQL.
    """
    cutoff_iso = datetime.utcnow().isoformat()
    query = """
    query($query: String!) {
      orders(first: 50, query: $query) {
        edges {
          node {
            name
            lineItems(first: 5) {
              edges {
                node {
                  product {
                    id
                    title
                  }
                  quantity
                }
              }
            }
          }
        }
      }
    }
    """
    gql_query = f"created_at:>={cutoff_iso}"
    data = _shopify_graphql(query, {"query": gql_query})
    orders = data.get("orders", {}).get("edges", []) if data else []
    results: List[Dict[str, str]] = []
    for edge in orders:
        node = edge.get("node", {})
        for item_edge in node.get("lineItems", {}).get("edges", []):
            item = item_edge.get("node", {})
            product = item.get("product") or {}
            results.append(
                {
                    "product_id": product.get("id"),
                    "title": product.get("title"),
                    "quantity": item.get("quantity"),
                    "order": node.get("name"),
                }
            )
    return results


def mark_hot_products(sales: List[Dict[str, str]], threshold: int = 5) -> List[str]:
    """
    Return product IDs that meet the sales threshold.
    """
    counts: Dict[str, int] = {}
    for sale in sales:
        pid = sale.get("product_id")
        qty = int(sale.get("quantity") or 0)
        if not pid:
            continue
        counts[pid] = counts.get(pid, 0) + qty
    return [pid for pid, total in counts.items() if total >= threshold]


def create_facebook_campaign(hot_products: List[str], ad_copy: str) -> None:
    """
    Placeholder for automated Facebook Ads campaign creation.
    """
    if FacebookAdsApi is None:
        raise RuntimeError("facebook-business SDK not installed. Install before running.")
    settings = get_settings()
    if not settings.FB_ADS_DAILY_LIMIT:
        print("FB_ADS_DAILY_LIMIT is 0; skipping campaign automation.")
        return
    print(f"[facebook] Would launch campaign for {len(hot_products)} products with budget {settings.FB_ADS_DAILY_LIMIT}.")


def create_google_ads_campaign(hot_products: List[str], ad_copy: str) -> None:
    """
    Placeholder for automated Google Ads campaign creation.
    """
    if GoogleAdsClient is None:
        raise RuntimeError("google-ads SDK not installed. Install before running.")
    settings = get_settings()
    if not settings.GOOGLE_ADS_DAILY_LIMIT:
        print("GOOGLE_ADS_DAILY_LIMIT is 0; skipping campaign automation.")
        return
    print(f"[google] Would launch campaign for {len(hot_products)} products with budget {settings.GOOGLE_ADS_DAILY_LIMIT}.")


def auto_ad(product: str, platform: str = "meta") -> str:
    """
    Stubbed helper for creating ads across platforms (Meta/Google/TikTok).
    Requires proper API credentials configured in Settings for real usage.
    """
    settings = get_settings()
    if platform == "meta":
        if not settings.FB_ADS_DAILY_LIMIT:
            return "Meta ads disabled—set FB_ADS_DAILY_LIMIT in .env to enable."
        return f"Ad created for {product} on Meta—preempt approve in dashboard"
    if platform == "google":
        if not settings.GOOGLE_ADS_DAILY_LIMIT:
            return "Google ads disabled—set GOOGLE_ADS_DAILY_LIMIT in .env to enable."
        return f"Ad created for {product} on Google Ads—review in dashboard"
    if platform == "tiktok":
        return "TikTok ad stub—add credentials in .env and integrate API."
    return "Ad stub—add keys in .env"
