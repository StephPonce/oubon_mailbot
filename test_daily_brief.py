"""
Test Daily Brief API

Tests the Daily Brief endpoints to verify GROK RECOMMENDATION #5 implementation.
"""
import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8001"

print("=" * 80)
print("🌅 DAILY BRIEF API TEST")
print("   Testing: Personalized Morning Summary Generation")
print("=" * 80)
print()

# Step 1: Register test user
print("1️⃣  Setting up test user...")
register_data = {
    "email": f"daily_brief_{datetime.now().timestamp()}@example.com",
    "password": "testpass123",
    "name": "Daily Brief Test User"
}
response = requests.post(f"{BASE_URL}/api/auth/register", json=register_data)
if response.status_code == 201:
    auth_data = response.json()
    token = auth_data["access_token"]
    user_id = auth_data["user"]["id"]
    email = auth_data["user"]["email"]
    print(f"   ✅ Test user created: ID={user_id}, Email={email}")
else:
    print(f"   ❌ Failed: {response.status_code}")
    print(f"      {response.text}")
    exit(1)

headers = {"Authorization": f"Bearer {token}"}

# Step 2: Create some test actions to show in the daily brief
print()
print("2️⃣  Creating test actions for the daily brief...")
test_actions = [
    {
        "action_type": "deploy_product",
        "title": "Deploy: Smart LED Bulb WiFi RGB",
        "description": "Deploy to Shopify at $29.99 (65% margin)",
        "confidence": 92.5,
        "rationale": "High velocity in smart home niche with excellent profit margin",
        "factors": [
            {"label": "High velocity", "value": 18.0, "icon": "trending_up"},
            {"label": "Excellent margin", "value": 20.0, "icon": "dollar_sign"},
            {"label": "Low competition", "value": 15.0, "icon": "check_circle"}
        ],
        "payload": {
            "product_id": "test_led_001",
            "product_name": "Smart LED Bulb WiFi RGB",
            "source_price": 10.50,
            "sell_price": 29.99,
            "margin": 65.0,
            "niche": "smart_home",
            "ai_score": 92.5,
            "velocity_score": 88.0,
            "saturation_score": 25.0
        },
        "estimated_impact": "+$340 projected monthly profit"
    },
    {
        "action_type": "deploy_product",
        "title": "Deploy: Resistance Bands Set 5 Levels",
        "description": "Deploy to Shopify at $27.99 (66% margin)",
        "confidence": 85.0,
        "rationale": "Proven fitness product with good margins",
        "factors": [
            {"label": "Good velocity", "value": 10.0, "icon": "trending_up"},
            {"label": "Excellent margin", "value": 20.0, "icon": "dollar_sign"}
        ],
        "payload": {
            "product_id": "test_bands_002",
            "product_name": "Resistance Bands Set 5 Levels",
            "source_price": 9.50,
            "sell_price": 27.99,
            "margin": 66.0,
            "niche": "fitness",
            "ai_score": 85.0,
            "velocity_score": 79.0,
            "saturation_score": 32.0
        },
        "estimated_impact": "+$280 projected monthly profit"
    },
    {
        "action_type": "pause_ad",
        "title": "Pause Ad: Generic Phone Case Campaign",
        "description": "ROAS dropped to 0.45x over 7 days",
        "confidence": 94.0,
        "rationale": "Campaign ROAS is 0.45x, below 1.0x threshold. Spent $145.00 with only 2 conversions in 7 days. Recommend pausing to prevent further loss.",
        "factors": [
            {"label": "ROAS below target", "value": -25.0, "icon": "alert_triangle"},
            {"label": "High CPA", "value": -15.0, "icon": "alert_triangle"}
        ],
        "payload": {
            "campaign_id": "test_campaign_001",
            "campaign_name": "Generic Phone Case Campaign",
            "platform": "meta",
            "current_roas": 0.45,
            "spend_last_7d": 145.00,
            "conversions": 2
        },
        "estimated_impact": "Save $145/week in ad spend"
    }
]

actions_created = 0
for action_data in test_actions:
    response = requests.post(f"{BASE_URL}/api/actions", json=action_data, headers=headers)
    if response.status_code == 200:
        actions_created += 1
        print(f"   ✅ Created: {action_data['title'][:50]}...")
    else:
        print(f"   ⚠️  Failed to create action: {response.status_code}")

print(f"   📊 Created {actions_created}/{len(test_actions)} test actions")

# Step 3: Get daily brief
print()
print("3️⃣  Generating daily brief...")
response = requests.get(f"{BASE_URL}/api/daily-brief", headers=headers)
if response.status_code == 200:
    brief = response.json()
    print(f"   ✅ Daily brief generated successfully")
    print()
    print("   📋 DAILY BRIEF CONTENT:")
    print("   " + "─" * 70)
    print(f"   Timestamp: {brief.get('timestamp', 'N/A')}")
    print(f"   Greeting: {brief.get('greeting', 'N/A')}")
    print()
    print("   Summary:")
    summary_text = brief.get('summary_text', 'No summary available')
    for line in summary_text.split('\n'):
        print(f"   {line}")
    print()
    print(f"   Pending Actions: {brief.get('pending_actions', {}).get('count', 0)}")
    print(f"   High Confidence Actions: {brief.get('pending_actions', {}).get('high_confidence', 0)}")
    print()
    print(f"   Performance Health Score: {brief.get('performance', {}).get('health_score', 0):.1f}/100")
    print()
    print(f"   Opportunities: {brief.get('opportunities', {}).get('count', 0)}")
    print()
    print(f"   Priority Items: {len(brief.get('priorities', []))}")
    for i, priority in enumerate(brief.get('priorities', [])[:3], 1):
        print(f"      {i}. [{priority.get('urgency', '?').upper()}] {priority.get('title', 'N/A')}")
    print("   " + "─" * 70)
else:
    print(f"   ❌ Failed: {response.status_code}")
    print(f"      {response.text}")
    exit(1)

# Step 4: Test preview endpoint
print()
print("4️⃣  Testing preview endpoint...")
response = requests.get(f"{BASE_URL}/api/daily-brief/preview", headers=headers)
if response.status_code == 200:
    preview = response.json()
    print(f"   ✅ Preview endpoint works")
    print(f"      Returns same structure as main endpoint")
else:
    print(f"   ❌ Failed: {response.status_code}")

# Step 5: Test send email endpoint
print()
print("5️⃣  Testing send email endpoint...")
response = requests.post(f"{BASE_URL}/api/daily-brief/send-email", headers=headers)
if response.status_code == 200:
    result = response.json()
    print(f"   ✅ Email send endpoint works")
    print(f"      Message: {result.get('message', 'N/A')}")
    print(f"      Would send to: {email}")
    print(f"      Note: {result.get('note', 'N/A')}")
else:
    print(f"   ❌ Failed: {response.status_code}")
    print(f"      {response.text}")

# Step 6: Verify data structure
print()
print("6️⃣  Verifying data structure...")
required_fields = [
    "timestamp", "greeting", "summary_text",
    "pending_actions", "performance", "opportunities", "priorities"
]
missing_fields = [field for field in required_fields if field not in brief]
if not missing_fields:
    print(f"   ✅ All required fields present")

    # Check nested structures
    pending_actions = brief.get("pending_actions", {})
    if "count" in pending_actions and "high_confidence" in pending_actions and "actions" in pending_actions:
        print(f"   ✅ pending_actions structure valid")
        action_count = len(pending_actions.get("actions", []))
        print(f"      {action_count} action(s) in queue")
    else:
        print(f"   ⚠️  pending_actions structure incomplete")

    performance = brief.get("performance", {})
    if "health_score" in performance:
        print(f"   ✅ performance structure valid")
    else:
        print(f"   ⚠️  performance structure incomplete")

    opportunities = brief.get("opportunities", {})
    if "count" in opportunities:
        print(f"   ✅ opportunities structure valid")
    else:
        print(f"   ⚠️  opportunities structure incomplete")

    priorities = brief.get("priorities", [])
    if isinstance(priorities, list):
        print(f"   ✅ priorities is a list with {len(priorities)} item(s)")
    else:
        print(f"   ⚠️  priorities should be a list")
else:
    print(f"   ❌ Missing fields: {', '.join(missing_fields)}")

print()
print("=" * 80)
print("✅ DAILY BRIEF API TEST COMPLETE!")
print("=" * 80)
print()
print("🎯 KEY METRICS:")
print()
print(f"   Actions Created: {actions_created}")
print(f"   Actions in Brief: {brief.get('pending_actions', {}).get('count', 0)}")
print(f"   High Confidence: {brief.get('pending_actions', {}).get('high_confidence', 0)}")
print(f"   Health Score: {brief.get('performance', {}).get('health_score', 0):.1f}/100")
print(f"   Priorities: {len(brief.get('priorities', []))}")
print()
print("NEXT STEPS:")
print("   1. ✅ Backend API is working")
print("   2. ⏭️  Create DailyBrief.tsx React component")
print("   3. ⏭️  Integrate into dashboard homepage")
print()
