#!/usr/bin/env python3
"""
🔍 OSPRA DIAGNOSTIC SCRIPT
Checks database status and API connectivity
"""

import sqlite3
import os
import requests
from pathlib import Path

print("=" * 60)
print("🔍 OSPRA INTELLIGENCE - DIAGNOSTIC REPORT")
print("=" * 60)

# 1. Check local database
print("\n📊 DATABASE STATUS:")
db_paths = [
    "data/product_history.db",
    "ospra_os.db",
    "oubon_store.db"
]

for db_path in db_paths:
    if Path(db_path).exists():
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Try products table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [t[0] for t in cursor.fetchall()]
            
            print(f"\n  ✅ {db_path}")
            print(f"     Tables: {', '.join(tables[:10])}")
            
            if 'products' in tables:
                cursor.execute("SELECT COUNT(*) FROM products")
                count = cursor.fetchone()[0]
                print(f"     Products: {count}")
                
                if count > 0:
                    cursor.execute("SELECT id, name FROM products LIMIT 3")
                    samples = cursor.fetchall()
                    print(f"     Samples: {[s[1][:30] for s in samples]}")
            
            conn.close()
        except Exception as e:
            print(f"  ❌ {db_path}: {e}")
    else:
        print(f"  ❌ {db_path}: NOT FOUND")

# 2. Check environment variables
print("\n🔑 API KEYS STATUS:")
api_keys = {
    "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
    "ALIEXPRESS_APP_KEY": os.getenv("ALIEXPRESS_APP_KEY"),
    "ALIEXPRESS_ACCESS_TOKEN": os.getenv("ALIEXPRESS_ACCESS_TOKEN"),
    "ALIEXPRESS_AFFILIATE_APP_KEY": os.getenv("ALIEXPRESS_AFFILIATE_APP_KEY"),
    "APIFY_API_TOKEN": os.getenv("APIFY_API_TOKEN"),
    "SHOPIFY_API_TOKEN": os.getenv("SHOPIFY_API_TOKEN"),
}

for key, value in api_keys.items():
    if value:
        masked = value[:8] + "..." + value[-4:] if len(value) > 12 else "***"
        print(f"  ✅ {key}: {masked}")
    else:
        print(f"  ❌ {key}: NOT SET")

# 3. Check backend connectivity
print("\n🌐 BACKEND CONNECTIVITY:")
endpoints = [
    ("Local", "http://localhost:8001/health"),
    ("Production", "https://oubon-mailbot.onrender.com/health"),
]

for name, url in endpoints:
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            print(f"  ✅ {name}: {data.get('status', 'unknown')}")
        else:
            print(f"  ⚠️ {name}: Status {resp.status_code}")
    except requests.exceptions.ConnectionError:
        print(f"  ❌ {name}: Connection failed")
    except Exception as e:
        print(f"  ❌ {name}: {e}")

# 4. Test product discovery endpoint
print("\n🔬 PRODUCT DISCOVERY TEST:")
try:
    resp = requests.get(
        "https://oubon-mailbot.onrender.com/api/dashboard/v2/products",
        timeout=30
    )
    data = resp.json()
    products = data.get('products', [])
    print(f"  Products returned: {len(products)}")
    if products:
        print(f"  First product: {products[0].get('name', 'N/A')[:40]}")
    else:
        print("  ⚠️ NO PRODUCTS IN DATABASE!")
        print("  Run: POST /api/intelligence/discover to populate")
except Exception as e:
    print(f"  ❌ Error: {e}")

# 5. Check frontend build
print("\n🎨 FRONTEND STATUS:")
frontend_paths = [
    "frontend/dist/index.html",
    "frontend/dist/assets",
    "frontend/node_modules"
]

for path in frontend_paths:
    if Path(path).exists():
        print(f"  ✅ {path}")
    else:
        print(f"  ❌ {path}: NOT FOUND")

print("\n" + "=" * 60)
print("📋 RECOMMENDATIONS:")
print("=" * 60)

print("""
1. If products = 0:
   curl -X POST https://oubon-mailbot.onrender.com/api/intelligence/discover \\
     -H "Content-Type: application/json" \\
     -d '{"niches": ["smart_home", "fitness", "kitchen"], "max_per_niche": 10}'

2. If frontend dist missing:
   cd frontend && npm run build

3. If blank white page:
   - Check browser console (F12)
   - Clear browser cache
   - Try incognito mode

4. If API keys missing:
   - Check .env file
   - Restart backend
""")
