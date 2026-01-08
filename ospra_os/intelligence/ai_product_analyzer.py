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

Author: OspraOS
Date: December 2024
"""

import os
import json
import asyncio
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime

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
    
    # Metadata
    analyzed_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    analysis_version: str = "v1.0"
    
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
            "analyzed_at": self.analyzed_at,
            "analysis_version": self.analysis_version,
        }


class AIProductAnalyzer:
    """
    Claude-powered product analyzer for COO-level insights.
    
    This transforms raw scores into actionable business intelligence.
    """
    
    # Analysis prompt template
    COO_ANALYSIS_PROMPT = """You are a veteran e-commerce COO with 15+ years experience in dropshipping, 
market analysis, and scaling online stores. You're analyzing a product opportunity for deployment.

## PRODUCT DATA
Name: {product_name}
Niche: {niche}
Supplier Cost: ${cost:.2f}
Suggested Retail: ${selling_price:.2f}
Profit per Sale: ${profit:.2f}
Profit Margin: {margin:.1f}%

## CROSS-REFERENCED SCORES (0-100 scale)
- Google Trends Score: {google_score}/100 (Trend Direction: {trend_direction})
- TikTok Viral Score: {tiktok_score}/100
- Twitter/X Sentiment: {twitter_score}/100 ({twitter_mentions} mentions)
- AliExpress Orders Score: {order_score}/100 ({orders:,} orders)
- Amazon Rank Score: {amazon_score}/100
- Reddit Sentiment: {reddit_score}/100 ({reddit_mentions} mentions)
- Supplier Rating: {supplier_score}/100 ({rating})

## COMPOSITE SCORE
OSPRA Score: {ospra_score}/10
Confidence: {confidence}%
Sources Validated: {sources_count} ({sources_list})

## STORE CONTEXT
Store Name: {store_name}
Store Niche Focus: {store_niche}
Previous Best Sellers: {best_sellers}
Average Order Value: ${aov:.2f}
Historical Conversion Rate: {conversion_rate:.2f}%

## YOUR TASK
Provide a comprehensive COO-level analysis. Be specific, actionable, and data-driven.
Don't hedge - make clear recommendations based on the data.

Respond in this EXACT JSON format:
{{
    "executive_summary": "2-3 sentence overview of the opportunity",
    "market_timing_analysis": "Detailed analysis of WHY NOW. Include trend velocity, market stage, and window of opportunity.",
    "competitive_position": "Analysis of competition level, saturation risk, and differentiation strategy",
    "store_fit_analysis": "Why this product fits (or doesn't fit) THIS specific store",
    "profit_strategy": "Specific pricing recommendation with rationale. Include competitor pricing context.",
    "risk_assessment": "Top 3 risks and how to mitigate each",
    "execution_plan": "Step-by-step plan if deploying (or what to monitor if waiting)",
    "recommendation": "DEPLOY_NOW | DEPLOY_SOON | MONITOR | SKIP",
    "urgency": "CRITICAL | HIGH | MEDIUM | LOW",
    "confidence_level": "HIGH | MEDIUM | LOW",
    "estimated_monthly_profit": <number>,
    "suggested_price": <number>,
    "competition_level": "LOW | MEDIUM | HIGH | SATURATED",
    "trend_stage": "EMERGING | GROWING | PEAK | DECLINING",
    "first_mover_window_days": <number>,
    "immediate_actions": ["action 1", "action 2", "action 3"],
    "watch_triggers": ["trigger that would change recommendation 1", "trigger 2"]
}}

Be a COO, not a chatbot. Make the call."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize with Claude API key."""
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.ai_provider = None
        self._initialized = False
        
        if not AI_AVAILABLE:
            logger.error("AI Factory not available - cannot initialize analyzer")
            return
            
        if not self.api_key:
            logger.error("ANTHROPIC_API_KEY not set - cannot initialize analyzer")
            return
        
        try:
            self.ai_provider = AIFactory.get_provider("claude", self.api_key)
            self._initialized = True
            logger.info("[SUCCESS] AI Product Analyzer initialized with Claude")
        except Exception as e:
            logger.error(f"Failed to initialize Claude: {e}")
    
    def is_available(self) -> bool:
        """Check if analyzer is ready."""
        return self._initialized and self.ai_provider is not None
    
    async def analyze_product(
        self,
        product: Dict[str, Any],
        store_context: Optional[Dict[str, Any]] = None
    ) -> Optional[COOAnalysis]:
        """
        Generate COO-level analysis for a product.
        
        Args:
            product: Validated product from discovery engine
            store_context: Information about the user's store
            
        Returns:
            COOAnalysis with comprehensive strategic assessment
        """
        if not self.is_available():
            logger.error("Analyzer not available")
            return None
        
        # Extract product data
        product_name = product.get("name", "Unknown Product")
        niche = product.get("niche", "general")
        
        # Pricing
        cost = float(product.get("cost", 0))
        selling_price = float(product.get("selling_price", product.get("price", 0)))
        profit = float(product.get("profit", selling_price - cost))
        margin = float(product.get("profit_margin", (profit / selling_price * 100) if selling_price > 0 else 0))
        
        # Scores
        score_breakdown = product.get("score_breakdown", {})
        google_score = score_breakdown.get("google_trends", 50)
        tiktok_score = score_breakdown.get("tiktok_viral", 50)
        twitter_score = score_breakdown.get("twitter_sentiment", 50)
        order_score = score_breakdown.get("aliexpress_orders", 50)
        amazon_score = score_breakdown.get("amazon_rank", 50)
        reddit_score = score_breakdown.get("reddit_sentiment", 50)
        supplier_score = score_breakdown.get("supplier_rating", 50)
        
        # Social proof
        social_proof = product.get("social_proof", {})
        twitter_mentions = social_proof.get("twitter_mentions", 0)
        reddit_mentions = social_proof.get("reddit_mentions", 0)
        
        # Other metrics
        orders = int(product.get("orders", 0))
        rating = float(product.get("rating", 4.0))
        ospra_score = float(product.get("score", product.get("ospra_score", 0)))
        confidence = float(product.get("confidence", 50))
        trend_direction = product.get("trend_direction", "stable")
        sources_validated = product.get("sources_validated", [])
        
        # Store context (defaults if not provided)
        store_context = store_context or {}
        store_name = store_context.get("store_name", "Your Store")
        store_niche = store_context.get("niche", niche)
        best_sellers = store_context.get("best_sellers", "Not enough data yet")
        aov = float(store_context.get("avg_order_value", 35.00))
        conversion_rate = float(store_context.get("conversion_rate", 2.0))
        
        # Build prompt
        prompt = self.COO_ANALYSIS_PROMPT.format(
            product_name=product_name,
            niche=niche,
            cost=cost,
            selling_price=selling_price,
            profit=profit,
            margin=margin,
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
            trend_direction=trend_direction,
            ospra_score=ospra_score,
            confidence=confidence,
            sources_count=len(sources_validated),
            sources_list=", ".join(sources_validated),
            store_name=store_name,
            store_niche=store_niche,
            best_sellers=best_sellers,
            aov=aov,
            conversion_rate=conversion_rate,
        )
        
        try:
            logger.info(f"[BRAIN] Analyzing: {product_name[:50]}...")
            
            # Call Claude
            response = await self.ai_provider.chat(
                message=prompt,
                context={"system_prompt": "You are a veteran e-commerce COO. Respond only with valid JSON."}
            )
            
            # Parse response
            analysis_data = self._parse_response(response)
            
            if not analysis_data:
                logger.error(f"Failed to parse Claude response for {product_name}")
                return None
            
            # Build COOAnalysis
            return COOAnalysis(
                product_id=product.get("id", ""),
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
            )
            
        except Exception as e:
            logger.error(f"Claude analysis failed: {e}")
            return None
    
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
