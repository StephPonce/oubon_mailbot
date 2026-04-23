#!/usr/bin/env python3
"""
Apify Account Diagnostic
========================
Checks your Apify account status, balance, and why actors might be failing.
"""

import os
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv()

async def check_apify_account():
    print("=" * 70)
    print("APIFY ACCOUNT DIAGNOSTIC")
    print("=" * 70)

    token = os.getenv('APIFY_API_TOKEN') or os.getenv('OUBONSHOP_APIFY_API_TOKEN')

    if not token:
        print("\n❌ No APIFY_API_TOKEN found in environment!")
        return

    print(f"\n✅ Token found: {token[:15]}...{token[-5:]}")

    base_url = "https://api.apify.com/v2"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    async with httpx.AsyncClient(timeout=30.0) as client:

        # 1. Check user info
        print("\n[1] Checking Account Info...")
        try:
            resp = await client.get(f"{base_url}/users/me", headers=headers)
            if resp.status_code == 200:
                data = resp.json().get('data', {})
                print(f"   ✅ Username: {data.get('username', 'N/A')}")
                print(f"   ✅ Email: {data.get('email', 'N/A')}")
                print(f"   ✅ Plan: {data.get('plan', {}).get('id', 'N/A')}")

                # Check plan limits
                plan = data.get('plan', {})
                print(f"\n   📋 Plan Details:")
                print(f"      - Monthly usage limit: ${plan.get('monthlyUsageCreditsUsd', 'N/A')}")
                print(f"      - Max memory MB: {plan.get('maxMemoryMbytes', 'N/A')}")
                print(f"      - Max concurrent runs: {plan.get('maxConcurrentRuns', 'N/A')}")
            else:
                print(f"   ❌ Failed to get user info: {resp.status_code}")
                print(f"   Response: {resp.text[:200]}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # 2. Check account usage/billing
        print("\n[2] Checking Usage & Billing...")
        try:
            # Get current billing period usage
            resp = await client.get(f"{base_url}/users/me/usage/monthly", headers=headers)
            if resp.status_code == 200:
                data = resp.json().get('data', {})
                print(f"   📊 Current Month Usage:")
                print(f"      - Total USD spent: ${data.get('usageCreditsUsedUsd', 0):.2f}")
                print(f"      - Actor compute: ${data.get('actorComputeUnitsUsedUsd', 0):.2f}")
                print(f"      - Dataset reads: ${data.get('datasetReadsUsedUsd', 0):.2f}")
                print(f"      - Dataset writes: ${data.get('datasetWritesUsedUsd', 0):.2f}")
            else:
                print(f"   ⚠️ Could not get usage: {resp.status_code}")
        except Exception as e:
            print(f"   ⚠️ Usage check error: {e}")

        # 3. Check prepaid balance
        print("\n[3] Checking Prepaid Balance...")
        try:
            resp = await client.get(f"{base_url}/users/me", headers=headers)
            if resp.status_code == 200:
                data = resp.json().get('data', {})
                prepaid = data.get('prepaidUsd', 0)
                print(f"   💰 Prepaid Balance: ${prepaid:.2f}")

                # This is likely the issue!
                if prepaid < 5:
                    print(f"   ⚠️  LOW PREPAID BALANCE - Paid actors require prepaid credits!")
                    print(f"   💡 Your $39 might be SUBSCRIPTION credits, not PREPAID credits")
                    print(f"   💡 Paid actors (clockworks/tiktok-scraper) need prepaid balance")
        except Exception as e:
            print(f"   ⚠️ Balance check error: {e}")

        # 4. Test a FREE actor
        print("\n[4] Testing FREE Actor (apify/web-scraper)...")
        try:
            test_input = {
                "startUrls": [{"url": "https://example.com"}],
                "maxCrawlingDepth": 0,
                "maxPagesPerCrawl": 1
            }
            resp = await client.post(
                f"{base_url}/acts/apify~web-scraper/runs",
                headers=headers,
                json=test_input
            )
            if resp.status_code in [200, 201]:
                print(f"   ✅ FREE actor started successfully!")
                run_data = resp.json().get('data', {})
                print(f"   Run ID: {run_data.get('id', 'N/A')}")
            elif resp.status_code == 402:
                print(f"   ❌ Even FREE actor failed with 402!")
                print(f"   Response: {resp.text[:300]}")
            else:
                print(f"   ⚠️ Status: {resp.status_code}")
                print(f"   Response: {resp.text[:200]}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # 5. Check specific paid actor pricing
        print("\n[5] Checking Paid Actor Info (clockworks/tiktok-scraper)...")
        try:
            resp = await client.get(
                f"{base_url}/acts/clockworks~tiktok-scraper",
                headers=headers
            )
            if resp.status_code == 200:
                data = resp.json().get('data', {})
                pricing = data.get('pricingPerUnitUsd', 'N/A')
                print(f"   💵 Pricing: ${pricing} per compute unit")
                print(f"   📝 Name: {data.get('name', 'N/A')}")

                # Check if it's a paid actor
                if data.get('isPublic') and pricing and float(pricing) > 0:
                    print(f"   ⚠️  This is a PAID actor - requires prepaid balance!")
            else:
                print(f"   Status: {resp.status_code}")
        except Exception as e:
            print(f"   Error: {e}")

    print("\n" + "=" * 70)
    print("DIAGNOSIS")
    print("=" * 70)
    print("""
The error "$0.491071 remaining usage" likely means:

1. SUBSCRIPTION vs PREPAID Credits:
   - Your $39 is probably your MONTHLY SUBSCRIPTION limit
   - The $0.49 is your PREPAID BALANCE for paid actors
   - Paid actors (clockworks/tiktok-scraper) require PREPAID credits

2. To fix this, you have TWO options:

   OPTION A: Add prepaid credits
   - Go to: https://console.apify.com/billing
   - Add prepaid credits (even $5 would help)

   OPTION B: Use only FREE actors (already implemented!)
   - The code now tries FREE actors first
   - reGOTTI/tiktok-scraper and microworlds/tiktok-scraper are free

Run the product discovery again - it should now use free actors!
""")


if __name__ == "__main__":
    asyncio.run(check_apify_account())
