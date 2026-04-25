"""
Smart Context Builder for Claude
=================================

Builds optimal context for Claude based on:
1. Always include: Latest summary (warm memory)
2. Query-relevant: Retrieve specific data based on question
3. Token budget: Stay under 4000 tokens for context

This enables unlimited memory without hitting token limits.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from ospra_os.database import SessionLocal
from ospra_os.learning.summary_models import (
    LearningSummary,
    NichePerformance,
    ProductPerformance,
    TimeSeriesMetrics
)
from ospra_os.learning.hybrid_learning_engine import LearningEvent


def parse_query_intent(user_query: str) -> Dict[str, Any]:
    """
    Parse user query to determine what context to retrieve.

    Returns:
        {
            'topics': ['ads', 'tiktok', 'products', 'niches', 'revenue'],
            'timeframe': 'last_month' | 'last_week' | 'all_time',
            'products': ['prod_123', 'prod_456'],
            'niches': ['smart_home', 'fitness'],
            'scope': 'overview' | 'detailed' | 'specific'
        }
    """
    query_lower = user_query.lower()

    intent = {
        'topics': [],
        'timeframe': 'all_time',
        'products': [],
        'niches': [],
        'scope': 'overview'
    }

    # Detect topics
    topic_keywords = {
        'ads': ['ad', 'advertisement', 'roas', 'campaign', 'facebook', 'tiktok', 'google ads', 'meta'],
        'products': ['product', 'item', 'selling', 'inventory'],
        'niches': ['niche', 'category', 'vertical'],
        'revenue': ['revenue', 'sales', 'money', 'profit', 'income', 'earnings'],
        'performance': ['performance', 'metrics', 'stats', 'analytics'],
        'trends': ['trend', 'pattern', 'growth', 'decline'],
        'recommendations': ['recommend', 'suggest', 'should i', 'what to sell', 'advice']
    }

    for topic, keywords in topic_keywords.items():
        if any(keyword in query_lower for keyword in keywords):
            intent['topics'].append(topic)

    # Detect timeframe
    if any(word in query_lower for word in ['today', 'yesterday']):
        intent['timeframe'] = 'last_day'
    elif any(word in query_lower for word in ['this week', 'last week', 'past week']):
        intent['timeframe'] = 'last_week'
    elif any(word in query_lower for word in ['this month', 'last month', 'past month']):
        intent['timeframe'] = 'last_month'
    elif any(word in query_lower for word in ['this year', 'last year']):
        intent['timeframe'] = 'last_year'

    # Detect scope
    if any(word in query_lower for word in ['complete', 'full', 'comprehensive', 'detailed', 'everything']):
        intent['scope'] = 'detailed'
    elif any(word in query_lower for word in ['specific', 'particular', 'just']):
        intent['scope'] = 'specific'

    # Detect specific niches mentioned
    known_niches = ['smart_home', 'fitness', 'kitchen', 'beauty', 'tech', 'home', 'outdoor', 'fashion']
    for niche in known_niches:
        niche_variants = [niche, niche.replace('_', ' '), niche.replace('_', '-')]
        if any(variant in query_lower for variant in niche_variants):
            intent['niches'].append(niche)

    return intent


def get_latest_summary(user_id: int, db: Session) -> str:
    """
    Fetch the most recent learning summary for a user.

    Returns formatted markdown string (~800-1000 tokens).
    """
    summary = db.query(LearningSummary).filter_by(user_id=user_id).order_by(
        desc(LearningSummary.summary_date)
    ).first()

    if not summary:
        return "No learning data available yet. Deploy products and make sales to start learning."

    overall = summary.overall_performance
    niches = summary.niche_insights

    # Format as markdown
    context = f"""**Your Business Overview** (as of {summary.summary_date.strftime('%Y-%m-%d')})

[STATS] **Overall Performance:**
- Total Revenue: ${overall.get('total_revenue', 0):,.2f}
- Products Deployed: {overall.get('total_products_deployed', 0)}
- Total Sales: {overall.get('total_sales', 0)}
- Avg Revenue per Product: ${overall.get('avg_revenue_per_product', 0):.2f}
- Best Month: {overall.get('best_month', 'N/A')}

[TARGET] **Niche Performance:**
"""

    # Add top 3 niches
    sorted_niches = sorted(niches.items(), key=lambda x: x[1].get('revenue', 0), reverse=True)
    for niche, data in sorted_niches[:3]:
        context += f"- **{niche}**: ${data.get('revenue', 0):,.2f} revenue, {data.get('success_rate', 0)*100:.0f}% success rate, avg ${data.get('avg_price', 0):.2f} price\n"

    # Add price insights
    price_data = summary.price_insights
    if price_data and price_data.get('optimal_range'):
        context += f"\n[PRICE] **Optimal Price Range:** {price_data['optimal_range']}\n"

    # Add ad insights if available
    ad_data = summary.ad_insights
    if ad_data and ad_data.get('best_platform'):
        context += f"\n[MOBILE] **Ad Performance:**\n"
        context += f"- Best Platform: {ad_data['best_platform']}\n"
        context += f"- Average ROAS: {ad_data.get('avg_roas', 0):.2f}x\n"

    # Add AI recommendations
    if summary.recommendations:
        context += f"\n[NEW] **AI Recommendations:**\n{summary.recommendations}\n"

    return context


def get_ad_performance(user_id: int, timeframe: str, db: Session) -> str:
    """
    Fetch detailed ad performance data.

    Returns formatted string with ad metrics (~300-500 tokens).
    """
    # Calculate date range
    since_date = _get_timeframe_date(timeframe)

    # Query ad performance events
    ad_events = db.query(LearningEvent).filter(
        LearningEvent.user_id == user_id,
        LearningEvent.event_type == 'ad_performance',
        LearningEvent.created_at >= since_date
    ).all()

    if not ad_events:
        return "No ad performance data available for this timeframe."

    # Aggregate by platform
    platform_stats = {}
    for event in ad_events:
        details = event.details
        platform = details.get('platform', 'unknown')

        if platform not in platform_stats:
            platform_stats[platform] = {
                'spend': 0,
                'revenue': 0,
                'conversions': 0,
                'clicks': 0,
                'impressions': 0
            }

        platform_stats[platform]['spend'] += details.get('spend', 0)
        platform_stats[platform]['revenue'] += details.get('revenue', 0)
        platform_stats[platform]['conversions'] += details.get('conversions', 0)
        platform_stats[platform]['clicks'] += details.get('clicks', 0)
        platform_stats[platform]['impressions'] += details.get('impressions', 0)

    # Format output
    context = f"**Ad Performance** ({timeframe}):\n\n"

    for platform, stats in sorted(platform_stats.items(), key=lambda x: x[1]['revenue'], reverse=True):
        roas = (stats['revenue'] / stats['spend']) if stats['spend'] > 0 else 0
        ctr = (stats['clicks'] / stats['impressions'] * 100) if stats['impressions'] > 0 else 0

        context += f"**{platform.title()}:**\n"
        context += f"- Spend: ${stats['spend']:,.2f}\n"
        context += f"- Revenue: ${stats['revenue']:,.2f}\n"
        context += f"- ROAS: {roas:.2f}x\n"
        context += f"- Conversions: {stats['conversions']}\n"
        context += f"- CTR: {ctr:.2f}%\n\n"

    return context


def get_product_details(product_ids: List[str], user_id: int, db: Session) -> str:
    """
    Fetch detailed performance for specific products.

    Returns formatted string with product metrics (~200-400 tokens).
    """
    if not product_ids:
        # Get top 5 products instead
        top_products = db.query(ProductPerformance).filter_by(
            user_id=user_id
        ).order_by(desc(ProductPerformance.total_revenue)).limit(5).all()

        if not top_products:
            return "No product performance data available."

        context = "**Top Performing Products:**\n\n"
        for product in top_products:
            context += f"**{product.product_name}** ({product.niche}):\n"
            context += f"- Revenue: ${product.total_revenue:,.2f}\n"
            context += f"- Units Sold: {product.total_units_sold}\n"
            context += f"- Avg Price: ${product.avg_price:.2f}\n"
            context += f"- ROI: {product.roi_percentage:.1f}%\n"
            if product.roas > 0:
                context += f"- ROAS: {product.roas:.2f}x\n"
            context += "\n"

        return context

    # Fetch specific products
    products = db.query(ProductPerformance).filter(
        ProductPerformance.user_id == user_id,
        ProductPerformance.product_id.in_(product_ids)
    ).all()

    if not products:
        return f"No data found for products: {', '.join(product_ids)}"

    context = "**Product Details:**\n\n"
    for product in products:
        context += f"**{product.product_name}** (ID: {product.product_id}):\n"
        context += f"- Niche: {product.niche}\n"
        context += f"- Total Revenue: ${product.total_revenue:,.2f}\n"
        context += f"- Units Sold: {product.total_units_sold}\n"
        context += f"- Avg Price: ${product.avg_price:.2f}\n"
        context += f"- ROI: {product.roi_percentage:.1f}%\n"
        context += f"- Deployed: {product.deploy_date.strftime('%Y-%m-%d') if product.deploy_date else 'N/A'}\n"
        context += f"- Last Sale: {product.last_sale_date.strftime('%Y-%m-%d') if product.last_sale_date else 'N/A'}\n\n"

    return context


def get_niche_analysis(user_id: int, db: Session) -> str:
    """
    Fetch comprehensive niche performance analysis.

    Returns formatted string with niche metrics (~400-600 tokens).
    """
    niches = db.query(NichePerformance).filter_by(user_id=user_id).order_by(
        desc(NichePerformance.total_revenue)
    ).all()

    if not niches:
        return "No niche performance data available."

    context = "**Niche Analysis:**\n\n"

    total_revenue = sum(n.total_revenue for n in niches)

    for niche in niches:
        revenue_share = (niche.total_revenue / total_revenue * 100) if total_revenue > 0 else 0

        context += f"**{niche.niche.replace('_', ' ').title()}:**\n"
        context += f"- Revenue: ${niche.total_revenue:,.2f} ({revenue_share:.1f}% of total)\n"
        context += f"- Products: {niche.total_products}\n"
        context += f"- Units Sold: {niche.total_units_sold}\n"
        context += f"- Avg Price: ${niche.avg_price:.2f}\n"
        context += f"- Success Rate: {niche.success_rate*100:.0f}%\n"

        if niche.avg_roas > 0:
            context += f"- Avg ROAS: {niche.avg_roas:.2f}x\n"

        if niche.last_sale_date:
            days_since_sale = (datetime.now(timezone.utc) - niche.last_sale_date).days
            context += f"- Last Sale: {days_since_sale} days ago\n"

        context += "\n"

    return context


def get_time_series_data(user_id: int, period_type: str, db: Session) -> str:
    """
    Fetch time series metrics for trend analysis.

    Args:
        period_type: 'week' or 'month'

    Returns formatted string with trend data (~300-500 tokens).
    """
    # Get last 6 periods
    periods = db.query(TimeSeriesMetrics).filter(
        TimeSeriesMetrics.user_id == user_id,
        TimeSeriesMetrics.period_type == period_type
    ).order_by(desc(TimeSeriesMetrics.period_start)).limit(6).all()

    if not periods:
        return f"No {period_type}ly trend data available."

    periods = list(reversed(periods))  # Chronological order

    context = f"**{period_type.title()}ly Trends:**\n\n"

    for period in periods:
        period_label = period.period_start.strftime('%Y-%m-%d')
        context += f"**{period_label}:**\n"
        context += f"- Revenue: ${period.total_revenue:,.2f}\n"
        context += f"- Units Sold: {period.total_units_sold}\n"
        context += f"- Products Deployed: {period.total_products_deployed}\n"

        if period.avg_roas > 0:
            context += f"- Avg ROAS: {period.avg_roas:.2f}x\n"

        if period.top_niche:
            context += f"- Top Niche: {period.top_niche} (${period.top_niche_revenue:,.2f})\n"

        context += "\n"

    # Calculate growth
    if len(periods) >= 2:
        latest = periods[-1]
        previous = periods[-2]
        growth = ((latest.total_revenue - previous.total_revenue) / previous.total_revenue * 100) if previous.total_revenue > 0 else 0

        context += f"**Growth:** {growth:+.1f}% from previous {period_type}\n"

    return context


def _get_timeframe_date(timeframe: str) -> datetime:
    """Convert timeframe string to datetime."""
    now = datetime.now(timezone.utc)

    if timeframe == 'last_day':
        return now - timedelta(days=1)
    elif timeframe == 'last_week':
        return now - timedelta(weeks=1)
    elif timeframe == 'last_month':
        return now - timedelta(days=30)
    elif timeframe == 'last_year':
        return now - timedelta(days=365)
    else:
        return datetime(2000, 1, 1)  # All time


def estimate_tokens(text: str) -> int:
    """Rough token estimation (1 token ≈ 4 characters)."""
    return len(text) // 4


def combine_within_budget(context_parts: List[str], token_budget: int = 4000) -> str:
    """
    Combine context parts within token budget.

    Priority order:
    1. Latest summary (always include)
    2. Query-specific data
    3. Additional context if space allows
    """
    if not context_parts:
        return ""

    combined = []
    tokens_used = 0

    for part in context_parts:
        part_tokens = estimate_tokens(part)

        if tokens_used + part_tokens <= token_budget:
            combined.append(part)
            tokens_used += part_tokens
        else:
            # Try to include truncated version
            remaining_budget = token_budget - tokens_used
            if remaining_budget > 200:  # Only if we have meaningful space
                chars_available = remaining_budget * 4
                truncated = part[:chars_available] + "\n\n[...truncated due to token limit...]"
                combined.append(truncated)
            break

    result = "\n\n".join(combined)
    result += f"\n\n---\n*Context size: ~{estimate_tokens(result)} tokens*"

    return result


def build_claude_context(user_id: int, user_query: str, db: Session = None) -> str:
    """
    Build optimal context for Claude based on user query.

    This is the main entry point for context generation.

    Args:
        user_id: User ID
        user_query: User's question/request
        db: Database session (optional, will create if not provided)

    Returns:
        Formatted context string optimized for Claude (~4000 tokens max)
    """
    if db is None:
        db = SessionLocal()
        close_db = True
    else:
        close_db = False

    try:
        context_parts = []

        # 1. Always include latest summary (~800-1000 tokens)
        summary = get_latest_summary(user_id, db)
        context_parts.append(summary)

        # 2. Parse query intent
        intent = parse_query_intent(user_query)

        # 3. Retrieve query-relevant data

        # Ads performance
        if 'ads' in intent['topics'] or 'performance' in intent['topics']:
            ad_data = get_ad_performance(user_id, intent['timeframe'], db)
            context_parts.append(ad_data)

        # Niche analysis
        if 'niches' in intent['topics'] or intent['niches'] or 'niche' in user_query.lower():
            niche_data = get_niche_analysis(user_id, db)
            context_parts.append(niche_data)

        # Product details
        if 'products' in intent['topics'] or intent['scope'] == 'detailed':
            product_data = get_product_details(intent['products'], user_id, db)
            context_parts.append(product_data)

        # Trends/time series
        if 'trends' in intent['topics'] or intent['timeframe'] in ['last_month', 'last_year']:
            period_type = 'month' if intent['timeframe'] == 'last_year' else 'week'
            trend_data = get_time_series_data(user_id, period_type, db)
            context_parts.append(trend_data)

        # Recommendations context (if asking for advice)
        if 'recommendations' in intent['topics']:
            # Summary already includes recommendations, but add extra context
            context_parts.append("\n**Additional Context for Recommendations:**\n"
                               "Focus on actionable, data-driven insights based on the performance metrics above. "
                               "Consider ROI, success rates, and market trends.")

        # 4. Combine within token budget
        final_context = combine_within_budget(context_parts, token_budget=4000)

        return final_context

    finally:
        if close_db:
            db.close()


# Convenience function for testing
def test_context_builder(user_id: int = 1, query: str = "What products should I sell?"):
    """Test the context builder with a sample query."""
    db = SessionLocal()
    try:
        context = build_claude_context(user_id, query, db)
        print("=" * 80)
        print(f"QUERY: {query}")
        print("=" * 80)
        print(context)
        print("=" * 80)
        return context
    finally:
        db.close()


if __name__ == "__main__":
    # Test with different query types
    test_queries = [
        "What products should I sell?",
        "How are my ads performing on TikTok?",
        "Give me a complete analysis of my business performance",
        "Which niches are most profitable?",
        "Show me my revenue trends for the last month"
    ]

    print("Testing Context Builder with various queries:\n")
    for query in test_queries:
        test_context_builder(user_id=1, query=query)
        print("\n" + "=" * 80 + "\n")
