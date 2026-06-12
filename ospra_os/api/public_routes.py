"""
Public (no-auth) routes — task #52.

GET /api/public/scoreboard — the live proof page: AI-graded product picks
with real store outcomes. This is a marketing asset, so it is:
  - Oubon dogfood data only (SCOREBOARD_USER_ID, default user 1)
  - anonymized: no store URLs, supplier costs, source links, or emails;
    revenue is reported as a direction, not a number
  - cached for 1 hour in-process (the data changes slowly)
  - rate-limited per IP (it's unauthenticated)
"""

import logging
import os
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/public", tags=["Public"])

# BUY = grades we tell users to act on; AVOID = grades we warn against.
# B/C tiers are "consider" and excluded from win-rate math for honesty.
BUY_GRADES = {"A+", "A", "B+"}
AVOID_GRADES = {"D", "F"}

CACHE_TTL_SECONDS = 3600
_cache: dict = {"payload": None, "expires_at": 0.0}

# Unauthenticated endpoint — keep the limit generous enough for a shared
# marketing page behind one office NAT, tight enough to stop scraping loops.
_RATE_LIMIT = "30/minute"
_limiter = None


def _check_rate_limit(request: Request) -> bool:
    """True if this client is allowed. Fail-open if the limiter breaks."""
    global _limiter
    try:
        if _limiter is None:
            from ospra_os.middleware.custom_rate_limiter import InMemoryRateLimiter
            _limiter = InMemoryRateLimiter()
        client_ip = request.client.host if request.client else "unknown"
        allowed, _ = _limiter.is_allowed(f"scoreboard:{client_ip}", _RATE_LIMIT)
        return allowed
    except Exception as e:  # pragma: no cover - limiter must never 500 the page
        logger.warning(f"Scoreboard rate limiter unavailable: {e}")
        return True


def _scoreboard_user_id() -> int:
    return int(os.getenv("SCOREBOARD_USER_ID", "1"))


def _niche_from_tags(tags) -> Optional[str]:
    if isinstance(tags, list) and tags:
        first = tags[0]
        if isinstance(first, str) and first.strip():
            return first.strip().replace("-", " ").replace("_", " ")
    return None


def _build_scoreboard() -> dict:
    """Query graded picks + outcomes for the dogfood tenant.

    Each query is guarded independently so prod schema drift (a missing
    column or un-migrated table) degrades the page instead of 503-ing it.
    `degraded_stages` names which query failed — those names are not
    sensitive (no table names / SQL) so they're safe in the public body,
    while the full exception is logged server-side with exc_info.
    """
    from ospra_os.auth.jwt_auth import get_db
    from ospra_os.database.product_models import Product
    from ospra_os.database.performance_models import AILearningEvent
    from ospra_os.database.store_models import Store

    user_id = _scoreboard_user_id()
    degraded_stages = []
    products = []
    first_sales = []
    db = next(get_db())
    try:
        try:
            products = (
                db.query(Product)
                .join(Store, Product.store_id == Store.id)
                .filter(Store.user_id == user_id, Product.grade.isnot(None))
                .order_by(Product.created_at.desc())
                .limit(200)
                .all()
            )
        except Exception as e:
            db.rollback()
            logger.error(f"Scoreboard graded_products query failed: {e}", exc_info=True)
            degraded_stages.append("graded_products")

        # first-sale events carry days_to_first_sale in their details JSON
        try:
            first_sales = (
                db.query(AILearningEvent)
                .filter(
                    AILearningEvent.user_id == user_id,
                    AILearningEvent.event_type == "first_sale",
                )
                .all()
            )
        except Exception as e:
            db.rollback()
            logger.error(f"Scoreboard first_sales query failed: {e}", exc_info=True)
            degraded_stages.append("first_sales")
    finally:
        db.close()

    days_to_sale_by_product: dict = {}
    for event in first_sales:
        details = event.details or {}
        pid = str(details.get("product_id") or event.product_id or "")
        days = details.get("days_to_first_sale")
        if pid and isinstance(days, (int, float)):
            # keep the earliest (first) sale if duplicates exist
            existing = days_to_sale_by_product.get(pid)
            if existing is None or days < existing:
                days_to_sale_by_product[pid] = int(days)

    picks = []
    buy_deployed = buy_with_sales = 0
    avoid_total = avoid_with_sales = 0
    sale_days = []

    for p in products:
        try:
            grade = (getattr(p, "grade", None) or "").strip()
            units = getattr(p, "total_sales", 0) or 0
            deployed = getattr(p, "deployed_at", None) is not None
            days_to_first_sale = days_to_sale_by_product.get(str(p.id))
            if days_to_first_sale is not None:
                sale_days.append(days_to_first_sale)

            if grade in BUY_GRADES and deployed:
                buy_deployed += 1
                if units > 0:
                    buy_with_sales += 1
            if grade in AVOID_GRADES:
                avoid_total += 1
                if units > 0:
                    avoid_with_sales += 1

            score = getattr(p, "discovery_score", None)
            created = getattr(p, "created_at", None)
            picks.append({
                # Anonymized: title + niche only; no source/store/supplier data.
                "title": (getattr(p, "ai_title", None) or getattr(p, "product_name", None)
                          or "Unnamed product")[:120],
                "niche": _niche_from_tags(getattr(p, "ai_tags", None)) or "general",
                "grade": grade,
                "score": round(score, 1) if score else None,
                "graded_at": created.isoformat() if created else None,
                "deployed": deployed,
                "units_sold": units if deployed else None,
                "revenue_direction": (
                    "up" if (getattr(p, "total_revenue", 0) or 0) > 0 else "flat"
                ) if deployed else None,
                "days_to_first_sale": days_to_first_sale,
            })
        except Exception as e:
            logger.warning(f"Scoreboard skipped a malformed product row: {e}")
            continue

    sale_days.sort()
    median_days = sale_days[len(sale_days) // 2] if sale_days else None
    sold_within_14 = sum(1 for d in sale_days if d <= 14)

    return {
        "picks": picks[:50],
        "stats": {
            "total_graded": len(picks),
            "buy_graded_deployed": buy_deployed,
            "buy_with_sales": buy_with_sales,
            "buy_win_rate": round(buy_with_sales / buy_deployed, 3) if buy_deployed else None,
            "avoid_graded": avoid_total,
            "avoid_with_sales": avoid_with_sales,
            "median_days_to_first_sale": median_days,
            "sold_within_14_days": sold_within_14,
            "first_sale_sample_size": len(sale_days),
        },
        "meta": {
            "source": "Live Oubon Shop store data — our own storefront running Ospra",
            "note": "Small sample sizes are shown as-is; we don't extrapolate.",
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "degraded_stages": degraded_stages,
        },
    }


@router.get("/scoreboard")
async def get_public_scoreboard(request: Request):
    """Public, cached, rate-limited scoreboard of graded picks + outcomes."""
    if not _check_rate_limit(request):
        raise HTTPException(status_code=429, detail="Too many requests — try again in a minute.")

    now = time.time()
    if _cache["payload"] is not None and now < _cache["expires_at"]:
        return _cache["payload"]

    try:
        payload = _build_scoreboard()
    except Exception as e:
        logger.error(f"Scoreboard build failed: {e}", exc_info=True)
        # Serve stale cache over an error page if we have one.
        if _cache["payload"] is not None:
            return _cache["payload"]
        raise HTTPException(status_code=503, detail="Scoreboard temporarily unavailable.")

    # Full-hour cache only for clean builds; a degraded payload caches briefly
    # so the page recovers quickly once the underlying schema issue is fixed.
    degraded = bool(payload.get("meta", {}).get("degraded_stages"))
    _cache["payload"] = payload
    _cache["expires_at"] = now + (60 if degraded else CACHE_TTL_SECONDS)
    return payload
