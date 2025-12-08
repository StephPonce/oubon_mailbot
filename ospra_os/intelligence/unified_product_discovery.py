"""
Unified Product Discovery Engine v2
====================================
MULTI-SOURCE Architecture (Official APIs + Strategic Apify)

Data Source Priority (Updated 2025-12-07):
1. TikTok API (viral products) - PRIMARY
   - Viral product detection with engagement metrics
   - Apify scraper supplements official TikTok API with shop-specific data
2. Amazon Apify (bestsellers, proven demand) - SECONDARY
   - No official Amazon Product API exists for non-sellers
   - Provides sales rank and demand validation
3. AliExpress Official API (supplier/pricing) - FOR SOURCING
   - Official Affiliate API (App ID: 522382) for product discovery
   - Dropshipping API (App ID: 520918) for order fulfillment
4. Google Trends API (search interest) - VALIDATION
   - Advanced scraper bypasses rate limits
   - Validates niche momentum and search volume
5. X/Twitter via xAI (social buzz) - SENTIMENT
   - Real-time trending topics via Grok AI
   - Replaces Reddit sentiment analysis

Removed Sources (2025-12-07):
- ❌ Reddit Sentiment Apify scraper (covered by X/Twitter API)
- ❌ AliExpress Apify scraper (replaced by official APIs)
- ❌ Shopify Competitor scraper (not priority)

Cost Savings: ~$30-45/month from Apify cleanup
"""

import asyncio
import logging
from typing import List, Dict, Optional
from datetime import datetime
import os

logger = logging.getLogger(__name__)

# Import OpportunityScorer for integrated scoring
try:
    from ospra_os.intelligence.opportunity_scorer import OpportunityScorer, get_opportunity_scorer
    OPPORTUNITY_SCORER_AVAILABLE = True
    logger.info("✅ OpportunityScorer integrated into Product Discovery")
except ImportError as e:
    OPPORTUNITY_SCORER_AVAILABLE = False
    logger.warning(f"⚠️  OpportunityScorer not available: {e}")


class UnifiedProductDiscoveryV2:
    """
    Multi-Source Product Discovery Engine (Updated 2025-12-07)

    Data Source Priority:
    1. TikTok (via Apify) - Viral products with engagement metrics
    2. Amazon (via Apify) - Bestsellers with proven demand
    3. AliExpress (Official API) - Supplier pricing and sourcing
    4. Google Trends (Advanced Scraper) - Search interest validation
    5. X/Twitter (via xAI Grok) - Social sentiment (future integration)

    Removed deprecated Apify scrapers:
    - Reddit sentiment (replaced by X/Twitter API)
    - AliExpress scraper (replaced by official API)
    - Shopify competitor (not priority)
    """

    # Niche-to-search-term mapping (40+ curated niches)
    NICHE_SEARCH_TERMS = {
        # ===== HOME & LIVING =====
        "smart_home": [
            "smart home gadgets", "LED lights room", "smart plug wifi",
            "home automation", "smart doorbell", "smart sensors"
        ],
        "home_decor": [
            "home decor aesthetic", "wall art modern", "decorative accessories",
            "room decor", "minimalist decor"
        ],
        "lighting": [
            "LED strip lights", "sunset lamp", "galaxy projector",
            "desk lamp", "ambient lighting", "neon signs"
        ],
        "organization": [
            "storage organizer", "closet organization", "desk organizer",
            "drawer organizer", "cable management"
        ],
        "cleaning": [
            "cleaning gadgets", "robot vacuum", "steam cleaner",
            "cleaning tools", "car cleaning"
        ],
        
        # ===== KITCHEN & DINING =====
        "kitchen": [
            "kitchen gadgets", "cooking accessories", "food storage",
            "kitchen organizer", "cooking tools", "meal prep containers"
        ],
        "coffee_tea": [
            "coffee accessories", "espresso tools", "tea infuser",
            "coffee mug", "barista tools"
        ],
        "barware": [
            "cocktail set", "bar accessories", "wine accessories",
            "ice molds", "drink dispenser"
        ],
        
        # ===== HEALTH & WELLNESS =====
        "fitness": [
            "home gym equipment", "fitness gadgets", "workout accessories",
            "resistance bands", "yoga accessories", "exercise equipment"
        ],
        "wellness": [
            "massage gun", "posture corrector", "sleep accessories",
            "meditation accessories", "aromatherapy diffuser"
        ],
        "health": [
            "health gadgets", "pulse oximeter", "blood pressure monitor",
            "health tracker", "first aid"
        ],
        
        # ===== BEAUTY & PERSONAL CARE =====
        "beauty": [
            "beauty tools", "skincare devices", "makeup accessories",
            "hair styling", "beauty gadgets"
        ],
        "skincare": [
            "skincare tools", "face roller", "LED face mask",
            "facial steamer", "gua sha"
        ],
        "haircare": [
            "hair tools", "hair dryer", "curling iron",
            "hair accessories", "scalp massager"
        ],
        "grooming": [
            "grooming kit", "electric shaver", "beard trimmer",
            "nail kit", "personal care"
        ],
        
        # ===== TECH & ELECTRONICS =====
        "tech": [
            "tech gadgets", "cool gadgets", "useful gadgets",
            "electronic accessories", "tech accessories"
        ],
        "phone_accessories": [
            "phone accessories", "phone case", "phone stand",
            "wireless charger", "screen protector", "MagSafe accessories"
        ],
        "audio": [
            "wireless earbuds", "bluetooth speaker", "headphones",
            "audio accessories", "microphone"
        ],
        "computer": [
            "laptop accessories", "keyboard", "mouse pad",
            "webcam", "USB hub", "monitor stand"
        ],
        "gaming": [
            "gaming accessories", "gaming headset", "controller accessories",
            "RGB gaming", "gaming desk accessories"
        ],
        "camera": [
            "camera accessories", "ring light", "tripod",
            "phone gimbal", "vlogging kit"
        ],
        
        # ===== OUTDOOR & TRAVEL =====
        "outdoor": [
            "outdoor gadgets", "camping gear", "hiking accessories",
            "survival gear", "outdoor tools"
        ],
        "travel": [
            "travel accessories", "luggage organizer", "travel gadgets",
            "packing cubes", "travel pillow"
        ],
        "automotive": [
            "car accessories", "car gadgets", "car organizer",
            "car phone mount", "car cleaning"
        ],
        "cycling": [
            "bike accessories", "cycling gear", "bike lights",
            "bike phone mount", "cycling gadgets"
        ],
        
        # ===== PETS =====
        "pet": [
            "pet accessories", "dog toys", "cat products",
            "pet grooming", "pet tech"
        ],
        "dog": [
            "dog accessories", "dog toys", "dog grooming",
            "dog training", "dog bed"
        ],
        "cat": [
            "cat accessories", "cat toys", "cat tree",
            "cat grooming", "cat bed"
        ],
        
        # ===== FAMILY & KIDS =====
        "baby": [
            "baby products", "baby gadgets", "baby safety",
            "baby feeding", "baby toys"
        ],
        "kids": [
            "kids toys", "educational toys", "kids gadgets",
            "kids room decor", "kids accessories"
        ],
        "parenting": [
            "parenting gadgets", "baby monitor", "kids safety",
            "family organizer", "mom accessories"
        ],
        
        # ===== OFFICE & WORK =====
        "office": [
            "office accessories", "desk accessories", "office gadgets",
            "work from home", "desk organization"
        ],
        "desk_setup": [
            "desk setup", "monitor stand", "desk mat",
            "cable management", "desk organizer"
        ],
        "stationery": [
            "stationery", "planner", "notebook",
            "pen set", "desk accessories"
        ],
        
        # ===== FASHION & ACCESSORIES =====
        "fashion_accessories": [
            "fashion accessories", "sunglasses", "watches",
            "bags", "wallets"
        ],
        "jewelry": [
            "jewelry", "necklace", "bracelet",
            "rings", "earrings"
        ],
        "watches": [
            "smart watch accessories", "watch bands", "watch stand",
            "watch case", "luxury watches"
        ],
        
        # ===== HOBBIES & CRAFTS =====
        "crafts": [
            "craft supplies", "DIY kits", "art supplies",
            "sewing accessories", "craft tools"
        ],
        "garden": [
            "garden tools", "plant accessories", "indoor plants",
            "garden gadgets", "hydroponics"
        ],
        "music": [
            "music accessories", "guitar accessories", "piano accessories",
            "music gadgets", "instrument accessories"
        ],
        
        # ===== SPECIAL CATEGORIES =====
        "gifts": [
            "gift ideas", "unique gifts", "personalized gifts",
            "gift set", "gadget gifts"
        ],
        "seasonal": [
            "trending products", "viral products", "new arrivals",
            "bestsellers", "popular items"
        ],
        "eco_friendly": [
            "eco friendly products", "sustainable products", "reusable products",
            "zero waste", "green products"
        ],
        "luxury": [
            "luxury accessories", "premium products", "high end gadgets",
            "designer accessories", "luxury gifts"
        ],
        
        # ===== TRENDING / VIRAL =====
        "tiktok_viral": [
            "TikTok viral products", "TikTok made me buy", "viral gadgets",
            "trending products", "TikTok finds"
        ],
        "amazon_finds": [
            "Amazon finds", "Amazon must haves", "Amazon gadgets",
            "Amazon bestsellers", "hidden gems Amazon"
        ]
    }

    # Amazon category mapping (expanded to 40+ niches)
    AMAZON_CATEGORIES = {
        # Home & Living
        "smart_home": "Smart-Home",
        "home_decor": "Home-Kitchen",
        "lighting": "Lighting-Ceiling-Fans",
        "organization": "Home-Kitchen",
        "cleaning": "Home-Kitchen",
        
        # Kitchen & Dining
        "kitchen": "Kitchen-Dining",
        "coffee_tea": "Kitchen-Dining",
        "barware": "Kitchen-Dining",
        
        # Health & Wellness
        "fitness": "Sports-Outdoors",
        "wellness": "Health-Household",
        "health": "Health-Household",
        
        # Beauty & Personal Care
        "beauty": "Beauty-Personal-Care",
        "skincare": "Beauty-Personal-Care",
        "haircare": "Beauty-Personal-Care",
        "grooming": "Beauty-Personal-Care",
        
        # Tech & Electronics
        "tech": "Electronics",
        "phone_accessories": "Cell-Phones-Accessories",
        "audio": "Electronics",
        "computer": "Computers-Accessories",
        "gaming": "Video-Games",
        "camera": "Electronics",
        
        # Outdoor & Travel
        "outdoor": "Sports-Outdoors",
        "travel": "Luggage-Travel-Gear",
        "automotive": "Automotive",
        "cycling": "Sports-Outdoors",
        
        # Pets
        "pet": "Pet-Supplies",
        "dog": "Pet-Supplies",
        "cat": "Pet-Supplies",
        
        # Family & Kids
        "baby": "Baby",
        "kids": "Toys-Games",
        "parenting": "Baby",
        
        # Office & Work
        "office": "Office-Products",
        "desk_setup": "Office-Products",
        "stationery": "Office-Products",
        
        # Fashion & Accessories
        "fashion_accessories": "Clothing-Shoes-Jewelry",
        "jewelry": "Clothing-Shoes-Jewelry",
        "watches": "Clothing-Shoes-Jewelry",
        
        # Hobbies & Crafts
        "crafts": "Arts-Crafts-Sewing",
        "garden": "Patio-Lawn-Garden",
        "music": "Musical-Instruments",
        
        # Special Categories
        "gifts": "Gift-Cards",
        "seasonal": "Electronics",
        "eco_friendly": "Home-Kitchen",
        "luxury": "Luxury-Beauty",
        
        # Trending
        "tiktok_viral": "Electronics",
        "amazon_finds": "Electronics"
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
                logger.info("✅ Apify scrapers loaded (TikTok: VIRAL DATA / Amazon: DEMAND VALIDATION)")
            except Exception as e:
                logger.warning(f"⚠️  Apify import failed: {e}")

        # Check AliExpress (FOR SOURCING)
        try:
            from ospra_os.integrations.aliexpress.client import AliExpressClient
            self.aliexpress = AliExpressClient(use_affiliate=True)
            self.aliexpress_available = True
            logger.info("✅ AliExpress Official API loaded (SUPPLIER SOURCING & PRICING)")
        except Exception as e:
            logger.warning(f"⚠️  AliExpress not available: {e}")

        # Initialize Google Trends - Use AdvancedProductScraper (bypasses rate limits)
        try:
            from ospra_os.intelligence.advanced_scraper import AdvancedProductScraper
            self.advanced_scraper = AdvancedProductScraper()
            self.trends_available = True
            logger.info("✅ Google Trends (Advanced Scraper) loaded (SEARCH INTEREST VALIDATION)")
        except Exception as e:
            self.advanced_scraper = None
            logger.warning(f"⚠️  Advanced Scraper not available: {e}")

        # Initialize OpportunityScorer (ANTI-AUTODS ALGORITHM)
        self.opportunity_scorer = None
        if OPPORTUNITY_SCORER_AVAILABLE:
            try:
                self.opportunity_scorer = get_opportunity_scorer()
                logger.info("✅ OpportunityScorer loaded (ANTI-SATURATION)")
            except Exception as e:
                logger.warning(f"⚠️  OpportunityScorer init failed: {e}")

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
            # Home & Living
            "smart_home": ["Smart LED Strip", "WiFi Plug", "Motion Sensor", "Smart Bulb", "Door Sensor"],
            "home_decor": ["Wall Art Canvas", "Decorative Vase", "Throw Pillow", "Wall Mirror", "Floating Shelf"],
            "lighting": ["LED Strip Lights", "Sunset Lamp", "Galaxy Projector", "Desk Lamp", "Neon Sign"],
            "organization": ["Drawer Organizer", "Closet System", "Cable Box", "Shelf Divider", "Storage Bins"],
            "cleaning": ["Robot Vacuum", "Steam Mop", "Pressure Washer", "Cordless Vacuum", "UV Sanitizer"],
            
            # Kitchen & Dining
            "kitchen": ["Knife Set", "Food Container", "Vegetable Chopper", "Spice Rack", "Pan Set"],
            "coffee_tea": ["Pour Over Set", "Electric Kettle", "Coffee Grinder", "Espresso Cups", "Tea Infuser"],
            "barware": ["Cocktail Shaker", "Ice Mold", "Wine Opener", "Whiskey Glasses", "Bar Tools Set"],
            
            # Health & Wellness
            "fitness": ["Resistance Bands", "Yoga Mat", "Jump Rope", "Ab Roller", "Foam Roller"],
            "wellness": ["Massage Gun", "Posture Corrector", "Acupressure Mat", "Meditation Cushion", "Diffuser"],
            "health": ["Pulse Oximeter", "Blood Pressure Monitor", "Smart Scale", "Thermometer", "First Aid Kit"],
            
            # Beauty & Personal Care
            "beauty": ["Makeup Brush Set", "Face Roller", "Hair Dryer", "Nail Kit", "Skincare Set"],
            "skincare": ["LED Face Mask", "Facial Steamer", "Gua Sha Set", "Ice Roller", "Dermaplaner"],
            "haircare": ["Hair Straightener", "Curling Wand", "Scalp Massager", "Hair Clips", "Silk Scrunchies"],
            "grooming": ["Electric Shaver", "Beard Trimmer", "Nose Trimmer", "Manicure Set", "Grooming Kit"],
            
            # Tech & Electronics
            "tech": ["Phone Stand", "USB Hub", "Webcam", "Mouse Pad", "Cable Organizer"],
            "phone_accessories": ["MagSafe Charger", "Phone Grip", "Screen Protector", "Phone Case", "Car Mount"],
            "audio": ["Wireless Earbuds", "Bluetooth Speaker", "Headphones", "Microphone", "Soundbar"],
            "computer": ["Mechanical Keyboard", "Ergonomic Mouse", "Monitor Light", "Laptop Stand", "Docking Station"],
            "gaming": ["Gaming Headset", "RGB Mousepad", "Controller Stand", "Gaming Chair", "Capture Card"],
            "camera": ["Ring Light", "Tripod", "Phone Gimbal", "Lens Kit", "Camera Bag"],
            
            # Outdoor & Travel
            "outdoor": ["Camping Lantern", "Hiking Backpack", "Survival Kit", "Portable Grill", "Hammock"],
            "travel": ["Packing Cubes", "Travel Pillow", "Luggage Scale", "Passport Holder", "Compression Bags"],
            "automotive": ["Car Vacuum", "Phone Mount", "Dash Cam", "Seat Organizer", "Jump Starter"],
            "cycling": ["Bike Light", "Phone Mount", "Bike Lock", "Cycling Gloves", "Water Bottle Cage"],
            
            # Pets
            "pet": ["Dog Toy", "Cat Tree", "Pet Brush", "Pet Bowl", "Pet Bed"],
            "dog": ["Dog Harness", "Training Clicker", "Chew Toys", "Dog Crate", "Poop Bag Holder"],
            "cat": ["Cat Scratching Post", "Interactive Toy", "Cat Fountain", "Litter Mat", "Cat Tunnel"],
            
            # Family & Kids
            "baby": ["Baby Monitor", "Bottle Warmer", "Diaper Bag", "Baby Carrier", "Sound Machine"],
            "kids": ["STEM Toys", "Art Supplies", "Building Blocks", "Educational Games", "Night Light"],
            "parenting": ["Baby Gate", "Outlet Covers", "Cabinet Locks", "Corner Guards", "Monitor Camera"],
            
            # Office & Work
            "office": ["Desk Organizer", "Monitor Stand", "Desk Mat", "Pen Holder", "Filing System"],
            "desk_setup": ["Standing Desk Mat", "Cable Tray", "Desk Shelf", "Monitor Arm", "Keyboard Tray"],
            "stationery": ["Planner", "Notebook Set", "Pen Collection", "Sticky Notes", "Desk Calendar"],
            
            # Fashion & Accessories
            "fashion_accessories": ["Sunglasses", "Belt", "Scarf", "Hat", "Wallet"],
            "jewelry": ["Layered Necklace", "Stacking Rings", "Hoop Earrings", "Bracelet Set", "Pendant"],
            "watches": ["Watch Band", "Watch Case", "Watch Stand", "Smart Watch Charger", "Watch Tools"],
            
            # Hobbies & Crafts
            "crafts": ["Embroidery Kit", "Candle Making", "Resin Art", "Knitting Set", "Paint By Numbers"],
            "garden": ["Plant Pots", "Garden Tools", "Watering Can", "Seed Starter", "Grow Lights"],
            "music": ["Guitar Picks", "Capo", "Tuner", "Music Stand", "Instrument Cable"],
            
            # Special Categories
            "gifts": ["Gift Box Set", "Personalized Item", "Subscription Box", "Novelty Gift", "Luxury Set"],
            "seasonal": ["Holiday Decor", "Seasonal Lights", "Party Supplies", "Themed Items", "Limited Edition"],
            "eco_friendly": ["Reusable Bags", "Bamboo Products", "Solar Charger", "Beeswax Wraps", "Metal Straws"],
            "luxury": ["Premium Leather", "Designer Case", "Gold Accented", "Crystal Set", "Silk Items"],
            
            # Trending
            "tiktok_viral": ["Viral Gadget", "TikTok Famous", "Trending Item", "Must Have", "Influencer Pick"],
            "amazon_finds": ["Hidden Gem", "Best Seller", "Top Rated", "Editors Choice", "Most Wished"]
        }

        niche_titles = titles.get(niche, titles.get("tech", ["Generic Product"]))

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
        """Validate products with Google Trends using Advanced Scraper (bypasses rate limits)"""
        if not self.advanced_scraper:
            logger.warning("   Trends validation skipped: Advanced Scraper not available")
            for product in products:
                product['trend_score'] = 50  # Default neutral
            return products

        try:
            # Get trend score for the niche
            search_terms = self.NICHE_SEARCH_TERMS.get(niche, [niche])[:3]
            keyword = search_terms[0] if search_terms else niche

            # Use Advanced Scraper (Playwright-based, bypasses 429 errors)
            result = await self.advanced_scraper.scrape_google_trends(
                keyword=keyword,
                timeframe='today 3-m'
            )

            if result.get('success') and result.get('trend_values'):
                # Calculate average trend score
                trend_values = result['trend_values']
                avg_trend = sum(trend_values) / len(trend_values)
                trend_momentum = min(avg_trend, 100)

                # Apply trend score to all products
                for product in products:
                    product['trend_score'] = round(trend_momentum, 1)
                    if 'data_sources' not in product:
                        product['data_sources'] = {}
                    product['data_sources']['google_trends'] = {
                        'available': True,
                        'trend_score': round(trend_momentum, 1),
                        'velocity_score': result.get('velocity_score', 50)
                    }

                logger.info(f"   Google Trends: {trend_momentum:.1f} average interest")
            else:
                logger.warning("   Trends validation: No data returned")
                for product in products:
                    product['trend_score'] = 50  # Default neutral

        except Exception as e:
            logger.warning(f"   Trends validation skipped: {e}")
            for product in products:
                product['trend_score'] = 50  # Default neutral

        return products

    def _calculate_final_scores(self, products: List[Dict]) -> List[Dict]:
        """
        Calculate OPPORTUNITY scores for all products.
        
        Uses OpportunityScorer (Anti-AutoDS Algorithm) when available:
        - Demand Score: velocity + volume + momentum
        - Competition Score: sellers + ads + timing + internal saturation
        - Opportunity Score: Demand × (1 - Competition × 0.7)
        
        Falls back to basic scoring if OpportunityScorer unavailable.
        """
        
        # Try to use OpportunityScorer for full anti-saturation analysis
        if self.opportunity_scorer:
            logger.info("   🎯 Using OpportunityScorer (Anti-AutoDS Algorithm)")
            return self._score_with_opportunity_scorer(products)
        else:
            logger.info("   📊 Using basic scoring (OpportunityScorer unavailable)")
            return self._score_basic(products)
    
    def _score_with_opportunity_scorer(self, products: List[Dict]) -> List[Dict]:
        """
        Score products using the OpportunityScorer (Anti-AutoDS Algorithm).
        
        This considers:
        - Demand velocity (is interest growing?)
        - Competition saturation (how many sellers?)
        - Timing (early to trend or late?)
        - Internal saturation (how many Ospra users have this?)
        """
        scored_products = []
        
        for product in products:
            try:
                # Build data for OpportunityScorer
                product_name = product.get('title', 'Unknown Product')
                niche = product.get('niche', 'general')
                cost_price = product.get('price', 0) * 0.4  # Estimate cost as 40% of retail
                
                # Gather metrics from product data
                demand_data = {
                    'google_trends': {
                        'current_interest': product.get('trend_score', 50),
                        'growth_percent': product.get('trend_score', 50) - 50  # Estimate growth
                    },
                    'tiktok': {
                        'views': product.get('views', 0),
                        'likes': product.get('likes', 0),
                        'engagement_rate': self._calc_engagement_rate(product)
                    },
                    'amazon': {
                        'bsr': product.get('bestseller_rank', 9999),
                        'reviews': product.get('reviews_count', 0)
                    }
                }
                
                competition_data = {
                    'amazon_sellers': product.get('amazon_sellers', 50),  # Default estimate
                    'shopify_stores': product.get('shopify_stores', 100),  # Default estimate
                    'facebook_ads': product.get('facebook_ads', 100),  # Default estimate
                    'days_trending': product.get('days_trending', 30)  # Default estimate
                }
                
                # Get opportunity score
                try:
                    opportunity_result = self.opportunity_scorer.score_product(
                        product_name=product_name,
                        niche=niche,
                        demand_data=demand_data,
                        competition_data=competition_data,
                        cost_price=cost_price
                    )
                    
                    # Apply results to product
                    product['opportunity_score'] = opportunity_result.opportunity_score
                    product['demand_score'] = opportunity_result.demand_score
                    product['competition_score'] = opportunity_result.competition_score
                    product['final_score'] = opportunity_result.opportunity_score  # Main score
                    product['tier'] = opportunity_result.tier.value if hasattr(opportunity_result.tier, 'value') else str(opportunity_result.tier)
                    product['recommendation'] = opportunity_result.recommendation
                    product['reasons'] = opportunity_result.reasons
                    product['risks'] = opportunity_result.risks
                    product['suggested_price'] = opportunity_result.suggested_price
                    product['estimated_monthly_volume'] = opportunity_result.estimated_monthly_volume
                    product['estimated_profit'] = opportunity_result.estimated_profit
                    
                    logger.info(f"   🎯 {product_name[:30]}... → {opportunity_result.opportunity_score:.0f} (D:{opportunity_result.demand_score:.0f}/C:{opportunity_result.competition_score:.0f}) [{product['tier']}]")
                    
                except Exception as e:
                    logger.warning(f"   OpportunityScorer failed for {product_name[:30]}: {e}")
                    # Fall back to basic scoring for this product
                    product = self._score_single_basic(product)
                    
            except Exception as e:
                logger.error(f"   Scoring error: {e}")
                product = self._score_single_basic(product)
            
            scored_products.append(product)
        
        return scored_products
    
    def _calc_engagement_rate(self, product: Dict) -> float:
        """Calculate engagement rate from views/likes/shares"""
        views = product.get('views', 0)
        likes = product.get('likes', 0)
        shares = product.get('shares', 0)
        comments = product.get('comments_count', 0)
        
        if views == 0:
            return 0.0
        
        engagements = likes + shares + comments
        return min((engagements / views) * 100, 20)  # Cap at 20%
    
    def _score_basic(self, products: List[Dict]) -> List[Dict]:
        """Basic scoring (fallback when OpportunityScorer unavailable)"""
        for product in products:
            product = self._score_single_basic(product)
        return products
    
    def _score_single_basic(self, product: Dict) -> Dict:
        """Basic scoring for a single product"""
        source = product.get('source', 'unknown')

        # Base scores based on source
        if source == 'tiktok_shop':
            viral = product.get('viral_score', 0)
            views = product.get('views', 0)
            engagement_bonus = min(views / 100000, 20)
            base_score = viral + engagement_bonus

        elif source == 'amazon_bestsellers':
            demand = product.get('demand_score', 0)
            rating = product.get('rating', 0) * 10
            bestseller_bonus = 20 if product.get('is_bestseller') else 0
            base_score = demand + rating + bestseller_bonus

        elif source == 'aliexpress':
            commission = product.get('commission_rate', 0) * 5
            sales = min(product.get('sales_volume', 0) * 2, 30)
            price = product.get('price', 0)
            price_bonus = 20 if 10 <= price <= 50 else 10
            base_score = commission + sales + price_bonus

        else:
            base_score = product.get('viral_score', 0) or product.get('demand_score', 50)

        # Add trend bonus
        trend_score = product.get('trend_score', 50)
        trend_bonus = trend_score * 0.3

        # Calculate final score
        final_score = min(base_score + trend_bonus, 100)
        product['final_score'] = round(final_score, 1)
        product['opportunity_score'] = round(final_score, 1)  # Alias
        product['velocity_score'] = round(final_score, 1)  # Legacy alias

        # Assign tier
        if final_score >= 85:
            product['tier'] = 'GOLDEN'
        elif final_score >= 70:
            product['tier'] = 'EXCELLENT'
        elif final_score >= 55:
            product['tier'] = 'GOOD'
        elif final_score >= 40:
            product['tier'] = 'FAIR'
        elif final_score >= 25:
            product['tier'] = 'POOR'
        else:
            product['tier'] = 'AVOID'
        
        # Basic recommendation
        product['recommendation'] = self._get_basic_recommendation(product['tier'])
        product['reasons'] = []
        product['risks'] = []

        logger.info(f"   📊 {product['title'][:35]}... → {final_score:.0f} ({product['tier']})")
        
        return product
    
    def _get_basic_recommendation(self, tier: str) -> str:
        """Get basic recommendation text based on tier"""
        recommendations = {
            'GOLDEN': '🔥 ACT NOW: Rare opportunity',
            'EXCELLENT': '✅ STRONG BUY: Proceed with deployment',
            'GOOD': '👍 CONSIDER: Test with limited inventory',
            'FAIR': '⚠️ CAUTION: Only with strong differentiation',
            'POOR': '🚫 SKIP: Risk outweighs reward',
            'AVOID': '❌ AVOID: Does not meet criteria'
        }
        return recommendations.get(tier, '❓ Unknown tier')


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


def get_available_niches() -> Dict[str, List[str]]:
    """
    Get all available niches organized by category.
    
    Returns:
        Dict with category names as keys and list of niche slugs as values
    """
    return {
        "home_living": ["smart_home", "home_decor", "lighting", "organization", "cleaning"],
        "kitchen_dining": ["kitchen", "coffee_tea", "barware"],
        "health_wellness": ["fitness", "wellness", "health"],
        "beauty_care": ["beauty", "skincare", "haircare", "grooming"],
        "tech_electronics": ["tech", "phone_accessories", "audio", "computer", "gaming", "camera"],
        "outdoor_travel": ["outdoor", "travel", "automotive", "cycling"],
        "pets": ["pet", "dog", "cat"],
        "family_kids": ["baby", "kids", "parenting"],
        "office_work": ["office", "desk_setup", "stationery"],
        "fashion": ["fashion_accessories", "jewelry", "watches"],
        "hobbies": ["crafts", "garden", "music"],
        "special": ["gifts", "seasonal", "eco_friendly", "luxury"],
        "trending": ["tiktok_viral", "amazon_finds"]
    }


def get_all_niche_slugs() -> List[str]:
    """
    Get flat list of all available niche slugs.
    
    Returns:
        List of all niche slug strings
    """
    all_niches = []
    for category_niches in get_available_niches().values():
        all_niches.extend(category_niches)
    return all_niches


async def discover_all_niches(products_per_niche: int = 5, niches: List[str] = None) -> Dict[str, List[Dict]]:
    """
    Discover products across multiple niches.
    
    Args:
        products_per_niche: Number of products to fetch per niche
        niches: Optional list of specific niches. Defaults to popular ones.

    Returns:
        Dict mapping niche to list of products
    """
    engine = get_discovery_engine()
    
    # Default to popular niches if not specified
    if niches is None:
        niches = ["smart_home", "fitness", "kitchen", "beauty", "tech", 
                  "gaming", "phone_accessories", "tiktok_viral"]

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
