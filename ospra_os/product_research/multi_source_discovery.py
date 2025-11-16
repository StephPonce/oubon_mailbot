"""Product discovery from multiple sources without Reddit dependency."""

from typing import List, Dict, Optional
import asyncio
from pytrends.request import TrendReq
from ospra_os.product_research.connectors.amazon import AmazonPAAPIConnector
from ospra_os.product_research.connectors.apify import TikTokShopScraper, AmazonBestsellersScraper


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
