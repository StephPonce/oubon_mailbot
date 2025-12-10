#!/usr/bin/env python3
"""
Test script to verify the velocity_score fix
"""

from ospra_os.database.product_history import ProductHistoryDB

print("🧪 Testing velocity_score fix...")
print()

# Get products from database
db = ProductHistoryDB()
products = db.get_all_products()

print(f"Found {len(products)} products in database")
print()

# Check for None values
none_count = sum(1 for p in products if p.get('velocity_score') is None)
print(f"Products with None velocity_score: {none_count}")
print()

# Test the old way (should fail if there are None values)
try:
    high_velocity_OLD = [p for p in products if p['velocity_score'] >= 70]
    print(f"✅ OLD METHOD worked: {len(high_velocity_OLD)} high velocity products")
except TypeError as e:
    print(f"❌ OLD METHOD failed: {e}")

print()

# Test the new way (should always work)
try:
    high_velocity_NEW = [p for p in products if p.get('velocity_score', 0) >= 70]
    medium_velocity_NEW = [p for p in products if 40 <= p.get('velocity_score', 0) < 70]
    low_velocity_NEW = [p for p in products if p.get('velocity_score', 0) < 40]

    print(f"✅ NEW METHOD worked:")
    print(f"   High velocity: {len(high_velocity_NEW)}")
    print(f"   Medium velocity: {len(medium_velocity_NEW)}")
    print(f"   Low velocity: {len(low_velocity_NEW)}")
    print(f"   Total: {len(high_velocity_NEW) + len(medium_velocity_NEW) + len(low_velocity_NEW)}")
except Exception as e:
    print(f"❌ NEW METHOD failed: {e}")
