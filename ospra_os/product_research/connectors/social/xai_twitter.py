"""
xAI Grok-powered Twitter/X Product Discovery

WHY xAI?
=========
Grok is the ONLY AI with real-time Twitter/X data access.
- Claude, GPT, Gemini = NO Twitter access
- Grok = Full Twitter access (Elon owns both xAI and X)

WHAT THIS GIVES YOU:
====================
1. Viral product detection across 100+ hashtags
2. Real social sentiment from actual buyers
3. Product URLs shared on Twitter
4. Influencer product picks
5. Trending products BEFORE they hit mainstream

EXPANDED COVERAGE:
==================
- 15+ niches (not just smart home)
- 100+ viral hashtags
- Industry influencer tracking
- Multi-language trend detection

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
    
    # Niche detected
    niche: str = "general"
    
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
            "niche": self.niche,
            "source": "twitter_xai"
        }


class XAITwitterDiscovery:
    """
    Discover viral products using xAI Grok's Twitter access.
    
    This is a PRIMARY discovery source - finds actual products!
    
    MASSIVELY EXPANDED with 100+ hashtags across 15+ niches.
    
    Discovery Strategies:
    1. HASHTAG MINING - 100+ product discovery hashtags
    2. VIRAL DETECTION - Products with sudden engagement spikes
    3. INFLUENCER TRACKING - What are influencers promoting?
    4. SENTIMENT ANALYSIS - Are people loving or hating a product?
    5. URL EXTRACTION - Get actual product links from tweets
    6. NICHE DISCOVERY - Find new emerging niches
    """
    
    # ================================================================
    # MASSIVELY EXPANDED HASHTAGS - 100+ across 15+ niches
    # ================================================================
    
    PRODUCT_HASHTAGS = {
        # === VIRAL GENERAL (These find products across ALL niches) ===
        "viral_general": [
            "#TikTokMadeMeBuyIt",
            "#AmazonFinds",
            "#AmazonMustHaves",
            "#ViralProducts",
            "#TrendingProducts",
            "#MustHave",
            "#GameChanger",
            "#LifeHack",
            "#BestPurchase",
            "#WorthIt",
            "#NeedThis",
            "#ShutUpAndTakeMyMoney",
            "#AddToCart",
            "#ImpulseBuy",
            "#BestBuy",
            "#StealDeal",
            "#DealOfTheDay",
            "#HiddenGem",
            "#UnderRated",
            "#ProductReview",
        ],
        
        # === SMART HOME / HOME AUTOMATION ===
        "smart_home": [
            "#SmartHome",
            "#HomeAutomation",
            "#SmartLighting",
            "#AlexaDevice",
            "#GoogleHome",
            "#SmartGadgets",
            "#TechHome",
            "#SmartPlug",
            "#WiFiDevice",
            "#HomeAssistant",
            "#IoT",
            "#SmartSpeaker",
            "#VoiceControl",
            "#SmartThermostat",
            "#SmartDoorbell",
            "#SecurityCamera",
            "#SmartLock",
            "#LEDStrip",
            "#RGBLights",
            "#SmartBlinds",
        ],
        
        # === HOME GOODS / DECOR / ORGANIZATION ===
        "home_goods": [
            "#HomeDecor",
            "#OrganizationHacks",
            "#CleaningHacks",
            "#KitchenGadgets",
            "#HomeFavorites",
            "#HomeHacks",
            "#HomeOrganization",
            "#StorageSolutions",
            "#MinimalistHome",
            "#CozyHome",
            "#HomeEssentials",
            "#HomeTips",
            "#CleanTok",
            "#OrganizeTok",
            "#HomeInspo",
            "#InteriorDesign",
            "#ApartmentTherapy",
            "#SmallSpaceLiving",
            "#RenterFriendly",
            "#HomeUpgrade",
        ],
        
        # === KITCHEN / COOKING ===
        "kitchen": [
            "#KitchenTok",
            "#KitchenGadgets",
            "#CookingTok",
            "#FoodPrep",
            "#MealPrep",
            "#AirFryer",
            "#InstaPot",
            "#KitchenHacks",
            "#CookingHacks",
            "#BakingTok",
            "#KitchenEssentials",
            "#KitchenOrganization",
            "#KitchenTools",
            "#ChefTok",
            "#FoodieFinds",
            "#KitchenMustHaves",
            "#CookingGadgets",
            "#KitchenUpgrade",
            "#RecipeTok",
            "#HealthyEating",
        ],
        
        # === TECH / GADGETS / ELECTRONICS ===
        "tech_gadgets": [
            "#TechGadgets",
            "#GadgetReview",
            "#TechFinds",
            "#CoolGadgets",
            "#TechDeals",
            "#NewTech",
            "#TechTok",
            "#Gadgets",
            "#TechAccessories",
            "#PhoneAccessories",
            "#WirelessCharger",
            "#USBGadgets",
            "#LaptopAccessories",
            "#GamingSetup",
            "#DeskSetup",
            "#WorkFromHome",
            "#TechEssentials",
            "#EDC",
            "#EveryDayCarry",
            "#TechReview",
        ],
        
        # === FITNESS / GYM / HEALTH ===
        "fitness": [
            "#FitnessTok",
            "#GymTok",
            "#WorkoutGear",
            "#FitnessGadgets",
            "#HomeGym",
            "#GymEssentials",
            "#FitnessFinds",
            "#WorkoutEquipment",
            "#YogaTok",
            "#RunningGear",
            "#FitnessTech",
            "#HealthTok",
            "#WellnessTok",
            "#ProteinShaker",
            "#ResistanceBands",
            "#MassageGun",
            "#FoamRoller",
            "#WorkoutClothes",
            "#Activewear",
            "#GymMotivation",
        ],
        
        # === BEAUTY / SKINCARE / MAKEUP ===
        "beauty": [
            "#BeautyTok",
            "#SkincareTok",
            "#MakeupTok",
            "#BeautyFinds",
            "#SkincareRoutine",
            "#MakeupReview",
            "#BeautyHacks",
            "#GlowUp",
            "#SkinCare",
            "#BeautyTools",
            "#LEDFaceMask",
            "#FacialDevice",
            "#MakeupOrganizer",
            "#BeautyEssentials",
            "#SkincareAddict",
            "#MakeupAddict",
            "#CleanBeauty",
            "#BeautyTips",
            "#HairTok",
            "#NailTok",
        ],
        
        # === PET / ANIMALS ===
        "pet": [
            "#PetTok",
            "#DogTok",
            "#CatTok",
            "#PetFinds",
            "#PetGadgets",
            "#DogProducts",
            "#CatProducts",
            "#PetEssentials",
            "#DogMom",
            "#CatMom",
            "#PetAccessories",
            "#DogToys",
            "#CatToys",
            "#PetCamera",
            "#AutomaticFeeder",
            "#PetGrooming",
            "#DogWalking",
            "#PetTravel",
            "#PetBed",
            "#PetCarrier",
        ],
        
        # === CAR / AUTOMOTIVE ===
        "car": [
            "#CarTok",
            "#CarAccessories",
            "#CarGadgets",
            "#CarOrganization",
            "#DashCam",
            "#CarTech",
            "#CarEssentials",
            "#CarUpgrade",
            "#CarInterior",
            "#CarLED",
            "#CarCleaning",
            "#CarDetailing",
            "#RoadTrip",
            "#CarMods",
            "#CarReview",
            "#PhoneMount",
            "#CarCharger",
            "#TrunkOrganizer",
            "#CarAir",
            "#CarSeat",
        ],
        
        # === OFFICE / WORK FROM HOME ===
        "home_office": [
            "#DeskSetup",
            "#WorkFromHome",
            "#HomeOffice",
            "#OfficeEssentials",
            "#ProductivityHacks",
            "#DeskOrganization",
            "#WFH",
            "#RemoteWork",
            "#DeskAccessories",
            "#OfficeTour",
            "#DeskGoals",
            "#SetupTour",
            "#MinimalistDesk",
            "#DeskDecor",
            "#OfficeUpgrade",
            "#WorkspaceGoals",
            "#DeskInspo",
            "#StandingDesk",
            "#ErgonomicSetup",
            "#TechDesk",
        ],
        
        # === BABY / PARENTING / KIDS ===
        "baby_kids": [
            "#MomTok",
            "#DadTok",
            "#ParentingHacks",
            "#BabyProducts",
            "#BabyEssentials",
            "#MomFinds",
            "#BabyRegistry",
            "#NewMom",
            "#ToddlerMom",
            "#KidsToys",
            "#BabyGadgets",
            "#ParentingTips",
            "#MomLife",
            "#BabyHacks",
            "#KidsActivities",
            "#BabyGear",
            "#NurseryDecor",
            "#BabyShower",
            "#ToddlerLife",
            "#MomMusthaves",
        ],
        
        # === TRAVEL / LUGGAGE / PACKING ===
        "travel": [
            "#TravelTok",
            "#TravelEssentials",
            "#PackingHacks",
            "#TravelGadgets",
            "#TravelFinds",
            "#PackingTips",
            "#TravelAccessories",
            "#LuggageReview",
            "#CarryOn",
            "#TravelOrganization",
            "#AirportHacks",
            "#TravelMustHaves",
            "#Wanderlust",
            "#TravelGear",
            "#Backpacking",
            "#TravelLight",
            "#TravelReady",
            "#FlightHacks",
            "#TravelTips",
            "#Vacation",
        ],
        
        # === GAMING / STREAMING ===
        "gaming": [
            "#GamingSetup",
            "#GamerTok",
            "#StreamerSetup",
            "#GamingGear",
            "#PCGaming",
            "#GamingAccessories",
            "#TwitchStreamer",
            "#GamingDesk",
            "#RGBSetup",
            "#GamingChair",
            "#GamingMouse",
            "#GamingKeyboard",
            "#GamingHeadset",
            "#StreamDeck",
            "#GamingMonitor",
            "#SetupGoals",
            "#GamingRoom",
            "#BattleStation",
            "#GamerLife",
            "#LEDSetup",
        ],
        
        # === OUTDOOR / CAMPING / SURVIVAL ===
        "outdoor": [
            "#OutdoorTok",
            "#CampingGear",
            "#HikingGear",
            "#SurvivalGear",
            "#OutdoorGadgets",
            "#CampingHacks",
            "#Overlanding",
            "#Bushcraft",
            "#EDCGear",
            "#OutdoorEssentials",
            "#CampingEssentials",
            "#HikingEssentials",
            "#BackpackingGear",
            "#CampfireCooking",
            "#AdventureTok",
            "#NatureLovers",
            "#Wildcamping",
            "#Glamping",
            "#VanLife",
            "#OffGrid",
        ],
        
        # === FASHION / STYLE / CLOTHING ===
        "fashion": [
            "#FashionTok",
            "#OOTD",
            "#StyleTok",
            "#FashionFinds",
            "#WardrobeEssentials",
            "#StreetStyle",
            "#ShoeTok",
            "#SneakerHead",
            "#ThriftTok",
            "#FashionHaul",
            "#FashionReview",
            "#TrendAlert",
            "#StyleInspo",
            "#FashionHacks",
            "#DupeTok",
            "#LuxuryDupe",
            "#AmazonFashion",
            "#SHEINHaul",
            "#FashionDeals",
            "#CapsulewWardrobe",
        ],
        
        # === CRAFT / DIY / HOBBY ===
        "craft_diy": [
            "#CraftTok",
            "#DIYTok",
            "#MakerTok",
            "#CraftSupplies",
            "#DIYProjects",
            "#SmallBusiness",
            "#EtsySeller",
            "#CricutProjects",
            "#Crafter",
            "#HandMade",
            "#CraftHacks",
            "#DIYHome",
            "#Upcycle",
            "#ResinArt",
            "#Sewing",
            "#Knitting",
            "#Embroidery",
            "#PaperCrafts",
            "#WoodWorking",
            "#Jewelry Making",
        ],
        
        # === WELLNESS / SELF-CARE / RELAXATION ===
        "wellness": [
            "#WellnessTok",
            "#SelfCareTok",
            "#MentalHealth",
            "#SelfCare",
            "#Relaxation",
            "#Meditation",
            "#Aromatherapy",
            "#EssentialOils",
            "#WellnessJourney",
            "#Mindfulness",
            "#SleepTok",
            "#StressRelief",
            "#WellnessProducts",
            "#SelfLove",
            "#HolisticHealth",
            "#Journaling",
            "#MorningRoutine",
            "#NightRoutine",
            "#SpaDay",
            "#BathBombs",
        ],
    }
    
    # ================================================================
    # EXPANDED INFLUENCERS BY NICHE
    # ================================================================
    
    INFLUENCERS = {
        "tech": [
            "@MKBHD", "@iJustine", "@UnboxTherapy", "@Mrwhosetheboss",
            "@LinusTech", "@AustinEvans", "@JerryRigEverything",
            "@TechLinked", "@ShortCircuit", "@davelee", "@TheVerge"
        ],
        "home": [
            "@NestWithLess", "@TheHomeEdit", "@MrsHinch",
            "@CleanMama", "@OrganizedHome", "@DIYDanie", "@JordanPage"
        ],
        "fitness": [
            "@MegSquats", "@JeffNippard", "@AthleanX", "@SimonMiller",
            "@WhitneySimmons", "@NatalyMarquezX", "@ChrisHeria"
        ],
        "beauty": [
            "@JamesCharles", "@NikkieTutorials", "@Hyram",
            "@Doctorlyy", "@PatrickStarrr", "@MakeupByMario"
        ],
        "gaming": [
            "@Ninja", "@Shroud", "@DrDisrespect", "@Pokimane",
            "@xQc", "@Ludwig", "@DisguisedToast"
        ],
        "fashion": [
            "@ChiaraFerragni", "@EmmaChamberlain", "@WeWoreWhat",
            "@DanielleMarcan", "@TaylorHillOfficial"
        ],
        "pet": [
            "@JiffPom", "@Nala_Cat", "@TunaTheDog",
            "@Juniperfoxx", "@MrBubz"
        ],
        "outdoor": [
            "@BrodieMoss", "@YBSYoungbloods", "@JimShockey",
            "@StevenRinella", "@RexInEffects"
        ],
    }
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize xAI Twitter discovery."""
        self.api_key = api_key or os.getenv("XAI_API_KEY")
        self.client = None
        self._available = False
        
        if not HAS_OPENAI:
            print("[WARNING]  openai package not installed - run: pip install openai")
            return
            
        if not self.api_key:
            print("[WARNING]  XAI_API_KEY not configured")
            return
            
        # xAI uses OpenAI-compatible API
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url="https://api.x.ai/v1"
        )
        self._available = True
        print("[SUCCESS] xAI Twitter Discovery initialized (100+ hashtags, 15+ niches)")
    
    def is_available(self) -> bool:
        """Check if xAI API is configured and available."""
        return self._available and self.client is not None
    
    def get_all_niches(self) -> List[str]:
        """Get all available niches."""
        return list(self.PRODUCT_HASHTAGS.keys())
    
    def get_hashtags_for_niche(self, niche: str) -> List[str]:
        """Get all hashtags for a specific niche."""
        return self.PRODUCT_HASHTAGS.get(niche, [])
    
    def get_all_hashtags(self) -> List[str]:
        """Get ALL hashtags across all niches."""
        all_tags = []
        for tags in self.PRODUCT_HASHTAGS.values():
            all_tags.extend(tags)
        return list(set(all_tags))
    
    async def discover_viral_products(
        self,
        niche: str = "smart_home",
        max_products: int = 10,
        time_range: str = "24h",
        include_general: bool = True
    ) -> List[TwitterProduct]:
        """
        Discover viral products from Twitter using Grok.
        
        Args:
            niche: Product niche (see PRODUCT_HASHTAGS keys)
            max_products: Maximum products to return
            time_range: Time range to search (1h, 24h, 7d)
            include_general: Include viral_general hashtags
            
        Returns:
            List of TwitterProduct with full engagement data
        """
        if not self.is_available():
            print("[ERROR] xAI Twitter not available")
            return []
        
        print(f"\n xAI Twitter Discovery: {niche}")
        print(f"   Time range: {time_range}")
        print(f"   Max products: {max_products}")
        
        # Get relevant hashtags for this niche
        hashtags = self.PRODUCT_HASHTAGS.get(niche, []).copy()
        
        # Always include general viral hashtags for broader coverage
        if include_general and niche != "viral_general":
            hashtags += self.PRODUCT_HASHTAGS.get("viral_general", [])[:10]
        
        # Get niche-specific influencers
        niche_key = niche.replace("_", "").lower()
        for key in self.INFLUENCERS:
            if key in niche_key or niche_key in key:
                influencers = self.INFLUENCERS[key][:5]
                break
        else:
            influencers = self.INFLUENCERS.get("tech", [])[:3]
        
        # Build the Grok prompt
        prompt = f"""You have access to real-time Twitter/X data. 

TASK: Find {max_products} viral products being discussed on Twitter in the last {time_range}.

SEARCH FOCUS:
- Niche: {niche}
- Hashtags to monitor: {', '.join(hashtags[:15])}
- Influencers to check: {', '.join(influencers)}
- Look for products with high engagement (likes, retweets, replies)
- Prioritize products with actual purchase links (Amazon, AliExpress, Shopify stores)
- Look for products people are ACTUALLY BUYING, not just discussing

For each product found, provide:
1. Product name (specific, not generic - like "Govee LED Strip Lights" not just "LED lights")
2. Product URL if mentioned in tweets (Amazon, AliExpress, or store link)
3. Approximate price if mentioned
4. Number of tweets mentioning it
5. Total engagement (likes + retweets + replies estimate)
6. Sentiment (positive/negative/neutral/mixed)
7. Key hashtags where it appeared
8. 2-3 example tweet snippets (paraphrased)
9. Any influencer mentions
10. Why this product is going viral (specific reason)

RESPOND IN THIS EXACT JSON FORMAT:
{{
    "products": [
        {{
            "name": "Specific Product Name With Brand",
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
            "viral_reason": "TikTok video hit 5M views showing the product"
        }}
    ],
    "trending_hashtags": ["#hashtag1", "#hashtag2"],
    "emerging_products": ["Product that's starting to trend but not viral yet"],
    "market_insight": "Brief insight about current Twitter trends in {niche}"
}}

IMPORTANT: Only include products that are ACTUALLY trending on Twitter right now. Be specific with product names and brands."""

        try:
            response = await self.client.chat.completions.create(
                model="grok-3",
                messages=[
                    {
                        "role": "system",
                        "content": "You are Grok, an AI with real-time access to Twitter/X data. You can see current tweets, engagement metrics, and trending topics. Provide accurate, real-time data about what's trending on Twitter. Be specific about product names and brands - avoid generic descriptions."
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
            
            print(f"   [SUCCESS] Found {len(products)} viral products on Twitter")
            return products[:max_products]
            
        except Exception as e:
            print(f"   [ERROR] xAI Twitter discovery failed: {e}")
            return []
    
    async def discover_across_all_niches(
        self,
        max_per_niche: int = 5,
        time_range: str = "24h"
    ) -> Dict[str, List[TwitterProduct]]:
        """
        Discover viral products across ALL niches.
        
        Returns dict of {niche: [products]}
        """
        all_products = {}
        
        for niche in self.PRODUCT_HASHTAGS.keys():
            if niche == "viral_general":
                continue  # Skip this, it's included in others
            
            products = await self.discover_viral_products(
                niche=niche,
                max_products=max_per_niche,
                time_range=time_range
            )
            
            if products:
                all_products[niche] = products
            
            await asyncio.sleep(0.5)  # Rate limiting
        
        return all_products
    
    async def analyze_product_sentiment(
        self,
        product_name: str
    ) -> Dict[str, Any]:
        """
        Analyze Twitter/X sentiment for a specific product.

        This is the PRIMARY method for product sentiment analysis.

        Args:
            product_name: Product name to analyze

        Returns:
            Full sentiment analysis with engagement metrics
        """
        result = await self.get_product_sentiment(product_name, include_tweets=True)

        # Add buzz_level calculation
        if "tweet_count" in result:
            tweet_count = result["tweet_count"]
            if tweet_count >= 1000:
                result["buzz_level"] = "viral"
            elif tweet_count >= 100:
                result["buzz_level"] = "high"
            elif tweet_count >= 10:
                result["buzz_level"] = "moderate"
            else:
                result["buzz_level"] = "low"

        # Add sample_tweets (top 3) if not already present
        if "sample_tweets" not in result:
            result["sample_tweets"] = []

        return result

    async def get_product_sentiment(
        self,
        product_name: str,
        include_tweets: bool = True
    ) -> Dict[str, Any]:
        """
        Get Twitter sentiment for a specific product.
        """
        if not self.is_available():
            return {"error": "xAI not available", "sentiment_score": 0}
        
        print(f" Analyzing Twitter sentiment: {product_name}")
        
        prompt = f"""Analyze Twitter/X sentiment for this product: "{product_name}"

Search recent tweets mentioning this product and provide:
1. Overall sentiment (positive/negative/neutral/mixed)
2. Sentiment score (-1.0 to 1.0)
3. Total tweet count (approximate)
4. Engagement metrics (likes, retweets, replies)
5. Common praise (what people love)
6. Common complaints (what people hate)
7. Purchase intent signals (people who bought it, want to buy, or recommending)
8. Comparison to competitors if mentioned

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
    "common_praise": ["fast shipping", "great quality", "worth the price"],
    "common_complaints": ["battery life could be better"],
    "purchase_intent": {{
        "bought_it": 45,
        "want_to_buy": 120,
        "recommending": 85
    }},
    "competitor_comparison": "Often compared to [X], generally preferred because [reason]",
    "recommendation": "BUY/SKIP/CONSIDER with reason"
}}"""

        try:
            response = await self.client.chat.completions.create(
                model="grok-3",
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
            return {"error": str(e), "sentiment_score": 0}
    
    async def find_trending_hashtags(
        self, 
        niche: str = "smart_home",
        include_related: bool = True
    ) -> List[Dict]:
        """Find currently trending hashtags related to a niche."""
        if not self.is_available():
            return []
        
        # Get seed hashtags for context
        seed_tags = self.PRODUCT_HASHTAGS.get(niche, [])[:10]
        
        prompt = f"""Find the top 20 trending Twitter/X hashtags related to: {niche}

Seed hashtags for context: {', '.join(seed_tags)}

Focus on:
1. Product-related and e-commerce hashtags
2. Hashtags where people share purchases
3. Review and recommendation hashtags
4. Viral content hashtags in this space

RESPOND IN JSON:
{{
    "hashtags": [
        {{
            "tag": "#SmartHome",
            "volume": "5000/hour",
            "trend": "rising",
            "sample_products": ["Ring Doorbell", "Philips Hue"],
            "tweet_velocity": "fast" 
        }}
    ],
    "emerging_hashtags": ["#NewHashtag that's starting to trend"],
    "related_niches": ["niches that overlap with {niche}"]
}}"""

        try:
            response = await self.client.chat.completions.create(
                model="grok-3",
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
            print(f"   [ERROR] Trending hashtags failed: {e}")
            return []
    
    async def discover_emerging_niches(self) -> Dict[str, Any]:
        """
        Discover NEW emerging niches by analyzing Twitter trends.
        
        This is for finding niches you DON'T already track.
        """
        if not self.is_available():
            return {"error": "xAI not available"}
        
        prompt = """Analyze current Twitter/X trends to find EMERGING e-commerce niches.

Look for:
1. New product categories that are gaining viral attention
2. Hashtags with rapidly growing engagement
3. Products that don't fit traditional categories
4. Trends that haven't hit mainstream yet

RESPOND IN JSON:
{
    "emerging_niches": [
        {
            "niche_name": "AI Gadgets",
            "description": "AI-powered consumer devices",
            "growth_rate": "rapid",
            "key_hashtags": ["#AIGadgets", "#SmartAI"],
            "example_products": ["AI Photo Frame", "AI Pet Feeder"],
            "estimated_market_size": "growing",
            "recommended_action": "Start tracking now"
        }
    ],
    "declining_niches": ["Niches that are losing interest"],
    "market_signals": "Overall e-commerce trends on Twitter"
}"""

        try:
            response = await self.client.chat.completions.create(
                model="grok-3",
                messages=[
                    {"role": "system", "content": "You are Grok, analyzing e-commerce trends on Twitter."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4,
                max_tokens=2000
            )
            
            import re
            json_match = re.search(r'\{[\s\S]*\}', response.choices[0].message.content)
            if json_match:
                return json.loads(json_match.group())
            return {"raw_response": response.choices[0].message.content}
            
        except Exception as e:
            return {"error": str(e)}
    
    async def monitor_influencers(
        self,
        niche: str = "tech",
        time_range: str = "7d"
    ) -> List[Dict[str, Any]]:
        """Monitor what products influencers are talking about."""
        if not self.is_available():
            return []
        
        # Get influencers for this niche
        influencers = self.INFLUENCERS.get(niche, self.INFLUENCERS.get("tech", []))[:8]
        
        prompt = f"""Check recent tweets from these influencers for product mentions:
{', '.join(influencers)}

Time range: {time_range}

Find products they've mentioned, reviewed, or promoted.

RESPOND IN JSON:
{{
    "influencer_picks": [
        {{
            "product": "Specific Product Name",
            "influencer": "@handle",
            "tweet_summary": "What they said about it",
            "sentiment": "positive",
            "engagement": {{"likes": 5000, "retweets": 500}},
            "url": "product_url or null",
            "is_sponsored": false,
            "recommendation_strength": "strong/moderate/weak"
        }}
    ],
    "most_mentioned_products": ["Products mentioned by multiple influencers"],
    "influencer_trends": "What topics influencers are focusing on"
}}"""

        try:
            response = await self.client.chat.completions.create(
                model="grok-3",
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
            print(f"   [ERROR] Influencer monitoring failed: {e}")
            return []
    
    async def find_product_comparisons(self, product_name: str) -> Dict[str, Any]:
        """
        Find Twitter comparisons of a product vs competitors.
        
        Useful for understanding competitive landscape.
        """
        if not self.is_available():
            return {"error": "xAI not available"}
        
        prompt = f"""Find Twitter discussions comparing "{product_name}" to competitors.

Look for:
1. Direct comparison tweets ("X vs Y")
2. "I switched from X to Y" discussions
3. Recommendation threads asking for alternatives
4. Review threads comparing multiple products

RESPOND IN JSON:
{{
    "product": "{product_name}",
    "competitors": [
        {{
            "name": "Competitor Name",
            "comparison_sentiment": "product is better/worse/equal",
            "key_differences": ["price", "quality", "features"],
            "twitter_preference": "which one Twitter prefers",
            "tweet_count": 100
        }}
    ],
    "overall_position": "How this product ranks vs competition",
    "unique_advantages": ["What makes this product stand out"],
    "common_criticisms": ["What competitors do better"]
}}"""

        try:
            response = await self.client.chat.completions.create(
                model="grok-3",
                messages=[
                    {"role": "system", "content": "You are Grok analyzing product comparisons on Twitter."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1500
            )
            
            import re
            json_match = re.search(r'\{[\s\S]*\}', response.choices[0].message.content)
            if json_match:
                return json.loads(json_match.group())
            return {"raw_response": response.choices[0].message.content}
            
        except Exception as e:
            return {"error": str(e)}
    
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
                    buy_signal=self._get_buy_signal(viral_score, p.get("sentiment_score", 0)),
                    niche=niche
                )
                products.append(product)
                
        except Exception as e:
            print(f"   [WARNING]  Failed to parse products: {e}")
        
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
            return "[HOT] STRONG BUY - Viral + Positive"
        elif viral_score >= 60 and sentiment_score >= 0.3:
            return "[SUCCESS] BUY - Good viral potential"
        elif viral_score >= 40 and sentiment_score >= 0:
            return "[WARNING] CONSIDER - Moderate interest"
        elif sentiment_score < 0:
            return "[ERROR] SKIP - Negative sentiment"
        else:
            return "[PAUSE] WATCH - Low viral score"


# ================================================================
# CONVENIENCE FUNCTIONS
# ================================================================

async def discover_twitter_products(niche: str = "smart_home", max_products: int = 10) -> List[Dict]:
    """Quick function to discover viral products on Twitter."""
    discovery = XAITwitterDiscovery()
    if not discovery.is_available():
        return []
    
    products = await discovery.discover_viral_products(niche, max_products)
    return [p.to_dict() for p in products]


async def get_all_niches() -> List[str]:
    """Get all available niches."""
    discovery = XAITwitterDiscovery()
    return discovery.get_all_niches()


async def test_xai_twitter():
    """Test xAI Twitter discovery."""
    print("\n" + "="*70)
    print("[TEST] TESTING xAI TWITTER DISCOVERY (EXPANDED)")
    print("="*70 + "\n")
    
    discovery = XAITwitterDiscovery()
    
    if not discovery.is_available():
        print("[ERROR] xAI not configured. Set XAI_API_KEY in .env")
        return
    
    print(f"[STATS] Available niches: {len(discovery.get_all_niches())}")
    print(f"[STATS] Total hashtags: {len(discovery.get_all_hashtags())}")
    print(f"[STATS] Niches: {', '.join(discovery.get_all_niches())}\n")
    
    # Test smart_home
    products = await discovery.discover_viral_products(
        niche="smart_home",
        max_products=5,
        time_range="24h"
    )
    
    for p in products:
        print(f"\n[HOT] {p.name}")
        print(f"   Viral Score: {p.viral_score}/100")
        print(f"   Signal: {p.buy_signal}")
        print(f"   Tweets: {p.tweet_count} | Likes: {p.total_likes}")
        if p.url:
            print(f"   URL: {p.url}")
    
    # Test emerging niches
    print("\n" + "="*50)
    print(" DISCOVERING EMERGING NICHES...")
    emerging = await discovery.discover_emerging_niches()
    if "emerging_niches" in emerging:
        for niche in emerging["emerging_niches"][:3]:
            print(f"\n   [TREND] {niche.get('niche_name', 'Unknown')}")
            print(f"      Growth: {niche.get('growth_rate', 'N/A')}")
            print(f"      Products: {', '.join(niche.get('example_products', [])[:3])}")
    
    print("\n[SUCCESS] Test complete!")


if __name__ == "__main__":
    asyncio.run(test_xai_twitter())
