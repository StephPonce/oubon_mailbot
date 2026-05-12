"""
Product Analysis & Caption Generation Routes
=============================================
AI-powered analysis and Shopify-ready caption generation.

Routes:
- POST /api/oi/analyze-product - Full AI analysis
- POST /api/oi/generate-caption - Generate Shopify caption

Brand parameterization (Cleanup Pass 4 SaaS refactor):
  Prompts read the tenant's brand name + descriptor from
  ospra_os.tenancy.brand.get_tenant_brand{,_descriptor}. These default to
  "Oubon Shop" / "a premium smart home and lifestyle store" so Oubon's
  single-tenant deployment is unchanged. New tenants can override by
  setting users.brand_name / users.brand_descriptor.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import hashlib
import json
import logging
import os
import time
import httpx

from ospra_os.auth.jwt_auth import get_current_user
from ospra_os.database import User
from ospra_os.tenancy.brand import (
    get_tenant_brand,
    get_tenant_brand_descriptor,
    DEFAULT_BRAND_NAME,
    DEFAULT_BRAND_DESCRIPTOR,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/oi", tags=["AI Analysis"])

ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY') or os.getenv('CLAUDE_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Task #11: Variance controls for AI analysis
# ----------------------------------------------------------------------
# Two users looked at the same product 5 minutes apart and saw two very
# different analyses. Three causes were identified:
#   1. Claude was being called with the default temperature (1.0), so every
#      refresh sampled differently.
#   2. The prompt was constructed from unsorted dict iteration order, so
#      the BYTES of the prompt differed between runs.
#   3. There was no server-side cache, so every UI refresh hit the API.
# We fix all three: deterministic prompt, low temperature, short-TTL cache.
ANALYSIS_TEMPERATURE = 0.2          # low-but-nonzero: stable w/o degenerate tokens
ANALYSIS_CACHE_TTL = int(os.getenv("ANALYSIS_CACHE_TTL_SECONDS", "900"))  # 15min
_analysis_cache: Dict[str, tuple] = {}  # key -> (result, expires_at)


def _round_num(v, decimals: int = 2):
    """Deterministic number formatter used in prompt construction."""
    try:
        return round(float(v), decimals)
    except (TypeError, ValueError):
        return v


def _analysis_cache_key(
    title: str, product: dict, brand_name: str = DEFAULT_BRAND_NAME
) -> str:
    """
    Build a stable cache key so two refreshes of the same product — with
    identical signals — hit the cache instead of firing a fresh API call.

    We SORT keys, ROUND floats, and JSON-dump with sort_keys=True so the
    hash is byte-identical across runs, regardless of dict insertion order.

    `brand_name` is part of the key so two tenants asking about the same
    product don't share each other's cached analyses (the prompt embeds
    the brand, so the output legitimately differs).
    """
    # Only include fields that actually influence the analysis. Others
    # (e.g. a changing 'refreshed_at' timestamp) would invalidate the cache
    # on every call and defeat the purpose.
    relevant = {
        'title': title.strip() if title else '',
        'brand_name': brand_name,
        'niche': product.get('niche', 'general'),
        'cost_price': _round_num(product.get('cost_price', 0)),
        'suggested_price': _round_num(product.get('suggested_price', 0)),
        'profit': _round_num(product.get('profit', 0)),
        'oi_score': _round_num(product.get('oi_score', product.get('score', 50)), 1),
        'demand_score': _round_num(product.get('demand_score', 50), 1),
        'trend_score': _round_num(product.get('trend_score', 50), 1),
        'sentiment_score': _round_num(product.get('sentiment_score', 50), 1),
        'sales_count': product.get('sales_count', 'Unknown'),
        'rating': product.get('rating', 'Unknown'),
        'source': product.get('source', 'Unknown'),
        'data_sources': sorted((product.get('data_sources') or {}).keys()),
    }
    blob = json.dumps(relevant, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _cache_get(key: str) -> Optional[dict]:
    entry = _analysis_cache.get(key)
    if not entry:
        return None
    result, expires_at = entry
    if time.time() > expires_at:
        _analysis_cache.pop(key, None)
        return None
    return result


def _cache_put(key: str, result: dict) -> None:
    _analysis_cache[key] = (result, time.time() + ANALYSIS_CACHE_TTL)


def _clear_analysis_cache() -> None:
    """Test hook / admin helper."""
    _analysis_cache.clear()


# ============================================================================
# REQUEST MODELS
# ============================================================================

class ProductAnalysisRequest(BaseModel):
    product_id: str
    product_title: str
    product_data: Optional[Dict[str, Any]] = {}
    # When True, bypass the 15-minute analysis cache. Wired to the
    # frontend "Refresh" button — the cache was silently shadowing it,
    # making the button look broken. Auto-load on panel-open still
    # leaves this False so it can hit the cache.
    force_refresh: bool = False


class CaptionRequest(BaseModel):
    product_title: str
    product_niche: str = "general"
    price: float = 0
    tags: Optional[List[str]] = []


# Phase K (on-demand): the route accepts a product dict produced by
# discovery, the same shape /analyze-product expects. The Amazon ASIN/URL
# is read from ``product_data.amazon_evidence.top_matches[0]``.
class AmazonReviewTextRequest(BaseModel):
    product_data: Dict[str, Any]
    max_reviews: int = 15


# Lazy singleton — engine init spins up sentiment connectors. We don't
# want to pay that on every request, but we don't want to do it at import
# time either (some tests stub out env vars before importing). One cheap
# instance per process is plenty.
_engine_singleton = None
_engine_lock = None


async def _get_engine():
    """Lazily build a single ProductDiscoveryEngine instance per process."""
    global _engine_singleton, _engine_lock
    if _engine_singleton is not None:
        return _engine_singleton
    import asyncio
    if _engine_lock is None:
        _engine_lock = asyncio.Lock()
    async with _engine_lock:
        if _engine_singleton is not None:
            return _engine_singleton
        from ospra_os.intelligence.product_discovery import ProductDiscoveryEngine
        _engine_singleton = ProductDiscoveryEngine()
    return _engine_singleton


# ============================================================================
# ROUTES
# ============================================================================

@router.post("/analyze-product")
async def analyze_product(request: ProductAnalysisRequest, current_user: User = Depends(get_current_user)):
    """
    Generate comprehensive AI analysis for a product.
    Uses Claude (Anthropic) or falls back to rule-based analysis.

    Task #34: structured error reporting + retry-friendly response.
    Previously this endpoint silently swallowed all Claude failures with
    a generic "AI Analysis failed" toast — users couldn't tell apart
    timeout, rate limit, JSON parse failure, content-policy reject, or
    transient network blip. Different failure modes need different
    responses (retry vs upgrade vs ignore).
    """
    product = request.product_data
    product_title_short = (request.product_title or '')[:60]

    # Resolve tenant brand from the authenticated user (Oubon defaults apply
    # when the user has not set a custom brand_name / brand_descriptor).
    brand_name = (getattr(current_user, "brand_name", None) or DEFAULT_BRAND_NAME)
    brand_descriptor = (
        getattr(current_user, "brand_descriptor", None) or DEFAULT_BRAND_DESCRIPTOR
    )

    # Try Claude API with structured error capture
    claude_error_kind = None  # None | 'no_api_key' | 'timeout' | 'rate_limit' | 'auth' | 'http' | 'json_parse' | 'network' | 'unknown'
    claude_error_detail = None
    claude_retryable = False  # Frontend can show "Try again" only when this is True

    if ANTHROPIC_API_KEY:
        try:
            analysis = await _analyze_with_claude(
                request.product_title,
                product,
                brand_name=brand_name,
                brand_descriptor=brand_descriptor,
                force_refresh=request.force_refresh,
            )
            if analysis:
                return {
                    "success": True,
                    "analysis": analysis,
                    "source": "claude",
                    "product_title": product_title_short,
                }
            # _analyze_with_claude returned None — non-200 response or
            # JSON parse failure. The logger.error inside the helper already
            # captured the specific reason, but we don't currently get the
            # error type back. Mark as unknown for now.
            claude_error_kind = 'unknown'
            claude_error_detail = 'Claude returned no analysis (check backend logs)'
            claude_retryable = True
        except Exception as e:
            # Classify the exception so the frontend can react sensibly.
            err_name = type(e).__name__
            err_msg = str(e)[:200]
            if 'TimeoutException' in err_name or 'Timeout' in err_name:
                claude_error_kind = 'timeout'
                claude_retryable = True
            elif '429' in err_msg or 'rate' in err_msg.lower():
                claude_error_kind = 'rate_limit'
                claude_retryable = True
            elif '401' in err_msg or '403' in err_msg or 'auth' in err_msg.lower():
                claude_error_kind = 'auth'
                claude_retryable = False
            elif 'Connect' in err_name or 'Network' in err_name:
                claude_error_kind = 'network'
                claude_retryable = True
            else:
                claude_error_kind = 'unknown'
                claude_retryable = True
            claude_error_detail = f"{err_name}: {err_msg}"
            logger.warning(
                f"[AI-ANALYSIS] {claude_error_kind} for {product_title_short!r}: {claude_error_detail}"
            )
    else:
        claude_error_kind = 'no_api_key'
        claude_error_detail = 'ANTHROPIC_API_KEY not configured'
        claude_retryable = False

    # Fallback to rule-based analysis. Still returns success=True because
    # SOMETHING is better than nothing, but include the Claude error so the
    # frontend can show a "Generated from rule-based analysis (Claude
    # unavailable — Try again)" banner.
    analysis = _generate_fallback_analysis(request.product_title, product)
    return {
        "success": True,
        "analysis": analysis,
        "source": "fallback",
        "product_title": product_title_short,
        "claude_error": {
            "kind": claude_error_kind,
            "detail": claude_error_detail,
            "retryable": claude_retryable,
        },
    }


@router.post("/refresh-sentiment")
async def refresh_sentiment_now(current_user: User = Depends(get_current_user)):
    """
    Task #17: On-demand sentiment refresh for the current user's watched products.

    Normally the scheduler runs this every 4 hours, but users can hit this
    endpoint to force a refresh (e.g., after a viral TikTok hits a product
    in their store). Returns a summary of how many products were refreshed.
    """
    try:
        from ospra_os.intelligence.sentiment_refresher import SentimentRefresher
        refresher = SentimentRefresher()
        summary = await refresher.refresh_watched_products()
        return {"success": True, "summary": summary}
    except Exception as e:
        logger.error(f"Manual sentiment refresh failed: {e}")
        raise HTTPException(status_code=500, detail=f"Refresh failed: {e}")


@router.post("/amazon-reviews")
async def fetch_amazon_review_text(
    request: AmazonReviewTextRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Phase K (on-demand): pull verbatim Amazon review text for ONE product.

    Called by the frontend when a user opens a product card or hits
    "Refresh AI analysis", NOT during bulk discovery. The fetch is cached
    by ASIN for 24h so repeated clicks on the same listing don't re-bill
    the Apify actor.

    Response:
      - 200 with ``{"success": True, "available": True, ..., "cached": bool}``
        when reviews were fetched (or returned from cache).
      - 200 with ``{"success": True, "available": False, "reason": ...}``
        when the product has no Amazon match, the connector isn't
        configured, or the actor returned nothing — the frontend should
        surface a clean "no Amazon reviews available" state.
    """
    product = request.product_data or {}
    title = product.get("title") or product.get("name") or "(unknown)"

    engine = await _get_engine()

    if not getattr(engine, "amazon_reviews_text_available", False):
        return {
            "success": True,
            "available": False,
            "reason": "amazon_review_text_connector_unavailable",
            "title": title,
        }

    # Quick guard: if the product has no Amazon match at all there's
    # nothing for the engine to fetch. Surface this as a clean "no data"
    # instead of letting the engine silently return None.
    evidence = product.get("amazon_evidence") or {}
    if not (evidence.get("top_matches") or []):
        return {
            "success": True,
            "available": False,
            "reason": "no_amazon_match",
            "title": title,
        }

    try:
        result = await engine.fetch_amazon_review_text(
            product, max_reviews=max(1, min(int(request.max_reviews), 25))
        )
    except Exception as exc:
        logger.warning(f"amazon-reviews fetch failed for {title}: {exc}")
        raise HTTPException(status_code=502, detail=f"Apify call failed: {exc}")

    if not result:
        return {
            "success": True,
            "available": False,
            "reason": "actor_returned_no_data",
            "title": title,
        }

    # Echo the per-product payload so the frontend can render it directly.
    return {
        "success": True,
        "available": True,
        "title": title,
        "asin": result.get("asin"),
        "review_count_returned": result.get("review_count_returned", 0),
        "average_rating": result.get("average_rating"),
        "verified_share": result.get("verified_share", 0.0),
        "reviews": result.get("reviews") or [],
        "cached": result.get("cached", False),
    }


@router.post("/generate-caption")
async def generate_caption(request: CaptionRequest, current_user: User = Depends(get_current_user)):
    """
    Generate Shopify-ready product caption.
    Professional, clean copy - NO emojis, NO hashtags.
    """
    brand_name = (getattr(current_user, "brand_name", None) or DEFAULT_BRAND_NAME)
    brand_descriptor = (
        getattr(current_user, "brand_descriptor", None) or DEFAULT_BRAND_DESCRIPTOR
    )

    # Try Claude API
    if ANTHROPIC_API_KEY:
        try:
            caption = await _generate_caption_with_claude(
                request.product_title,
                request.product_niche,
                request.price,
                request.tags,
                brand_name=brand_name,
                brand_descriptor=brand_descriptor,
            )
            if caption:
                return {"success": True, "caption": caption, "source": "claude"}
        except Exception as e:
            logger.warning(f"Claude caption failed: {e}")

    # Fallback to template
    caption = _generate_template_caption(
        request.product_title,
        request.product_niche,
        request.price,
        request.tags
    )
    return {"success": True, "caption": caption, "source": "template"}


# ============================================================================
# CLAUDE API INTEGRATION
# ============================================================================

def _build_analysis_prompt(
    title: str,
    product: dict,
    brand_name: str = DEFAULT_BRAND_NAME,
    brand_descriptor: str = DEFAULT_BRAND_DESCRIPTOR,
) -> str:
    """
    Task #11: Build a BYTE-STABLE analysis prompt.

    Every field is explicitly formatted (rounded floats, sorted lists) so
    two calls with identical product data produce identical prompts. This
    is a prerequisite for caching and for reducing the non-sampling variance
    the user was hitting. `brand_name` / `brand_descriptor` are part of
    the prompt bytes on purpose; the cache key must incorporate them when
    tenants have different brands (today the cache key already covers it
    via `user_id`).
    """
    ds_keys = sorted((product.get('data_sources') or {}).keys())
    return (
        f"You are an e-commerce analyst for {brand_name}, {brand_descriptor}.\n\n"
        "Analyze this product for dropshipping potential:\n\n"
        f"Product: {title}\n"
        f"Niche: {product.get('niche', 'general')}\n"
        f"Supplier Cost: ${_round_num(product.get('cost_price', 0)):.2f}\n"
        f"Suggested Retail Price: ${_round_num(product.get('suggested_price', 0)):.2f}\n"
        f"Profit: ${_round_num(product.get('profit', 0)):.2f}\n"
        f"OI Score: {_round_num(product.get('oi_score', product.get('score', 50)), 1)}/100\n"
        f"Demand Score: {_round_num(product.get('demand_score', 50), 1)}/100\n"
        f"Trend Score: {_round_num(product.get('trend_score', 50), 1)}/100\n"
        f"Sentiment Score: {_round_num(product.get('sentiment_score', 50), 1)}/100\n"
        f"Sales Count: {product.get('sales_count', 'Unknown')}\n"
        f"Rating: {product.get('rating', 'Unknown')}\n"
        f"Source: {product.get('source', 'Unknown')}\n\n"
        f"Data Sources Available: {ds_keys}\n\n"
        "Provide a PROFESSIONAL analysis in this exact JSON format:\n"
        "{\n"
        '    "summary": "Brief 2-sentence executive summary of product viability",\n'
        '    "verdict": "BUY | CONSIDER | SKIP",\n'
        '    "confidence": 85,\n'
        '    "strengths": ["specific strength 1", "specific strength 2", "specific strength 3"],\n'
        '    "risks": ["specific risk 1", "specific risk 2"],\n'
        '    "target_audience": "Precise target demographic description",\n'
        '    "marketing_angles": ["angle 1", "angle 2", "angle 3"],\n'
        '    "ad_spend_recommendation": "Recommended daily ad budget and approach",\n'
        '    "price_strategy": "Pricing recommendation with reasoning",\n'
        '    "competition_assessment": "Assessment of competitive landscape",\n'
        '    "seasonal_factors": "Any seasonal considerations"\n'
        "}\n\n"
        "Be specific and data-driven. No generic advice. Only respond with valid JSON."
    )


async def _analyze_with_claude(
    title: str,
    product: dict,
    brand_name: str = DEFAULT_BRAND_NAME,
    brand_descriptor: str = DEFAULT_BRAND_DESCRIPTOR,
    force_refresh: bool = False,
) -> Optional[dict]:
    """
    Generate analysis using Claude API.

    Task #11: Variance-locked. See module-level comments.
      - Deterministic prompt (sorted lists, rounded floats)
      - temperature=0.2 (low-but-nonzero sampling)
      - 15-minute in-memory result cache to stop UI refresh loops from
        burning API tokens and producing drifting analyses.
      - ``force_refresh`` (Bug fix): the 15-min cache was silently
        shadowing the frontend "Refresh" button — same product
        signals → same cache key → same response. When True we skip
        the cache lookup but still write the new result back so a
        subsequent auto-load can hit it.
    """
    # Cache check FIRST — same signals, same analysis.
    # Brand is part of the cache key so different tenants don't share cache entries.
    cache_key = _analysis_cache_key(title, product, brand_name=brand_name)
    if not force_refresh:
        cached = _cache_get(cache_key)
        if cached is not None:
            logger.debug(f"[AI-ANALYSIS] Cache hit for {title[:40]!r} (key={cache_key[:8]})")
            return cached

    prompt = _build_analysis_prompt(title, product, brand_name, brand_descriptor)

    # Timeout tightened from 30s → 20s. The global request timeout
    # middleware kicks in at ~30s, so a 30s Claude timeout left zero
    # headroom — when Claude was slow we 504'd the entire request
    # instead of degrading to the rule-based fallback. With 20s we get
    # ~8s of headroom for the fallback to run before global timeout.
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-sonnet-4-5-20250929",
                "max_tokens": 1024,
                "temperature": ANALYSIS_TEMPERATURE,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=20.0
        )

        if response.status_code == 200:
            data = response.json()
            content = data["content"][0]["text"]
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            try:
                parsed = json.loads(content.strip())
            except json.JSONDecodeError as e:
                logger.error(f"[AI-ANALYSIS] Claude returned non-JSON: {e}")
                return None
            _cache_put(cache_key, parsed)
            return parsed
        else:
            logger.error(f"Claude API error: {response.status_code} - {response.text}")
            return None


async def _generate_caption_with_claude(
    title: str,
    niche: str,
    price: float,
    tags: list,
    brand_name: str = DEFAULT_BRAND_NAME,
    brand_descriptor: str = DEFAULT_BRAND_DESCRIPTOR,
) -> Optional[str]:
    """
    Generate PROFESSIONAL Shopify product caption.

    Task #16: Prompt now feeds Claude the specific product signals
    (title tokens, tags, price tier) so copy varies per product
    instead of sounding like a niche template.
    """
    import re as _re

    clean_tags = [t for t in (tags or []) if isinstance(t, str) and t.strip()]
    tag_line = ", ".join(clean_tags[:12]) if clean_tags else "(none provided)"

    # Extract feature-bearing tokens from the title so the prompt
    # has something to chew on even when tags are sparse.
    title_tokens = [
        t for t in _re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", title or "")
        if t.lower() not in {"the", "and", "with", "for", "pro", "max", "mini", "plus"}
    ]
    key_tokens = ", ".join(title_tokens[:8]) if title_tokens else "(none detected)"

    if price <= 0:
        price_tier = "accessible entry price"
    elif price < 15:
        price_tier = f"budget-friendly (~${price:.2f})"
    elif price < 40:
        price_tier = f"mid-range (${price:.2f})"
    elif price < 100:
        price_tier = f"considered purchase (${price:.2f})"
    else:
        price_tier = f"premium tier (${price:.2f})"

    # Caption prompt — anti-template version (regression fix of #16).
    #
    # The previous prompt had a rigid 4-step ``STRUCTURE`` block, which
    # made Claude collapse onto the same scaffold every time
    # (every caption opened "Transform any standard X into an
    # intelligent command center with the Y, engineered for..."). We
    # now (a) drop the structure block entirely, (b) let Claude pick
    # the shape, and (c) explicitly forbid the specific opener
    # patterns we've seen repeat. Combined with ``temperature: 0.9``
    # below this stops the templated-output failure mode.
    prompt = f"""You are a senior copywriter for {brand_name}, {brand_descriptor}.

Write a Shopify product description for THIS SPECIFIC product. The copy must be
recognisably about THIS product — not a generic description of its category.

Product title: {title}
Category: {niche.replace('_', ' ').title()}
Price tier: {price_tier}
Tags: {tag_line}
Salient title tokens: {key_tokens}

REQUIREMENTS
- 80-120 words. Tight, premium, modern. Tone matches the {brand_name} brand.
- Lead with a concrete detail of THIS product (a feature, a use, a material).
  Do NOT open with the words "Transform", "Discover", "Introducing", "Experience",
  "Elevate", "Upgrade your", or any variation that could fit any product.
- Work in at least two product-specific signals drawn from the title, tags, or
  salient tokens above (mechanism, material, capacity, compatibility, etc.).
  Don't invent specs that weren't provided.
- Pick whatever structure best fits THIS product — don't follow a fixed scaffold.
  The shape of the paragraph(s) should differ based on what the product is.
- No emojis. No hashtags. Max 1 exclamation mark in total.
- End with a soft, brand-appropriate close. Avoid "Order now", "Shop today", or
  other off-the-shelf CTAs.

Output ONLY the caption text. No preamble, no labels, no markdown."""

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-sonnet-4-5-20250929",
                "max_tokens": 400,
                # Higher temperature so two products in the same niche
                # genuinely diverge. The analysis call uses 0.2 for
                # stability; captions need the opposite.
                "temperature": 0.9,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=20.0
        )
        
        if response.status_code == 200:
            data = response.json()
            caption = data["content"][0]["text"].strip()
            # Double-check: remove any emojis or hashtags that slipped through
            import re
            caption = re.sub(r'[#⃣[HOT][NEW][PRICE][SUCCESS][SHIPPING][STAR][BELOW][CART][SPECIAL][TARGET][TOP][LOVE][PERFECT][SUCCESS][APPLAUSE][GIFT][PACKAGE]]', '', caption)
            caption = re.sub(r'#\w+', '', caption)
            caption = caption.strip()
            return caption
        else:
            logger.error(f"Claude caption error: {response.status_code}")
            return None


# ============================================================================
# FALLBACK GENERATORS (When API unavailable)
# ============================================================================

def _generate_fallback_analysis(title: str, product: dict) -> dict:
    """Generate rule-based analysis when API unavailable"""
    
    score = product.get('oi_score', product.get('score', 50))
    cost = product.get('cost_price', 0)
    sell = product.get('suggested_price', 0)
    profit = product.get('profit', sell - cost if sell and cost else 0)
    margin = ((sell - cost) / cost * 100) if cost > 0 else 0
    
    # Determine verdict
    if score >= 75:
        verdict = "BUY"
        confidence = 85
    elif score >= 55:
        verdict = "CONSIDER"
        confidence = 65
    else:
        verdict = "SKIP"
        confidence = 70
    
    # Generate strengths based on actual metrics
    strengths = []
    if score >= 70:
        strengths.append(f"High OI score ({score}/100) indicates strong market opportunity")
    if margin >= 100:
        strengths.append(f"Excellent profit margin of {margin:.0f}% supports aggressive ad spend")
    if product.get('sales_count', 0) > 100:
        strengths.append(f"Proven demand with {product.get('sales_count')} confirmed sales")
    if product.get('rating', 0) >= 4.5:
        strengths.append(f"Strong customer satisfaction ({product.get('rating')}/5 rating)")
    if product.get('trend_score', 0) >= 60:
        strengths.append(f"Trending momentum (trend score: {product.get('trend_score')})")
    if product.get('sentiment_score', 50) >= 65:
        strengths.append("Positive social sentiment across platforms")
    if len(strengths) < 2:
        strengths.append("Competitive entry price point")
    
    # Generate risks based on actual data
    risks = []
    if margin < 50:
        risks.append(f"Thin margin ({margin:.0f}%) limits advertising flexibility")
    if product.get('source') == 'aliexpress':
        risks.append("Extended shipping times (10-20 days) may impact customer satisfaction")
    if product.get('competition_score', 50) < 40:
        risks.append("High market saturation in this product category")
    if product.get('sentiment_score', 50) < 45:
        risks.append("Mixed social sentiment suggests quality concerns")
    if len(risks) < 1:
        risks.append("Market conditions subject to seasonal fluctuation")
    
    niche = product.get('niche', 'general').replace('_', ' ')
    
    return {
        "summary": f"{title} presents a {'strong' if score >= 70 else 'moderate' if score >= 50 else 'weak'} opportunity in the {niche} market. {'Recommended for testing with targeted ad campaigns.' if score >= 55 else 'Consider alternative products with better metrics.'}",
        "verdict": verdict,
        "confidence": confidence,
        "strengths": strengths[:4],
        "risks": risks[:3],
        "target_audience": f"Online consumers interested in {niche} products, primarily ages 25-45",
        "marketing_angles": [
            "Problem-solution focused content",
            "Social proof and user testimonials",
            "Comparison to higher-priced alternatives"
        ],
        "ad_spend_recommendation": f"Start with ${10 if score >= 70 else 5}/day, scale to ${50 if margin >= 100 else 25}/day if ROAS > 2.5",
        "price_strategy": f"${sell:.2f} optimal. Test ${sell * 1.1:.2f} for perceived premium value.",
        "competition_assessment": "Moderate competition. Differentiate through faster shipping or bundle offers.",
        "seasonal_factors": "Consistent year-round demand with potential Q4 spike"
    }


def _generate_template_caption(title: str, niche: str, price: float, tags: list) -> str:
    """
    Task #16: Generate a per-product caption that actually varies across
    products in the same niche.

    The old version had 5 hard-coded niche templates and produced
    identical copy for every product in the same niche (only the title
    swapped in). This version composes from three rotating slots (hook,
    body, close) seeded deterministically from the product title + price,
    so the same product always gets the same caption, but different
    products in the same niche get materially different copy.

    It also weaves in product-specific details:
      - Price tier language ("under $20", "premium at $149")
      - Feature hints mined from the title & tags
      - Niche-appropriate hooks (fallback to a generic-lifestyle set)

    NO emojis, NO hashtags.
    """
    import hashlib
    import re as _re

    clean_niche = (niche or "").replace('_', ' ').strip() or "lifestyle"
    # Deterministic seed from title + price so the caption is stable per product.
    seed_src = f"{title}|{price:.2f}".encode('utf-8')
    seed = int(hashlib.sha1(seed_src).hexdigest()[:8], 16)

    def pick(options):
        return options[seed % len(options)]

    def pick_next(options, shift):
        return options[(seed // shift) % len(options)] if options else ""

    # ---- Price tier phrase --------------------------------------------------
    if price <= 0:
        price_phrase = "at an accessible price point"
    elif price < 15:
        price_phrase = f"for under ${int(price + 1)}"
    elif price < 40:
        price_phrase = f"at ${price:.2f}"
    elif price < 100:
        price_phrase = f"at a mid-tier ${price:.2f}"
    else:
        price_phrase = f"at a premium ${price:.2f}"

    # ---- Feature hints from title + tags -----------------------------------
    title_tokens = set(_re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", (title or "").lower()))
    tag_tokens = set(t.lower() for t in (tags or []) if isinstance(t, str))
    signals = title_tokens | tag_tokens

    feature_hints = []
    keyword_map = [
        (["wireless", "bluetooth", "cordless"], "wireless convenience"),
        (["rechargeable", "battery", "usb-c", "usb"],  "long-lasting rechargeable power"),
        (["smart", "app", "wifi", "voice"],   "seamless smart connectivity"),
        (["led", "light", "rgb", "lamp"],     "adjustable ambient lighting"),
        (["stainless", "steel", "aluminum", "alloy"], "durable metal construction"),
        (["portable", "compact", "travel", "mini"], "a compact, portable design"),
        (["waterproof", "ipx", "water-resistant"], "reliable water-resistant build"),
        (["silicone", "eco", "organic", "bpa-free"], "skin-safe, food-grade materials"),
        (["massage", "relief", "therapy"],    "therapeutic comfort"),
        (["foldable", "collapsible"],         "space-saving foldable design"),
        (["rgb", "colors", "dimmable"],       "customizable color control"),
        (["automatic", "auto", "sensor"],     "hands-free automatic operation"),
    ]
    for needles, phrase in keyword_map:
        if any(n in signals for n in needles):
            feature_hints.append(phrase)
        if len(feature_hints) == 3:
            break

    # ---- Hook (opening sentence) -------------------------------------------
    niche_hooks = {
        "smart_home": [
            f"Bring smarter control to the spaces you live in most with the {title}.",
            f"Upgrade your home's rhythm with the {title}.",
            f"Meet the {title} — a quiet upgrade to how your home works.",
        ],
        "kitchen": [
            f"Make every cook feel a little more effortless with the {title}.",
            f"The {title} earns a permanent place on your countertop.",
            f"Bring thoughtful craftsmanship to your kitchen routine with the {title}.",
        ],
        "fitness": [
            f"Train smarter, not harder, with the {title}.",
            f"The {title} makes every session count.",
            f"Build better habits around the {title}.",
        ],
        "beauty": [
            f"Reveal a more polished routine with the {title}.",
            f"Bring salon-level results home with the {title}.",
            f"The {title} is the quiet upgrade your routine has been missing.",
        ],
        "tech": [
            f"Keep up with your day — and get ahead of it — with the {title}.",
            f"Cleaner design, quieter performance: the {title}.",
            f"The {title} replaces three half-measures with one that works.",
        ],
    }
    generic_hooks = [
        f"Meet the {title} — designed around the way you actually use it.",
        f"The {title} quietly earns its keep, one use at a time.",
        f"Simple where it should be, capable where it matters: the {title}.",
        f"A small upgrade that punches above its weight — the {title}.",
    ]
    hooks = niche_hooks.get(niche, generic_hooks)
    hook = pick(hooks)

    # ---- Body (middle — weaves in features) --------------------------------
    if feature_hints:
        if len(feature_hints) >= 2:
            feature_phrase = f"{feature_hints[0]}, {feature_hints[1]}"
            if len(feature_hints) >= 3:
                feature_phrase += f", and {feature_hints[2]}"
        else:
            feature_phrase = feature_hints[0]
        body_variants = [
            f"Built around {feature_phrase}, it fits into your day without asking for much in return.",
            f"It leans on {feature_phrase} — the kind of details that show up every time you use it.",
            f"Between {feature_phrase}, there's a reason this sits in the top of its category.",
        ]
    else:
        body_variants = [
            f"Made for real, daily use — not a showroom photo — it earns its spot quickly.",
            f"It's the kind of {clean_niche} piece you stop noticing in the best way: it just works.",
            f"Every choice in its construction was weighed against how you'd actually use it.",
        ]
    body = pick_next(body_variants, 16)

    # ---- Trust + price line ------------------------------------------------
    trust_variants = [
        f"Quality you can feel, {price_phrase}, with our satisfaction guarantee behind it.",
        f"Priced {price_phrase}, backed by responsive support and a no-fuss returns policy.",
        f"A considered piece {price_phrase}, supported by our customer-first guarantee.",
    ]
    trust = pick_next(trust_variants, 256)

    # ---- Close (CTA) -------------------------------------------------------
    close_variants = [
        "Add it to your cart and see why customers come back for more.",
        "Order yours and see the difference on the first use.",
        "Take it home — the hard part was finding it.",
        "Ready when you are.",
    ]
    close = pick_next(close_variants, 4096)

    return f"{hook}\n\n{body} {trust}\n\n{close}"
