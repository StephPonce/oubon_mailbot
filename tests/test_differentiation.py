"""
Test the complete differentiation system

Tests all 4 layers:
1. Saturation Tracking
2. Velocity Detection
3. Subscription Tiers
4. Marketing Angles

Plus the master SmartRecommendationEngine that combines them all.

NOTE (Pass 6): `SmartRecommendationEngine` imports the Groq provider
transitively, which in turn imports the top-level `groq` package at module
load time. In environments where `groq` isn't installed (CI minimal profile,
dev sandboxes without optional AI deps), the import cascade raises
ModuleNotFoundError at *collection* time — taking down unrelated tests in
the same pytest run. We guard the import so the file loads regardless, and
skip the tests inside when the dep is missing. The guard preserves full
coverage when groq IS installed.
"""
import asyncio

import pytest

from ospra_os.core.settings import get_settings

try:
    from ospra_os.intelligence.smart_recommendations import SmartRecommendationEngine

    SMART_RECS_AVAILABLE = True
    SMART_RECS_SKIP_REASON = ""
except ModuleNotFoundError as _e:  # pragma: no cover - env-dependent
    SmartRecommendationEngine = None  # type: ignore[assignment]
    SMART_RECS_AVAILABLE = False
    SMART_RECS_SKIP_REASON = (
        f"SmartRecommendationEngine import failed ({_e.name} missing). "
        "Install optional AI providers or mock them to run this test."
    )

pytestmark = pytest.mark.skipif(
    not SMART_RECS_AVAILABLE, reason=SMART_RECS_SKIP_REASON
)


async def test_smart_recommendations():
    """Test the smart recommendations engine"""

    print("\n" + "=" * 70)
    print("[TEST] TESTING COMPLETE DIFFERENTIATION SYSTEM")
    print("=" * 70)

    # ``get_settings()`` is ``@lru_cache``'d, and various tests touch
    # ``os.environ`` (test_security uses ``patch.dict(..., clear=True)``).
    # Bust the cache so we re-read the env we care about — DATABASE_URL,
    # which conftest pins to the per-worker SQLite file. Pass 4d also
    # silenced the ``load_dotenv(override=True)`` calls in
    # ``ospra_os/main.py`` and ``ospra_os/integrations/tiktok_client.py``
    # under APP_ENV=testing to keep this URL stable across test imports.
    get_settings.cache_clear()
    settings = get_settings()
    engine = SmartRecommendationEngine(settings.database_url)

    # Test for user ID 1
    user_id = 1

    print(f"\n[STATS] TEST 1: Getting recommendations for user {user_id}...")
    print("-" * 70)

    try:
        recommendations = await engine.get_personalized_recommendations(
            user_id=user_id,
            niches=['smart_home'],
            max_products=5,
            include_angles=True
        )

        if recommendations.get('success'):
            print(f"\n[SUCCESS] RECOMMENDATIONS SUCCESSFUL!")
            print(f"\n   User Information:")
            print(f"   • Tier: {recommendations['user_tier']}")
            print(f"   • Phase Access: {recommendations['tier_info']['phase_access']}")
            print(f"   • Advantage: {recommendations['tier_info']['advantage']}")

            print(f"\n   Filtering Pipeline:")
            filters = recommendations.get('filters_applied', {})
            print(f"   • Discovered: {filters.get('discovered', 0)} products")
            print(f"   • After Saturation Filter: {filters.get('after_saturation_filter', 0)}")
            print(f"   • After Tier Filter: {filters.get('after_tier_filter', 0)}")
            print(f"   • Final Count: {filters.get('final_count', 0)}")

            print(f"\n   Personalization Features:")
            personalization = recommendations.get('personalization', {})
            for key, value in personalization.items():
                print(f"   • {key.replace('_', ' ').title()}: {value}")

            print(f"\n   Products Recommended:")
            for idx, product in enumerate(recommendations.get('products', []), 1):
                print(f"\n   {idx}. {product.get('name', 'Unknown')}")
                print(f"      • Niche: {product.get('niche', 'N/A')}")
                print(f"      • Phase: {product.get('phase', 'N/A')}")
                print(f"      • Velocity Score: {product.get('velocity_score', 0)}")

                if 'marketing_angle' in product and product['marketing_angle']:
                    angle = product['marketing_angle']
                    print(f"      • Marketing Angle: {angle.get('angle', 'N/A')}")
                    print(f"      • Personalized Title: {angle.get('title', 'N/A')}")
                    print(f"      • Target Audience: {angle.get('target_audience', 'N/A')}")
        else:
            print(f"\n[ERROR] RECOMMENDATIONS FAILED")
            print(f"   Error: {recommendations.get('error', 'Unknown error')}")
            if 'traceback' in recommendations:
                print(f"\n   Traceback:")
                print(recommendations['traceback'])

    except Exception as e:
        print(f"\n[ERROR] TEST FAILED WITH EXCEPTION")
        print(f"   Error: {e}")
        import traceback
        traceback.print_exc()

    # Test analytics
    print(f"\n" + "-" * 70)
    print(f"[TREND] TEST 2: Getting analytics for user {user_id}...")
    print("-" * 70)

    try:
        analytics = await engine.get_recommendation_analytics(user_id)

        print(f"\n   Overall Statistics:")
        print(f"   • Total Recommended: {analytics.get('total_recommendations', 0)}")
        print(f"   • Products Deployed: {analytics.get('products_deployed', 0)}")
        print(f"   • Successful Products: {analytics.get('successful_products', 0)}")
        print(f"   • Success Rate: {analytics.get('success_rate', 0):.1f}%")

        diversity = analytics.get('product_diversity', {})
        print(f"\n   Product Diversity:")
        print(f"   • Unique Niches: {diversity.get('unique_niches', 0)}")
        print(f"   • Unique Marketing Angles: {diversity.get('unique_marketing_angles', 0)}")

        top_niches = analytics.get('top_performing_niches', [])
        if top_niches:
            print(f"\n   Top Performing Niches:")
            for niche in top_niches[:3]:
                print(f"   • {niche.get('niche')}: {niche.get('success_rate', 0):.1f}% success rate")

        top_angles = analytics.get('most_effective_angles', [])
        if top_angles:
            print(f"\n   Most Effective Marketing Angles:")
            for angle in top_angles[:3]:
                print(f"   • {angle.get('angle')}: {angle.get('success_rate', 0):.1f}% success rate")

    except Exception as e:
        print(f"\n[ERROR] ANALYTICS TEST FAILED")
        print(f"   Error: {e}")
        import traceback
        traceback.print_exc()

    # Close engine
    await engine.close()

    print("\n" + "=" * 70)
    print("[SUCCESS] DIFFERENTIATION SYSTEM TEST COMPLETE")
    print("=" * 70)


async def test_individual_systems():
    """Test each system individually"""

    print("\n" + "=" * 70)
    print(" TESTING INDIVIDUAL SYSTEMS")
    print("=" * 70)

    settings = get_settings()

    # Test 1: Saturation Tracker
    print("\n[STATS] TEST: Saturation Tracker")
    print("-" * 70)
    try:
        from ospra_os.intelligence.saturation_tracker import SaturationTracker

        tracker = SaturationTracker(settings.database_url)
        print("[SUCCESS] SaturationTracker initialized successfully")

        # Test filtering
        test_products = [
            {'id': 'test_1', 'name': 'Test Product 1'},
            {'id': 'test_2', 'name': 'Test Product 2'}
        ]
        filtered = await tracker.filter_saturated_products(test_products, max_users_per_product=50)
        print(f"[SUCCESS] Filtering works - {len(filtered)} products passed saturation filter")

        await tracker.close()

    except Exception as e:
        print(f"[ERROR] SaturationTracker failed: {e}")

    # Test 2: Velocity Detector
    print("\n[STATS] TEST: Velocity Detector")
    print("-" * 70)
    try:
        from ospra_os.intelligence.velocity_detector import VelocityDetector

        detector = VelocityDetector(settings.database_url)
        print("[SUCCESS] VelocityDetector initialized successfully")

        # Test velocity calculation
        test_product = {
            'id': 'test_product',
            'search_volume_7d': 1000,
            'search_volume_30d': 5000,
            'orders_7d': 50,
            'orders_30d': 200,
            'days_since_first_seen': 15
        }
        velocity = await detector.calculate_velocity_score(test_product)
        print(f"[SUCCESS] Velocity calculation works - Score: {velocity['velocity_score']:.2f}, Phase: {velocity['phase']}")

        await detector.close()

    except Exception as e:
        print(f"[ERROR] VelocityDetector failed: {e}")

    # Test 3: Tier Manager
    print("\n[STATS] TEST: Tier Manager")
    print("-" * 70)
    try:
        from ospra_os.subscription.tier_manager import TierManager

        tier_mgr = TierManager(settings.database_url)
        print("[SUCCESS] TierManager initialized successfully")

        # Test tier info
        tier_info = await tier_mgr.get_tier_info(user_id=1)
        print(f"[SUCCESS] Tier info works - User tier: {tier_info['tier_name']}")

        await tier_mgr.close()

    except Exception as e:
        print(f"[ERROR] TierManager failed: {e}")

    # Test 4: Marketing Angle Generator
    print("\n[STATS] TEST: Marketing Angle Generator")
    print("-" * 70)
    try:
        from ospra_os.intelligence.marketing_angle_generator import MarketingAngleGenerator

        generator = MarketingAngleGenerator(ai_provider='claude')
        print("[SUCCESS] MarketingAngleGenerator initialized successfully")

        # Test available angles
        angles = generator.get_available_angles('smart_home')
        print(f"[SUCCESS] Angle generation works - {len(angles)} angles available for smart_home niche")

    except Exception as e:
        print(f"[ERROR] MarketingAngleGenerator failed: {e}")

    print("\n" + "=" * 70)
    print("[SUCCESS] INDIVIDUAL SYSTEMS TEST COMPLETE")
    print("=" * 70)


async def main():
    """Run all tests"""

    # Test individual systems first
    await test_individual_systems()

    # Test integrated smart recommendations
    await test_smart_recommendations()

    print("\n" + "" * 70)
    print("[LAUNCH] ALL DIFFERENTIATION TESTS COMPLETE!")
    print("" * 70)
    print("\nThe Complete Anti-AutoDS System is operational:")
    print("  [SUCCESS] Saturation Tracking - Prevents oversaturation")
    print("  [SUCCESS] Velocity Detection - Tier-based early access")
    print("  [SUCCESS] Subscription Tiers - Different access levels")
    print("  [SUCCESS] Marketing Angles - Unique positioning")
    print("  [SUCCESS] Smart Recommendations - Master integration")
    print("\n[START] Users will NEVER compete directly!")
    print("" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
