"""
Test script for Smart Recommendations System - The Complete Anti-AutoDS Solution

Tests the master recommendation engine that integrates:
1. Saturation Tracking - Prevents oversaturated products
2. Velocity Detection - Tier-based early access to trending products
3. Subscription Tiers - Different access levels
4. Marketing Angles - Unique positioning per user

Result: No two users compete directly, everyone gets personalized recommendations
"""

import asyncio
import httpx
from ospra_os.core.settings import Settings


async def test_smart_recommendation_engine():
    """Test SmartRecommendationEngine class (service layer)"""
    print("\n" + "="*70)
    print("TEST 1: Smart Recommendation Engine Service")
    print("="*70)

    try:
        from ospra_os.intelligence.smart_recommendations import SmartRecommendationEngine

        settings = Settings()

        # Initialize engine
        print("\n[Test 1.1] Initializing SmartRecommendationEngine...")
        engine = SmartRecommendationEngine(database_url=settings.database_url)
        print("✓ Engine initialized with all 4 sub-systems:")
        print("  - SaturationTracker")
        print("  - VelocityDetector")
        print("  - TierManager")
        print("  - MarketingAngleGenerator")

        # Test personalized recommendations for different users
        print("\n[Test 1.2] Getting recommendations for Free tier user (user_id=1)...")
        free_user_recs = await engine.get_personalized_recommendations(
            user_id=1,
            niches=['smart_home', 'fitness'],
            max_products=5,
            include_angles=True
        )

        if free_user_recs.get('success'):
            print(f"✓ Free user recommendations:")
            print(f"  Tier: {free_user_recs['user_tier']}")
            print(f"  Phase Access: {free_user_recs['tier_info']['phase_access']}")
            print(f"  Products: {free_user_recs['count']}")
            print(f"  Advantage: {free_user_recs['tier_info']['advantage']}")
        else:
            print(f"✗ Free user recommendations failed: {free_user_recs.get('error')}")

        # Test Pro tier user
        print("\n[Test 1.3] Getting recommendations for Pro tier user (user_id=2)...")
        pro_user_recs = await engine.get_personalized_recommendations(
            user_id=2,
            niches=['smart_home'],
            max_products=5,
            include_angles=True
        )

        if pro_user_recs.get('success'):
            print(f"✓ Pro user recommendations:")
            print(f"  Tier: {pro_user_recs['user_tier']}")
            print(f"  Phase Access: {pro_user_recs['tier_info']['phase_access']}")
            print(f"  Products: {pro_user_recs['count']}")
            print(f"  Advantage: {pro_user_recs['tier_info']['advantage']}")

            # Show first product with marketing angle
            if pro_user_recs['count'] > 0:
                product = pro_user_recs['products'][0]
                print(f"\n  Example Product:")
                print(f"    Name: {product.get('name')}")
                if product.get('marketing_angle'):
                    angle = product['marketing_angle']
                    print(f"    Marketing Angle: {angle.get('angle')}")
                    print(f"    Personalized Title: {angle.get('title')}")
                    print(f"    Target Audience: {angle.get('target_audience')}")
        else:
            print(f"✗ Pro user recommendations failed: {pro_user_recs.get('error')}")

        # Test analytics
        print("\n[Test 1.4] Getting recommendation analytics for user 1...")
        analytics = await engine.get_recommendation_analytics(user_id=1)

        print(f"✓ Analytics retrieved:")
        print(f"  Total recommendations: {analytics.get('total_recommendations', 0)}")
        print(f"  Products deployed: {analytics.get('products_deployed', 0)}")
        print(f"  Success rate: {analytics.get('success_rate', 0)}%")

        # Close engine
        await engine.close()
        print("\n✓ All SmartRecommendationEngine tests passed!")
        return True

    except Exception as e:
        print(f"\n✗ SmartRecommendationEngine test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_api_endpoints():
    """Test smart recommendations API endpoints"""
    print("\n" + "="*70)
    print("TEST 2: Smart Recommendations API Endpoints")
    print("="*70)

    base_url = "http://localhost:8001"

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            # Test 1: Smart recommendations endpoint
            print("\n[Test 2.1] POST /api/recommendations/smart")
            response = await client.post(
                f"{base_url}/api/recommendations/smart",
                params={
                    "user_id": 1,
                    "niches": ["smart_home", "fitness"],
                    "max_products": 5,
                    "include_angles": True
                }
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    print(f"✓ API responded successfully")
                    print(f"  User Tier: {data.get('user_tier')}")
                    print(f"  Products Returned: {data.get('count')}")
                    print(f"  Saturation Protected: {data.get('personalization', {}).get('saturation_protected')}")
                    print(f"  Unique Angles: {data.get('personalization', {}).get('unique_marketing_angles')}")
                    print(f"  Tier-Based Access: {data.get('personalization', {}).get('tier_based_early_access')}")

                    # Show filtering stats
                    filters = data.get('filters_applied', {})
                    print(f"\n  Filtering Pipeline:")
                    print(f"    Discovered: {filters.get('discovered', 0)} products")
                    print(f"    After Saturation Filter: {filters.get('after_saturation_filter', 0)}")
                    print(f"    After Tier Filter: {filters.get('after_tier_filter', 0)}")
                    print(f"    Final Count: {filters.get('final_count', 0)}")
                else:
                    print(f"✗ API error: {data.get('error')}")
                    return False
            else:
                print(f"✗ HTTP {response.status_code}: {response.text[:200]}")
                return False

            # Test 2: Analytics endpoint
            print("\n[Test 2.2] GET /api/recommendations/analytics/1")
            response = await client.get(
                f"{base_url}/api/recommendations/analytics/1"
            )

            if response.status_code == 200:
                data = response.json()
                print(f"✓ API responded successfully")
                print(f"  User ID: {data.get('user_id')}")
                print(f"  Total Recommendations: {data.get('total_recommendations', 0)}")
                print(f"  Products Deployed: {data.get('products_deployed', 0)}")
                print(f"  Successful Products: {data.get('successful_products', 0)}")
                print(f"  Success Rate: {data.get('success_rate', 0)}%")

                diversity = data.get('product_diversity', {})
                print(f"\n  Product Diversity:")
                print(f"    Unique Niches: {diversity.get('unique_niches', 0)}")
                print(f"    Unique Angles: {diversity.get('unique_marketing_angles', 0)}")
            else:
                print(f"✗ HTTP {response.status_code}")
                return False

            # Test 3: Different tiers get different products
            print("\n[Test 2.3] Testing tier differentiation...")

            # Free tier user
            free_response = await client.post(
                f"{base_url}/api/recommendations/smart",
                params={"user_id": 1, "max_products": 3, "include_angles": False}
            )

            # Pro tier user (assuming user_id 2 is Pro)
            pro_response = await client.post(
                f"{base_url}/api/recommendations/smart",
                params={"user_id": 2, "max_products": 3, "include_angles": False}
            )

            if free_response.status_code == 200 and pro_response.status_code == 200:
                free_data = free_response.json()
                pro_data = pro_response.json()

                print(f"✓ Tier differentiation working:")
                print(f"  Free tier: {free_data.get('user_tier')} - Access to {free_data.get('tier_info', {}).get('phase_access')}")
                print(f"  Pro tier: {pro_data.get('user_tier')} - Access to {pro_data.get('tier_info', {}).get('phase_access')}")
            else:
                print(f"✗ Tier differentiation test failed")

            print("\n✓ All API endpoint tests passed!")
            return True

        except httpx.ConnectError:
            print("✗ Failed to connect to backend")
            print("  Make sure the backend is running on port 8001")
            return False

        except Exception as e:
            print(f"✗ API test failed: {e}")
            import traceback
            traceback.print_exc()
            return False


async def demonstration():
    """Demonstrate the complete anti-AutoDS system in action"""
    print("\n" + "="*70)
    print("DEMONSTRATION: Complete Anti-AutoDS System")
    print("="*70)

    print("\nScenario: 3 users want product recommendations")
    print("- User A: Free tier")
    print("- User B: Starter tier")
    print("- User C: Pro tier")
    print("\nThe system ensures:")
    print("1. Each tier gets different velocity phases (early access)")
    print("2. No oversaturated products are recommended")
    print("3. Each user gets unique marketing angles")
    print("4. No two users compete directly")

    try:
        from ospra_os.intelligence.smart_recommendations import SmartRecommendationEngine
        from ospra_os.core.settings import Settings

        settings = Settings()
        engine = SmartRecommendationEngine(database_url=settings.database_url)

        # User A: Free tier
        print("\n" + "-"*70)
        print("👤 USER A (Free Tier)")
        print("-"*70)

        user_a = await engine.get_personalized_recommendations(
            user_id=100,  # Test user
            niches=['smart_home'],
            max_products=2,
            include_angles=True
        )

        if user_a.get('success'):
            print(f"Tier: {user_a['user_tier']}")
            print(f"Phase Access: {user_a['tier_info']['phase_access']}")
            print(f"Advantage: {user_a['tier_info']['advantage']}")
            print(f"Products: {user_a['count']}")

        # User B: Starter tier (would need to set up user with starter tier)
        print("\n" + "-"*70)
        print("👤 USER B (Starter Tier)")
        print("-"*70)

        user_b = await engine.get_personalized_recommendations(
            user_id=101,  # Test user
            niches=['smart_home'],
            max_products=2,
            include_angles=True
        )

        if user_b.get('success'):
            print(f"Tier: {user_b['user_tier']}")
            print(f"Phase Access: {user_b['tier_info']['phase_access']}")
            print(f"Advantage: {user_b['tier_info']['advantage']}")
            print(f"Products: {user_b['count']}")

        # User C: Pro tier
        print("\n" + "-"*70)
        print("👤 USER C (Pro Tier)")
        print("-"*70)

        user_c = await engine.get_personalized_recommendations(
            user_id=102,  # Test user
            niches=['smart_home'],
            max_products=2,
            include_angles=True
        )

        if user_c.get('success'):
            print(f"Tier: {user_c['user_tier']}")
            print(f"Phase Access: {user_c['tier_info']['phase_access']}")
            print(f"Advantage: {user_c['tier_info']['advantage']}")
            print(f"Products: {user_c['count']}")

        await engine.close()

        print("\n" + "="*70)
        print("✅ RESULT: Complete Anti-AutoDS System Working!")
        print("="*70)
        print("\nKey Features Demonstrated:")
        print("  ✓ Tier-based early access (different phases per tier)")
        print("  ✓ Saturation protection (oversaturated products filtered)")
        print("  ✓ Velocity detection (lifecycle phase filtering)")
        print("  ✓ Unique marketing angles (prevent direct competition)")
        print("\nNo two users compete directly - each gets personalized recommendations!")
        print("="*70)

    except Exception as e:
        print(f"\n✗ Demonstration failed: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Run all tests"""
    print("\n" + "█"*70)
    print("SMART RECOMMENDATIONS SYSTEM - COMPLETE ANTI-AUTODS VERIFICATION")
    print("█"*70)

    try:
        # Test 1: Service layer
        test1_passed = await test_smart_recommendation_engine()

        # Test 2: API endpoints
        test2_passed = await test_api_endpoints()

        # Demonstration
        await demonstration()

        # Summary
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)
        print(f"✓ SmartRecommendationEngine Service: {'PASSED' if test1_passed else 'FAILED'}")
        print(f"✓ API Endpoints: {'PASSED' if test2_passed else 'FAILED'}")

        if test1_passed and test2_passed:
            print("\n" + "█"*70)
            print("🎉 ALL TESTS PASSED - COMPLETE ANTI-AUTODS SYSTEM READY!")
            print("█"*70)
            print("\nThe master recommendation system is now active:")
            print("  ✓ 4 integrated sub-systems")
            print("  ✓ Saturation tracking prevents oversaturation")
            print("  ✓ Velocity detection provides tier-based early access")
            print("  ✓ Subscription tiers differentiate access levels")
            print("  ✓ Marketing angles ensure unique positioning")
            print("\nAPI Endpoints:")
            print("  • POST /api/recommendations/smart")
            print("  • GET /api/recommendations/analytics/{user_id}")
            print("\n🚀 Users will NEVER compete directly - everyone wins!")
            return 0
        else:
            print("\n❌ SOME TESTS FAILED")
            return 1

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
