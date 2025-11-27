"""
AI-Powered Product Analyst
Generates UNIQUE, detailed analysis for each product using Claude
NO TEMPLATES - Each product gets custom intelligence
"""

import os
import logging
from typing import Dict
from anthropic import Anthropic

logger = logging.getLogger(__name__)


class AIProductAnalyst:
    """
    Uses Claude to generate unique, thorough product analysis
    Incorporates all available data: sales, trends, social proof, market signals
    """

    def __init__(self):
        api_key = os.getenv('ANTHROPIC_API_KEY') or os.getenv('CLAUDE_API_KEY')

        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY or CLAUDE_API_KEY required for AI analysis")

        self.claude = Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-5-20250929"  # Latest Sonnet 4.5 - Superior analysis

        logger.info(f"✅ AI Analyst initialized with model: {self.model}")

    async def generate_unique_analysis(
        self,
        product: Dict,
        trend_data: Dict,
        niche: str
    ) -> str:
        """
        Generate UNIQUE, detailed analysis for this specific product

        Returns: Comprehensive markdown analysis with:
        - Sales performance metrics
        - Trend analysis (Google Trends momentum)
        - Profit calculations
        - Market opportunity assessment
        - Risk factors specific to this product
        - Custom recommendation with unique angle
        """

        # Build comprehensive context for Claude
        context = self._build_analysis_context(product, trend_data, niche)

        # Generate unique analysis
        try:
            message = self.claude.messages.create(
                model=self.model,
                max_tokens=1500,  # Long detailed response
                temperature=0.7,  # Some creativity, but grounded
                messages=[{
                    "role": "user",
                    "content": self._create_analysis_prompt(context)
                }]
            )

            analysis = message.content[0].text
            logger.info(f"✅ Generated unique analysis for: {product.get('name', 'unknown')[:50]}...")

            return analysis

        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            # Return detailed fallback
            return self._create_detailed_fallback(product, trend_data)

    def _build_analysis_context(self, product: Dict, trend_data: Dict, niche: str) -> Dict:
        """
        Build comprehensive context for AI analysis
        """
        # Extract data
        aliexpress = trend_data.get('aliexpress_metrics', {})
        market = trend_data.get('market_signals', {})
        google = trend_data.get('google_trends', {})

        return {
            # Product basics
            'name': product.get('name', 'Unknown'),
            'niche': niche,
            'score': product.get('score', 0),
            'priority': product.get('priority', 'UNKNOWN'),

            # 🎯 MULTI-SOURCE DISCOVERY DATA (NEW - QUAD PRIMARY SOURCE)
            'source_count': product.get('source_count', 0),
            'primary_sources': product.get('primary_sources', []),
            'multi_source_validated': product.get('source_count', 0) >= 2,

            # Platform-specific scores
            'platform_scores': product.get('platform_scores', {}),

            # TikTok Shop data
            'tiktok_sales': product.get('tiktok_sales', 0),
            'tiktok_sales_7d': product.get('tiktok_sales_7d', 0),
            'tiktok_price': product.get('tiktok_price', 0),
            'tiktok_shop_url': product.get('tiktok_shop_url', ''),

            # Amazon data
            'amazon_bestseller': product.get('amazon_bestseller', False),
            'amazon_rank': product.get('amazon_rank', 0),
            'amazon_category': product.get('amazon_category', ''),
            'amazon_rating': product.get('amazon_rating', 0),
            'amazon_reviews': product.get('amazon_reviews', 0),
            'amazon_price': product.get('amazon_price', 0),

            # Shopify Competitor data
            'shopify_competitor': product.get('shopify_competitor', False),
            'shopify_price': product.get('shopify_price', 0),
            'shopify_store_url': product.get('shopify_store_url', ''),
            'shopify_store_name': product.get('shopify_store_name', ''),

            # Pricing & profit
            'supplier_cost': product.get('price', 0),
            'market_price': round(product.get('price', 0) * 3, 2),
            'profit_margin': round(((3 - 1) / 3) * 100, 1),
            'profit_per_sale': round(product.get('price', 0) * 2, 2),

            # Sales data (AliExpress)
            'total_orders': aliexpress.get('total_orders', 0),
            'rating': product.get('rating', 0),
            'daily_orders_estimate': aliexpress.get('estimated_daily_orders', 0),
            'monthly_orders_estimate': aliexpress.get('monthly_orders_estimate', 0),
            'monthly_revenue_estimate': aliexpress.get('revenue_estimate_monthly', 0),

            # Market signals
            'competition': market.get('competition_level', 'UNKNOWN'),
            'saturation': market.get('saturation_level', 'UNKNOWN'),
            'demand': market.get('demand_strength', 'UNKNOWN'),
            'opportunity': market.get('overall_opportunity', 'UNKNOWN'),

            # Trends
            'google_trend_available': google.get('available', False),
            'trend_direction': google.get('trend_direction', 'UNKNOWN'),
            'momentum_percent': google.get('primary_momentum', 0),
            'search_keywords': google.get('keywords', []),

            # Quality indicators
            'supplier_rating': product.get('supplier_rating', 0),
            'shipping_days': product.get('shipping_days', 0),
            'store_name': product.get('store_name', 'Unknown'),

            # Score breakdown
            'score_breakdown': product.get('score_breakdown', {})
        }

    def _create_analysis_prompt(self, context: Dict) -> str:
        """
        Create detailed prompt for Claude to generate unique analysis
        """
        # Build multi-source validation section
        source_count = context.get('source_count', 0)
        primary_sources = context.get('primary_sources', [])
        multi_validated = context.get('multi_source_validated', False)

        source_names = {
            'tiktok_shop': 'TikTok Shop',
            'amazon_bestsellers': 'Amazon Bestsellers',
            'shopify_competitors': 'Shopify Competitors',
            'google_trends': 'Google Trends'
        }

        sources_list = ', '.join([source_names.get(s, s) for s in primary_sources]) if primary_sources else 'Single source'

        validation_status = ""
        if source_count >= 4:
            validation_status = "🎯 JACKPOT! Found in ALL 4 primary sources"
        elif source_count == 3:
            validation_status = "🔥 HIGHLY VALIDATED - Found in 3 primary sources"
        elif source_count == 2:
            validation_status = "⭐ CROSS-VALIDATED - Found in 2 primary sources"
        else:
            validation_status = "📍 Single source discovery"

        # Build platform-specific data sections
        platform_scores = context.get('platform_scores', {})

        tiktok_section = ""
        if context.get('tiktok_sales', 0) > 0:
            tiktok_section = f"""
🎵 TIKTOK SHOP PERFORMANCE:
- Total Sales: {context['tiktok_sales']:,}
- Sales (7 days): {context['tiktok_sales_7d']:,}
- TikTok Price: ${context['tiktok_price']}
- Platform Score: {platform_scores.get('tiktok_shop_score', 0)}/100
"""

        amazon_section = ""
        if context.get('amazon_bestseller', False):
            amazon_section = f"""
📦 AMAZON BESTSELLER DATA:
- Bestseller Rank: #{context['amazon_rank']} in {context['amazon_category']}
- Customer Rating: {context['amazon_rating']}/5.0 ({context['amazon_reviews']:,} reviews)
- Amazon Price: ${context['amazon_price']}
- Platform Score: {platform_scores.get('amazon_score', 0)}/100
"""

        shopify_section = ""
        if context.get('shopify_competitor', False):
            shopify_section = f"""
🏪 SHOPIFY COMPETITOR INTELLIGENCE:
- Found in successful store: {context['shopify_store_name']}
- Competitor Price: ${context['shopify_price']}
- Store URL: {context['shopify_store_url']}
- Platform Score: {platform_scores.get('shopify_score', 0)}/100
"""

        return f"""You are an expert e-commerce product analyst. Analyze this product opportunity and provide a comprehensive, unique recommendation.

PRODUCT DETAILS:
- Name: {context['name']}
- Niche: {context['niche']}
- Overall Score: {context['score']}/10
- Priority Level: {context['priority']}

🎯 MULTI-SOURCE DISCOVERY VALIDATION:
- {validation_status}
- Discovery Sources: {sources_list} ({source_count} source{'s' if source_count != 1 else ''})
- Multi-Source Bonus: +{platform_scores.get('multi_source_bonus', 0)} points
{tiktok_section}{amazon_section}{shopify_section}
FINANCIAL METRICS:
- Supplier Cost: ${context['supplier_cost']}
- Recommended Retail: ${context['market_price']}
- Profit per Sale: ${context['profit_per_sale']}
- Profit Margin: {context['profit_margin']}%

SALES PERFORMANCE:
- Total Orders on AliExpress: {context['total_orders']:,}
- Customer Rating: {context['rating']}/5.0 stars
- Estimated Daily Orders: {context['daily_orders_estimate']}
- Estimated Monthly Orders: {context['monthly_orders_estimate']}
- Estimated Monthly Revenue: ${context['monthly_revenue_estimate']:,.2f}

MARKET ANALYSIS:
- Competition Level: {context['competition']}
- Market Saturation: {context['saturation']}
- Demand Strength: {context['demand']}
- Overall Opportunity: {context['opportunity']}

TREND ANALYSIS:
- Google Trends Available: {context['google_trend_available']}
- Trend Direction: {context['trend_direction']}
- Search Momentum: {context['momentum_percent']:+.1f}%
- Key Search Terms: {', '.join(context['search_keywords'])}

SUPPLIER QUALITY:
- Supplier Rating: {context['supplier_rating']}/100
- Shipping Time: {context['shipping_days']} days
- Store: {context['store_name']}

PERFORMANCE SCORES:
- Sales Performance: {context['score_breakdown'].get('sales_performance', 0)}/10
- Customer Sentiment: {context['score_breakdown'].get('customer_sentiment', 0)}/10
- Profit Potential: {context['score_breakdown'].get('profit_potential', 0)}/10
- Market Opportunity: {context['score_breakdown'].get('market_opportunity', 0)}/10
- Trending Factor: {context['score_breakdown'].get('trending_factor', 0)}/10

INSTRUCTIONS:
Generate a detailed, unique analysis in markdown format. Include:

1. **Opening Assessment** (2-3 sentences)
   - Quick verdict: Should they add this product?
   - Why this specific product stands out (be specific to THIS product)
   - EMPHASIZE multi-source validation if product found in 2+ sources

2. **🎯 Multi-Source Validation Analysis** (CRITICAL - NEW SECTION)
   - Analyze what it means that this product was found in {source_count} primary source(s)
   - If found in multiple sources: explain the significance of cross-platform validation
   - If JACKPOT (4 sources): This is EXTREMELY rare and valuable - explain why
   - Compare TikTok sales vs Amazon rank vs Shopify competitor presence
   - What does cross-platform demand tell us about product viability?
   - Does pricing differ across platforms? What does that mean?

3. **📈 Sales & Performance Analysis**
   - Interpret ALL sales numbers from ALL sources (TikTok, Amazon, AliExpress)
   - Calculate realistic profit projections using actual platform data
   - Analyze the velocity and demand pattern across platforms
   - Compare to typical products in this niche
   - If TikTok sales exist: what does social commerce performance indicate?
   - If Amazon bestseller: what does traditional e-commerce rank mean?

4. **🎯 Market Opportunity**
   - Is the market saturated or is there room?
   - What's the competitive landscape?
   - Specific angles to differentiate this product
   - Target audience insights

4. **📊 Trend Intelligence**
   - What do the Google Trends tell us?
   - Is momentum building or fading?
   - Seasonal considerations for THIS specific product
   - Timing recommendations (launch now vs wait)

5. **💰 Profit Strategy**
   - Specific pricing recommendation with reasoning
   - Volume projections (conservative estimate)
   - Monthly profit potential
   - Break-even analysis

6. **⚠️ Risk Assessment**
   - Specific risks for THIS product (not generic)
   - Shipping time concerns
   - Competition challenges
   - Quality/supplier concerns
   - Mitigation strategies

7. **✅ Final Recommendation**
   - Clear ADD/SKIP/MAYBE verdict
   - Unique selling angle for this product
   - Marketing approach (be specific)
   - Who should buy this from your store?

CRITICAL: Make this analysis UNIQUE to this product. Reference specific numbers, trends, and characteristics. Avoid generic advice. Be direct, insightful, and actionable.

Use emojis sparingly for visual hierarchy. Keep it professional yet engaging."""

    def _create_detailed_fallback(self, product: Dict, trend_data: Dict) -> str:
        """
        Detailed fallback if AI fails (still product-specific, not template)
        """
        name = product.get('name', 'Unknown Product')
        orders = trend_data.get('aliexpress_metrics', {}).get('total_orders', 0)
        rating = product.get('rating', 0)
        price = product.get('price', 0)
        score = product.get('score', 0)

        profit = round(price * 2, 2)
        market_price = round(price * 3, 2)

        competition = trend_data.get('market_signals', {}).get('competition_level', 'MEDIUM')
        demand = trend_data.get('market_signals', {}).get('demand_strength', 'MEDIUM')

        # Multi-source validation info
        source_count = product.get('source_count', 0)
        primary_sources = product.get('primary_sources', [])
        tiktok_sales = product.get('tiktok_sales', 0)
        amazon_bestseller = product.get('amazon_bestseller', False)
        amazon_rank = product.get('amazon_rank', 0)
        shopify_competitor = product.get('shopify_competitor', False)

        validation_badge = ""
        if source_count >= 4:
            validation_badge = "🎯 JACKPOT! Found in ALL 4 primary sources"
        elif source_count == 3:
            validation_badge = "🔥 HIGHLY VALIDATED - Found in 3 primary sources"
        elif source_count == 2:
            validation_badge = "⭐ CROSS-VALIDATED - Found in 2 primary sources"

        multi_source_section = ""
        if source_count >= 2:
            sources_display = ', '.join(primary_sources)
            multi_source_section = f"""
### 🎯 Multi-Source Validation

**{validation_badge}**

This product was discovered independently by **{source_count} primary sources**: {sources_display}

Cross-platform validation significantly increases confidence in product viability.
"""

        platform_data = ""
        if tiktok_sales > 0:
            platform_data += f"\n- **TikTok Shop**: {tiktok_sales:,} sales"
        if amazon_bestseller:
            platform_data += f"\n- **Amazon**: Bestseller Rank #{amazon_rank}"
        if shopify_competitor:
            platform_data += f"\n- **Shopify**: Found in successful competitor store"

        return f"""## {name}

**Score: {score}/10** | **Priority: {'HIGH' if score > 7.5 else 'MEDIUM' if score > 6 else 'LOW'}**
{multi_source_section}
### 📈 Sales Performance
{platform_data}

This product has achieved **{orders:,} orders** on AliExpress with a **{rating}/5.0** rating.

Estimated velocity: ~{round(orders/365, 1)} orders/day, suggesting {round(orders/365 * 30)} monthly sales at current pace.

### 💰 Profit Analysis

- **Cost**: ${price}
- **Recommended Price**: ${market_price}
- **Profit per Sale**: ${profit}
- **Margin**: {round((profit/market_price)*100, 1)}%

At 500 monthly sales (conservative), estimated profit: **${round(profit * 500):,}/month**

### 🎯 Market Assessment

- **Competition**: {competition}
- **Demand**: {demand}
- **Opportunity**: {'Strong' if score > 7.5 else 'Moderate' if score > 6 else 'Limited'}

### ⚠️ Considerations

- Shipping time: {product.get('shipping_days', 15)} days (manage customer expectations)
- Competition level is {competition.lower()} - {
    'differentiation required' if competition == 'HIGH' else
    'good opportunity' if competition == 'LOW' else
    'moderate effort needed'}
- {'High' if rating > 4.5 else 'Good' if rating > 4.0 else 'Acceptable'} customer satisfaction

### ✅ Recommendation

{'**ADD TO STORE** - Strong fundamentals with proven demand' if score > 7.5 else
 '**CONSIDER** - Decent opportunity, test with small inventory' if score > 6 else
 '**SKIP** - Better opportunities available'}

{'Focus on unique marketing angle to stand out in competitive market.' if competition == 'HIGH' else
 'Good opportunity for early movers in this niche.' if competition == 'LOW' else
 'Solid product for established stores with marketing capabilities.'}
"""
