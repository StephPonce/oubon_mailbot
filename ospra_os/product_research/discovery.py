"""
Product Discovery Engine - Complete workflow for finding winning products.

This module implements the full product discovery pipeline:
1. Search Reddit for trending products
2. Validate with Google Trends
3. Find sourcing on AliExpress (when OAuth available)
4. Score and rank candidates
5. Return top products with priority labels
"""

from typing import List, Dict, Optional
from datetime import datetime
from .connectors.social.reddit import RedditConnector
from .connectors.trends.google_trends import GoogleTrendsConnector
from .connectors.suppliers.aliexpress import AliExpressConnector
from .connectors.base import ProductCandidate
from .scorer import ProductScorer


class ProductDiscoveryEngine:
    """
    Complete product discovery engine.

    Usage:
        engine = ProductDiscoveryEngine(
            reddit_client_id="...",
            reddit_secret="...",
            aliexpress_api_key="..."  # Optional
        )

        # Discover products in a niche
        results = await engine.discover(
            niche="smart home devices",
            max_results=15,
            min_score=5.0
        )

        # Validate a specific product idea
        validation = await engine.validate_product("wireless charging pad")
    """

    def __init__(
        self,
        reddit_client_id: Optional[str] = None,
        reddit_secret: Optional[str] = None,
        aliexpress_api_key: Optional[str] = None,
        aliexpress_app_secret: Optional[str] = None,
    ):
        """
        Initialize discovery engine with API credentials.

        Args:
            reddit_client_id: Reddit app client ID
            reddit_secret: Reddit app secret
            aliexpress_api_key: AliExpress app key (optional)
            aliexpress_app_secret: AliExpress app secret (optional)
        """
        self.reddit = RedditConnector(
            client_id=reddit_client_id,
            client_secret=reddit_secret
        )
        self.google_trends = GoogleTrendsConnector()
        self.aliexpress = AliExpressConnector(
            api_key=aliexpress_api_key,
            app_secret=aliexpress_app_secret
        )
        self.scorer = ProductScorer()

        # Track discovery stats
        self.stats = {
            "total_discovered": 0,
            "total_searches": 0,
            "last_search": None,
        }

    async def discover(
        self,
        niche: str,
        max_results: int = 15,
        min_score: float = 5.0,
        include_reddit: bool = True,
        include_trends: bool = True,
        include_aliexpress: bool = False,  # Default False since OAuth may not be ready
    ) -> Dict:
        """
        Run full product discovery for a niche.

        Args:
            niche: Product niche/category (e.g., "smart home", "fitness gear")
            max_results: Maximum products to return
            min_score: Minimum score threshold (0-10)
            include_reddit: Include Reddit community validation
            include_trends: Include Google Trends data
            include_aliexpress: Include AliExpress sourcing (requires OAuth)

        Returns:
            {
                "niche": str,
                "total_found": int,
                "high_priority": int,
                "medium_priority": int,
                "low_priority": int,
                "products": List[Dict],
                "search_time": str,
            }
        """
        print(f"\n{'='*70}")
        print(f"🚀 PRODUCT DISCOVERY: {niche.upper()}")
        print(f"{'='*70}\n")

        start_time = datetime.now()
        all_candidates = []

        # Step 1: Search Reddit for trending products
        if include_reddit and self.reddit.is_available():
            print(f"🔍 Step 1: Searching Reddit for '{niche}'...")
            try:
                reddit_products = await self.reddit.search(
                    niche,
                    subreddits=self._get_subreddits_for_niche(niche),
                    time_filter="month",
                    limit=25
                )
                all_candidates.extend(reddit_products)
                print(f"   ✅ Found {len(reddit_products)} products on Reddit\n")
            except Exception as e:
                print(f"   ❌ Reddit search failed: {e}\n")
        else:
            print("   ⏭️  Reddit search skipped (not configured)\n")

        # Step 2: Check Google Trends for validation
        if include_trends:
            print(f"📈 Step 2: Checking Google Trends for '{niche}'...")
            try:
                trends_data = await self.google_trends.search(niche)
                all_candidates.extend(trends_data)
                print(f"   ✅ Got trend data: Score {trends_data[0].trend_score if trends_data else 'N/A'}\n")
            except Exception as e:
                print(f"   ⚠️  Google Trends check failed: {e}\n")

        # Step 3: Search AliExpress for sourcing (if OAuth available)
        if include_aliexpress and self.aliexpress.is_available():
            print(f"📦 Step 3: Finding AliExpress sourcing options...")
            try:
                aliexpress_products = await self.aliexpress.search(niche, limit=10)
                all_candidates.extend(aliexpress_products)
                print(f"   ✅ Found {len(aliexpress_products)} sourcing options\n")
            except Exception as e:
                print(f"   ⚠️  AliExpress search failed: {e}\n")
        else:
            print("   ⏭️  AliExpress search skipped (OAuth not ready)\n")

        if not all_candidates:
            print("❌ No products found from any source\n")
            return {
                "niche": niche,
                "total_found": 0,
                "high_priority": 0,
                "medium_priority": 0,
                "low_priority": 0,
                "products": [],
                "search_time": str(datetime.now() - start_time),
                "error": "No products found"
            }

        # Step 4: Score and rank all candidates
        print(f"🎯 Step 4: Scoring {len(all_candidates)} total candidates...")
        ranked = self.scorer.rank(all_candidates, limit=max_results * 2)

        # Step 5: Filter by minimum score
        filtered = [r for r in ranked if r["score"] >= min_score][:max_results]

        # Count by priority
        priority_counts = {
            "high": sum(1 for p in filtered if p["priority"] == "HIGH"),
            "medium": sum(1 for p in filtered if p["priority"] == "MEDIUM"),
            "low": sum(1 for p in filtered if p["priority"] == "LOW"),
        }

        # Update stats
        self.stats["total_discovered"] += len(filtered)
        self.stats["total_searches"] += 1
        self.stats["last_search"] = datetime.now().isoformat()

        search_time = datetime.now() - start_time

        print(f"   ✅ Scored all products\n")
        print(f"{'='*70}")
        print(f"✅ DISCOVERY COMPLETE")
        print(f"{'='*70}")
        print(f"Found: {len(filtered)} products above score {min_score}")
        print(f"  🔥 HIGH PRIORITY: {priority_counts['high']}")
        print(f"  ✅ MEDIUM PRIORITY: {priority_counts['medium']}")
        print(f"  ⚠️  LOW PRIORITY: {priority_counts['low']}")
        print(f"Search time: {search_time.total_seconds():.1f}s\n")

        return {
            "niche": niche,
            "total_found": len(filtered),
            "high_priority": priority_counts["high"],
            "medium_priority": priority_counts["medium"],
            "low_priority": priority_counts["low"],
            "products": filtered,
            "search_time": str(search_time),
        }

    async def validate_product(self, product_name: str) -> Dict:
        """
        Validate a specific product idea across all sources.

        Args:
            product_name: Product name to validate

        Returns:
            {
                "product_name": str,
                "overall_score": float,
                "priority": str,
                "recommendation": str,
                "validation": {
                    "reddit": {...},
                    "trends": {...},
                    "sourcing": {...}
                }
            }
        """
        print(f"\n🔍 VALIDATING: {product_name}")
        print("-" * 70)

        validation = {
            "product_name": product_name,
            "reddit_mentions": 0,
            "trends_score": None,
            "sourcing_available": False,
            "overall_score": 0.0,
            "priority": "LOW",
            "recommendation": "",
        }

        # Check Reddit community interest
        if self.reddit.is_available():
            try:
                print("   Checking Reddit mentions...")
                reddit_results = await self.reddit.search(product_name, limit=15)

                if reddit_results:
                    validation["reddit_mentions"] = len(reddit_results)
                    avg_score = sum(p.trend_score or 0 for p in reddit_results) / len(reddit_results)

                    validation["reddit_data"] = {
                        "mentions": len(reddit_results),
                        "avg_engagement_score": round(avg_score, 2),
                        "top_post_url": reddit_results[0].url if reddit_results else None,
                    }
                    print(f"   ✅ Found {len(reddit_results)} mentions on Reddit")
            except Exception as e:
                print(f"   ⚠️  Reddit check failed: {e}")

        # Check Google Trends
        try:
            print("   Checking Google Trends...")
            trends_results = await self.google_trends.search(product_name)

            if trends_results and trends_results[0].trend_score:
                validation["trends_score"] = trends_results[0].trend_score
                validation["trends_data"] = {
                    "trend_score": trends_results[0].trend_score,
                    "search_volume": trends_results[0].search_volume,
                }
                print(f"   ✅ Trend score: {trends_results[0].trend_score}/100")
        except Exception as e:
            print(f"   ⚠️  Trends check failed: {e}")

        # Check sourcing availability
        if self.aliexpress.is_available():
            try:
                print("   Checking AliExpress sourcing...")
                sourcing = await self.aliexpress.search(product_name, limit=5)

                if sourcing:
                    validation["sourcing_available"] = True
                    validation["sourcing_data"] = {
                        "options_found": len(sourcing),
                        "price_range": {
                            "min": min(s.price for s in sourcing if s.price),
                            "max": max(s.price for s in sourcing if s.price),
                        }
                    }
                    print(f"   ✅ Found {len(sourcing)} sourcing options")
            except Exception as e:
                print(f"   ⚠️  Sourcing check failed: {e}")

        # Calculate overall score based on validation data
        score = 0.0

        # Reddit mentions (max 4 points)
        if validation["reddit_mentions"] >= 10:
            score += 4.0
        elif validation["reddit_mentions"] >= 5:
            score += 3.0
        elif validation["reddit_mentions"] >= 2:
            score += 2.0
        elif validation["reddit_mentions"] >= 1:
            score += 1.0

        # Trends score (max 3 points)
        if validation["trends_score"]:
            score += min(3.0, validation["trends_score"] / 33)

        # Sourcing availability (3 points)
        if validation["sourcing_available"]:
            score += 3.0

        validation["overall_score"] = round(score, 2)

        # Determine priority and recommendation
        if score >= 7.0:
            validation["priority"] = "HIGH"
            validation["recommendation"] = "🔥 STRONG CANDIDATE - High demand, trending, and sourceable"
        elif score >= 4.0:
            validation["priority"] = "MEDIUM"
            validation["recommendation"] = "✅ MODERATE CANDIDATE - Some validation signals present"
        else:
            validation["priority"] = "LOW"
            validation["recommendation"] = "⚠️  WEAK CANDIDATE - Limited validation data"

        print(f"\n   Score: {validation['overall_score']}/10")
        print(f"   Priority: {validation['priority']}")
        print(f"   {validation['recommendation']}")
        print("-" * 70 + "\n")

        return validation

    def _get_subreddits_for_niche(self, niche: str) -> List[str]:
        """Get relevant subreddits based on niche."""
        niche_lower = niche.lower()

        if any(term in niche_lower for term in ["smart home", "automation", "iot", "alexa", "google home"]):
            return ["smarthome", "homeautomation", "HomeKit", "amazonecho"]
        elif any(term in niche_lower for term in ["fitness", "workout", "gym", "exercise"]):
            return ["fitness", "homegym", "bodyweightfitness"]
        elif any(term in niche_lower for term in ["pet", "dog", "cat"]):
            return ["pets", "dogs", "cats"]
        elif any(term in niche_lower for term in ["kitchen", "cooking", "food"]):
            return ["Cooking", "KitchenConfidential"]
        else:
            # Default broad product subreddits
            return ["shutupandtakemymoney", "ProductPorn", "BuyItForLife"]

    def get_stats(self) -> Dict:
        """Get discovery engine statistics."""
        return {
            "total_discovered": self.stats["total_discovered"],
            "total_searches": self.stats["total_searches"],
            "last_search": self.stats["last_search"],
            "apis_available": {
                "reddit": self.reddit.is_available(),
                "google_trends": True,
                "aliexpress": self.aliexpress.is_available(),
            }
        }
