#!/usr/bin/env python3
"""Local test script for smart reply system."""
import json
from datetime import datetime
from app.business_hours import BusinessHours
from app.refund_processor import RefundProcessor
from app.smart_reply import SmartReplySystem
from app.settings import Settings


def test_business_hours():
    """Test operating hours detection."""
    print("=" * 60)
    print("TEST 1: Business Hours Detection")
    print("=" * 60)

    bh = BusinessHours(
        weekday_start=datetime.strptime("07:00", "%H:%M").time(),
        weekday_end=datetime.strptime("21:00", "%H:%M").time(),
        weekend_start=datetime.strptime("10:00", "%H:%M").time(),
        weekend_end=datetime.strptime("19:00", "%H:%M").time(),
        timezone="America/New_York",
    )

    # Test different times
    test_times = [
        ("2025-01-15 10:00:00", "Wednesday 10 AM EST"),  # Weekday Operating
        ("2025-01-15 22:00:00", "Wednesday 10 PM EST"),  # Quiet (after hours)
        ("2025-01-18 12:00:00", "Saturday 12 PM EST"),   # Weekend Operating
        ("2025-01-18 20:00:00", "Saturday 8 PM EST"),    # Weekend Quiet (after 7PM)
        ("2025-01-13 08:00:00", "Monday 8 AM EST"),      # Weekday Operating
        ("2025-01-19 09:00:00", "Sunday 9 AM EST"),      # Weekend Quiet (before 10AM)
    ]

    for time_str, description in test_times:
        dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
        dt = dt.replace(tzinfo=bh.timezone)
        mode = bh.get_response_mode(dt)
        is_quiet = bh.is_quiet_hours(dt)
        is_operating = bh.is_operating_hours(dt)

        print(f"\n{description}:")
        print(f"  Mode: {mode}")
        print(f"  Quiet hours: {is_quiet}")
        print(f"  Operating hours: {is_operating}")

    print("\n✅ Business hours test complete\n")


def test_refund_processor():
    """Test refund eligibility logic."""
    print("=" * 60)
    print("TEST 2: Refund Processing Logic")
    print("=" * 60)

    processor = RefundProcessor(
        max_auto_refund_amount=100.00,
        auto_refund_days_limit=15,
        require_shipped_back=True,
    )

    # Test cases
    test_cases = [
        {
            "name": "Eligible: Small order, recent, valid reason, will ship back",
            "order": {
                "total_price": "50.00",
                "created_at": "2025-10-20T10:00:00Z",
            },
            "message": "The product arrived broken. I'd like a refund and will ship it back.",
        },
        {
            "name": "Too expensive for auto-refund",
            "order": {
                "total_price": "150.00",
                "created_at": "2025-10-20T10:00:00Z",
            },
            "message": "Product is damaged. I'll return it.",
        },
        {
            "name": "Too old for auto-refund (>15 days)",
            "order": {
                "total_price": "50.00",
                "created_at": "2025-10-01T10:00:00Z",
            },
            "message": "Product is damaged. I'll ship it back.",
        },
        {
            "name": "No valid reason",
            "order": {
                "total_price": "50.00",
                "created_at": "2025-10-20T10:00:00Z",
            },
            "message": "I just don't want it anymore. Will send back.",
        },
        {
            "name": "No shipped back confirmation",
            "order": {
                "total_price": "50.00",
                "created_at": "2025-10-20T10:00:00Z",
            },
            "message": "The product is broken. I need a refund.",
        },
    ]

    for test in test_cases:
        print(f"\n{test['name']}:")
        decision = processor.should_auto_refund(test["order"], test["message"])
        print(f"  Action: {decision['action']}")
        print(f"  Eligible: {decision['eligible']}")
        print(f"  Reason: {decision['reason']}")
        if decision.get("refund_amount"):
            print(f"  Amount: ${decision['refund_amount']:.2f}")

    print("\n✅ Refund processor test complete\n")


def test_email_classification():
    """Test email classification and template selection."""
    print("=" * 60)
    print("TEST 3: Email Classification")
    print("=" * 60)

    # Load rules
    with open("data/rules.json", "r") as f:
        rules = json.load(f)

    # Load templates
    with open("data/templates.json", "r") as f:
        templates = json.load(f)

    test_emails = [
        {
            "subject": "Where is my order #1234?",
            "body": "I haven't received my package yet.",
            "expected_label": "Tracking",
        },
        {
            "subject": "Refund request",
            "body": "I'd like to return my order and get a refund.",
            "expected_label": "Return/Refund",
        },
        {
            "subject": "Product arrived broken",
            "body": "The item I received is damaged and doesn't work.",
            "expected_label": "Support",
        },
        {
            "subject": "Partnership inquiry",
            "body": "We're interested in wholesale pricing.",
            "expected_label": "VIP",
        },
    ]

    for email in test_emails:
        text = f"{email['subject']}\n{email['body']}".lower()
        matched_rule = None

        for rule in rules["rules"]:
            for keyword in rule.get("if_any", []):
                if keyword.lower() in text:
                    matched_rule = rule
                    break
            if matched_rule:
                break

        print(f"\nSubject: {email['subject']}")
        print(f"  Expected label: {email['expected_label']}")
        if matched_rule:
            print(f"  Matched label: {matched_rule['apply_label']}")
            print(f"  Template: {matched_rule.get('auto_reply_template')}")
            print(f"  ✅ Match!" if matched_rule['apply_label'] == email['expected_label'] else "  ❌ Mismatch!")
        else:
            print(f"  ❌ No rule matched!")

    print("\n✅ Email classification test complete\n")


def test_order_id_extraction():
    """Test order ID extraction from emails."""
    print("=" * 60)
    print("TEST 4: Order ID Extraction")
    print("=" * 60)

    processor = RefundProcessor()

    test_cases = [
        ("Where is order #1234?", "Should extract #1234"),
        ("My order number is 5678", "Should extract #5678"),
        ("Order: #9999", "Should extract #9999"),
        ("No order number here", "Should return None"),
    ]

    for text, description in test_cases:
        order_id = processor.extract_order_id_from_message("", text)
        print(f"\n{description}:")
        print(f"  Input: \"{text}\"")
        print(f"  Extracted: {order_id}")

    print("\n✅ Order ID extraction test complete\n")


def test_template_rendering():
    """Test template variable replacement."""
    print("=" * 60)
    print("TEST 5: Template Variable Replacement")
    print("=" * 60)

    with open("data/templates.json", "r") as f:
        templates = json.load(f)

    test_data = {
        "name": "John",
        "order_id": "#1234",
        "ticket_id": "TKT-5678",
    }

    for template_name, template in templates.items():
        print(f"\nTemplate: {template_name}")
        body = template["body"]

        # Replace variables
        for var, value in test_data.items():
            body = body.replace(f"{{{{{var}}}}}", value)

        print(f"  Subject: {template['subject']}")
        print(f"  Has name: {'{{name}}' in template['body']}")
        print(f"  Rendered preview: {body[:100]}...")

    print("\n✅ Template rendering test complete\n")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("OUBON SHOP SMART REPLY SYSTEM - LOCAL TESTS")
    print("=" * 60 + "\n")

    try:
        test_business_hours()
        test_refund_processor()
        test_email_classification()
        test_order_id_extraction()
        test_template_rendering()

        print("=" * 60)
        print("✅ ALL TESTS COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Set up environment variables (.env file)")
        print("2. Test with real Shopify API (optional)")
        print("3. Test with real Gmail API (optional)")
        print("4. Deploy to Render")
        print()

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
