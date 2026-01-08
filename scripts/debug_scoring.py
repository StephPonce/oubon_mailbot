#!/usr/bin/env python3
"""
[SEARCH] DEBUG CROSS-REFERENCE SCORING
=================================

This script tests EACH data source individually to see:
1. Which sources are actually returning data
2. What scores each source is providing
3. Why all products might be getting the same score

Run with: python3 scripts/debug_scoring.py
"""

import os
import sys
import asyncio
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


async def debug_single_product():
    """Debug scoring for a single test product."""
    
    print("\n" + "="*70)
    print("[SEARCH] DEBUG: Cross-Reference Scoring Test")
    print("="*70)
    
    test_product = {
        "name": "Smart Plug WiFi 16A",
        "orders": 15000,
        "rating": 4.5,
        "price": 6.50,
    }
    
    print(f"\n[PACKAGE] Test Product: {test_product['name']}")
    print(f"   Orders: {test_product['orders']:,}")
    print(f"   Rating: {test_product['rating']}")
    print(f"   Price: ${test_product['price']}")
    
    # Initialize components
    print("\n[STATS] Initializing data sources...")
    
    # 1. Check OspraIntelligenceEngine
    try:
        from ospra_os.intelligence.ospra_engine import OspraIntelligenceEngine
        engine = OspraIntelligenceEngine()
        
        print(f"\n   Google Trends enabled: {getattr(engine, 'google_trends_enabled', False)}")
        print(f"   xAI enabled: {getattr(engine, 'xai_enabled', False)}")
        print(f"   Reddit enabled: {getattr(engine, 'reddit_enabled', False)}")
        print(f"   TikTok enabled: {getattr(engine, 'tiktok_enabled', False)}")
        
        # Check if pytrends exists
        has_pytrends = hasattr(engine, 'pytrends')
        print(f"   pytrends object: {has_pytrends}")
        
        if has_pytrends and engine.google_trends_enabled:
            print("\n   [SEARCH] Testing Google Trends API...")
            try:
                engine.pytrends.build_payload(["smart plug"], timeframe='today 3-m', geo='US')
                interest = engine.pytrends.interest_over_time()
                if not interest.empty:
                    print(f"   [SUCCESS] Google Trends returned data: {len(interest)} rows")
                    if "smart plug" in interest.columns:
                        latest = interest["smart plug"].values[-1]
                        print(f"   [SUCCESS] Latest interest: {latest}/100")
                else:
                    print("   [WARNING] Google Trends returned empty data")
            except Exception as e:
                print(f"   [ERROR] Google Trends error: {e}")
        
        # Check xAI
        if hasattr(engine, 'xai_twitter') and engine.xai_enabled:
            print("\n   [SEARCH] Testing xAI/Twitter API...")
            try:
                sentiment = await engine.xai_twitter.get_product_sentiment("smart plug")
                if sentiment:
                    print(f"   [SUCCESS] xAI returned: {sentiment}")
                else:
                    print("   [WARNING] xAI returned None")
            except Exception as e:
                print(f"   [ERROR] xAI error: {e}")
        else:
            print("\n   [WARNING] xAI not available on engine")
            print(f"      hasattr xai_twitter: {hasattr(engine, 'xai_twitter')}")
            print(f"      xai_enabled: {getattr(engine, 'xai_enabled', 'not set')}")
        
    except Exception as e:
        print(f"   [ERROR] OspraIntelligenceEngine failed: {e}")
        import traceback
        traceback.print_exc()
    
    # 2. Test Enhanced Discovery Pipeline directly
    print("\n" + "-"*50)
    print("[TEST] Testing Enhanced Discovery Pipeline...")
    
    try:
        from ospra_os.intelligence.enhanced_discovery import EnhancedDiscoveryPipeline
        
        pipeline = EnhancedDiscoveryPipeline()
        
        print(f"\n   Discovery enabled: {pipeline.discovery_enabled}")
        print(f"   Saturation enabled: {pipeline.saturation_enabled}")
        print(f"   COO enabled: {pipeline.coo_enabled}")
        print(f"   AliExpress enabled: {pipeline.aliexpress_enabled}")
        
        # Test _get_base_scores directly
        print("\n   [SEARCH] Testing _get_base_scores() method...")
        
        scores = await pipeline._get_base_scores(
            product_name="Smart Plug WiFi 16A",
            niche="smart_home",
            raw_product=test_product
        )
        
        print(f"\n   [STATS] RETURNED SCORES:")
        print(f"      OSPRA Score: {scores.get('ospra_score')}/10")
        print(f"      Google Trends: {scores.get('google_trends')}/100")
        print(f"      TikTok Viral: {scores.get('tiktok_viral')}/100")
        print(f"      Twitter Sentiment: {scores.get('twitter_sentiment')}/100")
        print(f"      AliExpress Orders: {scores.get('aliexpress_orders')}/100")
        print(f"      Amazon Rank: {scores.get('amazon_rank')}/100")
        print(f"      Reddit Sentiment: {scores.get('reddit_sentiment')}/100")
        print(f"      Supplier Rating: {scores.get('supplier_rating')}/100")
        print(f"      Sources Validated: {scores.get('sources')}")
        print(f"      Confidence: {scores.get('confidence')}%")
        
    except Exception as e:
        print(f"   [ERROR] Enhanced Discovery Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
    
    # 3. Test with a DIFFERENT product to see if scores vary
    print("\n" + "-"*50)
    print("[TEST] Testing with DIFFERENT product (LED Strip)...")
    
    try:
        test_product_2 = {
            "name": "LED Strip Lights RGB 5050",
            "orders": 500,
            "rating": 3.8,
            "price": 2.50,
        }
        
        scores_2 = await pipeline._get_base_scores(
            product_name="LED Strip Lights RGB 5050",
            niche="smart_home",
            raw_product=test_product_2
        )
        
        print(f"\n   [STATS] PRODUCT 2 SCORES:")
        print(f"      OSPRA Score: {scores_2.get('ospra_score')}/10")
        print(f"      AliExpress Orders: {scores_2.get('aliexpress_orders')}/100")
        print(f"      Supplier Rating: {scores_2.get('supplier_rating')}/100")
        print(f"      Sources Validated: {scores_2.get('sources')}")
        
        # Compare
        print(f"\n   [TREND] COMPARISON:")
        print(f"      Product 1 OSPRA: {scores.get('ospra_score')}/10")
        print(f"      Product 2 OSPRA: {scores_2.get('ospra_score')}/10")
        
        if scores.get('ospra_score') == scores_2.get('ospra_score'):
            print(f"\n   [WARNING] SCORES ARE IDENTICAL - This indicates API calls are failing!")
        else:
            print(f"\n   [SUCCESS] SCORES ARE DIFFERENT - Cross-referencing is working!")
            
    except Exception as e:
        print(f"   [ERROR] Test 2 failed: {e}")
    
    print("\n" + "="*70)
    print("[SUCCESS] DEBUG COMPLETE")
    print("="*70)


if __name__ == "__main__":
    asyncio.run(debug_single_product())
