"""
Ospra Intelligence - Product Discovery Engine v2
================================================
TREND-FIRST discovery with supplier cross-referencing.

FLOW:
1. TRENDS → Get what's hot (Google Trends, TikTok viral, Amazon BSR)
2. SUPPLIERS → Search trending keywords on AliExpress + CJ
3. CROSS-REF → Match similar products across suppliers
4. SENTIMENT → Add social validation
5. SCORE → Calculate OI score with all data

10 DATA SOURCES:
1. Google Trends - Search interest validation (TREND SOURCE)
2. TikTok Shop (via Apify) - Viral product detection (TREND SOURCE)
3. Amazon Bestsellers (via Apify) - Demand validation (TREND SOURCE)
4. X/Twitter Sentiment (via xAI Grok) - Social buzz
5. Reddit Sentiment - Community feedback
6. AliExpress Affiliate API (522382) - Commission links (SUPPLIER)
7. AliExpress Dropshipping API (520918) - Direct sourcing (SUPPLIER)
8. CJ Dropshipping - US/EU warehouse suppliers (SUPPLIER)
9. Claude AI - Analysis & captions
10. OpenAI - Image generation
"""

import asyncio
import logging
import os
import re
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


class ProductDiscoveryEngine:
    """
    TREND-FIRST multi-source product discovery.
    
    Key Insight: Find what's TRENDING first, then find where to SOURCE it.
    """
    
    NICHE_KEYWORDS = {
        "smart_home": ["smart home gadgets", "LED lights", "smart plug wifi", "home automation", "smart bulb"],
        "kitchen": ["kitchen gadgets", "cooking accessories", "food storage", "meal prep", "kitchen organizer"],
        "fitness": ["home gym equipment", "fitness gadgets", "workout accessories", "resistance bands", "yoga mat"],
        "beauty": ["beauty tools", "skincare devices", "makeup accessories", "LED face mask", "hair styling"],
        "tech": ["tech gadgets", "cool gadgets", "electronic accessories", "phone accessories", "wireless charger"],
        "home_decor": ["home decor", "wall art", "decorative accessories", "minimalist decor", "LED decor"],
        "pet": ["pet accessories", "dog toys", "cat products", "pet tech", "pet grooming"],
        "outdoor": ["outdoor gadgets", "camping gear", "hiking accessories", "survival gear", "portable light"],
        "office": ["office accessories", "desk setup", "work from home", "desk organizer", "ergonomic"],
        "gaming": ["gaming accessories", "RGB setup", "gaming desk", "gaming headset", "controller stand"],
    }
    
    def __init__(self):
        """Initialize all data source connectors"""
        self.sources_status = {}
        self._init_trend_sources()
        self._init_supplier_sources()
        self._init_sentiment_sources()
        self._log_status()
    
    # =========================================================================
    # INITIALIZATION
    # =========================================================================
    
    def _init_trend_sources(self):
        """Initialize TREND sources (what's hot)"""
        # Google Trends via TrendAnalyzer (uses pytrends)
        self.trends_available = False
        self.trend_analyzer = None
        try:
            from ospra_os.intelligence.trend_analyzer import TrendAnalyzer
            self.trend_analyzer = TrendAnalyzer()
            # Check if pytrends is actually available
            if self.trend_analyzer.pytrends is not None:
                self.trends_available = True
                self.sources_status['google_trends'] = '[SUCCESS] Connected (pytrends)'
                logger.info("[SUCCESS] Google Trends loaded via TrendAnalyzer")
            else:
                self.sources_status['google_trends'] = '[WARNING] pytrends not installed'
                logger.warning("[WARNING] Google Trends: pytrends not installed")
        except Exception as e:
            self.sources_status['google_trends'] = f'[ERROR] {e}'
            logger.warning(f"[WARNING] Google Trends init failed: {e}")
        
        # TikTok + Amazon via Apify
        self.apify_token = os.getenv('APIFY_API_TOKEN') or os.getenv('OUBONSHOP_APIFY_API_TOKEN')
        self.tiktok_scraper = None
        self.amazon_scraper = None
        self.apify_available = False
        
        if self.apify_token:
            try:
                from ospra_os.product_research.connectors.apify import TikTokShopScraper, AmazonBestsellersScraper
                self.tiktok_scraper = TikTokShopScraper()
                self.amazon_scraper = AmazonBestsellersScraper()
                self.apify_available = True
                self.sources_status['tiktok'] = '[SUCCESS] Connected (Apify)'
                self.sources_status['amazon'] = '[SUCCESS] Connected (Apify)'
                logger.info("[SUCCESS] TikTok + Amazon scrapers loaded")
            except Exception as e:
                self.sources_status['tiktok'] = f'[ERROR] {e}'
                self.sources_status['amazon'] = f'[ERROR] {e}'
        else:
            self.sources_status['tiktok'] = '[ERROR] No APIFY_API_TOKEN'
            self.sources_status['amazon'] = '[ERROR] No APIFY_API_TOKEN'
    
    def _init_supplier_sources(self):
        """Initialize SUPPLIER sources (where to buy)"""
        # AliExpress
        self.aliexpress = None
        self.aliexpress_available = False
        try:
            from ospra_os.integrations.aliexpress.client import AliExpressClient
            self.aliexpress = AliExpressClient(use_affiliate=True)
            self.aliexpress_available = True
            self.sources_status['aliexpress'] = '[SUCCESS] Connected (522382 + 520918)'
            logger.info("[SUCCESS] AliExpress API loaded")
        except Exception as e:
            self.sources_status['aliexpress'] = f'[ERROR] {e}'
        
        # CJ Dropshipping
        self.cj_client = None
        self.cj_available = False
        try:
            from ospra_os.integrations.cj_dropshipping.client import CJDropshippingClient
            self.cj_client = CJDropshippingClient()
            self.cj_available = self.cj_client.is_available()
            self.sources_status['cj_dropshipping'] = '[SUCCESS] Connected (US/EU warehouses)' if self.cj_available else '[ERROR] No token'
            if self.cj_available:
                logger.info("[SUCCESS] CJ Dropshipping API loaded")
        except Exception as e:
            self.sources_status['cj_dropshipping'] = f'[ERROR] {e}'
    
    def _init_sentiment_sources(self):
        """Initialize SENTIMENT sources (social validation)"""
        # X/Twitter via xAI
        self.xai_twitter = None
        self.xai_available = False
        xai_key = os.getenv('XAI_API_KEY')
        if xai_key:
            try:
                from ospra_os.product_research.connectors.social.xai_twitter import XAITwitterDiscovery
                self.xai_twitter = XAITwitterDiscovery(api_key=xai_key)
                self.xai_available = self.xai_twitter.is_available()
                self.sources_status['x_twitter'] = '[SUCCESS] Connected (xAI Grok)' if self.xai_available else '[ERROR] Init failed'
            except Exception as e:
                self.sources_status['x_twitter'] = f'[ERROR] {e}'
        else:
            self.sources_status['x_twitter'] = '[ERROR] No XAI_API_KEY'
        
        # Reddit
        self.reddit = None
        self.reddit_available = False
        reddit_id = os.getenv('OUBONSHOP_REDDIT_CLIENT_ID')
        reddit_secret = os.getenv('OUBONSHOP_REDDIT_SECRET')
        if reddit_id and reddit_secret:
            try:
                from ospra_os.product_research.connectors.social.reddit import RedditConnector
                self.reddit = RedditConnector(client_id=reddit_id, client_secret=reddit_secret)
                self.reddit_available = True
                self.sources_status['reddit'] = '[SUCCESS] Connected'
            except Exception as e:
                self.sources_status['reddit'] = f'[ERROR] {e}'
        else:
            self.sources_status['reddit'] = '[ERROR] No credentials'
    
    def _log_status(self):
        """Log data source status"""
        logger.info("\n" + "="*60)
        logger.info("[OSPRA] OSPRA INTELLIGENCE - DATA SOURCES")
        logger.info("="*60)
        logger.info("\n[TREND] TREND SOURCES (What's Hot):")
        for source in ['google_trends', 'tiktok', 'amazon']:
            logger.info(f"   {source}: {self.sources_status.get(source, '[ERROR] Not loaded')}")
        logger.info("\n[SUPPLIER] SUPPLIER SOURCES (Where to Buy):")
        for source in ['aliexpress', 'cj_dropshipping']:
            logger.info(f"   {source}: {self.sources_status.get(source, '[ERROR] Not loaded')}")
        logger.info("\n[SENTIMENT] SENTIMENT SOURCES (Social Validation):")
        for source in ['x_twitter', 'reddit']:
            logger.info(f"   {source}: {self.sources_status.get(source, '[ERROR] Not loaded')}")
        connected = sum(1 for s in self.sources_status.values() if '[SUCCESS]' in s)
        logger.info(f"\n[STATS] {connected}/{len(self.sources_status)} sources connected")
        logger.info("="*60 + "\n")
    
    # =========================================================================
    # MAIN DISCOVERY (TREND-FIRST FLOW)
    # =========================================================================
    
    async def discover_products(
        self,
        niche: str = "smart_home",
        max_products: int = 20,
        min_score: float = 30.0,
        include_sentiment: bool = True
    ) -> List[Dict]:
        """
        TREND-FIRST discovery flow.
        
        1. Get trending keywords/products
        2. Search suppliers for those trends
        3. Cross-reference across suppliers
        4. Add sentiment data
        5. Score and rank
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"[SEARCH] TREND-FIRST DISCOVERY: {niche}")
        logger.info(f"{'='*60}")
        
        data_sources_used = []
        
        # =====================================================================
        # STEP 1: GET TRENDING KEYWORDS
        # =====================================================================
        logger.info("\n[TREND] STEP 1: Finding trending products/keywords...")
        
        trending_keywords = await self._get_trending_keywords(niche)
        data_sources_used.extend(['google_trends', 'tiktok', 'amazon'])
        
        logger.info(f"   Found {len(trending_keywords)} trending keywords: {trending_keywords[:5]}")
        
        # =====================================================================
        # STEP 2: SEARCH SUPPLIERS FOR TRENDING PRODUCTS
        # =====================================================================
        logger.info("\n[SUPPLIER] STEP 2: Searching suppliers for trending products...")
        
        aliexpress_products = []
        cj_products = []
        
        # Search AliExpress with trending keywords
        if self.aliexpress_available:
            logger.info("   [CART] Searching AliExpress...")
            for keyword in trending_keywords[:3]:  # Top 3 trending keywords
                ali_results = await self._fetch_aliexpress(keyword, count=10)
                aliexpress_products.extend(ali_results)
            logger.info(f"      -> {len(aliexpress_products)} products from AliExpress")
            if aliexpress_products:
                data_sources_used.append('aliexpress')
        
        # Search CJ with trending keywords AND category
        if self.cj_available:
            logger.info("   [PACKAGE] Searching CJ Dropshipping...")
            # First try category-based search (more reliable)
            cj_results = await self._fetch_cj(keyword="", count=15, niche=niche)
            cj_products.extend(cj_results)
            
            # Also try keyword searches if we have trending keywords
            if len(cj_products) < 10:
                for keyword in trending_keywords[:2]:
                    more_results = await self._fetch_cj(keyword=keyword, count=10, niche=None)
                    # Avoid duplicates
                    existing_ids = {p.get('product_id') for p in cj_products}
                    for r in more_results:
                        if r.get('product_id') not in existing_ids:
                            cj_products.append(r)
            
            logger.info(f"      -> {len(cj_products)} products from CJ Dropshipping")
            if cj_products:
                data_sources_used.append('cj_dropshipping')
        
        # =====================================================================
        # STEP 3: CROSS-REFERENCE SUPPLIERS
        # =====================================================================
        logger.info("\n[CROSSREF] STEP 3: Cross-referencing suppliers...")
        
        all_products = await self._cross_reference_suppliers(
            aliexpress_products, 
            cj_products,
            niche
        )
        
        logger.info(f"   -> {len(all_products)} unique products after cross-reference")
        
        if len(all_products) == 0:
            logger.warning("[WARNING] No products found from any source")
            return []
        
        # =====================================================================
        # STEP 4: ENRICH WITH SENTIMENT (if enabled)
        # =====================================================================
        if include_sentiment:
            logger.info("\n[SENTIMENT] STEP 4: Adding sentiment data...")
            
            if self.xai_available:
                logger.info("   [TWITTER] Getting Twitter/X sentiment...")
                all_products = await self._enrich_with_twitter_sentiment(all_products)
                data_sources_used.append('x_twitter')
            
            if self.reddit_available:
                logger.info("   [REDDIT] Getting Reddit sentiment...")
                all_products = await self._enrich_with_reddit_sentiment(all_products, niche)
                data_sources_used.append('reddit')
        
        # =====================================================================
        # STEP 5: SCORE AND RANK
        # =====================================================================
        logger.info("\n[SCORE] STEP 5: Calculating OI scores...")
        
        scored_products = self._calculate_scores(all_products)
        
        # Filter and sort
        filtered = [p for p in scored_products if p.get('oi_score', 0) >= min_score]
        ranked = sorted(filtered, key=lambda x: x.get('oi_score', 0), reverse=True)
        final = ranked[:max_products]
        
        # Add metadata
        for product in final:
            product['_discovery_metadata'] = {
                'sources_queried': list(set(data_sources_used)),
                'discovered_at': datetime.now().isoformat(),
                'niche': niche,
                'flow': 'trend_first_v2'
            }
        
        logger.info(f"\n[SUCCESS] Discovery complete!")
        logger.info(f"   Sources: {', '.join(set(data_sources_used))}")
        logger.info(f"   Total: {len(aliexpress_products) + len(cj_products)} -> Unique: {len(all_products)} -> Final: {len(final)}")
        
        # Log supplier breakdown
        ali_count = sum(1 for p in final if 'aliexpress' in p.get('available_on', []))
        cj_count = sum(1 for p in final if 'cj_dropshipping' in p.get('available_on', []))
        both_count = sum(1 for p in final if len(p.get('available_on', [])) > 1)
        logger.info(f"   AliExpress: {ali_count} | CJ: {cj_count} | Both: {both_count}")
        
        return final
    
    # =========================================================================
    # STEP 1: TRENDING KEYWORDS
    # =========================================================================
    
    async def _get_trending_keywords(self, niche: str) -> List[str]:
        """
        Get trending keywords from multiple sources.
        
        Sources:
        - Niche keywords (base)
        - Google Trends (rising searches) via TrendAnalyzer
        - TikTok (viral product names)
        - Amazon (bestseller keywords)
        """
        keywords = []
        
        # Start with niche keywords
        base_keywords = self.NICHE_KEYWORDS.get(niche, [niche])
        keywords.extend(base_keywords)
        
        # Add Google Trends rising queries via TrendAnalyzer
        if self.trends_available and self.trend_analyzer:
            try:
                for kw in base_keywords[:2]:
                    # TrendAnalyzer uses _get_google_trends internally
                    trend_data = await self.trend_analyzer._get_google_trends(kw, niche)
                    if trend_data.get('available'):
                        # Get rising momentum keywords
                        momentum = trend_data.get('momentum', {})
                        for keyword, score in momentum.items():
                            if score > 10:  # Rising trend
                                keywords.append(keyword)
                        logger.info(f"   [TREND] Google Trends: {trend_data.get('trend_direction', 'STABLE')} for '{kw}'")
            except Exception as e:
                logger.warning(f"[WARNING] Google Trends keywords failed: {e}")
        
        # Add TikTok viral product names
        if self.apify_available and self.tiktok_scraper:
            try:
                tiktok_products = await self.tiktok_scraper.discover_products(
                    niche=niche,
                    max_products=5,
                    keyword=base_keywords[0]
                )
                for p in tiktok_products:
                    name = p.get('name', '')
                    # Extract key product words
                    words = [w for w in name.split() if len(w) > 3 and w.isalpha()]
                    if words:
                        keywords.append(' '.join(words[:3]))
            except Exception as e:
                logger.warning(f"[WARNING] TikTok keywords failed: {e}")
        
        # Dedupe and clean
        seen = set()
        unique_keywords = []
        for kw in keywords:
            kw_clean = kw.lower().strip()
            if kw_clean and kw_clean not in seen:
                seen.add(kw_clean)
                unique_keywords.append(kw)
        
        return unique_keywords[:10]  # Top 10 trending keywords
    
    # =========================================================================
    # STEP 2: SUPPLIER FETCHING
    # =========================================================================
    
    async def _fetch_aliexpress(self, keyword: str, count: int) -> List[Dict]:
        """Fetch from AliExpress API with ALL product images for AI analysis"""
        products = []
        
        try:
            results = await self.aliexpress.search_products(
                keywords=keyword,
                page_size=count
            )
            
            for item in results:
                price_str = item.get('target_sale_price', '0')
                cost_price = float(price_str) if price_str else 0
                if cost_price == 0:
                    continue
                
                suggested_price = round(cost_price * 2.5, 2)
                profit = round(suggested_price - cost_price, 2)
                
                # === CAPTURE ALL PRODUCT IMAGES FOR AI ===
                main_image = item.get('product_main_image_url', '')
                
                # AliExpress API returns product_small_image_urls in various formats
                small_images_data = item.get('product_small_image_urls', {})
                additional_images = []
                
                # Handle different formats from AliExpress API
                if isinstance(small_images_data, dict):
                    # Format: {"string": ["url1", "url2", ...]}
                    additional_images = small_images_data.get('string', [])
                elif isinstance(small_images_data, list):
                    # Format: ["url1", "url2", ...]
                    additional_images = small_images_data
                elif isinstance(small_images_data, str):
                    # Single URL as string
                    additional_images = [small_images_data]
                
                # Build complete image list (deduplicated)
                all_images = [main_image] if main_image else []
                for img in additional_images:
                    if img and img not in all_images and img.startswith('http'):
                        all_images.append(img)
                
                # Limit to 10 images max (enough for AI analysis)
                all_images = all_images[:10]
                
                logger.debug(f"[IMAGES] {item.get('product_title', '')[:30]}: {len(all_images)} images captured")
                
                product = {
                    "product_id": str(item.get('product_id', '')),
                    "title": item.get('product_title', 'AliExpress Product'),
                    "title_normalized": self._normalize_title(item.get('product_title', '')),
                    "cost_price": cost_price,
                    "supplier_cost": cost_price,
                    "suggested_price": suggested_price,
                    "profit": profit,
                    # Primary image for display
                    "image_url": main_image,
                    # ALL images for AI analysis (up to 10)
                    "all_images": all_images,
                    "image_count": len(all_images),
                    "affiliate_link": item.get('promotion_link', ''),
                    "supplier_url": item.get('promotion_link', ''),
                    "source": "aliexpress",
                    "available_on": ["aliexpress"],
                    "is_mock": False,
                    "niche": keyword,
                    "sales_count": item.get('lastest_volume', 0),
                    "commission_rate": float(str(item.get('commission_rate', '0')).replace('%', '')),
                    "data_sources": {
                        "aliexpress": {
                            "available": True,
                            "cost": cost_price,
                            "orders": item.get('lastest_volume', 0),
                            "commission": item.get('commission_rate', '0'),
                            "url": item.get('promotion_link', ''),
                            "image_count": len(all_images)
                        }
                    },
                    "discovered_at": datetime.now().isoformat()
                }
                products.append(product)
                
        except Exception as e:
            logger.error(f"AliExpress fetch error: {e}")
        
        return products
    
    async def _fetch_cj(self, keyword: str, count: int, niche: str = None) -> List[Dict]:
        """Fetch from CJ Dropshipping using keyword AND category"""
        products = []
        
        try:
            # Try category-based search first (more reliable)
            if niche:
                logger.info(f"   [INFO] CJ: Trying category search for niche '{niche}'")
                results = await self.cj_client.search_by_niche(niche, page_size=count)
            else:
                results = []
            
            # If category search returns nothing, try keyword search
            if not results and keyword:
                logger.info(f"   [INFO] CJ: Trying keyword search for '{keyword}'")
                results = await self.cj_client.search_products(keyword, page_size=count)
            
            # Process results - they're already normalized by CJ client
            for item in results:
                # Items are already normalized, just add cross-reference fields
                product = item.copy()
                product['title_normalized'] = self._normalize_title(item.get('title', ''))
                product['available_on'] = ['cj_dropshipping']
                product['niche'] = niche or keyword
                products.append(product)
            
            if products:
                logger.info(f"   [SUCCESS] CJ: {len(products)} products found")
            else:
                logger.warning(f"   [WARNING] CJ: No products for '{keyword}' / niche '{niche}'")
                
        except Exception as e:
            logger.error(f"[ERROR] CJ fetch error: {e}")
        
        return products
    
    # =========================================================================
    # STEP 3: CROSS-REFERENCE SUPPLIERS
    # =========================================================================
    
    async def _cross_reference_suppliers(
        self, 
        aliexpress_products: List[Dict], 
        cj_products: List[Dict],
        niche: str
    ) -> List[Dict]:
        """
        Cross-reference products across suppliers.
        
        Goals:
        1. Find products available on BOTH suppliers
        2. Compare prices to find best deal
        3. Note warehouse advantages
        4. Merge duplicate products
        """
        merged = []
        matched_cj_ids = set()
        
        for ali_product in aliexpress_products:
            ali_title = ali_product.get('title_normalized', '')
            matched = False
            
            # Try to find matching CJ product
            for cj_product in cj_products:
                if cj_product['product_id'] in matched_cj_ids:
                    continue
                    
                cj_title = cj_product.get('title_normalized', '')
                similarity = self._title_similarity(ali_title, cj_title)
                
                if similarity > 0.6:  # 60% title match = likely same product
                    # MATCH FOUND - merge data
                    merged_product = self._merge_supplier_data(ali_product, cj_product)
                    merged.append(merged_product)
                    matched_cj_ids.add(cj_product['product_id'])
                    matched = True
                    logger.debug(f"   [MATCH] Matched: {ali_title[:40]}... ({similarity:.0%})")
                    break
            
            if not matched:
                # No CJ match - add AliExpress only
                ali_product['cross_referenced'] = False
                ali_product['supplier_comparison'] = None
                merged.append(ali_product)
        
        # Add remaining CJ products (not matched)
        for cj_product in cj_products:
            if cj_product['product_id'] not in matched_cj_ids:
                cj_product['cross_referenced'] = False
                cj_product['supplier_comparison'] = None
                merged.append(cj_product)
        
        # Log cross-reference stats
        matched_count = sum(1 for p in merged if p.get('cross_referenced'))
        logger.info(f"   [MATCHED] Cross-referenced: {matched_count} products found on both suppliers")
        
        return merged
    
    def _normalize_title(self, title: str) -> str:
        """Normalize title for comparison"""
        if not title:
            return ""
        # Remove common filler words and normalize
        title = title.lower()
        # Remove size/color variations
        title = re.sub(r'\b(small|medium|large|xl|xxl|s|m|l)\b', '', title)
        title = re.sub(r'\b(black|white|red|blue|green|pink|gold|silver)\b', '', title)
        # Remove numbers and special chars
        title = re.sub(r'[0-9]+', '', title)
        title = re.sub(r'[^\w\s]', ' ', title)
        # Remove extra spaces
        title = ' '.join(title.split())
        return title.strip()
    
    def _title_similarity(self, title1: str, title2: str) -> float:
        """Calculate similarity between two product titles"""
        if not title1 or not title2:
            return 0.0
        return SequenceMatcher(None, title1, title2).ratio()
    
    def _merge_supplier_data(self, ali_product: Dict, cj_product: Dict) -> Dict:
        """Merge data when same product found on both suppliers"""
        # Start with AliExpress data (usually more complete)
        merged = ali_product.copy()
        
        # Mark as cross-referenced
        merged['cross_referenced'] = True
        merged['available_on'] = ['aliexpress', 'cj_dropshipping']
        
        # Add CJ data to data_sources
        if 'data_sources' not in merged:
            merged['data_sources'] = {}
        merged['data_sources']['cj_dropshipping'] = cj_product.get('data_sources', {}).get('cj_dropshipping', {})
        merged['data_sources']['cj_dropshipping']['available'] = True
        
        # Compare prices
        ali_cost = ali_product.get('cost_price', 0)
        cj_cost = cj_product.get('cost_price', 0)
        
        # Supplier comparison
        merged['supplier_comparison'] = {
            'aliexpress_cost': ali_cost,
            'cj_cost': cj_cost,
            'price_diff': abs(ali_cost - cj_cost),
            'cheaper_on': 'cj_dropshipping' if cj_cost < ali_cost else 'aliexpress',
            'cj_warehouse': cj_product.get('warehouse', 'CN'),
            'cj_us_warehouse': cj_product.get('us_warehouse', False),
            'cj_eu_warehouse': cj_product.get('eu_warehouse', False),
        }
        
        # Recommendation based on comparison
        if cj_product.get('us_warehouse') or cj_product.get('eu_warehouse'):
            merged['sourcing_recommendation'] = f"SOURCE FROM CJ: {cj_product.get('warehouse', 'US/EU')} warehouse = faster shipping"
        elif cj_cost < ali_cost * 0.9:  # CJ is 10%+ cheaper
            merged['sourcing_recommendation'] = f"SOURCE FROM CJ: ${cj_cost:.2f} vs ${ali_cost:.2f} on AliExpress"
        else:
            merged['sourcing_recommendation'] = "SOURCE FROM ALIEXPRESS: Better commission rate"
        
        # Store CJ product ID for reference
        merged['cj_pid'] = cj_product.get('cj_pid', '')
        merged['cj_supplier_url'] = cj_product.get('supplier_url', '')
        
        return merged
    
    # =========================================================================
    # STEP 4: SENTIMENT ENRICHMENT
    # =========================================================================
    
    async def _enrich_with_twitter_sentiment(self, products: List[Dict]) -> List[Dict]:
        """Add X/Twitter sentiment via xAI Grok"""
        if not self.xai_available:
            return products
        
        for product in products[:10]:
            try:
                sentiment = await self.xai_twitter.analyze_product_sentiment(
                    product.get('title', '')[:50]
                )
                
                if sentiment and 'sentiment_score' in sentiment:
                    product['twitter_sentiment'] = sentiment.get('sentiment_score', 0)
                    product['twitter_buzz'] = sentiment.get('buzz_level', 'low')
                    
                    if 'data_sources' not in product:
                        product['data_sources'] = {}
                    product['data_sources']['x_twitter'] = {
                        'available': True,
                        'sentiment': sentiment.get('sentiment', 'neutral'),
                        'sentiment_score': sentiment.get('sentiment_score', 0),
                        'buzz': sentiment.get('buzz_level', 'low')
                    }
            except Exception as e:
                logger.warning(f"Twitter sentiment failed: {e}")
            
            await asyncio.sleep(0.3)
        
        return products
    
    async def _enrich_with_reddit_sentiment(self, products: List[Dict], niche: str) -> List[Dict]:
        """Add Reddit community sentiment"""
        if not self.reddit_available:
            return products
        
        subreddit_map = {
            "smart_home": ["smarthome", "homeautomation"],
            "kitchen": ["Cooking", "MealPrepSunday"],
            "fitness": ["homegym", "fitness"],
            "beauty": ["SkincareAddiction", "MakeupAddiction"],
            "tech": ["gadgets", "technology"],
            "pet": ["dogs", "cats"],
            "gaming": ["gaming", "pcgaming"],
        }
        subreddits = subreddit_map.get(niche, ["shutupandtakemymoney"])
        
        try:
            for subreddit in subreddits[:1]:  # Just 1 subreddit for speed
                reddit_posts = await self.reddit.get_subreddit_products(
                    subreddit=subreddit,
                    time_filter="week",
                    limit=20
                )
                
                for product in products:
                    title_lower = product.get('title', '').lower()
                    for post in reddit_posts:
                        post_title = post.name.lower() if hasattr(post, 'name') else ''
                        if any(word in title_lower for word in post_title.split()[:3] if len(word) > 4):
                            product['reddit_mentions'] = product.get('reddit_mentions', 0) + 1
                            if 'data_sources' not in product:
                                product['data_sources'] = {}
                            product['data_sources']['reddit'] = {
                                'available': True,
                                'subreddit': subreddit,
                                'mentions': product.get('reddit_mentions', 0)
                            }
                            break
        except Exception as e:
            logger.warning(f"Reddit sentiment failed: {e}")
        
        return products
    
    # =========================================================================
    # STEP 5: SCORING
    # =========================================================================
    
    def _calculate_scores(self, products: List[Dict]) -> List[Dict]:
        """
        Calculate OI Score with cross-reference bonus.
        
        Components:
        - Demand (25%): Sales, BSR, views
        - Trend (25%): Google Trends, virality
        - Sentiment (15%): Twitter + Reddit
        - Profit (15%): Margin percentage
        - Sourcing (20%): Cross-reference bonus, warehouse advantage
        """
        for product in products:
            # DEMAND (25%)
            demand_score = 50
            sales = product.get('sales_count', 0)
            if sales > 1000:
                demand_score = 90
            elif sales > 500:
                demand_score = 80
            elif sales > 100:
                demand_score = 70
            elif sales > 50:
                demand_score = 60
            product['demand_score'] = demand_score
            
            # TREND (25%)
            trend_score = product.get('trend_score', 50)
            viral_score = product.get('viral_score', 0)
            if viral_score > 0:
                trend_score = max(trend_score, viral_score)
            product['trend_score'] = trend_score
            
            # SENTIMENT (15%)
            sentiment_score = 50
            twitter_sentiment = product.get('twitter_sentiment', 0)
            if twitter_sentiment != 0:
                sentiment_score = int((twitter_sentiment + 1) * 50)
            reddit_mentions = product.get('reddit_mentions', 0)
            if reddit_mentions > 10:
                sentiment_score = max(sentiment_score, 75)
            product['sentiment_score'] = sentiment_score
            
            # PROFIT (15%)
            cost = product.get('cost_price', 0)
            suggested = product.get('suggested_price', 0)
            if cost > 0 and suggested > 0:
                margin = ((suggested - cost) / cost) * 100
                if margin >= 150:
                    profit_score = 95
                elif margin >= 100:
                    profit_score = 80
                elif margin >= 50:
                    profit_score = 65
                else:
                    profit_score = 40
            else:
                profit_score = 50
            product['profit_score'] = profit_score
            
            # SOURCING (20%) - NEW: Cross-reference and warehouse bonus
            sourcing_score = 50
            
            # Bonus for being on both suppliers
            if product.get('cross_referenced'):
                sourcing_score += 20
                logger.debug(f"   +20 cross-reference bonus: {product.get('title', '')[:30]}")
            
            # Bonus for US/EU warehouse (faster shipping)
            if product.get('us_warehouse') or product.get('eu_warehouse'):
                sourcing_score += 15
            
            # Bonus for having CJ option (generally better for dropshipping)
            if 'cj_dropshipping' in product.get('available_on', []):
                sourcing_score += 10
            
            product['sourcing_score'] = min(100, sourcing_score)
            
            # FINAL OI SCORE
            oi_score = (
                demand_score * 0.25 +
                trend_score * 0.25 +
                sentiment_score * 0.15 +
                profit_score * 0.15 +
                sourcing_score * 0.20
            )
            
            product['oi_score'] = round(oi_score, 0)
            product['final_score'] = product['oi_score']
            
            # Tier and recommendation
            if oi_score >= 80:
                product['tier'] = 'EXCELLENT'
                product['recommendation'] = 'Strong buy - trending with great sourcing options'
            elif oi_score >= 65:
                product['tier'] = 'GOOD'
                product['recommendation'] = 'Worth testing - solid opportunity'
            elif oi_score >= 50:
                product['tier'] = 'FAIR'
                product['recommendation'] = 'Proceed with caution'
            else:
                product['tier'] = 'POOR'
                product['recommendation'] = 'Skip - weak signals'
        
        return products


# =============================================================================
# SINGLETON & COMPATIBILITY
# =============================================================================

_engine_instance = None

def get_engine() -> ProductDiscoveryEngine:
    """Get singleton instance"""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = ProductDiscoveryEngine()
    return _engine_instance


async def discover_products(niche: str = "smart_home", count: int = 20) -> List[Dict]:
    """Convenience function"""
    engine = get_engine()
    return await engine.discover_products(niche=niche, max_products=count)


# Backward compatibility
UnifiedProductDiscoveryV3 = ProductDiscoveryEngine
UnifiedProductDiscovery = ProductDiscoveryEngine
OspraIntelligenceEngine = ProductDiscoveryEngine
ProductIntelligenceEngine = ProductDiscoveryEngine
