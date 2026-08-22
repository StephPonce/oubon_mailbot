"""
TikTok Client for Product Discovery
Discover trending products from TikTok videos using official API
"""

import os
import re
import requests
import logging
from typing import Dict, List, Optional
from datetime import datetime
from urllib.parse import urlencode
from dotenv import load_dotenv

# Load .env file to ensure environment variables are available
# override=True forces .env values to take precedence over shell env vars
# — except in tests, where the harness has already fixed up the env (e.g.
# pinning DATABASE_URL to the per-worker SQLite file). Overriding there
# would clobber those test-only values with real Neon Postgres credentials
# from .env and break unrelated tests that touch settings-derived URLs.
_in_tests = os.getenv("APP_ENV") == "testing" or "PYTEST_CURRENT_TEST" in os.environ
load_dotenv(override=not _in_tests)

logger = logging.getLogger(__name__)


class TikTokClient:
    """TikTok API client for viral product discovery"""

    def __init__(self):
        self.client_key = os.getenv("TIKTOK_CLIENT_KEY")
        self.client_secret = os.getenv("TIKTOK_CLIENT_SECRET")
        self.redirect_uri = os.getenv("TIKTOK_REDIRECT_URI")
        self.access_token = os.getenv("TIKTOK_ACCESS_TOKEN")  # Optional: for server-to-server

        if not self.client_key or not self.client_secret:
            logger.warning("TikTok credentials not configured")
            self.enabled = False
        else:
            self.enabled = True
            logger.info("[SUCCESS] TikTok Client initialized")

        self.base_url = "https://open.tiktokapis.com/v2"
        self.auth_url = "https://www.tiktok.com/v2/auth/authorize"

        # Product categories for price estimation
        self.category_prices = {
            "smart_home": {"min": 15, "max": 150},
            "fitness": {"min": 20, "max": 200},
            "beauty": {"min": 10, "max": 80},
            "kitchen": {"min": 15, "max": 120},
            "tech": {"min": 25, "max": 300},
            "fashion": {"min": 15, "max": 100},
            "pets": {"min": 10, "max": 80},
            "kids": {"min": 15, "max": 100},
            "outdoor": {"min": 20, "max": 200},
            "general": {"min": 15, "max": 100}
        }

    def get_authorization_url(self, state: str = None) -> str:
        """
        Generate OAuth authorization URL for user to grant access

        Args:
            state: Optional state parameter for CSRF protection

        Returns:
            Authorization URL
        """
        if not self.enabled:
            return None

        # Scopes MUST match exactly what's enabled in the TikTok Developer
        # Portal → Scopes tab. Requesting a scope here that isn't enabled
        # in the portal triggers a "scope mismatch" rejection during app
        # review (May 2026 — confirmed by review feedback).
        #
        # Currently enabled in portal:
        #   - user.info.basic    (Login Kit)
        #   - user.info.profile  (Login Kit)
        #   - user.info.stats    (Login Kit)
        #   - video.publish      (Content Posting API — Direct Post)
        #   - video.upload       (Content Posting API — Upload as Draft)
        #
        # `video.list` was previously requested here but is NOT in the
        # approved scope list — removed to fix the mismatch.
        params = {
            "client_key": self.client_key,
            "response_type": "code",
            "scope": "user.info.basic,user.info.profile,user.info.stats,video.publish,video.upload",
            "redirect_uri": self.redirect_uri,
        }

        if state:
            params["state"] = state

        return f"{self.auth_url}?{urlencode(params)}"

    def exchange_code_for_token(self, code: str) -> Optional[Dict]:
        """
        Exchange authorization code for access token

        Args:
            code: Authorization code from OAuth callback

        Returns:
            Token response with access_token, refresh_token, expires_in
        """
        if not self.enabled:
            return None

        url = "https://open.tiktokapis.com/v2/oauth/token/"

        data = {
            "client_key": self.client_key,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": self.redirect_uri
        }

        try:
            response = requests.post(url, json=data, timeout=30)

            if response.status_code == 200:
                token_data = response.json()
                logger.info("[SUCCESS] TikTok access token obtained")
                return token_data
            else:
                logger.error(f"Token exchange failed: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            logger.error(f"Token exchange error: {e}")
            return None

    def search_trending_products(
        self,
        keywords: List[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """
        Search for trending products on TikTok

        Args:
            keywords: List of product keywords to search (e.g., ["smart home", "fitness"])
            limit: Maximum products to return

        Returns:
            List of product dictionaries with viral metrics
        """
        if not keywords:
            keywords = [
                "smart home", "fitness gadget", "kitchen tool",
                "beauty product", "tech gadget", "home organization"
            ]

        all_products = []

        for keyword in keywords:
            logger.info(f"[SEARCH] Searching TikTok for: {keyword}")

            # Search videos for this keyword
            videos = self._search_videos(keyword, limit=20)

            # Extract products from videos
            for video in videos:
                product = self._extract_product_from_video(video, keyword)
                if product:
                    all_products.append(product)

            if len(all_products) >= limit:
                break

        # Sort by viral score (highest first)
        all_products.sort(key=lambda x: x.get("viral_score", 0), reverse=True)

        return all_products[:limit]

    def _search_videos(self, keyword: str, limit: int = 20) -> List[Dict]:
        """
        Search TikTok videos by keyword

        Args:
            keyword: Search keyword
            limit: Max videos to return

        Returns:
            List of video dictionaries
        """
        if not self.enabled or not self.access_token:
            logger.warning("TikTok API not configured")
            return []  # Return empty list to allow priority chain to continue

        # Note: TikTok's official API has limited search capabilities
        # This is a placeholder for the real implementation
        # You may need to use TikTok Research API or partner with a data provider

        url = f"{self.base_url}/research/video/query/"

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        # Example query structure (check TikTok API docs for exact format)
        query = {
            "query": {
                "and": [
                    {"field_name": "keyword", "operation": "IN", "field_values": [keyword]}
                ]
            },
            "max_count": limit
        }

        try:
            response = requests.post(url, headers=headers, json=query, timeout=30)

            if response.status_code == 200:
                data = response.json()
                return data.get("data", {}).get("videos", [])
            else:
                logger.warning(f"TikTok API returned {response.status_code}")
                return []  # Return empty list to allow priority chain to continue

        except Exception as e:
            logger.error(f"TikTok video search error: {e}")
            return []  # Return empty list to allow priority chain to continue

    # _get_fallback_videos removed 2026-08 — fabricated view/like/comment counts and fake TikTok URLs; had zero callers.

    def _extract_product_from_video(self, video: Dict, search_keyword: str) -> Optional[Dict]:
        """
        Extract product information from TikTok video metadata

        Args:
            video: Video dictionary from TikTok API
            search_keyword: Original search keyword for context

        Returns:
            Product dictionary or None if no product found
        """
        try:
            # Extract product name from video description or title
            description = video.get("description", "")
            product_name = self._extract_product_name(description, search_keyword)

            if not product_name:
                return None

            # Get statistics
            stats = video.get("statistics", {})
            views = stats.get("view_count", 0)
            likes = stats.get("like_count", 0)
            comments = stats.get("comment_count", 0)
            shares = stats.get("share_count", 0)

            # Calculate viral score (0-100)
            viral_score = self._calculate_viral_score(views, likes, comments, shares)

            # Estimate price based on category
            estimated_price = self._estimate_price(product_name, search_keyword)

            # Calculate profit margin (typical dropshipping: 2-3x markup)
            cost = estimated_price / 2.5
            profit = estimated_price - cost
            margin = (profit / estimated_price) * 100

            return {
                "id": f"tiktok_{video['id']}",
                "name": product_name,
                "description": description[:200],
                "price": round(estimated_price, 2),
                "cost": round(cost, 2),
                "profit_margin": round(margin, 1),
                "estimated_profit": round(profit, 2),
                "source": "tiktok",
                "source_url": video.get("video_url", ""),
                "category": search_keyword,
                "viral_score": viral_score,
                "velocity_score": min(100, int(viral_score * 1.2)),  # Convert viral to velocity
                "orders": views // 100,  # Estimate: 1% conversion
                "rating": round(4.0 + (viral_score / 100), 1),
                "statistics": {
                    "views": views,
                    "likes": likes,
                    "comments": comments,
                    "shares": shares,
                    "engagement_rate": round(((likes + comments + shares) / views) * 100, 2) if views > 0 else 0
                },
                "discovered_at": datetime.now().isoformat(),
                "score": min(10, int((viral_score / 100) * 10)),  # Convert to 0-10 scale
            }

        except Exception as e:
            logger.error(f"Error extracting product from video: {e}")
            return None

    def _extract_product_name(self, description: str, category: str) -> Optional[str]:
        """
        Extract product name from video description

        Args:
            description: Video description text
            category: Product category for context

        Returns:
            Product name or None
        """
        # Remove hashtags and URLs
        clean_desc = re.sub(r'#\w+', '', description)
        clean_desc = re.sub(r'http\S+|www\.\S+', '', clean_desc)

        # Look for product indicators
        product_patterns = [
            r'(?:check out|get|buy|shop|found) (?:this |the |my )?([\w\s]+?)(?:!|\.|\n|$)',
            r'([\w\s]+?) (?:review|unboxing|haul)',
            r'(?:amazing|best|top) ([\w\s]+?)(?:!|\.|\n)',
        ]

        for pattern in product_patterns:
            match = re.search(pattern, clean_desc, re.IGNORECASE)
            if match:
                product_name = match.group(1).strip()

                # Ensure it's not too short or generic
                if len(product_name) > 5 and product_name.lower() not in ['this', 'these', 'that', 'it']:
                    return product_name.title()

        # Fallback: Use category + generic name
        return f"{category.title()} Product"

    def _estimate_price(self, product_name: str, category: str) -> float:
        """
        Estimate product price based on name and category

        Args:
            product_name: Name of the product
            category: Product category

        Returns:
            Estimated price in USD
        """

        # Normalize category
        category_key = category.lower().replace(" ", "_")

        # Get price range for category
        price_range = self.category_prices.get(category_key, self.category_prices["general"])

        # Adjust based on keywords in product name
        multiplier = 1.0
        product_lower = product_name.lower()

        if any(word in product_lower for word in ["premium", "pro", "professional", "smart"]):
            multiplier = 1.3
        elif any(word in product_lower for word in ["mini", "basic", "portable"]):
            multiplier = 0.8

        # Random price within range
        # TikTok video metadata does not contain price. This used to return
        # random.uniform(min, max) rounded to .99 as "psychological pricing" —
        # an invented number presented as a product price. Band midpoint,
        # explicitly an estimate.
        base_price = (price_range["min"] + price_range["max"]) / 2
        estimated_price = base_price * multiplier

        # Round to .99 for psychological pricing
        return round(estimated_price - 0.01, 2)

    def _calculate_viral_score(
        self,
        views: int,
        likes: int,
        comments: int,
        shares: int
    ) -> int:
        """
        Calculate viral score (0-100) based on engagement metrics

        Args:
            views: View count
            likes: Like count
            comments: Comment count
            shares: Share count

        Returns:
            Viral score (0-100)
        """
        if views == 0:
            return 0

        # Calculate engagement rate
        total_engagement = likes + (comments * 3) + (shares * 5)  # Weighted
        engagement_rate = (total_engagement / views) * 100

        # Normalize to 0-100 scale
        # Typical viral videos have 10-20% engagement rate
        viral_score = min(100, int(engagement_rate / 0.2))

        # Boost score for high view counts
        if views > 1000000:
            viral_score = min(100, viral_score + 10)
        elif views > 500000:
            viral_score = min(100, viral_score + 5)

        return viral_score

    def get_trending_hashtags(self, limit: int = 20) -> List[str]:
        """
        Get trending product hashtags on TikTok

        Args:
            limit: Number of hashtags to return

        Returns:
            List of trending hashtags
        """
        # This would use TikTok's trending hashtags API
        # For now, return common product hashtags

        trending = [
            "tiktokmademebuyit",
            "amazonfinds",
            "musthaves",
            "productreview",
            "gadgets",
            "smarthome",
            "fitnessproducts",
            "kitchengadgets",
            "beautyhacks",
            "techreview",
            "homeorganization",
            "tiktoktips",
            "producthaul",
            "unboxing",
            "founditonamazon",
            "viralproducts",
            "trending",
            "shopwithme",
            "producttesting",
            "lifehacks"
        ]

        return trending[:limit]
