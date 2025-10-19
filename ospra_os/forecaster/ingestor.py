from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib import request as urlreq
from urllib.parse import urlencode


def _shopify_headers(token: str) -> Dict[str, str]:
    return {
        "X-Shopify-Access-Token": token,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _json_get(url: str, headers: Dict[str, str], timeout: int = 20) -> Dict[str, Any]:
    req = urlreq.Request(url, headers=headers)
    with urlreq.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="ignore"))


def iso_day(dt: datetime) -> datetime:
    """Normalize to midnight (date bucket)."""
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def fetch_orders_since(
    *, store_domain: str, token: str, since: datetime, status: str = "any", limit: int = 250
) -> Iterable[Dict[str, Any]]:
    """
    Generator over orders since `since` (created_at_min), using REST.
    Note: This uses basic page-based iteration (no link headers) for simplicity.
    """
    base = f"https://{store_domain}/admin/api/2024-10/orders.json"
    page_info: Optional[str] = None
    params = {
        "status": status,
        "limit": str(limit),
        "created_at_min": since.isoformat(timespec="seconds"),
        "fields": "id,name,created_at,line_items,financial_status,fulfillment_status,cancelled_at",
        "order": "created_at asc",
    }
    headers = _shopify_headers(token)

    while True:
        url = base + "?" + urlencode(params)
        data = _json_get(url, headers=headers)
        orders = data.get("orders", []) or []
        if not orders:
            break
        for o in orders:
            yield o
        # naive pagination: move min forward by last order time
        last = orders[-1]
        last_created = last.get("created_at")
        if not last_created:
            break
        params["created_at_min"] = last_created


def build_daily_series_by_sku(
    orders: Iterable[Dict[str, Any]], *, ignore_canceled: bool = True
) -> Dict[str, List[Tuple[datetime, float]]]:
    """
    Return dict[sku] -> list[(date, units)] aggregated by day.
    SKUs missing in the line item default to the item's title as a fallback key.
    """
    buckets: Dict[str, Dict[datetime, float]] = {}
    for o in orders:
        if ignore_canceled and o.get("cancelled_at"):
            continue
        created_at = o.get("created_at")
        if not created_at:
            continue
        try:
            ts = datetime.fromisoformat(created_at.replace("Z", "+00:00")).astimezone().replace(tzinfo=None)
        except Exception:
            continue
        day = iso_day(ts)
        for li in o.get("line_items", []) or []:
            sku = (li.get("sku") or "").strip() or (li.get("title") or "UNKNOWN")
            qty = float(li.get("quantity") or 0)
            if qty <= 0:
                continue
            day_map = buckets.setdefault(sku, {})
            day_map[day] = day_map.get(day, 0.0) + qty

    # convert inner dicts to sorted lists
    series_by_sku: Dict[str, List[Tuple[datetime, float]]] = {}
    for sku, day_map in buckets.items():
        pairs = sorted(day_map.items(), key=lambda x: x[0])
        series_by_sku[sku] = pairs
    return series_by_sku


def fill_gaps(series: List[Tuple[datetime, float]], horizon_days: int = 0) -> List[Tuple[datetime, float]]:
    """
    Ensure continuous daily series by filling missing dates with zero.
    Optionally extend with zeroes for horizon alignment (not required for fit).
    """
    if not series:
        return series
    start = series[0][0]
    end = series[-1][0]
    all_days: Dict[datetime, float] = {ds: y for ds, y in series}
    out: List[Tuple[datetime, float]] = []
    d = start
    while d <= end:
        out.append((d, all_days.get(d, 0.0)))
        d += timedelta(days=1)
    # optionally extend
    for _ in range(horizon_days):
        end += timedelta(days=1)
        out.append((end, 0.0))
    return out
