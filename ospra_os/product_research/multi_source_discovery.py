"""Product discovery from multiple sources without Reddit dependency."""

from typing import List, Dict, Optional
import asyncio
from pytrends.request import TrendReq

# Optional cross-reference engine import
try:
    from ospra_os.intelligence.cross_reference import CrossReferenceEngine
    HAS_CROSS_REF = True
except ImportError:
    CrossReferenceEngine = None
    HAS_CROSS_REF = False

# Optional imports - system works without these
try:
    from ospra_os.product_research.connectors.amazon import AmazonPAAPIConnector
    HAS_AMAZON = True
except ImportError:
    AmazonPAAPIConnector = None
    HAS_AMAZON = False

try:
    from ospra_os.product_research.connectors.apify import (
        TikTokShopScraper,
        AmazonBestsellersScraper
        # Removed 2025-12-07: RedditSentimentScraper, ShopifyCompetitorScraper, AliExpressScraper
        # Use official APIs instead: AliExpress Affiliate API, X/Twitter API, Shopify API
    )
    HAS_APIFY = True
except ImportError:
    TikTokShopScraper = None
    AmazonBestsellersScraper = None
    HAS_APIFY = False

try:
    from ospra_os.product_research.connectors.social.xai_twitter import XAITwitterDiscovery
    HAS_XAI_TWITTER = True
except ImportError:
    XAITwitterDiscovery = None
    HAS_XAI_TWITTER = False


class MultiSourceDiscovery:
    """
    Discover trending products using multiple data sources.

    NO REDDIT DEPENDENCY - works perfectly on cloud hosts like Render!

    Data Sources:
    1. Google Trends (search volume - shows REAL buying intent)
    2. Amazon PA-API (US market data - best pricing intelligence)
    3. AliExpress API (dropship pricing - supplier data)
    4. TikTok Shop via Apify (viral products + engagement data)
    5. Amazon Bestsellers via Apify (proven demand + sales velocity)

    Why multi-source is powerful:
    - ✅ Google Trends: Real buying intent signals
    - ✅ Amazon PA-API: US market validation + competitive pricing
    - ✅ AliExpress: Dropship costs + profit margins
    - ✅ TikTok Shop: Viral potential + social proof
    - ✅ Amazon Bestsellers: Proven demand + velocity leaders
    - ✅ Works on Render (no blocking)
    - ✅ Comprehensive market intelligence across 5 sources
    """

    # Curated trending keywords for each niche (Smart Home Focus)
    TRENDING_KEYWORDS = {
        "smart_home": [
            "smart home devices",
            "alexa smart home",
            "wifi smart plug",
            "smart light bulbs",
            "smart home security",
            "google home devices",
            "smart home hub",
            "smart thermostat"
        ],
        "smart_lighting": [
            "led strip lights",
            "smart bulbs",
            "rgb lights",
            "alexa lights",
            "wifi led strips"
        ],
        "home_security": [
            "security camera",
            "doorbell camera",
            "smart lock",
            "ring doorbell",
            "wyze cam"
        ],
        "cleaning_gadgets": [
            "robot vacuum",
            "cordless vacuum",
            "air purifier",
            "steam mop",
            "carpet cleaner"
        ],
        "kitchen_tech": [
            "air fryer",
            "instant pot",
            "coffee maker",
            "ninja blender",
            "smart scale"
        ],
        "smart_home_hub": [
            "smart speaker",
            "google home",
            "alexa echo",
            "smart display",
            "home hub"
        ],
        "climate_control": [
            "smart thermostat",
            "humidifier",
            "dehumidifier",
            "tower fan",
            "air circulator"
        ]
    }

    def __init__(self):
        """Initialize multi-source discovery."""
        self.pytrends = None
        self.aliexpress = None
        self.amazon = None
        self.tiktok = None
        self.amazon_bestsellers = None
        self.reddit = None
        self.shopify_competitor = None
        self.xai_twitter = None

        # Try to initialize Amazon connector
        try:
            from ospra_os.core.settings import get_settings

            settings = get_settings()
            if settings.AMAZON_ACCESS_KEY and settings.AMAZON_SECRET_KEY and settings.AMAZON_PARTNER_TAG:
                self.amazon = AmazonPAAPIConnector(
                    access_key=settings.AMAZON_ACCESS_KEY,
                    secret_key=settings.AMAZON_SECRET_KEY,
                    partner_tag=settings.AMAZON_PARTNER_TAG,
                    country=settings.AMAZON_COUNTRY
                )
                print("✅ Amazon PA-API connector initialized")
            else:
                print("⚠️  Amazon PA-API credentials not configured - skipping Amazon enrichment")
        except Exception as e:
            print(f"⚠️  Failed to initialize Amazon connector: {e}")
            self.amazon = None

        # Try to initialize AliExpress connector
        try:
            from ospra_os.core.settings import get_settings
            from ospra_os.product_research.connectors.suppliers.aliexpress import AliExpressConnector

            settings = get_settings()
            if settings.ALIEXPRESS_API_KEY and settings.ALIEXPRESS_APP_SECRET:
                self.aliexpress = AliExpressConnector(
                    api_key=settings.ALIEXPRESS_API_KEY,
                    app_secret=settings.ALIEXPRESS_APP_SECRET
                )
                print("✅ AliExpress API connector initialized")
            else:
                print("⚠️  AliExpress API credentials not configured - using estimated pricing")
        except Exception as e:
            print(f"⚠️  Failed to initialize AliExpress connector: {e}")
            self.aliexpress = None

        # Try to initialize TikTok Shop scraper via Apify
        try:
            self.tiktok = TikTokShopScraper()
            if self.tiktok.is_available():
                print("✅ TikTok Shop scraper initialized via Apify")
            else:
                print("⚠️  Apify not configured - skipping TikTok Shop scraping")
                self.tiktok = None
        except Exception as e:
            print(f"⚠️  Failed to initialize TikTok scraper: {e}")
            self.tiktok = None

        # Try to initialize Amazon Bestsellers scraper via Apify
        try:
            self.amazon_bestsellers = AmazonBestsellersScraper()
            if self.amazon_bestsellers.is_available():
                print("✅ Amazon Bestsellers scraper initialized via Apify")
            else:
                print("⚠️  Apify not configured - skipping Amazon Bestsellers scraping")
                self.amazon_bestsellers = None
        except Exception as e:
            print(f"⚠️  Failed to initialize Amazon Bestsellers scraper: {e}")
            self.amazon_bestsellers = None

        # REMOVED 2025-12-07: Reddit, Shopify, AliExpress Apify scrapers
        # Use official APIs instead:
        # - Reddit → X/Twitter API (via xAI) + TikTok API
        # - Shopify → Official Shopify Admin API
        # - AliExpress → Official AliExpress Affiliate API
        self.reddit = None
        self.shopify_competitor = None
        self.aliexpress_scraper = None

        # Try to initialize xAI Twitter discovery
        try:
            self.xai_twitter = XAITwitterDiscovery()
            if self.xai_twitter.is_available():
                print("✅ xAI Twitter Discovery initialized")
            else:
                self.xai_twitter = None
        except Exception as e:
            print(f"⚠️  xAI Twitter init failed: {e}")
            self.xai_twitter = None

        # Initialize cross-reference engine if all required scrapers are available
        # Updated 2025-12-07: Use xAI Twitter instead of Reddit
        self.cross_ref = None
        if HAS_CROSS_REF and self.amazon_bestsellers and self.tiktok and self.xai_twitter:
            try:
                self.cross_ref = CrossReferenceEngine(
                    self.amazon_bestsellers,
                    self.tiktok,
                    self.xai_twitter  # Use xAI Twitter instead of Reddit
                )
                print("✅ Cross-reference engine initialized (with xAI Twitter)")
            except Exception as e:
                print(f"⚠️  Failed to initialize cross-reference engine: {e}")
                self.cross_ref = None
        else:
            if not HAS_CROSS_REF:
                print("⚠️  Cross-reference engine unavailable (module not found)")
            else:
                print("⚠️  Cross-reference engine unavailable (missing scrapers: Amazon, TikTok, or xAI Twitter)")

    async def discover_all_niches(
        self,
        min_score: float = 70,
        max_per_niche: int = 5
    ) -> Dict[str, List[Dict]]:
        """
        Discover trending products across all niches using Google Trends.

        Args:
            min_score: Minimum Google Trends score (0-100)
            max_per_niche: Maximum products per niche

        Returns:
            {
                "smart_lighting": [
                    {
                        "name": "LED Strip Lights",
                        "niche": "smart_lighting",
                        "score": 7.8,
                        "trend_score": 78,
                        "source": "Google Trends",
                        "priority": "HIGH"
                    },
                    ...
                ],
                ...
            }
        """

        print(f"\n{'='*70}")
        print(f"🔍 MULTI-SOURCE DISCOVERY STARTING (REDDIT-FREE)")
        print(f"{'='*70}")
        print(f"Niches: {len(self.TRENDING_KEYWORDS)}")
        print(f"Min Trend Score: {min_score}/100")
        print(f"Max Per Niche: {max_per_niche}")
        print(f"Data Source: Google Trends (Real search behavior)")
        print(f"{'='*70}\n")

        all_products = {}
        total_checked = 0
        total_found = 0

        for niche, keywords in self.TRENDING_KEYWORDS.items():
            print(f"📊 Discovering {niche}...")

            niche_products = []

            for keyword in keywords:
                total_checked += 1

                try:
                    # Get Google Trends data
                    trend_score = await self._get_trend_score(keyword)

                    # Calculate enhanced score with more variation
                    enhanced_score = self._calculate_enhanced_score(
                        trend_score=trend_score,
                        keyword=keyword,
                        niche=niche
                    )

                    if enhanced_score >= (min_score / 10):  # Convert min_score to 0-10 scale
                        product = {
                            "name": keyword.title(),
                            "niche": niche,
                            "score": enhanced_score,
                            "trend_score": trend_score,
                            "search_volume": int(trend_score),  # Represents relative search volume
                            "source": "google_trends",
                            "priority": self._get_priority(enhanced_score),
                            "tags": ["trending", niche, "google_trends"],
                            "search_query": keyword,  # For smart search
                            # Placeholders for Amazon data (enriched later)
                            "amazon_price": None,
                            "amazon_url": None,
                            "amazon_image": None,
                            "amazon_rating": None,
                            # Placeholders for AliExpress data (enriched later)
                            "aliexpress_price": None,
                            "aliexpress_url": None,
                            "aliexpress_image": None,
                            "supplier_rating": None
                        }
                        niche_products.append(product)
                        total_found += 1
                        print(f"   ✅ {keyword}: {enhanced_score}/10 (trend: {trend_score}/100) → {product['priority']} priority")
                    else:
                        print(f"   ⚠️  {keyword}: {enhanced_score}/10 (below threshold)")

                    # Rate limit to avoid Google Trends throttling
                    await asyncio.sleep(2.0)  # Slower but more accurate - reduces 429 rate limit errors

                except Exception as e:
                    print(f"   ❌ {keyword} failed: {e}")
                    continue

            # Sort by score (highest first)
            niche_products.sort(key=lambda x: x["score"], reverse=True)

            # Limit to max_per_niche
            all_products[niche] = niche_products[:max_per_niche]

            if len(niche_products) > 0:
                print(f"   🔥 Found {len(niche_products)} products in {niche}")
            else:
                print(f"   📭 No products above threshold in {niche}")

        print(f"\n{'='*70}")
        print(f"✅ MULTI-SOURCE DISCOVERY COMPLETE")
        print(f"{'='*70}")
        print(f"Keywords Checked: {total_checked}")
        print(f"Products Found: {total_found}")
        print(f"Niches with Products: {sum(1 for p in all_products.values() if len(p) > 0)}")
        print(f"{'='*70}\n")

        # Enrich with Amazon data if available
        if self.amazon and self.amazon.is_available():
            print(f"\n{'='*70}")
            print(f"🛍️  ENRICHING WITH AMAZON DATA (US Market Intelligence)")
            print(f"{'='*70}\n")
            await self._enrich_with_amazon(all_products)

        # Enrich with AliExpress data if available
        if self.aliexpress and self.aliexpress.is_available():
            print(f"\n{'='*70}")
            print(f"🛒 ENRICHING WITH ALIEXPRESS DATA (Dropship Pricing)")
            print(f"{'='*70}\n")
            await self._enrich_with_aliexpress(all_products)

        # Enrich with TikTok Shop data if available
        if self.tiktok and self.tiktok.is_available():
            await self._enrich_with_tiktok(all_products)

        # Enrich with Amazon Bestsellers data if available
        if self.amazon_bestsellers and self.amazon_bestsellers.is_available():
            await self._enrich_with_amazon_bestsellers(all_products)

        return all_products

    async def _get_trend_score(self, keyword: str) -> float:
        """
        Get Google Trends score (0-100).

        This represents relative search volume:
        - 100 = Peak popularity
        - 50 = Half of peak
        - 0 = Very low search volume
        """
        try:
            # Initialize pytrends if not already done
            if self.pytrends is None:
                self.pytrends = TrendReq(hl='en-US', tz=360)

            # Build payload for last 3 months
            self.pytrends.build_payload([keyword], timeframe='today 3-m')

            # Rate limiting: prevent 429 errors from Google
            await asyncio.sleep(1.5)

            # Get interest over time
            interest = self.pytrends.interest_over_time()

            if not interest.empty and keyword in interest.columns:
                # Calculate average interest over the period
                avg_interest = interest[keyword].mean()
                return float(avg_interest)

            return 0.0

        except Exception as e:
            print(f"      Trends API error for '{keyword}': {e}")
            # Return a default score instead of failing completely
            return 50.0  # Neutral score

    def _calculate_enhanced_score(
        self,
        trend_score: float,
        keyword: str,
        niche: str
    ) -> float:
        """
        Calculate score with MORE variation and intelligence.

        New scoring model:
        - Trend score (0-100) base with aggressive distribution
        - Keyword bonuses (popular terms)
        - Niche multipliers (hot categories)
        - Competition penalties (oversaturated)
        """

        # Step 1: Aggressive base score distribution
        if trend_score >= 75:
            base_score = 7.5 + ((trend_score - 75) / 25) * 2.5  # 7.5-10.0
        elif trend_score >= 60:
            base_score = 6.0 + ((trend_score - 60) / 15) * 1.5  # 6.0-7.5
        elif trend_score >= 45:
            base_score = 4.5 + ((trend_score - 45) / 15) * 1.5  # 4.5-6.0
        elif trend_score >= 30:
            base_score = 3.0 + ((trend_score - 30) / 15) * 1.5  # 3.0-4.5
        else:
            base_score = (trend_score / 30) * 3.0  # 0-3.0

        # Step 2: Keyword bonuses (hot product types)
        keyword_bonuses = {
            'led': 0.8,
            'smart': 0.7,
            'wireless': 0.5,
            'robot': 0.6,
            'security': 0.5,
            'camera': 0.4,
            'rgb': 0.6,
            'alexa': 0.5,
            'google home': 0.5,
            'bluetooth': 0.3,
            'usb': 0.2,
            'portable': 0.3,
            'automatic': 0.4,
            'wifi': 0.5,
            'app control': 0.6,
            'voice': 0.4,
            'programmable': 0.3
        }

        keyword_lower = keyword.lower()
        bonus = 0
        for bonus_word, bonus_points in keyword_bonuses.items():
            if bonus_word in keyword_lower:
                bonus += bonus_points

        # Step 3: Niche multipliers (trending categories)
        niche_multipliers = {
            'smart_lighting': 1.2,       # Hot category
            'home_security': 1.15,       # Growing
            'cleaning_gadgets': 1.1,     # Popular
            'kitchen_tech': 1.0,         # Stable
            'smart_home_hub': 1.25,      # Very hot
            'climate_control': 1.15      # Growing
        }

        multiplier = niche_multipliers.get(niche, 1.0)

        # Calculate final score
        final_score = (base_score + bonus) * multiplier

        # Cap between 0-10
        return round(min(10.0, max(0.0, final_score)), 1)

    def _get_priority(self, score: float) -> str:
        """
        Convert 0-10 score to priority label.

        HIGH (>=7.5): Strong buying intent - list immediately
        MEDIUM (5.5-7.5): Moderate interest - worth testing
        LOW (<5.5): Weak signal - skip unless niche
        """
        if score >= 7.5:
            return "HIGH"
        elif score >= 5.5:
            return "MEDIUM"
        else:
            return "LOW"

    async def _enrich_with_amazon(self, niche_products: Dict[str, List[Dict]]):
        """
        Enrich products with Amazon US market data.

        Updates products in-place with:
        - amazon_price: US retail price
        - amazon_url: Amazon product link
        - amazon_image: Product image URL
        - amazon_rating: Customer rating (0-5)

        This provides US market validation and competitive pricing intelligence.
        """
        enriched_count = 0
        total_count = sum(len(products) for products in niche_products.values())

        for niche_name, products in niche_products.items():
            for product in products:
                try:
                    # Search Amazon for this product
                    results = await self.amazon.search(
                        query=product["name"],
                        limit=1,  # Just need the top result
                        min_price=500,  # $5 minimum (in cents)
                        max_price=10000  # $100 maximum (in cents)
                    )

                    if results and len(results) > 0:
                        # Use the first (most relevant) result
                        amazon_product = results[0]

                        # Update product with Amazon data
                        product["amazon_price"] = amazon_product.price
                        product["amazon_url"] = amazon_product.url
                        product["amazon_image"] = amazon_product.image_url or product.get("amazon_image")
                        product["amazon_rating"] = amazon_product.supplier_rating  # Uses supplier_rating field

                        enriched_count += 1
                        price_str = f"${amazon_product.price:.2f}" if amazon_product.price else "N/A"
                        rating_str = f"{amazon_product.supplier_rating:.1f}/5" if amazon_product.supplier_rating else "N/A"
                        print(f"   ✅ {product['name']}: {price_str} (rating: {rating_str})")
                    else:
                        print(f"   ⚠️  {product['name']}: No Amazon matches found")

                except Exception as e:
                    print(f"   ❌ {product['name']}: Amazon error - {e}")
                    continue

                # Small delay to avoid rate limiting
                await asyncio.sleep(0.5)

        print(f"\n✅ Amazon enrichment complete:")
        print(f"   Enriched: {enriched_count}/{total_count} products")
        print(f"   Coverage: {(enriched_count/total_count*100):.1f}%")
        print(f"{'='*70}\n")

    async def _enrich_with_aliexpress(self, niche_products: Dict[str, List[Dict]]):
        """
        Enrich products with real AliExpress pricing and images.

        Updates products in-place with:
        - aliexpress_price: Real product cost
        - aliexpress_url: Direct product link
        - aliexpress_image: Product image URL
        - supplier_rating: Supplier rating (0-5)
        """
        enriched_count = 0
        total_count = sum(len(products) for products in niche_products.values())

        for niche_name, products in niche_products.items():
            for product in products:
                try:
                    # Search AliExpress for this product
                    results = await self.aliexpress.search(
                        query=product["name"],
                        min_rating=4.0,
                        max_price=50,  # Reasonable upper limit for dropshipping
                        sort="orders"  # Sort by popularity
                    )

                    if results and len(results) > 0:
                        # Use the first (most popular) result
                        ali_product = results[0]

                        # Update product with AliExpress data
                        product["aliexpress_price"] = ali_product.price
                        product["aliexpress_url"] = ali_product.url
                        product["aliexpress_image"] = ali_product.image_url
                        product["supplier_rating"] = ali_product.supplier_rating

                        enriched_count += 1
                        print(f"   ✅ {product['name']}: ${ali_product.price:.2f} (rating: {ali_product.supplier_rating:.1f}/5)")
                    else:
                        print(f"   ⚠️  {product['name']}: No AliExpress matches found")

                except Exception as e:
                    print(f"   ❌ {product['name']}: AliExpress error - {e}")
                    continue

                # Small delay to avoid rate limiting
                await asyncio.sleep(0.5)

        print(f"\n✅ AliExpress enrichment complete:")
        print(f"   Enriched: {enriched_count}/{total_count} products")
        print(f"{'='*70}\n")

    def get_top_products_overall(
        self,
        niche_products: Dict[str, List[Dict]],
        limit: int = 20
    ) -> List[Dict]:
        """
        Get top N products across ALL niches sorted by score.

        Args:
            niche_products: Products organized by niche
            limit: Maximum products to return

        Returns:
            List of top products sorted by score (highest first)
        """
        all_products = []
        for niche_name, products in niche_products.items():
            all_products.extend(products)

        # Sort by score (highest first)
        all_products.sort(key=lambda x: x["score"], reverse=True)

        return all_products[:limit]

    def get_stats(self, niche_products: Dict[str, List[Dict]]) -> Dict:
        """Get discovery statistics."""
        total_products = sum(len(products) for products in niche_products.values())
        niches_with_products = sum(1 for products in niche_products.values() if len(products) > 0)

        # Count by priority
        high_priority = 0
        medium_priority = 0
        low_priority = 0

        for products in niche_products.values():
            for product in products:
                priority = product.get("priority", "LOW")
                if priority == "HIGH":
                    high_priority += 1
                elif priority == "MEDIUM":
                    medium_priority += 1
                else:
                    low_priority += 1

        return {
            "total_products": total_products,
            "niches_searched": len(self.TRENDING_KEYWORDS),
            "niches_with_products": niches_with_products,
            "high_priority": high_priority,
            "medium_priority": medium_priority,
            "low_priority": low_priority,
        }

    def _map_niche_to_tiktok_category(self, niche: str) -> str:
        """Map our niche to TikTok Shop category."""
        mapping = {
            'smart_lighting': 'Home & Garden',
            'home_security': 'Electronics',
            'cleaning_gadgets': 'Home & Garden',
            'kitchen_tech': 'Kitchen & Dining',
            'smart_home_hub': 'Electronics',
            'climate_control': 'Home & Garden'
        }
        return mapping.get(niche, 'All')

    def _map_niche_to_amazon_category(self, niche: str) -> str:
        """Map our niche to Amazon category."""
        mapping = {
            'smart_lighting': 'Electronics',
            'home_security': 'Electronics',
            'cleaning_gadgets': 'Home & Kitchen',
            'kitchen_tech': 'Home & Kitchen',
            'smart_home_hub': 'Electronics',
            'climate_control': 'Home & Kitchen'
        }
        return mapping.get(niche, 'All')

    async def _enrich_with_tiktok(self, niche_products: Dict[str, List[Dict]]):
        """
        Enrich products with TikTok Shop viral potential data.

        Updates products in-place with:
        - tiktok_viral_score: Viral potential score
        - tiktok_engagement_rate: Engagement rate percentage
        - tiktok_views: Video views
        - tiktok_sales: Product sales count
        """
        if not self.tiktok or not self.tiktok.is_available():
            return

        enriched_count = 0
        total_count = sum(len(products) for products in niche_products.values())

        print(f"\n{'='*70}")
        print(f"🔥 ENRICHING WITH TIKTOK SHOP DATA (Viral Potential)")
        print(f"{'='*70}\n")

        for niche_name, products in niche_products.items():
            try:
                # Get TikTok trending products for this niche
                tiktok_category = self._map_niche_to_tiktok_category(niche_name)
                tiktok_products = await self.tiktok.scrape_trending_products(
                    category=tiktok_category,
                    max_products=20
                )

                # Create lookup dict by normalized product name
                tiktok_lookup = {}
                for tp in tiktok_products:
                    normalized_name = tp['name'].lower().replace(' ', '')
                    tiktok_lookup[normalized_name] = tp

                # Match products with TikTok data
                for product in products:
                    normalized_product_name = product['name'].lower().replace(' ', '')

                    # Try fuzzy matching (if exact match fails, try partial match)
                    matched_tiktok = None
                    for tiktok_name, tiktok_data in tiktok_lookup.items():
                        if tiktok_name in normalized_product_name or normalized_product_name in tiktok_name:
                            matched_tiktok = tiktok_data
                            break

                    if matched_tiktok:
                        product["tiktok_viral_score"] = matched_tiktok.get("viral_score", 0)
                        product["tiktok_engagement_rate"] = matched_tiktok.get("engagement_rate", 0)
                        product["tiktok_views"] = matched_tiktok.get("views", 0)
                        product["tiktok_sales"] = matched_tiktok.get("sales_count", 0)

                        enriched_count += 1
                        print(f"   🔥 {product['name']}: Viral Score {matched_tiktok.get('viral_score', 0):.1f}")

            except Exception as e:
                print(f"   ❌ {niche_name}: TikTok error - {e}")
                continue

        print(f"\n✅ TikTok enrichment complete:")
        print(f"   Enriched: {enriched_count}/{total_count} products")
        if total_count > 0:
            print(f"   Coverage: {(enriched_count/total_count*100):.1f}%")
        print(f"{'='*70}\n")

    async def _enrich_with_amazon_bestsellers(self, niche_products: Dict[str, List[Dict]]):
        """
        Enrich products with Amazon Bestsellers data.

        Updates products in-place with:
        - amazon_bestseller_rank: Bestseller rank (1 = #1)
        - amazon_demand_score: Demand score (0-100)
        - is_amazon_bestseller: True if in top 100
        """
        if not self.amazon_bestsellers or not self.amazon_bestsellers.is_available():
            return

        enriched_count = 0
        total_count = sum(len(products) for products in niche_products.values())

        print(f"\n{'='*70}")
        print(f"📊 ENRICHING WITH AMAZON BESTSELLERS DATA (Proven Demand)")
        print(f"{'='*70}\n")

        for niche_name, products in niche_products.items():
            try:
                # Get Amazon bestsellers for this niche
                amazon_category = self._map_niche_to_amazon_category(niche_name)
                bestsellers = await self.amazon_bestsellers.scrape_bestsellers(
                    category=amazon_category,
                    max_products=30
                )

                # Create lookup dict by normalized product name
                bestsellers_lookup = {}
                for bs in bestsellers:
                    normalized_name = bs['name'].lower().replace(' ', '')
                    bestsellers_lookup[normalized_name] = bs

                # Match products with bestsellers data
                for product in products:
                    normalized_product_name = product['name'].lower().replace(' ', '')

                    # Try fuzzy matching
                    matched_bestseller = None
                    for bs_name, bs_data in bestsellers_lookup.items():
                        if bs_name in normalized_product_name or normalized_product_name in bs_name:
                            matched_bestseller = bs_data
                            break

                    if matched_bestseller:
                        product["amazon_bestseller_rank"] = matched_bestseller.get("bestseller_rank", 999)
                        product["amazon_demand_score"] = matched_bestseller.get("demand_score", 0)
                        product["is_amazon_bestseller"] = matched_bestseller.get("is_bestseller", False)

                        enriched_count += 1
                        rank_str = f"#{matched_bestseller.get('bestseller_rank', 'N/A')}"
                        demand_str = f"{matched_bestseller.get('demand_score', 0):.1f}"
                        print(f"   📊 {product['name']}: Rank {rank_str}, Demand {demand_str}")

            except Exception as e:
                print(f"   ❌ {niche_name}: Amazon Bestsellers error - {e}")
                continue

        print(f"\n✅ Amazon Bestsellers enrichment complete:")
        print(f"   Enriched: {enriched_count}/{total_count} products")
        if total_count > 0:
            print(f"   Coverage: {(enriched_count/total_count*100):.1f}%")
        print(f"{'='*70}\n")

    async def discover_products_enriched(
        self,
        niche: str,
        max_products: int = 5,
        min_trend_score: float = 70.0
    ) -> List[Dict]:
        """
        CONSERVATIVE ENRICHED DISCOVERY

        1. Find trending keywords with Google Trends (FREE)
        2. Take ONLY top N highest scoring
        3. Enrich with Apify (costs ~$0.10-0.50)
        4. Cross-reference for validation
        5. Return SELLABLE products with URLs, images, everything

        Args:
            niche: Product niche to discover
            max_products: Maximum products to enrich (CONSERVATIVE - keep low)
            min_trend_score: Minimum trend score threshold

        Returns:
            List of enriched, validated products ready to sell
        """
        print(f"\n{'='*70}")
        print(f"🚀 ENRICHED DISCOVERY - Conservative Mode")
        print(f"{'='*70}")
        print(f"Niche: {niche}")
        print(f"Max products: {max_products}")
        print(f"Min trend score: {min_trend_score}")
        print()

        # Step 1: Get trending keywords from Google Trends (FREE)
        print(f"📊 STEP 1: Google Trends Discovery (FREE)...")

        try:
            # Use keywords from our predefined list
            trending_keywords = self.TRENDING_KEYWORDS.get(niche, [niche])

            if not trending_keywords:
                trending_keywords = [niche]

            print(f"✅ Found {len(trending_keywords)} trending keywords")

        except Exception as e:
            print(f"⚠️  Google Trends error: {e}")
            trending_keywords = [niche]

        # Step 2: Score keywords (FREE)
        print(f"\n📊 STEP 2: Scoring keywords...")

        scored_keywords = []
        for keyword in trending_keywords[:max_products * 2]:  # Get 2x to have options
            try:
                # Get real trend score
                trend_score = await self._get_trend_score(keyword)

                # Calculate enhanced score
                score = self._calculate_enhanced_score(
                    trend_score=trend_score,
                    keyword=keyword,
                    niche=niche
                ) * 10  # Scale to 0-100

                scored_keywords.append({
                    'keyword': keyword,
                    'score': score,
                    'trend_score': trend_score
                })

                await asyncio.sleep(1.0)  # Rate limit

            except Exception as e:
                print(f"   ⚠️  Error scoring {keyword}: {e}")
                continue

        # Sort by score, take top N
        scored_keywords.sort(key=lambda x: x['score'], reverse=True)
        top_keywords = scored_keywords[:max_products]

        print(f"✅ Top {len(top_keywords)} keywords selected:")
        for kw in top_keywords[:3]:
            print(f"   • {kw['keyword']} (score: {kw['score']:.1f})")

        # Step 3: Enrich ONLY top keywords with Apify (COSTS MONEY)
        print(f"\n💰 STEP 3: Apify Enrichment (Conservative - top {len(top_keywords)} only)...")

        if not self.cross_ref:
            print("⚠️  Cross-reference engine unavailable, skipping enrichment")
            return []

        enriched_products = []

        for i, kw_data in enumerate(top_keywords, 1):
            keyword = kw_data['keyword']

            print(f"\n   [{i}/{len(top_keywords)}] Enriching: {keyword}")

            try:
                # Cross-reference across all sources
                validation = await self.cross_ref.validate_product(keyword, niche)

                # Build enriched product
                product = {
                    'name': keyword,
                    'niche': niche,
                    'trend_score': kw_data['score'],
                    'validation_score': validation['validation_score'],
                    'recommendation': validation['recommendation']
                }

                # Add Amazon data if found
                if validation['amazon_data']:
                    amazon = validation['amazon_data']
                    product.update({
                        'price': amazon.get('price', 0),
                        'source_url': amazon.get('source_url', ''),
                        'image_url': amazon.get('image_url', ''),
                        'rating': amazon.get('rating', 0),
                        'reviews_count': amazon.get('reviews_count', 0),
                        'asin': amazon.get('asin', ''),
                        'amazon_available': True
                    })
                else:
                    product['amazon_available'] = False

                # Add TikTok data if found
                if validation['tiktok_data']:
                    tiktok = validation['tiktok_data']
                    product.update({
                        'tiktok_viral_score': tiktok.get('viral_score', 0),
                        'tiktok_views': tiktok.get('views', 0),
                        'tiktok_likes': tiktok.get('likes', 0),
                        'tiktok_url': tiktok.get('source_url', ''),
                        'tiktok_available': True
                    })
                else:
                    product['tiktok_available'] = False

                # Add Reddit sentiment if found
                if validation['reddit_data']:
                    reddit = validation['reddit_data']
                    product.update({
                        'reddit_sentiment': reddit.get('sentiment_score', 50),
                        'reddit_mentions': reddit.get('mentions', 0),
                        'reddit_available': True
                    })
                else:
                    product['reddit_available'] = False

                # Calculate final score
                product['final_score'] = (
                    product['trend_score'] * 0.3 +
                    product['validation_score'] * 0.7
                )

                # Determine priority
                if product['final_score'] >= 80 and product['amazon_available']:
                    product['priority'] = 'HIGH'
                elif product['final_score'] >= 60:
                    product['priority'] = 'MEDIUM'
                else:
                    product['priority'] = 'LOW'

                enriched_products.append(product)

            except Exception as e:
                print(f"   ❌ Enrichment failed for {keyword}: {e}")
                continue

        # Step 4: Filter and rank
        print(f"\n📊 STEP 4: Final Ranking...")

        # Only keep products with Amazon URLs (sellable)
        sellable = [p for p in enriched_products if p.get('amazon_available')]

        # Sort by final score
        sellable.sort(key=lambda x: x['final_score'], reverse=True)

        print(f"\n{'='*70}")
        print(f"✅ ENRICHED DISCOVERY COMPLETE")
        print(f"{'='*70}")
        print(f"   Keywords analyzed: {len(top_keywords)}")
        print(f"   Products enriched: {len(enriched_products)}")
        print(f"   Sellable products: {len(sellable)}")

        # Show top 3
        if sellable:
            print(f"\n🏆 TOP SELLABLE PRODUCTS:\n")
            for i, p in enumerate(sellable[:3], 1):
                print(f"   {i}. {p['name']}")
                print(f"      Final Score: {p['final_score']:.1f}/100")
                print(f"      Priority: {p['priority']}")
                print(f"      Recommendation: {p['recommendation']}")
                print(f"      Price: ${p.get('price', 0):.2f}")
                print(f"      Amazon: {'✅' if p['amazon_available'] else '❌'}")
                print(f"      TikTok: {'✅' if p.get('tiktok_available') else '❌'}")
                print(f"      Reddit: {'✅' if p.get('reddit_available') else '❌'}")
                print()

        print(f"{'='*70}\n")

        return sellable

    async def discover_unified(
        self,
        niches: List[str] = None,
        max_per_niche: int = 5,
        min_trend_score: float = 70.0,
        use_tiktok_shop: bool = True,
        use_amazon_bestsellers: bool = True,
        use_shopify_competitors: bool = True
    ) -> List[Dict]:
        """
        UNIFIED product discovery combining all data sources.

        Discovery Strategy - QUAD PRIMARY SOURCES:

        PRIMARY SOURCE 1 - TikTok Shop (What's SELLING on Social Commerce):
        - Real sales data (actual velocity!)
        - Customer engagement (likes, comments, shares)
        - Real reviews and ratings
        - Price data

        PRIMARY SOURCE 2 - Amazon Bestsellers (What's SELLING on Traditional E-commerce):
        - Bestseller rankings (proven velocity!)
        - High-volume sales data
        - Customer reviews and ratings
        - Market pricing data

        PRIMARY SOURCE 3 - Shopify Competitors (What Successful Stores are SELLING):
        - Products from top-performing Shopify stores
        - Proven dropshipping winners
        - Real store data

        PRIMARY SOURCE 4 - Google Trends (What's TRENDING):
        - Search volume (buying intent)
        - Trend momentum

        SECONDARY SOURCES (Cross-reference & Enrich):
        - AliExpress (Apify) → Get ACTUAL dropship URLs + pricing
        - Reddit (Apify) → Sentiment analysis

        Discovery Flow:
        1. Find products from ALL 4 primary sources
        2. Cross-reference and deduplicate by product name
        3. Products appearing in MULTIPLE primary sources = STRONGER signal
        4. Enrich with AliExpress dropship URLs
        5. Validate with Reddit sentiment
        6. Calculate composite score (bonus for multi-source products!)
        7. Return TOP BUY/SKIP/CONSIDER recommendations

        Args:
            niches: List of niches to search (default: smart home niches)
            max_per_niche: Max products per niche
            min_trend_score: Minimum Google Trends score
            use_tiktok_shop: Use TikTok Shop as primary discovery source
            use_amazon_bestsellers: Use Amazon Bestsellers as primary discovery source
            use_shopify_competitors: Use Shopify competitor stores as primary discovery source

        Returns:
            List of enriched products with:
            - Source tracking (which primary sources found this product)
            - TikTok Shop sales data (if available)
            - Amazon bestseller data (velocity, reviews, rank)
            - Shopify competitor data (if available)
            - AliExpress dropship URLs (actual supplier links)
            - Reddit sentiment
            - Final BUY/SKIP recommendation with composite score
            - Bonus scoring for products appearing in multiple primary sources!
        """
        if not niches:
            niches = ["smart_lighting", "home_security", "cleaning_gadgets"]

        print(f"\n{'='*70}")
        print("🚀 UNIFIED QUAD-SOURCE PRODUCT DISCOVERY")
        print(f"{'='*70}\n")
        print(f"📊 Configuration:")
        print(f"   Niches: {niches}")
        print(f"   Max per niche: {max_per_niche}")
        print(f"   Min trend score: {min_trend_score}")
        print(f"\n📡 PRIMARY Discovery Sources (Find Products):")
        print(f"   {'✅' if use_tiktok_shop and self.tiktok else '❌'} 1. TikTok Shop (social commerce sales)")
        print(f"   {'✅' if use_amazon_bestsellers and self.amazon_bestsellers else '❌'} 2. Amazon Bestsellers (traditional e-commerce velocity)")
        print(f"   {'✅' if use_shopify_competitors and self.shopify_competitor else '❌'} 3. Shopify Competitors (proven store winners)")
        print(f"   ✅ 4. Google Trends (search trends)")
        print(f"\n🔍 SECONDARY Sources (Cross-Reference & Enrich):")
        print(f"   {'✅' if self.aliexpress_scraper else '❌'} AliExpress (dropship URLs + pricing)")
        print(f"   {'✅' if self.reddit else '❌'} Reddit (sentiment validation)")
        print(f"\n💡 Products found in MULTIPLE primary sources get BONUS scoring!")
        print(f"\n{'='*70}\n")

        all_products = []
        products_by_name = {}  # Dedupe by product name

        for niche in niches:
            print(f"\n🎯 Processing niche: {niche.upper()}")
            print(f"{'─'*70}")

            niche_products = []

            # ═══════════════════════════════════════════════════════════
            # PRIMARY SOURCE 1: TikTok Shop (What's SELLING NOW)
            # ═══════════════════════════════════════════════════════════
            if use_tiktok_shop and self.tiktok:
                print(f"\n🛍️  TikTok Shop Discovery (ACTUAL SALES DATA):")
                print(f"{'─'*70}")
                try:
                    # Map niches to TikTok Shop categories
                    tiktok_categories = {
                        'smart_lighting': 'Home & Garden',
                        'home_security': 'Electronics',
                        'cleaning_gadgets': 'Home & Garden',
                        'kitchen_tech': 'Kitchen & Dining',
                        'smart_home_hub': 'Electronics',
                        'climate_control': 'Home & Garden'
                    }

                    category = tiktok_categories.get(niche, 'Home & Garden')

                    tiktok_products = await self.tiktok.scrape_trending_products(
                        category=category,
                        max_products=max_per_niche * 2,  # Get more to filter
                        min_sales=50  # Min 50 sales to be considered
                    )

                    print(f"   Found {len(tiktok_products)} products selling on TikTok Shop")

                    for tt_product in tiktok_products[:max_per_niche]:
                        product_name = tt_product.get('name', '')
                        print(f"\n   🔥 TikTok: '{product_name}'")
                        print(f"      Sales: {tt_product.get('sales_count', 0):,}")
                        print(f"      Price: ${tt_product.get('price', 0):.2f}")
                        print(f"      Reviews: {tt_product.get('review_count', 0)}")
                        print(f"      Likes: {tt_product.get('likes', 0):,}")

                        # Create product data starting with TikTok Shop data
                        product_data = {
                            'name': product_name,
                            'niche': niche,
                            'keyword': product_name.lower(),
                            'source': 'QUAD_PRIMARY_DISCOVERY',
                            'primary_sources': ['tiktok_shop'],  # Track which primary sources found this
                            'source_count': 1,  # Number of primary sources

                            # TikTok Shop metrics (ACTUAL SALES!)
                            'tiktok_sales': tt_product.get('sales_count', 0),
                            'tiktok_price': tt_product.get('price', 0),
                            'tiktok_rating': tt_product.get('rating', 0),
                            'tiktok_reviews': tt_product.get('review_count', 0),
                            'tiktok_likes': tt_product.get('likes', 0),
                            'tiktok_comments': tt_product.get('comments', 0),
                            'tiktok_shares': tt_product.get('shares', 0),
                            'tiktok_viral_score': tt_product.get('viral_score', 0),
                            'tiktok_url': tt_product.get('source_url', ''),
                            'image_url': tt_product.get('image_url', ''),
                        }

                        # Now cross-reference with other sources
                        await self._cross_reference_product(product_data, product_name)

                        niche_products.append(product_data)
                        products_by_name[product_name.lower()] = product_data  # Track for cross-referencing

                except Exception as e:
                    print(f"   ❌ TikTok Shop discovery failed: {e}")
                    import traceback
                    traceback.print_exc()

            # ═══════════════════════════════════════════════════════════
            # PRIMARY SOURCE 2: Amazon Bestsellers (What's SELLING on Traditional E-commerce)
            # ═══════════════════════════════════════════════════════════
            if use_amazon_bestsellers and self.amazon_bestsellers:
                print(f"\n📦 Amazon Bestsellers Discovery (PROVEN VELOCITY):")
                print(f"{'─'*70}")
                try:
                    # Map niches to Amazon categories
                    amazon_categories = {
                        'smart_lighting': 'Electronics',
                        'home_security': 'Electronics',
                        'cleaning_gadgets': 'Home & Kitchen',
                        'kitchen_tech': 'Kitchen & Dining',
                        'smart_home_hub': 'Electronics',
                        'climate_control': 'Home & Kitchen'
                    }

                    category = amazon_categories.get(niche, 'Electronics')

                    amazon_products = await self.amazon_bestsellers.scrape_bestsellers(
                        category=category,
                        max_products=max_per_niche * 2  # Get more to filter
                    )

                    print(f"   Found {len(amazon_products)} bestselling products on Amazon")

                    for amz_product in amazon_products[:max_per_niche]:
                        product_name = amz_product.get('name', '')
                        print(f"\n   🏆 Amazon: '{product_name}'")
                        print(f"      Rank: #{amz_product.get('bestseller_rank', '?')}")
                        print(f"      Reviews: {amz_product.get('reviews_count', 0):,}")
                        print(f"      Rating: {amz_product.get('rating', 0):.1f}")

                        # Check if product already exists (cross-reference)
                        if product_name.lower() in products_by_name:
                            print(f"      🔗 CROSS-MATCH! Also found in {products_by_name[product_name.lower()]['primary_sources']}")
                            existing = products_by_name[product_name.lower()]
                            existing['primary_sources'].append('amazon_bestsellers')
                            existing['source_count'] += 1
                            # Add Amazon data
                            existing.update({
                                'amazon_bestseller': True,
                                'amazon_rank': amz_product.get('bestseller_rank', 999),
                                'amazon_rating': amz_product.get('rating', 0),
                                'amazon_reviews': amz_product.get('reviews_count', 0),
                                'amazon_orders_estimate': self._estimate_orders_from_rank(
                                    amz_product.get('bestseller_rank', 999)
                                ),
                                'amazon_reference_url': amz_product.get('source_url', ''),
                            })
                            if not existing.get('image_url'):
                                existing['image_url'] = amz_product.get('image_url', '')
                        else:
                            # New product from Amazon
                            product_data = {
                                'name': product_name,
                                'niche': niche,
                                'keyword': product_name.lower(),
                                'source': 'QUAD_PRIMARY_DISCOVERY',
                                'primary_sources': ['amazon_bestsellers'],
                                'source_count': 1,

                                # Amazon Bestseller metrics
                                'amazon_bestseller': True,
                                'amazon_rank': amz_product.get('bestseller_rank', 999),
                                'amazon_rating': amz_product.get('rating', 0),
                                'amazon_reviews': amz_product.get('reviews_count', 0),
                                'amazon_orders_estimate': self._estimate_orders_from_rank(
                                    amz_product.get('bestseller_rank', 999)
                                ),
                                'amazon_reference_url': amz_product.get('source_url', ''),
                                'image_url': amz_product.get('image_url', ''),
                            }

                            # Cross-reference with secondary sources (AliExpress, Reddit)
                            await self._cross_reference_product(product_data, product_name)

                            niche_products.append(product_data)
                            products_by_name[product_name.lower()] = product_data

                except Exception as e:
                    print(f"   ❌ Amazon Bestsellers discovery failed: {e}")
                    import traceback
                    traceback.print_exc()

            # ═══════════════════════════════════════════════════════════
            # PRIMARY SOURCE 3: Shopify Competitors (What Successful Stores are SELLING)
            # ═══════════════════════════════════════════════════════════
            if use_shopify_competitors and self.shopify_competitor:
                print(f"\n🏪 Shopify Competitor Discovery (PROVEN WINNERS):")
                print(f"{'─'*70}")
                try:
                    # Get products from successful Shopify stores in this niche
                    # You can configure competitor store URLs in settings or pass them in
                    competitor_stores = [
                        f"https://www.example-{niche}-store.com"  # Placeholder - replace with actual stores
                    ]

                    for store_url in competitor_stores[:2]:  # Limit to 2 stores per niche
                        print(f"   Scraping: {store_url}")
                        shopify_products = await self.shopify_competitor.scrape_competitor_store(
                            store_url=store_url,
                            max_products=max_per_niche
                        )

                        print(f"   Found {len(shopify_products)} products in competitor store")

                        for shop_product in shopify_products[:max_per_niche]:
                            product_name = shop_product.get('name', '')
                            print(f"\n   🏬 Shopify: '{product_name}'")
                            print(f"      Price: ${shop_product.get('price', 0):.2f}")

                            # Check if product already exists (cross-reference)
                            if product_name.lower() in products_by_name:
                                print(f"      🔗 CROSS-MATCH! Also found in {products_by_name[product_name.lower()]['primary_sources']}")
                                existing = products_by_name[product_name.lower()]
                                existing['primary_sources'].append('shopify_competitors')
                                existing['source_count'] += 1
                                # Add Shopify data
                                existing.update({
                                    'shopify_competitor': True,
                                    'shopify_price': shop_product.get('price', 0),
                                    'shopify_store_url': store_url,
                                })
                            else:
                                # New product from Shopify
                                product_data = {
                                    'name': product_name,
                                    'niche': niche,
                                    'keyword': product_name.lower(),
                                    'source': 'QUAD_PRIMARY_DISCOVERY',
                                    'primary_sources': ['shopify_competitors'],
                                    'source_count': 1,

                                    # Shopify Competitor metrics
                                    'shopify_competitor': True,
                                    'shopify_price': shop_product.get('price', 0),
                                    'shopify_store_url': store_url,
                                    'image_url': shop_product.get('image_url', ''),
                                }

                                # Cross-reference with secondary sources
                                await self._cross_reference_product(product_data, product_name)

                                niche_products.append(product_data)
                                products_by_name[product_name.lower()] = product_data

                except Exception as e:
                    print(f"   ❌ Shopify Competitors discovery failed: {e}")
                    import traceback
                    traceback.print_exc()

            # ═══════════════════════════════════════════════════════════
            # PRIMARY SOURCE 4: Google Trends (What's TRENDING)
            # ═══════════════════════════════════════════════════════════
            print(f"\n📈 Google Trends Discovery (SEARCH INTENT):")
            print(f"{'─'*70}")

            keywords = self.TRENDING_KEYWORDS.get(niche, [])
            if not keywords:
                print(f"⚠️  No keywords configured for {niche}")
            else:
                print(f"   Analyzing ALL {len(keywords)} trending keywords (will return top {max_per_niche})...")

            # Process ALL keywords, then sort and take top max_per_niche
            google_trends_products = []
            for keyword in keywords:  # Check ALL keywords!
                try:
                    # Get trend score
                    trend_score = await self._get_trend_score(keyword)

                    if trend_score < min_trend_score:
                        print(f"   ⏭️  '{keyword}' trend score too low ({trend_score:.1f}) - skipping")
                        continue

                    print(f"\n   ✅ '{keyword}' - Trend score: {trend_score:.1f}")

                    # Check if product already exists (cross-reference)
                    if keyword.lower() in products_by_name:
                        print(f"      🔗 CROSS-MATCH! Also found in {products_by_name[keyword.lower()]['primary_sources']}")
                        existing = products_by_name[keyword.lower()]
                        existing['primary_sources'].append('google_trends')
                        existing['source_count'] += 1
                        existing['trend_score'] = trend_score  # Add trend data
                        continue  # Skip to next keyword

                    # New product from Google Trends
                    product_data = {
                        'name': keyword.title(),
                        'niche': niche,
                        'keyword': keyword,
                        'trend_score': trend_score,
                        'source': 'QUAD_PRIMARY_DISCOVERY',
                        'primary_sources': ['google_trends'],
                        'source_count': 1,
                    }

                    # Cross-reference with secondary sources (AliExpress, Reddit)
                    await self._cross_reference_product(product_data, keyword)

                    # Add priority
                    final_score = product_data.get('final_score', 0)
                    if final_score >= 85:
                        product_data['priority'] = 'HIGH'
                    elif final_score >= 70:
                        product_data['priority'] = 'MEDIUM'
                    else:
                        product_data['priority'] = 'LOW'

                    print(f"      📊 Final Score: {final_score:.1f}/100 | {product_data['priority']} | {product_data['recommendation']}")

                    google_trends_products.append(product_data)
                    products_by_name[keyword.lower()] = product_data  # Track for cross-referencing

                except Exception as e:
                    print(f"   ❌ Error processing '{keyword}': {e}")
                    continue

            # Sort Google Trends products by score and take top max_per_niche
            google_trends_products.sort(key=lambda x: x.get('final_score', 0), reverse=True)
            top_google_trends = google_trends_products[:max_per_niche]

            print(f"\n   📊 Selected top {len(top_google_trends)} Google Trends products (from {len(google_trends_products)} analyzed)")
            niche_products.extend(top_google_trends)

            # Sort ALL niche products by final score (from all primary sources)
            niche_products.sort(key=lambda x: x.get('final_score', 0), reverse=True)

            # Take top products
            top_products = niche_products[:max_per_niche]
            all_products.extend(top_products)

            print(f"\n   ✅ Found {len(top_products)} products for {niche}")

        print(f"\n{'='*70}")
        print(f"✅ DISCOVERY COMPLETE: {len(all_products)} total products")
        print(f"{'='*70}\n")

        return all_products

    def _estimate_orders_from_rank(self, rank: int) -> int:
        """Estimate order volume from Amazon bestseller rank"""
        if rank <= 10:
            return 10000
        elif rank <= 50:
            return 5000
        elif rank <= 100:
            return 2000
        elif rank <= 500:
            return 500
        else:
            return 100

    async def _cross_reference_product(self, product_data: Dict, product_name: str):
        """
        Cross-reference a product across all sources

        Updates product_data dictionary in-place with:
        - Amazon research data (velocity, reviews)
        - AliExpress dropship URLs
        - Reddit sentiment
        - Google Trends data (if not already present)
        """

        # Amazon research (velocity, reviews) - NOT for dropshipping!
        if self.amazon_bestsellers:
            print(f"      🔍 Amazon research (velocity/reviews)...")
            try:
                amazon_products = await self.amazon_bestsellers.scrape_bestsellers(
                    category="Electronics",
                    max_products=3
                )

                if amazon_products:
                    amazon_ref = amazon_products[0]
                    product_data.update({
                        'amazon_reference': True,
                        'amazon_image': amazon_ref.get('image_url', ''),
                        'amazon_rating': amazon_ref.get('rating', 0),
                        'amazon_reviews': amazon_ref.get('reviews_count', 0),
                        'amazon_rank': amazon_ref.get('bestseller_rank', 999),
                        'amazon_orders_estimate': self._estimate_orders_from_rank(
                            amazon_ref.get('bestseller_rank', 999)
                        ),
                        'amazon_reference_url': amazon_ref.get('source_url', ''),
                    })
                    print(f"         ✅ Amazon: {amazon_ref.get('reviews_count', 0)} reviews, rank #{amazon_ref.get('bestseller_rank', '?')}")
                else:
                    product_data['amazon_reference'] = False
            except Exception as e:
                print(f"         ❌ Amazon lookup failed: {e}")
                product_data['amazon_reference'] = False

        # AliExpress dropship URL (THIS is where we dropship from!)
        if self.aliexpress_scraper:
            print(f"      📦 AliExpress dropship URL...")
            try:
                ali_products = await self.aliexpress_scraper.search_products(
                    keyword=product_name,
                    max_products=3,
                    min_rating=4.0,
                    min_orders=100
                )

                if ali_products:
                    ali_product = ali_products[0]
                    product_data.update({
                        'aliexpress_url': ali_product.get('aliexpress_url', ''),
                        'aliexpress_product_id': ali_product.get('product_id', ''),
                        'cost': ali_product.get('price', 0),
                        'aliexpress_price': ali_product.get('price', 0),
                        'aliexpress_orders': ali_product.get('orders', 0),
                        'aliexpress_rating': ali_product.get('rating', 0),
                        'aliexpress_shipping_cost': ali_product.get('shipping_cost', 0),
                        'aliexpress_free_shipping': ali_product.get('free_shipping', False),
                        'aliexpress_supplier': ali_product.get('seller_name', 'Unknown'),
                        'aliexpress_images': ali_product.get('images', []),
                    })

                    # Calculate profit
                    if product_data.get('tiktok_price', 0) > 0:
                        # Use TikTok price as market price
                        market_price = product_data['tiktok_price']
                        cost = ali_product.get('price', 0)
                        profit = market_price - cost
                        profit_margin = (profit / market_price) * 100 if market_price > 0 else 0

                        product_data.update({
                            'price': market_price,
                            'profit': profit,
                            'profit_margin': profit_margin
                        })

                    print(f"         ✅ AliExpress: ${ali_product.get('price', 0):.2f}, {ali_product.get('orders', 0)} orders")
            except Exception as e:
                print(f"         ❌ AliExpress lookup failed: {e}")

        # Reddit sentiment
        if self.reddit:
            print(f"      💬 Reddit sentiment...")
            try:
                reddit_data = await self.reddit.get_product_sentiment(
                    product_name=product_name,
                    subreddit="BuyItForLife,amazondeals,homeautomation"
                )

                if reddit_data:
                    product_data.update({
                        'reddit_sentiment': reddit_data.get('sentiment', 'neutral'),
                        'reddit_mentions': reddit_data.get('mentions', 0),
                    })
                    print(f"         ✅ Reddit: {reddit_data.get('sentiment', 'neutral')} ({reddit_data.get('mentions', 0)} mentions)")
            except Exception as e:
                print(f"         ❌ Reddit lookup failed: {e}")

        # Google Trends (if not already present from primary discovery)
        if not product_data.get('trend_score'):
            try:
                trend_score = await self._get_trend_score(product_name)
                product_data['trend_score'] = trend_score
            except:
                product_data['trend_score'] = 50  # Default

        # Calculate final score
        final_score = self._calculate_final_score(product_data)
        product_data['final_score'] = final_score
        product_data['recommendation'] = self._get_recommendation(final_score, product_data)

        # Add priority
        if final_score >= 85:
            product_data['priority'] = 'HIGH'
        elif final_score >= 70:
            product_data['priority'] = 'MEDIUM'
        else:
            product_data['priority'] = 'LOW'

        print(f"      📊 Final Score: {final_score:.1f}/100 | {product_data['priority']} | {product_data['recommendation']}")

    def _calculate_final_score(self, product: Dict) -> float:
        """
        Calculate final score from all data sources

        QUAD PRIMARY SOURCE SCORING:
        - Multi-Source Bonus: 20% (products in 2+ primary sources)
        - TikTok Shop Sales: 25%
        - Amazon Bestseller Rank: 20%
        - Google Trends: 15%
        - Shopify Competitor: 5%
        - AliExpress Availability: 10%
        - Reddit Sentiment: 5%
        """
        score = 0

        # MULTI-SOURCE BONUS (20%) - HUGE advantage if found in multiple primary sources!
        source_count = product.get('source_count', 0)
        primary_sources = product.get('primary_sources', [])
        if source_count >= 4:
            # Found in ALL 4 primary sources = MAXIMUM BONUS!
            score += 20
            print(f"         🎯 JACKPOT! Found in ALL 4 primary sources: {primary_sources}")
        elif source_count == 3:
            # Found in 3 primary sources = STRONG SIGNAL
            score += 15
            print(f"         🔥 Found in 3 primary sources: {primary_sources}")
        elif source_count == 2:
            # Found in 2 primary sources = GOOD SIGNAL
            score += 10
            print(f"         ⭐ Found in 2 primary sources: {primary_sources}")
        else:
            # Only 1 primary source
            print(f"         ℹ️  Found in 1 primary source: {primary_sources}")

        # TikTok Shop SALES (25%) - ACTUAL sales data!
        tiktok_sales = product.get('tiktok_sales', 0)
        if tiktok_sales > 0:
            # Normalize sales: 10K+ sales = 100 points
            sales_score = min((tiktok_sales / 10000) * 100, 100)
            score += (sales_score / 100) * 25
            print(f"         TikTok Sales: {(sales_score / 100) * 25:.1f}/25 ({tiktok_sales:,} sales)")

        # Amazon Bestseller Rank (20%) - Traditional e-commerce velocity
        if product.get('amazon_bestseller') or product.get('amazon_reference'):
            rank = product.get('amazon_rank', 999)
            rank_score = max(0, 100 - (rank / 10))
            score += (rank_score / 100) * 20
            print(f"         Amazon Rank: {(rank_score / 100) * 20:.1f}/20 (rank #{rank})")

        # Google Trends (15%) - Search volume/intent
        trend_score = product.get('trend_score', 0)
        if trend_score > 0:
            score += (trend_score / 100) * 15
            print(f"         Google Trends: {(trend_score / 100) * 15:.1f}/15 (trend {trend_score:.1f})")

        # Shopify Competitor (5%) - Bonus if successful stores sell this
        if product.get('shopify_competitor'):
            score += 5
            print(f"         Shopify Competitor: 5/5 (proven winner!)")

        # AliExpress availability (10%) - Must have dropship URL!
        if product.get('aliexpress_url'):
            score += 10
            # Bonus for high orders on AliExpress
            orders = product.get('aliexpress_orders', 0)
            if orders > 1000:
                score += 3  # Small bonus
            print(f"         AliExpress: 10/10 ({orders} orders)")

        # Reddit sentiment (5%)
        sentiment = product.get('reddit_sentiment', 'neutral')
        if sentiment == 'positive':
            score += 5
            print(f"         Reddit: 5/5 (positive sentiment)")
        elif sentiment == 'neutral':
            score += 2.5
            print(f"         Reddit: 2.5/5 (neutral sentiment)")

        return min(100, score)

    def _get_recommendation(self, score: float, product: Dict) -> str:
        """
        Get BUY/SKIP recommendation based on score and ALL data

        Now prioritizes products found in MULTIPLE primary sources!
        """

        # Must have AliExpress URL to dropship
        if not product.get('aliexpress_url'):
            return "SKIP - No dropship URL"

        # Check how many primary sources found this product
        source_count = product.get('source_count', 0)
        tiktok_sales = product.get('tiktok_sales', 0)

        # JACKPOT - Found in ALL 4 primary sources!
        if source_count >= 4:
            if score >= 70:
                return f"🎯 BUY NOW - Found in ALL 4 sources! (Score: {score:.1f})"
            elif score >= 60:
                return f"🎯 STRONG BUY - All 4 sources agree! (Score: {score:.1f})"
            else:
                return f"CONSIDER - 4 sources but lower score ({score:.1f})"

        # Found in 3 primary sources = VERY STRONG
        elif source_count == 3:
            if score >= 75:
                return f"🔥 BUY - 3 sources confirm! (Score: {score:.1f})"
            elif score >= 65:
                return f"🔥 CONSIDER - 3 sources, good potential ({score:.1f})"
            else:
                return f"MAYBE - 3 sources but verify ({score:.1f})"

        # Found in 2 primary sources = STRONG
        elif source_count == 2:
            if score >= 80:
                return f"⭐ BUY - 2 sources + high score ({score:.1f})"
            elif score >= 70:
                return f"⭐ CONSIDER - 2 sources confirm ({score:.1f})"
            else:
                return f"MAYBE - 2 sources but lower score ({score:.1f})"

        # Only 1 primary source - rely on score + TikTok sales
        else:
            if tiktok_sales > 5000:
                # HIGH SALES on TikTok Shop = strong buy signal
                if score >= 75:
                    return f"BUY - Proven TikTok seller ({tiktok_sales:,} sales, {score:.1f})"
                elif score >= 60:
                    return f"CONSIDER - Good TikTok sales ({tiktok_sales:,} sales, {score:.1f})"
            elif tiktok_sales > 1000:
                # MODERATE SALES on TikTok Shop
                if score >= 80:
                    return f"BUY - Strong opportunity ({tiktok_sales:,} TikTok sales, {score:.1f})"
                elif score >= 65:
                    return f"CONSIDER - Decent potential ({tiktok_sales:,} sales, {score:.1f})"
            else:
                # No TikTok sales data - rely on score only
                if score >= 85:
                    return f"BUY - High score ({score:.1f})"
                elif score >= 70:
                    return f"CONSIDER - Good potential ({score:.1f})"

        return f"SKIP - Score too low ({score:.1f}/100)"

    async def discover_with_twitter(
        self,
        niche: str,
        max_products: int = 10,
        time_range: str = "24h"
    ) -> List[Dict]:
        """
        Discover viral products using xAI Twitter Discovery.
        
        Args:
            niche: Product niche (smart_home, fitness, etc.)
            max_products: Maximum products to return
            time_range: Time range for Twitter search ("24h", "7d", "30d")
            
        Returns:
            List of product dicts with Twitter viral metrics
        """
        if not self.xai_twitter:
            print("⚠️  xAI Twitter Discovery not available")
            return []
        
        try:
            twitter_products = await self.xai_twitter.discover_viral_products(
                niche=niche,
                max_products=max_products,
                time_range=time_range
            )

            return [p.to_dict() for p in twitter_products]

        except Exception as e:
            print(f"❌ Twitter discovery error: {e}")
            return []
