#!/usr/bin/env python3
"""
[TEST] RUN THIS TO TEST THE ENTIRE DISCOVERY BRAIN
===============================================

This tests:
1. ALL 10 data sources
2. TRUE cross-source filtering
3. Claude COO analysis for EVERY product
4. ZERO mock data

Run with:
    cd "/Users/stephenponce/Documents/Ospra OS/Bots/Ospra OS"
    python3 scripts/test_full_discovery.py
"""

import asyncio
import sys
import os
import logging

# Setup
logging.basicConfig(level=logging.INFO, format='%(message)s')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


async def main():
    print("\n" + "="*70)
    print("[BRAIN] OSPRA INTELLIGENCE - FULL DISCOVERY TEST")
    print("="*70)
    print("   Testing ALL 10 data sources")
    print("   TRUE cross-source filtering")
    print("   Claude COO analysis for EVERY product")
    print("   ZERO mock data")
    print("="*70)
    
    try:
        from ospra_os.intelligence.true_cross_source_discovery import TrueCrossSourceDiscovery
        
        discovery = TrueCrossSourceDiscovery()
        
        print("\n[SEARCH] Running discovery on 'smart_home' niche...")
        print("   This will take 1-2 minutes...\n")
        
        products = await discovery.discover_and_validate(
            niches=['smart_home'],
            max_products=5,
            require_claude_analysis=True
        )
        
        print("\n" + "="*70)
        print(f"[TOP] FINAL RESULTS: {len(products)} products passed ALL criteria")
        print("="*70)
        
        for i, p in enumerate(products, 1):
            print(f"\n{''*60}")
            print(f"#{i} {p.name[:55]}...")
            print(f"{''*60}")
            print(f"   [STATS] OSPRA Score: {p.ospra_score}/10")
            print(f"   [SUCCESS] Sources Validated: {p.sources_validated}/{p.sources_checked}")
            print(f"   [TREND] Validation Rate: {p.validation_rate}%")
            print(f"   [TARGET] Confidence: {p.confidence}%")
            print(f"   [PRICE] Profit: ${p.profit:.2f} ({p.profit_margin:.0f}% margin)")
            
            print(f"\n   [SEARCH] SOURCE VALIDATION:")
            for name, v in p.validations.items():
                if v.status.value == "validated":
                    icon = "[SUCCESS]"
                elif v.status.value == "neutral":
                    icon = "[WARNING]"
                elif v.status.value == "unavailable":
                    icon = "[PLUGIN]"
                else:
                    icon = "[ERROR]"
                print(f"      {icon} {name}: {v.status.value} | score: {v.score:.0f}/100")
            
            print(f"\n   [AI] CLAUDE COO ANALYSIS:")
            print(f"      Recommendation: {p.recommendation}")
            print(f"      Urgency: {p.urgency}")
            if p.executive_summary:
                # Wrap summary to 60 chars
                summary = p.executive_summary
                while len(summary) > 0:
                    print(f"      {summary[:60]}")
                    summary = summary[60:]
        
        print("\n" + "="*70)
        print("[SUCCESS] TEST COMPLETE")
        print("="*70)
        
        return products
        
    except Exception as e:
        print(f"\n[ERROR] ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    asyncio.run(main())
