"""Reddit connector for community-driven product discovery."""

from typing import List, Optional
import asyncio
import re
from ..base import BaseConnector, ProductCandidate


class RedditConnector(BaseConnector):
    """
    Reddit integration for product discovery and validation.

    Use Reddit API (PRAW) to:
    - Monitor product subreddits (r/ProductPorn, r/shutupandtakemymoney)
    - Track product mentions
    - Analyze community sentiment
    - Find viral products

    Setup:
    1. Create Reddit app at reddit.com/prefs/apps
    2. Set REDDIT_CLIENT_ID, REDDIT_SECRET in .env
    """

    def __init__(self, client_id: Optional[str] = None, client_secret: Optional[str] = None):
        super().__init__(api_key=client_id)
        self.client_id = client_id
        self.client_secret = client_secret
        # Use a more descriptive user agent (Reddit requires platform:app_name:version format)
        self.user_agent = "web:OspraOS:v1.0 (by /u/OspraBot)"

    @property
    def name(self) -> str:
        return "Reddit"

    @property
    def source_id(self) -> str:
        return "reddit"

    def is_available(self) -> bool:
        """Reddit JSON API is always available (no auth required for public subreddits)."""
        return True  # Public JSON API doesn't require credentials

    def _extract_product_name(self, title: str) -> str:
        """Extract product name from Reddit post title."""
        # Remove common Reddit title patterns
        title = re.sub(r'\[.*?\]', '', title)  # Remove [tags]
        title = re.sub(r'\(.*?\)', '', title)  # Remove (parentheses)
        title = re.sub(r'Check out|Look at|Just got|My new|Love my', '', title, flags=re.IGNORECASE)
        return title.strip()[:100]  # Limit to 100 chars

    def _calculate_engagement_score(self, post) -> float:
        """Calculate engagement score from Reddit metrics."""
        upvotes = post.score
        comments = post.num_comments
        upvote_ratio = post.upvote_ratio

        # Weighted score: upvotes (50%) + comments (30%) + ratio (20%)
        score = (upvotes * 0.5) + (comments * 10 * 0.3) + (upvote_ratio * 100 * 0.2)
        return round(score, 2)

    async def search(self, query: str, **kwargs) -> List[ProductCandidate]:
        """
        Search Reddit for product mentions.

        Args:
            query: Product name or category
            subreddits: List of subreddits to search (default: product-focused subs)
            time_filter: 'day', 'week', 'month', 'year', 'all'

        Returns:
            Product candidates with Reddit engagement data
        """
        if not self.is_available():
            print("⚠️  Reddit API credentials not configured")
            return []

        try:
            import praw
        except ImportError:
            print("⚠️  praw not installed. Run: pip install praw")
            return []

        subreddits = kwargs.get("subreddits", ["smarthome", "homeautomation", "HomeKit", "amazonecho"])
        time_filter = kwargs.get("time_filter", "month")
        limit = kwargs.get("limit", 25)

        # Initialize Reddit client in read-only mode (no user auth needed for public subs)
        reddit = praw.Reddit(
            client_id=self.client_id,
            client_secret=self.client_secret,
            user_agent=self.user_agent,
            check_for_async=False  # We handle async ourselves
        )
        reddit.read_only = True  # Enable read-only mode

        products = []

        try:
            # Search each subreddit
            for subreddit_name in subreddits:
                try:
                    subreddit = reddit.subreddit(subreddit_name)

                    # Search for query in subreddit
                    loop = asyncio.get_event_loop()
                    search_results = await loop.run_in_executor(
                        None,
                        lambda: list(subreddit.search(query, time_filter=time_filter, limit=limit))
                    )

                    for post in search_results:
                        # Skip removed/deleted posts
                        if post.removed_by_category or post.selftext == '[removed]':
                            continue

                        # Extract product info
                        product_name = self._extract_product_name(post.title)
                        engagement_score = self._calculate_engagement_score(post)

                        product = ProductCandidate(
                            name=product_name,
                            source=self.source_id,
                            url=f"https://reddit.com{post.permalink}",
                            social_mentions=post.score,
                            social_engagement=post.num_comments,
                            trend_score=engagement_score,
                            category=subreddit_name,
                            tags=["reddit", "community-validated"]
                        )
                        products.append(product)

                except Exception as e:
                    print(f"⚠️  Error searching r/{subreddit_name}: {e}")
                    continue

            print(f"✅ Reddit search: Found {len(products)} products for '{query}'")
            return products

        except Exception as e:
            print(f"❌ Reddit search error: {e}")
            return []

    async def get_trending(self, category: Optional[str] = None, limit: int = 10) -> List[ProductCandidate]:
        """
        Get hot/trending products on Reddit.

        Args:
            category: Product category
            limit: Max results

        Returns:
            Trending products from Reddit communities
        """
        if not self.is_available():
            print("⚠️  Reddit API credentials not configured")
            return []

        try:
            import praw
        except ImportError:
            print("⚠️  praw not installed. Run: pip install praw")
            return []

        # Initialize Reddit client in read-only mode (no user auth needed for public subs)
        reddit = praw.Reddit(
            client_id=self.client_id,
            client_secret=self.client_secret,
            user_agent=self.user_agent,
            check_for_async=False  # We handle async ourselves
        )
        reddit.read_only = True  # Enable read-only mode

        # Target subreddits based on category
        if category and category.lower() in ["smart home", "home automation", "iot"]:
            subreddits = ["smarthome", "homeautomation", "HomeKit"]
        else:
            subreddits = ["shutupandtakemymoney", "ProductPorn", "BuyItForLife"]

        products = []

        try:
            for subreddit_name in subreddits:
                try:
                    subreddit = reddit.subreddit(subreddit_name)

                    # Get hot posts
                    loop = asyncio.get_event_loop()
                    hot_posts = await loop.run_in_executor(
                        None,
                        lambda: list(subreddit.hot(limit=limit))
                    )

                    for post in hot_posts:
                        # Skip stickied posts and removed content
                        if post.stickied or post.removed_by_category:
                            continue

                        product_name = self._extract_product_name(post.title)
                        engagement_score = self._calculate_engagement_score(post)

                        product = ProductCandidate(
                            name=product_name,
                            source=self.source_id,
                            url=f"https://reddit.com{post.permalink}",
                            social_mentions=post.score,
                            social_engagement=post.num_comments,
                            trend_score=engagement_score,
                            category=subreddit_name,
                            tags=["reddit", "trending", "hot"]
                        )
                        products.append(product)

                except Exception as e:
                    print(f"⚠️  Error fetching hot posts from r/{subreddit_name}: {e}")
                    continue

            print(f"✅ Reddit trending: Found {len(products)} hot products")
            return products

        except Exception as e:
            print(f"❌ Reddit trending error: {e}")
            return []

    async def get_subreddit_products(self, subreddit: str, time_filter: str = "week", limit: int = 25) -> List[ProductCandidate]:
        """
        Get top products from a specific subreddit using Reddit's public JSON API.

        Args:
            subreddit: Subreddit name (without r/)
            time_filter: Time period ('hour', 'day', 'week', 'month', 'year', 'all')
            limit: Max posts to analyze

        Returns:
            Product candidates from subreddit
        """
        # Use Reddit's public JSON API (no auth required for public subreddits)
        import aiohttp

        url = f"https://www.reddit.com/r/{subreddit}/top.json"
        params = {
            "t": time_filter,  # time filter
            "limit": min(limit, 100)  # Reddit max is 100
        }
        headers = {
            "User-Agent": self.user_agent
        }

        products = []

        try:
            print(f"🔍 Fetching r/{subreddit} - URL: {url}, params: {params}")
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers) as response:
                    print(f"📡 Response status: {response.status}")
                    if response.status != 200:
                        resp_text = await response.text()
                        print(f"❌ Reddit API error for r/{subreddit}: HTTP {response.status}")
                        print(f"Response: {resp_text[:200]}")
                        return []

                    data = await response.json()
                    posts = data.get("data", {}).get("children", [])
                    print(f"📊 Received {len(posts)} posts from r/{subreddit}")

                    filtered_stickied = 0
                    filtered_removed = 0
                    for post_wrapper in posts:
                        post = post_wrapper.get("data", {})

                        # Skip stickied posts
                        if post.get("stickied", False):
                            filtered_stickied += 1
                            continue

                        # Skip removed/deleted posts
                        if post.get("removed_by_category") or post.get("selftext") == "[removed]":
                            filtered_removed += 1
                            continue

                        # Extract product info
                        title = post.get("title", "")
                        product_name = self._extract_product_name(title)

                        # Calculate engagement score
                        score = post.get("score", 0)
                        num_comments = post.get("num_comments", 0)
                        upvote_ratio = post.get("upvote_ratio", 0.5)

                        engagement_score = (score * 0.5) + (num_comments * 10 * 0.3) + (upvote_ratio * 100 * 0.2)
                        engagement_score = round(engagement_score, 2)

                        product = ProductCandidate(
                            name=product_name,
                            source=self.source_id,
                            url=f"https://reddit.com{post.get('permalink', '')}",
                            social_mentions=score,
                            social_engagement=num_comments,
                            trend_score=engagement_score,
                            category=subreddit,
                            tags=["reddit", f"top_{time_filter}"]
                        )
                        products.append(product)

                    print(f"🔧 Filtered: {filtered_stickied} stickied, {filtered_removed} removed")

            print(f"✅ r/{subreddit}: Found {len(products)} top products")
            return products

        except Exception as e:
            print(f"❌ Error fetching from r/{subreddit}: {e}")
            return []
