#!/usr/bin/env python3
"""
[TEST] OSPRA INTELLIGENCE ENGINE - COMPREHENSIVE TEST SUITE
=========================================================

Tests ALL components of the discovery pipeline:
1. Google Trends connector
2. xAI Twitter discovery (100+ hashtags, 15+ niches)
3. AliExpress product search
4. TikTok viral detection
5. Apify Amazon/TikTok scraping
6. Hybrid image generation (DALL-E + Gemini)
7. Full discovery pipeline
8. Cross-validation scoring

Run this to verify your entire system is working!
"""

import os
import sys
import asyncio
from datetime import datetime
from typing import Dict, List, Any

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def print_header(title: str):
    print("\n" + "="*70)
    print(f"[TEST] {title}")
    print("="*70)


def print_result(name: str, success: bool, details: str = ""):
    status = "[SUCCESS]" if success else "[ERROR]"
    print(f"   {status} {name}: {details}")


async def test_google_trends():
    """Test Google Trends connector"""
    print_header("GOOGLE TRENDS CONNECTOR")
    
    try:
        from pytrends.request import TrendReq
        import time
        
        # Add delay and retry for rate limiting
        pytrends = TrendReq(hl='en-US', tz=360, retries=2, backoff_factor=0.5)
        
        # Wait a bit before making request (rate limiting)
        await asyncio.sleep(1)
        
        # Test a simple search
        pytrends.build_payload(['smart home'], timeframe='today 3-m', geo='US')
        interest = pytrends.interest_over_time()
        
        if not interest.empty:
            current = int(interest['smart home'].iloc[-1])
            print_result("pytrends", True, f"Current interest: {current}/100")
            return True
        else:
            print_result("pytrends", False, "Empty response")
            return False
            
    except ImportError:
        print_result("pytrends", False, "Not installed - pip install pytrends")
        return False
    except Exception as e:
        error_msg = str(e)
        if '429' in error_msg:
            print_result("pytrends", False, "Rate limited (429) - wait and retry")
        else:
            print_result("pytrends", False, error_msg)
        return False


async def test_xai_twitter():
    """Test xAI Twitter discovery"""
    print_header("XAI TWITTER DISCOVERY (Grok-2)")
    
    try:
        from ospra_os.product_research.connectors.social.xai_twitter import XAITwitterDiscovery
        
        discovery = XAITwitterDiscovery()
        
        if not discovery.is_available():
            print_result("xAI Connection", False, "XAI_API_KEY not set")
            return False
        
        print_result("xAI Connection", True, "Connected to Grok-2")
        
        # Check niches and hashtags
        niches = discovery.get_all_niches()
        hashtags = discovery.get_all_hashtags()
        
        print_result("Niches Available", True, f"{len(niches)} niches")
        print_result("Hashtags Available", True, f"{len(hashtags)} hashtags")
        
        # Test actual discovery
        print("\n    Testing live discovery (smart_home)...")
        products = await discovery.discover_viral_products(
            niche="smart_home",
            max_products=3,
            time_range="24h"
        )
        
        if products:
            print_result("Viral Discovery", True, f"Found {len(products)} products")
            for p in products[:2]:
                print(f"      [HOT] {p.name[:40]}... | Score: {p.viral_score}")
        else:
            print_result("Viral Discovery", False, "No products found")
            
        return len(products) > 0
        
    except ImportError as e:
        print_result("xAI Import", False, str(e))
        return False
    except Exception as e:
        print_result("xAI Twitter", False, str(e))
        return False


async def test_aliexpress():
    """Test AliExpress connector"""
    print_header("ALIEXPRESS API")
    
    try:
        from ospra_os.product_research.connectors.suppliers.aliexpress import AliExpressConnector
        
        api_key = os.getenv('ALIEXPRESS_APP_KEY')
        app_secret = os.getenv('ALIEXPRESS_APP_SECRET')
        access_token = os.getenv('ALIEXPRESS_ACCESS_TOKEN')
        
        if not all([api_key, app_secret, access_token]):
            print_result("AliExpress Config", False, "Missing credentials")
            return False
        
        connector = AliExpressConnector(
            api_key=api_key,
            app_secret=app_secret,
            access_token=access_token
        )
        
        print_result("AliExpress Config", True, "Credentials set")
        
        # Test search
        print("\n    Testing product search...")
        products = await connector.search(query="smart plug wifi", min_rating=4.0)
        
        if products:
            print_result("Product Search", True, f"Found {len(products)} products")
            for p in products[:2]:
                name = getattr(p, 'name', 'Unknown')[:40]
                price = getattr(p, 'price', 0)
                print(f"      [PACKAGE] {name}... | ${price:.2f}")
        else:
            print_result("Product Search", False, "No products found")
            
        return len(products) > 0
        
    except ImportError as e:
        print_result("AliExpress Import", False, str(e))
        return False
    except Exception as e:
        print_result("AliExpress", False, str(e))
        return False


async def test_tiktok():
    """Test TikTok client"""
    print_header("TIKTOK API")
    
    try:
        from ospra_os.integrations.tiktok_client import TikTokClient
        
        client = TikTokClient()
        enabled = getattr(client, 'enabled', False)
        
        if enabled:
            print_result("TikTok Client", True, "Configured and enabled")
        else:
            print_result("TikTok Client", False, "Client loaded but not enabled")
            
        return enabled
        
    except ImportError as e:
        print_result("TikTok Import", False, str(e))
        return False
    except Exception as e:
        print_result("TikTok", False, str(e))
        return False


async def test_apify():
    """Test Apify scraping"""
    print_header("APIFY CLIENT")
    
    try:
        from ospra_os.product_research.connectors.apify.base_apify import ApifyClient
        
        apify_token = os.getenv('APIFY_API_TOKEN')
        if not apify_token:
            print_result("Apify Config", False, "APIFY_API_TOKEN not set")
            return False
        
        client = ApifyClient(api_token=apify_token)
        
        # Test connection
        print("\n    Testing Apify connection...")
        connection = await client.test_connection()
        
        if connection.get('connected'):
            print_result("Apify Connection", True, f"User: {connection.get('username')}")
            print_result("Apify Plan", True, connection.get('plan', 'unknown'))
            return True
        else:
            print_result("Apify Connection", False, connection.get('error', 'Unknown error'))
            return False
        
    except ImportError as e:
        print_result("Apify Import", False, str(e))
        return False
    except Exception as e:
        print_result("Apify", False, str(e))
        return False


async def test_cj_dropshipping():
    """Test CJ Dropshipping API"""
    print_header("CJ DROPSHIPPING")
    
    try:
        cj_token = os.getenv('CJ_ACCESS_TOKEN')
        if not cj_token:
            print_result("CJ Config", False, "CJ_ACCESS_TOKEN not set")
            return False
        
        from ospra_os.integrations.cj_dropshipping import get_cj_client
        
        client = get_cj_client()
        print_result("CJ Client", True, "Initialized")
        
        return True
        
    except ImportError as e:
        print_result("CJ Import", False, str(e))
        return False
    except Exception as e:
        print_result("CJ Dropshipping", False, str(e))
        return False


async def test_image_generator():
    """Test hybrid image generator"""
    print_header("HYBRID IMAGE GENERATOR")
    
    try:
        from ospra_os.media.ai_image_generator import AIImageGenerator, ImageProvider
        
        generator = AIImageGenerator()
        
        providers = generator.available_providers
        print_result("Providers Detected", True, f"{len(providers)} providers")
        
        for p in providers:
            if p != ImageProvider.MOCK:
                print(f"      [OK] {p.value}")
        
        # Check DALL-E
        dalle_available = ImageProvider.DALLE in providers
        print_result("DALL-E (Premium)", dalle_available, "OpenAI API" if dalle_available else "OPENAI_API_KEY not set")
        
        # Check Gemini
        gemini_available = ImageProvider.GEMINI in providers
        print_result("Gemini Imagen (Bulk)", gemini_available, "Google API" if gemini_available else "GOOGLE_API_KEY not set")
        
        return dalle_available or gemini_available
        
    except ImportError as e:
        print_result("Image Generator Import", False, str(e))
        return False
    except Exception as e:
        print_result("Image Generator", False, str(e))
        return False


async def test_ai_providers():
    """Test AI providers"""
    print_header("AI PROVIDERS")
    
    results = {}
    
    # Claude
    try:
        anthropic_key = os.getenv('ANTHROPIC_API_KEY')
        print_result("Claude (Anthropic)", bool(anthropic_key), "API key set" if anthropic_key else "ANTHROPIC_API_KEY not set")
        results['claude'] = bool(anthropic_key)
    except:
        results['claude'] = False
    
    # OpenAI
    try:
        openai_key = os.getenv('OPENAI_API_KEY')
        print_result("OpenAI (GPT-4)", bool(openai_key), "API key set" if openai_key else "OPENAI_API_KEY not set")
        results['openai'] = bool(openai_key)
    except:
        results['openai'] = False
    
    # xAI (Grok)
    try:
        xai_key = os.getenv('XAI_API_KEY')
        print_result("xAI (Grok-2)", bool(xai_key), "API key set" if xai_key else "XAI_API_KEY not set")
        results['xai'] = bool(xai_key)
    except:
        results['xai'] = False
    
    # Gemini
    try:
        google_key = os.getenv('GOOGLE_API_KEY')
        print_result("Gemini (Google)", bool(google_key), "API key set" if google_key else "GOOGLE_API_KEY not set")
        results['gemini'] = bool(google_key)
    except:
        results['gemini'] = False
    
    # Groq (Llama)
    try:
        groq_key = os.getenv('GROQ_API_KEY')
        print_result("Groq (Llama)", bool(groq_key), "API key set" if groq_key else "GROQ_API_KEY not set")
        results['groq'] = bool(groq_key)
    except:
        results['groq'] = False
    
    return sum(results.values())


async def test_full_engine():
    """Test the full Ospra Intelligence Engine"""
    print_header("OSPRA INTELLIGENCE ENGINE (Full Pipeline)")
    
    try:
        from ospra_os.intelligence.ospra_engine import OspraIntelligenceEngine
        
        engine = OspraIntelligenceEngine()
        
        # Get stats
        stats = engine.get_stats()
        connected = stats.get('connected_sources', {})
        
        total = sum(1 for v in connected.values() if v)
        print_result("Engine Initialized", True, f"{total}/{len(connected)} sources connected")
        
        for source, status in connected.items():
            if status:
                print(f"      [OK] {source}")
        
        # Test discovery (quick - just 1 niche, 2 products)
        print("\n    Testing live discovery pipeline...")
        winners = await engine.discover_winners(
            niches=['smart_home'],
            max_per_niche=2,
            save_to_db=False,
            generate_images=False
        )
        
        if winners:
            print_result("Discovery Pipeline", True, f"Found {len(winners)} winners")
            for w in winners[:2]:
                print(f"      [TOP] {w.name[:35]}... | Score: {w.ospra_score}/10")
                print(f"         Sources: {', '.join(w.sources_validated)}")
        else:
            print_result("Discovery Pipeline", False, "No winners found (might be data issues)")
            
        return len(winners) > 0
        
    except ImportError as e:
        print_result("Engine Import", False, str(e))
        return False
    except Exception as e:
        import traceback
        print_result("Engine", False, str(e))
        traceback.print_exc()
        return False


async def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("[START] OSPRA INTELLIGENCE - COMPREHENSIVE TEST SUITE")
    print(f"   Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    results = {}
    
    # Test each component
    results['google_trends'] = await test_google_trends()
    results['xai_twitter'] = await test_xai_twitter()
    results['aliexpress'] = await test_aliexpress()
    results['tiktok'] = await test_tiktok()
    results['apify'] = await test_apify()
    results['cj_dropshipping'] = await test_cj_dropshipping()
    results['image_generator'] = await test_image_generator()
    results['ai_providers'] = await test_ai_providers() >= 2  # At least 2 AI providers
    results['full_engine'] = await test_full_engine()
    
    # Summary
    print_header("TEST SUMMARY")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test, passed_test in results.items():
        status = "[SUCCESS] PASS" if passed_test else "[ERROR] FAIL"
        print(f"   {status}: {test.replace('_', ' ').title()}")
    
    print(f"\n   [STATS] TOTAL: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n   [LAUNCH] ALL SYSTEMS OPERATIONAL!")
    elif passed >= total * 0.7:
        print("\n   [WARNING]  Most systems working. Check failed tests.")
    else:
        print("\n    Multiple systems failing. Check your .env file.")
    
    print("\n" + "="*70)
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
