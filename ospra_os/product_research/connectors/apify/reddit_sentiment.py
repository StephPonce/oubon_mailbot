"""
Reddit Sentiment Scraper using Apify

Analyzes product mentions and sentiment on Reddit to identify
trending products with strong community buzz.
"""
from typing import List, Dict, Optional
import logging
from .base_apify import ApifyConnector

logger = logging.getLogger(__name__)


class RedditSentimentScraper(ApifyConnector):
    """Scrape Reddit for product sentiment and trending discussions"""

    # Apify actor for Reddit scraping
    REDDIT_SCRAPER_ACTOR = "trudax/reddit-scraper"

    async def scrape_product_mentions(
        self,
        product_keywords: List[str],
        subreddits: Optional[List[str]] = None,
        max_posts: int = 100,
        time_filter: str = "week"
    ) -> List[Dict]:
        """
        Scrape Reddit for product mentions and sentiment

        Args:
            product_keywords: Keywords to search for
            subreddits: List of subreddits to search (None = all)
            max_posts: Maximum number of posts to scrape
            time_filter: Time filter (hour, day, week, month, year, all)

        Returns:
            List of product sentiment dictionaries
        """
        if not self.is_available():
            logger.warning("Reddit scraper not available - Apify not configured")
            return []

        logger.info(f"🔍 Scraping Reddit for: {', '.join(product_keywords)}")

        # Default to popular product discussion subreddits
        if subreddits is None:
            subreddits = [
                "BuyItForLife",
                "ProductPorn",
                "shutupandtakemymoney",
                "amazondealsus",
                "deals",
                "gadgets",
                "homeimprovement",
                "smarthome"
            ]

        run_input = {
            "startUrls": [
                f"https://www.reddit.com/search/?q={' OR '.join(product_keywords)}"
            ],
            "maxItems": max_posts,
            "maxComments": 50
        }

        try:
            items = await self.run_actor(
                actor_id=self.REDDIT_SCRAPER_ACTOR,
                run_input=run_input,
                timeout_secs=300
            )

            # Parse sentiment from posts and comments
            sentiment_data = []
            for item in items:
                try:
                    parsed = self._parse_reddit_post(item, product_keywords)
                    if parsed:
                        sentiment_data.append(parsed)
                except Exception as e:
                    logger.error(f"Error parsing Reddit post: {e}")
                    continue

            logger.info(f"✅ Analyzed {len(sentiment_data)} Reddit discussions")
            return sentiment_data

        except Exception as e:
            logger.error(f"❌ Reddit scraping failed: {e}")
            return []

    async def scrape_trending_products(
        self,
        subreddit: str = "shutupandtakemymoney",
        max_posts: int = 50
    ) -> List[Dict]:
        """
        Scrape trending products from specific subreddit

        Args:
            subreddit: Subreddit to scrape
            max_posts: Maximum number of posts

        Returns:
            List of trending product dictionaries
        """
        if not self.is_available():
            logger.warning("Reddit scraper not available")
            return []

        logger.info(f"📈 Scraping trending products from r/{subreddit}")

        run_input = {
            "subreddits": [subreddit],
            "maxPosts": max_posts,
            "sort": "hot",  # Hot posts = trending now
            "includeComments": True,
            "maxComments": 20
        }

        try:
            items = await self.run_actor(
                actor_id=self.REDDIT_SCRAPER_ACTOR,
                run_input=run_input,
                timeout_secs=240
            )

            products = []
            for item in items:
                product = self._extract_product_from_post(item)
                if product:
                    products.append(product)

            logger.info(f"✅ Found {len(products)} trending products")
            return products

        except Exception as e:
            logger.error(f"❌ Reddit trending scraping failed: {e}")
            return []

    def _parse_reddit_post(
        self,
        post: Dict,
        keywords: List[str]
    ) -> Optional[Dict]:
        """
        Parse Reddit post for product sentiment

        Args:
            post: Raw post data from scraper
            keywords: Product keywords to analyze

        Returns:
            Sentiment data dict or None
        """
        try:
            # Calculate sentiment score from upvotes/downvotes
            upvotes = post.get('upVotes', post.get('score', 0))
            comments_count = post.get('commentsCount', post.get('numComments', 0))

            # Sentiment score: upvotes + (comments * 2) = engagement
            engagement_score = upvotes + (comments_count * 2)

            # Determine sentiment from title and body
            title = post.get('title', '').lower()
            body = post.get('body', post.get('selfText', '')).lower()
            full_text = f"{title} {body}"

            # Simple sentiment analysis
            positive_words = ['amazing', 'love', 'great', 'best', 'recommend', 'worth', 'perfect', 'awesome']
            negative_words = ['bad', 'terrible', 'hate', 'worst', 'avoid', 'waste', 'regret', 'broke']

            positive_count = sum(1 for word in positive_words if word in full_text)
            negative_count = sum(1 for word in negative_words if word in full_text)

            sentiment = "positive" if positive_count > negative_count else "neutral" if positive_count == negative_count else "negative"

            # Match to product keywords
            matched_keywords = [kw for kw in keywords if kw.lower() in full_text]

            return {
                'product_keywords': matched_keywords,
                'subreddit': post.get('subreddit', 'unknown'),
                'title': post.get('title', ''),
                'url': post.get('url', ''),
                'upvotes': upvotes,
                'comments_count': comments_count,
                'engagement_score': engagement_score,
                'sentiment': sentiment,
                'sentiment_score': positive_count - negative_count,
                'created_utc': post.get('createdAt', post.get('createdUtc', 0)),
                'author': post.get('author', 'unknown'),
                'source': 'reddit'
            }

        except Exception as e:
            logger.error(f"Error parsing Reddit sentiment: {e}")
            return None

    def _extract_product_from_post(self, post: Dict) -> Optional[Dict]:
        """
        Extract product information from Reddit post

        Args:
            post: Raw post data

        Returns:
            Product dict or None
        """
        try:
            title = post.get('title', '')
            url = post.get('url', '')
            upvotes = post.get('upVotes', post.get('score', 0))

            # Check if post has product link (Amazon, AliExpress, etc.)
            has_amazon_link = 'amazon.com' in url.lower() or 'amzn.to' in url.lower()
            has_ali_link = 'aliexpress.com' in url.lower()

            if not (has_amazon_link or has_ali_link):
                return None

            product = {
                'name': title,
                'source_url': url,
                'reddit_upvotes': upvotes,
                'reddit_comments': post.get('commentsCount', post.get('numComments', 0)),
                'subreddit': post.get('subreddit', 'unknown'),
                'reddit_post_url': post.get('postUrl', post.get('permalink', '')),
                'source': 'reddit_trending',
                'created_at': post.get('createdAt', post.get('createdUtc', 0))
            }

            return product

        except Exception as e:
            logger.error(f"Error extracting product from Reddit post: {e}")
            return None

    def calculate_sentiment_metrics(
        self,
        sentiment_data: List[Dict]
    ) -> Dict:
        """
        Calculate aggregate sentiment metrics

        Args:
            sentiment_data: List of sentiment dicts

        Returns:
            Aggregate metrics
        """
        if not sentiment_data:
            return {
                'total_mentions': 0,
                'avg_sentiment_score': 0,
                'positive_ratio': 0,
                'total_engagement': 0
            }

        total_mentions = len(sentiment_data)
        avg_sentiment = sum(d['sentiment_score'] for d in sentiment_data) / total_mentions
        positive_count = sum(1 for d in sentiment_data if d['sentiment'] == 'positive')
        total_engagement = sum(d['engagement_score'] for d in sentiment_data)

        return {
            'total_mentions': total_mentions,
            'avg_sentiment_score': round(avg_sentiment, 2),
            'positive_ratio': round(positive_count / total_mentions, 2),
            'total_engagement': total_engagement,
            'sentiment_strength': 'strong' if abs(avg_sentiment) > 2 else 'moderate' if abs(avg_sentiment) > 1 else 'weak'
        }
