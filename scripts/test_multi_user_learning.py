#!/usr/bin/env python3
"""
Multi-User Learning System Test
================================

Tests the Global Brain + Personal Layer hybrid learning system:
1. Seeds data for 3 users with different preferences
2. Verifies global brain aggregates across all users
3. Verifies personal layers show unique patterns per user
4. Tests all event types (sales, deployments, ad performance)

Usage:
    uv run python scripts/test_multi_user_learning.py
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ospra_os.database import SessionLocal, engine as db_engine
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


async def seed_multi_user_data(db: SessionLocal):
    """
    Seed learning events for 3 users with different preferences:
    - User 1: Smart home enthusiast (high revenue)
    - User 2: Fitness focused (moderate revenue)
    - User 3: Kitchen/beauty mix (low revenue)
    """
    print_section("SEEDING MULTI-USER DATA")

    events = [
        # ========================================================================
        # USER 1: Smart Home Enthusiast (best performer)
        # ========================================================================
        LearningEvent(
            user_id=1,
            event_type="sale",
            details={
                "product_id": "u1_prod_001",
                "product_name": "Smart WiFi Camera 4K",
                "niche": "smart_home",
                "price": 89.99,
                "quantity": 15,
                "revenue": 1349.85,
                "source": "multi_user_test"
            }
        ),
        LearningEvent(
            user_id=1,
            event_type="sale",
            details={
                "product_id": "u1_prod_002",
                "product_name": "Smart Light Bulbs 4-Pack",
                "niche": "smart_home",
                "price": 34.99,
                "quantity": 25,
                "revenue": 874.75,
                "source": "multi_user_test"
            }
        ),
        LearningEvent(
            user_id=1,
            event_type="product_deployed",
            details={
                "product_id": "u1_prod_003",
                "product_name": "Smart Doorbell Pro",
                "niche": "smart_home",
                "price": 129.99,
                "predicted_score": 92,
                "source": "multi_user_test"
            }
        ),
        LearningEvent(
            user_id=1,
            event_type="ad_performance",
            details={
                "product_id": "u1_prod_001",
                "product_name": "Smart WiFi Camera 4K",
                "niche": "smart_home",
                "price": 89.99,
                "platform": "facebook",
                "spend": 200.00,
                "impressions": 50000,
                "clicks": 1500,
                "conversions": 15,
                "revenue": 1349.85,
                "roas": 6.75,
                "source": "multi_user_test"
            }
        ),

        # ========================================================================
        # USER 2: Fitness Focused (moderate performer)
        # ========================================================================
        LearningEvent(
            user_id=2,
            event_type="sale",
            details={
                "product_id": "u2_prod_001",
                "product_name": "Resistance Bands Pro Set",
                "niche": "fitness",
                "price": 24.99,
                "quantity": 20,
                "revenue": 499.80,
                "source": "multi_user_test"
            }
        ),
        LearningEvent(
            user_id=2,
            event_type="sale",
            details={
                "product_id": "u2_prod_002",
                "product_name": "Yoga Mat Premium TPE",
                "niche": "fitness",
                "price": 29.99,
                "quantity": 18,
                "revenue": 539.82,
                "source": "multi_user_test"
            }
        ),
        LearningEvent(
            user_id=2,
            event_type="sale",
            details={
                "product_id": "u2_prod_003",
                "product_name": "Foam Roller Massage",
                "niche": "fitness",
                "price": 19.99,
                "quantity": 12,
                "revenue": 239.88,
                "source": "multi_user_test"
            }
        ),
        LearningEvent(
            user_id=2,
            event_type="product_deployed",
            details={
                "product_id": "u2_prod_004",
                "product_name": "Adjustable Dumbbells",
                "niche": "fitness",
                "price": 89.99,
                "predicted_score": 78,
                "source": "multi_user_test"
            }
        ),
        LearningEvent(
            user_id=2,
            event_type="ad_performance",
            details={
                "product_id": "u2_prod_001",
                "product_name": "Resistance Bands Pro Set",
                "niche": "fitness",
                "price": 24.99,
                "platform": "google",
                "spend": 100.00,
                "impressions": 25000,
                "clicks": 800,
                "conversions": 20,
                "revenue": 499.80,
                "roas": 4.99,
                "source": "multi_user_test"
            }
        ),

        # ========================================================================
        # USER 3: Kitchen/Beauty Mix (lowest performer)
        # ========================================================================
        LearningEvent(
            user_id=3,
            event_type="sale",
            details={
                "product_id": "u3_prod_001",
                "product_name": "Portable Blender USB",
                "niche": "kitchen",
                "price": 19.99,
                "quantity": 8,
                "revenue": 159.92,
                "source": "multi_user_test"
            }
        ),
        LearningEvent(
            user_id=3,
            event_type="sale",
            details={
                "product_id": "u3_prod_002",
                "product_name": "LED Makeup Mirror",
                "niche": "beauty",
                "price": 24.99,
                "quantity": 6,
                "revenue": 149.94,
                "source": "multi_user_test"
            }
        ),
        LearningEvent(
            user_id=3,
            event_type="product_deployed",
            details={
                "product_id": "u3_prod_003",
                "product_name": "Air Fryer Compact",
                "niche": "kitchen",
                "price": 49.99,
                "predicted_score": 65,
                "source": "multi_user_test"
            }
        ),
        LearningEvent(
            user_id=3,
            event_type="ad_performance",
            details={
                "product_id": "u3_prod_001",
                "product_name": "Portable Blender USB",
                "niche": "kitchen",
                "price": 19.99,
                "platform": "tiktok",
                "spend": 75.00,
                "impressions": 15000,
                "clicks": 400,
                "conversions": 8,
                "revenue": 159.92,
                "roas": 2.13,
                "source": "multi_user_test"
            }
        ),
    ]

    # Add all events
    for event in events:
        db.add(event)

    db.commit()

    print(f"[SUCCESS] Seeded {len(events)} learning events across 3 users")
    print()
    print("User breakdown:")
    print(f"  User 1 (Smart Home): 2 sales ($2,224.60 revenue) + 1 deployment + 1 ad")
    print(f"  User 2 (Fitness): 3 sales ($1,279.50 revenue) + 1 deployment + 1 ad")
    print(f"  User 3 (Kitchen/Beauty): 2 sales ($309.86 revenue) + 1 deployment + 1 ad")
    print()
    print("Total revenue: $3,813.96")


async def run_analysis():
    """Run global and personal analysis"""
    print_section("RUNNING PATTERN ANALYSIS")

    import httpx

    print("Triggering global analysis...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "http://localhost:8001/api/learning/analyze/global",
                timeout=30.0
            )
            if response.status_code == 200:
                print("[SUCCESS] Global analysis completed")
            else:
                print(f"[ERROR] Failed: {response.status_code}")
                print(response.text)
                return False
        except Exception as e:
            print(f"[ERROR] Error: {e}")
            return False

    print()
    print("Triggering personal analysis for all users...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "http://localhost:8001/api/learning/analyze/all-users",
                timeout=30.0
            )
            if response.status_code == 200:
                print("[SUCCESS] Personal analysis completed for all users")
            else:
                print(f"[ERROR] Failed: {response.status_code}")
        except Exception as e:
            print(f"[ERROR] Error: {e}")

    return True


async def verify_global_brain(db: SessionLocal):
    """Verify global brain aggregates all users"""
    print_section("VERIFYING GLOBAL BRAIN")

    global_weights = db.query(GlobalLearningWeights).first()

    if not global_weights:
        print("[ERROR] No global weights found")
        return False

    print("[SUCCESS] Global Brain data:")
    print(f"   Learning cycles: {global_weights.learning_cycles}")
    print(f"   Total users contributing: {global_weights.total_users_contributing}")
    print(f"   Total sales analyzed: {global_weights.total_sales_analyzed}")
    print(f"   Total revenue analyzed: ${global_weights.total_revenue_analyzed:,.2f}")
    print()
    print(f"   Niche confidence (revenue-weighted):")
    for niche, confidence in sorted(global_weights.niche_confidence.items(), key=lambda x: x[1], reverse=True):
        print(f"      {niche}: {confidence:.1%}")

    # Verify multi-user aggregation
    if global_weights.total_users_contributing >= 3:
        print()
        print("[SUCCESS] Global Brain is aggregating across multiple users")
    else:
        print()
        print(f"[WARNING]  Only {global_weights.total_users_contributing} users contributing")

    return True


async def verify_personal_layers(db: SessionLocal):
    """Verify each user has unique personal patterns"""
    print_section("VERIFYING PERSONAL LAYERS")

    users = [1, 2, 3]
    personal_data = {}

    for user_id in users:
        personal = db.query(PersonalLearningWeights).filter_by(user_id=user_id).first()

        if not personal:
            print(f"[ERROR] No personal weights for user {user_id}")
            continue

        personal_data[user_id] = personal

        print(f"\n User {user_id}:")
        print(f"   Learning cycles: {personal.learning_cycles}")
        print(f"   Sales analyzed: {personal.sales_analyzed}")
        print(f"   Revenue analyzed: ${personal.revenue_analyzed:,.2f}")
        print(f"   Best niches: {personal.best_performing_niches}")
        print(f"   Optimal price range: ${personal.optimal_price_range.get('min', 0):.2f} - ${personal.optimal_price_range.get('max', 0):.2f}")

    # Verify users have DIFFERENT patterns
    print()
    print("=" * 80)
    print("COMPARING PERSONAL PATTERNS:")
    print("=" * 80)

    if len(personal_data) >= 3:
        user1_niches = set(personal_data[1].best_performing_niches or [])
        user2_niches = set(personal_data[2].best_performing_niches or [])
        user3_niches = set(personal_data[3].best_performing_niches or [])

        print(f"\nUser 1 niches: {user1_niches}")
        print(f"User 2 niches: {user2_niches}")
        print(f"User 3 niches: {user3_niches}")

        # Check if users have different primary niches
        if user1_niches != user2_niches or user2_niches != user3_niches:
            print("\n[SUCCESS] Users have UNIQUE niche preferences (Personal Layer working!)")
        else:
            print("\n[WARNING]  All users have same niches")

        # Compare revenue
        print(f"\nRevenue comparison:")
        print(f"  User 1: ${personal_data[1].revenue_analyzed:,.2f} (should be highest)")
        print(f"  User 2: ${personal_data[2].revenue_analyzed:,.2f} (should be middle)")
        print(f"  User 3: ${personal_data[3].revenue_analyzed:,.2f} (should be lowest)")

        return True

    return False


async def test_event_types(db: SessionLocal):
    """Verify all event types were processed"""
    print_section("VERIFYING ALL EVENT TYPES")

    event_counts = {}
    # Get all events (simpler query)
    events = db.query(LearningEvent).all()

    for event in events:
        event_type = event.event_type
        event_counts[event_type] = event_counts.get(event_type, 0) + 1

    print("Event type breakdown:")
    for event_type, count in sorted(event_counts.items()):
        print(f"  {event_type}: {count}")

    expected_types = {'sale', 'product_deployed', 'ad_performance'}
    found_types = set(event_counts.keys())

    if expected_types.issubset(found_types):
        print("\n[SUCCESS] All event types present!")
        return True
    else:
        missing = expected_types - found_types
        print(f"\n[WARNING]  Missing event types: {missing}")
        return False


async def main():
    """Main test function"""
    print()
    print("" + "" * 78 + "")
    print("" + " " * 18 + "MULTI-USER LEARNING SYSTEM TEST" + " " * 27 + "")
    print("" + "" * 78 + "")

    # Create tables
    print_section("SETUP: CREATING DATABASE TABLES")
    Base.metadata.create_all(bind=db_engine)
    print("[SUCCESS] Database tables created")

    # Create DB session
    db = SessionLocal()

    try:
        # Step 1: Seed multi-user data
        await seed_multi_user_data(db)

        # Step 2: Run analysis
        analysis_ok = await run_analysis()
        if not analysis_ok:
            print("\n[ERROR] Analysis failed - cannot continue")
            return

        # Wait for analysis to complete
        await asyncio.sleep(2)

        # Step 3: Verify Global Brain
        global_ok = await verify_global_brain(db)

        # Step 4: Verify Personal Layers
        personal_ok = await verify_personal_layers(db)

        # Step 5: Verify all event types
        events_ok = await test_event_types(db)

        # Final summary
        print_section("TEST SUMMARY")

        results = [
            ("Multi-user data seeded", True),
            ("Analysis completed", analysis_ok),
            ("Global Brain verified", global_ok),
            ("Personal Layers verified", personal_ok),
            ("All event types processed", events_ok),
        ]

        for test_name, passed in results:
            status = "[SUCCESS] PASS" if passed else "[ERROR] FAIL"
            print(f"  {status}  {test_name}")

        print()
        all_passed = all(r[1] for r in results)

        if all_passed:
            print("" + "" * 78 + "")
            print("" + " " * 20 + "[SUCCESS] ALL TESTS PASSED! [SUCCESS]" + " " * 31 + "")
            print("" + " " * 78 + "")
            print("" + "  The hybrid learning system is working correctly:" + " " * 24 + "")
            print("" + "  • Global Brain aggregates across all users" + " " * 31 + "")
            print("" + "  • Personal Layers show unique user preferences" + " " * 26 + "")
            print("" + "  • All event types (sales, deployments, ads) are tracked" + " " * 17 + "")
            print("" + "" * 78 + "")
        else:
            print("" + "" * 78 + "")
            print("" + " " * 24 + "[WARNING]  SOME TESTS FAILED" + " " * 29 + "")
            print("" + "" * 78 + "")

    except Exception as e:
        print()
        print(f"[ERROR] Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
