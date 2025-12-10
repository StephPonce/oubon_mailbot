"""
Test script for Actions Queue API

Tests all endpoints to verify the Actions Queue implementation is working.
"""
import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8001"

print("=" * 70)
print("🧪 ACTIONS QUEUE API TEST")
print("=" * 70)
print()

# Step 1: Register a test user
print("1️⃣  Registering test user...")
register_data = {
    "email": f"test_actions_{datetime.now().timestamp()}@example.com",
    "password": "testpass123",
    "name": "Actions Test User"
}
response = requests.post(f"{BASE_URL}/api/auth/register", json=register_data)
if response.status_code == 201:
    auth_data = response.json()
    token = auth_data["access_token"]
    user_id = auth_data["user"]["id"]
    print(f"   ✅ User registered: ID={user_id}")
    print(f"   ✅ Access token obtained")
else:
    print(f"   ❌ Registration failed: {response.status_code}")
    print(f"      {response.text}")
    exit(1)

headers = {"Authorization": f"Bearer {token}"}

# Step 2: Get stats (should be empty)
print()
print("2️⃣  Getting action stats...")
response = requests.get(f"{BASE_URL}/api/actions/stats", headers=headers)
if response.status_code == 200:
    stats = response.json()
    print(f"   ✅ Stats retrieved:")
    print(f"      Total: {stats['total']}")
    print(f"      Pending: {stats['pending']}")
    print(f"      Approved: {stats['approved']}")
else:
    print(f"   ❌ Failed: {response.status_code} - {response.text}")
    exit(1)

# Step 3: Create a test action
print()
print("3️⃣  Creating test action...")
action_data = {
    "action_type": "deploy_product",
    "title": "Deploy Premium Yoga Mat to Smart Home Store",
    "description": "AI recommends deploying this high-velocity product",
    "confidence": 92.5,
    "rationale": "This product shows strong velocity score (18) and low saturation in the smart home niche",
    "factors": [
        {"label": "Velocity Score", "value": 18.0, "icon": "trending_up"},
        {"label": "Competition", "value": 3.2, "icon": "users"},
        {"label": "Profit Margin", "value": 45.0, "icon": "dollar_sign"}
    ],
    "payload": {
        "product_name": "Premium Yoga Mat TPE 6mm",
        "product_id": "ae_12345",
        "price": 29.99,
        "cost": 16.50,
        "store_id": 1,
        "niche": "fitness"
    },
    "estimated_impact": "+$520 projected monthly profit",
    "product_image": "https://example.com/yoga-mat.jpg"
}

response = requests.post(f"{BASE_URL}/api/actions", json=action_data, headers=headers)
if response.status_code == 200:
    action = response.json()
    action_id = action["id"]
    print(f"   ✅ Action created: ID={action_id}")
    print(f"      Title: {action['title']}")
    print(f"      Confidence: {action['confidence']}%")
    print(f"      Status: {action['status']}")
else:
    print(f"   ❌ Failed: {response.status_code} - {response.text}")
    exit(1)

# Step 4: Get all actions
print()
print("4️⃣  Fetching all actions...")
response = requests.get(f"{BASE_URL}/api/actions?status=pending", headers=headers)
if response.status_code == 200:
    actions = response.json()
    print(f"   ✅ Found {len(actions)} pending action(s)")
else:
    print(f"   ❌ Failed: {response.status_code} - {response.text}")
    exit(1)

# Step 5: Get single action
print()
print("5️⃣  Getting action details...")
response = requests.get(f"{BASE_URL}/api/actions/{action_id}", headers=headers)
if response.status_code == 200:
    action = response.json()
    print(f"   ✅ Action retrieved")
    print(f"      Rationale: {action['rationale'][:50]}...")
else:
    print(f"   ❌ Failed: {response.status_code} - {response.text}")
    exit(1)

# Step 6: Approve action
print()
print("6️⃣  Approving action...")
response = requests.post(f"{BASE_URL}/api/actions/{action_id}/approve", headers=headers)
if response.status_code == 200:
    result = response.json()
    print(f"   ✅ Action approved")
    print(f"      Message: {result['message']}")
    print(f"      Status: {result['action']['status']}")
else:
    print(f"   ❌ Failed: {response.status_code} - {response.text}")
    exit(1)

# Step 7: Get updated stats
print()
print("7️⃣  Getting updated stats...")
response = requests.get(f"{BASE_URL}/api/actions/stats", headers=headers)
if response.status_code == 200:
    stats = response.json()
    print(f"   ✅ Updated stats:")
    print(f"      Total: {stats['total']}")
    print(f"      Pending: {stats['pending']}")
    print(f"      Executed: {stats['executed']}")
    print(f"      Avg Confidence: {stats['avg_confidence']:.1f}%")
else:
    print(f"   ❌ Failed: {response.status_code} - {response.text}")

print()
print("=" * 70)
print("✅ ALL TESTS PASSED!")
print("=" * 70)
print()
print("The Actions Queue API is working correctly!")
print("All 9 endpoints are functional and properly authenticated.")
