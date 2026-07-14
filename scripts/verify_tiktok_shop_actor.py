#!/usr/bin/env python3
"""ONE capped live run of the TikTok Shop product actor → dump + parse check.

Phase-1 verification harness (run when Apify credits exist — the account is
over its $45 cap until 2026-08-07). Spends roughly $0.03 at the default cap.

    uv run python scripts/verify_tiktok_shop_actor.py [--items 20] [--keyword "water bottle"]

What it does:
  1. Checks the account is actually under its usage limit (refuses otherwise).
  2. Runs APIFY_TIKTOK_SHOP_ACTOR (default trakk/tiktok-shop-search-scraper)
     capped at --items.
  3. Dumps the RAW items to data/tiktok_shop_actor_sample.json — eyeball this.
  4. Runs the canonical parser on them and prints the verdict + real cost.

If parse status != ok: the alias tables in
ospra_os/product_research/connectors/apify/tiktok_shop_products.py need
updating to the REAL field names in the dump. Flip LIVE_VERIFIED=True there
only after this harness reports ok and the dump looks sane.
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--items", type=int, default=20, help="max items (credit cap)")
    parser.add_argument("--keyword", default="kitchen gadgets")
    args = parser.parse_args()

    import httpx

    token = os.getenv("APIFY_API_TOKEN")
    if not token:
        print("[ERROR] APIFY_API_TOKEN not set")
        return 1

    limits = httpx.get(
        "https://api.apify.com/v2/users/me/limits", params={"token": token}, timeout=30
    ).json().get("data", {})
    used = (limits.get("current") or {}).get("monthlyUsageUsd", 0)
    cap = (limits.get("limits") or {}).get("maxMonthlyUsageUsd", 0)
    print(f"[APIFY] usage ${used:.2f} / ${cap:.2f}")
    if used >= cap:
        print("[BLOCKED] Account at/over its monthly cap — the run would fail. "
              "Raise the limit in the Apify console or wait for the cycle reset.")
        return 2

    from ospra_os.product_research.connectors.apify.tiktok_shop_products import (
        TikTokShopProductsScraper, parse_items,
    )

    scraper = TikTokShopProductsScraper()
    print(f"[RUN] actor={scraper.actor_id} keyword={args.keyword!r} cap={args.items}")
    print(f"[RUN] input={json.dumps(scraper.build_input([args.keyword], args.items))}")

    raw = await scraper.client.run_actor(
        actor_id=scraper.actor_id,
        run_input=scraper.build_input([args.keyword], args.items),
        timeout_secs=240,
        max_items=args.items,
    )

    out = Path(__file__).resolve().parents[1] / "data" / "tiktok_shop_actor_sample.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(raw, indent=2, default=str))
    print(f"[DUMP] {len(raw)} raw items → {out}")

    parsed = parse_items(raw)
    print(f"[PARSE] status={parsed['status']} valid={len(parsed['products'])} "
          f"invalid={parsed['invalid_count']}")
    if parsed["status"] != "ok":
        print(f"[ACTION] first-item keys: {parsed.get('sample_keys')}")
        print("[ACTION] update the alias tables in tiktok_shop_products.py to these names.")
        return 3

    for p in parsed["products"][:5]:
        print(f"   id={p.tiktok_product_id} sold={p.sold_count} ${p.price} "
              f"rating={p.rating} reviews={p.review_count} | {p.title[:60]}")
    print("\n[NEXT] If the dump looks sane, set LIVE_VERIFIED=True in "
          "tiktok_shop_products.py and record the actor's REAL charged cost "
          "(Apify console → last run) in the Phase-1 report.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
