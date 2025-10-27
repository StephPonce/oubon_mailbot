#!/usr/bin/env python3
"""
Test AliExpress Dropshipping Solution API WITHOUT OAuth.

If this works, we don't need OAuth at all!
"""

import hmac
import hashlib
import time
import requests

app_key = "520918"
app_secret = "idjX6tOzHx6urVsSylVzEcHZKwBN4YhN"

# API parameters
params = {
    "app_key": app_key,
    "method": "aliexpress.ds.product.get",
    "timestamp": str(int(time.time() * 1000)),
    "format": "json",
    "v": "2.0",
    "sign_method": "sha256",
    "ship_to_country": "US",
    "product_id": "1005004043442825",
    "target_currency": "USD",
    "target_language": "en",
}

# Generate signature
sorted_params = sorted(params.items())
sign_string = "".join([f"{k}{v}" for k, v in sorted_params])
signature = hmac.new(
    app_secret.encode('utf-8'),
    sign_string.encode('utf-8'),
    hashlib.sha256
).hexdigest().upper()

params["sign"] = signature

# Make request
url = "https://api-sg.aliexpress.com/sync"
print("=" * 70)
print("TESTING DROPSHIPPING API WITHOUT OAUTH")
print("=" * 70)
print(f"\nEndpoint: {url}")
print(f"Method: {params['method']}")
print(f"Product ID: {params['product_id']}")
print(f"\nMaking request...")

response = requests.get(url, params=params, timeout=15)

print(f"\nHTTP Status Code: {response.status_code}")

# Check for success
data = response.json()

if "aliexpress_ds_product_get_response" in data:
    print("\n" + "🎉" * 35)
    print("✅ SUCCESS! Dropshipper API works WITHOUT OAuth!")
    print("🎉" * 35)

    result = data["aliexpress_ds_product_get_response"]["result"]

    print(f"\n📦 Product Details:")
    print(f"   Title: {result.get('subject', 'N/A')}")
    print(f"   Price: ${result.get('target_original_price', 'N/A')}")
    print(f"   Sale Price: ${result.get('target_sale_price', 'N/A')}")
    print(f"   Currency: {result.get('target_currency', 'N/A')}")
    print(f"   Product ID: {result.get('product_id', 'N/A')}")

    if 'ae_item_sku_info_dtos' in result:
        print(f"   SKUs Available: {len(result['ae_item_sku_info_dtos']['ae_item_sku_info_d_t_o'])}")

    print("\n💡 IMPLICATIONS:")
    print("   ✅ We can get product details WITHOUT OAuth")
    print("   ✅ We can search products (if ds.product.query works)")
    print("   ✅ We might be able to place orders WITHOUT OAuth")
    print("   ✅ We can build the dashboard with REAL data TODAY")

    print("\n🚀 NEXT: Test product search and order placement!")

elif "error_response" in data:
    error = data["error_response"]
    error_code = error.get('code', 'Unknown')
    error_msg = error.get('msg', 'Unknown')

    print("\n❌ API ERROR:")
    print(f"   Code: {error_code}")
    print(f"   Message: {error_msg}")

    if "access_token" in error_msg.lower() or "MissingParameter" in error_code:
        print("\n💔 BAD NEWS: OAuth IS required")
        print("   We need to complete the OAuth flow")
    else:
        print("\n⚠️  Different error - might be fixable!")

else:
    print("\n⚠️ Unexpected response format")
    print(f"Response keys: {list(data.keys())}")

print("\n" + "=" * 70)
print("\nFull Response:")
print("=" * 70)
import json
print(json.dumps(data, indent=2))
