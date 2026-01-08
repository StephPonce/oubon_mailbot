#!/usr/bin/env python3
"""
[HOT] TEST TREND-FIRST DISCOVERY
==============================

This discovers products based on what's TRENDING NOW,
not the same old AliExpress bestsellers.

Run with:
    cd "/Users/stephenponce/Documents/Ospra OS/Bots/Ospra OS"
    uv run python scripts/test_trend_discovery.py
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


async def main():
    from ospra_os.intelligence.trend_first_discovery import (
        TrendFirstDiscovery,
        DynamicKeywordGenerator,
        test_trend_first_discovery
    )
    
    await test_trend_first_discovery()


if __name__ == "__main__":
    asyncio.run(main())
