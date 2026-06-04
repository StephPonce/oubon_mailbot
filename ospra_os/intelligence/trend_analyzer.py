"""
Enhanced Trend Analysis System
Integrates Google Trends, Instagram, TikTok for comprehensive product intelligence

NOTE: pytrends is ARCHIVED (April 2025) and constantly hits 429 errors.
This now uses Apify's Google Trends Scraper instead (99.7% success rate).
"""

import os
import logging
from typing import Dict, Optional, List
from datetime import datetime, timedelta
import asyncio

logger = logging.getLogger(__name__)

# Apify Google Trends (PREFERRED - 99.7% success rate, no 429 errors)
HAS_APIFY_TRENDS = False
try:
    from ospra_os.product_research.connectors.apify.google_trends_apify import ApifyGoogleTrends
    HAS_APIFY_TRENDS = True
    logger.info("[SUCCESS] Apify Google Trends connector loaded (replaces pytrends)")
except ImportError as e:
    logger.warning(f"Apify Google Trends not available: {e}")

# Legacy pytrends (archived April 2025) — wired here as the FREE fallback
# when the Apify Google Trends actor is unavailable / quota-exhausted /
# rate-limited. The "expect 429 errors" tag in earlier comments was the
# original author's resignation; with proxies + retries (configured at
# init time, below) it works often enough to lift trend_score off "Est."
# on a meaningful chunk of products.
try:
    from pytrends.request import TrendReq
    HAS_PYTRENDS = True
    logger.warning("[WARNING] pytrends loaded as fallback (DEPRECATED - use Apify instead)")
except ImportError:
    HAS_PYTRENDS = False
    logger.info("pytrends not installed (not needed - using Apify)")


_URLLIB3_PYTRENDS_PATCHED = False


def _patch_urllib3_for_pytrends() -> None:
    """
    Compat shim: pytrends 4.9.x calls ``Retry(method_whitelist=...)`` but
    urllib3 v2 renamed that kwarg to ``allowed_methods`` and removed the
    old one. Without this patch every pytrends call raises
    ``TypeError: Retry.__init__() got an unexpected keyword argument
    'method_whitelist'`` before a single HTTP request fires.

    Pinning urllib3<2 was rejected: it cascades into half the project's
    other HTTP dependencies. Instead we wrap ``Retry.__init__`` and
    aliases ``method_whitelist`` → ``allowed_methods`` on the way in.
    Idempotent, called once at TrendAnalyzer init.
    """
    global _URLLIB3_PYTRENDS_PATCHED
    if _URLLIB3_PYTRENDS_PATCHED:
        return
    try:
        from urllib3.util.retry import Retry
    except Exception:
        return

    original_init = Retry.__init__

    def patched_init(self, *args, **kwargs):
        if "method_whitelist" in kwargs and "allowed_methods" not in kwargs:
            kwargs["allowed_methods"] = kwargs.pop("method_whitelist")
        return original_init(self, *args, **kwargs)

    Retry.__init__ = patched_init
    _URLLIB3_PYTRENDS_PATCHED = True
    logger.info("[TRENDS] urllib3.Retry patched for pytrends 4.x compatibility")

# Claude AI for product analysis
try:
    from anthropic import Anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False
    logger.warning("anthropic package not installed. AI analysis will be unavailable.")


class TrendAnalyzer:
    """
    Multi-platform trend analysis
    - Google Trends (search momentum)
    - Instagram (hashtag popularity)
    - TikTok (video views)
    """

    def __init__(self):
        # Google Trends - Apify FIRST (99.7% success rate, no 429 errors)
        self.apify_trends = None
        self.pytrends = None  # Legacy fallback

        if HAS_APIFY_TRENDS:
            try:
                self.apify_trends = ApifyGoogleTrends()
                logger.info("[SUCCESS] Apify Google Trends initialized (PREFERRED)")
            except Exception as e:
                logger.warning(f"[WARNING] Apify Google Trends init failed: {e}")
                self.apify_trends = None

        # pytrends fallback — initialize WHENEVER it is importable, not just
        # when Apify is missing. The old gate skipped pytrends whenever an
        # Apify client was constructed even if every Apify call returned 0
        # results (paid actor, rate limit, downtime), which is why every
        # Google-Trends row went to UNKNOWN in production. Apify is still
        # preferred (tried first in ``_get_google_trends``); pytrends is
        # here so the fallback path is actually wired.
        #
        # Free-tier rate-limit mitigation:
        #   PYTRENDS_PROXIES — comma-separated list of "https://host:port"
        #     proxies. pytrends rotates through them on retry, dodging the
        #     anonymous-IP 429 wall.
        #   PYTRENDS_RETRIES (default 2) — automatic retry count.
        #   PYTRENDS_BACKOFF (default 0.5) — exponential backoff factor.
        if HAS_PYTRENDS:
            try:
                _patch_urllib3_for_pytrends()
                _proxies_raw = os.getenv("PYTRENDS_PROXIES", "").strip()
                proxies = [p.strip() for p in _proxies_raw.split(",") if p.strip()]
                retries = int(os.getenv("PYTRENDS_RETRIES", "2"))
                backoff = float(os.getenv("PYTRENDS_BACKOFF", "0.5"))
                kwargs = dict(hl="en-US", tz=360, retries=retries, backoff_factor=backoff)
                if proxies:
                    kwargs["proxies"] = proxies
                self.pytrends = TrendReq(**kwargs)
                logger.info(
                    "[TRENDS] pytrends fallback ready "
                    f"(proxies={len(proxies)}, retries={retries}, backoff={backoff})"
                )
            except Exception as e:
                logger.warning(f"[WARNING] pytrends init failed: {e}")
                self.pytrends = None

        if not self.apify_trends and not self.pytrends:
            logger.warning("[WARNING] NO Google Trends available - set APIFY_API_TOKEN")

        # Instagram Graph API
        self.instagram_token = os.getenv('INSTAGRAM_ACCESS_TOKEN')
        if self.instagram_token:
            logger.info("[SUCCESS] Instagram API token found")
        else:
            logger.warning("[WARNING]  INSTAGRAM_ACCESS_TOKEN not set")

        # TikTok API
        self.tiktok_client_key = os.getenv('TIKTOK_CLIENT_KEY')
        if self.tiktok_client_key:
            logger.info("[SUCCESS] TikTok API credentials found")
        else:
            logger.warning("[WARNING]  TIKTOK_CLIENT_KEY not set")

        # Claude AI for product analysis
        self.anthropic_key = os.getenv('ANTHROPIC_API_KEY')
        if HAS_ANTHROPIC and self.anthropic_key:
            try:
                self.claude_client = Anthropic(api_key=self.anthropic_key)
                logger.info("[SUCCESS] Claude AI initialized for product analysis")
            except Exception as e:
                logger.warning(f"[WARNING]  Claude AI init failed: {e}")
                self.claude_client = None
        else:
            self.claude_client = None
            if not self.anthropic_key:
                logger.warning("[WARNING]  ANTHROPIC_API_KEY not set - AI analysis unavailable")

    async def analyze_product_trends(self, product: Dict) -> Dict:
        """
        Comprehensive trend analysis for a product
        Returns enriched data for AI analysis
        """
        product_name = product.get('name', '')
        niche = product.get('niche', '')

        trend_data = {
            'google_trends': await self._get_google_trends(product_name, niche),
            'instagram_data': await self._get_instagram_data(product_name),
            'tiktok_data': await self._get_tiktok_data(product_name),
            'aliexpress_metrics': self._extract_aliexpress_metrics(product),
            'market_signals': self._calculate_market_signals(product)
        }

        return trend_data

    def analyze_product(self, product: Dict) -> Dict:
        """
        AI-powered product analysis using Claude
        Returns investment recommendation and insights
        """
        if not self.claude_client:
            return {
                "status": "error",
                "message": "Claude AI not available. Set ANTHROPIC_API_KEY environment variable.",
                "score": 0,
                "recommendation": "UNAVAILABLE"
            }

        try:
            product_name = product.get('name', 'Unknown Product')
            price = product.get('price', 0)
            cost = product.get('cost', 0)
            velocity_score = product.get('velocity_score', 0)
            profit_margin = product.get('profit_margin', 0)
            estimated_profit = product.get('estimated_profit', 0)
            niche = product.get('niche', 'Unknown')

            # Build analysis prompt
            prompt = f"""You are an expert e-commerce analyst. Analyze this product opportunity:

**Product:** {product_name}
**Niche:** {niche}
**Price:** ${price:.2f}
**Cost:** ${cost:.2f}
**Velocity Score:** {velocity_score}/100
**Profit Margin:** {profit_margin * 100:.1f}%
**Estimated Profit per Sale:** ${estimated_profit:.2f}

Provide a structured analysis with:

1. **Score** (0-10): Overall investment score
2. **Recommendation**: One of STRONG_BUY, BUY, HOLD, PASS
3. **Reasoning**: 3-5 bullet points on marketing angles and opportunities
4. **Risks**: 2-4 bullet points on potential challenges

Format your response as JSON:
{{
  "score": 8.5,
  "recommendation": "STRONG_BUY",
  "reasoning": ["Point 1", "Point 2", "Point 3"],
  "risks": ["Risk 1", "Risk 2"]
}}"""

            logger.info(f"[AI] Analyzing product with Claude: {product_name}")

            response = self.claude_client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}]
            )

            # Parse response
            import json
            response_text = response.content[0].text

            # Try to extract JSON from response
            try:
                # Find JSON in response (might have markdown code blocks)
                import re
                json_match = re.search(r'\{[\s\S]*\}', response_text)
                if json_match:
                    analysis = json.loads(json_match.group())
                else:
                    raise ValueError("No JSON found in response")
            except (json.JSONDecodeError, ValueError, TypeError):
                # Fallback if parsing fails
                logger.warning("Failed to parse Claude response as JSON, using defaults")
                analysis = {
                    "score": 7.0,
                    "recommendation": "HOLD",
                    "reasoning": ["AI analysis parsing failed"],
                    "risks": ["Unable to complete full analysis"]
                }

            logger.info(f"[SUCCESS] Analysis complete - Score: {analysis.get('score')}/10, Recommendation: {analysis.get('recommendation')}")

            return analysis

        except Exception as e:
            logger.error(f"Product analysis failed: {e}")
            return {
                "status": "error",
                "message": f"Analysis failed: {str(e)}",
                "score": 0,
                "recommendation": "ERROR",
                "reasoning": ["Analysis service unavailable"],
                "risks": ["Technical error occurred"]
            }

    async def _get_google_trends(self, product_name: str, niche: str) -> Dict:
        """
        Get Google Trends data for product/niche

        Uses Apify Google Trends Scraper (PREFERRED - 99.7% success rate)
        Falls back to pytrends (DEPRECATED - constant 429 errors)
        """
        # Extract key search terms
        keywords = self._extract_keywords(product_name, niche)[:5]  # Max 5 keywords

        if not keywords:
            return {'available': False, 'reason': 'no keywords'}

        # APIFY: demoted to a last-resort fallback that ONLY runs when
        # pytrends isn't configured at all. The `apify/google-trends-scraper`
        # actor takes ~12 min/run (verified 2026-06-04: a SUCCEEDED run took
        # 739s) — far longer than any inline request timeout — so it must
        # never sit on the discovery request path. pytrends (below) is the
        # primary inline source; Apify is kept only for degraded mode and
        # should be moved to a background pre-warm + cache if reinstated.
        if self.apify_trends and not self.pytrends:
            try:
                logger.info(f"[TRENDS] Fetching Google Trends via Apify (fallback): {keywords}")

                results = await self.apify_trends.get_interest(
                    search_terms=keywords,
                    geo='US',
                    # `today 12-m` is REJECTED by this actor (allowed values:
                    # today 1-m / 3-m / 5-y / all). 3-m returns ~93 daily
                    # points; the recent-window metric adapts to the length.
                    timeframe='today 3-m'
                )

                if results:
                    # Convert Apify results to our format
                    latest_values = {}
                    momentum = {}
                    # Phase G: capture related_queries — what people search
                    # ALONGSIDE this keyword. This is qualitative context for
                    # the AI agent: "users searching for 'smart plug' are
                    # also searching for 'reviews', 'vs alexa', 'doesn't
                    # work' — shape our read of the product accordingly."
                    # Trends remains an INTEREST signal, not a sentiment
                    # signal. We're using related-query VOCABULARY as
                    # qualitative context, not the search-volume number.
                    related_queries_by_kw: dict[str, list] = {}

                    for trend_data in results:
                        kw = trend_data.search_term
                        latest_values[kw] = trend_data.current_interest
                        momentum[kw] = trend_data.velocity
                        rqs = getattr(trend_data, 'related_queries', None) or []
                        if rqs:
                            related_queries_by_kw[kw] = [
                                {
                                    'query': rq.get('query'),
                                    'value': rq.get('value'),
                                    'rank': rq.get('rank'),
                                }
                                for rq in rqs
                                if rq.get('query')
                            ][:10]

                    primary_keyword = keywords[0]
                    primary_momentum = momentum.get(primary_keyword, 0)
                    trend_direction = 'RISING' if primary_momentum > 10 else \
                                    'FALLING' if primary_momentum < -10 else 'STABLE'

                    logger.info(f"[SUCCESS] Apify Google Trends: {trend_direction}, {len(results)} terms")

                    return {
                        'available': True,
                        'source': 'apify',  # Flag that we used Apify
                        'keywords': keywords,
                        'interest_scores': latest_values,
                        'momentum': momentum,
                        'trend_direction': trend_direction,
                        'primary_momentum': primary_momentum,
                        'related_queries': related_queries_by_kw,
                    }

            except Exception as e:
                logger.warning(f"[WARNING] Apify Google Trends failed: {e}")
                # Fall through to pytrends fallback

        # PRIMARY inline source: pytrends (in-process, seconds, works with the
        # urllib3 patch + PYTRENDS_PROXIES wired at init). Chosen over the
        # Apify actor because the actor is ~12 min/run — incompatible with a
        # ~50s discovery request. Verified live 2026-06-04: returns 53 weekly
        # points for `today 12-m` with distinct cross-product series.
        if self.pytrends:
            logger.info(f"[TRENDS] Fetching Google Trends via pytrends: {keywords}")
            try:
                # 12-month timeframe gives us weekly data points (~52),
                # which is exactly what the recent-vs-baseline metric
                # needs: ``today 3-m`` returned daily points where "last
                # 4 weeks" wouldn't span enough data to be meaningful.
                self.pytrends.build_payload(
                    keywords,
                    timeframe='today 12-m',
                    geo='US'
                )

                # Rate limiting: prevent 429 errors
                await asyncio.sleep(2)

                # Get interest over time
                interest_over_time = self.pytrends.interest_over_time()

                if interest_over_time.empty:
                    return {'available': False, 'reason': 'no data'}

                # Convert peak-normalized series → comparable cross-product
                # metric (see ApifyGoogleTrends._parse_apify_result for the
                # same math + rationale). pytrends scales each term to its
                # own peak=100, so latest values were always saturating
                # near 100 and every product looked equally "trending."
                latest_values = {}
                peak_values = {}
                momentum = {}

                for keyword in keywords:
                    if keyword in interest_over_time.columns:
                        values = interest_over_time[keyword].values
                        peak_values[keyword] = int(values[-1]) if len(values) > 0 else 0

                        if len(values) > 0:
                            recent_window = max(1, min(4, len(values) // 4)) if len(values) >= 8 else max(1, len(values) // 2)
                            recent_mean = float(values[-recent_window:].mean())
                            overall_mean = float(values.mean()) if values.mean() > 0 else 1.0
                            ratio = recent_mean / overall_mean
                            latest_values[keyword] = max(0, min(100, int(round(ratio * 50))))
                        else:
                            latest_values[keyword] = 0

                        # Calculate momentum (% change over period)
                        if len(values) >= 2:
                            start_avg = values[:len(values)//3].mean()
                            end_avg = values[-len(values)//3:].mean()
                            if start_avg > 0:
                                momentum[keyword] = round(((end_avg - start_avg) / start_avg) * 100, 1)
                            else:
                                momentum[keyword] = 0
                        else:
                            momentum[keyword] = 0

                # Overall trend direction
                primary_keyword = keywords[0]
                trend_direction = 'RISING' if momentum.get(primary_keyword, 0) > 10 else \
                                'FALLING' if momentum.get(primary_keyword, 0) < -10 else 'STABLE'

                return {
                    'available': True,
                    'source': 'pytrends',  # Flag that we used pytrends
                    'keywords': keywords,
                    'interest_scores': latest_values,
                    'peak_normalized_interest': peak_values,
                    'momentum': momentum,
                    'trend_direction': trend_direction,
                    'primary_momentum': momentum.get(primary_keyword, 0)
                }

            except Exception as e:
                logger.error(f"[ERROR] pytrends error: {e}")
                return {'available': False, 'reason': str(e)}

        return {'available': False, 'reason': 'no trends connector - set APIFY_API_TOKEN'}

    async def get_trend_interest(self, terms: List[str]) -> Dict[str, Dict]:
        """Batch-fetch trend interest for EXPLICIT search phrases.

        Unlike ``_get_google_trends`` this does NOT run keyword extraction —
        it queries the phrases verbatim, batched ≤5 per pytrends call, and
        returns ``{term_lower: {interest, direction, momentum, available}}``.

        Used to wire trend into per-product scores at winner granularity:
        the discovery layer calls this with the winner phrases, then stamps
        each sourced product's ``data_sources['google_trends']`` from its
        winner. ``interest`` is the same comparable recent-vs-baseline metric
        as the rest of the trend path (50 = at baseline, 100 = ~2× baseline).
        """
        out: Dict[str, Dict] = {}
        if not self.pytrends or not terms:
            return out

        # Clean + de-dupe (order-preserving, case-insensitive).
        seen: set = set()
        uniq: List[str] = []
        for t in terms:
            t = (t or '').strip()
            if t and t.lower() not in seen:
                seen.add(t.lower())
                uniq.append(t)

        for i in range(0, len(uniq), 5):
            batch = uniq[i:i + 5]
            try:
                self.pytrends.build_payload(batch, timeframe='today 12-m', geo='US')
                await asyncio.sleep(2)  # gentle pacing to avoid 429s
                iot = self.pytrends.interest_over_time()
                if iot.empty:
                    continue
                for term in batch:
                    if term not in iot.columns:
                        continue
                    values = iot[term].values
                    if len(values) == 0:
                        continue
                    recent_window = max(1, min(4, len(values) // 4)) if len(values) >= 8 else max(1, len(values) // 2)
                    recent_mean = float(values[-recent_window:].mean())
                    overall_mean = float(values.mean()) if values.mean() > 0 else 1.0
                    interest = max(0, min(100, int(round((recent_mean / overall_mean) * 50))))
                    if len(values) >= 3:
                        start_avg = values[:len(values) // 3].mean()
                        end_avg = values[-len(values) // 3:].mean()
                        momentum = round(((end_avg - start_avg) / start_avg) * 100, 1) if start_avg > 0 else 0.0
                    else:
                        momentum = 0.0
                    direction = 'rising' if momentum > 10 else 'falling' if momentum < -10 else 'stable'
                    out[term.lower()] = {
                        'interest': interest,
                        'direction': direction,
                        'momentum': momentum,
                        'available': True,
                    }
            except Exception as e:
                logger.warning(f"[TRENDS] batch interest failed for {batch}: {e}")

        return out

    async def _get_instagram_data(self, product_name: str) -> Dict:
        """
        Get Instagram hashtag data
        Note: Requires Instagram Graph API setup
        """
        if not self.instagram_token:
            return {'available': False, 'reason': 'no_token'}

        try:
            import aiohttp

            # Extract hashtags from product name
            hashtags = self._extract_hashtags(product_name)

            # For now, return placeholder - full implementation requires Business account
            # Instagram Graph API requires Business/Creator account with approved permissions
            return {
                'available': False,
                'reason': 'requires_business_account',
                'note': 'Instagram Graph API requires Business account with approved permissions',
                'potential_hashtags': hashtags
            }

        except Exception as e:
            logger.error(f"Instagram API error: {e}")
            return {'available': False, 'reason': str(e)}

    async def _get_tiktok_data(self, product_name: str) -> Dict:
        """
        Get TikTok trending data
        Note: Requires TikTok API setup
        """
        if not self.tiktok_client_key:
            return {'available': False, 'reason': 'no_credentials'}

        # TikTok API requires OAuth flow - placeholder for now
        return {
            'available': False,
            'reason': 'requires_oauth',
            'note': 'TikTok API requires OAuth authentication flow'
        }

    def _extract_aliexpress_metrics(self, product: Dict) -> Dict:
        """
        Extract and format AliExpress metrics
        """
        orders = product.get('orders', 0)
        rating = product.get('rating', 0)
        price = product.get('price', 0)
        supplier_rating = product.get('supplier_rating', 0)

        # Calculate velocity (orders per day estimate)
        # Assuming products have been on sale for ~1 year on average
        estimated_velocity = round(orders / 365, 1) if orders > 0 else 0

        return {
            'total_orders': orders,
            'rating': rating,
            'price': price,
            'supplier_rating': supplier_rating,
            'estimated_daily_orders': estimated_velocity,
            'monthly_orders_estimate': round(estimated_velocity * 30),
            'revenue_estimate_monthly': round(price * estimated_velocity * 30, 2)
        }

    def _calculate_market_signals(self, product: Dict) -> Dict:
        """
        Calculate market opportunity signals
        """
        orders = product.get('orders', 0)
        rating = product.get('rating', 0)
        score = product.get('score', 0)

        # Market saturation estimate (simplified)
        saturation = 'LOW' if orders < 5000 else 'MEDIUM' if orders < 20000 else 'HIGH'

        # Competition level
        competition = 'LOW' if orders < 10000 else 'MEDIUM' if orders < 50000 else 'HIGH'

        # Demand strength
        demand = 'HIGH' if orders > 20000 and rating > 4.5 else \
                'MEDIUM' if orders > 5000 and rating > 4.0 else 'LOW'

        return {
            'saturation_level': saturation,
            'competition_level': competition,
            'demand_strength': demand,
            'overall_opportunity': 'HIGH' if score > 8 else 'MEDIUM' if score > 6 else 'LOW'
        }

    def _extract_keywords(self, product_name: str, niche: str) -> List[str]:
        """Build clean, Trends-friendly search phrases from a product name.

        Google Trends needs real multi-word product phrases ("wireless
        carplay adapter", "smart video doorbell"), NOT single generic
        tokens. The old version shredded every input into one product-type
        word + one category word + the underscore niche (e.g. ['smart',
        'plug', 'smart_home']) — Trends returns near-zero / ambiguous data
        for bare words like "smart" or the non-word "smart_home", which is
        why the live pipeline saw empty trend series. We now keep the actual
        phrase, and add a generic two-word "{type} {category}" companion
        (never a bare single word) as a broader sibling series.

        Handles both caller shapes: clean niche seeds ("wifi smart plug")
        are used verbatim; long product titles are trimmed to their first
        few informative words.
        """
        import re

        def _clean(text: str) -> str:
            t = (text or "").lower().replace("_", " ").replace("-", " ")
            t = re.sub(r"[^a-z0-9 ]+", " ", t)
            return re.sub(r"\s+", " ", t).strip()

        keywords: List[str] = []
        name = _clean(product_name)

        if name:
            words = name.split()
            if len(words) <= 4:
                # Already a clean, search-friendly phrase — use verbatim.
                phrase = " ".join(words)
            else:
                # Long title → keep the first 3 informative words.
                stop = {"the", "a", "an", "for", "with", "fit", "to", "of",
                        "and", "pack", "set", "new", "case"}
                informative = [w for w in words if w not in stop and len(w) > 2]
                phrase = " ".join(informative[:3]) or " ".join(words[:3])
            if phrase:
                keywords.append(phrase)

        # Generic two-word companion phrase ("{type} {category}") when both
        # are present — gives Trends a broader sibling series. Never a bare
        # single word, and never the underscore niche.
        product_types = ['smart', 'wifi', 'wireless', 'bluetooth', 'led',
                         'portable', 'mini', 'rechargeable', 'solar', 'robot']
        categories = ['light', 'camera', 'speaker', 'vacuum', 'thermostat',
                      'plug', 'bulb', 'strip', 'sensor', 'lock', 'doorbell',
                      'monitor', 'tracker', 'adapter']
        ptype = next((p for p in product_types if p in name), '')
        cat = next((c for c in categories if c in name), '')
        if ptype and cat:
            keywords.append(f"{ptype} {cat}")

        # De-dupe (order-preserving), max 5.
        seen: set = set()
        out: List[str] = []
        for k in keywords:
            if k and k not in seen:
                seen.add(k)
                out.append(k)
        return out[:5]

    def _extract_hashtags(self, product_name: str) -> List[str]:
        """
        Generate potential Instagram hashtags
        """
        name_lower = product_name.lower().replace('-', ' ')
        words = name_lower.split()

        # Remove common words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'with', 'for', 'to', 'of'}
        keywords = [w for w in words if w not in stop_words and len(w) > 3]

        # Generate hashtags
        hashtags = [f"#{w}" for w in keywords[:5]]

        # Add category hashtags
        if 'smart' in name_lower:
            hashtags.append('#smarthome')
        if any(word in name_lower for word in ['light', 'led', 'bulb']):
            hashtags.append('#lighting')
        if 'security' in name_lower or 'camera' in name_lower:
            hashtags.append('#homesecurity')

        return hashtags[:8]  # Max 8 hashtags

    def chat_response(self, message: str, context: Optional[Dict] = None, user_id: Optional[int] = None) -> str:
        """
        Generate a conversational response using Claude AI with smart context building.

        Now uses the scalable memory system to provide unlimited historical knowledge
        without hitting token limits.

        Args:
            message: User's question/message
            context: Optional context about current product, niche, etc.
            user_id: Optional user ID for personalized learning context

        Returns:
            Claude's response as a string
        """
        if not self.claude_client:
            return "I'm currently unavailable. Please make sure ANTHROPIC_API_KEY is set in your environment."

        try:
            # Build system prompt with context
            system_prompt = """You are Ospra, the Chief Operating Officer of the user's e-commerce business. You speak with the authority and clarity of a seasoned executive who respects their CEO's time.

Communication Style:
- Direct and concise - get to the point
- Use data to support insights, not decorate them
- Organize information with clear hierarchy
- NO decorative emoji - Do not use , , [HOT], [TIP], [START], [STATS], [PRICE], or any product/category emoji
- ONLY use [OK] and [WARNING] when marking status or warnings
- Speak in complete sentences, not bullet-point fragments
- When presenting options, be clear about your recommendation and why

Format Guidelines:
- Use headers sparingly and only for major sections
- Bold for emphasis on key metrics or actions only
- Present numbers cleanly: "$45,678" not "**$45,678** [PRICE]"
- Product names are plain text: "Smart Home Security Camera" NOT "[HOT] Smart Home Security Camera "
- If listing items, use clean numbered lists or brief paragraphs
- End with a clear next step or question when appropriate

You have access to:
- Real-time store analytics and revenue data
- Product performance metrics
- Market trends and competitor analysis
- Email/support queue status
- Advertising performance

Your role is to surface what matters, recommend actions, and help the CEO make informed decisions quickly. You're not here to impress - you're here to help run a profitable business."""

            # Build user message with context
            context_str = ""

            # Add current product context if provided (immediate context)
            if context:
                context_str += "\n\n**Current Context:**\n"
                if 'product_name' in context:
                    context_str += f"Product: {context['product_name']}\n"
                if 'product_price' in context:
                    context_str += f"Price: ${context['product_price']}\n"
                if 'velocity_score' in context:
                    context_str += f"Velocity Score: {context['velocity_score']}\n"
                if 'profit_margin' in context:
                    context_str += f"Profit Margin: {context['profit_margin']}%\n"
                if 'niche' in context:
                    context_str += f"Niche: {context['niche']}\n"

            # Add smart learning context if user_id provided (scalable memory system)
            if user_id:
                try:
                    from ospra_os.learning.context_builder import build_claude_context
                    from ospra_os.database import SessionLocal

                    db = SessionLocal()
                    try:
                        # Use smart context builder - automatically selects relevant data based on query
                        learning_context = build_claude_context(user_id, message, db)
                        context_str += "\n\n" + learning_context
                    finally:
                        db.close()

                except ImportError:
                    logger.warning("Smart context builder not available - falling back to basic context")
                    # Fallback to old method if context_builder not available
                    try:
                        from ospra_os.learning.hybrid_learning_engine import get_learning_engine

                        engine = get_learning_engine()

                        # Get personal learning insights (Soar+ tiers)
                        try:
                            personal = engine.session.query(engine.PersonalLearningWeights).filter_by(user_id=user_id).first()

                            if personal and personal.learning_cycles > 0:
                                context_str += "\n**Your Store's Performance History:**\n"
                                context_str += f"- Products analyzed: {personal.sales_analyzed}\n"

                                if personal.best_performing_niches:
                                    niches = personal.best_performing_niches[:3] if isinstance(personal.best_performing_niches, list) else []
                                    if niches:
                                        context_str += f"- Best performing niches: {', '.join(niches)}\n"

                                if personal.optimal_price_range and isinstance(personal.optimal_price_range, dict):
                                    min_price = personal.optimal_price_range.get('min', 0)
                                    max_price = personal.optimal_price_range.get('max', 0)
                                    if min_price > 0 and max_price > 0:
                                        context_str += f"- Optimal price range: ${min_price:.0f}-${max_price:.0f}\n"
                        except (AttributeError, TypeError, KeyError):
                            pass  # Personal weights not available or invalid format
                    except Exception as e:
                        logger.warning(f"Could not fetch fallback learning context: {e}")

                except Exception as e:
                    logger.warning(f"Could not fetch smart context: {e}")
                    # Continue without learning context

            user_message = context_str + "\n" + message if context_str else message

            # DEBUG: Print what Claude receives
            print("=" * 80)
            print("[SEARCH] CLAUDE RECEIVES THIS CONTEXT:")
            print("=" * 80)
            print(f"System Prompt: {system_prompt[:200]}...")
            print("-" * 80)
            print(f"User Message with Context:\n{user_message}")
            print("=" * 80)

            # Call Claude API
            response = self.claude_client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=1024,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": user_message
                    }
                ]
            )

            # Extract text from response
            return response.content[0].text

        except Exception as e:
            logger.error(f"Claude chat error: {e}")
            return f"Sorry, I encountered an error: {str(e)}"
