"""
Test Auto-Action Creation from Product Discovery

Demonstrates GROK RECOMMENDATION #4:
AI discovers products → Automatically creates Actions → User approves

This transforms Ospra from passive info display to active decision queue.
"""
import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8001"

print("=" * 80)
print("🤖 AUTO-ACTION CREATION TEST")
print("   Simulating: AI Product Discovery → Automatic Action Queue")
print("=" * 80)
print()

# Step 1: Register test user
print("1️⃣  Setting up test user...")
register_data = {
    "email": f"auto_actions_{datetime.now().timestamp()}@example.com",
    "password": "testpass123",
    "name": "Auto Actions Test"
}
response = requests.post(f"{BASE_URL}/api/auth/register", json=register_data)
if response.status_code == 201:
    auth_data = response.json()
    token = auth_data["access_token"]
    user_id = auth_data["user"]["id"]
    print(f"   ✅ Test user created: ID={user_id}")
else:
    print(f"   ❌ Failed: {response.status_code}")
    exit(1)

headers = {"Authorization": f"Bearer {token}"}

# Step 2: Simulate product discovery
print()
print("2️⃣  Simulating AI product discovery...")
print("   (In production, this would be from real discovery API)")
print()

discovered_products = [
    {
        "id": "ae_premium_yoga_mat_001",
        "title": "Premium Yoga Mat TPE 6mm Extra Thick",
        "price": 16.50,
        "suggested_price": 39.99,
        "niche": "fitness",
        "ai_score": 92.5,
        "velocity_score": 88.0,
        "saturation_score": 25.0,
        "images": ["https://example.com/yoga-mat-1.jpg", "https://example.com/yoga-mat-2.jpg"],
        "rationale": "High demand in fitness niche with low competition"
    },
    {
        "id": "ae_smart_wifi_plug_002",
        "title": "Smart WiFi Plug 20A with Energy Monitor",
        "price": 8.99,
        "suggested_price": 24.99,
        "niche": "smart_home",
        "ai_score": 85.0,
        "velocity_score": 82.0,
        "saturation_score": 45.0,
        "images": ["https://example.com/wifi-plug.jpg"],
        "rationale": "Proven seller with good margins"
    },
    {
        "id": "ae_led_strip_003",
        "title": "Smart LED Strip Lights 5M RGB WiFi",
        "price": 12.75,
        "suggested_price": 34.99,
        "niche": "smart_home",
        "ai_score": 78.0,
        "velocity_score": 75.0,
        "saturation_score": 38.0,
        "images": ["https://example.com/led-strip.jpg"],
        "rationale": "Popular item with solid velocity"
    },
    {
        "id": "ae_resistance_bands_004",
        "title": "Resistance Bands Set 5 Levels with Handles",
        "price": 9.50,
        "suggested_price": 27.99,
        "niche": "fitness",
        "ai_score": 81.0,
        "velocity_score": 79.0,
        "saturation_score": 32.0,
        "images": ["https://example.com/bands.jpg"],
        "rationale": "Low saturation with good demand"
    },
    {
        "id": "ae_poor_product_005",
        "title": "Generic Phone Case",
        "price": 2.50,
        "suggested_price": 9.99,
        "niche": "accessories",
        "ai_score": 45.0,  # Low score - should NOT create action
        "velocity_score": 40.0,
        "saturation_score": 85.0,
        "images": [],
        "rationale": "High saturation, low differentiation"
    }
]

print(f"   📊 Discovered {len(discovered_products)} products")
print()

# Step 3: Auto-create actions for high-scoring products
print("3️⃣  Auto-creating actions for top products (score >= 70)...")
print()

actions_created = []
for product in discovered_products:
    if product["ai_score"] >= 70:  # Only queue high-quality products
        margin = ((product["suggested_price"] - product["price"]) / product["suggested_price"]) * 100

        # Build factors
        factors = []
        if product["velocity_score"] > 80:
            factors.append({"label": "High velocity", "value": 18.0, "icon": "trending_up"})
        elif product["velocity_score"] > 60:
            factors.append({"label": "Good velocity", "value": 10.0, "icon": "trending_up"})

        if margin > 50:
            factors.append({"label": "Excellent margin", "value": 20.0, "icon": "dollar_sign"})
        elif margin > 35:
            factors.append({"label": "Good margin", "value": 12.0, "icon": "dollar_sign"})

        if product["saturation_score"] < 30:
            factors.append({"label": "Low competition", "value": 15.0, "icon": "check_circle"})

        # Calculate estimated impact
        estimated_monthly_sales = max(5, int(product["velocity_score"] / 10))
        profit_per_sale = product["suggested_price"] - product["price"]
        estimated_impact = f"+${estimated_monthly_sales * profit_per_sale:.0f} projected monthly profit"

        # Create action via API
        action_data = {
            "action_type": "deploy_product",
            "title": f"Deploy: {product['title']}",
            "description": f"Deploy to Shopify at ${product['suggested_price']:.2f} ({margin:.0f}% margin)",
            "confidence": min(95, product["ai_score"]),
            "rationale": product["rationale"],
            "factors": factors,
            "payload": {
                "product_id": product["id"],
                "product_name": product["title"],
                "source_price": product["price"],
                "sell_price": product["suggested_price"],
                "margin": round(margin, 1),
                "niche": product["niche"],
                "images": product["images"],
                "ai_score": product["ai_score"],
                "velocity_score": product["velocity_score"],
                "saturation_score": product["saturation_score"]
            },
            "estimated_impact": estimated_impact,
            "product_image": product["images"][0] if product["images"] else None
        }

        response = requests.post(f"{BASE_URL}/api/actions", json=action_data, headers=headers)
        if response.status_code == 200:
            action = response.json()
            actions_created.append(action)
            print(f"   ✅ Action created: {product['title'][:40]}...")
            print(f"      Confidence: {action['confidence']:.1f}% | ID: {action['id']}")
        else:
            print(f"   ❌ Failed for {product['title']}: {response.status_code}")
    else:
        print(f"   ⏭️  Skipped: {product['title'][:40]}... (score {product['ai_score']} < 70)")

print()
print(f"   📊 Created {len(actions_created)} actions from {len(discovered_products)} products")
print()

# Step 4: Show action queue
print("4️⃣  Fetching action queue...")
response = requests.get(f"{BASE_URL}/api/actions?status=pending", headers=headers)
if response.status_code == 200:
    actions = response.json()
    print(f"   ✅ Found {len(actions)} pending action(s) in queue")
    print()

    for i, action in enumerate(actions[:3], 1):  # Show first 3
        print(f"   Action #{i}:")
        print(f"      Title: {action['title']}")
        print(f"      Confidence: {action['confidence']:.1f}%")
        print(f"      Impact: {action.get('estimated_impact', 'N/A')}")
        print(f"      Expires: {action.get('expires_at', 'N/A')}")
        print()
else:
    print(f"   ❌ Failed: {response.status_code}")

# Step 5: Get stats
print("5️⃣  Checking action statistics...")
response = requests.get(f"{BASE_URL}/api/actions/stats", headers=headers)
if response.status_code == 200:
    stats = response.json()
    print(f"   ✅ Queue Statistics:")
    print(f"      Pending: {stats.get('pending', 0)}")
    print(f"      Total: {stats.get('total', 0)}")
    print(f"      Avg Confidence: {stats.get('avg_confidence', 0):.1f}%")
else:
    print(f"   ❌ Failed: {response.status_code}")

# Step 6: Simulate approval workflow
print()
print("6️⃣  Simulating user approval of top action...")
if actions_created:
    top_action = actions_created[0]
    response = requests.post(
        f"{BASE_URL}/api/actions/{top_action['id']}/approve",
        headers=headers
    )
    if response.status_code == 200:
        result = response.json()
        print(f"   ✅ Approved: {top_action['title']}")
        print(f"      Status: {result['action']['status']}")
        print(f"      Message: {result['message']}")
    else:
        print(f"   ❌ Approval failed: {response.status_code}")

print()
print("=" * 80)
print("✅ AUTO-ACTION CREATION TEST COMPLETE!")
print("=" * 80)
print()
print("🎯 TRANSFORMATION DEMONSTRATED:")
print()
print("BEFORE (Manual):")
print("   1. AI finds products")
print("   2. User views list")
print("   3. User manually deploys each one")
print()
print("AFTER (Automated):")
print("   1. AI finds products")
print("   2. ✨ Actions automatically created")
print("   3. User clicks Approve/Skip")
print()
print("This is the core of GROK RECOMMENDATION #4:")
print("Every AI insight becomes an actionable item requiring approval.")
print()
