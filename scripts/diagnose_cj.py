"""
CJ Dropshipping Live Diagnostic
================================
Fix #7 / Step D: verify whether CJ category 1489 (smart_home) actually has
products, or whether our category mapping is broken.

Usage (from repo root):
    python scripts/diagnose_cj.py

Output:
    - Confirms CJ_ACCESS_TOKEN is loaded
    - Lists top-level CJ categories (to verify 1489 exists)
    - Fetches products from category 1489 directly
    - Fetches products by keyword "smart plug" for comparison
    - Prints clear pass/fail for each test
"""

import asyncio
import os
import sys
from pathlib import Path

# Make ospra_os importable when running from repo root
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO_ROOT / ".env")

from ospra_os.integrations.cj_dropshipping.client import CJDropshippingClient  # noqa: E402


DIVIDER = "=" * 70


def section(title: str) -> None:
    print(f"\n{DIVIDER}\n {title}\n{DIVIDER}")


async def test_token(client: CJDropshippingClient) -> bool:
    section("TEST 1 — CJ_ACCESS_TOKEN present")
    if client.is_available():
        token_preview = (client.access_token or "")[:10]
        print(f"  ✅ Token loaded: {token_preview}... (len={len(client.access_token or '')})")
        return True
    print("  ❌ CJ_ACCESS_TOKEN not configured — set it in .env before continuing")
    return False


async def test_category_list(client: CJDropshippingClient) -> bool:
    """Hit /product/getCategory and verify category 1489 exists."""
    section("TEST 2 — Category list (verify 1489 exists)")
    result = await client._request("product/getCategory", {})
    if not result:
        print("  ❌ getCategory returned nothing. Token may be invalid or endpoint changed.")
        return False

    # CJ's category tree is nested — flatten to id set
    found_ids = set()

    def walk(nodes):
        for n in nodes or []:
            if isinstance(n, dict):
                cid = str(n.get("categoryId", ""))
                if cid:
                    found_ids.add(cid)
                for k in ("categoryChildList", "children", "sub", "subCategory"):
                    if k in n:
                        walk(n[k])

    if isinstance(result, list):
        walk(result)
    elif isinstance(result, dict):
        walk(result.get("list") or result.get("data") or [])

    print(f"  Flat category ids found: {len(found_ids)}")
    target = "1489"
    if target in found_ids:
        print(f"  ✅ Category {target} exists in CJ catalog")
        return True
    print(f"  ⚠️ Category {target} NOT in the flat list — may be deprecated or under a parent we didn't walk")
    print(f"     Sample ids: {sorted(list(found_ids))[:20]}")
    return False


async def test_products_by_category(client: CJDropshippingClient, category_id: str) -> int:
    section(f"TEST 3 — Products by category {category_id} (smart_home)")
    products = await client.search_products(keyword="", category_id=category_id, page_size=10)
    print(f"  Products returned: {len(products)}")
    for i, p in enumerate(products[:3], 1):
        title = (p.get("title") or p.get("name") or "?")[:60]
        price = p.get("price") or p.get("sellPrice") or "?"
        print(f"    {i}. {title}  (price={price})")
    if not products:
        print("  ❌ Category 1489 returned ZERO products — root cause of CJ:0 in discovery")
    else:
        print(f"  ✅ Category {category_id} works — discovery should receive these")
    return len(products)


async def test_products_by_keyword(client: CJDropshippingClient) -> int:
    section("TEST 4 — Products by keyword 'smart plug' (control test)")
    products = await client.search_products(keyword="smart plug", page_size=10)
    print(f"  Products returned: {len(products)}")
    for i, p in enumerate(products[:3], 1):
        title = (p.get("title") or p.get("name") or "?")[:60]
        price = p.get("price") or p.get("sellPrice") or "?"
        print(f"    {i}. {title}  (price={price})")
    if not products:
        print("  ❌ Keyword search also returned ZERO — account or API issue, not category issue")
    else:
        print("  ✅ Keyword search works — category search is specifically broken")
    return len(products)


async def main():
    client = CJDropshippingClient()

    if not await test_token(client):
        return 1

    await test_category_list(client)
    cat_count = await test_products_by_category(client, "1489")
    kw_count = await test_products_by_keyword(client)

    section("VERDICT")
    if cat_count > 0:
        print("  ✅ CJ category search works. Discovery should show CJ products.")
        print("     If you're still seeing CJ: 0, the issue is elsewhere (cross-ref filter, scoring).")
    elif kw_count > 0:
        print("  ⚠️ CJ keyword search works but category 1489 is empty.")
        print("     Options: (a) use a different category id, (b) fall back to keyword strategy.")
    else:
        print("  ❌ Both category and keyword search returned zero.")
        print("     Likely: token lacks product-access scope, or CJ account is limited.")
        print("     Action: log into https://developers.cjdropshipping.com/ and verify account + scope.")

    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
