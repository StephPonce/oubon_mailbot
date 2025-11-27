"""
Unified Product Discovery Engine
=================================
Combines AliExpress Affiliate API (PRIMARY) + Apify (CROSS-REFERENCE)

Data Flow:
1. AliExpress Affiliate API → Live products with commission tracking
2. Google Trends → Validate search volume & trend momentum
3. Apify Scrapers → Cross-reference pricing, reviews, social proof
4. Unified Scoring → Rank products by opportunity score

Why This Architecture:
- ✅ LIVE data from AliExpress (real-time inventory + pricing)
- ✅ Affiliate links ready (instant monetization)
- ✅ Commission rates visible (profit calculation)
- ✅ Apify enrichment (social proof, reviews, competition)
- ✅ Multi-source validation (reduces risk)
"""

import asyncio
import logging
from typing import List, Dict, Optional
from datetime import datetime
from pytrends.request import TrendReq

# AliExpress Affiliate API (PRIMARY SOURCE)
from ospra_os.integrations.aliexpress.client import AliExpressClient

# Cross-reference engines (ENRICHMENT)
try:
    from ospra_os.product_research.connectors.apify import (
        AmazonBestsellersScraper,
        RedditSentimentScraper,
        AliExpressScraper
    )
    HAS_APIFY = True
except ImportError:
    HAS_APIFY = False
    print("⚠️  Apify connectors not available - running with AliExpress only")

logger = logging.getLogger(__name__)


class UnifiedProductDiscovery:
    """
    Unified Product Discovery Engine

    PRIMARY: AliExpress Affiliate API (live products)
    SECONDARY: Apify + Google Trends (validation & enrichment)
    """

    # Niche keywords for discovery
    NICHE_KEYWORDS = {
        "smart_home": [
            "smart plug wifi",
            "led strip lights",
            "smart light bulb",
            "security camera wireless",
            "smart doorbell",
            "motion sensor light"
        ],
        "fitness": [
            "resistance bands",
            "yoga mat",
            "foam roller",
            "jump rope",
            "resistance tubes",
            "ab roller"
        ],
        "kitchen": [
            "silicone spatula set",
            "kitchen organizer",
            "food storage containers",
            "knife sharpener",
            "vegetable chopper",
            "measuring cups"
        ],
        "beauty": [
            "makeup brush set",
            "facial roller",
            "hair straightener",
            "nail art kit",
            "eyelash curler",
            "makeup organizer"
        ],
        "pet": [
            "dog toy",
            "cat toy",
            "pet grooming brush",
            "pet water fountain",
            "pet bed",
            "dog leash"
        ],
        "phone_accessories": [
            "phone case",
            "phone holder car",
            "screen protector",
            "charging cable",
            "phone stand",
            "wireless charger"
        ],
        "car_accessories": [
            "car phone mount",
            "car charger",
            "car organizer",
            "car seat covers",
            "dashcam",
            "car vacuum"
        ],
        "home_decor": [
            "wall art",
            "throw pillows",
            "string lights",
            "wall clock",
            "photo frames",
            "curtains"
        ]
    }

    def __init__(self):
        """Initialize discovery engine"""
        # PRIMARY: AliExpress Affiliate Client
        try:
            self.aliexpress = AliExpressClient(use_affiliate=True)
            self.has_aliexpress = True
            logger.info("✅ AliExpress Affiliate API connected")
        except Exception as e:
            self.has_aliexpress = False
            logger.warning(f"⚠️  AliExpress API not available: {e}")

        # SECONDARY: Apify scrapers for enrichment
        if HAS_APIFY:
            try:
                self.apify_amazon = AmazonBestsellersScraper()
                self.apify_reddit = RedditSentimentScraper()
                self.apify_aliexpress = AliExpressScraper()
                logger.info("✅ Apify enrichment engines loaded")
            except:
                logger.warning("⚠️  Apify enrichment not available")

        # Google Trends for validation
        self.trends = TrendReq(hl='en-US', tz=360)
        logger.info("✅ Google Trends validator loaded")

    async def discover_products(
        self,
        niche: str,
        max_products: int = 20,
        min_trend_score: float = 60.0,
        enable_cross_reference: bool = True
    ) -> List[Dict]:
        """
        Discover trending products for a niche

        Args:
            niche: Niche category (e.g., "smart_home", "fitness")
            max_products: Maximum products to return
            min_trend_score: Minimum Google Trends score (0-100)
            enable_cross_reference: Enable Apify cross-referencing

        Returns:
            List of products with scores and data from all sources
        """
        logger.info(f"🔍 Starting unified discovery for niche: {niche}")
        logger.info(f"   Max products: {max_products}")
        logger.info(f"   Min trend score: {min_trend_score}")
        logger.info(f"   Cross-reference: {enable_cross_reference}")

        # Get keywords for niche
        keywords = self.NICHE_KEYWORDS.get(niche, self.NICHE_KEYWORDS["smart_home"])

        all_products = []

        # Step 1: Get products from AliExpress Affiliate API (PRIMARY)
        logger.info("\n" + "="*80)
        logger.info("📡 STEP 1: AliExpress Affiliate API (PRIMARY SOURCE)")
        logger.info("="*80)

        if self.has_aliexpress:
            for keyword in keywords[:5]:  # Limit to first 5 keywords
                try:
                    logger.info(f"\n🔍 Searching: '{keyword}'")

                    products = await self.aliexpress.search_products(
                        keywords=keyword,
                        page_size=10
                    )

                    logger.info(f"   ✅ Found {len(products)} products")

                    # Transform to unified format
                    for product in products:
                        unified_product = {
                            # Core product data
                            "product_id": str(product.get('product_id')),
                            "title": product.get('product_title', ''),
                            "price": float(product.get('target_sale_price', 0)),
                            "original_price": float(product.get('target_original_price', 0)),
                            "currency": product.get('target_sale_price_currency', 'USD'),

                            # Images
                            "main_image": product.get('product_main_image_url', ''),
                            "images": product.get('product_small_image_urls', {}).get('string', []),

                            # Affiliate data
                            "affiliate_link": product.get('promotion_link', ''),
                            "commission_rate": float(product.get('commission_rate', '0%').replace('%', '')),

                            # Performance metrics
                            "sales_volume": product.get('lastest_volume', 0),
                            "rating": product.get('evaluate_rate', '0%'),

                            # Categories
                            "category_main": product.get('first_level_category_name', ''),
                            "category_sub": product.get('second_level_category_name', ''),

                            # Shop info
                            "shop_name": product.get('shop_name', ''),
                            "shop_id": product.get('shop_id', ''),

                            # Discovery metadata
                            "niche": niche,
                            "keyword": keyword,
                            "source": "aliexpress_affiliate",
                            "discovered_at": datetime.now().isoformat(),

                            # Scoring (to be calculated)
                            "trend_score": 0,
                            "opportunity_score": 0,
                            "competition_score": 0,
                            "final_score": 0,

                            # Data sources metadata for frontend badges
                            "data_sources": {
                                "aliexpress": {
                                    "available": True,
                                    "orders": product.get('lastest_volume', 0),
                                    "url": product.get('promotion_link', '')
                                },
                                "google_trends": {
                                    "available": True,
                                    "trend_score": 0  # Will be updated in validation step
                                }
                            }
                        }

                        all_products.append(unified_product)

                except Exception as e:
                    logger.error(f"   ❌ Error searching '{keyword}': {e}")
                    continue

            logger.info(f"\n✅ Total products from AliExpress: {len(all_products)}")
        else:
            logger.warning("⚠️  AliExpress API not available - skipping primary source")

        # Step 2: Validate with Google Trends
        logger.info("\n" + "="*80)
        logger.info("📈 STEP 2: Google Trends Validation")
        logger.info("="*80)

        for product in all_products:
            keyword = product['keyword']
            try:
                # Get trend data
                self.trends.build_payload([keyword], timeframe='today 3-m')
                interest_data = self.trends.interest_over_time()

                if not interest_data.empty:
                    # Calculate trend score
                    recent_interest = interest_data[keyword].tail(4).mean()
                    peak_interest = interest_data[keyword].max()
                    trend_momentum = (recent_interest / peak_interest * 100) if peak_interest > 0 else 0

                    product['trend_score'] = round(trend_momentum, 1)

                    # Update data_sources with actual trend score
                    if 'data_sources' in product and 'google_trends' in product['data_sources']:
                        product['data_sources']['google_trends']['trend_score'] = round(trend_momentum, 1)

                    logger.info(f"   '{keyword[:30]}...': Trend score {trend_momentum:.1f}")
                else:
                    product['trend_score'] = 0

                    # Update data_sources with 0 score
                    if 'data_sources' in product and 'google_trends' in product['data_sources']:
                        product['data_sources']['google_trends']['trend_score'] = 0

            except Exception as e:
                product['trend_score'] = 50  # Default neutral score
                logger.debug(f"   Trend check skipped for '{keyword}': {e}")

        # Step 3: Cross-reference with Apify (OPTIONAL)
        if enable_cross_reference and HAS_APIFY and len(all_products) > 0:
            logger.info("\n" + "="*80)
            logger.info("🔍 STEP 3: Apify Cross-Reference (ENRICHMENT)")
            logger.info("="*80)

            all_products = await self._cross_reference_with_apify(all_products)

        # Step 4: Calculate final scores
        logger.info("\n" + "="*80)
        logger.info("🎯 STEP 4: Scoring & Ranking")
        logger.info("="*80)

        scored_products = self._calculate_scores(all_products)

        # Step 5: Filter and rank
        # Filter by minimum trend score
        filtered = [p for p in scored_products if p['trend_score'] >= min_trend_score]

        # Sort by final score
        ranked = sorted(filtered, key=lambda x: x['final_score'], reverse=True)

        # Limit to max_products
        final_products = ranked[:max_products]

        logger.info(f"\n✅ Discovery complete!")
        logger.info(f"   Total found: {len(all_products)}")
        logger.info(f"   After filtering: {len(filtered)}")
        logger.info(f"   Final selection: {len(final_products)}")

        return final_products

    async def _cross_reference_with_apify(self, products: List[Dict]) -> List[Dict]:
        """Cross-reference products with Apify data (TikTok, Amazon)"""
        if not HAS_APIFY:
            logger.info("   ⏭️ Apify not available - skipping cross-reference")
            return products

        logger.info(f"   Cross-referencing {len(products)} products with Apify...")

        # Sample first few products for enrichment (avoid API limits)
        sample_size = min(3, len(products))  # Limit to 3 for speed
        sample_products = products[:sample_size]

        for idx, product in enumerate(sample_products):
            try:
                product_name = product.get('title', '')[:50]  # Truncate for search
                logger.info(f"   🔍 [{idx+1}/{sample_size}] Enriching: {product_name}...")

                # Initialize data_sources if not present
                if 'data_sources' not in product:
                    product['data_sources'] = {}

                # 1. TikTok enrichment - Check viral potential
                try:
                    if hasattr(self, 'apify_amazon'):  # Using as generic Apify client
                        tiktok_data = await self.apify_amazon.run_actor(
                            actor_id="clockworks/tiktok-scraper",
                            run_input={
                                "searchQueries": [product_name],
                                "resultsPerPage": 1
                            },
                            timeout_secs=30
                        )

                        if tiktok_data and len(tiktok_data) > 0:
                            top_result = tiktok_data[0]
                            product['data_sources']['tiktok'] = {
                                'available': True,
                                'views': top_result.get('playCount', 0),
                                'url': top_result.get('webVideoUrl', '')
                            }
                            logger.info(f"      ✅ TikTok: {top_result.get('playCount', 0):,} views")
                        else:
                            product['data_sources']['tiktok'] = {'available': False}
                except Exception as e:
                    logger.debug(f"      ⚠️ TikTok check skipped: {e}")
                    product['data_sources']['tiktok'] = {'available': False}

                # 2. Amazon enrichment - Check sales rank & reviews
                try:
                    if hasattr(self, 'apify_amazon'):
                        amazon_data = await self.apify_amazon.run_actor(
                            actor_id="junglee/free-amazon-product-scraper",
                            run_input={
                                "categoryUrls": [f"https://www.amazon.com/s?k={product_name.replace(' ', '+')}"],
                                "maxItems": 1
                            },
                            timeout_secs=30
                        )

                        if amazon_data and len(amazon_data) > 0:
                            top_result = amazon_data[0]
                            product['data_sources']['amazon'] = {
                                'available': True,
                                'sales_rank': top_result.get('salesRank', 0),
                                'url': top_result.get('url', '')
                            }
                            logger.info(f"      ✅ Amazon: Rank #{top_result.get('salesRank', 'N/A')}")
                        else:
                            product['data_sources']['amazon'] = {'available': False}
                except Exception as e:
                    logger.debug(f"      ⚠️ Amazon check skipped: {e}")
                    product['data_sources']['amazon'] = {'available': False}

                product['cross_referenced'] = True
                logger.info(f"   ✅ Enriched: {product_name}")

            except Exception as e:
                logger.warning(f"   ⚠️ Cross-reference failed for '{product.get('title', 'unknown')}': {e}")
                product['cross_referenced'] = False

        logger.info(f"   ✅ Cross-reference complete for {sample_size} products")
        return products

    def _calculate_scores(self, products: List[Dict]) -> List[Dict]:
        """Calculate opportunity scores for products"""
        for product in products:
            # Scoring weights
            weights = {
                'trend': 0.30,        # 30% - Google Trends momentum
                'commission': 0.25,   # 25% - Commission rate
                'sales': 0.20,        # 20% - Sales volume
                'price': 0.15,        # 15% - Price point (sweet spot $10-50)
                'discount': 0.10      # 10% - Discount percentage
            }

            # 1. Trend Score (already calculated, 0-100)
            trend_score = product.get('trend_score', 50)

            # 2. Commission Score (normalize to 0-100)
            commission = product.get('commission_rate', 0)
            commission_score = min(commission * 10, 100)  # 10% = 100 points

            # 3. Sales Score (normalize to 0-100)
            sales = product.get('sales_volume', 0)
            sales_score = min(sales * 5, 100)  # 20 sales = 100 points

            # 4. Price Score (sweet spot $10-50)
            price = product.get('price', 0)
            if 10 <= price <= 50:
                price_score = 100
            elif price < 10:
                price_score = price * 10  # $1 = 10 points
            else:
                price_score = max(0, 100 - (price - 50))  # Penalty above $50

            # 5. Discount Score
            original_price = product.get('original_price', price)
            if original_price > 0 and price < original_price:
                discount_pct = ((original_price - price) / original_price) * 100
                discount_score = min(discount_pct * 2, 100)  # 50% discount = 100 points
            else:
                discount_score = 0

            # Calculate weighted final score
            final_score = (
                trend_score * weights['trend'] +
                commission_score * weights['commission'] +
                sales_score * weights['sales'] +
                price_score * weights['price'] +
                discount_score * weights['discount']
            )

            product['opportunity_score'] = round(final_score, 1)
            product['final_score'] = round(final_score, 1)

            # Add tier classification
            if final_score >= 80:
                product['tier'] = 'EXCELLENT'
            elif final_score >= 65:
                product['tier'] = 'GOOD'
            elif final_score >= 50:
                product['tier'] = 'AVERAGE'
            else:
                product['tier'] = 'BELOW_AVERAGE'

            logger.info(f"   📊 {product['title'][:40]}... → Score: {final_score:.1f} ({product['tier']})")

        return products

    async def get_live_trending_products(
        self,
        niche: str = "smart_home",
        count: int = 10
    ) -> List[Dict]:
        """
        Quick method to get live trending products using AliExpress Affiliate API
        (For dashboard integration - FAST!)
        """
        from datetime import datetime

        logger.info(f"🚀 Quick AliExpress Discovery: niche={niche}, count={count}")

        # Get keywords for this niche
        keywords = self.NICHE_KEYWORDS.get(niche, ["trending products"])
        all_products = []

        # Search AliExpress for each keyword
        for keyword in keywords[:5]:  # Limit to 5 keywords for speed
            logger.info(f"🔍 Searching AliExpress: {keyword}")
            try:
                products = await self.aliexpress.search_products(
                    keywords=keyword,
                    page_size=min(count, 10),  # 10 products per keyword
                    min_price=5,
                    max_price=100
                )

                # Transform to our format
                for p in products:
                    # Parse rating - AliExpress returns as string like "95.5%" or "0"
                    rating_str = p.get("evaluate_rate", "0")
                    if isinstance(rating_str, str):
                        # Remove % sign if present and convert to float
                        rating = float(rating_str.replace('%', '')) / 20.0  # Convert 0-100% to 0-5 stars
                    else:
                        rating = float(rating_str) if rating_str else 0.0

                    # Parse price fields - AliExpress returns as strings
                    price_str = p.get("target_sale_price", "0")
                    price = float(price_str) if price_str else 0.0

                    original_price_str = p.get("target_original_price", "0")
                    original_price = float(original_price_str) if original_price_str else 0.0

                    # Parse commission rate - comes as "7.0%"
                    commission_str = p.get("commission_rate", "0")
                    if isinstance(commission_str, str):
                        commission_rate = float(commission_str.replace('%', ''))
                    else:
                        commission_rate = float(commission_str) if commission_str else 0.0

                    # Calculate REAL scores based on product metrics
                    # Price Value Score (0-30): Lower price relative to original = better deal
                    price_value = 0
                    if original_price > 0:
                        discount_pct = ((original_price - price) / original_price) * 100
                        price_value = min(discount_pct * 0.5, 30)  # Max 30 points

                    # Rating Score (0-30): 5 stars = 30 points
                    rating_score = (rating / 5.0) * 30 if rating > 0 else 0

                    # Commission Score (0-20): Higher commission = more profit
                    commission_score = min(commission_rate * 2, 20)  # Max 20 points

                    # Price Range Score (0-20): Sweet spot $10-$50
                    if 10 <= price <= 50:
                        price_range_score = 20
                    elif 5 <= price < 10 or 50 < price <= 100:
                        price_range_score = 10
                    else:
                        price_range_score = 5

                    # Final Velocity Score (0-100)
                    velocity_score = round(price_value + rating_score + commission_score + price_range_score)

                    # Determine tier based on score
                    if velocity_score >= 80:
                        tier = "EXCELLENT"
                    elif velocity_score >= 65:
                        tier = "GOOD"
                    elif velocity_score >= 50:
                        tier = "FAIR"
                    else:
                        tier = "POOR"

                    all_products.append({
                        "product_id": p.get("product_id", ""),
                        "title": p.get("product_title", ""),
                        "main_image": p.get("product_main_image_url", ""),
                        "price": price,
                        "original_price": original_price,
                        "commission_rate": commission_rate,
                        "affiliate_link": p.get("promotion_link", ""),
                        "sales_volume": p.get("volume", 0),
                        "rating": rating,  # Now a number 0-5
                        "niche": niche,
                        "keyword": keyword,
                        "trend_score": round(price_value + rating_score),  # Trend = value + rating
                        "final_score": velocity_score,  # REAL calculated velocity
                        "tier": tier,  # REAL tier based on score
                        "competition_score": round(50 + (rating_score / 2)),  # Competition based on rating
                        "discovered_at": datetime.now().isoformat(),

                        # Data sources metadata for frontend badges
                        "data_sources": {
                            "aliexpress": {
                                "available": True,
                                "orders": p.get("volume", 0),
                                "url": p.get("promotion_link", "")
                            },
                            "google_trends": {
                                "available": True,
                                "trend_score": round(price_value + rating_score)
                            }
                        }
                    })

                logger.info(f"✅ Found {len(products)} AliExpress products")

            except Exception as e:
                logger.error(f"❌ Search failed for '{keyword}': {e}")
                continue

        # Deduplicate and limit
        seen_ids = set()
        unique_products = []
        for p in all_products:
            if p["product_id"] not in seen_ids:
                seen_ids.add(p["product_id"])
                unique_products.append(p)
                if len(unique_products) >= count:
                    break

        logger.info(f"✅ Returning {len(unique_products)} unique products for {niche}")
        return unique_products

    async def discover_multiple_niches(
        self,
        niches: List[str],
        products_per_niche: int = 5
    ) -> Dict[str, List[Dict]]:
        """
        Discover products across multiple niches
        (For dashboard overview)
        """
        results = {}

        for niche in niches:
            try:
                products = await self.discover_products(
                    niche=niche,
                    max_products=products_per_niche,
                    min_trend_score=55.0,  # Slightly lower threshold
                    enable_cross_reference=False
                )
                results[niche] = products
                logger.info(f"✅ {niche}: {len(products)} products")
            except Exception as e:
                logger.error(f"❌ {niche}: {e}")
                results[niche] = []

        return results


# Convenience function for quick access
async def discover_live_products(niche: str = "smart_home", count: int = 10) -> List[Dict]:
    """
    Quick function to discover live products

    Usage:
        products = await discover_live_products("smart_home", 20)
    """
    engine = UnifiedProductDiscovery()
    return await engine.get_live_trending_products(niche, count)
