"""Product discovery pipeline combining multiple data sources."""

from typing import List, Dict, Optional
from .connectors.social.reddit import RedditConnector
from .connectors.suppliers.aliexpress import AliExpressConnector
from .connectors.trends.google_trends import GoogleTrendsConnector
from .scorer import ProductScorer


class ProductDiscoveryPipeline:
    """
    End-to-end product discovery pipeline.

    Flow:
    1. Search Reddit for trending products in niche
    2. Search Google Trends for validation
    3. Search AliExpress for sourcing options
    4. Score and rank all candidates
    5. Return top products
    """

    def __init__(
        self,
        reddit_client_id: Optional[str] = None,
        reddit_secret: Optional[str] = None,
        aliexpress_api_key: Optional[str] = None,
        aliexpress_app_secret: Optional[str] = None
    ):
        self.reddit = RedditConnector(client_id=reddit_client_id, client_secret=reddit_secret)
        self.aliexpress = AliExpressConnector(api_key=aliexpress_api_key, app_secret=aliexpress_app_secret)
        self.google_trends = GoogleTrendsConnector()
        self.scorer = ProductScorer()

    async def discover_products(
        self,
        niche: str,
        max_results: int = 10,
        min_score: float = 5.0,
        include_reddit: bool = True,
        include_aliexpress: bool = True,
        include_trends: bool = True
    ) -> List[Dict]:
        """
        Run full product discovery pipeline.

        Args:
            niche: Product niche/category to research
            max_results: Maximum products to return
            min_score: Minimum score threshold
            include_reddit: Include Reddit social validation
            include_aliexpress: Include AliExpress sourcing
            include_trends: Include Google Trends data

        Returns:
            List of scored products with all data
        """
        all_candidates = []

        # Step 1: Search Reddit for trending products
        if include_reddit and self.reddit.is_available():
            try:
                print(f"🔍 Searching Reddit for '{niche}'...")
                reddit_products = await self.reddit.search(niche, time_filter="month", limit=20)
                all_candidates.extend(reddit_products)
                print(f"✅ Reddit: Found {len(reddit_products)} candidates")
            except Exception as e:
                print(f"⚠️  Reddit search failed: {e}")

        # Step 2: Search Google Trends for validation
        if include_trends:
            try:
                print(f"📈 Checking Google Trends for '{niche}'...")
                trends_products = await self.google_trends.search(niche, category=None)
                all_candidates.extend(trends_products)
                print(f"✅ Google Trends: Found {len(trends_products)} candidates")
            except Exception as e:
                print(f"⚠️  Google Trends search failed: {e}")

        # Step 3: Search AliExpress for sourcing
        if include_aliexpress and self.aliexpress.is_available():
            try:
                print(f"📦 Searching AliExpress for '{niche}'...")
                aliexpress_products = await self.aliexpress.search(niche)
                all_candidates.extend(aliexpress_products)
                print(f"✅ AliExpress: Found {len(aliexpress_products)} candidates")
            except Exception as e:
                print(f"⚠️  AliExpress search failed: {e}")

        if not all_candidates:
            print("❌ No products found from any source")
            return []

        # Step 4: Score and rank all candidates
        print(f"🎯 Scoring {len(all_candidates)} total candidates...")
        ranked = self.scorer.rank(all_candidates, limit=max_results * 2)  # Get 2x for filtering

        # Step 5: Filter by minimum score
        filtered = [r for r in ranked if r["score"] >= min_score][:max_results]

        print(f"✅ Pipeline complete: {len(filtered)} products above score {min_score}")
        return filtered

    async def discover_niche_winners(
        self,
        subreddits: List[str],
        max_results: int = 15
    ) -> List[Dict]:
        """
        Discover winning products from specific subreddits.

        Args:
            subreddits: List of subreddit names to monitor
            max_results: Max products to return

        Returns:
            Top products with sourcing options
        """
        all_candidates = []

        # Get trending products from each subreddit
        if self.reddit.is_available():
            for subreddit in subreddits:
                try:
                    print(f"🔍 Scanning r/{subreddit}...")
                    products = await self.reddit.get_subreddit_products(
                        subreddit=subreddit,
                        time_filter="week",
                        limit=25
                    )
                    all_candidates.extend(products)
                    print(f"✅ r/{subreddit}: Found {len(products)} products")
                except Exception as e:
                    print(f"⚠️  r/{subreddit} failed: {e}")

        if not all_candidates:
            return []

        # Score and rank
        ranked = self.scorer.rank(all_candidates, limit=max_results)

        # For top products, try to find sourcing on AliExpress
        if self.aliexpress.is_available():
            for product in ranked[:max_results]:
                try:
                    product_name = product["product"]["name"]
                    print(f"📦 Finding sourcing for: {product_name}")

                    # Search AliExpress for this product
                    sourcing_options = await self.aliexpress.search(product_name, limit=3)

                    if sourcing_options:
                        product["sourcing"] = [
                            {
                                "name": s.name,
                                "price": s.price,
                                "url": s.url,
                                "image": s.image_url,
                                "supplier_rating": s.supplier_rating
                            }
                            for s in sourcing_options[:3]
                        ]
                        print(f"✅ Found {len(sourcing_options)} sourcing options")
                except Exception as e:
                    print(f"⚠️  Sourcing lookup failed: {e}")
                    product["sourcing"] = []

        return ranked[:max_results]

    async def validate_product_idea(self, product_name: str) -> Dict:
        """
        Validate a product idea across all data sources.

        Args:
            product_name: Product name to validate

        Returns:
            Validation report with scores and recommendations
        """
        print(f"🔍 Validating product idea: '{product_name}'")

        validation = {
            "product_name": product_name,
            "reddit_validation": None,
            "trends_validation": None,
            "sourcing_available": False,
            "overall_score": 0.0,
            "recommendation": ""
        }

        # Check Reddit community interest
        if self.reddit.is_available():
            try:
                reddit_results = await self.reddit.search(product_name, limit=10)
                if reddit_results:
                    avg_engagement = sum(p.trend_score or 0 for p in reddit_results) / len(reddit_results)
                    validation["reddit_validation"] = {
                        "mentions": len(reddit_results),
                        "avg_engagement": round(avg_engagement, 2),
                        "top_post": reddit_results[0].url if reddit_results else None
                    }
            except Exception as e:
                print(f"⚠️  Reddit validation failed: {e}")

        # Check Google Trends
        try:
            trends_results = await self.google_trends.search(product_name)
            if trends_results:
                validation["trends_validation"] = {
                    "trend_score": trends_results[0].trend_score,
                    "search_volume": trends_results[0].search_volume
                }
        except Exception as e:
            print(f"⚠️  Trends validation failed: {e}")

        # Check sourcing availability
        if self.aliexpress.is_available():
            try:
                sourcing = await self.aliexpress.search(product_name, limit=5)
                validation["sourcing_available"] = len(sourcing) > 0
                if sourcing:
                    validation["sourcing_options"] = len(sourcing)
                    validation["price_range"] = {
                        "min": min(s.price for s in sourcing if s.price),
                        "max": max(s.price for s in sourcing if s.price)
                    }
            except Exception as e:
                print(f"⚠️  Sourcing check failed: {e}")

        # Calculate overall score
        score = 0.0
        if validation["reddit_validation"]:
            score += min(validation["reddit_validation"]["mentions"] * 0.5, 5.0)  # Max 5 points
        if validation["trends_validation"]:
            score += min(validation["trends_validation"]["trend_score"] / 10, 3.0)  # Max 3 points
        if validation["sourcing_available"]:
            score += 2.0  # 2 points for sourcing

        validation["overall_score"] = round(score, 2)

        # Generate recommendation
        if score >= 8:
            validation["recommendation"] = "✅ STRONG - High demand, community interest, and available sourcing"
        elif score >= 5:
            validation["recommendation"] = "⚠️  MODERATE - Some validation, proceed with caution"
        else:
            validation["recommendation"] = "❌ WEAK - Limited validation, risky opportunity"

        print(f"✅ Validation complete: Score {validation['overall_score']}/10")
        return validation
