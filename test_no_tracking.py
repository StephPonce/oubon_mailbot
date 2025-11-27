"""
Test AliExpress API without tracking ID
To see if we can get basic product data
"""
import asyncio
import os
import hashlib
import time
import httpx
import json
from dotenv import load_dotenv

load_dotenv()


async def test_without_tracking():
    """Test API calls without tracking_id parameter"""
    print("=" * 80)
    print("🧪 Testing AliExpress API WITHOUT Tracking ID")
    print("=" * 80)
    print()

    app_key = os.getenv('ALIEXPRESS_AFFILIATE_APP_KEY')
    app_secret = os.getenv('ALIEXPRESS_AFFILIATE_APP_SECRET')

    # Test 1: Product search WITHOUT tracking_id
    print("1️⃣ Product Search (NO tracking_id)")
    print("-" * 80)

    params = {
        'app_key': app_key,
        'method': 'aliexpress.affiliate.product.query',
        'timestamp': str(int(time.time() * 1000)),
        'format': 'json',
        'v': '2.0',
        'sign_method': 'md5',
        'keywords': 'phone case',
        'page_size': '5'
        # NOTE: NO tracking_id parameter!
    }

    # Sign request
    sorted_params = sorted(params.items())
    sign_str = app_secret
    for k, v in sorted_params:
        sign_str += f"{k}{v}"
    sign_str += app_secret
    signature = hashlib.md5(sign_str.encode('utf-8')).hexdigest().upper()
    params['sign'] = signature

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api-sg.aliexpress.com/sync",
                data=params
            )

            result = response.json()
            print("📦 Response:")
            print(json.dumps(result, indent=2))
            print()

            if 'error_response' in result:
                error = result['error_response']
                print(f"❌ Error: {error.get('msg')}")
                print()

                if 'tracking' in error.get('msg', '').lower():
                    print("💡 Tracking ID is REQUIRED for this API")
                    print("   You MUST get a valid tracking ID from AliExpress portal")
                    print()
            else:
                print("✅ Request succeeded without tracking ID!")
                print("   (This means tracking ID might be optional)")
                print()

    except Exception as e:
        print(f"❌ Request failed: {e}")
        print()

    # Test 2: Try with a generic tracking_id pattern
    print("2️⃣ Testing Common Tracking ID Patterns")
    print("-" * 80)

    test_patterns = [
        "default",
        f"{app_key}",  # Use app key as tracking id
        "oubon-20",
        "oubon_default",
    ]

    for tracking_id in test_patterns:
        print(f"Testing: {tracking_id}")

        params = {
            'app_key': app_key,
            'method': 'aliexpress.affiliate.product.query',
            'timestamp': str(int(time.time() * 1000)),
            'format': 'json',
            'v': '2.0',
            'sign_method': 'md5',
            'keywords': 'phone case',
            'page_size': '3',
            'tracking_id': tracking_id
        }

        # Sign
        sorted_params = sorted(params.items())
        sign_str = app_secret
        for k, v in sorted_params:
            sign_str += f"{k}{v}"
        sign_str += app_secret
        signature = hashlib.md5(sign_str.encode('utf-8')).hexdigest().upper()
        params['sign'] = signature

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api-sg.aliexpress.com/sync",
                    data=params
                )

                result = response.json()

                # Check for success
                if 'error_response' in result:
                    print(f"  ❌ {result['error_response'].get('msg')}")
                else:
                    resp_result = result.get('aliexpress_affiliate_product_query_response', {}).get('resp_result', {})
                    resp_code = resp_result.get('resp_code')
                    resp_msg = resp_result.get('resp_msg', '')

                    if resp_code == 200:
                        print(f"  ✅ SUCCESS! Use this tracking ID: {tracking_id}")
                        return tracking_id
                    else:
                        print(f"  ⚠️  Code {resp_code}: {resp_msg}")

        except Exception as e:
            print(f"  ❌ Error: {e}")

        print()

    print("=" * 80)
    print("💡 WHAT TO DO NEXT:")
    print("=" * 80)
    print()
    print("Since none of the common patterns worked, you need to:")
    print()
    print("1. Login to AliExpress Affiliate Portal:")
    print("   → https://portals.aliexpress.com/")
    print()
    print("2. Find 'Tracking IDs' or 'Link Management'")
    print()
    print("3. Look for your tracking ID - it might look like:")
    print("   • oubon-20")
    print("   • Some number like: 123456")
    print("   • Custom name you created")
    print()
    print("4. Copy it and update .env:")
    print("   ALIEXPRESS_TRACKING_ID=your_actual_tracking_id")
    print()
    print("5. Run this test again:")
    print("   uv run python test_aliexpress_detailed.py")
    print()


if __name__ == "__main__":
    asyncio.run(test_without_tracking())
