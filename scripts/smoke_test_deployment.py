"""
Deployment pipeline smoke test (Task #24).

Exercises the full deploy pipeline WITHOUT hitting Shopify, so we can
verify the source-agnostic payload contract end-to-end without a real
staging store credential.

Modes
-----
--validate-only
    Run CJ / AliExpress / minimal fixtures through the Pydantic
    `SourceProduct` schema from deployment_routes.py. This is the
    cheapest check (no deployer instantiation, no AI calls) and proves
    that a frontend-shaped payload will make it through FastAPI
    validation.

--dry-run (default)
    Instantiate ProductDeployer, stub out content_generator /
    image_processor / shopify (so no network calls or API keys needed),
    and run deploy_product() for each fixture. Capture the product_dict
    that would have been POSTed to ShopifyAdapter.deploy_product() and
    assert the invariants:
      - title  : non-empty string
      - price  : positive float
      - sku    : starts with the right source prefix (CJ- / AE- / PROD-)
      - images : non-empty list
      - description (body_html) : non-empty string
      - tags   : list
      - Shopify validate_product_data() accepts the payload

--live-cj
    Gated by env (SHOPIFY_STORE + SHOPIFY_API_TOKEN) AND the explicit
    `--confirm` flag. Runs a real deployment of ONE CJ fixture into the
    configured staging store. Refuses to run if either is missing.

Usage
-----
    python scripts/smoke_test_deployment.py --validate-only
    python scripts/smoke_test_deployment.py --dry-run
    python scripts/smoke_test_deployment.py --live-cj --confirm

Exit code is 0 on all-pass, 1 on any failure.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Make the repo importable when run as a script.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# A realistic CJ-shaped product (what CJConnector would return after
# normalization). Notably: no `category`, uses `all_images` not `images`,
# source='cj_dropshipping', plus CJ-specific fields that must survive
# Pydantic extra='allow'.
CJ_FIXTURE: Dict[str, Any] = {
    "title": "Wireless LED Light Strip 5m RGB Bluetooth App Control",
    "description": "Smart LED strip with app + voice control. Millions of colors.",
    "features": ["App controlled", "Voice assistant compatible", "16M colors", "Music sync"],
    "price": 8.45,
    "all_images": [
        "https://cc-west-usa.oss-accelerate.aliyuncs.com/cj-demo-img-1.jpg",
        "https://cc-west-usa.oss-accelerate.aliyuncs.com/cj-demo-img-2.jpg",
    ],
    "source": "cj_dropshipping",
    # Extra CJ-specific fields — must flow through extra='allow'.
    "cj_pid": "CJNSCJAA12345",
    "warehouse": "CN",
    "us_warehouse": True,
    "supplier_cost": 8.45,
}

# AliExpress-shaped product — images key, source='aliexpress', has category.
AE_FIXTURE: Dict[str, Any] = {
    "title": "Portable Car Vacuum Cleaner Wireless USB Rechargeable",
    "description": "Compact vacuum for car interior detailing. USB-C charging.",
    "features": ["Wireless", "USB-C charge", "8000Pa suction", "Lightweight"],
    "category": "car_accessories",
    "price": 12.99,
    "images": [
        "https://ae01.alicdn.com/kf/ae-demo-img-1.jpg",
        "https://ae01.alicdn.com/kf/ae-demo-img-2.jpg",
    ],
    "source": "aliexpress",
}

# Minimal / "unknown source" payload — only required fields. Proves the
# deployer falls back to PROD- SKU prefix and single image_url.
MINIMAL_FIXTURE: Dict[str, Any] = {
    "title": "Generic Kitchen Gadget",
    "price": 5.00,
    "image_url": "https://example.com/generic-kitchen.jpg",
    # no source, no images list, no all_images
}


FIXTURES: List[Tuple[str, Dict[str, Any], str]] = [
    # (name, payload, expected SKU prefix)
    ("cj", CJ_FIXTURE, "CJ-"),
    ("aliexpress", AE_FIXTURE, "AE-"),
    ("minimal_unknown_source", MINIMAL_FIXTURE, "PROD-"),
]


# ---------------------------------------------------------------------------
# Reporter
# ---------------------------------------------------------------------------

class Reporter:
    def __init__(self) -> None:
        self.passes = 0
        self.fails = 0
        self.failures: List[str] = []

    def ok(self, label: str) -> None:
        self.passes += 1
        print(f"  [PASS] {label}")

    def fail(self, label: str, detail: str = "") -> None:
        self.fails += 1
        msg = f"[FAIL] {label}" + (f" — {detail}" if detail else "")
        self.failures.append(msg)
        print(f"  {msg}")

    def assert_true(self, cond: bool, label: str, detail: str = "") -> None:
        if cond:
            self.ok(label)
        else:
            self.fail(label, detail)

    def section(self, name: str) -> None:
        print(f"\n=== {name} ===")

    def summary(self) -> int:
        print("\n" + "=" * 60)
        print(f"PASSED: {self.passes}")
        print(f"FAILED: {self.fails}")
        if self.failures:
            print("\nFailures:")
            for f in self.failures:
                print(f"  - {f}")
        print("=" * 60)
        return 0 if self.fails == 0 else 1


# ---------------------------------------------------------------------------
# Mode: --validate-only
# ---------------------------------------------------------------------------

def run_validate_only(reporter: Reporter) -> None:
    reporter.section("VALIDATE-ONLY: Pydantic SourceProduct schema")

    try:
        from ospra_os.api.deployment_routes import (
            SourceProduct,
            PrepareProductRequest,
            DeployProductRequest,
        )
    except Exception as e:
        reporter.fail("import SourceProduct", detail=f"{type(e).__name__}: {e}")
        return

    for name, payload, _ in FIXTURES:
        try:
            sp = SourceProduct(**payload)
            reporter.ok(f"{name}: SourceProduct accepts payload")
            # Extra fields must pass through (extra='allow').
            if name == "cj":
                d = sp.model_dump()
                has_cj_pid = d.get("cj_pid") == "CJNSCJAA12345"
                reporter.assert_true(
                    has_cj_pid,
                    "cj: cj_pid survives extra='allow'",
                    detail=f"got model_dump={list(d.keys())}",
                )
        except Exception as e:
            reporter.fail(f"{name}: SourceProduct", detail=f"{type(e).__name__}: {e}")

        # Also test wrapping in the full request models used by the routes.
        try:
            PrepareProductRequest(product=payload, niche="smart_home")
            reporter.ok(f"{name}: wraps in PrepareProductRequest")
        except Exception as e:
            reporter.fail(
                f"{name}: PrepareProductRequest",
                detail=f"{type(e).__name__}: {e}",
            )

        try:
            DeployProductRequest(product=payload, niche="smart_home", options={})
            reporter.ok(f"{name}: wraps in DeployProductRequest")
        except Exception as e:
            reporter.fail(
                f"{name}: DeployProductRequest",
                detail=f"{type(e).__name__}: {e}",
            )

    # Negative: missing price must be rejected.
    try:
        SourceProduct(title="No price")  # type: ignore[call-arg]
        reporter.fail("negative: missing price rejected",
                      detail="Pydantic accepted a product with no price")
    except Exception:
        reporter.ok("negative: missing price rejected")

    # Negative: price <= 0 must be rejected.
    try:
        SourceProduct(title="Zero price", price=0.0)
        reporter.fail("negative: price=0 rejected",
                      detail="Pydantic accepted price=0")
    except Exception:
        reporter.ok("negative: price=0 rejected")


# ---------------------------------------------------------------------------
# Mode: --dry-run
# ---------------------------------------------------------------------------

class _CapturingShopify:
    """
    Stand-in for ShopifyAdapter that captures the product_dict passed to
    deploy_product() so we can assert on its shape, and also runs the
    real validate_product_data() check to confirm the payload would have
    been accepted.
    """

    def __init__(self) -> None:
        self.captured: List[Dict[str, Any]] = []
        # Pull the real validator off the real adapter class so we don't
        # duplicate its invariants here.
        from ospra_os.platforms.shopify import ShopifyAdapter
        # Build a bare instance without running __init__ (which would
        # need creds). Rebind the validate method onto ourselves.
        adapter = ShopifyAdapter.__new__(ShopifyAdapter)
        adapter.platform_name = "shopify"
        self._validate = adapter.validate_product_data

    async def deploy_product(self, product: Dict[str, Any]) -> Dict[str, Any]:
        # Run the REAL validator — if it raises, surface the error the
        # way ShopifyAdapter would.
        try:
            self._validate(product)
        except Exception as e:
            return {"success": False, "error": f"validate_product_data rejected payload: {e}"}
        self.captured.append(product)
        # Fake but realistic Shopify response.
        fake_id = str(10_000_000 + len(self.captured))
        return {
            "success": True,
            "platform_product_id": fake_id,
            "platform_url": f"https://smoke-test.com/products/fake-{fake_id}",
            "admin_url": f"https://smoke-test.myshopify.com/admin/products/{fake_id}",
        }


async def _run_one_dry(
    name: str,
    payload: Dict[str, Any],
    expected_sku_prefix: str,
    reporter: Reporter,
) -> None:
    from ospra_os.services.product_deployer import ProductDeployer

    # Instantiate WITHOUT real creds. Shopify init will fail inside
    # ProductDeployer.__init__ — that's fine, we override it.
    os.environ.pop("SHOPIFY_STORE", None)
    os.environ.pop("SHOPIFY_API_TOKEN", None)
    deployer = ProductDeployer.__new__(ProductDeployer)
    # Manually install stubs (skip real __init__ so we don't need API
    # keys for Claude/OpenAI/Shopify).
    deployer.content_generator = None     # forces fallback content (pure sync)
    deployer.image_processor = None       # forces original images (no AI)
    deployer.image_storage = None
    capturing = _CapturingShopify()
    deployer.shopify = capturing

    try:
        result = await deployer.deploy_product(
            source_product=payload,
            niche="smart_home",
            options={"enhance_images": False, "generate_content": False},
        )
    except Exception as e:
        reporter.fail(f"{name}: deploy_product raised",
                      detail=f"{type(e).__name__}: {e}")
        traceback.print_exc()
        return

    reporter.assert_true(
        result.get("success") is True,
        f"{name}: deploy_product returned success=True",
        detail=f"result={json.dumps({k: v for k, v in result.items() if k != 'ai_costs'})[:300]}",
    )
    reporter.assert_true(
        len(capturing.captured) == 1,
        f"{name}: exactly one ShopifyAdapter.deploy_product call",
        detail=f"got {len(capturing.captured)}",
    )
    if not capturing.captured:
        return

    product_dict = capturing.captured[0]

    # Invariant 1: title non-empty string
    reporter.assert_true(
        isinstance(product_dict.get("title"), str) and product_dict["title"].strip(),
        f"{name}: product_dict.title is non-empty string",
        detail=f"got {product_dict.get('title')!r}",
    )

    # Invariant 2: price > 0
    price = product_dict.get("price")
    reporter.assert_true(
        isinstance(price, (int, float)) and price > 0,
        f"{name}: product_dict.price > 0",
        detail=f"got {price!r}",
    )

    # Invariant 3: SKU prefix matches source
    sku = product_dict.get("sku", "")
    reporter.assert_true(
        isinstance(sku, str) and sku.startswith(expected_sku_prefix),
        f"{name}: sku starts with {expected_sku_prefix}",
        detail=f"got sku={sku!r}",
    )

    # Invariant 4: images list populated
    images = product_dict.get("images", [])
    reporter.assert_true(
        isinstance(images, list) and len(images) > 0,
        f"{name}: images list non-empty",
        detail=f"got images={images!r}",
    )

    # Invariant 5: body_html / description populated
    desc = product_dict.get("description", "")
    reporter.assert_true(
        isinstance(desc, str) and len(desc) > 0,
        f"{name}: description (body_html) populated",
        detail=f"got len={len(desc) if isinstance(desc, str) else 'N/A'}",
    )

    # Invariant 6: tags is a list
    tags = product_dict.get("tags")
    reporter.assert_true(
        isinstance(tags, list),
        f"{name}: tags is a list",
        detail=f"got type={type(tags).__name__}",
    )

    # Invariant 7: the REAL ShopifyAdapter.validate_product_data accepted
    # this payload (enforced inside _CapturingShopify.deploy_product —
    # if it failed, success would be False and we'd have caught it in
    # invariant 1). Add an explicit check anyway so the output is
    # self-documenting.
    reporter.ok(f"{name}: ShopifyAdapter.validate_product_data accepted payload")


def run_dry_run(reporter: Reporter) -> None:
    reporter.section("DRY-RUN: deploy_product pipeline (mocked Shopify)")

    for name, payload, expected_prefix in FIXTURES:
        reporter.section(f"fixture: {name}  (expect SKU {expected_prefix}…)")
        asyncio.run(_run_one_dry(name, payload, expected_prefix, reporter))


# ---------------------------------------------------------------------------
# Mode: --live-cj
# ---------------------------------------------------------------------------

def run_live_cj(reporter: Reporter, confirmed: bool) -> None:
    reporter.section("LIVE-CJ: real Shopify deploy of ONE CJ fixture")

    store = os.getenv("SHOPIFY_STORE")
    token = os.getenv("SHOPIFY_API_TOKEN")
    if not store or not token:
        reporter.fail(
            "env check",
            detail="SHOPIFY_STORE and SHOPIFY_API_TOKEN must be set for --live-cj",
        )
        return
    if not confirmed:
        reporter.fail(
            "confirm check",
            detail="pass --confirm to run a real deploy (safety gate)",
        )
        return

    from ospra_os.services.product_deployer import ProductDeployer

    deployer = ProductDeployer(shopify_store=store, shopify_token=token)

    async def go() -> Dict[str, Any]:
        return await deployer.deploy_product(
            source_product=CJ_FIXTURE,
            niche="smart_home",
            # Skip AI so this is a clean schema-check even in live mode.
            options={"enhance_images": False, "generate_content": False},
        )

    try:
        result = asyncio.run(go())
    except Exception as e:
        reporter.fail("live deploy raised", detail=f"{type(e).__name__}: {e}")
        traceback.print_exc()
        return

    reporter.assert_true(
        result.get("success") is True,
        "live deploy success",
        detail=f"result={json.dumps(result)[:500]}",
    )
    if result.get("success"):
        print(f"\n  Live product ID: {result.get('shopify_product_id')}")
        print(f"  Admin URL:       {result.get('admin_url')}")
        print("\n  NOTE: verify the product in Shopify admin — SKU should start"
              " with 'CJ-', images should be present.\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--validate-only", action="store_true",
                      help="Only run Pydantic schema checks (fast, no imports of deployer)")
    mode.add_argument("--dry-run", action="store_true",
                      help="Run deploy_product with a mocked Shopify adapter (default)")
    mode.add_argument("--live-cj", action="store_true",
                      help="Run a real deploy against staging Shopify (requires --confirm)")
    ap.add_argument("--confirm", action="store_true",
                    help="Required safety gate for --live-cj")
    args = ap.parse_args()

    reporter = Reporter()

    if args.validate_only:
        run_validate_only(reporter)
    elif args.live_cj:
        run_live_cj(reporter, confirmed=args.confirm)
    else:
        # default: validate AND dry-run together — the combination
        # proves the whole FastAPI→deployer→Shopify payload contract.
        run_validate_only(reporter)
        run_dry_run(reporter)

    return reporter.summary()


if __name__ == "__main__":
    sys.exit(main())
