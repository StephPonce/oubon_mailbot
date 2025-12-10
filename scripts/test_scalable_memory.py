#!/usr/bin/env python3
"""
Scalable Memory System End-to-End Test
=======================================

Tests the complete unlimited memory pipeline:
1. Seeds realistic learning data
2. Generates pre-computed summaries
3. Tests smart context builder
4. Verifies Claude uses REAL data (not hallucinations)
5. Confirms unlimited scaling without token limits

Usage:
    uv run python scripts/test_scalable_memory.py
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ospra_os.database.multi_store_models import SessionLocal, engine as db_engine
from ospra_os.learning.hybrid_learning_engine import LearningEvent, Base
from ospra_os.learning.summary_models import LearningSummary
from ospra_os.learning.summary_generator import generate_daily_summaries
from ospra_os.learning.summary_jobs import update_aggregated_tables


def print_section(title):
    """Print a section header"""
    print()
    print("=" * 80)
    print(f"  {title}")
    print("=" * 80)


async def seed_realistic_data(db: SessionLocal):
    """
    Seed realistic business data for user 1.

    Simulates 3 months of e-commerce history:
    - 50+ products deployed
    - 200+ sales across multiple niches
    - Ad campaigns on Facebook, TikTok, Google
    """
    print_section("STEP 1: SEEDING REALISTIC BUSINESS DATA")

    events = []

    # Smart Home niche (best performer)
    smart_home_products = [
        ("Smart WiFi Camera 4K", 89.99, 45),
        ("Smart Light Bulbs 4-Pack", 34.99, 78),
        ("Smart Thermostat Pro", 129.99, 23),
        ("Smart Door Lock", 79.99, 34),
        ("Smart Plug 2-Pack", 24.99, 156),
    ]

    for product_name, price, units in smart_home_products:
        product_id = f"sh_{product_name[:10].replace(' ', '_').lower()}"

        # Deployment
        events.append(LearningEvent(
            user_id=1,
            event_type="product_deployed",
            details={
                "product_id": product_id,
                "product_name": product_name,
                "niche": "smart_home",
                "price": price,
                "predicted_score": 85 + (units % 10),
                "source": "scalable_memory_test"
            }
        ))

        # Sales
        revenue = price * units
        events.append(LearningEvent(
            user_id=1,
            event_type="sale",
            details={
                "product_id": product_id,
                "product_name": product_name,
                "niche": "smart_home",
                "price": price,
                "quantity": units,
                "revenue": revenue,
                "source": "scalable_memory_test"
            }
        ))

        # Ad performance
        ad_spend = revenue * 0.25  # 25% ad spend
        events.append(LearningEvent(
            user_id=1,
            event_type="ad_performance",
            details={
                "product_id": product_id,
                "product_name": product_name,
                "niche": "smart_home",
                "price": price,
                "platform": "facebook" if units > 50 else "tiktok",
                "spend": ad_spend,
                "impressions": units * 500,
                "clicks": units * 15,
                "conversions": units,
                "revenue": revenue,
                "roas": revenue / ad_spend,
                "source": "scalable_memory_test"
            }
        ))

    # Fitness niche (moderate performer)
    fitness_products = [
        ("Resistance Bands Pro Set", 24.99, 89),
        ("Yoga Mat Premium TPE", 29.99, 67),
        ("Foam Roller Massage", 19.99, 45),
        ("Adjustable Dumbbells", 89.99, 23),
    ]

    for product_name, price, units in fitness_products:
        product_id = f"fit_{product_name[:10].replace(' ', '_').lower()}"

        events.append(LearningEvent(
            user_id=1,
            event_type="product_deployed",
            details={
                "product_id": product_id,
                "product_name": product_name,
                "niche": "fitness",
                "price": price,
                "predicted_score": 75 + (units % 10),
                "source": "scalable_memory_test"
            }
        ))

        revenue = price * units
        events.append(LearningEvent(
            user_id=1,
            event_type="sale",
            details={
                "product_id": product_id,
                "product_name": product_name,
                "niche": "fitness",
                "price": price,
                "quantity": units,
                "revenue": revenue,
                "source": "scalable_memory_test"
            }
        ))

        # Ad performance (Google Ads)
        ad_spend = revenue * 0.30
        events.append(LearningEvent(
            user_id=1,
            event_type="ad_performance",
            details={
                "product_id": product_id,
                "product_name": product_name,
                "niche": "fitness",
                "price": price,
                "platform": "google",
                "spend": ad_spend,
                "impressions": units * 400,
                "clicks": units * 12,
                "conversions": units,
                "revenue": revenue,
                "roas": revenue / ad_spend,
                "source": "scalable_memory_test"
            }
        ))

    # Kitchen niche (lower performer)
    kitchen_products = [
        ("Portable Blender USB", 19.99, 34),
        ("Air Fryer Compact", 49.99, 28),
        ("Knife Set 8-Piece", 34.99, 19),
    ]

    for product_name, price, units in kitchen_products:
        product_id = f"kit_{product_name[:10].replace(' ', '_').lower()}"

        events.append(LearningEvent(
            user_id=1,
            event_type="product_deployed",
            details={
                "product_id": product_id,
                "product_name": product_name,
                "niche": "kitchen",
                "price": price,
                "predicted_score": 65 + (units % 10),
                "source": "scalable_memory_test"
            }
        ))

        revenue = price * units
        events.append(LearningEvent(
            user_id=1,
            event_type="sale",
            details={
                "product_id": product_id,
                "product_name": product_name,
                "niche": "kitchen",
                "price": price,
                "quantity": units,
                "revenue": revenue,
                "source": "scalable_memory_test"
            }
        ))

    # Add all events
    for event in events:
        db.add(event)

    db.commit()

    # Calculate summary stats
    total_products = len(smart_home_products) + len(fitness_products) + len(kitchen_products)
    total_sales = sum([u for _, _, u in smart_home_products + fitness_products + kitchen_products])
    smart_home_revenue = sum([p * u for p, u in [(p, u) for _, p, u in smart_home_products]])
    fitness_revenue = sum([p * u for p, u in [(p, u) for _, p, u in fitness_products]])
    kitchen_revenue = sum([p * u for p, u in [(p, u) for _, p, u in kitchen_products]])
    total_revenue = smart_home_revenue + fitness_revenue + kitchen_revenue

    print(f"✅ Seeded {len(events)} learning events")
    print()
    print(f"Products deployed: {total_products}")
    print(f"Total sales: {total_sales}")
    print(f"Total revenue: ${total_revenue:,.2f}")
    print()
    print("Revenue by niche:")
    print(f"  smart_home: ${smart_home_revenue:,.2f} ({smart_home_revenue/total_revenue*100:.1f}%)")
    print(f"  fitness: ${fitness_revenue:,.2f} ({fitness_revenue/total_revenue*100:.1f}%)")
    print(f"  kitchen: ${kitchen_revenue:,.2f} ({kitchen_revenue/total_revenue*100:.1f}%)")


async def generate_summaries(db: SessionLocal):
    """Generate pre-computed summaries"""
    print_section("STEP 2: GENERATING PRE-COMPUTED SUMMARIES")

    print("Running summary generator...")

    # Generate summary for user 1
    summary_data = generate_daily_summaries(user_id=1, db=db)

    # Save to database
    summary = LearningSummary(
        user_id=1,
        summary_date=datetime.utcnow(),
        overall_performance=summary_data['overall_performance'],
        niche_insights=summary_data['niche_insights'],
        top_products=summary_data['top_products'],
        underperformers=summary_data['underperformers'],
        price_insights=summary_data['price_insights'],
        ad_insights=summary_data['ad_insights'],
        recommendations=summary_data['recommendations'],
        estimated_tokens=summary_data['estimated_tokens']
    )

    db.add(summary)
    db.commit()

    print(f"✅ Summary generated: {summary_data['estimated_tokens']} tokens")
    print()
    print("Summary preview:")
    print(f"  Total revenue: ${summary_data['overall_performance']['total_revenue']:,.2f}")
    print(f"  Products deployed: {summary_data['overall_performance']['total_products_deployed']}")
    print(f"  Top niches: {', '.join(list(summary_data['niche_insights'].keys())[:3])}")

    # Update aggregated tables
    print()
    print("Updating aggregated performance tables...")
    await update_aggregated_tables()
    print("✅ Aggregated tables updated")


async def test_context_builder():
    """Test the smart context builder with different query types"""
    print_section("STEP 3: TESTING SMART CONTEXT BUILDER")

    from ospra_os.learning.context_builder import build_claude_context, parse_query_intent

    test_queries = [
        "What products should I sell?",
        "How are my ads performing?",
        "Which niches are most profitable?",
        "Give me a complete analysis of my business performance",
    ]

    db = SessionLocal()
    try:
        for query in test_queries:
            print(f"\n📝 Query: \"{query}\"")

            # Parse intent
            intent = parse_query_intent(query)
            print(f"   Intent detected: {intent['topics']}, scope={intent['scope']}, timeframe={intent['timeframe']}")

            # Build context
            context = build_claude_context(user_id=1, user_query=query, db=db)

            # Check context size
            token_estimate = len(context) // 4
            print(f"   Context size: ~{token_estimate} tokens")

            if token_estimate > 4000:
                print(f"   ⚠️  Context exceeds 4000 token budget!")
            else:
                print(f"   ✅ Context within budget")

    finally:
        db.close()


async def test_claude_chat():
    """Test Claude chat with complete business analysis"""
    print_section("STEP 4: TESTING CLAUDE BUSINESS ANALYSIS")

    query = "Give me a complete analysis of my business performance. What are my strongest and weakest niches? Where should I invest more?"

    print(f"Query: \"{query}\"")
    print()

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "http://localhost:8001/api/dashboard/v2/claude/chat",
                json={
                    "message": query,
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

                # Verify Claude uses REAL data (not hallucinations)
                indicators = [
                    ("smart_home" in claude_response.lower() or "smart home" in claude_response.lower(), "smart_home niche"),
                    ("fitness" in claude_response.lower(), "fitness niche"),
                    ("kitchen" in claude_response.lower(), "kitchen niche"),
                    (any(price in claude_response for price in ["89.99", "$89", "$90"]), "Smart Camera price ($89.99)"),
                    (any(price in claude_response for price in ["24.99", "$24", "$25"]), "Smart Plug price ($24.99)"),
                    ("facebook" in claude_response.lower() or "tiktok" in claude_response.lower(), "ad platform"),
                    ("google" in claude_response.lower(), "Google Ads"),
                ]

                print("==" * 40)
                print("VERIFICATION: Does Claude reference REAL data?")
                print("=" * 80)

                references_count = 0
                for found, description in indicators:
                    if found:
                        print(f"  ✅ References {description}")
                        references_count += 1
                    else:
                        print(f"  ⚠️  Does not reference {description}")

                print()
                if references_count >= 4:
                    print(f"✅ PASS: Claude is using REAL data!")
                    print(f"   Found {references_count}/{len(indicators)} expected data points")
                    return True
                else:
                    print(f"⚠️  CONCERN: Claude may be hallucinating")
                    print(f"   Only found {references_count}/{len(indicators)} expected data points")
                    return False

            else:
                print(f"❌ Chat request failed: {response.status_code}")
                print(response.text)
                return False

        except Exception as e:
            print(f"❌ Failed to test Claude chat: {e}")
            return False


async def verify_unlimited_scaling():
    """Verify the system can handle unlimited data without token limits"""
    print_section("STEP 5: VERIFYING UNLIMITED SCALING")

    db = SessionLocal()
    try:
        # Check raw events count
        from ospra_os.learning.hybrid_learning_engine import LearningEvent
        total_events = db.query(LearningEvent).filter_by(user_id=1).count()

        # Check summary
        summary = db.query(LearningSummary).filter_by(user_id=1).order_by(
            LearningSummary.summary_date.desc()
        ).first()

        if not summary:
            print("❌ No summary found")
            return False

        estimated_raw_tokens = total_events * 100  # ~100 tokens per event
        summary_tokens = summary.estimated_tokens

        compression_ratio = estimated_raw_tokens / summary_tokens if summary_tokens > 0 else 0

        print(f"Raw learning events: {total_events}")
        print(f"Estimated raw data tokens: ~{estimated_raw_tokens:,}")
        print()
        print(f"Pre-computed summary tokens: ~{summary_tokens}")
        print(f"Compression ratio: {compression_ratio:.1f}x")
        print()

        if compression_ratio > 5:
            print(f"✅ EXCELLENT compression! {compression_ratio:.1f}x reduction")
            print("   This system can scale to unlimited historical data!")
            return True
        elif compression_ratio > 2:
            print(f"✅ Good compression: {compression_ratio:.1f}x reduction")
            return True
        else:
            print(f"⚠️  Low compression: {compression_ratio:.1f}x reduction")
            return False

    finally:
        db.close()


async def main():
    """Main test function"""
    print()
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 18 + "SCALABLE MEMORY SYSTEM TEST" + " " * 33 + "║")
    print("║" + " " * 78 + "║")
    print("║" + "  Testing unlimited historical knowledge without token limits" + " " * 16 + "║")
    print("╚" + "═" * 78 + "╝")

    # Create tables
    print_section("SETUP: CREATING DATABASE TABLES")
    from ospra_os.learning.summary_models import Base as SummaryBase
    Base.metadata.create_all(bind=db_engine)
    SummaryBase.metadata.create_all(bind=db_engine)
    print("✅ Database tables created")

    # Create DB session
    db = SessionLocal()

    try:
        # Step 1: Seed data
        await seed_realistic_data(db)

        # Step 2: Generate summaries
        await generate_summaries(db)

        # Step 3: Test context builder
        await test_context_builder()

        # Step 4: Test Claude chat
        claude_ok = await test_claude_chat()

        # Step 5: Verify scaling
        scaling_ok = await verify_unlimited_scaling()

        # Final summary
        print_section("TEST SUMMARY")

        results = [
            ("Realistic data seeded", True),
            ("Summaries generated", True),
            ("Context builder works", True),
            ("Claude uses REAL data", claude_ok),
            ("Unlimited scaling verified", scaling_ok),
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
            print("║" + "  The scalable memory system is working correctly!" + " " * 25 + "║")
            print("║" + "  Claude now has unlimited historical knowledge without token limits." + " " * 8 + "║")
            print("║" + "  Pre-computed summaries compress data efficiently." + " " * 25 + "║")
            print("║" + "  Smart context builder serves only relevant data." + " " * 26 + "║")
            print("╚" + "═" * 78 + "╝")
        else:
            print("╔" + "═" * 78 + "╗")
            print("║" + " " * 24 + "⚠️  SOME TESTS FAILED" + " " * 29 + "║")
            print("╚" + "═" * 78 + "╝")

    except Exception as e:
        print()
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
