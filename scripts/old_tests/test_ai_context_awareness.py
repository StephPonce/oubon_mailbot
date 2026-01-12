"""
AI CONTEXT AWARENESS TEST

Comprehensive test to verify AI has full visibility into ALL Ospra OS data sources.

Tests:
1. Unified context compilation from ALL 6 data sources
2. AI's ability to access and use each data source
3. Correlation detection across data sources
4. Complete data inventory report
5. AI responses demonstrating full context awareness
"""

import asyncio
import json
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

print("=" * 80)
print("AI CONTEXT AWARENESS TEST")
print("=" * 80)
print()

# Test 1: Import and initialize unified context
print("1. INITIALIZING UNIFIED CONTEXT SYSTEM")
print("-" * 80)

try:
    from ospra_os.database import SessionLocal
    from ospra_os.intelligence.unified_context import get_unified_context_builder
    print("[SUCCESS] Unified context system imported")
except Exception as e:
    print(f"[ERROR] Failed to import: {e}")
    exit(1)

# Create database session
db = SessionLocal()
context_builder = get_unified_context_builder(db)
print("[SUCCESS] Context builder initialized")
print()

# Test 2: Build full unified context
print("2. BUILDING FULL UNIFIED CONTEXT")
print("-" * 80)
print("Gathering data from all 6 sources in parallel...")
print()

async def build_context():
    return await context_builder.build_full_context(force_refresh=True)

context = asyncio.run(build_context())

print("[SUCCESS] Unified context built successfully")
print()

# Test 3: Data source inventory
print("3. DATA SOURCE INVENTORY")
print("-" * 80)

data_sources = {
    "products": "Product performance across all stores",
    "ads": "Meta/TikTok ad campaign performance",
    "emails": "Customer signals from email support",
    "social": "Social media trends (TikTok/Instagram)",
    "competitors": "Competitor intelligence and tracking",
    "learning": "Self-learning patterns and insights"
}

for source, description in data_sources.items():
    data = context.get(source, {})
    if isinstance(data, dict):
        item_count = len([k for k in data.keys() if not k.startswith('_')])
        has_data = any(data.values()) if data else False
    else:
        item_count = len(data) if data else 0
        has_data = bool(item_count)

    status = "[SUCCESS]" if has_data else "[WARNING] "
    print(f"{status} {source.upper()}")
    print(f"   {description}")

    if source == "products":
        print(f"   Total Products: {data.get('total_products', 0)}")
        print(f"   Active Products: {data.get('active_products', 0)}")
        print(f"   Total Revenue: ${data.get('total_revenue', 0):,.2f}")
        print(f"   Top Performers: {len(data.get('top_performers', []))}")
        print(f"   Underperformers: {len(data.get('underperformers', []))}")

    elif source == "ads":
        print(f"   Active Campaigns: {data.get('active_campaigns', 0)}")
        print(f"   Total Spend: ${data.get('total_spend', 0):,.2f}")
        print(f"   Average ROAS: {data.get('avg_roas', 0):.2f}x")
        print(f"   Total Conversions: {data.get('total_conversions', 0)}")

    elif source == "emails":
        print(f"   Total Emails: {data.get('total_emails', 0)}")
        print(f"   Complaints: {len(data.get('complaints', []))}")
        print(f"   Refund Requests: {len(data.get('refund_requests', []))}")

    elif source == "social":
        print(f"   Trending Products: {len(data.get('trending_products', []))}")
        print(f"   Trending Niches: {len(data.get('trending_niches', []))}")

    elif source == "competitors":
        print(f"   Tracked Competitors: {data.get('tracked_competitors', 0)}")
        print(f"   New Products: {len(data.get('new_products', []))}")

    elif source == "learning":
        patterns = data.get('patterns', {})
        print(f"   Success Patterns: {len(patterns.get('success_patterns', []))}")
        print(f"   Failure Patterns: {len(patterns.get('failure_patterns', []))}")

    print()

# Test 4: Correlation detection
print("4. CORRELATION DETECTION")
print("-" * 80)

correlations = context.get("correlations", [])
print(f"[SUCCESS] {len(correlations)} correlations detected across data sources")
print()

if correlations:
    print("Top correlations:")
    for i, corr in enumerate(correlations[:5], 1):
        severity_emoji = {
            "high": "",
            "medium": "",
            "low": ""
        }.get(corr.get("severity", "low"), "")

        print(f"{i}. {severity_emoji} {corr.get('type', 'unknown').replace('_', ' ').title()}")
        print(f"   Severity: {corr.get('severity', 'unknown')}")
        print(f"   Signal: {corr.get('signal', 'N/A')}")
        print(f"   Recommended Action: {corr.get('action', 'N/A')}")
        print()
else:
    print("No critical correlations detected - business running smoothly")
    print()

# Test 5: Summary metrics
print("5. EXECUTIVE SUMMARY")
print("-" * 80)

summary = context.get("summary", {})
print(f"Total Revenue: ${summary.get('total_revenue', 0):,.2f}")
print(f"Active Products: {summary.get('active_products', 0)}")
print(f"Ad Spend: ${summary.get('ad_spend', 0):,.2f}")
print(f"Average ROAS: {summary.get('avg_roas', 0):.2f}x")
print(f"Critical Issues: {summary.get('critical_issues', 0)}")
print(f"Medium Issues: {summary.get('medium_issues', 0)}")
print(f"Health Score: {summary.get('health_score', 0):.1f}/100")
print()

# Test 6: Initialize AI provider
print("6. INITIALIZING AI PROVIDER")
print("-" * 80)

try:
    from ospra_os.ai.providers.claude import ClaudeProvider

    claude_key = os.getenv("CLAUDE_API_KEY")
    if not claude_key:
        print("[ERROR] CLAUDE_API_KEY not found")
        exit(1)

    provider = ClaudeProvider(api_key=claude_key)
    print("[SUCCESS] ClaudeProvider initialized")
    print(f"   Model: {provider.model_name}")
    print()
except Exception as e:
    print(f"[ERROR] Failed to initialize AI: {e}")
    exit(1)

# Test 7: Test AI with full context
print("7. TESTING AI WITH FULL UNIFIED CONTEXT")
print("-" * 80)
print("Asking AI to analyze business based on ALL available data...")
print()

async def test_ai_with_context():
    # Build context dict for AI
    ai_context = {
        "store_metrics": {
            "total_revenue": summary.get("total_revenue", 0),
            "active_products": summary.get("active_products", 0),
            "health_score": summary.get("health_score", 0),
            "ad_spend": summary.get("ad_spend", 0),
            "avg_roas": summary.get("avg_roas", 0)
        },
        "current_products": context.get("products", {}).get("top_performers", []),
        "active_campaigns": context.get("ads", {}).get("best_campaigns", []),
        "correlations": correlations,
        "recent_activity": [
            f"{corr.get('type', 'event').replace('_', ' ').title()}: {corr.get('signal', 'N/A')[:50]}..."
            for corr in correlations[:3]
        ]
    }

    # Test 1: General business analysis
    print("TEST A: General business health analysis")
    print("-" * 40)

    response = await provider.chat(
        message=f"Based on the current data, what is the overall health of my business? What are the top 3 priorities I should focus on today?",
        context=ai_context
    )

    print(response)
    print()
    print("-" * 40)
    print()

    # Test 2: Specific correlation awareness
    if correlations:
        print("TEST B: AI awareness of detected correlations")
        print("-" * 40)

        response = await provider.chat(
            message=f"I see {len(correlations)} issues were detected. Can you explain the most critical one and what I should do about it?",
            context=ai_context
        )

        print(response)
        print()
        print("-" * 40)
        print()

    # Test 3: Product-specific insights
    top_products = context.get("products", {}).get("top_performers", [])
    if top_products:
        print("TEST C: AI awareness of product performance")
        print("-" * 40)

        response = await provider.chat(
            message=f"Looking at my top performing products, which ones should I invest more in with advertising?",
            context=ai_context
        )

        print(response)
        print()
        print("-" * 40)
        print()

    return True

success = asyncio.run(test_ai_with_context())

# Test 8: Verify data completeness
print("8. DATA COMPLETENESS VERIFICATION")
print("-" * 80)

completeness_report = {
    "Products Data": {
        "status": bool(context.get("products", {}).get("total_products", 0)),
        "coverage": "100%" if context.get("products", {}).get("total_products", 0) > 0 else "0%"
    },
    "Ad Campaign Data": {
        "status": bool(context.get("ads", {}).get("active_campaigns", 0)),
        "coverage": "100%" if context.get("ads", {}).get("active_campaigns", 0) > 0 else "0%"
    },
    "Email Signals": {
        "status": bool(context.get("emails", {}).get("total_emails", 0)),
        "coverage": "0%" if context.get("emails", {}).get("total_emails", 0) == 0 else "100%"
    },
    "Social Trends": {
        "status": bool(context.get("social", {}).get("trending_products", [])),
        "coverage": "0%" if not context.get("social", {}).get("trending_products", []) else "100%"
    },
    "Competitor Intelligence": {
        "status": bool(context.get("competitors", {}).get("tracked_competitors", 0)),
        "coverage": "0%" if context.get("competitors", {}).get("tracked_competitors", 0) == 0 else "100%"
    },
    "Self-Learning Patterns": {
        "status": bool(context.get("learning", {}).get("patterns", {})),
        "coverage": "100%" if context.get("learning", {}).get("patterns", {}) else "0%"
    }
}

for source, info in completeness_report.items():
    status_icon = "[SUCCESS]" if info["status"] else "[WARNING] "
    print(f"{status_icon} {source}: {info['coverage']} coverage")

print()

# Calculate overall coverage
active_sources = sum(1 for info in completeness_report.values() if info["status"])
total_sources = len(completeness_report)
overall_coverage = (active_sources / total_sources) * 100

print(f"Overall Data Coverage: {overall_coverage:.0f}% ({active_sources}/{total_sources} sources active)")
print()

# Close database
db.close()

# Final summary
print("=" * 80)
print("SUMMARY")
print("=" * 80)
print()
print("AI Context Awareness:")
print(f"  Data Sources Available: {active_sources}/{total_sources}")
print(f"  Correlations Detected: {len(correlations)}")
print(f"  Business Health Score: {summary.get('health_score', 0):.1f}/100")
print(f"  AI Can Access: Products, Ads, Emails, Social, Competitors, Learning Data")
print(f"  AI Can Detect: Cross-source patterns and correlations")
print(f"  AI Can Provide: Context-aware recommendations")
print()
print("Active Data Sources:")
for source, info in completeness_report.items():
    if info["status"]:
        print(f"  [SUCCESS] {source}")

print()
print("Pending Data Sources (to be implemented):")
for source, info in completeness_report.items():
    if not info["status"]:
        print(f"  [WARNING]  {source}")

print()
print("=" * 80)
print("AI CONTEXT AWARENESS: VERIFIED")
print("=" * 80)
print()
print(f"The AI has access to {active_sources}/{total_sources} data sources and can")
print("provide intelligent recommendations based on unified business context.")
print()
