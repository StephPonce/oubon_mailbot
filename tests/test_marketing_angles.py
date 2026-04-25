"""
Test script for Marketing Angle Generator

Tests the AI-powered marketing angle generation system that creates
unique positioning for products to prevent direct competition between users.

NOTE (Pass 6): `MarketingAngleGenerator` imports AIFactory which transitively
imports the Groq provider's top-level `groq` package at module load time.
In environments without the optional `groq` dep the import cascade raises
ModuleNotFoundError at *collection* time. We guard the import so the file
loads regardless, and skip the tests inside when the dep is missing.
"""

import asyncio

import httpx
import pytest

try:
    from ospra_os.intelligence.marketing_angle_generator import MarketingAngleGenerator

    MARKETING_ANGLES_AVAILABLE = True
    MARKETING_ANGLES_SKIP_REASON = ""
except ModuleNotFoundError as _e:  # pragma: no cover - env-dependent
    MarketingAngleGenerator = None  # type: ignore[assignment]
    MARKETING_ANGLES_AVAILABLE = False
    MARKETING_ANGLES_SKIP_REASON = (
        f"MarketingAngleGenerator import failed ({_e.name} missing). "
        "Install optional AI providers (groq) or mock them to run this test."
    )

pytestmark = pytest.mark.skipif(
    not MARKETING_ANGLES_AVAILABLE, reason=MARKETING_ANGLES_SKIP_REASON
)


async def test_marketing_angle_generator():
    """Test MarketingAngleGenerator class"""
    print("\n" + "="*70)
    print("TEST 1: Marketing Angle Generator Service")
    print("="*70)

    # Test product
    product_name = "Smart LED Strip Lights"
    product_description = "WiFi-enabled RGB LED strips with app control, 16 million colors, music sync"

    try:
        # Initialize generator
        print("\n[Test 1.1] Initializing MarketingAngleGenerator...")
        generator = MarketingAngleGenerator(ai_provider='claude')
        print("[OK] Generator initialized")

        # Test 1: Generate single angle
        print("\n[Test 1.2] Generating 'home_automation' angle...")
        angle = await generator.generate_unique_angle(
            product_name=product_name,
            product_description=product_description,
            user_brand_voice='professional',
            user_target_audience='tech-savvy homeowners',
            niche='smart_home',
            avoid_angles=[]
        )

        print(f"[OK] Angle generated: {angle['angle']}")
        print(f"  Title: {angle['title']}")
        print(f"  Target Audience: {angle['target_audience']}")
        print(f"  Pain Point: {angle['pain_point']}")
        print(f"  CTA: {angle['cta']}")
        print(f"  Benefits: {len(angle['benefits'])} benefits")

        # Test 2: Generate multiple angles
        print("\n[Test 1.3] Generating 3 different angles for A/B testing...")
        angles = await generator.generate_multiple_angles(
            product_name=product_name,
            product_description=product_description,
            niche='smart_home',
            num_angles=3,
            user_brand_voice='casual',
            user_target_audience='young homeowners'
        )

        print(f"[OK] Generated {len(angles)} unique angles:")
        for i, angle in enumerate(angles, 1):
            print(f"  {i}. {angle['angle']} - {angle['title'][:50]}...")

        # Test 3: Get available angles
        print("\n[Test 1.4] Getting available angles for smart_home niche...")
        available = generator.get_available_angles('smart_home')
        print(f"[OK] Found {len(available)} available angles:")
        print(f"  {', '.join(available)}")

        # Test 4: Get angle description
        print("\n[Test 1.5] Getting description for 'energy_saving' angle...")
        desc = generator.get_angle_description('energy_saving')
        print(f"[OK] Angle: {desc['angle']}")
        print(f"  Target Audience: {desc['target_audience']}")
        print(f"  Pain Point: {desc['pain_point']}")

        print("\n[OK] All MarketingAngleGenerator tests passed!")
        return True

    except Exception as e:
        print(f"\n MarketingAngleGenerator test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_api_endpoints():
    """Test marketing angle API endpoints"""
    print("\n" + "="*70)
    print("TEST 2: Marketing Angle API Endpoints")
    print("="*70)

    base_url = "http://localhost:8001"

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            # Test 1: Generate single angle
            print("\n[Test 2.1] POST /api/marketing/generate-angle")
            response = await client.post(
                f"{base_url}/api/marketing/generate-angle",
                params={
                    "product_name": "Smart Fitness Tracker Watch",
                    "product_description": "Track your steps, heart rate, sleep quality, and calories burned",
                    "niche": "fitness",
                    "user_brand_voice": "motivational",
                    "user_target_audience": "fitness enthusiasts"
                }
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    angle = data['angle']
                    print(f"[OK] API responded successfully")
                    print(f"  Angle: {angle['angle']}")
                    print(f"  Title: {angle['title']}")
                    print(f"  Target: {angle['target_audience']}")
                else:
                    print(f" API error: {data.get('error')}")
                    return False
            else:
                print(f" HTTP {response.status_code}: {response.text[:200]}")
                return False

            # Test 2: Generate multiple angles
            print("\n[Test 2.2] POST /api/marketing/generate-multiple-angles")
            response = await client.post(
                f"{base_url}/api/marketing/generate-multiple-angles",
                params={
                    "product_name": "Electric Milk Frother",
                    "product_description": "Create perfect foam for lattes and cappuccinos in seconds",
                    "niche": "kitchen",
                    "num_angles": 3,
                    "user_brand_voice": "friendly",
                    "user_target_audience": "coffee lovers"
                }
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    print(f"[OK] API responded successfully")
                    print(f"  Generated {data['count']} angles:")
                    for i, angle in enumerate(data['angles'], 1):
                        print(f"    {i}. {angle['angle']}: {angle['title'][:45]}...")
                else:
                    print(f" API error: {data.get('error')}")
                    return False
            else:
                print(f" HTTP {response.status_code}")
                return False

            # Test 3: Get available angles
            print("\n[Test 2.3] GET /api/marketing/available-angles")
            response = await client.get(
                f"{base_url}/api/marketing/available-angles",
                params={"niche": "fitness"}
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    print(f"[OK] API responded successfully")
                    print(f"  Niche: {data['niche']}")
                    print(f"  Available angles: {data['count']}")
                    for angle in data['angles'][:3]:
                        print(f"    - {angle['angle']}: {angle['target_audience']}")
                else:
                    print(f" API error: {data.get('error')}")
                    return False
            else:
                print(f" HTTP {response.status_code}")
                return False

            print("\n[OK] All API endpoint tests passed!")
            return True

        except httpx.ConnectError:
            print(" Failed to connect to backend")
            print("  Make sure the backend is running on port 8001")
            return False

        except Exception as e:
            print(f" API test failed: {e}")
            import traceback
            traceback.print_exc()
            return False


async def demonstration():
    """Demonstrate how different users get different angles for same product"""
    print("\n" + "="*70)
    print("DEMONSTRATION: Same Product, Different Marketing Angles")
    print("="*70)

    product_name = "Smart WiFi Security Camera"
    product_description = "1080p HD camera with night vision, motion detection, and two-way audio"

    print(f"\nProduct: {product_name}")
    print(f"Description: {product_description}")
    print("\n" + "-"*70)

    try:
        generator = MarketingAngleGenerator(ai_provider='claude')

        # User 1: Security-focused
        print("\n USER 1: Security-Focused Brand")
        print("   Brand Voice: Trustworthy, Professional")
        print("   Target Audience: Homeowners concerned about safety")

        angle1 = await generator.generate_unique_angle(
            product_name=product_name,
            product_description=product_description,
            user_brand_voice='trustworthy',
            user_target_audience='security-conscious families',
            niche='smart_home',
            avoid_angles=[]
        )

        print(f"\n   Generated Angle: {angle1['angle'].upper()}")
        print(f"   Title: {angle1['title']}")
        print(f"   Pain Point: {angle1['pain_point']}")
        print(f"   Ad Copy: {angle1.get('ad_copy', 'N/A')[:100]}...")

        # User 2: Convenience-focused
        print("\n USER 2: Convenience-Focused Brand")
        print("   Brand Voice: Friendly, Helpful")
        print("   Target Audience: Busy parents")

        angle2 = await generator.generate_unique_angle(
            product_name=product_name,
            product_description=product_description,
            user_brand_voice='friendly',
            user_target_audience='busy working parents',
            niche='smart_home',
            avoid_angles=[angle1['angle']]  # Avoid angle1
        )

        print(f"\n   Generated Angle: {angle2['angle'].upper()}")
        print(f"   Title: {angle2['title']}")
        print(f"   Pain Point: {angle2['pain_point']}")
        print(f"   Ad Copy: {angle2.get('ad_copy', 'N/A')[:100]}...")

        # User 3: Tech-focused
        print("\n USER 3: Tech-Innovation Brand")
        print("   Brand Voice: Modern, Sophisticated")
        print("   Target Audience: Tech enthusiasts")

        angle3 = await generator.generate_unique_angle(
            product_name=product_name,
            product_description=product_description,
            user_brand_voice='sophisticated',
            user_target_audience='tech-savvy early adopters',
            niche='smart_home',
            avoid_angles=[angle1['angle'], angle2['angle']]  # Avoid both
        )

        print(f"\n   Generated Angle: {angle3['angle'].upper()}")
        print(f"   Title: {angle3['title']}")
        print(f"   Pain Point: {angle3['pain_point']}")
        print(f"   Ad Copy: {angle3.get('ad_copy', 'N/A')[:100]}...")

        print("\n" + "="*70)
        print("[SUCCESS] RESULT: Same product, 3 completely different marketing approaches!")
        print("   Users won't compete directly - each targets different audiences.")
        print("="*70)

    except Exception as e:
        print(f"\n Demonstration failed: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Run all tests"""
    print("\n" + ""*70)
    print("MARKETING ANGLE GENERATOR - VERIFICATION")
    print(""*70)

    try:
        # Test 1: Service layer
        test1_passed = await test_marketing_angle_generator()

        # Test 2: API endpoints
        test2_passed = await test_api_endpoints()

        # Demonstration
        await demonstration()

        # Summary
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)
        print(f"[OK] MarketingAngleGenerator Service: {'PASSED' if test1_passed else 'FAILED'}")
        print(f"[OK] API Endpoints: {'PASSED' if test2_passed else 'FAILED'}")

        if test1_passed and test2_passed:
            print("\n" + ""*70)
            print("[LAUNCH] ALL TESTS PASSED - SYSTEM READY!")
            print(""*70)
            print("\nMarketing Angle Generator is now active:")
            print("  [OK] AI-powered unique positioning per user")
            print("  [OK] 6+ niches with tailored angles")
            print("  [OK] Prevents direct competition")
            print("  [OK] A/B testing support")
            print("\nAPI Endpoints:")
            print("  • POST /api/marketing/generate-angle")
            print("  • POST /api/marketing/generate-multiple-angles")
            print("  • GET /api/marketing/available-angles")
            return 0
        else:
            print("\n[ERROR] SOME TESTS FAILED")
            return 1

    except Exception as e:
        print(f"\n[ERROR] ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
