# app/shopify_client.py
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

try:
    import requests
except Exception:  # requests not strictly required (we can still use local orders.json)
    requests = None  # type: ignore

from app.settings import get_settings
from urllib import request as urlreq, parse as urlparse


def _s(v: Any) -> str:
    """Return a safe string for env-derived settings (handles int/None)."""
    try:
        return v if isinstance(v, str) else "" if v is None else str(v)
    except Exception:
        return ""


# -----------------------------
# Helpers: Settings & Sessions
# -----------------------------
def _get_shopify_env() -> Tuple[str, str, str]:
    print("\n--- DEBUG: ENTERING _get_shopify_env ---")
    s = get_settings()
    raw_token = s.SHOPIFY_API_TOKEN
    print(f"[DEBUG] Raw SHOPIFY_API_TOKEN: '{raw_token}' (Type: {type(raw_token)})")
    token = str(raw_token or "").strip()
    raw_store = s.SHOPIFY_STORE
    print(f"[DEBUG] Raw SHOPIFY_STORE: '{raw_store}' (Type: {type(raw_store)})")
    store = str(raw_store or "").strip()
    mode = str(s.SHOPIFY_MODE or "safe").strip().lower()
    if not token or not store:
        raise ValueError("Shopify token/store missing—check .env as str")
    print("--- DEBUG: SUCCESSFULLY PROCESSED SETTINGS ---\n")
    return token, store, mode


def _shopify_request(
    method: str,
    path: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Minimal REST wrapper for Shopify Admin API.
    """
    token, store, _mode = _get_shopify_env()
    if not token or not store or requests is None:
        raise ValueError("Shopify REST unavailable (missing token/store/requests)")

    s = get_settings()
    api_version = _s(getattr(s, "SHOPIFY_API_VERSION", "2025-10")).strip("/")
    url = f"https://{store}/admin/api/{api_version}{path}"
    headers = {
        "X-Shopify-Access-Token": token,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    try:
        resp = requests.request(
            method.upper(), url, headers=headers, params=params, json=json_body, timeout=15
        )
        print(f"Shopify status: {resp.status_code} (URL: {url})")
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError as e:  # type: ignore[attr-defined]
        status = e.response.status_code if e.response else "unknown"
        msg = e.response.text.strip() if e.response and e.response.text else "No response body"
        print(f"Shopify API error: {status} - {msg} (URL: {url})")
        if status == 404:
            print("Hint: Store domain invalid or API version deprecated - verify settings and domain linkage.")
        elif status == 401:
            print("Hint: Token invalid or missing read_shop scope - regenerate with correct permissions.")
        elif status == 429:
            print("Hint: Rate limited - add time.sleep(1) before calls.")
        raise
    except requests.exceptions.RequestException as e:  # type: ignore[attr-defined]
        print(f"Network error: {type(e).__name__} - {str(e)}")
        raise
    except Exception as e:
        print(f"Unexpected error during Shopify GET: {type(e).__name__} - {str(e)}")
        raise


def _shopify_get(path: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        return _shopify_request("GET", path, params=params)
    except Exception:
        return None


def _shopify_post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return _shopify_request("POST", path, json_body=payload)


def _shopify_put(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return _shopify_request("PUT", path, json_body=payload)


# -----------------------------
# Parsing: Order IDs in emails
# -----------------------------
def parse_order_id(subject: str, body: str) -> Optional[str]:
    """
    Look for:
      - OU-style ids (OU12345)
      - 'order #12345'
      - '#12345'
      - bare 5+ digits
    Return a cleaned string (e.g., 'OU12345' or '12345') or None.
    """
    text = f"{subject}\n{body}"

    m = re.search(r"\bOU\d{5,}\b", text, flags=re.I)
    if m:
        return m.group(0).upper()

    m = re.search(r"\border\s*#\s*(\d{5,})\b", text, flags=re.I)
    if m:
        return m.group(1)

    m = re.search(r"#\s*(\d{5,})\b", text, flags=re.I)
    if m:
        return m.group(1)

    m = re.search(r"\b(\d{5,})\b", text)
    if m:
        return m.group(1)

    return None


# -----------------------------
# Lookup: Local file first, then Shopify
# -----------------------------
def _normalize_shopify_order(o: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize raw Shopify order JSON into our compact shape.
    """
    order_id = o.get("name") or str(o.get("id") or "")
    status = o.get("fulfillment_status") or o.get("financial_status") or o.get("cancel_reason") or "Unknown"

    carrier = tracking = None
    last_update = o.get("updated_at") or o.get("processed_at")

    # Try pull tracking from first fulfillment
    try:
        fulfills = o.get("fulfillments") or []
        if fulfills:
            f0 = fulfills[0]
            carrier = f0.get("tracking_company") or (f0.get("tracking_numbers") or [None])[0]
            tracking = (
                f0.get("tracking_number")
                or (f0.get("tracking_numbers") or [None])[0]
                or (f0.get("tracking_urls") or [None])[0]
            )
            last_update = f0.get("updated_at") or last_update
    except Exception:
        pass

    return {
        "order_id": order_id,
        "status": status,
        "carrier": carrier,
        "tracking": tracking,
        "last_update": last_update,
    }


def _lookup_local(order_id: str) -> Optional[Dict[str, Any]]:
    """
    Reads data/orders.json and returns the first matching order dict (normalized) or None.
    Schema expected:
      [
        {"order_id":"OU10001","status":"Shipped","carrier":"UPS","tracking":"1Z...","last_update":"..."},
        ...
      ]
    """
    path = Path("data/orders.json")
    if not path.exists():
        return None
    try:
        orders = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

    for o in orders or []:
        if (o.get("order_id") or "").upper() == (order_id or "").upper():
            # If it's already normalized, return as-is
            if {"order_id", "status", "carrier", "tracking", "last_update"} <= set(o.keys()):
                return o
            # Otherwise map best-effort
            return {
                "order_id": o.get("order_id") or order_id,
                "status": o.get("status") or o.get("fulfillment_status") or "Unknown",
                "carrier": o.get("carrier"),
                "tracking": o.get("tracking"),
                "last_update": o.get("last_update") or o.get("updated_at"),
            }
    return None


def lookup_order(order_id: str) -> Optional[Dict[str, Any]]:
    """
    Try local file first; if not found, try Shopify Admin REST.
    Returns normalized dict or None.
    """
    if not order_id:
        return None

    # 1) Local cache/file
    local = _lookup_local(order_id)
    if local:
        return local

    # 2) Shopify Admin REST (if configured)
    token, store, mode = _get_shopify_env()
    if not token or not store:
        return None

    # For Shopify "name" is typically like "#1001". If user gave "1001" try both.
    candidates = []
    if order_id.startswith("#"):
        candidates.append(order_id)
        candidates.append(order_id.lstrip("#"))
    else:
        candidates.append(order_id)
        candidates.append(f"#{order_id}")

    # First, try direct "name" filter (works for Admin REST)
    for cand in candidates:
        data = _shopify_get("/orders.json", {"status": "any", "name": cand})
        if data and (data.get("orders") or []):
            return _normalize_shopify_order(data["orders"][0])

    # Fallback: search by order number via query (if supported)
    # Not all plans/stores support Admin REST "query" param; safe to try.
    for cand in candidates:
        data = _shopify_get("/orders.json", {"status": "any", "query": cand})
        if data and (data.get("orders") or []):
            return _normalize_shopify_order(data["orders"][0])

    return None


async def get_order_by_name(order_name: str) -> dict | None:
    s = get_settings()
    store = getattr(s, "SHOPIFY_STORE", "").replace("https://", "").replace("http://", "")
    token = getattr(s, "SHOPIFY_API_TOKEN", "")
    if not store or not token:
        return None
    candidates = [order_name, order_name.lstrip("#")] if order_name.startswith("#") else [order_name, f"#{order_name}"]
    for candidate in candidates:
        try:
            qs = urlparse.urlencode({"name": candidate})
            url = f"https://{store}/admin/api/2024-10/orders.json?{qs}"
            req = urlreq.Request(url, headers={"X-Shopify-Access-Token": token, "Accept": "application/json"})
            with urlreq.urlopen(req, timeout=15) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            orders = payload.get("orders") or []
            if orders:
                return orders[0]
        except Exception:
            continue
    return None


async def cancel_unfulfilled_order(order: dict) -> dict:
    s = get_settings()
    store = getattr(s, "SHOPIFY_STORE", "").replace("https://", "").replace("http://", "")
    token = getattr(s, "SHOPIFY_API_TOKEN", "")
    order_id = order.get("id")
    if not (store and token and order_id):
        return {"ok": False, "error": "missing_shopify_config_or_id"}
    url = f"https://{store}/admin/api/2024-10/orders/{order_id}/cancel.json"
    req = urlreq.Request(url, method="POST", headers={"X-Shopify-Access-Token": token, "Accept": "application/json"})
    with urlreq.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return {"ok": True, "data": data}


async def update_order_address(order: dict, new_addr: dict) -> dict:
    s = get_settings()
    store = getattr(s, "SHOPIFY_STORE", "").replace("https://", "").replace("http://", "")
    token = getattr(s, "SHOPIFY_API_TOKEN", "")
    order_id = order.get("id")
    if not (store and token and order_id):
        return {"ok": False, "error": "missing_shopify_config_or_id"}
    url = f"https://{store}/admin/api/2024-10/orders/{order_id}.json"
    payload = json.dumps({"order": {"id": order_id, "shipping_address": new_addr}}).encode("utf-8")
    req = urlreq.Request(url, data=payload, method="PUT", headers={
        "X-Shopify-Access-Token": token,
        "Content-Type": "application/json",
        "Accept": "application/json"
    })
    with urlreq.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return {"ok": True, "data": data}


def get_shop_timezone() -> str:
    """Fetch the store's timezone from Shopify settings using GraphQL with a REST fallback."""
    query = """
    query {
        shop {
            ianaTimezone
        }
    }
    """
    data = _shopify_graphql(query)
    timezone = data.get("shop", {}).get("ianaTimezone") if data else None
    if timezone:
        return timezone

    # Fallback to REST lookup if GraphQL is unavailable.
    rest = _shopify_get("/shop.json", {})
    if rest:
        return rest.get("shop", {}).get("iana_timezone", "America/Chicago")

    print("[warn] Could not fetch Shopify timezone via REST fallback.")
    return "America/Chicago"


def validate_shopify_config() -> str:
    """
    Call during startup (main module or FastAPI lifespan) to ensure Shopify credentials (REST + GraphQL) are valid.
    """
    rest_result = _shopify_get("/shop.json", {})
    if not rest_result:
        raise ValueError("Shopify REST config invalid - check store/token/version in .env and logs.")

    gql_query = """
    query {
        shop {
            ianaTimezone
        }
    }
    """
    gql_result = _shopify_graphql(gql_query)
    if not gql_result or not gql_result.get("shop"):
        raise ValueError("Shopify GraphQL unreachable - ensure token scopes allow shop access.")

    timezone = (
        gql_result.get("shop", {}).get("ianaTimezone")
        or rest_result.get("shop", {}).get("iana_timezone")
        or "Unknown"
    )
    print("Shopify connected: Timezone =", timezone)
    return timezone


def _shopify_graphql(
    query: str,
    variables: Optional[Dict[str, Any]] = None,
    *,
    access_token: Optional[str] = None,
    store_domain: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Minimal Shopify Admin GraphQL client using the same credentials as REST.
    """
    s = get_settings()
    token, store, _mode = _get_shopify_env()
    token_to_use = access_token or token
    store_to_use = (store_domain or store or "").strip()
    if not token_to_use or not store_to_use or requests is None:
        return None

    api_version = _s(getattr(s, "SHOPIFY_API_VERSION", "2025-10")).strip("/")
    url = f"https://{store_to_use}/admin/api/{api_version}/graphql.json"
    headers = {
        "X-Shopify-Access-Token": token_to_use,
        "Content-Type": "application/json",
    }
    payload = {"query": query, "variables": variables or {}}
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if "errors" in data:
            print(f"GraphQL errors: {data['errors']}")
            return None
        return data.get("data")
    except requests.exceptions.RequestException as e:  # type: ignore[attr-defined]
        print(f"GraphQL network error: {type(e).__name__} - {str(e)}")
        return None
    except Exception as e:
        print(f"GraphQL error: {type(e).__name__} - {str(e)}")
        return None


def get_shop_timezone_graphql() -> str:
    """
    Fetch the store timezone via GraphQL (more efficient than REST for future queries).
    """
    query = """
    query {
        shop {
            timezoneAbbreviation
            ianaTimezone
        }
    }
    """
    data = _shopify_graphql(query)
    return data.get("shop", {}).get("ianaTimezone", "America/Chicago") if data else "America/Chicago"
