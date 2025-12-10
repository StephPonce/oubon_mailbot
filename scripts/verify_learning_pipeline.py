#!/usr/bin/env python3
"""
Learning Pipeline Verification Script
======================================

This script tests the complete learning pipeline end-to-end:
1. Seeds test data into learning_events
2. Runs analysis to calculate patterns
3. Queries the database to verify data was created
4. Tests Claude chat to confirm it references real data

Usage:
    uv run python scripts/verify_learning_pipeline.py
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
import httpx

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ospra_os.database.multi_store_models import SessionLocal, engine as db_engine
from ospra_os.learning.hybrid_learning_engine import (
    LearningEvent,
    GlobalLearningWeights,
    PersonalLearningWeights,
    Base
)


def print_section(title):
    """Print a section header"""
    print()
    print("=" * 80)
    print(f"  {title}")
    print("=" * 80)


async def seed_test_data(db: SessionLocal):
    """Seed test learning events"""
    print_section("STEP 1: SEEDING TEST DATA")

    test_events = [
        # Smart home sales (high performing)
        LearningEvent(
            user_id=1,
            event_type="sale",
            details={
                "product_id": "prod_001",
                "product_name": "Smart WiFi LED Bulb",
                "niche": "smart_home",
                "price": 24.99,
                "quantity": 12,
                "revenue": 299.88,
                "source": "test_data"
            }
        ),
        LearningEvent(
            user_id=1,
            event_type="sale",
            details={
                "product_id": "prod_002",
                "product_name": "Security Camera WiFi",
                "niche": "smart_home",
                "price": 39.99,
                "quantity": 8,
                "revenue": 319.92,
                "source": "test_data"
            }
        ),
        # Fitness sales (moderate performing)
        LearningEvent(
            user_id=1,
            event_type="sale",
            details={
                "product_id": "prod_003",
                "product_name": "Resistance Bands Set",
                "niche": "fitness",
                "price": 19.99,
                "quantity": 5,
                "revenue": 99.95,
                "source": "test_data"
            }
        ),
        # Product deployment events
        LearningEvent(
            user_id=1,
            event_type="product_deployed",
            details={
                "product_id": "prod_004",
                "product_name": "Portable Blender",
                "niche": "kitchen",
                "price": 34.99,
                "predicted_score": 78,
                "source": "test_data"
            }
        ),
        # Ad performance event
        LearningEvent(
            user_id=1,
            event_type="ad_performance",
            details={
                "product_id": "prod_001",
                "product_name": "Smart WiFi LED Bulb",
                "niche": "smart_home",
                "price": 24.99,
                "platform": "facebook",
                "spend": 50.00,
                "impressions": 10000,
                "clicks": 250,
                "conversions": 12,
                "revenue": 299.88,
                "roas": 5.99,
                "source": "test_data"
            }
        )
    ]

    # Add all events
    for event in test_events:
        db.add(event)

    db.commit()

    print(f"✅ Seeded {len(test_events)} test learning events")
    print()
    print("Event breakdown:")
    print(f"  - Sales: 3")
    print(f"  - Deployments: 1")
    print(f"  - Ad Performance: 1")
    print()
    print("Products by niche:")
    print(f"  - smart_home: 2 sales ($619.80 revenue)")
    print(f"  - fitness: 1 sale ($99.95 revenue)")
    print(f"  - kitchen: 1 deployment")


async def run_analysis():
    """Run pattern analysis"""
    print_section("STEP 2: RUNNING PATTERN ANALYSIS")

    print("Triggering global analysis...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "http://localhost:8001/api/learning/analyze/global",
                timeout=30.0
            )
            if response.status_code == 200:
                print("✅ Global analysis completed")
            else:
                print(f"❌ Global analysis failed: {response.status_code}")
                print(response.text)
        except Exception as e:
            print(f"❌ Failed to trigger analysis: {e}")
            print("   Make sure the backend is running on port 8001")
            return False

    print()
    print("Triggering personal analysis for user 1...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "http://localhost:8001/api/learning/analyze/personal/1",
                timeout=30.0
            )
            if response.status_code == 200:
                print("✅ Personal analysis completed")
            else:
                print(f"❌ Personal analysis failed: {response.status_code}")
        except Exception as e:
            print(f"❌ Failed to trigger analysis: {e}")

    return True


async def verify_database(db: SessionLocal):
    """Verify data was created in database"""
    print_section("STEP 3: VERIFYING DATABASE")

    # Check learning events
    events_count = db.query(LearningEvent).count()
    print(f"Learning events: {events_count}")

    # Check global weights
    global_weights = db.query(GlobalLearningWeights).first()
    if global_weights:
        print("✅ Global weights exist")
        print(f"   Learning cycles: {global_weights.learning_cycles}")
        print(f"   Sales analyzed: {global_weights.total_sales_analyzed}")
        print(f"   Revenue analyzed: ${global_weights.total_revenue_analyzed:.2f}")
        print(f"   Niche confidence: {global_weights.niche_confidence}")
    else:
        print("❌ No global weights found")
        return False

    # Check personal weights
    personal_weights = db.query(PersonalLearningWeights).filter_by(user_id=1).first()
    if personal_weights:
        print("✅ Personal weights exist for user 1")
        print(f"   Learning cycles: {personal_weights.learning_cycles}")
        print(f"   Sales analyzed: {personal_weights.sales_analyzed}")
        print(f"   Best niches: {personal_weights.best_performing_niches}")
        print(f"   Optimal price range: {personal_weights.optimal_price_range}")
    else:
        print("❌ No personal weights found for user 1")
        return False

    return True


async def test_claude_chat():
    """Test Claude chat with learning context"""
    print_section("STEP 4: TESTING CLAUDE CHAT")

    print("Asking Claude: 'What products should I sell based on my history?'")
    print()

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "http://localhost:8001/api/dashboard/v2/claude/chat",
                json={
                    "message": "What products should I sell based on my sales history? Be specific about which niches performed best.",
                    "user_id": 1
                },
                timeout=60.0
            )

            if response.status_code == 200:
                data = response.json()
                claude_response = data.get("response", "")

                print("Claude's response:")
                print("-" * 80)
                print(claude_response)
                print("-" * 80)
                print()

                # Check if Claude mentions specific data from our test
                indicators = [
                    ("smart_home" in claude_response.lower() or "smart home" in claude_response.lower(), "smart_home niche"),
                    ("fitness" in claude_response.lower(), "fitness niche"),
                    ("24.99" in claude_response or "$24" in claude_response or "$25" in claude_response, "price ($24.99)"),
                    ("39.99" in claude_response or "$39" in claude_response or "$40" in claude_response, "price ($39.99)"),
                    ("619" in claude_response or "600" in claude_response, "revenue (~$620)"),
                ]

                print("Verification:")
                references_count = 0
                for found, description in indicators:
                    if found:
                        print(f"  ✅ References {description}")
                        references_count += 1
                    else:
                        print(f"  ⚠️  Does not reference {description}")

                print()
                if references_count >= 2:
                    print("✅ Claude appears to be using REAL data!")
                    print(f"   Found {references_count}/{len(indicators)} expected data points")
                    return True
                else:
                    print("⚠️  Claude may not be using real data")
                    print(f"   Only found {references_count}/{len(indicators)} expected data points")
                    print("   This could mean:")
                    print("   1. Learning context is not being passed correctly")
                    print("   2. Database is still empty")
                    print("   3. Claude is generating plausible-sounding data")
                    return False

            else:
                print(f"❌ Chat request failed: {response.status_code}")
                print(response.text)
                return False

        except Exception as e:
            print(f"❌ Failed to test Claude chat: {e}")
            return False


async def get_learning_insights():
    """Get learning insights from API"""
    print_section("STEP 5: CHECKING LEARNING INSIGHTS")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                "http://localhost:8001/api/learning/insights/1",
                timeout=10.0
            )

            if response.status_code == 200:
                insights = response.json()
                print("Learning insights for user 1:")
                print()
                import json
                print(json.dumps(insights, indent=2))
                return True
            else:
                print(f"❌ Failed to get insights: {response.status_code}")
                return False

        except Exception as e:
            print(f"❌ Failed to get insights: {e}")
            return False


async def main():
    """Main verification function"""
    print()
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 20 + "LEARNING PIPELINE VERIFICATION" + " " * 28 + "║")
    print("╚" + "═" * 78 + "╝")

    # Create tables
    print_section("SETUP: CREATING DATABASE TABLES")
    Base.metadata.create_all(bind=db_engine)
    print("✅ Database tables created")

    # Create DB session
    db = SessionLocal()

    try:
        # Step 1: Seed test data
        await seed_test_data(db)

        # Step 2: Run analysis
        analysis_ok = await run_analysis()
        if not analysis_ok:
            print()
            print("❌ Analysis failed - cannot continue verification")
            return

        # Give analysis a moment to complete
        await asyncio.sleep(2)

        # Step 3: Verify database
        db_ok = await verify_database(db)
        if not db_ok:
            print()
            print("❌ Database verification failed")
            return

        # Step 4: Test Claude chat
        claude_ok = await test_claude_chat()

        # Step 5: Get learning insights
        insights_ok = await get_learning_insights()

        # Final summary
        print_section("VERIFICATION SUMMARY")

        results = [
            ("Test data seeded", True),
            ("Analysis completed", analysis_ok),
            ("Database verified", db_ok),
            ("Claude uses real data", claude_ok),
            ("Insights API works", insights_ok)
        ]

        for test_name, passed in results:
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"  {status}  {test_name}")

        print()
        all_passed = all(r[1] for r in results)

        if all_passed:
            print("╔" + "═" * 78 + "╗")
            print("║" + " " * 22 + "✅ ALL TESTS PASSED! ✅" + " " * 29 + "║")
            print("║" + " " * 78 + "║")
            print("║" + "  The learning pipeline is working correctly!              " + " " * 18 + "║")
            print("║" + "  Claude is now using REAL historical data for recommendations." + " " * 13 + "║")
            print("╚" + "═" * 78 + "╝")
        else:
            print("╔" + "═" * 78 + "╗")
            print("║" + " " * 22 + "⚠️  SOME TESTS FAILED" + " " * 31 + "║")
            print("║" + " " * 78 + "║")
            print("║" + "  Check the output above for details on what failed." + " " * 24 + "║")
            print("╚" + "═" * 78 + "╝")

    except Exception as e:
        print()
        print(f"❌ Verification failed with error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
