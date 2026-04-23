"""
[BRAIN] AI PRODUCT ANALYZER - Claude-Powered COO Analysis
====================================================

This is THE MISSING PIECE that transforms Ospra from
"hot products dashboard" into "AI e-commerce COO".

Takes validated products from discovery engine and generates:
1. Deep strategic analysis (not templates)
2. Anti-saturation assessment
3. Timing recommendations
4. Store-specific fit analysis
5. Risk factors and mitigation
6. Execution plan

Uses Claude for reasoning - the best at complex analysis.

CACHING: v2.0 adds analysis caching for:
- Consistency: Same product = same analysis (until cache expires)
- Cost reduction: Avoid duplicate API calls
- Speed: Instant response for cached products

Author: OspraOS
Date: December 2024
Updated: v2.0 with caching support
"""

import os
import json
import asyncio
import logging
import hashlib
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Import AI Factory for Claude access
try:
    from ospra_os.ai.factory import AIFactory
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    logger.warning("AI Factory not available")


@dataclass
class COOAnalysis:
    """Complete COO-level product analysis from Claude"""

    # Product identification
    product_id: str
    product_name: str
    niche: str

    # Scores (from discovery engine)
    ospra_score: float
    confidence: float

    # Claude-generated analysis
    executive_summary: str          # 2-3 sentence overview
    market_timing_analysis: str     # Why now? Window of opportunity
    competitive_position: str       # Saturation and differentiation
    store_fit_analysis: str         # Why this product for THIS store
    profit_strategy: str            # Pricing and margin recommendations
    risk_assessment: str            # What could go wrong
    execution_plan: str             # Step-by-step action items

    # Structured recommendations
    recommendation: str             # DEPLOY_NOW, DEPLOY_SOON, MONITOR, SKIP
    urgency: str                    # CRITICAL, HIGH, MEDIUM, LOW
    confidence_level: str           # HIGH, MEDIUM, LOW

    # Key metrics extracted
    estimated_monthly_profit: float
    suggested_price: float
    competition_level: str          # LOW, MEDIUM, HIGH, SATURATED
    trend_stage: str                # EMERGING, GROWING, PEAK, DECLINING
    first_mover_window_days: int    # Days until market saturates

    # Action items
    immediate_actions: List[str]
    watch_triggers: List[str]       # What would change recommendation

    # DATA TRANSPARENCY - NEW
    data_sources_cited: str = ""    # Which sources were used in analysis
    sources_validated: List[str] = field(default_factory=list)  # List of validated sources
    score_breakdown: Dict[str, Any] = field(default_factory=dict)  # Detailed score components

    # Metadata
    analyzed_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    analysis_version: str = "v2.0"  # Updated version
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "product_id": self.product_id,
            "product_name": self.product_name,
            "niche": self.niche,
            "ospra_score": self.ospra_score,
            "confidence": self.confidence,
            "executive_summary": self.executive_summary,
            "market_timing_analysis": self.market_timing_analysis,
            "competitive_position": self.competitive_position,
            "store_fit_analysis": self.store_fit_analysis,
            "profit_strategy": self.profit_strategy,
            "risk_assessment": self.risk_assessment,
            "execution_plan": self.execution_plan,
            "recommendation": self.recommendation,
            "urgency": self.urgency,
            "confidence_level": self.confidence_level,
            "estimated_monthly_profit": self.estimated_monthly_profit,
            "suggested_price": self.suggested_price,
            "competition_level": self.competition_level,
            "trend_stage": self.trend_stage,
            "first_mover_window_days": self.first_mover_window_days,
            "immediate_actions": self.immediate_actions,
            "watch_triggers": self.watch_triggers,
            # DATA TRANSPARENCY
            "data_sources_cited": self.data_sources_cited,
            "sources_validated": self.sources_validated,
            "score_breakdown": self.score_breakdown,
            "analyzed_at": self.analyzed_at,
            "analysis_version": self.analysis_version,
        }


class AnalysisCache:
    """
    In-memory cache for AI analysis results.

    Provides:
    - TTL-based expiration (default 4 hours)
    - Consistent results for same product
    - Reduced API costs
    """

    def __init__(self, default_ttl_hours: float = 4.0):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._default_ttl = timedelta(hours=default_ttl_hours)
        self._stats = {"hits": 0, "misses": 0, "evictions": 0}

    def _generate_key(self, product: Dict[str, Any], store_context: Optional[Dict] = None) -> str:
        """
        Generate cache key from product and store context.

        The key is intentionally coarse — product_id + store_name only. Previously
        it included oi_score and confidence, which meant every tiny score wobble
        from a fresh discovery (±1-2 points from shifted supplier data) busted the
        cache and triggered a new Claude call with fresh variance. That was the
        root cause of the >10% drift users saw between refreshes.

        If a user genuinely wants a fresh take after material score changes, the
        "Refresh Analysis" button calls analyze_product(force_refresh=True) which
        bypasses this cache entirely.
        """
        product_id = product.get("id") or product.get("product_id", "")
        store_name = (store_context or {}).get("store_name", "default")

        key_string = f"{product_id}|{store_name}"
        return hashlib.sha256(key_string.encode()).hexdigest()[:16]

    def get(self, product: Dict[str, Any], store_context: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        """Get cached analysis if fresh."""
        key = self._generate_key(product, store_context)

        if key not in self._cache:
            self._stats["misses"] += 1
            return None

        entry = self._cache[key]
        cached_at = entry.get("cached_at")
        ttl = entry.get("ttl", self._default_ttl)

        # Check if expired
        if datetime.utcnow() - cached_at > ttl:
            del self._cache[key]
            self._stats["evictions"] += 1
            self._stats["misses"] += 1
            return None

        self._stats["hits"] += 1
        return entry.get("analysis")

    def set(
        self,
        product: Dict[str, Any],
        analysis: Dict[str, Any],
        store_context: Optional[Dict] = None,
        ttl: Optional[timedelta] = None
    ):
        """Cache an analysis result."""
        key = self._generate_key(product, store_context)
        self._cache[key] = {
            "analysis": analysis,
            "cached_at": datetime.utcnow(),
            "ttl": ttl or self._default_ttl,
            "product_id": product.get("id") or product.get("product_id"),
        }

    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {
            **self._stats,
            "cached_count": len(self._cache),
            "hit_rate": round(self._stats["hits"] / max(1, self._stats["hits"] + self._stats["misses"]) * 100, 1)
        }

    def clear(self):
        """Clear all cached entries."""
        count = len(self._cache)
        self._cache.clear()
        return count

    def cleanup_expired(self) -> int:
        """Remove expired entries."""
        now = datetime.utcnow()
        expired_keys = []

        for key, entry in self._cache.items():
            cached_at = entry.get("cached_at")
            ttl = entry.get("ttl", self._default_ttl)
            if now - cached_at > ttl:
                expired_keys.append(key)

        for key in expired_keys:
            del self._cache[key]
            self._stats["evictions"] += 1

        return len(expired_keys)


class AIProductAnalyzer:
    """
    Claude-powered product analyzer for COO-level insights.

    This transforms raw scores into actionable business intelligence.

    v2.0 Features:
    - Analysis caching for consistency and cost reduction
    - Data source transparency
    - Score breakdown integration
    """
    
    # Analysis prompt template - UPDATED with source transparency
    COO_ANALYSIS_PROMPT = """You are a veteran e-commerce COO with 15+ years experience in dropshipping,
market analysis, and scaling online stores. You're analyzing a product opportunity for deployment.

## PRODUCT DATA
Name: {product_name}
Niche: {niche}
Supplier Cost: ${cost:.2f}
Suggested Retail: ${selling_price:.2f}
Profit per Sale: ${profit:.2f}
Profit Margin: {margin:.1f}%
Product Tier: {tier}

## CROSS-REFERENCED SCORES (0-100 scale)
- Google Trends Score: {google_score}/100 (Trend Direction: {trend_direction})
- TikTok Viral Score: {tiktok_score}/100
- Twitter/X Sentiment: {twitter_score}/100 ({twitter_mentions} mentions)
- AliExpress Orders Score: {order_score}/100 ({orders:,} orders)
- Amazon Rank Score: {amazon_score}/100
- Reddit Sentiment: {reddit_score}/100 ({reddit_mentions} mentions)
- Supplier Rating: {supplier_score}/100 ({rating} stars)

## COMPONENT SCORES (Used in OI calculation)
- Demand Score: {demand_score}/100 (Sales volume, views, BSR)
- Trend Score: {trend_score_component}/100 (Google Trends, virality)
- Sentiment Score: {sentiment_score}/100 (Social proof, mentions)
- Profit Score: {profit_score}/100 (Margin analysis)
- Sourcing Score: {sourcing_score}/100 (Cross-reference, warehouse)

## COMPOSITE SCORE
OSPRA OI Score: {ospra_score}/100
Confidence: {confidence}%
Sources Validated: {sources_count}/6 ({sources_list})

## DATA SOURCE TRANSPARENCY
{data_source_details}

## STORE CONTEXT
Store Name: {store_name}
Store Niche Focus: {store_niche}
Previous Best Sellers: {best_sellers}
Average Order Value: ${aov:.2f}
Historical Conversion Rate: {conversion_rate:.2f}%

## YOUR TASK
Provide a comprehensive COO-level analysis. Be specific, actionable, and data-driven.
Don't hedge - make clear recommendations based on the data.

IMPORTANT: Your confidence_level MUST match the confidence percentage above:
- 70%+ confidence = HIGH confidence_level
- 40-69% confidence = MEDIUM confidence_level
- <40% confidence = LOW confidence_level

Reference the specific data sources in your analysis (e.g., "Based on {orders:,} AliExpress orders..." or "Google Trends shows {trend_direction} momentum...").

Respond in this EXACT JSON format:
{{
    "executive_summary": "2-3 sentence overview referencing key data points",
    "market_timing_analysis": "Detailed analysis of WHY NOW. Reference trend direction ({trend_direction}) and specific metrics.",
    "competitive_position": "Analysis of competition level, saturation risk, and differentiation strategy",
    "store_fit_analysis": "Why this product fits (or doesn't fit) THIS specific store ({store_name})",
    "profit_strategy": "Specific pricing recommendation. Cost: ${cost:.2f}, Suggested: ${selling_price:.2f}, Margin: {margin:.1f}%",
    "risk_assessment": "Top 3 risks with specific mitigation strategies",
    "execution_plan": "Step-by-step plan based on {tier} tier classification",
    "data_sources_cited": "List of data sources used: {sources_list}",
    "recommendation": "DEPLOY_NOW | DEPLOY_SOON | MONITOR | SKIP",
    "urgency": "CRITICAL | HIGH | MEDIUM | LOW",
    "confidence_level": "HIGH | MEDIUM | LOW (must match {confidence}% confidence)",
    "estimated_monthly_profit": <number>,
    "suggested_price": <number>,
    "competition_level": "LOW | MEDIUM | HIGH | SATURATED",
    "trend_stage": "EMERGING | GROWING | PEAK | DECLINING",
    "first_mover_window_days": <number>,
    "immediate_actions": ["action 1", "action 2", "action 3"],
    "watch_triggers": ["trigger that would change recommendation 1", "trigger 2"]
}}

Be a COO, not a chatbot. Make the call based on the ACTUAL data provided."""

    def __init__(self, api_key: Optional[str] = None, cache_ttl_hours: float = 4.0):
        """
        Initialize with Claude API key and caching.

        Args:
            api_key: Anthropic API key (defaults to env var)
            cache_ttl_hours: How long to cache analyses (default 4 hours)
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.ai_provider = None
        self._initialized = False

        # Initialize analysis cache
        self._cache = AnalysisCache(default_ttl_hours=cache_ttl_hours)
        self._cache_enabled = True

        if not AI_AVAILABLE:
            logger.error("AI Factory not available - cannot initialize analyzer")
            return

        if not self.api_key:
            logger.error("ANTHROPIC_API_KEY not set - cannot initialize analyzer")
            return

        try:
            self.ai_provider = AIFactory.get_provider("claude", self.api_key)
            self._initialized = True
            logger.info(f"[SUCCESS] AI Product Analyzer initialized with Claude (cache TTL: {cache_ttl_hours}h)")
        except Exception as e:
            logger.error(f"Failed to initialize Claude: {e}")
    
    def is_available(self) -> bool:
        """Check if analyzer is ready."""
        return self._initialized and self.ai_provider is not None

    def enable_cache(self, enabled: bool = True):
        """Enable or disable caching."""
        self._cache_enabled = enabled
        logger.info(f"Analysis cache {'enabled' if enabled else 'disabled'}")

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return self._cache.get_stats()

    def clear_cache(self) -> int:
        """Clear all cached analyses."""
        return self._cache.clear()
    
    async def analyze_product(
        self,
        product: Dict[str, Any],
        store_context: Optional[Dict[str, Any]] = None,
        force_refresh: bool = False
    ) -> Optional[COOAnalysis]:
        """
        Generate COO-level analysis for a product.

        Args:
            product: Validated product from discovery engine
            store_context: Information about the user's store
            force_refresh: If True, bypass cache and generate fresh analysis

        Returns:
            COOAnalysis with comprehensive strategic assessment

        Caching:
            - Analyses are cached for 4 hours by default
            - Cache key includes product ID, OI score, and store name
            - Set force_refresh=True to bypass cache
        """
        if not self.is_available():
            logger.error("Analyzer not available")
            return None

        # Check cache first (unless force_refresh)
        if self._cache_enabled and not force_refresh:
            cached = self._cache.get(product, store_context)
            if cached:
                product_name = product.get("name") or product.get("title", "Unknown")
                logger.info(f"[CACHE HIT] Returning cached analysis for: {product_name[:40]}...")
                # Return cached COOAnalysis
                return COOAnalysis(**cached) if isinstance(cached, dict) else cached

        # Extract product data - handle multiple field name formats
        product_name = product.get("name") or product.get("title", "Unknown Product")
        niche = product.get("niche", "general")

        # Pricing - handle multiple field names
        cost = float(product.get("cost") or product.get("cost_price") or product.get("supplier_cost") or 0)
        selling_price = float(product.get("selling_price") or product.get("suggested_price") or product.get("price") or 0)
        if selling_price == 0 and cost > 0:
            selling_price = cost * 2.5  # Default markup
        profit = float(product.get("profit", selling_price - cost))
        margin = float(product.get("profit_margin") or product.get("profit_margin_pct") or ((profit / selling_price * 100) if selling_price > 0 else 0))

        # Get score_breakdown (now populated by fixed scoring algorithm)
        score_breakdown = product.get("score_breakdown", {})

        # Extract individual scores from score_breakdown
        google_score = score_breakdown.get("google_trends", 40)
        tiktok_score = score_breakdown.get("tiktok_viral", 40)
        twitter_score = score_breakdown.get("twitter_sentiment", 40)
        order_score = score_breakdown.get("aliexpress_orders", 40)
        amazon_score = score_breakdown.get("amazon_rank", 50)
        reddit_score = score_breakdown.get("reddit_sentiment", 40)
        supplier_score = score_breakdown.get("supplier_rating", 50)

        # Component scores (from scoring algorithm)
        demand_score = product.get("demand_score", 40)
        trend_score_component = product.get("trend_score", 40)
        sentiment_score = product.get("sentiment_score", 40)
        profit_score = product.get("profit_score", 40)
        sourcing_score = product.get("sourcing_score", 35)

        # Tier from scoring
        tier = product.get("tier", "FAIR")

        # Social proof - extract from data_sources or direct fields
        data_sources = product.get("data_sources", {})
        twitter_data = data_sources.get("x_twitter", {})
        reddit_data = data_sources.get("reddit", {})
        ali_data = data_sources.get("aliexpress", {})

        twitter_mentions = twitter_data.get("mentions", 0) or product.get("twitter_mentions", 0)
        reddit_mentions = reddit_data.get("mentions", 0) or product.get("reddit_mentions", 0)

        # Order count from AliExpress
        orders = int(ali_data.get("orders", 0) or product.get("sales_count") or product.get("orders", 0))

        # Rating
        rating = float(product.get("rating") or ali_data.get("rating") or 4.0)

        # Composite score (now 0-100 from scoring algorithm)
        ospra_score = float(product.get("oi_score") or product.get("score") or product.get("ospra_score") or 50)

        # Confidence (based on sources validated)
        sources_validated = product.get("sources_validated", [])
        confidence = float(product.get("confidence") or (len(sources_validated) / 6 * 100) or 50)

        # Trend direction
        trend_direction = product.get("trend_direction", "stable")

        # Build data source transparency section
        data_source_details = self._build_data_source_details(product, data_sources, sources_validated)

        # Store context (defaults if not provided)
        store_context = store_context or {}
        store_name = store_context.get("store_name", "Your Store")
        store_niche = store_context.get("niche", niche)
        best_sellers = store_context.get("best_sellers", "Not enough data yet")
        aov = float(store_context.get("avg_order_value", 35.00))
        conversion_rate = float(store_context.get("conversion_rate", 2.0))

        # Build prompt with all the new fields
        prompt = self.COO_ANALYSIS_PROMPT.format(
            product_name=product_name,
            niche=niche,
            cost=cost,
            selling_price=selling_price,
            profit=profit,
            margin=margin,
            tier=tier,
            google_score=google_score,
            tiktok_score=tiktok_score,
            twitter_score=twitter_score,
            twitter_mentions=twitter_mentions,
            order_score=order_score,
            orders=orders,
            amazon_score=amazon_score,
            reddit_score=reddit_score,
            reddit_mentions=reddit_mentions,
            supplier_score=supplier_score,
            rating=rating,
            demand_score=demand_score,
            trend_score_component=trend_score_component,
            sentiment_score=sentiment_score,
            profit_score=profit_score,
            sourcing_score=sourcing_score,
            trend_direction=trend_direction,
            ospra_score=ospra_score,
            confidence=confidence,
            sources_count=len(sources_validated),
            sources_list=", ".join(sources_validated) if sources_validated else "limited data",
            data_source_details=data_source_details,
            store_name=store_name,
            store_niche=store_niche,
            best_sellers=best_sellers,
            aov=aov,
            conversion_rate=conversion_rate,
        )
        
        try:
            logger.info(f"[BRAIN] Analyzing: {product_name[:50]}...")
            
            # Call Claude with LOW TEMPERATURE for consistency.
            # Anthropic's API defaults to temperature=1.0 which was producing
            # >10% drift between refreshes on the same product. 0.2 is low enough
            # to be near-deterministic for structured JSON output while still
            # allowing Claude to pick the most natural phrasing. (Anthropic's API
            # doesn't support a `seed` parameter — unlike OpenAI — so we can't
            # make it strictly deterministic.)
            response = await self.ai_provider.chat(
                message=prompt,
                context={
                    "system_prompt": "You are a veteran e-commerce COO. Respond only with valid JSON.",
                    "temperature": 0.2,
                }
            )
            
            # Parse response
            analysis_data = self._parse_response(response)
            
            if not analysis_data:
                logger.error(f"Failed to parse Claude response for {product_name}")
                return None
            
            # Build COOAnalysis with data transparency
            analysis = COOAnalysis(
                product_id=product.get("id") or product.get("product_id", ""),
                product_name=product_name,
                niche=niche,
                ospra_score=ospra_score,
                confidence=confidence,
                executive_summary=analysis_data.get("executive_summary", ""),
                market_timing_analysis=analysis_data.get("market_timing_analysis", ""),
                competitive_position=analysis_data.get("competitive_position", ""),
                store_fit_analysis=analysis_data.get("store_fit_analysis", ""),
                profit_strategy=analysis_data.get("profit_strategy", ""),
                risk_assessment=analysis_data.get("risk_assessment", ""),
                execution_plan=analysis_data.get("execution_plan", ""),
                recommendation=analysis_data.get("recommendation", "MONITOR"),
                urgency=analysis_data.get("urgency", "MEDIUM"),
                confidence_level=analysis_data.get("confidence_level", "MEDIUM"),
                estimated_monthly_profit=float(analysis_data.get("estimated_monthly_profit", 0)),
                suggested_price=float(analysis_data.get("suggested_price", selling_price)),
                competition_level=analysis_data.get("competition_level", "MEDIUM"),
                trend_stage=analysis_data.get("trend_stage", "GROWING"),
                first_mover_window_days=int(analysis_data.get("first_mover_window_days", 30)),
                immediate_actions=analysis_data.get("immediate_actions", []),
                watch_triggers=analysis_data.get("watch_triggers", []),
                # DATA TRANSPARENCY - NEW
                data_sources_cited=analysis_data.get("data_sources_cited", ", ".join(sources_validated)),
                sources_validated=sources_validated,
                score_breakdown=score_breakdown,
            )

            # Cache the analysis for future requests
            if self._cache_enabled:
                self._cache.set(product, analysis.to_dict(), store_context)
                logger.info(f"[CACHE STORED] Analysis cached for: {product_name[:40]}...")

            return analysis

        except Exception as e:
            logger.error(f"Claude analysis failed: {e}")
            return None
    
    def _build_data_source_details(
        self,
        product: Dict[str, Any],
        data_sources: Dict[str, Any],
        sources_validated: List[str]
    ) -> str:
        """Build a transparency section showing which data sources contributed."""
        lines = []

        # AliExpress data
        ali_data = data_sources.get("aliexpress", {})
        if "aliexpress" in sources_validated or ali_data.get("available"):
            orders = ali_data.get("orders", 0) or product.get("sales_count", 0)
            commission = ali_data.get("commission", "0%")
            lines.append(f"✅ AliExpress: {orders:,} orders, {commission} commission")
        else:
            lines.append("❌ AliExpress: No data available")

        # CJ Dropshipping
        cj_data = data_sources.get("cj_dropshipping", {})
        if "cj_dropshipping" in sources_validated or cj_data.get("available"):
            warehouse = cj_data.get("warehouse", "CN")
            lines.append(f"✅ CJ Dropshipping: Available ({warehouse} warehouse)")
        else:
            lines.append("❌ CJ Dropshipping: Not available or not connected")

        # Google Trends
        google_data = data_sources.get("google_trends", {})
        if "google_trends" in sources_validated or google_data.get("available"):
            direction = google_data.get("direction", product.get("trend_direction", "stable"))
            lines.append(f"✅ Google Trends: {direction.upper()} trend detected")
        else:
            lines.append("❌ Google Trends: No trend data available")

        # TikTok
        tiktok_data = data_sources.get("tiktok", {})
        if "tiktok" in sources_validated or tiktok_data.get("available"):
            views = tiktok_data.get("views", 0)
            lines.append(f"✅ TikTok: {views:,} views on related content")
        else:
            lines.append("❌ TikTok: No viral data available")

        # Twitter/X
        twitter_data = data_sources.get("x_twitter", {})
        if "twitter" in sources_validated or twitter_data.get("available"):
            sentiment = twitter_data.get("sentiment", "neutral")
            buzz = twitter_data.get("buzz", "low")
            lines.append(f"✅ Twitter/X: {sentiment} sentiment, {buzz} buzz level")
        else:
            lines.append("❌ Twitter/X: No sentiment data available")

        # Reddit
        reddit_data = data_sources.get("reddit", {})
        if "reddit" in sources_validated or reddit_data.get("available"):
            mentions = reddit_data.get("mentions", 0) or product.get("reddit_mentions", 0)
            subreddit = reddit_data.get("subreddit", "unknown")
            lines.append(f"✅ Reddit: {mentions} mentions in r/{subreddit}")
        else:
            lines.append("❌ Reddit: No community data available")

        # Summary
        validated_count = len(sources_validated)
        if validated_count >= 4:
            lines.append(f"\n📊 Data Quality: HIGH ({validated_count}/6 sources validated)")
        elif validated_count >= 2:
            lines.append(f"\n📊 Data Quality: MEDIUM ({validated_count}/6 sources validated)")
        else:
            lines.append(f"\n📊 Data Quality: LOW ({validated_count}/6 sources validated)")

        return "\n".join(lines)

    def _parse_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse Claude's JSON response, handling code blocks."""
        import re
        
        # Step 1: Strip code block markers (```json ... ```)
        cleaned = response.strip()
        
        # Remove ```json or ``` at start
        if cleaned.startswith('```json'):
            cleaned = cleaned[7:]
        elif cleaned.startswith('```'):
            cleaned = cleaned[3:]
        
        # Remove ``` at end
        if cleaned.endswith('```'):
            cleaned = cleaned[:-3]
        
        cleaned = cleaned.strip()
        
        # Step 2: Try direct JSON parse on cleaned response
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
        
        # Step 3: Try to extract JSON object from cleaned response
        json_match = re.search(r'\{[\s\S]*\}', cleaned)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        # Step 4: Try original response (maybe we over-stripped)
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        logger.error(f"Could not parse response: {response[:200]}...")
        return None
    
    async def analyze_batch(
        self,
        products: List[Dict[str, Any]],
        store_context: Optional[Dict[str, Any]] = None,
        max_concurrent: int = 3
    ) -> List[COOAnalysis]:
        """
        Analyze multiple products in parallel.
        
        Args:
            products: List of validated products
            store_context: Store information
            max_concurrent: Max parallel analyses
            
        Returns:
            List of COOAnalysis results
        """
        if not self.is_available():
            return []
        
        results = []
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def analyze_with_limit(product):
            async with semaphore:
                return await self.analyze_product(product, store_context)
        
        tasks = [analyze_with_limit(p) for p in products]
        analyses = await asyncio.gather(*tasks, return_exceptions=True)
        
        for analysis in analyses:
            if isinstance(analysis, COOAnalysis):
                results.append(analysis)
            elif isinstance(analysis, Exception):
                logger.error(f"Analysis failed: {analysis}")
        
        return results
    
    async def get_strategic_summary(
        self,
        analyses: List[COOAnalysis],
        store_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate a strategic summary across all analyzed products.
        
        This is what a COO would present in a weekly meeting.
        """
        if not analyses:
            return "No products analyzed yet."
        
        # Categorize products
        deploy_now = [a for a in analyses if a.recommendation == "DEPLOY_NOW"]
        deploy_soon = [a for a in analyses if a.recommendation == "DEPLOY_SOON"]
        monitor = [a for a in analyses if a.recommendation == "MONITOR"]
        skip = [a for a in analyses if a.recommendation == "SKIP"]
        
        # Build summary
        lines = [
            "=" * 60,
            "[STATS] STRATEGIC PRODUCT ANALYSIS SUMMARY",
            "=" * 60,
            f"\nAnalyzed: {len(analyses)} products",
            f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            "",
        ]
        
        if deploy_now:
            lines.append("[HOT] DEPLOY NOW (Urgent Opportunities)")
            lines.append("-" * 40)
            for a in deploy_now[:5]:
                lines.append(f"  • {a.product_name[:40]}")
                lines.append(f"    Score: {a.ospra_score}/10 | Est. Profit: ${a.estimated_monthly_profit:.0f}/mo")
                lines.append(f"    Window: {a.first_mover_window_days} days | {a.executive_summary[:100]}...")
            lines.append("")
        
        if deploy_soon:
            lines.append("[SUCCESS] DEPLOY SOON (Strong Opportunities)")
            lines.append("-" * 40)
            for a in deploy_soon[:5]:
                lines.append(f"  • {a.product_name[:40]} - Score: {a.ospra_score}/10")
            lines.append("")
        
        if monitor:
            lines.append(f" MONITOR ({len(monitor)} products)")
            lines.append("-" * 40)
            lines.append(f"  {len(monitor)} products worth watching but not ready for deployment")
            lines.append("")
        
        if skip:
            lines.append(f"[ERROR] SKIP ({len(skip)} products)")
            lines.append("-" * 40)
            lines.append(f"  {len(skip)} products not recommended at this time")
            lines.append("")
        
        # Key insights
        lines.append("[TIP] KEY INSIGHTS")
        lines.append("-" * 40)
        
        # Best niche
        niche_scores = {}
        for a in analyses:
            if a.niche not in niche_scores:
                niche_scores[a.niche] = []
            niche_scores[a.niche].append(a.ospra_score)
        
        if niche_scores:
            best_niche = max(niche_scores.keys(), key=lambda n: sum(niche_scores[n])/len(niche_scores[n]))
            avg_score = sum(niche_scores[best_niche]) / len(niche_scores[best_niche])
            lines.append(f"  Best performing niche: {best_niche} (avg score: {avg_score:.1f}/10)")
        
        # Total potential
        total_profit = sum(a.estimated_monthly_profit for a in deploy_now + deploy_soon)
        lines.append(f"  Total monthly profit potential: ${total_profit:,.0f}")
        
        # Urgency
        critical = len([a for a in analyses if a.urgency == "CRITICAL"])
        if critical > 0:
            lines.append(f"  [WARNING] {critical} products require immediate action")
        
        lines.append("")
        lines.append("=" * 60)
        
        return "\n".join(lines)


# ============================================================================
# SINGLETON AND CONVENIENCE FUNCTIONS
# ============================================================================

_analyzer_instance: Optional[AIProductAnalyzer] = None


def get_product_analyzer() -> AIProductAnalyzer:
    """Get or create the product analyzer singleton."""
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = AIProductAnalyzer()
    return _analyzer_instance


async def analyze_product(product: Dict[str, Any], store_context: Optional[Dict] = None) -> Optional[COOAnalysis]:
    """Quick function to analyze a single product."""
    analyzer = get_product_analyzer()
    return await analyzer.analyze_product(product, store_context)


async def analyze_products(products: List[Dict[str, Any]], store_context: Optional[Dict] = None) -> List[COOAnalysis]:
    """Quick function to analyze multiple products."""
    analyzer = get_product_analyzer()
    return await analyzer.analyze_batch(products, store_context)


# ============================================================================
# TEST
# ============================================================================

async def test_analyzer():
    """Test the AI Product Analyzer."""
    print("\n" + "=" * 70)
    print("[TEST] TESTING AI PRODUCT ANALYZER")
    print("=" * 70)
    
    analyzer = AIProductAnalyzer()
    
    if not analyzer.is_available():
        print("[ERROR] Analyzer not available - check ANTHROPIC_API_KEY")
        return
    
    # Test product
    test_product = {
        "id": "test_123",
        "name": "WiFi Smart Plug with Energy Monitor - Tuya Compatible",
        "niche": "smart_home",
        "cost": 6.50,
        "selling_price": 18.99,
        "profit": 9.50,
        "profit_margin": 50.0,
        "score": 8.5,
        "ospra_score": 8.5,
        "confidence": 78,
        "trend_direction": "rising",
        "orders": 15000,
        "rating": 4.6,
        "sources_validated": ["aliexpress", "google_trends", "twitter", "tiktok"],
        "score_breakdown": {
            "google_trends": 82,
            "tiktok_viral": 75,
            "twitter_sentiment": 68,
            "aliexpress_orders": 85,
            "amazon_rank": 60,
            "reddit_sentiment": 55,
            "supplier_rating": 92,
        },
        "social_proof": {
            "twitter_mentions": 234,
            "reddit_mentions": 45,
            "tiktok_views": 1500000,
        }
    }
    
    store_context = {
        "store_name": "Oubon Shop",
        "niche": "smart_home",
        "best_sellers": "LED Strip Lights, Smart Doorbell, WiFi Camera",
        "avg_order_value": 32.50,
        "conversion_rate": 2.4,
    }
    
    print(f"\n[PACKAGE] Analyzing: {test_product['name'][:50]}...")
    
    analysis = await analyzer.analyze_product(test_product, store_context)
    
    if analysis:
        print(f"\n[SUCCESS] ANALYSIS COMPLETE")
        print("-" * 50)
        print(f"[LIST] Executive Summary:\n{analysis.executive_summary}\n")
        print(f"[ALARM] Market Timing:\n{analysis.market_timing_analysis}\n")
        print(f"[TOP] Competition:\n{analysis.competitive_position}\n")
        print(f"[TARGET] Store Fit:\n{analysis.store_fit_analysis}\n")
        print(f"[PRICE] Profit Strategy:\n{analysis.profit_strategy}\n")
        print(f"[WARNING] Risks:\n{analysis.risk_assessment}\n")
        print(f"[NOTE] Execution Plan:\n{analysis.execution_plan}\n")
        print("-" * 50)
        print(f"[START] Recommendation: {analysis.recommendation}")
        print(f"[FAST] Urgency: {analysis.urgency}")
        print(f"[MONEY] Est. Monthly Profit: ${analysis.estimated_monthly_profit:.0f}")
        print(f"[STATS] Competition Level: {analysis.competition_level}")
        print(f"[TREND] Trend Stage: {analysis.trend_stage}")
        print(f"⏳ First Mover Window: {analysis.first_mover_window_days} days")
        print(f"\n[SUCCESS] Immediate Actions:")
        for action in analysis.immediate_actions:
            print(f"   • {action}")
    else:
        print("[ERROR] Analysis failed")
    
    return analysis


if __name__ == "__main__":
    asyncio.run(test_analyzer())
