"""
Unified Product Discovery Engine v2
====================================
APIFY-FIRST Architecture (AliExpress OAuth is currently broken)

Data Flow:
1. Apify TikTok Shop → Viral products with engagement metrics
2. Apify Amazon Bestsellers → Proven demand products
3. Google Trends → Validate search momentum
4. AliExpress Affiliate API → FALLBACK (when OAuth fixed)

Why Apify-First:
- ✅ TikTok Shop = viral products with REAL engagement data
- ✅ Amazon Bestsellers = PROVEN demand (sales rank)
- ✅ No OAuth required - just API token
- ✅ Rich engagement metrics (views, likes, shares)
- ✅ Multiple data sources for validation
"""

import asyncio
import logging
from typing import List, Dict, Optional
from datetime import datetime
import os

logger = logging.getLogger(__name__)


class UnifiedProductDiscoveryV2:
    """
    Apify-First Product Discovery Engine

    PRIMARY: Apify (TikTok Shop + Amazon Bestsellers)
    SECONDARY: Google Trends (validation)
    FALLBACK: AliExpress Affiliate API (when OAuth works)
    """

    # Niche-to-search-term mapping
    NICHE_SEARCH_TERMS = {
        "smart_home": [
            "smart home gadgets",
            "LED lights room",
            "smart plug wifi",
            "home automation",
            "smart doorbell"
        ],
        "fitness": [
            "home gym equipment",
            "fitness gadgets",
            "workout accessories",
            "resistance bands",
            "yoga accessories"
        ],
        "kitchen": [
            "kitchen gadgets",
            "cooking accessories",
            "food storage",
            "kitchen organizer",
            "cooking tools"
        ],
        "beauty": [
            "beauty tools",
            "skincare devices",
            "makeup accessories",
            "hair styling",
            "beauty gadgets"
        ],
        "pet": [
            "pet accessories",
            "dog toys",
            "cat products",
            "pet grooming",
            "pet tech"
        ],
        "tech": [
            "tech gadgets",
            "phone accessories",
            "wireless earbuds",
            "charging accessories",
            "tech accessories"
        ]
    }

    # Amazon category mapping
    AMAZON_CATEGORIES = {
        "smart_home": "Smart-Home",
        "fitness": "Sports-Outdoors",
        "kitchen": "Kitchen-Dining",
        "beauty": "Beauty-Personal-Care",
        "pet": "Pet-Supplies",
        "tech": "Electronics"
    }

    def __init__(self):
        """Initialize discovery engine with all available sources"""
        self.apify_available = False
        self.aliexpress_available = False
        self.trends_available = False

        # Check Apify
        self.apify_token = os.getenv('APIFY_API_TOKEN') or os.getenv('OUBONSHOP_APIFY_API_TOKEN')
        if self.apify_token:
            try:
                from ospra_os.product_research.connectors.apify import (
                    TikTokShopScraper,
                    AmazonBestsellersScraper
                )
                self.tiktok_scraper = TikTokShopScraper()
                self.amazon_scraper = AmazonBestsellersScraper()
                self.apify_available = True
                logger.info("✅ Apify scrapers loaded (PRIMARY SOURCE)")
            except Exception as e:
                logger.warning(f"⚠️  Apify import failed: {e}")

        # Check AliExpress (FALLBACK)
        try:
            from ospra_os.integrations.aliexpress.client import AliExpressClient
            self.aliexpress = AliExpressClient(use_affiliate=True)
            self.aliexpress_available = True
            logger.info("✅ AliExpress client loaded (FALLBACK)")
        except Exception as e:
            logger.warning(f"⚠️  AliExpress not available: {e}")

        # Initialize Google Trends
        try:
            from pytrends.request import TrendReq
            self.trends = TrendReq(hl='en-US', tz=360)
            self.trends_available = True
            logger.info("✅ Google Trends loaded (VALIDATION)")
        except Exception as e:
            logger.warning(f"⚠️  Google Trends not available: {e}")

    async def discover_products(
        self,
        niche: str = "smart_home",
        max_products: int = 20,
        min_score: float = 40.0
    ) -> List[Dict]:
        """
        Discover trending products using Apify-first approach

        Args:
            niche: Product niche (smart_home, fitness, kitchen, etc.)
            max_products: Maximum products to return
            min_score: Minimum score threshold

        Returns:
            List of products with scores and metadata
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"🔍 UNIFIED DISCOVERY: niche={niche}, max={max_products}")
        logger.info(f"{'='*60}")

        all_products = []

        # STEP 1: Try Apify sources (PRIMARY)
        if self.apify_available:
            logger.info("\n📱 STEP 1: Apify Sources (PRIMARY)")

            # 1a. TikTok Shop - Viral products
            tiktok_products = await self._fetch_tiktok_products(niche, max_products // 2)
            all_products.extend(tiktok_products)
            logger.info(f"   TikTok Shop: {len(tiktok_products)} products")

            # 1b. Amazon Bestsellers - Proven demand
            amazon_products = await self._fetch_amazon_products(niche, max_products // 2)
            all_products.extend(amazon_products)
            logger.info(f"   Amazon Bestsellers: {len(amazon_products)} products")

        # STEP 2: Fallback to AliExpress if needed
        if len(all_products) < max_products and self.aliexpress_available:
            logger.info("\n🛒 STEP 2: AliExpress Fallback")
            needed = max_products - len(all_products)
            aliexpress_products = await self._fetch_aliexpress_products(niche, needed)
            all_products.extend(aliexpress_products)
            logger.info(f"   AliExpress: {len(aliexpress_products)} products")

        # STEP 3: Generate mock data if still empty (development/testing)
        if len(all_products) == 0:
            logger.warning("\n⚠️  No products from APIs - generating mock data")
            all_products = self._generate_mock_products(niche, max_products)

        # STEP 4: Validate with Google Trends
        if self.trends_available and len(all_products) > 0:
            logger.info("\n📈 STEP 3: Google Trends Validation")
            all_products = await self._validate_with_trends(all_products, niche)

        # STEP 5: Score and rank
        logger.info("\n🎯 STEP 4: Scoring & Ranking")
        scored_products = self._calculate_final_scores(all_products)

        # Filter by minimum score and limit
        filtered = [p for p in scored_products if p.get('final_score', 0) >= min_score]
        ranked = sorted(filtered, key=lambda x: x.get('final_score', 0), reverse=True)
        final_products = ranked[:max_products]

        logger.info(f"\n✅ Discovery complete!")
        logger.info(f"   Total found: {len(all_products)}")
        logger.info(f"   After filtering: {len(filtered)}")
        logger.info(f"   Final selection: {len(final_products)}")

        return final_products

    async def _fetch_tiktok_products(self, niche: str, count: int) -> List[Dict]:
        """Fetch products from TikTok Shop via Apify"""
        products = []

        try:
            search_terms = self.NICHE_SEARCH_TERMS.get(niche, ["trending products"])

            for term in search_terms[:2]:  # Limit to 2 searches for speed
                results = await self.tiktok_scraper.discover_products(
                    niche=niche,
                    max_products=count // 2,
                    keyword=term
                )

                for item in results:
                    product = {
                        "product_id": f"tiktok_{hash(item.get('name', '')) % 10000000}",
                        "title": item.get('name', 'TikTok Product'),
                        "price": item.get('price', 0) or 19.99,  # Default price
                        "original_price": item.get('original_price', 0) or 29.99,
                        "main_image": item.get('image_url', ''),
                        "source_url": item.get('source_url', ''),
                        "source": "tiktok_shop",
                        "niche": niche,

                        # TikTok engagement metrics
                        "views": item.get('views', 0),
                        "likes": item.get('likes', 0),
                        "shares": item.get('shares', 0),
                        "comments_count": item.get('comments_count', 0),
                        "viral_score": item.get('viral_score', 0),

                        # Data sources metadata
                        "data_sources": {
                            "tiktok": {
                                "available": True,
                                "views": item.get('views', 0),
                                "viral_score": item.get('viral_score', 0),
                                "url": item.get('source_url', '')
                            }
                        },

                        "discovered_at": datetime.now().isoformat()
                    }
                    products.append(product)

        except Exception as e:
            logger.error(f"TikTok fetch error: {e}")

        return products[:count]

    async def _fetch_amazon_products(self, niche: str, count: int) -> List[Dict]:
        """Fetch bestsellers from Amazon via Apify"""
        products = []

        try:
            category = self.AMAZON_CATEGORIES.get(niche, "Electronics")

            results = await self.amazon_scraper.scrape_bestsellers(
                category=category,
                max_products=count
            )

            for item in results:
                product = {
                    "product_id": f"amazon_{item.get('asin', hash(item.get('name', '')) % 10000000)}",
                    "title": item.get('name', 'Amazon Product'),
                    "price": item.get('price', 0),
                    "original_price": item.get('price', 0) * 1.2,  # Estimated
                    "main_image": item.get('image_url', ''),
                    "source_url": item.get('source_url', ''),
                    "source": "amazon_bestsellers",
                    "niche": niche,

                    # Amazon metrics
                    "rating": item.get('rating', 0),
                    "reviews_count": item.get('reviews_count', 0),
                    "bestseller_rank": item.get('bestseller_rank', 9999),
                    "demand_score": item.get('demand_score', 0),
                    "is_bestseller": item.get('is_bestseller', False),

                    # Data sources metadata
                    "data_sources": {
                        "amazon": {
                            "available": True,
                            "bestseller_rank": item.get('bestseller_rank', 0),
                            "reviews": item.get('reviews_count', 0),
                            "url": item.get('source_url', '')
                        }
                    },

                    "discovered_at": datetime.now().isoformat()
                }
                products.append(product)

        except Exception as e:
            logger.error(f"Amazon fetch error: {e}")

        return products[:count]

    async def _fetch_aliexpress_products(self, niche: str, count: int) -> List[Dict]:
        """Fetch products from AliExpress (fallback)"""
        products = []

        try:
            search_terms = self.NICHE_SEARCH_TERMS.get(niche, ["trending"])

            for term in search_terms[:2]:
                results = await self.aliexpress.search_products(
                    keywords=term,
                    page_size=count // 2
                )

                for item in results:
                    price_str = item.get('target_sale_price', '0')
                    price = float(price_str) if price_str else 0

                    original_str = item.get('target_original_price', '0')
                    original_price = float(original_str) if original_str else price

                    product = {
                        "product_id": str(item.get('product_id', '')),
                        "title": item.get('product_title', 'AliExpress Product'),
                        "price": price,
                        "original_price": original_price,
                        "main_image": item.get('product_main_image_url', ''),
                        "source_url": item.get('promotion_link', ''),
                        "source": "aliexpress",
                        "niche": niche,

                        # AliExpress metrics
                        "sales_volume": item.get('lastest_volume', 0),
                        "commission_rate": float(str(item.get('commission_rate', '0')).replace('%', '')),
                        "affiliate_link": item.get('promotion_link', ''),

                        # Data sources metadata
                        "data_sources": {
                            "aliexpress": {
                                "available": True,
                                "orders": item.get('lastest_volume', 0),
                                "url": item.get('promotion_link', '')
                            }
                        },

                        "discovered_at": datetime.now().isoformat()
                    }
                    products.append(product)

        except Exception as e:
            logger.error(f"AliExpress fetch error: {e}")

        return products[:count]

    def _generate_mock_products(self, niche: str, count: int) -> List[Dict]:
        """Generate mock products for testing"""
        import random

        logger.info(f"   Generating {count} mock products for {niche}")

        products = []
        titles = {
            "smart_home": ["Smart LED Strip", "WiFi Plug", "Motion Sensor", "Smart Bulb", "Door Sensor"],
            "fitness": ["Resistance Bands", "Yoga Mat", "Jump Rope", "Ab Roller", "Foam Roller"],
            "kitchen": ["Knife Set", "Food Container", "Vegetable Chopper", "Spice Rack", "Pan Set"],
            "beauty": ["Makeup Brush Set", "Face Roller", "Hair Dryer", "Nail Kit", "Skincare Set"],
            "pet": ["Dog Toy", "Cat Tree", "Pet Brush", "Pet Bowl", "Pet Bed"],
            "tech": ["Phone Stand", "USB Hub", "Webcam", "Mouse Pad", "Cable Organizer"]
        }

        niche_titles = titles.get(niche, titles["tech"])

        for i in range(count):
            base_title = random.choice(niche_titles)
            price = round(random.uniform(9.99, 49.99), 2)

            product = {
                "product_id": f"mock_{niche}_{i}_{random.randint(1000, 9999)}",
                "title": f"{base_title} - Premium Quality",
                "price": price,
                "original_price": round(price * 1.3, 2),
                "main_image": f"https://placehold.co/400x400/1a1a2e/eee?text={base_title.replace(' ', '+')}",
                "source_url": "#",
                "source": "mock_data",
                "niche": niche,

                # Mock metrics
                "views": random.randint(10000, 500000),
                "likes": random.randint(1000, 50000),
                "rating": round(random.uniform(4.0, 5.0), 1),
                "reviews_count": random.randint(100, 5000),
                "viral_score": random.randint(40, 95),
                "demand_score": random.randint(40, 95),

                # Data sources
                "data_sources": {
                    "mock": {
                        "available": True,
                        "note": "Mock data - waiting for API connection"
                    }
                },

                "discovered_at": datetime.now().isoformat()
            }
            products.append(product)

        return products

    async def _validate_with_trends(self, products: List[Dict], niche: str) -> List[Dict]:
        """Validate products with Google Trends"""
        try:
            # Get trend score for the niche
            search_terms = self.NICHE_SEARCH_TERMS.get(niche, [niche])[:3]

            self.trends.build_payload(search_terms, timeframe='today 3-m')
            interest_data = self.trends.interest_over_time()

            if not interest_data.empty:
                # Calculate average trend score
                avg_trend = interest_data.mean().mean()
                trend_momentum = min(avg_trend, 100)

                # Apply trend score to all products
                for product in products:
                    product['trend_score'] = round(trend_momentum, 1)
                    if 'data_sources' not in product:
                        product['data_sources'] = {}
                    product['data_sources']['google_trends'] = {
                        'available': True,
                        'trend_score': round(trend_momentum, 1)
                    }

                logger.info(f"   Google Trends: {trend_momentum:.1f} average interest")

        except Exception as e:
            logger.warning(f"   Trends validation skipped: {e}")
            for product in products:
                product['trend_score'] = 50  # Default neutral

        return products

    def _calculate_final_scores(self, products: List[Dict]) -> List[Dict]:
        """Calculate final scores for all products"""

        for product in products:
            source = product.get('source', 'unknown')

            # Base scores based on source
            if source == 'tiktok_shop':
                # TikTok: viral_score + engagement
                viral = product.get('viral_score', 0)
                views = product.get('views', 0)
                engagement_bonus = min(views / 100000, 20)  # Max 20 points for views
                base_score = viral + engagement_bonus

            elif source == 'amazon_bestsellers':
                # Amazon: demand_score + rating + bestseller bonus
                demand = product.get('demand_score', 0)
                rating = product.get('rating', 0) * 10  # 5 stars = 50 points
                bestseller_bonus = 20 if product.get('is_bestseller') else 0
                base_score = demand + rating + bestseller_bonus

            elif source == 'aliexpress':
                # AliExpress: commission + sales + price value
                commission = product.get('commission_rate', 0) * 5  # 10% = 50 points
                sales = min(product.get('sales_volume', 0) * 2, 30)  # Max 30 points
                price = product.get('price', 0)
                price_bonus = 20 if 10 <= price <= 50 else 10
                base_score = commission + sales + price_bonus

            else:
                # Mock/other: use viral_score or demand_score
                base_score = product.get('viral_score', 0) or product.get('demand_score', 50)

            # Add trend bonus
            trend_score = product.get('trend_score', 50)
            trend_bonus = trend_score * 0.3  # 30% weight for trends

            # Calculate final score
            final_score = min(base_score + trend_bonus, 100)
            product['final_score'] = round(final_score, 1)
            product['velocity_score'] = round(final_score, 1)  # Alias for compatibility

            # Assign tier
            if final_score >= 80:
                product['tier'] = 'EXCELLENT'
            elif final_score >= 65:
                product['tier'] = 'GOOD'
            elif final_score >= 50:
                product['tier'] = 'FAIR'
            else:
                product['tier'] = 'POOR'

            logger.info(f"   📊 {product['title'][:35]}... → {final_score:.0f} ({product['tier']})")

        return products


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

_discovery_engine = None


def get_discovery_engine() -> UnifiedProductDiscoveryV2:
    """Get or create singleton discovery engine"""
    global _discovery_engine
    if _discovery_engine is None:
        _discovery_engine = UnifiedProductDiscoveryV2()
    return _discovery_engine


async def get_live_products(niche: str = "smart_home", limit: int = 20) -> List[Dict]:
    """
    Quick function to get live products (for dashboard/realtime updater)

    Usage:
        products = await get_live_products("smart_home", 20)
    """
    engine = get_discovery_engine()
    return await engine.discover_products(niche=niche, max_products=limit, min_score=30)


async def discover_live_products(niche: str = "smart_home", count: int = 10) -> List[Dict]:
    """Alias for backwards compatibility"""
    return await get_live_products(niche, count)


async def discover_all_niches(products_per_niche: int = 5) -> Dict[str, List[Dict]]:
    """
    Discover products across all niches

    Returns:
        Dict mapping niche to list of products
    """
    engine = get_discovery_engine()
    niches = ["smart_home", "fitness", "kitchen", "beauty", "pet", "tech"]

    results = {}
    for niche in niches:
        try:
            products = await engine.discover_products(
                niche=niche,
                max_products=products_per_niche,
                min_score=40
            )
            results[niche] = products
            logger.info(f"✅ {niche}: {len(products)} products")
        except Exception as e:
            logger.error(f"❌ {niche}: {e}")
            results[niche] = []

    return results


# ============================================================================
# BACKWARDS COMPATIBILITY - Keep old class name working
# ============================================================================

class UnifiedProductDiscovery(UnifiedProductDiscoveryV2):
    """Alias for backwards compatibility"""
    pass
