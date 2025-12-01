"""
xAI Grok-powered Twitter/X Product Discovery

WHY xAI?
=========
Grok is the ONLY AI with real-time Twitter/X data access.
- Claude, GPT, Gemini = NO Twitter access
- Grok = Full Twitter access (Elon owns both xAI and X)

WHAT THIS GIVES YOU:
====================
1. Viral product detection (#TikTokMadeMeBuyIt, #AmazonFinds)
2. Real social sentiment from actual buyers
3. Product URLs shared on Twitter
4. Influencer product picks
5. Trending products BEFORE they hit mainstream

COST:
=====
~$5-10/month for moderate usage (much cheaper than Twitter API)
"""

import os
import json
import asyncio
from typing import List, Dict, Optional, Any
from datetime import datetime
from dataclasses import dataclass

try:
    from openai import AsyncOpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


@dataclass
class TwitterProduct:
    """Product discovered from Twitter/X"""
    name: str
    url: Optional[str]  # Product URL if shared
    image_url: Optional[str]
    price: Optional[float]
    
    # Twitter engagement metrics
    tweet_count: int  # How many tweets mention this
    total_likes: int
    total_retweets: int
    total_replies: int
    engagement_rate: float  # (likes + retweets + replies) / impressions
    
    # Sentiment
    sentiment: str  # positive, negative, neutral, mixed
    sentiment_score: float  # -1 to 1
    
    # Discovery metadata
    source_hashtags: List[str]
    sample_tweets: List[str]  # Example tweets mentioning this
    influencer_mentions: List[str]  # Notable accounts that mentioned
    
    # Calculated scores
    viral_score: float  # 0-100
    buy_signal: str  # BUY, CONSIDER, SKIP
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "url": self.url,
            "image_url": self.image_url,
            "price": self.price,
            "tweet_count": self.tweet_count,
            "total_likes": self.total_likes,
            "total_retweets": self.total_retweets,
            "total_replies": self.total_replies,
            "engagement_rate": self.engagement_rate,
            "sentiment": self.sentiment,
            "sentiment_score": self.sentiment_score,
            "source_hashtags": self.source_hashtags,
            "sample_tweets": self.sample_tweets[:3],
            "influencer_mentions": self.influencer_mentions,
            "viral_score": self.viral_score,
            "buy_signal": self.buy_signal,
            "source": "twitter_xai"
        }


class XAITwitterDiscovery:
    """
    Discover viral products using xAI Grok's Twitter access.
    
    This is a PRIMARY discovery source - finds actual products!
    
    Discovery Strategies:
    1. HASHTAG MINING - #TikTokMadeMeBuyIt, #AmazonFinds, #SmartHome
    2. VIRAL DETECTION - Products with sudden engagement spikes
    3. INFLUENCER TRACKING - What are tech influencers promoting?
    4. SENTIMENT ANALYSIS - Are people loving or hating a product?
    5. URL EXTRACTION - Get actual product links from tweets
    """
    
    # Viral product hashtags - GOLDMINE for e-commerce
    PRODUCT_HASHTAGS = {
        "viral_general": [
            "#TikTokMadeMeBuyIt",
            "#AmazonFinds",
            "#AmazonMustHaves",
            "#ViralProducts",
            "#TrendingProducts",
            "#MustHave",
            "#GameChanger",
        ],
        "smart_home": [
            "#SmartHome",
            "#HomeAutomation",
            "#SmartLighting",
            "#AlexaDevice",
            "#GoogleHome",
            "#SmartGadgets",
            "#TechHome",
        ],
        "home_goods": [
            "#HomeDecor",
            "#OrganizationHacks",
            "#CleaningHacks",
            "#KitchenGadgets",
            "#HomeFavorites",
            "#HomeHacks",
        ],
        "tech_gadgets": [
            "#TechGadgets",
            "#GadgetReview",
            "#TechFinds",
            "#CoolGadgets",
            "#TechDeals",
        ]
    }
    
    # Influencers to monitor (tech/home/lifestyle)
    INFLUENCERS = [
        "@MKBHD",
        "@iJustine",
        "@unaborrego",
        "@techreviewsHQ",
        "@smarthomeHQ",
    ]
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize xAI Twitter discovery."""
        self.api_key = api_key or os.getenv("XAI_API_KEY")
        self.client = None
        self._available = False
        
        if not HAS_OPENAI:
            print("⚠️  openai package not installed - run: pip install openai")
            return
            
        if not self.api_key:
            print("⚠️  XAI_API_KEY not configured")
            return
            
        # xAI uses OpenAI-compatible API
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url="https://api.x.ai/v1"
        )
        self._available = True
        print("✅ xAI Twitter Discovery initialized")
    
    def is_available(self) -> bool:
        """Check if xAI API is configured and available."""
        return self._available and self.client is not None
    
    async def discover_viral_products(
        self,
        niche: str = "smart_home",
        max_products: int = 10,
        time_range: str = "24h"
    ) -> List[TwitterProduct]:
        """
        Discover viral products from Twitter using Grok.
        
        Args:
            niche: Product niche (smart_home, home_goods, tech_gadgets)
            max_products: Maximum products to return
            time_range: Time range to search (1h, 24h, 7d)
            
        Returns:
            List of TwitterProduct with full engagement data
        """
        if not self.is_available():
            print("❌ xAI Twitter not available")
            return []
        
        print(f"\n🐦 xAI Twitter Discovery: {niche}")
        print(f"   Time range: {time_range}")
        print(f"   Max products: {max_products}")
        
        # Get relevant hashtags for this niche
        hashtags = self.PRODUCT_HASHTAGS.get(niche, [])
        hashtags += self.PRODUCT_HASHTAGS.get("viral_general", [])
        
        # Build the Grok prompt
        prompt = f"""You have access to real-time Twitter/X data. 

TASK: Find {max_products} viral products being discussed on Twitter in the last {time_range}.

SEARCH FOCUS:
- Niche: {niche}
- Hashtags to monitor: {', '.join(hashtags[:10])}
- Look for products with high engagement (likes, retweets, replies)
- Prioritize products with actual purchase links (Amazon, AliExpress, Shopify stores)

For each product found, provide:
1. Product name (specific, not generic)
2. Product URL if mentioned in tweets (Amazon, AliExpress, or store link)
3. Approximate price if mentioned
4. Number of tweets mentioning it
5. Total engagement (likes + retweets + replies estimate)
6. Sentiment (positive/negative/neutral/mixed)
7. Key hashtags where it appeared
8. 2-3 example tweet snippets (paraphrased)
9. Any influencer mentions

RESPOND IN THIS EXACT JSON FORMAT:
{{
    "products": [
        {{
            "name": "Product Name",
            "url": "https://amazon.com/... or null",
            "price": 29.99,
            "tweet_count": 150,
            "engagement": {{
                "likes": 5000,
                "retweets": 800,
                "replies": 200
            }},
            "sentiment": "positive",
            "sentiment_score": 0.85,
            "hashtags": ["#TikTokMadeMeBuyIt", "#SmartHome"],
            "sample_tweets": [
                "Just got this smart plug and it's amazing!",
                "Why didn't I buy this sooner??"
            ],
            "influencer_mentions": ["@techreviewsHQ"],
            "viral_reason": "Why this is going viral"
        }}
    ],
    "trending_hashtags": ["#hashtag1", "#hashtag2"],
    "market_insight": "Brief insight about current Twitter trends in this niche"
}}

Only include products that are ACTUALLY trending on Twitter right now."""

        try:
            response = await self.client.chat.completions.create(
                model="grok-2-latest",
                messages=[
                    {
                        "role": "system",
                        "content": "You are Grok, an AI with real-time access to Twitter/X data. You can see current tweets, engagement metrics, and trending topics. Provide accurate, real-time data about what's trending on Twitter."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=3000
            )
            
            content = response.choices[0].message.content
            products = self._parse_products_response(content, niche)
            
            print(f"   ✅ Found {len(products)} viral products on Twitter")
            return products[:max_products]
            
        except Exception as e:
            print(f"   ❌ xAI Twitter discovery failed: {e}")
            return []
    
    async def get_product_sentiment(
        self,
        product_name: str,
        include_tweets: bool = True
    ) -> Dict[str, Any]:
        """Get Twitter sentiment for a specific product."""
        if not self.is_available():
            return {"error": "xAI not available"}
        
        print(f"🐦 Analyzing Twitter sentiment: {product_name}")
        
        prompt = f"""Analyze Twitter/X sentiment for this product: "{product_name}"

Search recent tweets mentioning this product and provide:
1. Overall sentiment (positive/negative/neutral/mixed)
2. Sentiment score (-1.0 to 1.0)
3. Total tweet count (approximate)
4. Engagement metrics (likes, retweets, replies)
5. Common praise (what people love)
6. Common complaints (what people hate)
7. Purchase intent signals

RESPOND IN JSON FORMAT:
{{
    "product": "{product_name}",
    "sentiment": "positive",
    "sentiment_score": 0.75,
    "tweet_count": 500,
    "engagement": {{
        "total_likes": 15000,
        "total_retweets": 2000,
        "total_replies": 800
    }},
    "common_praise": ["fast shipping", "great quality"],
    "common_complaints": ["battery life could be better"],
    "purchase_intent": {{
        "bought_it": 45,
        "want_to_buy": 120,
        "recommending": 85
    }},
    "recommendation": "BUY/SKIP/CONSIDER with reason"
}}"""

        try:
            response = await self.client.chat.completions.create(
                model="grok-2-latest",
                messages=[
                    {"role": "system", "content": "You are Grok with real-time Twitter access."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1500
            )
            
            content = response.choices[0].message.content
            
            import re
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                return json.loads(json_match.group())
            
            return {"product": product_name, "raw_analysis": content}
            
        except Exception as e:
            return {"error": str(e)}
    
    async def find_trending_hashtags(self, niche: str = "smart_home") -> List[Dict]:
        """Find currently trending hashtags related to a niche."""
        if not self.is_available():
            return []
        
        prompt = f"""Find the top 15 trending Twitter/X hashtags related to: {niche}

Focus on product-related and e-commerce hashtags.

RESPOND IN JSON:
{{
    "hashtags": [
        {{
            "tag": "#SmartHome",
            "volume": "5000/hour",
            "trend": "rising",
            "sample_products": ["Ring Doorbell", "Philips Hue"]
        }}
    ]
}}"""

        try:
            response = await self.client.chat.completions.create(
                model="grok-2-latest",
                messages=[
                    {"role": "system", "content": "You are Grok with real-time Twitter trend access."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1500
            )
            
            import re
            json_match = re.search(r'\{[\s\S]*\}', response.choices[0].message.content)
            if json_match:
                return json.loads(json_match.group()).get("hashtags", [])
            return []
            
        except Exception as e:
            print(f"   ❌ Trending hashtags failed: {e}")
            return []
    
    async def monitor_influencers(
        self,
        influencer_handles: Optional[List[str]] = None,
        niche: str = "tech"
    ) -> List[Dict[str, Any]]:
        """Monitor what products influencers are talking about."""
        if not self.is_available():
            return []
        
        handles = influencer_handles or self.INFLUENCERS
        
        prompt = f"""Check recent tweets from these influencers for product mentions:
{', '.join(handles)}

Find products they've mentioned, reviewed, or promoted in the last 7 days.

RESPOND IN JSON:
{{
    "influencer_picks": [
        {{
            "product": "Product Name",
            "influencer": "@handle",
            "tweet_summary": "What they said",
            "sentiment": "positive",
            "engagement": {{"likes": 5000, "retweets": 500}},
            "url": "product_url or null"
        }}
    ]
}}"""

        try:
            response = await self.client.chat.completions.create(
                model="grok-2-latest",
                messages=[
                    {"role": "system", "content": "You are Grok with access to Twitter user timelines."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            import re
            json_match = re.search(r'\{[\s\S]*\}', response.choices[0].message.content)
            if json_match:
                return json.loads(json_match.group()).get("influencer_picks", [])
            return []
            
        except Exception as e:
            print(f"   ❌ Influencer monitoring failed: {e}")
            return []
    
    def _parse_products_response(self, content: str, niche: str) -> List[TwitterProduct]:
        """Parse Grok's response into TwitterProduct objects."""
        products = []
        
        try:
            import re
            json_match = re.search(r'\{[\s\S]*\}', content)
            if not json_match:
                return []
            
            data = json.loads(json_match.group())
            
            for p in data.get("products", []):
                engagement = p.get("engagement", {})
                likes = engagement.get("likes", 0)
                retweets = engagement.get("retweets", 0)
                replies = engagement.get("replies", 0)
                tweet_count = p.get("tweet_count", 1)
                
                # Calculate viral score
                viral_score = self._calculate_viral_score(
                    tweet_count, likes, retweets, p.get("sentiment_score", 0)
                )
                
                product = TwitterProduct(
                    name=p.get("name", "Unknown"),
                    url=p.get("url"),
                    image_url=None,
                    price=p.get("price"),
                    tweet_count=tweet_count,
                    total_likes=likes,
                    total_retweets=retweets,
                    total_replies=replies,
                    engagement_rate=(likes + retweets + replies) / max(tweet_count * 100, 1),
                    sentiment=p.get("sentiment", "neutral"),
                    sentiment_score=p.get("sentiment_score", 0),
                    source_hashtags=p.get("hashtags", []),
                    sample_tweets=p.get("sample_tweets", []),
                    influencer_mentions=p.get("influencer_mentions", []),
                    viral_score=viral_score,
                    buy_signal=self._get_buy_signal(viral_score, p.get("sentiment_score", 0))
                )
                products.append(product)
                
        except Exception as e:
            print(f"   ⚠️  Failed to parse products: {e}")
        
        return products
    
    def _calculate_viral_score(self, tweet_count: int, likes: int, retweets: int, sentiment_score: float) -> float:
        """Calculate viral potential score (0-100)."""
        tweet_score = min(tweet_count / 1000, 1.0) * 25
        engagement_score = min((likes + retweets) / 50000, 1.0) * 40
        sentiment_component = ((sentiment_score + 1) / 2) * 20
        retweet_ratio = min(retweets / max(likes, 1), 0.5) * 2 * 15 if likes > 0 else 0
        
        return round(min(100, tweet_score + engagement_score + sentiment_component + retweet_ratio), 1)
    
    def _get_buy_signal(self, viral_score: float, sentiment_score: float) -> str:
        """Determine buy/skip signal."""
        if viral_score >= 75 and sentiment_score >= 0.5:
            return "🔥 STRONG BUY - Viral + Positive"
        elif viral_score >= 60 and sentiment_score >= 0.3:
            return "✅ BUY - Good viral potential"
        elif viral_score >= 40 and sentiment_score >= 0:
            return "⚠️ CONSIDER - Moderate interest"
        elif sentiment_score < 0:
            return "❌ SKIP - Negative sentiment"
        else:
            return "⏸️ WATCH - Low viral score"


# Convenience function
async def discover_twitter_products(niche: str = "smart_home", max_products: int = 10) -> List[Dict]:
    """Quick function to discover viral products on Twitter."""
    discovery = XAITwitterDiscovery()
    if not discovery.is_available():
        return []
    
    products = await discovery.discover_viral_products(niche, max_products)
    return [p.to_dict() for p in products]


async def test_xai_twitter():
    """Test xAI Twitter discovery."""
    print("\n" + "="*70)
    print("🧪 TESTING xAI TWITTER DISCOVERY")
    print("="*70 + "\n")
    
    discovery = XAITwitterDiscovery()
    
    if not discovery.is_available():
        print("❌ xAI not configured. Set XAI_API_KEY in .env")
        return
    
    products = await discovery.discover_viral_products(
        niche="smart_home",
        max_products=5,
        time_range="24h"
    )
    
    for p in products:
        print(f"\n🔥 {p.name}")
        print(f"   Viral Score: {p.viral_score}/100")
        print(f"   Signal: {p.buy_signal}")
        print(f"   Tweets: {p.tweet_count} | Likes: {p.total_likes}")
        if p.url:
            print(f"   URL: {p.url}")
    
    print("\n✅ Test complete!")


if __name__ == "__main__":
    asyncio.run(test_xai_twitter())
