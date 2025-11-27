"""
Detailed AliExpress API Diagnostic Test
Shows exact request/response for debugging
"""
import asyncio
import os
import hmac
import hashlib
import time
import httpx
import json
from dotenv import load_dotenv

load_dotenv()


async def detailed_api_test():
    """Test AliExpress API with detailed logging"""
    print("=" * 80)
    print("🔍 DETAILED ALIEXPRESS API DIAGNOSTIC")
    print("=" * 80)
    print()

    # Get credentials
    app_key = os.getenv('ALIEXPRESS_AFFILIATE_APP_KEY')
    app_secret = os.getenv('ALIEXPRESS_AFFILIATE_APP_SECRET')
    tracking_id = os.getenv('ALIEXPRESS_TRACKING_ID', 'oubon_tracking')

    if not app_key or not app_secret:
        print("❌ Affiliate credentials not found!")
        return

    print(f"App Key: {app_key}")
    print(f"App Secret: {app_secret[:10]}***")
    print(f"Tracking ID: {tracking_id}")
    print()

    # Test different API methods
    test_methods = [
        {
            "name": "Product Search (Affiliate)",
            "method": "aliexpress.affiliate.product.query",
            "params": {
                "keywords": "phone case",
                "page_size": "5",
                "tracking_id": tracking_id
            }
        },
        {
            "name": "Hot Product Query",
            "method": "aliexpress.affiliate.hotproduct.query",
            "params": {
                "category_ids": "200000297",  # Consumer Electronics
                "page_size": "5",
                "tracking_id": tracking_id
            }
        },
        {
            "name": "Featured Promo Products",
            "method": "aliexpress.affiliate.featuredpromo.products.get",
            "params": {
                "page_size": "5",
                "tracking_id": tracking_id
            }
        }
    ]

    for test in test_methods:
        print("=" * 80)
        print(f"📡 Testing: {test['name']}")
        print("=" * 80)

        # Build params
        params = {
            'app_key': app_key,
            'method': test['method'],
            'timestamp': str(int(time.time() * 1000)),
            'format': 'json',
            'v': '2.0',
            'sign_method': 'md5'
        }
        params.update(test['params'])

        # Sign request
        sorted_params = sorted(params.items())
        sign_str = app_secret
        for k, v in sorted_params:
            sign_str += f"{k}{v}"
        sign_str += app_secret
        signature = hashlib.md5(sign_str.encode('utf-8')).hexdigest().upper()
        params['sign'] = signature

        print(f"Method: {test['method']}")
        print(f"Parameters:")
        for k, v in test['params'].items():
            print(f"  {k}: {v}")
        print()

        # Make request
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                print("🚀 Sending request...")
                response = await client.post(
                    "https://api-sg.aliexpress.com/sync",
                    data=params
                )

                print(f"Status Code: {response.status_code}")
                print()

                if response.status_code == 200:
                    result = response.json()
                    print("📦 Response:")
                    print(json.dumps(result, indent=2)[:1000])
                    print()

                    # Check for errors
                    if 'error_response' in result:
                        error = result['error_response']
                        print(f"❌ API Error:")
                        print(f"   Code: {error.get('code')}")
                        print(f"   Type: {error.get('type')}")
                        print(f"   Message: {error.get('msg')}")
                        print()

                        # Common error explanations
                        if error.get('code') == 'IncompleteSignature':
                            print("💡 This error means the signature is incorrect.")
                            print("   This could be due to:")
                            print("   - Wrong app_key or app_secret")
                            print("   - Incorrect signature algorithm")
                            print()
                        elif error.get('code') == 'InvalidParameter':
                            print("💡 This error means one of the parameters is invalid.")
                            print("   Check that all required parameters are provided.")
                            print()
                        elif 'permission' in error.get('msg', '').lower():
                            print("💡 This error means your app doesn't have permission.")
                            print("   You may need to:")
                            print("   - Apply for API access in the AliExpress portal")
                            print("   - Wait for approval")
                            print("   - Check if the API method is available for your plan")
                            print()
                    else:
                        # Success - check results
                        print("✅ Request successful!")
                        print()

                        # Try to find products in response
                        products_found = False
                        for key in result:
                            if 'product' in key.lower():
                                print(f"📦 Found products in key: {key}")
                                products_found = True

                        if not products_found:
                            print("⚠️  No products found in response")
                            print("   This could mean:")
                            print("   - The API call succeeded but returned 0 results")
                            print("   - You need to adjust search parameters")
                            print("   - The affiliate account needs activation")
                else:
                    print(f"❌ HTTP Error: {response.status_code}")
                    print(response.text[:500])

        except Exception as e:
            print(f"❌ Request failed: {e}")

        print()

    # Final recommendations
    print("=" * 80)
    print("💡 RECOMMENDATIONS")
    print("=" * 80)
    print()
    print("1. Check AliExpress Affiliate Portal:")
    print("   https://portals.aliexpress.com/")
    print()
    print("2. Verify your app has API permissions for:")
    print("   - Product Search API")
    print("   - Affiliate Link Generation API")
    print("   - Hot Products API")
    print()
    print("3. Check if your affiliate account is approved and active")
    print()
    print("4. Review tracking ID configuration")
    print()


if __name__ == "__main__":
    asyncio.run(detailed_api_test())
