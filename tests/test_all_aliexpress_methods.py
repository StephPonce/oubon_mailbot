#!/usr/bin/env python3
"""Test multiple AliExpress API endpoints to find which one works"""
import requests
import time
import hashlib
import json

app_key = "520918"
app_secret = "idjX6tOzHx6urVsSylVzEcHZKwBN4YhN"

def sign_api_request(params, secret):
    sorted_params = sorted(params.items())
    sign_string = secret
    for k, v in sorted_params:
        sign_string += str(k) + str(v)
    sign_string += secret
    return hashlib.md5(sign_string.encode('utf-8')).hexdigest().upper()

# Test different API methods
test_cases = [
    {
        'name': 'Affiliate Product Query',
        'method': 'aliexpress.affiliate.productquery',
        'extra_params': {
            'keywords': 'phone case',
            'target_currency': 'USD',
            'target_language': 'EN',
            'page_size': '5'
        }
    },
    {
        'name': 'Affiliate Featured Promo Products',
        'method': 'aliexpress.affiliate.featuredpromo.products.get',
        'extra_params': {
            'category_id': '509',
            'target_currency': 'USD',
            'target_language': 'EN',
        }
    },
    {
        'name': 'Affiliate Hot Product Query',
        'method': 'aliexpress.affiliate.hotproduct.query',
        'extra_params': {
            'keywords': 'phone case',
            'target_currency': 'USD',
            'target_language': 'EN',
        }
    },
    {
        'name': 'Dropshipping Product Query',
        'method': 'aliexpress.ds.product.get',
        'extra_params': {
            'product_id': '1005006289559042',  # Example product ID
            'target_currency': 'USD',
            'target_language': 'EN',
        }
    },
    {
        'name': 'Dropshipping Recommend Feed',
        'method': 'aliexpress.ds.recommend.feed.get',
        'extra_params': {
            'feed_name': 'DS_best_sellers',
            'target_currency': 'USD',
            'target_language': 'EN',
            'page_size': '5'
        }
    }
]

print("=" * 70)
print("🧪 TESTING ALIEXPRESS API ACCESS")
print("=" * 70)
print(f"\nApp Key: {app_key}")
print(f"Testing {len(test_cases)} different API methods...\n")

url = "https://api-sg.aliexpress.com/sync"

for i, test in enumerate(test_cases, 1):
    print(f"\n{'='*70}")
    print(f"Test {i}/{len(test_cases)}: {test['name']}")
    print(f"Method: {test['method']}")
    print(f"{'='*70}")
    
    params = {
        'app_key': app_key,
        'method': test['method'],
        'timestamp': str(int(time.time() * 1000)),
        'format': 'json',
        'v': '2.0',
        'sign_method': 'md5',
    }
    
    # Add method-specific params
    params.update(test['extra_params'])
    
    # Sign request
    params['sign'] = sign_api_request(params, app_secret)
    
    try:
        response = requests.get(url, params=params, timeout=10)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            if 'error_response' in data:
                error = data['error_response']
                print(f"❌ Error: {error.get('msg', 'Unknown error')}")
                print(f"   Code: {error.get('code', 'Unknown')}")
            else:
                print("✅ SUCCESS! This API method works!")
                print(f"\nResponse preview:")
                print(json.dumps(data, indent=2)[:500])
                print("\n🎉 FOUND A WORKING API METHOD!")
                break
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    time.sleep(0.5)  # Rate limiting

print("\n" + "="*70)
print("TEST COMPLETE")
print("="*70)
