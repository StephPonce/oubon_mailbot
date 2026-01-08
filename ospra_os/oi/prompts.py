"""
Oi System Prompts - CONTEXT-AWARE & HONEST

Oi NEVER fabricates data. If it doesn't have real data, it says so clearly.
NOW WITH: Dashboard context awareness - knows what user is viewing.

Author: OspraOS
Date: December 2024
"""

from typing import Dict, Any, List, Optional


# ============================================================================
# OI CORE PERSONALITY - HONESTY IS NON-NEGOTIABLE
# ============================================================================

OI_SYSTEM_PROMPT = """You are Oi (pronounced "oy"), the AI assistant for Ospra Intelligence - an e-commerce automation platform.

## CRITICAL RULE: NEVER FABRICATE DATA

You must NEVER:
- Make up store statistics, revenue numbers, or order counts
- Invent product names, prices, or performance metrics
- Fabricate trending products or market data
- Pretend to see data that isn't in your context

If you don't have real data, you MUST say:
- "I don't have that data connected yet"
- "Your [X] isn't connected, so I can't see [Y]"
- "Once you connect [X], I'll be able to show you [Y]"

## YOUR IDENTITY - CRITICAL
- You ARE Oi - the AI brain of Ospra Intelligence
- You are NOT Claude, ChatGPT, GPT-4, or any other named AI assistant
- NEVER say "I'm Claude" or "I'm made by Anthropic" or mention any underlying AI model/company
- If asked what AI you are, say: "I'm Oi, the AI assistant built into Ospra Intelligence"
- If pressed about your technology, say: "I'm Oi - custom AI built for e-commerce automation. My focus is helping you run your store."
- Personality: Helpful, direct, a bit witty, and always honest about data

## CONTEXT AWARENESS
You can see what the user is currently looking at on their dashboard:
- Which page they're on
- Which product they've selected (if any)
- Which store they're viewing
- What products are visible on their screen
- Their recent searches and filters

Use this context to give more relevant, specific responses.

## WHAT YOU CAN DO

With CONNECTED data sources:
1. **Analyze** - Real product trends, actual store performance, genuine competition data
2. **Recommend** - Based on real market signals, not made-up statistics
3. **Execute** - Deploy products, send emails, adjust prices (with user confirmation)
4. **Forecast** - Using actual historical data, not fabricated numbers

Without data connections:
1. **Explain** - What Ospra can do once connected
2. **Guide** - Help users connect their stores, email, etc.
3. **Answer** - General e-commerce questions from your training
4. **Plan** - Help strategize what to do once data is flowing

## PERSONALIZATION & LEARNING SYSTEMS
You have access to TWO learning systems that make you smarter over time:

1. GLOBAL BRAIN - Learns from ALL Ospra users (network effect)
   - Shows what niches/prices work across the entire network
   - Updates with every sale made by any user
   - Gives you confidence in recommendations based on real outcomes

2. PERSONAL LAYER (Soar+ tiers only) - Learns from THIS specific user
   - Tracks their specific patterns and preferences
   - Adjusts scores based on their store's actual performance
   - Knows their peak selling days and optimal price ranges

Use this learning to:
- Adjust product opportunity scores based on proven patterns
- Recommend niches that work specifically for THIS user
- Suggest optimal price ranges based on what actually sells
- Time recommendations based on their peak selling days

## PRODUCT RECOMMENDATIONS
When recommending products, you can access:
- Opportunity Score (0-100): Demand divided by Competition
- Personal Adjustment: Delta based on user's specific patterns
- Confidence Level: How sure we are based on data quality and learning cycles

Opportunity Tiers:
- 85+: GOLDEN - Rare gems, tell user to act NOW
- 70-84: EXCELLENT - Strong opportunity, recommend deployment
- 55-69: GOOD - Worth considering, proceed with plan
- 40-54: FAIR - Proceed with caution, explain risks
- <40: SKIP - Risk outweighs reward, suggest alternatives

ALWAYS explain WHY a product scored well or poorly using:
- Demand signals (Google Trends, TikTok, Reddit mentions)
- Competition levels (seller count, ad saturation)
- Timing (early vs late to trend)
- Personal fit (if learning data available)

## HOW TO RESPOND

### When You Have Real Data
- Lead with the actual numbers
- Cite where the data comes from (e.g., "From your Shopify store...")
- Reference what they're looking at if relevant
- Be specific and actionable

### When You Don't Have Data
- Be upfront: "I don't have access to that yet"
- Explain what's needed: "Once you connect your Shopify store, I can show you..."
- Offer to help connect: "Would you like help setting that up?"

### Communication Style
- Direct and honest - no fluff, no fake data
- Use plain text (no markdown symbols like **, ##, ---)
- Acknowledge uncertainty clearly
- Numbers only when they're real
- Reference their current view when relevant

## FORMATTING RULES
- NO markdown symbols (no ##, ***, ---, etc.)
- NO fabricated numbers or statistics
- Use plain text with clear paragraph breaks
- Use numbers (1, 2, 3) for lists when needed
"""


# ============================================================================
# CONTEXT PROMPT BUILDER - SHOWS ONLY REAL DATA
# ============================================================================

def build_context_prompt(context: Dict[str, Any]) -> str:
    """
    Build context section showing ONLY real data.
    Clearly indicates what's connected vs not.
    Now includes dashboard context (what user is viewing).
    """
    sections = ["## YOUR CURRENT DATA ACCESS"]
    
    # ========================================================================
    # DASHBOARD CONTEXT - What user is currently viewing
    # ========================================================================
    current_page = context.get("current_page")
    current_view = context.get("current_view")
    
    if current_page:
        sections.append(f"\n### USER IS CURRENTLY VIEWING")
        sections.append(f"  Page: {current_page}")
        if current_view:
            sections.append(f"  View: {current_view}")
    
    # Selected product (if any)
    selected_product = context.get("selected_product")
    if selected_product and isinstance(selected_product, dict):
        sections.append(f"\n### SELECTED PRODUCT (user is looking at this)")
        sections.append(f"  Name: {selected_product.get('name', 'Unknown')}")
        if selected_product.get("price"):
            sections.append(f"  Price: ${selected_product.get('price', 0):.2f}")
        if selected_product.get("supplier_cost"):
            sections.append(f"  Supplier Cost: ${selected_product.get('supplier_cost', 0):.2f}")
        if selected_product.get("score"):
            sections.append(f"  Score: {selected_product.get('score', 0)}/10")
        if selected_product.get("niche"):
            sections.append(f"  Niche: {selected_product.get('niche')}")
        if selected_product.get("trend_score"):
            sections.append(f"  Trend Score: {selected_product.get('trend_score', 0)}%")
    
    # Selected store (if any)
    selected_store = context.get("selected_store")
    if selected_store and isinstance(selected_store, dict):
        sections.append(f"\n### SELECTED STORE")
        sections.append(f"  Name: {selected_store.get('store_name', 'Unknown')}")
        sections.append(f"  Platform: {selected_store.get('platform', 'Unknown')}")
        sections.append(f"  URL: {selected_store.get('store_url', '')}")
    
    # Visible products on screen
    visible_products = context.get("visible_products")
    if visible_products and isinstance(visible_products, list) and len(visible_products) > 0:
        sections.append(f"\n### PRODUCTS VISIBLE ON SCREEN ({len(visible_products)} total)")
        for i, p in enumerate(visible_products[:10]):  # Show first 10
            if isinstance(p, dict):
                name = p.get("name", "Unknown")
                score = p.get("score", 0)
                sections.append(f"  {i+1}. {name} (Score: {score})")
        if len(visible_products) > 10:
            sections.append(f"  ... and {len(visible_products) - 10} more")
    
    # Trending products from Intelligence Engine
    trending_products = context.get("trending_products")
    if trending_products and isinstance(trending_products, list) and len(trending_products) > 0:
        sections.append(f"\n### TRENDING PRODUCTS FROM INTELLIGENCE ENGINE")
        for t in trending_products[:5]:
            if isinstance(t, dict):
                name = t.get("name", "Unknown")
                score = t.get("score", 0)
                trend = t.get("trend_direction", "stable")
                sections.append(f"  - {name}: Score {score}/10 (trending {trend})")
    
    # Active filters
    active_filters = context.get("active_filters")
    if active_filters and isinstance(active_filters, dict) and len(active_filters) > 0:
        sections.append(f"\n### ACTIVE FILTERS")
        for key, value in active_filters.items():
            sections.append(f"  {key}: {value}")
    
    # Recent searches
    recent_searches = context.get("recent_searches")
    if recent_searches and isinstance(recent_searches, list) and len(recent_searches) > 0:
        sections.append(f"\n### RECENT SEARCHES")
        for s in recent_searches[:5]:
            sections.append(f"  - {s}")
    
    # ========================================================================
    # CONNECTION STATUS
    # ========================================================================
    status = context.get("connection_status", {})
    
    connected = []
    not_connected = []
    
    if status.get("has_stores"):
        connected.append("Stores")
    else:
        not_connected.append("Stores")
    
    if status.get("has_metrics"):
        connected.append("Store Metrics")
    else:
        not_connected.append("Store Metrics")
    
    if status.get("has_trending"):
        connected.append("Trending Data")
    else:
        not_connected.append("Trending Data")
    
    if status.get("has_email"):
        connected.append("Email")
    else:
        not_connected.append("Email")
    
    if status.get("has_ads"):
        connected.append("Ads")
    else:
        not_connected.append("Ads")
    
    sections.append(f"\n### CONNECTION STATUS")
    if connected:
        sections.append(f"  CONNECTED: {', '.join(connected)}")
    if not_connected:
        sections.append(f"  NOT CONNECTED: {', '.join(not_connected)}")
        sections.append("  (You cannot provide data for unconnected sources - be honest about this)")
    
    # ========================================================================
    # REAL DATA FROM CONNECTED SOURCES
    # ========================================================================
    
    # Store metrics - REAL DATA ONLY
    metrics = context.get("store_metrics")
    if metrics and isinstance(metrics, dict) and metrics.get("revenue_7d") is not None:
        sections.append(f"\n### STORE PERFORMANCE (REAL DATA)")
        sections.append(f"  Revenue (7d): ${metrics.get('revenue_7d', 0):,.2f}")
        sections.append(f"  Revenue (30d): ${metrics.get('revenue_30d', 0):,.2f}")
        sections.append(f"  Orders (7d): {metrics.get('orders_7d', 0)}")
        sections.append(f"  Orders (30d): {metrics.get('orders_30d', 0)}")
        sections.append(f"  Products: {metrics.get('products_count', 0)}")
        sections.append(f"  Customers: {metrics.get('customers_count', 0)}")
        sections.append(f"  Avg Order Value: ${metrics.get('avg_order_value', 0):.2f}")
    
    # Email stats - REAL DATA ONLY
    email_stats = context.get("email_stats")
    if email_stats and isinstance(email_stats, dict):
        sections.append(f"\n### EMAIL STATS (REAL DATA)")
        sections.append(f"  Unread: {email_stats.get('unread_count', 0)}")
        sections.append(f"  Auto-replied: {email_stats.get('auto_replied_count', 0)}")
        sections.append(f"  Pending review: {email_stats.get('pending_review', 0)}")
    
    # Ad stats - REAL DATA ONLY
    ad_stats = context.get("ad_stats")
    if ad_stats and isinstance(ad_stats, dict):
        sections.append(f"\n### AD PERFORMANCE (REAL DATA)")
        sections.append(f"  Total Spend: ${ad_stats.get('total_spend', 0):,.2f}")
        sections.append(f"  Impressions: {ad_stats.get('total_impressions', 0):,}")
        sections.append(f"  Clicks: {ad_stats.get('total_clicks', 0):,}")
        sections.append(f"  ROAS: {ad_stats.get('roas', 0):.2f}x")
        sections.append(f"  Active Campaigns: {ad_stats.get('active_campaigns', 0)}")
    
    # ========================================================================
    # USER LEARNING DATA
    # ========================================================================
    user_learning = context.get("user_learning")
    if user_learning and isinstance(user_learning, dict):
        prefs = user_learning.get("user_preferences", {})
        behavior = user_learning.get("behavioral_patterns", {})
        
        if prefs.get("top_niches"):
            sections.append(f"\n### USER PREFERENCES (learned from behavior)")
            niches = prefs.get("top_niches", [])
            if niches:
                niche_str = ", ".join([n.get("niche", "") for n in niches[:3] if isinstance(n, dict)])
                sections.append(f"  Top niches: {niche_str}")
            if prefs.get("price_interest"):
                sections.append(f"  Avg price interest: ${prefs.get('price_interest', 0):.2f}")
        
        engagement = user_learning.get("engagement_level", "new")
        sections.append(f"\n### USER ENGAGEMENT LEVEL: {engagement}")
    
    # ========================================================================
    # INTELLIGENCE ENGINE DATA (from Intelligence Bridge)
    # ========================================================================
    intelligence = context.get("intelligence_context")
    if intelligence and isinstance(intelligence, dict):
        sections.append(f"\n### INTELLIGENCE ENGINE STATUS")
        sections.append(f"  Intelligence Available: {intelligence.get('intelligence_available', False)}")
        sections.append(f"  Learning Available: {intelligence.get('learning_available', False)}")
        sections.append(f"  Discovery Available: {intelligence.get('discovery_available', False)}")
        
        # Learning insights
        insights = intelligence.get("learning_insights")
        if insights:
            sections.append(f"\n### GLOBAL BRAIN INSIGHTS")
            global_niches = insights.get("global_best_niches", [])
            if global_niches:
                sections.append(f"  Best performing niches (network-wide): {', '.join(global_niches[:3])}")
            sections.append(f"  Global accuracy: {insights.get('global_accuracy', 50)}%")
            
            if insights.get("personal_available"):
                sections.append(f"\n### PERSONAL LAYER (this user)")
                personal_niches = insights.get("personal_best_niches", [])
                if personal_niches:
                    sections.append(f"  Best niches for this user: {', '.join(personal_niches[:3])}")
                sections.append(f"  Suggested focus: {insights.get('suggested_focus', 'Connect store for personalization')}")
        
        # Top opportunities
        opportunities = intelligence.get("top_opportunities")
        if opportunities and len(opportunities) > 0:
            sections.append(f"\n### TOP PRODUCT OPPORTUNITIES (REAL DATA)")
            for opp in opportunities[:5]:
                name = opp.get("name", "Unknown")[:40]
                score = opp.get("score", 0)
                confidence = opp.get("confidence", 0)
                urgency = opp.get("urgency", "MONITOR")
                reason = opp.get("top_reason", "Good opportunity")
                sections.append(f"  - {name}")
                sections.append(f"    Score: {score}/100 | Confidence: {confidence}% | Urgency: {urgency}")
                sections.append(f"    Why: {reason}")
    
    # ========================================================================
    # FINAL REMINDER
    # ========================================================================
    sections.append("\n---")
    sections.append("CRITICAL: Only discuss data shown above. If it's not listed, you don't have it.")
    sections.append("Use the user's current view (page, selected product) to make responses relevant.")
    
    return "\n".join(sections)


# ============================================================================
# CONTEXT-AWARE SUGGESTIONS
# ============================================================================

def build_contextual_suggestions(context: Dict[str, Any]) -> List[str]:
    """
    Generate context-aware suggestions based on what user is viewing.
    """
    suggestions = []
    
    current_page = context.get("current_page", "")
    selected_product = context.get("selected_product")
    selected_store = context.get("selected_store")
    visible_products = context.get("visible_products", [])
    store_metrics = context.get("store_metrics")
    
    # Product-specific suggestions
    if selected_product:
        product_name = selected_product.get("name", "this product")[:30]
        suggestions.append(f"Analyze '{product_name}'")
        suggestions.append(f"Deploy to store")
        suggestions.append(f"Find similar products")
        suggestions.append(f"Estimate profit margin")
    
    # Page-specific suggestions
    if current_page == "overview":
        if not selected_store:
            suggestions.append("Connect a store")
        else:
            suggestions.append("Store performance summary")
            suggestions.append("What should I focus on?")
    
    elif current_page == "products":
        if len(visible_products) > 1:
            suggestions.append(f"Compare top {min(5, len(visible_products))} products")
            suggestions.append("Which has best profit margin?")
        suggestions.append("Find trending products")
        suggestions.append("Filter by niche")
    
    elif current_page == "analytics":
        suggestions.append("Revenue trends")
        suggestions.append("Best performing products")
        suggestions.append("Customer insights")
    
    elif current_page == "emails":
        suggestions.append("Unread emails summary")
        suggestions.append("Draft a response")
        suggestions.append("Email automation settings")
    
    elif current_page == "ads":
        suggestions.append("Campaign performance")
        suggestions.append("Ad spend analysis")
        suggestions.append("Create new campaign")
    
    # General suggestions if not enough context-specific ones
    if len(suggestions) < 3:
        if store_metrics:
            suggestions.append("How's my store doing?")
        else:
            suggestions.append("Get started with Ospra")
        suggestions.append("What can you help with?")
    
    return suggestions[:4]  # Return max 4 suggestions


# ============================================================================
# ACTION PROMPTS - HONEST ABOUT CAPABILITIES
# ============================================================================

ACTION_CONFIRMATION_PROMPTS = {
    "deploy_product": """
I'm ready to deploy "{product_name}" to {store_name}:
- Price: ${price}
- Supplier: {supplier}

This will create a live product listing. Confirm? (yes/no)
""",
    
    "no_store_connected": """
I can't deploy products yet because you don't have a store connected.

To deploy products, you'll need to:
1. Go to Settings or Overview
2. Connect your Shopify or WooCommerce store
3. Then come back and I can deploy products for you

Want me to help you connect your store?
""",

    "no_data_available": """
I don't have access to that data yet.

What's needed: {requirement}

Would you like help setting that up?
""",

    "analyze_selected_product": """
Based on {product_name} you're currently viewing:

{analysis}

Would you like me to:
1. Compare with alternatives
2. Deploy to your store
3. Get deeper market analysis
""",

    "compare_visible_products": """
Looking at the {count} products on your screen:

{comparison}

My recommendation: {recommendation}

Want me to deploy the top pick?
"""
}


# ============================================================================
# PAGE-SPECIFIC WELCOME MESSAGES
# ============================================================================

def get_welcome_message(context: Dict[str, Any]) -> str:
    """Generate a context-aware welcome message."""
    current_page = context.get("current_page", "overview")
    selected_store = context.get("selected_store")
    selected_product = context.get("selected_product")
    visible_products = context.get("visible_products", [])
    
    # Base greeting
    messages = ["Hey! I'm Oi, your AI assistant for Ospra Intelligence."]
    
    # Page-specific content
    if current_page == "overview":
        if selected_store:
            messages.append(f"\nI can see you have {selected_store.get('store_name', 'a store')} connected.")
        else:
            messages.append("\nConnect your e-commerce store to unlock real-time analytics and AI-powered insights.")
    
    elif current_page == "products":
        if selected_product:
            messages.append(f"\nYou're looking at '{selected_product.get('name', 'a product')}'.")
            messages.append("Want me to analyze it or help you deploy it?")
        elif len(visible_products) > 0:
            messages.append(f"\nI can see {len(visible_products)} products on your screen.")
            messages.append("Need help comparing them or finding the best opportunity?")
        else:
            messages.append("\nReady to help you discover winning products.")
    
    elif current_page == "analytics":
        messages.append("\nReady to dive into your performance data.")
    
    elif current_page == "emails":
        messages.append("\nI can help manage your customer communications.")
    
    elif current_page == "ads":
        messages.append("\nLet's optimize your advertising strategy.")
    
    # General capabilities
    messages.append("\n\nImportant: I only work with REAL data from your connected services. I'll never make up statistics or fake information.")
    messages.append("\n\nWhat would you like to know?")
    
    return "".join(messages)
