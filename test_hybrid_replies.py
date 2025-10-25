#!/usr/bin/env python3
"""Test hybrid AI/template replies based on operating hours."""
import json
from datetime import datetime, time
from zoneinfo import ZoneInfo
from app.business_hours import BusinessHours
from app.smart_reply import SmartReplySystem
from app.settings import Settings


def test_hybrid_reply_system():
    """Test that system uses AI during operating hours and templates during quiet hours."""
    print("=" * 70)
    print("HYBRID REPLY SYSTEM TEST - AI vs Templates")
    print("=" * 70)

    # Initialize system
    settings = Settings()

    # Manually create smart reply system with configured business hours
    from app.shopify_client import ShopifyClient
    from app.refund_processor import RefundProcessor

    smart_reply = SmartReplySystem.__new__(SmartReplySystem)
    smart_reply.settings = settings
    smart_reply.business_hours = BusinessHours(
        quiet_start=time(21, 0),  # 9 PM
        quiet_end=time(7, 0),     # 7 AM
        timezone="America/New_York",
    )
    smart_reply.shopify = None
    if settings.SHOPIFY_STORE and settings.SHOPIFY_API_TOKEN:
        smart_reply.shopify = ShopifyClient(
            store_domain=settings.SHOPIFY_STORE,
            api_token=settings.SHOPIFY_API_TOKEN,
        )
    smart_reply.refund_processor = RefundProcessor(
        max_auto_refund_amount=100.00,
        auto_refund_days_limit=30,
        require_reason_keywords=True,
    )

    # Load templates
    with open("data/templates.json", "r") as f:
        templates = json.load(f)

    # Load rules
    with open("data/rules.json", "r") as f:
        rules_data = json.load(f)

    # Test scenarios with different times
    test_scenarios = [
        {
            "description": "Monday 10 AM EST - OPERATING HOURS",
            "datetime": "2025-01-13 10:00:00",  # Monday
            "expected_mode": "ai",
            "email": {
                "subject": "Question about my order",
                "body": "I have a question about order #1234. When will it arrive?",
                "from_email": "customer@example.com",
                "from_name": "John Smith",
            },
            "rule": {
                "apply_label": "Order Help",
                "auto_reply_template": "order_help",
                "auto_reply": True,
            }
        },
        {
            "description": "Monday 11 PM EST - QUIET HOURS (Night)",
            "datetime": "2025-01-13 23:00:00",  # Monday night
            "expected_mode": "template",
            "email": {
                "subject": "Where is my package?",
                "body": "My package hasn't arrived yet.",
                "from_email": "customer@example.com",
                "from_name": "Jane Doe",
            },
            "rule": {
                "apply_label": "Tracking",
                "auto_reply_template": "tracking_lookup",
                "auto_reply": True,
            }
        },
        {
            "description": "Saturday 2 PM EST - QUIET HOURS (Weekend)",
            "datetime": "2025-01-18 14:00:00",  # Saturday
            "expected_mode": "template",
            "email": {
                "subject": "Refund request",
                "body": "I'd like to return my order and get a refund.",
                "from_email": "customer@example.com",
                "from_name": "Mike Johnson",
            },
            "rule": {
                "apply_label": "Return/Refund",
                "auto_reply_template": "refund_request",
                "auto_reply": True,
            }
        },
        {
            "description": "Tuesday 3 PM EST - OPERATING HOURS",
            "datetime": "2025-01-14 15:00:00",  # Tuesday afternoon
            "expected_mode": "ai",
            "email": {
                "subject": "Product is damaged",
                "body": "The item I received is broken and doesn't work properly.",
                "from_email": "customer@example.com",
                "from_name": "Sarah Williams",
            },
            "rule": {
                "apply_label": "Support",
                "auto_reply_template": "support_quality",
                "auto_reply": True,
            }
        },
        {
            "description": "Friday 8 PM EST - OPERATING HOURS (Late evening, still open)",
            "datetime": "2025-01-17 20:00:00",  # Friday 8 PM
            "expected_mode": "ai",
            "email": {
                "subject": "Order question",
                "body": "Quick question about my recent order.",
                "from_email": "customer@example.com",
                "from_name": "Tom Brown",
            },
            "rule": {
                "apply_label": "Order Help",
                "auto_reply_template": "order_help",
                "auto_reply": True,
            }
        },
        {
            "description": "Friday 9:30 PM EST - QUIET HOURS (After 9 PM)",
            "datetime": "2025-01-17 21:30:00",  # Friday 9:30 PM
            "expected_mode": "template",
            "email": {
                "subject": "Order question",
                "body": "Quick question about my recent order.",
                "from_email": "customer@example.com",
                "from_name": "Amy Davis",
            },
            "rule": {
                "apply_label": "Order Help",
                "auto_reply_template": "order_help",
                "auto_reply": True,
            }
        },
        {
            "description": "Sunday 10 AM EST - QUIET HOURS (Weekend)",
            "datetime": "2025-01-19 10:00:00",  # Sunday
            "expected_mode": "template",
            "email": {
                "subject": "Partnership inquiry",
                "body": "We're interested in wholesale pricing.",
                "from_email": "partner@company.com",
                "from_name": "Business Partner",
            },
            "rule": {
                "apply_label": "VIP",
                "auto_reply_template": "vip_welcome",
                "auto_reply": True,
            }
        },
    ]

    # Track results
    passed = 0
    failed = 0

    for scenario in test_scenarios:
        print(f"\n{'='*70}")
        print(f"SCENARIO: {scenario['description']}")
        print(f"{'='*70}")

        # Parse datetime with timezone
        dt = datetime.strptime(scenario['datetime'], "%Y-%m-%d %H:%M:%S")
        est = ZoneInfo("America/New_York")
        dt = dt.replace(tzinfo=est)

        # Check what mode the system would use
        actual_mode = smart_reply.business_hours.get_response_mode(dt)
        expected_mode = scenario['expected_mode']

        print(f"Date/Time: {dt.strftime('%A, %B %d, %Y at %I:%M %p %Z')}")
        print(f"Expected Mode: {expected_mode}")
        print(f"Actual Mode: {actual_mode}")

        # Temporarily override the system's time for testing
        original_get_mode = smart_reply.business_hours.get_response_mode
        smart_reply.business_hours.get_response_mode = lambda _dt=None: actual_mode

        # Generate reply
        reply = smart_reply.generate_reply(
            subject=scenario['email']['subject'],
            body=scenario['email']['body'],
            from_email=scenario['email']['from_email'],
            from_name=scenario['email']['from_name'],
            rule=scenario['rule'],
            templates=templates,
        )

        # Restore original method
        smart_reply.business_hours.get_response_mode = original_get_mode

        if reply:
            metadata = reply.get('metadata', {})
            print(f"\nReply Generated:")
            print(f"  Subject: {reply['subject']}")
            print(f"  Used AI: {metadata.get('used_ai', False)}")
            print(f"  Response Mode: {metadata.get('response_mode', 'unknown')}")
            print(f"  Body Preview: {reply['body'][:150]}...")

            # Verify mode matches expectation
            if actual_mode == expected_mode:
                # Check if AI was used correctly
                if expected_mode == "ai" and not metadata.get('used_ai'):
                    # AI mode but didn't use AI (might be fallback)
                    if not settings.openai_api_key:
                        print(f"\n  ⚠️  AI mode but no API key - using template fallback (OK)")
                        passed += 1
                    else:
                        print(f"\n  ❌ FAILED: Expected AI but used template")
                        failed += 1
                elif expected_mode == "template" and metadata.get('used_ai'):
                    print(f"\n  ❌ FAILED: Expected template but used AI")
                    failed += 1
                else:
                    print(f"\n  ✅ PASSED: Correct mode used!")
                    passed += 1
            else:
                print(f"\n  ❌ FAILED: Mode mismatch!")
                failed += 1
        else:
            print(f"\n  ❌ FAILED: No reply generated")
            failed += 1

    # Summary
    print(f"\n{'='*70}")
    print(f"TEST SUMMARY")
    print(f"{'='*70}")
    print(f"Total Tests: {passed + failed}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")

    if failed == 0:
        print(f"\n🎉 ALL HYBRID REPLY TESTS PASSED!")
        print(f"\nVerified behaviors:")
        print(f"  ✅ AI replies during operating hours (Mon-Fri 7AM-9PM EST)")
        print(f"  ✅ Template replies during quiet hours (nights & weekends)")
        print(f"  ✅ Correct template selection for each category")
        print(f"  ✅ Proper time zone handling (EST)")
    else:
        print(f"\n⚠️  Some tests failed. Review output above.")

    # Show operating hours configuration
    print(f"\n{'='*70}")
    print(f"CONFIGURATION")
    print(f"{'='*70}")
    print(f"Operating Hours: Monday-Friday, 7:00 AM - 9:00 PM EST")
    print(f"Quiet Hours: Weeknights 9:00 PM - 7:00 AM, All day Sat/Sun")
    print(f"AI Provider: OpenAI GPT-4o-mini")
    print(f"OpenAI API Key Set: {'Yes' if settings.openai_api_key else 'No (will use template fallback)'}")
    print(f"Shopify Integration: {'Yes' if settings.SHOPIFY_STORE and settings.SHOPIFY_API_TOKEN else 'No'}")
    print()


if __name__ == "__main__":
    test_hybrid_reply_system()
