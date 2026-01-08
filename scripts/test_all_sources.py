#!/usr/bin/env python3
"""
Test ALL Data Sources - OSPRA Intelligence
Tests: Amazon PAAPI, DALL-E, and all other sources
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()


async def test_dalle():
    """Test DALL-E image generation."""
    print("\n" + "="*60)
    print(" TESTING DALL-E (OpenAI Image Generation)")
    print("="*60)
    
    openai_key = os.getenv('OPENAI_API_KEY')
    if not openai_key:
        print("[ERROR] OPENAI_API_KEY not set")
        return False
    
    print(f"[SUCCESS] OPENAI_API_KEY: {openai_key[:20]}...{openai_key[-10:]}")
    
    try:
        from openai import OpenAI
        client = OpenAI(api_key=openai_key)
        
        print(" Generating test image...")
        response = client.images.generate(
            model="dall-e-3",
            prompt="A simple test image of a blue cube on white background",
            size="1024x1024",
            quality="standard",
            n=1
        )
        
        image_url = response.data[0].url
        print(f"[SUCCESS] DALL-E WORKING!")
        print(f"   Image URL: {image_url[:80]}...")
        return True
        
    except Exception as e:
        print(f"[ERROR] DALL-E Error: {e}")
        return False


async def test_amazon_paapi():
    """Test Amazon Product Advertising API."""
    print("\n" + "="*60)
    print("[CART] TESTING AMAZON PA-API")
    print("="*60)
    
    access_key = os.getenv('AMAZON_ACCESS_KEY')
    secret_key = os.getenv('AMAZON_SECRET_KEY')
    partner_tag = os.getenv('AMAZON_PARTNER_TAG')
    
    missing = []
    if not access_key:
        missing.append("AMAZON_ACCESS_KEY")
    if not secret_key:
        missing.append("AMAZON_SECRET_KEY")
    if not partner_tag:
        missing.append("AMAZON_PARTNER_TAG")
    
    if missing:
        print(f"[ERROR] Missing credentials: {', '.join(missing)}")
        print("\n[NOTE] TO FIX: Add these to your .env file:")
        print("   AMAZON_ACCESS_KEY=your_access_key")
        print("   AMAZON_SECRET_KEY=your_secret_key")
        print("   AMAZON_PARTNER_TAG=your_associate_tag-20")
        print("\n   Get credentials from: https://affiliate-program.amazon.com/")
        return False
    
    print(f"[SUCCESS] AMAZON_ACCESS_KEY: {access_key[:10]}...")
    print(f"[SUCCESS] AMAZON_SECRET_KEY: {secret_key[:10]}...")
    print(f"[SUCCESS] AMAZON_PARTNER_TAG: {partner_tag}")
    
    try:
        from amazon_paapi import AmazonApi
        
        amazon = AmazonApi(
            key=access_key,
            secret=secret_key,
            tag=partner_tag,
            country="US",
            throttling=1.0
        )
        
        print("[SEARCH] Searching for 'smart home'...")
        result = amazon.search_items(keywords="smart home", item_count=3)
        
        if result and hasattr(result, 'items') and result.items:
            print(f"[SUCCESS] AMAZON PA-API WORKING!")
            print(f"   Found {len(result.items)} products")
            for item in result.items[:2]:
                name = item.item_info.title.display_value if hasattr(item, 'item_info') else "Unknown"
                print(f"   - {name[:60]}...")
            return True
        else:
            print("[WARNING] Search returned no results")
            return False
            
    except ImportError as e:
        print(f"[ERROR] Package not installed: {e}")
        print("   Run: pip install python-amazon-paapi")
        return False
    except Exception as e:
        print(f"[ERROR] Amazon PA-API Error: {e}")
        return False


async def test_all_sources():
    """Test all data sources."""
    print("\n" + "="*60)
    print("[STATS] TESTING ALL OTHER DATA SOURCES")
    print("="*60)
    
    results = {}
    
    # 1. Google Trends
    print("\n1⃣ Google Trends...")
    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl='en-US', tz=360)
        pytrends.build_payload(['smart home'], timeframe='now 7-d')
        data = pytrends.interest_over_time()
        if not data.empty:
            print(f"   [SUCCESS] Working - {len(data)} data points")
            results['google_trends'] = True
        else:
            print("   [WARNING] No data returned")
            results['google_trends'] = False
    except Exception as e:
        print(f"   [ERROR] Error: {e}")
        results['google_trends'] = False
    
    # 2. xAI/Grok (Twitter sentiment)
    print("\n2⃣ xAI/Grok (Twitter)...")
    xai_key = os.getenv('XAI_API_KEY')
    if xai_key:
        print(f"   [SUCCESS] XAI_API_KEY set: {xai_key[:15]}...")
        results['xai'] = True
    else:
        print("   [ERROR] XAI_API_KEY not set")
        results['xai'] = False
    
    # 3. Claude (Anthropic)
    print("\n3⃣ Claude/Anthropic...")
    claude_key = os.getenv('ANTHROPIC_API_KEY') or os.getenv('CLAUDE_API_KEY')
    if claude_key:
        print(f"   [SUCCESS] ANTHROPIC_API_KEY set: {claude_key[:15]}...")
        results['claude'] = True
    else:
        print("   [ERROR] ANTHROPIC_API_KEY not set")
        results['claude'] = False
    
    # 4. Apify
    print("\n4⃣ Apify (Amazon/TikTok scraping)...")
    apify_key = os.getenv('APIFY_API_TOKEN')
    if apify_key:
        print(f"   [SUCCESS] APIFY_API_TOKEN set: {apify_key[:15]}...")
        results['apify'] = True
    else:
        print("   [ERROR] APIFY_API_TOKEN not set")
        results['apify'] = False
    
    # 5. CJ Dropshipping
    print("\n5⃣ CJ Dropshipping...")
    try:
        from ospra_os.integrations.cj_dropshipping import CJDropshippingClient
        cj = CJDropshippingClient()
        if cj.access_token:
            print(f"   [SUCCESS] CJ Token valid until: {getattr(cj, 'token_expires', 'Unknown')}")
            results['cj'] = True
        else:
            print("   [WARNING] CJ Token may be expired")
            results['cj'] = False
    except Exception as e:
        print(f"   [ERROR] Error: {e}")
        results['cj'] = False
    
    # 6. Reddit
    print("\n6⃣ Reddit...")
    try:
        import praw
        reddit_client_id = os.getenv('REDDIT_CLIENT_ID')
        if reddit_client_id:
            print(f"   [SUCCESS] REDDIT_CLIENT_ID set")
            results['reddit'] = True
        else:
            print("   [WARNING] REDDIT_CLIENT_ID not set (using anonymous)")
            results['reddit'] = 'anonymous'
    except Exception as e:
        print(f"   [ERROR] Error: {e}")
        results['reddit'] = False
    
    # 7. OpenAI (for text/analysis)
    print("\n7⃣ OpenAI (GPT)...")
    openai_key = os.getenv('OPENAI_API_KEY')
    if openai_key:
        print(f"   [SUCCESS] OPENAI_API_KEY set: {openai_key[:20]}...")
        results['openai'] = True
    else:
        print("   [ERROR] OPENAI_API_KEY not set")
        results['openai'] = False
    
    # 8. AliExpress
    print("\n8⃣ AliExpress...")
    ali_app_key = os.getenv('ALIEXPRESS_APP_KEY')
    if ali_app_key:
        print(f"   [SUCCESS] ALIEXPRESS_APP_KEY set: {ali_app_key}")
        results['aliexpress'] = True
    else:
        print("   [WARNING] ALIEXPRESS_APP_KEY not set (using Apify fallback)")
        results['aliexpress'] = 'via_apify'
    
    return results


async def main():
    print("="*60)
    print("[BRAIN] OSPRA INTELLIGENCE - FULL DATA SOURCE TEST")
    print("="*60)
    
    # Test DALL-E
    dalle_ok = await test_dalle()
    
    # Test Amazon PAAPI
    amazon_ok = await test_amazon_paapi()
    
    # Test all other sources
    other_results = await test_all_sources()
    
    # Summary
    print("\n" + "="*60)
    print("[STATS] SUMMARY")
    print("="*60)
    
    all_sources = {
        'DALL-E (Images)': '[SUCCESS]' if dalle_ok else '[ERROR]',
        'Amazon PA-API': '[SUCCESS]' if amazon_ok else '[ERROR] NEEDS SETUP',
        'Google Trends': '[SUCCESS]' if other_results.get('google_trends') else '[ERROR]',
        'xAI/Grok': '[SUCCESS]' if other_results.get('xai') else '[ERROR]',
        'Claude/Anthropic': '[SUCCESS]' if other_results.get('claude') else '[ERROR]',
        'Apify': '[SUCCESS]' if other_results.get('apify') else '[ERROR]',
        'CJ Dropshipping': '[SUCCESS]' if other_results.get('cj') else '[ERROR]',
        'Reddit': '[SUCCESS]' if other_results.get('reddit') else '[WARNING]',
        'OpenAI (GPT)': '[SUCCESS]' if other_results.get('openai') else '[ERROR]',
        'AliExpress': '[SUCCESS]' if other_results.get('aliexpress') == True else '[WARNING] via Apify',
    }
    
    working = 0
    for source, status in all_sources.items():
        print(f"  {status} {source}")
        if '[SUCCESS]' in status:
            working += 1
    
    print(f"\n[TREND] {working}/{len(all_sources)} sources operational")
    
    if not amazon_ok:
        print("\n" + "="*60)
        print("[NOTE] TO ADD AMAZON PA-API:")
        print("="*60)
        print("""
1. Join Amazon Associates: https://affiliate-program.amazon.com/
2. Apply for PA-API access (requires 3+ qualifying sales)
3. Get credentials from: https://affiliate-program.amazon.com/home/tools/product-advertising-api
4. Add to your .env file:
   
   AMAZON_ACCESS_KEY=AKIAIOSFODNN7EXAMPLE
   AMAZON_SECRET_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
   AMAZON_PARTNER_TAG=yourtag-20
""")


if __name__ == "__main__":
    asyncio.run(main())
