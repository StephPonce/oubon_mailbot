#!/usr/bin/env python3
"""
Pre-Deployment Validation Script for Ospra OS.

Checks:
1. Environment variables are set
2. All API connections work
3. Database initialization
4. Core functionality tests
5. Scoring algorithm validation

Run this before deploying to production!
"""

import sys
import asyncio
from pathlib import Path


def print_section(title: str):
    """Print a formatted section header."""
    print(f"\n{'='*70}")
    print(f"{title}")
    print(f"{'='*70}\n")


async def check_environment_variables():
    """Check that all required environment variables are set."""
    print_section("1. ENVIRONMENT VARIABLES CHECK")

    from ospra_os.core.settings import get_settings
    settings = get_settings()

    checks = {
        "Database": settings.database_url is not None,
        "Gmail OAuth (optional)": True,  # Optional
        "OpenAI API": settings.OPENAI_API_KEY is not None,
        "Anthropic API (optional)": True,  # Optional
        "Reddit API": settings.REDDIT_CLIENT_ID is not None and settings.REDDIT_SECRET is not None,
        "Google Trends": True,  # No API key needed
        "Shopify Store": settings.SHOPIFY_STORE_DOMAIN is not None,
        "Shopify API Token": getattr(settings, "SHOPIFY_ADMIN_TOKEN", None) is not None or getattr(settings, "SHOPIFY_API_TOKEN", None) is not None,
        "AliExpress API Key": settings.ALIEXPRESS_API_KEY is not None,
        "AliExpress App Secret": settings.ALIEXPRESS_APP_SECRET is not None,
    }

    all_passed = True
    for name, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"{status} {name}: {'Configured' if passed else 'NOT CONFIGURED'}")

        if not passed and "(optional)" not in name:
            all_passed = False

    if all_passed:
        print("\n✅ All required environment variables are set!")
    else:
        print("\n⚠️  Some required environment variables are missing!")
        print("   Set them in Render: Dashboard → Environment → Add Environment Variable")

    return all_passed


async def check_database_initialization():
    """Check that databases are initialized correctly."""
    print_section("2. DATABASE INITIALIZATION CHECK")

    from ospra_os.core.settings import get_settings
    settings = get_settings()

    checks = []

    # Check follow-up database
    try:
        from app.models import init_followup_db
        init_followup_db(settings.database_url)
        print("✅ Follow-up database initialized")
        checks.append(True)
    except Exception as e:
        print(f"❌ Follow-up database failed: {e}")
        checks.append(False)

    # Check analytics database
    try:
        from app.analytics import init_analytics_db
        init_analytics_db(settings.database_url)
        print("✅ Analytics database initialized")
        checks.append(True)
    except Exception as e:
        print(f"❌ Analytics database failed: {e}")
        checks.append(False)

    # Check AliExpress OAuth database
    try:
        from ospra_os.aliexpress.oauth import init_aliexpress_oauth_db
        init_aliexpress_oauth_db(settings.database_url)
        print("✅ AliExpress OAuth database initialized")
        checks.append(True)
    except Exception as e:
        print(f"❌ AliExpress OAuth database failed: {e}")
        checks.append(False)

    if all(checks):
        print("\n✅ All databases initialized successfully!")
    else:
        print("\n⚠️  Some database initializations failed!")

    return all(checks)


async def check_api_connections():
    """Test connections to all external APIs."""
    print_section("3. API CONNECTION TESTS")

    from ospra_os.core.settings import get_settings
    settings = get_settings()

    results = {}

    # Test Reddit API
    if settings.REDDIT_CLIENT_ID and settings.REDDIT_SECRET:
        try:
            from ospra_os.product_research.connectors.social.reddit import RedditConnector
            reddit = RedditConnector(
                client_id=settings.REDDIT_CLIENT_ID,
                client_secret=settings.REDDIT_SECRET
            )
            if reddit.is_available():
                print("✅ Reddit API: Connected and available")
                results["reddit"] = True
            else:
                print("❌ Reddit API: Not available")
                results["reddit"] = False
        except Exception as e:
            print(f"❌ Reddit API: Failed - {e}")
            results["reddit"] = False
    else:
        print("⏭️  Reddit API: Skipped (not configured)")
        results["reddit"] = None

    # Test Google Trends (always available)
    try:
        from ospra_os.product_research.connectors.trends.google_trends import GoogleTrendsConnector
        trends = GoogleTrendsConnector()
        print("✅ Google Trends: Always available (no API key needed)")
        results["google_trends"] = True
    except Exception as e:
        print(f"❌ Google Trends: Failed - {e}")
        results["google_trends"] = False

    # Test Shopify API
    if settings.SHOPIFY_STORE_DOMAIN:
        try:
            from app.shopify_client import ShopifyClient
            import requests

            client = ShopifyClient(settings)
            url = f"https://{settings.SHOPIFY_STORE_DOMAIN}/admin/api/{settings.SHOPIFY_API_VERSION}/shop.json"
            response = requests.get(url, headers=client.headers, timeout=10)

            if response.status_code == 200:
                shop = response.json()["shop"]
                print(f"✅ Shopify API: Connected to {shop.get('name')}")
                results["shopify"] = True
            else:
                print(f"❌ Shopify API: HTTP {response.status_code}")
                results["shopify"] = False
        except Exception as e:
            print(f"❌ Shopify API: Failed - {e}")
            results["shopify"] = False
    else:
        print("⏭️  Shopify API: Skipped (not configured)")
        results["shopify"] = None

    # Test AliExpress OAuth Status
    if settings.ALIEXPRESS_API_KEY:
        try:
            # Just check if credentials are set - OAuth needs manual authorization
            print("✅ AliExpress API: Credentials configured (OAuth authorization required)")
            results["aliexpress"] = True
        except Exception as e:
            print(f"❌ AliExpress API: Failed - {e}")
            results["aliexpress"] = False
    else:
        print("⏭️  AliExpress API: Skipped (not configured)")
        results["aliexpress"] = None

    configured_count = sum(1 for v in results.values() if v is True)
    total_required = 3  # Reddit, Google Trends, Shopify

    if configured_count >= 2:
        print(f"\n✅ {configured_count} APIs connected - System is operational!")
    else:
        print(f"\n⚠️  Only {configured_count} APIs connected - Consider configuring more APIs")

    return configured_count >= 2


async def test_scoring_algorithm():
    """Validate that the scoring algorithm is working correctly."""
    print_section("4. SCORING ALGORITHM TEST")

    from ospra_os.product_research.connectors.base import ProductCandidate
    from ospra_os.product_research.scorer import ProductScorer

    scorer = ProductScorer()

    # Test case: High priority product
    high_priority_product = ProductCandidate(
        name="Smart Lock with Fingerprint",
        source="reddit",
        social_mentions=1000,
        social_engagement=150,
        trend_score=500,
        search_volume=70,
    )

    score = scorer.score(high_priority_product)
    priority = scorer.get_priority_label(score)

    print(f"Test Product: {high_priority_product.name}")
    print(f"  Score: {score}/10")
    print(f"  Priority: {priority}")

    if score >= 7.0 and priority == "HIGH":
        print("✅ Scoring algorithm is working correctly!")
        return True
    else:
        print(f"❌ Scoring algorithm issue: Expected HIGH priority (>7.0), got {priority} ({score})")
        return False


async def test_dashboard_routes():
    """Test that all dashboard API routes are accessible."""
    print_section("5. DASHBOARD API ROUTES TEST")

    print("Checking that all dashboard routes are defined...")

    from ospra_os.main import app

    required_routes = [
        "/api/dashboard/overview",
        "/api/dashboard/products",
        "/api/dashboard/emails",
        "/api/dashboard/shopify",
        "/api/dashboard/api-status",
        "/api/discover",
        "/api/validate-product",
    ]

    all_routes = [route.path for route in app.routes]

    all_present = True
    for route in required_routes:
        if route in all_routes:
            print(f"✅ {route}")
        else:
            print(f"❌ {route} - NOT FOUND")
            all_present = False

    if all_present:
        print("\n✅ All dashboard routes are defined!")
    else:
        print("\n❌ Some dashboard routes are missing!")

    return all_present


async def test_file_structure():
    """Check that all required files exist."""
    print_section("6. FILE STRUCTURE CHECK")

    required_files = [
        "ospra_os/main.py",
        "ospra_os/core/settings.py",
        "ospra_os/product_research/scorer.py",
        "ospra_os/product_research/discovery.py",
        "ospra_os/product_research/pipeline.py",
        "ospra_os/aliexpress/oauth.py",
        "ospra_os/aliexpress/routes.py",
        "app/gmail_client.py",
        "app/shopify_client.py",
        "app/analytics.py",
        "static/ospra_dashboard.html",
    ]

    all_present = True
    for file_path in required_files:
        path = Path(file_path)
        if path.exists():
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path} - NOT FOUND")
            all_present = False

    if all_present:
        print("\n✅ All required files are present!")
    else:
        print("\n❌ Some required files are missing!")

    return all_present


async def main():
    """Run all deployment checks."""
    print("\n" + "🚀" * 35)
    print("OSPRA OS - PRE-DEPLOYMENT VALIDATION")
    print("🚀" * 35)

    results = {}

    # Run all checks
    results["environment"] = await check_environment_variables()
    results["database"] = await check_database_initialization()
    results["api_connections"] = await check_api_connections()
    results["scoring"] = await test_scoring_algorithm()
    results["routes"] = await test_dashboard_routes()
    results["files"] = await test_file_structure()

    # Summary
    print_section("📊 DEPLOYMENT READINESS SUMMARY")

    total_checks = len(results)
    passed_checks = sum(1 for v in results.values() if v)

    for check_name, passed in results.items():
        status = "✅" if passed else "❌"
        print(f"{status} {check_name.replace('_', ' ').title()}")

    print(f"\nOverall: {passed_checks}/{total_checks} checks passed")

    if all(results.values()):
        print("\n" + "✅" * 35)
        print("🎉 ALL CHECKS PASSED - READY FOR DEPLOYMENT!")
        print("✅" * 35)
        return 0
    else:
        print("\n" + "⚠️ " * 35)
        print("❌ SOME CHECKS FAILED - REVIEW BEFORE DEPLOYING")
        print("⚠️ " * 35)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
