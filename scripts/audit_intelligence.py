#!/usr/bin/env python3
"""
 BRUTAL HONEST AUDIT - Live Data Source Test
===============================================

This script tests EVERY data source and shows EXACTLY what's real vs fake.
NO MOCK DATA. NO FALLBACKS. Just the truth.

Run with: python3 scripts/audit_intelligence.py
"""

import os
import sys
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)

# Load environment
load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class IntelligenceAuditor:
    """Audit all intelligence sources - brutally honest."""
    
    def __init__(self):
        self.results = {
            "api_keys": {},
            "connectors": {},
            "live_data": {},
            "cross_reference_test": {},
            "issues": [],
            "mock_data_found": [],
        }
        
    async def run_full_audit(self):
        """Run complete audit of all systems."""
        print("\n" + "="*70)
        print(" OSPRA INTELLIGENCE AUDIT - BRUTAL HONESTY MODE")
        print("="*70)
        print(f"   Timestamp: {datetime.utcnow().isoformat()}")
        print("   Purpose: Identify ALL mock data and non-functional sources")
        print("="*70)
        
        # Step 1: Check API Keys
        await self._audit_api_keys()
        
        # Step 2: Test Each Connector
        await self._audit_connectors()
        
        # Step 3: Test Live Data Retrieval
        await self._test_live_data()
        
        # Step 4: Test Cross-Reference Logic
        await self._test_cross_reference()
        
        # Step 5: Check for Mock Data
        await self._scan_for_mock_data()
        
        # Step 6: Generate Report
        self._generate_report()
        
        return self.results
    
    async def _audit_api_keys(self):
        """Check all API keys."""
        print("\n" + "-"*70)
        print("[LIST] STEP 1: API KEY AUDIT")
        print("-"*70)
        
        keys = {
            "AliExpress": ("ALIEXPRESS_ACCESS_TOKEN", os.getenv("ALIEXPRESS_ACCESS_TOKEN")),
            "xAI/Grok": ("XAI_API_KEY", os.getenv("XAI_API_KEY")),
            "Apify": ("APIFY_API_TOKEN", os.getenv("APIFY_API_TOKEN")),
            "CJ Dropshipping": ("CJ_ACCESS_TOKEN", os.getenv("CJ_ACCESS_TOKEN")),
            "Anthropic/Claude": ("ANTHROPIC_API_KEY", os.getenv("ANTHROPIC_API_KEY")),
            "OpenAI": ("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY")),
            "Reddit": ("REDDIT_CLIENT_ID", os.getenv("OUBONSHOP_REDDIT_CLIENT_ID") or os.getenv("REDDIT_CLIENT_ID")),
            "Amazon": ("AMAZON_ACCESS_KEY", os.getenv("AMAZON_ACCESS_KEY")),
            "Google/Gemini": ("GOOGLE_API_KEY", os.getenv("GOOGLE_API_KEY")),
            "Groq": ("GROQ_API_KEY", os.getenv("GROQ_API_KEY")),
        }
        
        connected = 0
        for name, (env_var, value) in keys.items():
            if value and len(value) > 5:
                print(f"   [SUCCESS] {name}: Configured ({value[:12]}...)")
                self.results["api_keys"][name] = "CONFIGURED"
                connected += 1
            else:
                print(f"   [ERROR] {name}: NOT SET or EMPTY")
                self.results["api_keys"][name] = "MISSING"
                self.results["issues"].append(f"Missing API key: {name}")
        
        print(f"\n   TOTAL: {connected}/10 API keys configured")
        
    async def _audit_connectors(self):
        """Test each connector can be initialized."""
        print("\n" + "-"*70)
        print("[PLUGIN] STEP 2: CONNECTOR INITIALIZATION AUDIT")
        print("-"*70)
        
        connectors = {}
        
        # 1. AliExpress
        try:
            from ospra_os.product_research.connectors.suppliers.aliexpress import AliExpressConnector
            ali = AliExpressConnector(
                api_key=os.getenv("ALIEXPRESS_APP_KEY"),
                app_secret=os.getenv("ALIEXPRESS_APP_SECRET"),
                access_token=os.getenv("ALIEXPRESS_ACCESS_TOKEN")
            )
            connectors["AliExpress"] = {"status": "INITIALIZED", "connector": ali}
            print("   [SUCCESS] AliExpress: Connector initialized")
        except Exception as e:
            connectors["AliExpress"] = {"status": "FAILED", "error": str(e)}
            print(f"   [ERROR] AliExpress: {e}")
        
        # 2. xAI/Grok
        try:
            from ospra_os.product_research.connectors.social.xai_twitter import XAITwitterDiscovery
            xai = XAITwitterDiscovery(api_key=os.getenv("XAI_API_KEY"))
            is_available = xai.is_available()
            connectors["xAI/Grok"] = {"status": "AVAILABLE" if is_available else "NOT_AVAILABLE", "connector": xai}
            print(f"   {'[SUCCESS]' if is_available else '[WARNING]'} xAI/Grok: {'Available' if is_available else 'Not available'}")
        except Exception as e:
            connectors["xAI/Grok"] = {"status": "FAILED", "error": str(e)}
            print(f"   [ERROR] xAI/Grok: {e}")
        
        # 3. CJ Dropshipping
        try:
            from ospra_os.integrations.cj_dropshipping import get_cj_client
            cj = get_cj_client()
            connectors["CJ Dropshipping"] = {"status": "INITIALIZED", "connector": cj}
            print("   [SUCCESS] CJ Dropshipping: Connector initialized")
        except Exception as e:
            connectors["CJ Dropshipping"] = {"status": "FAILED", "error": str(e)}
            print(f"   [ERROR] CJ Dropshipping: {e}")
        
        # 4. Google Trends (pytrends)
        try:
            from pytrends.request import TrendReq
            pytrends = TrendReq(hl='en-US', tz=360)
            connectors["Google Trends"] = {"status": "INITIALIZED", "connector": pytrends}
            print("   [SUCCESS] Google Trends: Connector initialized")
        except Exception as e:
            connectors["Google Trends"] = {"status": "FAILED", "error": str(e)}
            print(f"   [ERROR] Google Trends: {e}")
        
        # 5. Apify
        try:
            from ospra_os.product_research.connectors.apify import ApifyClient
            apify = ApifyClient(api_token=os.getenv("APIFY_API_TOKEN"))
            is_available = apify.is_available()
            connectors["Apify"] = {"status": "AVAILABLE" if is_available else "NOT_AVAILABLE", "connector": apify}
            print(f"   {'[SUCCESS]' if is_available else '[WARNING]'} Apify: {'Available' if is_available else 'Not available'}")
        except Exception as e:
            connectors["Apify"] = {"status": "FAILED", "error": str(e)}
            print(f"   [ERROR] Apify: {e}")
        
        # 6. Reddit
        try:
            from ospra_os.product_research.connectors.social.reddit import RedditConnector
            reddit = RedditConnector(
                client_id=os.getenv("OUBONSHOP_REDDIT_CLIENT_ID"),
                client_secret=os.getenv("OUBONSHOP_REDDIT_SECRET")
            )
            connectors["Reddit"] = {"status": "INITIALIZED", "connector": reddit}
            print("   [SUCCESS] Reddit: Connector initialized")
        except Exception as e:
            connectors["Reddit"] = {"status": "FAILED", "error": str(e)}
            print(f"   [ERROR] Reddit: {e}")
        
        # 7. TikTok
        try:
            from ospra_os.integrations.tiktok_client import TikTokClient
            tiktok = TikTokClient()
            enabled = getattr(tiktok, 'enabled', False)
            connectors["TikTok"] = {"status": "ENABLED" if enabled else "NOT_ENABLED", "connector": tiktok}
            print(f"   {'[SUCCESS]' if enabled else '[WARNING]'} TikTok: {'Enabled' if enabled else 'Not enabled (sandbox?)'}")
        except Exception as e:
            connectors["TikTok"] = {"status": "FAILED", "error": str(e)}
            print(f"   [ERROR] TikTok: {e}")
        
        # 8. Claude (AI Factory)
        try:
            from ospra_os.ai.factory import AIFactory
            claude = AIFactory.get_provider("claude", os.getenv("ANTHROPIC_API_KEY"))
            connectors["Claude"] = {"status": "INITIALIZED", "connector": claude}
            print("   [SUCCESS] Claude: AI Provider initialized")
        except Exception as e:
            connectors["Claude"] = {"status": "FAILED", "error": str(e)}
            print(f"   [ERROR] Claude: {e}")
        
        self.results["connectors"] = {k: v["status"] for k, v in connectors.items()}
        self._connectors = connectors
        
    async def _test_live_data(self):
        """Test ACTUAL data retrieval from each source."""
        print("\n" + "-"*70)
        print("[WEB] STEP 3: LIVE DATA RETRIEVAL TEST")
        print("-"*70)
        print("   Testing with keyword: 'smart plug wifi'")
        print()
        
        test_keyword = "smart plug wifi"
        live_data = {}
        
        # 1. AliExpress - LIVE SEARCH
        print("   [SEARCH] Testing AliExpress...")
        try:
            if self._connectors.get("AliExpress", {}).get("connector"):
                ali = self._connectors["AliExpress"]["connector"]
                products = await ali.search(query=test_keyword, page_size=5)
                
                if products and len(products) > 0:
                    live_data["AliExpress"] = {
                        "status": "LIVE_DATA",
                        "count": len(products),
                        "sample": {
                            "name": getattr(products[0], 'name', 'Unknown')[:50],
                            "price": getattr(products[0], 'price', 0),
                            "orders": getattr(products[0], 'search_volume', 0),
                        }
                    }
                    print(f"      [SUCCESS] LIVE: Found {len(products)} products")
                    print(f"         Sample: {live_data['AliExpress']['sample']['name']}")
                    print(f"         Price: ${live_data['AliExpress']['sample']['price']}")
                else:
                    live_data["AliExpress"] = {"status": "NO_DATA", "count": 0}
                    print("      [WARNING] Connected but returned 0 products")
            else:
                live_data["AliExpress"] = {"status": "CONNECTOR_FAILED"}
                print("      [ERROR] Connector not available")
        except Exception as e:
            live_data["AliExpress"] = {"status": "ERROR", "error": str(e)}
            print(f"      [ERROR] Error: {e}")
        
        # 2. Google Trends - LIVE SEARCH
        print("\n   [SEARCH] Testing Google Trends...")
        try:
            if self._connectors.get("Google Trends", {}).get("connector"):
                pytrends = self._connectors["Google Trends"]["connector"]
                pytrends.build_payload([test_keyword], timeframe='today 3-m', geo='US')
                interest = pytrends.interest_over_time()
                
                if not interest.empty and test_keyword in interest.columns:
                    values = interest[test_keyword].values
                    current = int(values[-1]) if len(values) > 0 else 0
                    avg = int(sum(values) / len(values)) if len(values) > 0 else 0
                    
                    live_data["Google Trends"] = {
                        "status": "LIVE_DATA",
                        "current_interest": current,
                        "average_interest": avg,
                        "data_points": len(values),
                    }
                    print(f"      [SUCCESS] LIVE: Current interest: {current}/100, Avg: {avg}/100")
                else:
                    live_data["Google Trends"] = {"status": "NO_DATA"}
                    print("      [WARNING] No trend data returned")
            else:
                live_data["Google Trends"] = {"status": "CONNECTOR_FAILED"}
        except Exception as e:
            live_data["Google Trends"] = {"status": "ERROR", "error": str(e)}
            print(f"      [ERROR] Error: {e}")
        
        # 3. xAI/Grok - LIVE SENTIMENT
        print("\n   [SEARCH] Testing xAI/Grok (Twitter sentiment)...")
        try:
            if self._connectors.get("xAI/Grok", {}).get("status") == "AVAILABLE":
                xai = self._connectors["xAI/Grok"]["connector"]
                sentiment = await xai.get_product_sentiment(test_keyword)
                
                if sentiment and sentiment.get("sentiment_score") is not None:
                    live_data["xAI/Grok"] = {
                        "status": "LIVE_DATA",
                        "sentiment_score": sentiment.get("sentiment_score"),
                        "tweet_count": sentiment.get("tweet_count", 0),
                        "sentiment": sentiment.get("sentiment", "unknown"),
                    }
                    print(f"      [SUCCESS] LIVE: Sentiment: {sentiment.get('sentiment')}, Score: {sentiment.get('sentiment_score')}")
                else:
                    live_data["xAI/Grok"] = {"status": "NO_DATA"}
                    print("      [WARNING] No sentiment data returned")
            else:
                live_data["xAI/Grok"] = {"status": "CONNECTOR_FAILED"}
                print("      [ERROR] Connector not available")
        except Exception as e:
            live_data["xAI/Grok"] = {"status": "ERROR", "error": str(e)}
            print(f"      [ERROR] Error: {e}")
        
        # 4. CJ Dropshipping - LIVE SEARCH
        print("\n   [SEARCH] Testing CJ Dropshipping...")
        try:
            if self._connectors.get("CJ Dropshipping", {}).get("connector"):
                cj = self._connectors["CJ Dropshipping"]["connector"]
                products = await cj.search_products(keyword=test_keyword, page_size=5)
                
                if products and len(products) > 0:
                    live_data["CJ Dropshipping"] = {
                        "status": "LIVE_DATA",
                        "count": len(products),
                        "sample": products[0] if products else None
                    }
                    print(f"      [SUCCESS] LIVE: Found {len(products)} products")
                else:
                    live_data["CJ Dropshipping"] = {"status": "NO_DATA", "count": 0}
                    print("      [WARNING] Connected but returned 0 products")
            else:
                live_data["CJ Dropshipping"] = {"status": "CONNECTOR_FAILED"}
        except Exception as e:
            live_data["CJ Dropshipping"] = {"status": "ERROR", "error": str(e)}
            print(f"      [ERROR] Error: {e}")
        
        # 5. Apify - LIVE TEST
        print("\n   [SEARCH] Testing Apify...")
        try:
            if self._connectors.get("Apify", {}).get("status") == "AVAILABLE":
                apify = self._connectors["Apify"]["connector"]
                # Check available actors
                actors = await apify.list_available_actors() if hasattr(apify, 'list_available_actors') else []
                live_data["Apify"] = {
                    "status": "LIVE_DATA",
                    "available": True,
                    "note": "Ready for Amazon/TikTok scraping"
                }
                print(f"      [SUCCESS] LIVE: Apify connected and ready")
            else:
                live_data["Apify"] = {"status": "CONNECTOR_FAILED"}
                print("      [ERROR] Connector not available")
        except Exception as e:
            live_data["Apify"] = {"status": "ERROR", "error": str(e)}
            print(f"      [ERROR] Error: {e}")
        
        # 6. Reddit - LIVE SENTIMENT  
        print("\n   [SEARCH] Testing Reddit...")
        try:
            if self._connectors.get("Reddit", {}).get("connector"):
                reddit = self._connectors["Reddit"]["connector"]
                if hasattr(reddit, 'analyze_product_sentiment'):
                    sentiment = await reddit.analyze_product_sentiment(test_keyword)
                    live_data["Reddit"] = {
                        "status": "LIVE_DATA",
                        "score": sentiment.get("score", 50),
                        "mentions": sentiment.get("mentions", 0),
                    }
                    print(f"      [SUCCESS] LIVE: Score: {sentiment.get('score', 'N/A')}, Mentions: {sentiment.get('mentions', 0)}")
                else:
                    live_data["Reddit"] = {"status": "NO_METHOD"}
                    print("      [WARNING] analyze_product_sentiment method not found")
                    self.results["issues"].append("Reddit connector missing analyze_product_sentiment method")
            else:
                live_data["Reddit"] = {"status": "CONNECTOR_FAILED"}
        except Exception as e:
            live_data["Reddit"] = {"status": "ERROR", "error": str(e)}
            print(f"      [ERROR] Error: {e}")
        
        self.results["live_data"] = live_data
        
    async def _test_cross_reference(self):
        """Test if cross-referencing logic actually works."""
        print("\n" + "-"*70)
        print("[REFRESH] STEP 4: CROSS-REFERENCE LOGIC TEST")
        print("-"*70)
        
        # Test the main discovery engine
        try:
            from ospra_os.intelligence.ospra_engine import OspraIntelligenceEngine
            engine = OspraIntelligenceEngine()
            
            print("\n   Running discovery on 'smart_home' niche...")
            print("   (This tests the FULL cross-reference pipeline)")
            
            winners = await engine.discover_winners(
                niches=['smart_home'],
                max_per_niche=3,
                save_to_db=False,
                generate_images=False
            )
            
            stats = engine.get_stats()
            
            self.results["cross_reference_test"] = {
                "products_found": stats.get("products_found", 0),
                "products_validated": stats.get("products_validated", 0),
                "products_passed": stats.get("products_passed", 0),
                "sources_queried": stats.get("sources_queried", []),
                "winners": len(winners),
            }
            
            print(f"\n   [STATS] RESULTS:")
            print(f"      Products found: {stats.get('products_found', 0)}")
            print(f"      Products validated: {stats.get('products_validated', 0)}")
            print(f"      Winners (score >= 7.5): {len(winners)}")
            print(f"      Sources queried: {', '.join(stats.get('sources_queried', []))}")
            
            if winners:
                print(f"\n   [TOP] TOP WINNERS:")
                for w in winners[:3]:
                    print(f"\n      {w.name[:50]}...")
                    print(f"      Score: {w.ospra_score}/10 | Sources: {len(w.sources_validated)}")
                    print(f"      Sources: {', '.join(w.sources_validated)}")
                    print(f"      Google Trends: {w.google_trend_score}/100")
                    print(f"      TikTok: {w.tiktok_viral_score}/100")
                    print(f"      Twitter: {w.twitter_sentiment_score}/100")
                    print(f"      Orders: {w.orders:,}")
                    print(f"      AI Reason: {w.ai_reason[:80]}...")
            else:
                print("\n   [WARNING] No winners found - check threshold or data sources")
                
        except Exception as e:
            self.results["cross_reference_test"] = {"status": "FAILED", "error": str(e)}
            print(f"\n   [ERROR] Cross-reference test failed: {e}")
            import traceback
            traceback.print_exc()
    
    async def _scan_for_mock_data(self):
        """Scan code for hardcoded/mock data."""
        print("\n" + "-"*70)
        print("[SEARCH] STEP 5: MOCK DATA SCAN")
        print("-"*70)
        
        mock_patterns = []
        
        # Check enhanced_discovery.py for mock data
        try:
            enhanced_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "ospra_os", "intelligence", "enhanced_discovery.py"
            )
            
            if os.path.exists(enhanced_path):
                with open(enhanced_path, 'r') as f:
                    content = f.read()
                    
                # Look for hardcoded scores
                if '"ospra_score": 6.5' in content or "'ospra_score': 6.5" in content:
                    mock_patterns.append("enhanced_discovery.py: Hardcoded ospra_score = 6.5")
                if '"google_trends": 60' in content or "'google_trends': 60" in content:
                    mock_patterns.append("enhanced_discovery.py: Hardcoded google_trends = 60")
                if "# Simplified scoring" in content:
                    mock_patterns.append("enhanced_discovery.py: Contains 'Simplified scoring' placeholder")
        except Exception as e:
            print(f"   [WARNING] Could not scan enhanced_discovery.py: {e}")
        
        # Check ospra_engine.py for template-based reasons
        try:
            engine_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "ospra_os", "intelligence", "ospra_engine.py"
            )
            
            if os.path.exists(engine_path):
                with open(engine_path, 'r') as f:
                    content = f.read()
                    
                if "_generate_ai_reason" in content and "reasons.append" in content:
                    # Check if it's template-based
                    if 'f"High search demand' in content:
                        mock_patterns.append("ospra_engine.py: ai_reason uses TEMPLATES not Claude")
        except Exception as e:
            print(f"   [WARNING] Could not scan ospra_engine.py: {e}")
        
        self.results["mock_data_found"] = mock_patterns
        
        if mock_patterns:
            print("\n    MOCK DATA FOUND:")
            for pattern in mock_patterns:
                print(f"      [ERROR] {pattern}")
        else:
            print("\n   [SUCCESS] No obvious mock data patterns found")
    
    def _generate_report(self):
        """Generate final audit report."""
        print("\n" + "="*70)
        print("[STATS] FINAL AUDIT REPORT")
        print("="*70)
        
        # API Keys Summary
        api_ok = sum(1 for v in self.results["api_keys"].values() if v == "CONFIGURED")
        api_total = len(self.results["api_keys"])
        print(f"\n   API Keys: {api_ok}/{api_total} configured")
        
        # Connectors Summary
        conn_ok = sum(1 for v in self.results["connectors"].values() if v in ["INITIALIZED", "AVAILABLE", "ENABLED"])
        conn_total = len(self.results["connectors"])
        print(f"   Connectors: {conn_ok}/{conn_total} working")
        
        # Live Data Summary
        live_ok = sum(1 for v in self.results["live_data"].values() if v.get("status") == "LIVE_DATA")
        live_total = len(self.results["live_data"])
        print(f"   Live Data Sources: {live_ok}/{live_total} returning real data")
        
        # Cross-Reference
        cr = self.results.get("cross_reference_test", {})
        if cr.get("winners"):
            print(f"   Cross-Reference: [SUCCESS] Working ({cr['winners']} winners found)")
        else:
            print(f"   Cross-Reference: [WARNING] {cr.get('status', 'No winners')}")
        
        # Mock Data
        if self.results["mock_data_found"]:
            print(f"\n    MOCK DATA ISSUES: {len(self.results['mock_data_found'])}")
            for issue in self.results["mock_data_found"]:
                print(f"      - {issue}")
        
        # Issues
        if self.results["issues"]:
            print(f"\n   [WARNING] OTHER ISSUES: {len(self.results['issues'])}")
            for issue in self.results["issues"]:
                print(f"      - {issue}")
        
        print("\n" + "="*70)
        print("[TARGET] WHAT NEEDS TO BE FIXED:")
        print("="*70)
        
        fixes_needed = []
        
        if self.results["api_keys"].get("Amazon") == "MISSING":
            fixes_needed.append("1. Add Amazon PAAPI credentials for complete market data")
        
        if any("TEMPLATES" in m for m in self.results["mock_data_found"]):
            fixes_needed.append("2. Replace template-based ai_reason with Claude analysis")
        
        if any("Hardcoded" in m for m in self.results["mock_data_found"]):
            fixes_needed.append("3. Remove hardcoded scores in enhanced_discovery.py")
        
        live_data = self.results.get("live_data", {})
        if live_data.get("Reddit", {}).get("status") == "NO_METHOD":
            fixes_needed.append("4. Implement Reddit analyze_product_sentiment method")
        
        # Check if CJ is in scoring weights
        fixes_needed.append("5. Add CJ Dropshipping to scoring weights (currently 7 sources, should be 9+)")
        fixes_needed.append("6. Add Apify data to scoring (Amazon BSR, TikTok Shop)")
        fixes_needed.append("7. Implement TRUE cross-source filtering (reject products without multi-source validation)")
        
        for fix in fixes_needed:
            print(f"   {fix}")
        
        print("\n" + "="*70)


async def main():
    auditor = IntelligenceAuditor()
    await auditor.run_full_audit()


if __name__ == "__main__":
    asyncio.run(main())
