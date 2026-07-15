#!/usr/bin/env python3
"""ONE capped live run of the TikTok comments actor → dump + parse check.

Moat Phase-2 verification harness (run when Apify credits exist — the account
is over its $45 cap until 2026-08-07). ~$0.02 at the default cap.

    uv run python scripts/verify_tiktok_comments_actor.py --url "https://www.tiktok.com/@user/video/123" [--n 20]

  1. Refuses to run if the account is at/over its usage limit.
  2. Runs APIFY_TIKTOK_COMMENTS_ACTOR (default clockworks) for the video URL,
     capped at --n comments.
  3. Dumps raw items to data/tiktok_comments_actor_sample.json — eyeball this.
  4. Runs the canonical parser and prints the verdict + a signal preview.

If parse status != ok, the alias tables in
ospra_os/product_research/connectors/apify/tiktok_comments.py need updating to
the REAL field names in the dump. Flip LIVE_VERIFIED=True there only after
this reports ok AND the follower/account-age finding is re-confirmed against
the real output.
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
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True, help="a TikTok VIDEO url")
    ap.add_argument("--n", type=int, default=20, help="max comments (credit cap)")
    args = ap.parse_args()

    import httpx
    token = os.getenv("APIFY_API_TOKEN")
    if not token:
        print("[ERROR] APIFY_API_TOKEN not set")
        return 1

    lim = httpx.get("https://api.apify.com/v2/users/me/limits",
                    params={"token": token}, timeout=30).json().get("data", {})
    used = (lim.get("current") or {}).get("monthlyUsageUsd", 0)
    cap = (lim.get("limits") or {}).get("maxMonthlyUsageUsd", 0)
    print(f"[APIFY] usage ${used:.2f} / ${cap:.2f}")
    if used >= cap:
        print("[BLOCKED] Account at/over its monthly cap — the run would fail.")
        return 2

    from ospra_os.product_research.connectors.apify.tiktok_comments import (
        TikTokCommentsScraper, parse_comments,
    )
    scraper = TikTokCommentsScraper()
    scraper.comments_per_post = args.n
    print(f"[RUN] actor={scraper.actor_id} url={args.url} cap={args.n}")

    raw = await scraper.client.run_actor(
        actor_id=scraper.actor_id,
        run_input=scraper.build_input([args.url]),
        timeout_secs=240,
        max_items=args.n,
    )
    out = Path(__file__).resolve().parents[1] / "data" / "tiktok_comments_actor_sample.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(raw, indent=2, default=str))
    print(f"[DUMP] {len(raw)} raw items → {out}")

    parsed = parse_comments(raw)
    print(f"[PARSE] status={parsed['status']} valid={len(parsed['comments'])} "
          f"invalid={parsed['invalid_count']}")
    if parsed["status"] != "ok":
        print(f"[ACTION] first-item keys: {parsed.get('sample_keys')}")
        return 3

    # Confirm the follower/account-age finding against real output.
    if raw:
        keys = sorted(raw[0].keys())
        print(f"[FIELDS] real first-item keys: {keys}")
        has_followers = any("follow" in k.lower() for k in keys)
        has_age = any(("age" in k.lower() or "regtime" in k.lower() or "createaccount" in k.lower()) for k in keys)
        print(f"[FINDING] follower field present: {has_followers} | account-age field present: {has_age}")
    for c in parsed["comments"][:5]:
        print(f"   cid={c.comment_id} digg={c.digg_count} @{c.author_unique_id} "
              f"default_handle={c.author_is_default_handle} | {c.text[:50]!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
