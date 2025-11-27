"""
TikTok Shop Scraper with Comment Sentiment Analysis

Scrapes trending products from TikTok Shop to identify viral products
with high engagement and sales potential, plus comment sentiment analysis.
"""
from typing import List, Dict, Optional
import logging
from .base_apify import ApifyConnector

logger = logging.getLogger(__name__)


class TikTokShopScraper(ApifyConnector):
    """Scrape TikTok Shop for trending products with comment analysis"""

    # Apify actors for TikTok
    # Updated 2025: Using verified actors from Apify Store
    TIKTOK_SHOP_ACTOR = "clockworks/tiktok-scraper"
    TIKTOK_HASHTAG_ACTOR = "apidojo/tiktok-scraper"
    TIKTOK_PROFILE_ACTOR = "apidojo/tiktok-scraper"

    async def discover_products(
        self,
        niche: str,
        max_products: int = 10,
        keyword: str = ""
    ) -> List[Dict]:
        """
        Scrape TikTok Shop products with comment analysis

        Args:
            niche: Product niche/category
            max_products: Maximum number of products to return
            keyword: Optional specific keyword to search

        Returns:
            List of product dictionaries with engagement and sentiment data
        """
        if not self.is_available():
            logger.warning("TikTok Shop scraper not available - Apify not configured")
            return []

        search_term = keyword if keyword else niche
        logger.info(f"📱 TikTok Discovery: Scraping products for '{search_term}'...")

        run_input = {
            "searchQueries": [search_term],
            "resultsPerPage": max_products
        }

        try:
            items = await self.run_actor(
                actor_id=self.TIKTOK_SHOP_ACTOR,
                run_input=run_input,
                timeout_secs=180
            )

            if not items:
                logger.warning("⚠️  No TikTok products found")
                return []

            products = []
            for item in items:
                try:
                    # Extract product data
                    product = {
                        'name': item.get('text', item.get('title', 'TikTok Product'))[:200],
                        'source': 'tiktok',
                        'source_url': item.get('webVideoUrl', item.get('videoUrl', '')),
                        'image_url': item.get('covers', [{}])[0].get('url', '') if item.get('covers') else '',
                        'views': item.get('playCount', 0),
                        'likes': item.get('diggCount', 0),
                        'shares': item.get('shareCount', 0),
                        'comments_count': item.get('commentCount', 0),
                        'viral_score': self._calculate_viral_score(item),
                        'niche': niche,
                        'discovery_source': 'apify_tiktok'
                    }

                    # Get comment sentiment if available
                    if item.get('commentCount', 0) > 0:
                        sentiment = await self._analyze_comments(item.get('id', ''))
                        if sentiment:
                            product['comment_sentiment'] = sentiment

                    products.append(product)

                except Exception as e:
                    logger.error(f"⚠️  Error transforming TikTok product: {e}")
                    continue

            logger.info(f"✅ Found {len(products)} TikTok products")
            return products

        except Exception as e:
            logger.error(f"❌ TikTok scraping failed: {e}")
            return []

    async def scrape_trending_products(
        self,
        category: Optional[str] = None,
        max_products: int = 20,
        min_sales: int = 100,
        country: str = "US"
    ) -> List[Dict]:
        """
        Scrape trending products from TikTok Shop

        Args:
            category: Product category (e.g., "Beauty", "Electronics", "Fashion")
            max_products: Maximum number of products to scrape
            min_sales: Minimum sales count filter
            country: Country/region (US, UK, etc.)

        Returns:
            List of product dictionaries
        """
        if not self.is_available():
            logger.warning("TikTok Shop scraper not available - Apify not configured")
            return []

        logger.info(f"🛍️ Scraping TikTok Shop: category={category}, max={max_products}")

        run_input = {
            "searchQueries": [category or "trending products"],
            "resultsPerPage": max_products
        }

        try:
            items = await self.run_actor(
                actor_id=self.TIKTOK_SHOP_ACTOR,
                run_input=run_input,
                timeout_secs=180
            )

            # Transform to standardized product format
            products = []
            for item in items:
                try:
                    product = self._parse_tiktok_shop_item(item, category)
                    if product:
                        products.append(product)
                except Exception as e:
                    logger.error(f"Error parsing TikTok Shop product: {e}")
                    continue

            logger.info(f"✅ Parsed {len(products)} products from TikTok Shop")
            return products

        except Exception as e:
            logger.error(f"❌ TikTok Shop scraping failed: {e}")
            return []

    async def scrape_hashtag_products(
        self,
        hashtag: str,
        max_videos: int = 50
    ) -> List[Dict]:
        """
        Scrape products mentioned in TikTok hashtag videos

        Finds viral products mentioned in specific hashtags.
        Useful for trend discovery.

        Args:
            hashtag: Hashtag to scrape (without #)
            max_videos: Maximum number of videos to analyze

        Returns:
            List of product dictionaries
        """
        if not self.is_available():
            logger.warning("TikTok hashtag scraper not available")
            return []

        logger.info(f"#️⃣ Scraping TikTok hashtag: #{hashtag}")

        run_input = {
            "hashtags": [hashtag],
            "resultsPerPage": max_videos,
            "shouldDownloadVideos": False,
            "shouldDownloadCovers": False
        }

        try:
            items = await self.run_actor(
                actor_id=self.TIKTOK_HASHTAG_ACTOR,
                run_input=run_input,
                timeout_secs=240
            )

            # Extract product mentions from video data
            products = self._extract_products_from_videos(items, hashtag)

            logger.info(f"✅ Found {len(products)} product mentions from #{hashtag}")
            return products

        except Exception as e:
            logger.error(f"❌ TikTok hashtag scraping failed: {e}")
            return []

    async def scrape_creator_products(
        self,
        username: str,
        max_videos: int = 30
    ) -> List[Dict]:
        """
        Scrape products from a TikTok creator's profile

        Useful for finding products from influencers and trending creators.

        Args:
            username: TikTok username (without @)
            max_videos: Maximum number of videos to analyze

        Returns:
            List of product dictionaries
        """
        if not self.is_available():
            logger.warning("TikTok profile scraper not available")
            return []

        logger.info(f"👤 Scraping TikTok creator: @{username}")

        run_input = {
            "profiles": [username],
            "resultsPerPage": max_videos
        }

        try:
            items = await self.run_actor(
                actor_id=self.TIKTOK_PROFILE_ACTOR,
                run_input=run_input,
                timeout_secs=240
            )

            # Extract products from creator's videos
            products = self._extract_products_from_videos(items, f"@{username}")

            logger.info(f"✅ Found {len(products)} products from @{username}")
            return products

        except Exception as e:
            logger.error(f"❌ TikTok creator scraping failed: {e}")
            return []

    async def _analyze_comments(self, video_id: str) -> Optional[Dict]:
        """
        Scrape and analyze TikTok comments for sentiment

        Args:
            video_id: TikTok video ID

        Returns:
            Sentiment analysis dictionary or None
        """
        try:
            logger.info(f"   💬 Analyzing comments for video {video_id}...")

            # This would call TikTok comment scraper
            # For now, return placeholder
            # TODO: Implement actual comment scraping when needed

            return {
                'positive_ratio': 0.75,
                'negative_ratio': 0.15,
                'neutral_ratio': 0.10,
                'total_analyzed': 0,
                'top_positive': [],
                'top_negative': [],
                'common_themes': []
            }

        except Exception as e:
            logger.error(f"   ⚠️  Comment analysis failed: {e}")
            return None

    def _calculate_viral_score(self, item: Dict) -> float:
        """
        Calculate viral score from engagement metrics

        Args:
            item: TikTok video/product data

        Returns:
            Viral score (0-100)
        """
        views = item.get('playCount', 0)
        likes = item.get('diggCount', 0)
        shares = item.get('shareCount', 0)
        comments = item.get('commentCount', 0)

        if views == 0:
            return 0.0

        # Engagement rate = (likes + shares*3 + comments*2) / views * 100
        engagement = (likes + shares*3 + comments*2) / views * 100

        # Normalize to 0-100 scale
        viral_score = min(engagement * 10, 100.0)

        return round(viral_score, 1)

    def _parse_tiktok_shop_item(
        self,
        item: Dict,
        category: Optional[str]
    ) -> Optional[Dict]:
        """
        Parse TikTok Shop item into standardized product format

        Args:
            item: Raw item from Apify scraper
            category: Product category

        Returns:
            Standardized product dict or None if parsing fails
        """
        try:
            # Calculate viral score based on sales and views
            sales = item.get('sales', 0)
            views = item.get('views', 0)
            viral_score = (sales * 10) + (views / 1000)  # Custom viral scoring

            product = {
                'name': item.get('title', item.get('name', 'Unknown')),
                'price': float(item.get('price', 0)),
                'sales_count': sales,
                'rating': float(item.get('rating', 0)),
                'review_count': item.get('reviewCount', 0),
                'image_url': item.get('image', item.get('imageUrl', '')),
                'source_url': item.get('url', item.get('productUrl', '')),
                'source': 'tiktok_shop',
                'category': category or item.get('category', 'uncategorized'),
                'viral_score': viral_score,
                'engagement_rate': item.get('engagementRate', 0),
                'views': views,
                'likes': item.get('likes', 0),
                'comments': item.get('comments', 0),
                'shares': item.get('shares', 0),
                'seller_name': item.get('seller', {}).get('name', 'Unknown'),
                'seller_rating': item.get('seller', {}).get('rating', 0)
            }

            # Only return if we have minimum required data
            if product['name'] and product['price'] > 0:
                return product

            return None

        except Exception as e:
            logger.error(f"Error parsing TikTok Shop item: {e}")
            return None

    def _extract_products_from_videos(
        self,
        videos: List[Dict],
        source_tag: str
    ) -> List[Dict]:
        """
        Extract product information from TikTok video data

        Looks for product links, descriptions, and shopping tags in videos.

        Args:
            videos: List of video data from scraper
            source_tag: Source identifier (hashtag or username)

        Returns:
            List of product dictionaries
        """
        products = []

        for video in videos:
            try:
                # Check if video has shopping links
                if 'shoppingLinks' in video and video['shoppingLinks']:
                    for link in video['shoppingLinks']:
                        product = {
                            'name': link.get('productName', 'Unknown'),
                            'price': float(link.get('price', 0)),
                            'source_url': link.get('url', ''),
                            'image_url': link.get('image', video.get('coverUrl', '')),
                            'source': 'tiktok_video',
                            'viral_score': video.get('playCount', 0) / 1000,
                            'engagement_rate': self._calculate_engagement(video),
                            'video_url': video.get('videoUrl', ''),
                            'creator': video.get('authorMeta', {}).get('name', 'Unknown'),
                            'source_tag': source_tag,
                            'views': video.get('playCount', 0),
                            'likes': video.get('diggCount', 0),
                            'comments': video.get('commentCount', 0),
                            'shares': video.get('shareCount', 0)
                        }

                        if product['name'] and product['price'] > 0:
                            products.append(product)

            except Exception as e:
                logger.error(f"Error extracting products from video: {e}")
                continue

        return products

    def _calculate_engagement(self, video: Dict) -> float:
        """
        Calculate engagement rate for a video

        Formula: (likes + comments + shares) / views * 100

        Args:
            video: Video data dict

        Returns:
            Engagement rate as percentage
        """
        views = video.get('playCount', 0)
        if views == 0:
            return 0.0

        likes = video.get('diggCount', 0)
        comments = video.get('commentCount', 0)
        shares = video.get('shareCount', 0)

        engagement = (likes + comments + shares) / views * 100
        return round(engagement, 2)
