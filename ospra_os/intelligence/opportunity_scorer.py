"""
Opportunity Scorer - The Heart of Ospra Intelligence
=====================================================
Implements the core formula: OPPORTUNITY = DEMAND / COMPETITION

This is what separates Ospra from AutoDS. We don't just find "hot products" -
we find products with RISING demand AND LOW competition.

The Sweet Spot:
- High Demand + Low Competition = [TARGET] OPPORTUNITY
- High Demand + High Competition = [ERROR] TOO LATE
- Low Demand + Low Competition = [ERROR] DEAD PRODUCT
- Low Demand + High Competition = [ERROR] WORST CASE

Author: Ospra Intelligence
Version: 2.0.0
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import os

logger = logging.getLogger(__name__)


# =============================================================================
# DATA STRUCTURES
# =============================================================================

class OpportunityTier(str, Enum):
    """Opportunity classification tiers"""
    GOLDEN = "golden"          # Score 85+: Rare gems, act NOW
    EXCELLENT = "excellent"    # Score 70-84: Great opportunity
    GOOD = "good"              # Score 55-69: Worth considering
    FAIR = "fair"              # Score 40-54: Proceed with caution
    POOR = "poor"              # Score 25-39: High risk
    AVOID = "avoid"            # Score <25: Do not enter


class DemandSignal(str, Enum):
    """Types of demand signals we track"""
    GOOGLE_TRENDS = "google_trends"
    TIKTOK_VIEWS = "tiktok_views"
    TIKTOK_ENGAGEMENT = "tiktok_engagement"
    AMAZON_BSR = "amazon_bsr"
    AMAZON_REVIEWS = "amazon_reviews"
    REDDIT_MENTIONS = "reddit_mentions"
    REDDIT_SENTIMENT = "reddit_sentiment"
    PINTEREST_TREND = "pinterest_trend"
    PINTEREST_SAVES = "pinterest_saves"


class CompetitionSignal(str, Enum):
    """Types of competition signals we track"""
    AMAZON_SELLERS = "amazon_sellers"
    SHOPIFY_STORES = "shopify_stores"
    FACEBOOK_ADS = "facebook_ads"
    TIKTOK_ADS = "tiktok_ads"
    INTERNAL_SATURATION = "internal_saturation"


@dataclass
class DemandMetrics:
    """Aggregated demand metrics for a product"""
    # Raw values
    google_trend_score: float = 0.0          # 0-100, from Google Trends
    google_trend_growth: float = 0.0         # % change over period
    tiktok_views: int = 0                    # Total views on related content
    tiktok_views_growth: float = 0.0         # % change in views
    tiktok_engagement_rate: float = 0.0      # (likes + comments + shares) / views
    amazon_bsr: int = 0                      # Best Seller Rank (lower = better)
    amazon_bsr_trend: float = 0.0            # % change (negative = improving)
    amazon_reviews_count: int = 0            # Total reviews
    amazon_reviews_growth: float = 0.0       # New reviews per week
    reddit_mentions_7d: int = 0              # Mentions in last 7 days
    reddit_mentions_30d: int = 0             # Mentions in last 30 days
    reddit_sentiment: float = 0.0            # -1 to 1 sentiment score
    pinterest_trend_score: float = 0.0       # 0-100 from Pinterest Trends
    pinterest_velocity: float = 0.0          # % change estimate from Pinterest
    pinterest_saves: int = 0                 # Total saves on top results
    pinterest_repins: int = 0                # Total repins on top results

    # Calculated scores (0-100)
    velocity_score: float = 0.0              # How fast is demand growing?
    volume_score: float = 0.0                # How much demand exists?
    momentum_score: float = 0.0              # Is it accelerating or decelerating?
    
    # Final demand score
    demand_score: float = 0.0                # Weighted combination (0-100)
    
    # Confidence in our data
    data_quality: float = 0.0                # 0-1, how much data we have
    sources_available: List[str] = field(default_factory=list)


@dataclass
class CompetitionMetrics:
    """Aggregated competition metrics for a product"""
    # Raw values
    amazon_seller_count: int = 0             # Number of sellers on Amazon
    amazon_seller_growth: float = 0.0        # New sellers per week
    shopify_store_count: int = 0             # Estimated Shopify stores
    facebook_ad_count: int = 0               # Active Facebook ads
    facebook_ad_spend_estimate: float = 0.0  # Estimated monthly spend
    tiktok_ad_count: int = 0                 # Active TikTok ads
    internal_saturation: int = 0             # How many Ospra users have this
    saturation_threshold: int = 100          # Max before we stop recommending
    
    # Market timing
    days_since_trend_start: int = 0          # How old is this trend?
    first_mover_advantage: float = 0.0       # 0-1, are we early or late?
    
    # Calculated scores (0-100, LOWER = BETTER)
    seller_density_score: float = 0.0        # How crowded is the market?
    ad_saturation_score: float = 0.0         # How much advertising competition?
    timing_score: float = 0.0                # Are we early or late to the party?
    
    # Final competition score (0-100, LOWER = BETTER for opportunity)
    competition_score: float = 0.0           # Weighted combination
    
    # Confidence
    data_quality: float = 0.0
    sources_available: List[str] = field(default_factory=list)


@dataclass
class OpportunityScore:
    """Final opportunity assessment for a product"""
    product_id: str
    product_name: str
    niche: str
    
    # Core scores
    demand: DemandMetrics = field(default_factory=DemandMetrics)
    competition: CompetitionMetrics = field(default_factory=CompetitionMetrics)
    
    # THE MAGIC NUMBER
    opportunity_score: float = 0.0           # 0-100, THE score that matters
    opportunity_tier: OpportunityTier = OpportunityTier.AVOID
    
    # Actionable insights
    recommendation: str = ""
    key_reasons: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    timing_advice: str = ""
    
    # Profit potential
    suggested_price: float = 0.0
    estimated_margin: float = 0.0
    monthly_volume_estimate: int = 0
    monthly_profit_estimate: float = 0.0
    
    # Confidence
    overall_confidence: float = 0.0          # 0-1, how sure are we?
    data_freshness: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for API responses"""
        return {
            "product_id": self.product_id,
            "product_name": self.product_name,
            "niche": self.niche,
            "opportunity_score": round(self.opportunity_score, 1),
            "opportunity_tier": self.opportunity_tier.value,
            "demand_score": round(self.demand.demand_score, 1),
            "competition_score": round(self.competition.competition_score, 1),
            "recommendation": self.recommendation,
            "key_reasons": self.key_reasons,
            "risks": self.risks,
            "timing_advice": self.timing_advice,
            "profit_estimate": {
                "suggested_price": round(self.suggested_price, 2),
                "estimated_margin": round(self.estimated_margin, 2),
                "monthly_volume": self.monthly_volume_estimate,
                "monthly_profit": round(self.monthly_profit_estimate, 2)
            },
            "confidence": round(self.overall_confidence, 2),
            "data_freshness": self.data_freshness.isoformat()
        }


# =============================================================================
# OPPORTUNITY SCORER ENGINE
# =============================================================================

class OpportunityScorer:
    """
    The brain of Ospra's product intelligence.
    
    Calculates opportunity scores using the formula:
    OPPORTUNITY = (DEMAND_VELOCITY * VOLUME) / (COMPETITION * TIMING_PENALTY)
    
    A high opportunity score means:
    - Demand is growing (not peaked, not dead)
    - Volume is sufficient (people actually want this)
    - Competition is low (sellers haven't piled in yet)
    - Timing is good (we're early to the trend)
    """
    
    # Scoring weights (must sum to 1.0 within categories)
    DEMAND_WEIGHTS = {
        'velocity': 0.40,      # How fast is demand growing? (MOST IMPORTANT)
        'volume': 0.35,        # How much total demand exists?
        'momentum': 0.25       # Is it accelerating or slowing?
    }

    # Trend-source sub-weights — used inside velocity/volume/momentum to blend
    # multiple trend signals. Pinterest is a strong early-signal source for
    # visual product categories (home, kitchen, beauty, fitness, fashion) and
    # typically leads Google Trends by 4–8 weeks.
    TREND_SOURCE_WEIGHTS = {
        'google_trends': 0.55,
        'pinterest':     0.15,  # task #37 — Pinterest weight in opportunity_scorer
        'tiktok':        0.20,
        'amazon':        0.10,
    }
    
    COMPETITION_WEIGHTS = {
        'seller_density': 0.35,    # How many sellers?
        'ad_saturation': 0.30,     # How much ad competition?
        'timing': 0.20,            # Are we early or late?
        'internal_saturation': 0.15 # Our own user saturation
    }
    
    # Thresholds for opportunity tiers
    TIER_THRESHOLDS = {
        OpportunityTier.GOLDEN: 85,
        OpportunityTier.EXCELLENT: 70,
        OpportunityTier.GOOD: 55,
        OpportunityTier.FAIR: 40,
        OpportunityTier.POOR: 25
    }
    
    # Competition thresholds (when to consider it saturated)
    COMPETITION_THRESHOLDS = {
        'amazon_sellers_low': 20,      # < 20 sellers = low competition
        'amazon_sellers_medium': 50,   # 20-50 = medium
        'amazon_sellers_high': 100,    # > 100 = high
        'shopify_stores_low': 50,      # < 50 stores = low
        'shopify_stores_medium': 150,  # 50-150 = medium
        'shopify_stores_high': 300,    # > 300 = high
        'facebook_ads_low': 50,        # < 50 ads = low
        'facebook_ads_medium': 200,    # 50-200 = medium
        'facebook_ads_high': 500       # > 500 = high
    }
    
    def __init__(self):
        """Initialize the opportunity scorer"""
        self.google_trends = None
        self.advanced_scraper = None
        self.apify_available = False
        self.saturation_tracker = None
        self.velocity_detector = None
        self.pinterest_trends = None

        self._init_data_sources()

    def _init_data_sources(self):
        """Initialize connections to data sources"""
        # Google Trends - Use our advanced scraper (bypasses rate limits)
        try:
            from ospra_os.intelligence.advanced_scraper import AdvancedProductScraper
            self.advanced_scraper = AdvancedProductScraper()
            logger.info("[SUCCESS] Google Trends (Advanced Scraper) connected")
        except Exception as e:
            logger.warning(f"[WARNING] Advanced Scraper not available: {e}")
        
        # Apify
        self.apify_token = os.getenv('APIFY_API_TOKEN') or os.getenv('OUBONSHOP_APIFY_API_TOKEN')
        if self.apify_token:
            self.apify_available = True
            logger.info("[SUCCESS] Apify connected")

        # Pinterest Trends (Apify-driven; weight 0.15 in TREND_SOURCE_WEIGHTS)
        if self.apify_available:
            try:
                from ospra_os.product_research.connectors.apify.pinterest_trends import (
                    PinterestTrendsApify,
                )
                pin = PinterestTrendsApify(api_token=self.apify_token)
                if pin.is_available():
                    self.pinterest_trends = pin
                    logger.info("[SUCCESS] Pinterest Trends connected (weight 0.15)")
            except Exception as e:
                logger.warning(f"[WARNING] Pinterest Trends not available: {e}")
        
        # Internal trackers
        try:
            from ospra_os.intelligence.saturation_tracker import SaturationTracker
            from ospra_os.intelligence.velocity_detector import VelocityDetector
            
            db_url = os.getenv('DATABASE_URL', 'sqlite:///ospra_os.db')
            self.saturation_tracker = SaturationTracker(db_url)
            self.velocity_detector = VelocityDetector(db_url)
            logger.info("[SUCCESS] Internal trackers connected")
        except Exception as e:
            logger.warning(f"[WARNING] Internal trackers not available: {e}")
    
    # =========================================================================
    # DEMAND SCORING
    # =========================================================================
    
    async def calculate_demand(
        self,
        product_name: str,
        search_keywords: List[str],
        raw_data: Optional[Dict] = None
    ) -> DemandMetrics:
        """
        Calculate demand metrics from all available sources.
        
        Args:
            product_name: Name of the product
            search_keywords: Keywords to search for trends
            raw_data: Optional pre-fetched data from discovery
            
        Returns:
            DemandMetrics with all scores calculated
        """
        metrics = DemandMetrics()
        sources = []
        
        # 1. Google Trends (velocity + volume) - Using Advanced Scraper
        if self.advanced_scraper:
            try:
                trend_data = await self._get_google_trends(search_keywords[:5])
                metrics.google_trend_score = trend_data.get('current_interest', 0)
                metrics.google_trend_growth = trend_data.get('growth_rate', 0)
                sources.append('google_trends')
            except Exception as e:
                logger.warning(f"Google Trends error: {e}")
        
        # 2. TikTok data (from raw_data or Apify)
        if raw_data:
            metrics.tiktok_views = raw_data.get('views', 0)
            metrics.tiktok_engagement_rate = self._calc_engagement_rate(raw_data)
            if raw_data.get('source') == 'tiktok_shop':
                sources.append('tiktok')
        
        # 3. Amazon data (from raw_data)
        if raw_data and raw_data.get('source') == 'amazon_bestsellers':
            metrics.amazon_bsr = raw_data.get('bestseller_rank', 9999)
            metrics.amazon_reviews_count = raw_data.get('reviews_count', 0)
            sources.append('amazon')
        
        # 4. Reddit sentiment
        if self.apify_available:
            try:
                reddit_data = await self._get_reddit_sentiment(product_name)
                metrics.reddit_mentions_7d = reddit_data.get('mentions_7d', 0)
                metrics.reddit_mentions_30d = reddit_data.get('mentions_30d', 0)
                metrics.reddit_sentiment = reddit_data.get('sentiment', 0)
                sources.append('reddit')
            except Exception as e:
                logger.debug(f"Reddit data not available: {e}")

        # 5. Pinterest Trends (early-signal demand source, weight 0.15)
        if self.pinterest_trends:
            try:
                pin_data = await self._get_pinterest_trends(search_keywords[:3])
                metrics.pinterest_trend_score = pin_data.get('trend_score', 0)
                metrics.pinterest_velocity = pin_data.get('velocity', 0)
                metrics.pinterest_saves = pin_data.get('saves', 0)
                metrics.pinterest_repins = pin_data.get('repins', 0)
                if pin_data.get('trend_score', 0) > 0 or pin_data.get('saves', 0) > 0:
                    sources.append('pinterest')
            except Exception as e:
                logger.debug(f"Pinterest data not available: {e}")

        # Calculate component scores
        metrics.velocity_score = self._calc_velocity_score(metrics)
        metrics.volume_score = self._calc_volume_score(metrics)
        metrics.momentum_score = self._calc_momentum_score(metrics)

        # Calculate final demand score
        metrics.demand_score = (
            metrics.velocity_score * self.DEMAND_WEIGHTS['velocity'] +
            metrics.volume_score * self.DEMAND_WEIGHTS['volume'] +
            metrics.momentum_score * self.DEMAND_WEIGHTS['momentum']
        )

        # Data quality (5 possible sources: google, tiktok, amazon, reddit, pinterest)
        metrics.sources_available = sources
        metrics.data_quality = len(sources) / 5

        return metrics
    
    def _calc_velocity_score(self, metrics: DemandMetrics) -> float:
        """Calculate how fast demand is growing (0-100), source-weighted."""
        weighted_scores: List[Tuple[float, float]] = []  # (score, weight) pairs
        w = self.TREND_SOURCE_WEIGHTS

        # Google Trends growth (most reliable for velocity)
        if metrics.google_trend_growth:
            trend_velocity = 50 + metrics.google_trend_growth
            weighted_scores.append((max(0, min(100, trend_velocity)), w['google_trends']))

        # TikTok views velocity
        if metrics.tiktok_views > 0:
            import math
            view_score = min(100, 50 + math.log10(max(1, metrics.tiktok_views)) * 10)
            weighted_scores.append((view_score, w['tiktok']))

        # Amazon BSR improvement
        if metrics.amazon_bsr_trend != 0:
            bsr_velocity = 50 - (metrics.amazon_bsr_trend * 0.5)
            weighted_scores.append((max(0, min(100, bsr_velocity)), w['amazon']))

        # Pinterest velocity (rising-keyword + save/repin ratio signal, weight 0.15)
        if metrics.pinterest_velocity != 0 or metrics.pinterest_trend_score > 0:
            # Pinterest velocity is already a % change estimate (-50..+50)
            pin_velocity = 50 + metrics.pinterest_velocity
            weighted_scores.append((max(0, min(100, pin_velocity)), w['pinterest']))

        # Reddit mention growth — included as un-weighted bonus signal
        if metrics.reddit_mentions_30d > 0:
            reddit_growth = (metrics.reddit_mentions_7d / metrics.reddit_mentions_30d) * 100
            reddit_velocity = min(100, reddit_growth * 2)
            # Use a small fixed weight (treated as bonus signal)
            weighted_scores.append((reddit_velocity, 0.05))

        if not weighted_scores:
            return 50

        total_weight = sum(weight for _, weight in weighted_scores)
        if total_weight == 0:
            return 50
        return sum(score * weight for score, weight in weighted_scores) / total_weight
    
    def _calc_volume_score(self, metrics: DemandMetrics) -> float:
        """Calculate total demand volume (0-100), source-weighted."""
        weighted_scores: List[Tuple[float, float]] = []
        w = self.TREND_SOURCE_WEIGHTS

        # Google Trends absolute interest
        if metrics.google_trend_score > 0:
            weighted_scores.append((metrics.google_trend_score, w['google_trends']))

        # TikTok engagement
        if metrics.tiktok_views > 0:
            engagement_boost = metrics.tiktok_engagement_rate * 100
            view_base = min(80, metrics.tiktok_views / 50000)
            weighted_scores.append((min(100, view_base + engagement_boost), w['tiktok']))

        # Amazon volume (reviews + BSR averaged)
        amazon_components = []
        if metrics.amazon_reviews_count > 0:
            import math
            review_score = min(100, 30 + math.log10(max(1, metrics.amazon_reviews_count)) * 20)
            amazon_components.append(review_score)
        if metrics.amazon_bsr > 0:
            import math
            bsr_score = max(0, 100 - math.log10(max(1, metrics.amazon_bsr)) * 20)
            amazon_components.append(bsr_score)
        if amazon_components:
            weighted_scores.append(
                (sum(amazon_components) / len(amazon_components), w['amazon'])
            )

        # Pinterest volume (saves are highest purchase-intent signal, weight 0.15)
        if metrics.pinterest_trend_score > 0:
            weighted_scores.append((metrics.pinterest_trend_score, w['pinterest']))

        if not weighted_scores:
            return 50

        total_weight = sum(weight for _, weight in weighted_scores)
        if total_weight == 0:
            return 50
        return sum(score * weight for score, weight in weighted_scores) / total_weight
    
    def _calc_momentum_score(self, metrics: DemandMetrics) -> float:
        """Calculate if demand is accelerating or decelerating (0-100)"""
        # This would ideally use time-series data
        # For now, combine growth signals
        
        momentum = 50  # Neutral starting point
        
        # Google Trends: Is it still growing?
        if metrics.google_trend_growth > 20:
            momentum += 20  # Strong acceleration
        elif metrics.google_trend_growth > 0:
            momentum += 10  # Mild acceleration
        elif metrics.google_trend_growth < -20:
            momentum -= 20  # Strong deceleration
        elif metrics.google_trend_growth < 0:
            momentum -= 10  # Mild deceleration
        
        # Reddit: Recent buzz?
        if metrics.reddit_mentions_30d > 0:
            recency_ratio = metrics.reddit_mentions_7d / metrics.reddit_mentions_30d
            if recency_ratio > 0.4:  # 40%+ in last week = accelerating
                momentum += 15
            elif recency_ratio < 0.15:  # Less than 15% in last week = dying
                momentum -= 15
        
        # Sentiment affects momentum
        if metrics.reddit_sentiment > 0.3:
            momentum += 10
        elif metrics.reddit_sentiment < -0.3:
            momentum -= 10
        
        return max(0, min(100, momentum))
    
    def _calc_engagement_rate(self, data: Dict) -> float:
        """Calculate TikTok engagement rate"""
        views = data.get('views', 0)
        if views == 0:
            return 0
        
        likes = data.get('likes', 0)
        comments = data.get('comments_count', 0)
        shares = data.get('shares', 0)
        
        return (likes + comments * 2 + shares * 3) / views
    
    # =========================================================================
    # COMPETITION SCORING
    # =========================================================================
    
    async def calculate_competition(
        self,
        product_name: str,
        search_keywords: List[str],
        raw_data: Optional[Dict] = None
    ) -> CompetitionMetrics:
        """
        Calculate competition metrics from all available sources.
        
        Args:
            product_name: Name of the product
            search_keywords: Keywords to search for competitors
            raw_data: Optional pre-fetched data
            
        Returns:
            CompetitionMetrics with all scores calculated
        """
        metrics = CompetitionMetrics()
        sources = []
        
        # 1. Amazon seller count (via Apify)
        if self.apify_available:
            try:
                amazon_comp = await self._get_amazon_competition(search_keywords[0])
                metrics.amazon_seller_count = amazon_comp.get('seller_count', 0)
                sources.append('amazon_sellers')
            except Exception as e:
                logger.debug(f"Amazon competition data not available: {e}")
        
        # 2. Shopify store count (via Apify competitor scraper)
        if self.apify_available:
            try:
                shopify_comp = await self._get_shopify_competition(product_name)
                metrics.shopify_store_count = shopify_comp.get('store_count', 0)
                sources.append('shopify_stores')
            except Exception as e:
                logger.debug(f"Shopify competition data not available: {e}")
        
        # 3. Facebook Ad Library (would need specific API)
        # For now, estimate based on other signals
        metrics.facebook_ad_count = self._estimate_facebook_ads(metrics)
        
        # 4. Internal saturation (from our tracker)
        if self.saturation_tracker:
            try:
                is_saturated = await self.saturation_tracker.is_product_saturated(product_name=product_name)
                count, threshold = await self.saturation_tracker.get_saturation_count(product_name)
                metrics.internal_saturation = count
                metrics.saturation_threshold = threshold
                sources.append('internal_saturation')
            except Exception as e:
                logger.debug(f"Internal saturation not available: {e}")
        
        # 5. Trend timing (how old is this trend?)
        if self.advanced_scraper:
            try:
                timing = await self._get_trend_timing(search_keywords[:3])
                metrics.days_since_trend_start = timing.get('days_old', 0)
                metrics.first_mover_advantage = timing.get('first_mover_score', 0.5)
                sources.append('trend_timing')
            except Exception as e:
                logger.debug(f"Trend timing not available: {e}")
        
        # Calculate component scores
        metrics.seller_density_score = self._calc_seller_density(metrics)
        metrics.ad_saturation_score = self._calc_ad_saturation(metrics)
        metrics.timing_score = self._calc_timing_score(metrics)
        
        # Internal saturation component
        internal_sat_score = (metrics.internal_saturation / metrics.saturation_threshold) * 100 if metrics.saturation_threshold > 0 else 0
        
        # Calculate final competition score (LOWER = BETTER)
        metrics.competition_score = (
            metrics.seller_density_score * self.COMPETITION_WEIGHTS['seller_density'] +
            metrics.ad_saturation_score * self.COMPETITION_WEIGHTS['ad_saturation'] +
            metrics.timing_score * self.COMPETITION_WEIGHTS['timing'] +
            internal_sat_score * self.COMPETITION_WEIGHTS['internal_saturation']
        )
        
        # Data quality
        metrics.sources_available = sources
        metrics.data_quality = len(sources) / 5  # 5 possible sources
        
        return metrics
    
    def _calc_seller_density(self, metrics: CompetitionMetrics) -> float:
        """Calculate seller density score (0-100, higher = more competition)"""
        scores = []
        
        # Amazon sellers
        if metrics.amazon_seller_count > 0:
            thresholds = self.COMPETITION_THRESHOLDS
            if metrics.amazon_seller_count < thresholds['amazon_sellers_low']:
                scores.append(20)  # Low competition
            elif metrics.amazon_seller_count < thresholds['amazon_sellers_medium']:
                scores.append(50)  # Medium competition
            elif metrics.amazon_seller_count < thresholds['amazon_sellers_high']:
                scores.append(75)  # High competition
            else:
                scores.append(95)  # Saturated
        
        # Shopify stores
        if metrics.shopify_store_count > 0:
            thresholds = self.COMPETITION_THRESHOLDS
            if metrics.shopify_store_count < thresholds['shopify_stores_low']:
                scores.append(15)
            elif metrics.shopify_store_count < thresholds['shopify_stores_medium']:
                scores.append(45)
            elif metrics.shopify_store_count < thresholds['shopify_stores_high']:
                scores.append(70)
            else:
                scores.append(90)
        
        return sum(scores) / len(scores) if scores else 50
    
    def _calc_ad_saturation(self, metrics: CompetitionMetrics) -> float:
        """Calculate advertising saturation (0-100, higher = more saturated)"""
        thresholds = self.COMPETITION_THRESHOLDS
        
        fb_score = 50
        if metrics.facebook_ad_count < thresholds['facebook_ads_low']:
            fb_score = 20
        elif metrics.facebook_ad_count < thresholds['facebook_ads_medium']:
            fb_score = 50
        elif metrics.facebook_ad_count < thresholds['facebook_ads_high']:
            fb_score = 75
        else:
            fb_score = 95
        
        return fb_score
    
    def _calc_timing_score(self, metrics: CompetitionMetrics) -> float:
        """Calculate timing penalty (0-100, higher = later to the trend)"""
        days = metrics.days_since_trend_start
        
        # Optimal: 7-30 days old (early growth phase)
        if days < 7:
            return 30  # Too new, risky
        elif days < 30:
            return 10  # Perfect timing!
        elif days < 60:
            return 30  # Still good
        elif days < 90:
            return 50  # Getting crowded
        elif days < 180:
            return 70  # Late
        else:
            return 90  # Very late
    
    def _estimate_facebook_ads(self, metrics: CompetitionMetrics) -> int:
        """Estimate Facebook ad count based on other signals"""
        # Rough estimate: More sellers = more ads
        base = metrics.amazon_seller_count * 2 + metrics.shopify_store_count
        return min(1000, base)
    
    # =========================================================================
    # OPPORTUNITY CALCULATION
    # =========================================================================
    
    async def score_product(
        self,
        product_id: str,
        product_name: str,
        niche: str,
        search_keywords: List[str],
        raw_data: Optional[Dict] = None,
        cost_price: float = 0.0
    ) -> OpportunityScore:
        """
        Calculate the complete opportunity score for a product.
        
        This is THE function that determines if a product is worth selling.
        
        Args:
            product_id: Unique product identifier
            product_name: Product name/title
            niche: Product niche
            search_keywords: Keywords for trend/competition research
            raw_data: Optional pre-fetched discovery data
            cost_price: Cost to acquire the product
            
        Returns:
            OpportunityScore with complete analysis
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"[TARGET] OPPORTUNITY SCORING: {product_name[:40]}...")
        logger.info(f"{'='*60}")
        
        # Calculate demand
        logger.info("[TREND] Calculating demand metrics...")
        demand = await self.calculate_demand(product_name, search_keywords, raw_data)
        logger.info(f"   Demand Score: {demand.demand_score:.1f}")
        
        # Calculate competition
        logger.info(" Calculating competition metrics...")
        competition = await self.calculate_competition(product_name, search_keywords, raw_data)
        logger.info(f"   Competition Score: {competition.competition_score:.1f}")
        
        # THE MAGIC FORMULA
        # =================
        # Opportunity = Demand / Competition
        # But we need to normalize since both are 0-100
        #
        # If demand = 80 and competition = 20:
        #   opportunity = 80 * (1 - 0.2) = 80 * 0.8 = 64 [SUCCESS] Good
        #
        # If demand = 80 and competition = 80:
        #   opportunity = 80 * (1 - 0.8) = 80 * 0.2 = 16 [ERROR] Bad
        #
        # If demand = 30 and competition = 20:
        #   opportunity = 30 * (1 - 0.2) = 30 * 0.8 = 24 [ERROR] Bad (low demand)
        
        competition_penalty = competition.competition_score / 100  # 0-1
        opportunity_score = demand.demand_score * (1 - competition_penalty * 0.7)
        
        # Bonus for very low competition
        if competition.competition_score < 20:
            opportunity_score *= 1.15  # 15% bonus
        
        # Penalty for very high competition
        if competition.competition_score > 80:
            opportunity_score *= 0.7  # 30% penalty
        
        # Cap at 100
        opportunity_score = min(100, max(0, opportunity_score))
        
        # Determine tier
        tier = OpportunityTier.AVOID
        for t, threshold in self.TIER_THRESHOLDS.items():
            if opportunity_score >= threshold:
                tier = t
                break
        
        logger.info(f"[TARGET] Opportunity Score: {opportunity_score:.1f} ({tier.value})")
        
        # Build the result
        result = OpportunityScore(
            product_id=product_id,
            product_name=product_name,
            niche=niche,
            demand=demand,
            competition=competition,
            opportunity_score=opportunity_score,
            opportunity_tier=tier
        )
        
        # Generate insights
        result.key_reasons = self._generate_reasons(demand, competition, tier)
        result.risks = self._generate_risks(demand, competition)
        result.recommendation = self._generate_recommendation(tier, demand, competition)
        result.timing_advice = self._generate_timing_advice(competition)
        
        # Calculate profit potential
        if cost_price > 0:
            result.suggested_price = self._calculate_suggested_price(cost_price, tier)
            result.estimated_margin = result.suggested_price - cost_price
            result.monthly_volume_estimate = self._estimate_monthly_volume(demand, competition)
            result.monthly_profit_estimate = result.estimated_margin * result.monthly_volume_estimate
        
        # Confidence
        result.overall_confidence = (demand.data_quality + competition.data_quality) / 2
        
        return result
    
    async def score_products_batch(
        self,
        products: List[Dict],
        niche: str = "smart_home"
    ) -> List[OpportunityScore]:
        """
        Score multiple products efficiently.
        
        Args:
            products: List of product dicts from discovery
            niche: Product niche
            
        Returns:
            List of OpportunityScore objects, sorted by score
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"[STATS] BATCH SCORING: {len(products)} products")
        logger.info(f"{'='*60}")
        
        scores = []
        
        for product in products:
            try:
                # Extract keywords from product name
                keywords = product.get('title', '').split()[:5]
                keywords = [w for w in keywords if len(w) > 3]  # Filter short words
                
                if not keywords:
                    keywords = [niche]
                
                score = await self.score_product(
                    product_id=product.get('product_id', ''),
                    product_name=product.get('title', 'Unknown'),
                    niche=niche,
                    search_keywords=keywords,
                    raw_data=product,
                    cost_price=product.get('price', 0)
                )
                scores.append(score)
                
            except Exception as e:
                logger.error(f"Error scoring product: {e}")
                continue
        
        # Sort by opportunity score
        scores.sort(key=lambda x: x.opportunity_score, reverse=True)
        
        # Log summary
        tiers = {}
        for s in scores:
            tier = s.opportunity_tier.value
            tiers[tier] = tiers.get(tier, 0) + 1
        
        logger.info(f"\n[STATS] Scoring Summary:")
        for tier, count in tiers.items():
            logger.info(f"   {tier}: {count} products")
        
        return scores
    
    # =========================================================================
    # INSIGHT GENERATION
    # =========================================================================
    
    def _generate_reasons(
        self,
        demand: DemandMetrics,
        competition: CompetitionMetrics,
        tier: OpportunityTier
    ) -> List[str]:
        """Generate human-readable reasons for the score"""
        reasons = []
        
        # Demand reasons
        if demand.velocity_score >= 70:
            reasons.append("[START] Demand is growing rapidly")
        elif demand.velocity_score >= 50:
            reasons.append("[TREND] Steady demand growth")
        
        if demand.volume_score >= 70:
            reasons.append(" High search volume indicates strong market interest")
        
        if demand.momentum_score >= 60:
            reasons.append("[FAST] Trend is accelerating")
        
        # Competition reasons
        if competition.seller_density_score < 30:
            reasons.append("[TOP] Low seller competition - room to capture market")
        elif competition.seller_density_score > 70:
            reasons.append("[WARNING] High seller competition")
        
        if competition.timing_score < 30:
            reasons.append("[ALARM] Early to the trend - first mover advantage")
        
        # Tier-specific
        if tier == OpportunityTier.GOLDEN:
            reasons.insert(0, "[NEW] RARE OPPORTUNITY: Perfect demand/competition ratio")
        elif tier == OpportunityTier.EXCELLENT:
            reasons.insert(0, "[TARGET] Strong opportunity with favorable conditions")
        
        return reasons[:5]  # Limit to 5 reasons
    
    def _generate_risks(
        self,
        demand: DemandMetrics,
        competition: CompetitionMetrics
    ) -> List[str]:
        """Generate risk warnings"""
        risks = []
        
        if demand.data_quality < 0.5:
            risks.append("[STATS] Limited data - confidence is lower")
        
        if demand.momentum_score < 40:
            risks.append("[DECLINE] Trend may be slowing down")
        
        if competition.timing_score > 60:
            risks.append("⏳ Late to the trend - competition is building")
        
        if competition.internal_saturation > competition.saturation_threshold * 0.7:
            risks.append(f"[WARNING] {int(competition.internal_saturation / competition.saturation_threshold * 100)}% internal saturation")
        
        if competition.seller_density_score > 60:
            risks.append(" Crowded market - differentiation required")
        
        return risks
    
    def _generate_recommendation(
        self,
        tier: OpportunityTier,
        demand: DemandMetrics,
        competition: CompetitionMetrics
    ) -> str:
        """Generate actionable recommendation"""
        if tier == OpportunityTier.GOLDEN:
            return "[HOT] ACT NOW: This is a rare golden opportunity. Deploy immediately before competition increases."
        elif tier == OpportunityTier.EXCELLENT:
            return "[SUCCESS] STRONG BUY: Excellent opportunity with good risk/reward. Proceed with deployment."
        elif tier == OpportunityTier.GOOD:
            return "[GOOD] CONSIDER: Good opportunity but monitor competition. Test with limited inventory first."
        elif tier == OpportunityTier.FAIR:
            return "[WARNING] CAUTION: Marginal opportunity. Only proceed if you have a strong differentiation strategy."
        elif tier == OpportunityTier.POOR:
            return "[BLOCKED] SKIP: Risk outweighs potential reward. Look for better opportunities."
        else:
            return "[ERROR] AVOID: This product does not meet opportunity criteria."
    
    def _generate_timing_advice(self, competition: CompetitionMetrics) -> str:
        """Generate timing-specific advice"""
        days = competition.days_since_trend_start
        
        if days < 7:
            return " Very early stage - high reward but also higher risk. Monitor for 1-2 more weeks."
        elif days < 30:
            return "[START] Perfect timing - trend is established but not saturated. Move quickly."
        elif days < 60:
            return "[TREND] Good timing - still opportunity but competition is building. Don't delay."
        elif days < 90:
            return "[ALARM] Getting late - proceed only with strong differentiation or lower costs."
        else:
            return "⏳ Late stage - most opportunity has passed. Consider alternatives."
    
    def _calculate_suggested_price(self, cost: float, tier: OpportunityTier) -> float:
        """Calculate suggested retail price based on tier"""
        # Higher tier = can charge higher margins
        margin_multipliers = {
            OpportunityTier.GOLDEN: 3.5,
            OpportunityTier.EXCELLENT: 3.0,
            OpportunityTier.GOOD: 2.5,
            OpportunityTier.FAIR: 2.0,
            OpportunityTier.POOR: 1.8,
            OpportunityTier.AVOID: 1.5
        }
        
        multiplier = margin_multipliers.get(tier, 2.0)
        return round(cost * multiplier, 2)
    
    def _estimate_monthly_volume(
        self,
        demand: DemandMetrics,
        competition: CompetitionMetrics
    ) -> int:
        """Estimate monthly sales volume"""
        # Base estimate from demand signals
        base_volume = 0
        
        if demand.amazon_bsr > 0:
            # BSR 1000 ≈ 300 sales/month, BSR 10000 ≈ 30 sales/month
            base_volume = max(10, int(300000 / demand.amazon_bsr))
        elif demand.volume_score > 0:
            base_volume = int(demand.volume_score * 2)  # Score 80 = 160 sales
        
        # Adjust for competition
        competition_factor = 1 - (competition.competition_score / 200)  # Max 50% reduction
        
        return max(5, int(base_volume * competition_factor))
    
    # =========================================================================
    # DATA SOURCE HELPERS
    # =========================================================================
    
    async def _get_google_trends(self, keywords: List[str]) -> Dict:
        """Fetch Google Trends data using our advanced scraper (bypasses rate limits)"""
        if not self.advanced_scraper or not keywords:
            return {}

        try:
            # Use the first keyword (most relevant)
            keyword = keywords[0] if isinstance(keywords, list) else keywords

            # Scrape Google Trends using Playwright (bypasses rate limits)
            result = await self.advanced_scraper.scrape_google_trends(
                keyword=keyword,
                timeframe='today 3-m'
            )

            if not result.get('success'):
                logger.debug(f"Google Trends scrape failed for: {keyword}")
                return {}

            # Extract trend values
            trend_values = result.get('trend_values', [])
            velocity_score = result.get('velocity_score', 50)

            if trend_values and len(trend_values) >= 2:
                current = sum(trend_values[-7:]) / len(trend_values[-7:])  # Last 7 days
                previous = sum(trend_values[:7]) / min(7, len(trend_values[:7]))  # First 7 days

                growth_rate = ((current - previous) / previous * 100) if previous > 0 else 0
            else:
                current = velocity_score
                growth_rate = 0

            return {
                'current_interest': current,
                'growth_rate': growth_rate,
                'velocity_score': velocity_score,
                'trend_values': trend_values
            }
        except Exception as e:
            logger.debug(f"Google Trends fetch failed: {e}")
            return {}
    
    async def _get_reddit_sentiment(self, product_name: str) -> Dict:
        """Fetch Reddit sentiment data via Apify"""
        # This would call the Reddit sentiment Apify actor
        # For now, return placeholder
        return {
            'mentions_7d': 0,
            'mentions_30d': 0,
            'sentiment': 0
        }

    async def _get_pinterest_trends(self, keywords: List[str]) -> Dict:
        """
        Fetch Pinterest trend signals via Apify (weight 0.15 in demand calculation).

        Pinterest is an early-signal source for visual product categories
        (home, kitchen, beauty, fashion, fitness). Repins and saves typically
        precede Amazon bestseller status by 4-8 weeks.

        Returns averaged signals across the provided keywords.
        """
        if not self.pinterest_trends or not keywords:
            return {}

        try:
            results = await self.pinterest_trends.get_interest(
                search_terms=keywords[:3],
                geo='US',
            )

            if not results:
                return {}

            # Average across keywords (already trimmed to top 3)
            valid = [r for r in results if r.trend_score > 0 or r.total_saves > 0]
            if not valid:
                return {}

            avg_trend = sum(r.trend_score for r in valid) / len(valid)
            avg_velocity = sum(r.velocity for r in valid) / len(valid)
            total_saves = sum(r.total_saves for r in valid)
            total_repins = sum(r.total_repins for r in valid)

            return {
                'trend_score': round(avg_trend, 1),
                'velocity': round(avg_velocity, 1),
                'saves': total_saves,
                'repins': total_repins,
            }
        except Exception as e:
            logger.debug(f"Pinterest trends fetch failed: {e}")
            return {}
    
    async def _get_amazon_competition(self, keyword: str) -> Dict:
        """Fetch Amazon competition data"""
        # This would call Amazon scraper
        return {'seller_count': 0}
    
    async def _get_shopify_competition(self, product_name: str) -> Dict:
        """Fetch Shopify store competition data"""
        # This would call Shopify competitor scraper
        return {'store_count': 0}
    
    async def _get_trend_timing(self, keywords: List[str]) -> Dict:
        """Calculate how old the trend is using advanced scraper"""
        if not self.advanced_scraper or not keywords:
            return {'days_old': 30, 'first_mover_score': 0.5}

        try:
            # Use first keyword
            keyword = keywords[0] if isinstance(keywords, list) else keywords

            # Scrape 12-month trend data
            result = await self.advanced_scraper.scrape_google_trends(
                keyword=keyword,
                timeframe='today 12-m'
            )

            if not result.get('success'):
                return {'days_old': 30, 'first_mover_score': 0.5}

            trend_values = result.get('trend_values', [])
            if not trend_values or len(trend_values) < 10:
                return {'days_old': 30, 'first_mover_score': 0.5}

            # Find when trend started (first time it exceeded 20% of max)
            max_interest = max(trend_values)
            threshold = max_interest * 0.2

            # Find first index above threshold
            days_old = 30
            for i, value in enumerate(trend_values):
                if value > threshold:
                    # Estimate days based on position in data (12 months ≈ 365 days)
                    days_old = int((len(trend_values) - i) * (365 / len(trend_values)))
                    break

            # First mover advantage: decays over 6 months
            first_mover = max(0, 1 - (days_old / 180))

            return {
                'days_old': days_old,
                'first_mover_score': first_mover
            }

        except Exception as e:
            logger.debug(f"Trend timing fetch failed: {e}")
            return {'days_old': 30, 'first_mover_score': 0.5}


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

_scorer = None


def get_opportunity_scorer() -> OpportunityScorer:
    """Get or create singleton scorer instance"""
    global _scorer
    if _scorer is None:
        _scorer = OpportunityScorer()
    return _scorer


async def score_opportunity(
    product_name: str,
    niche: str = "smart_home",
    keywords: Optional[List[str]] = None
) -> OpportunityScore:
    """
    Quick function to score a single product opportunity.
    
    Usage:
        score = await score_opportunity("LED Strip Lights", "smart_home")
        print(f"Opportunity: {score.opportunity_score} ({score.opportunity_tier})")
    """
    scorer = get_opportunity_scorer()
    
    if keywords is None:
        keywords = product_name.split()[:5]
    
    return await scorer.score_product(
        product_id=f"manual_{hash(product_name) % 10000}",
        product_name=product_name,
        niche=niche,
        search_keywords=keywords
    )


async def find_opportunities(
    niche: str = "smart_home",
    limit: int = 20,
    min_score: float = 55.0
) -> List[OpportunityScore]:
    """
    Discover and score products, returning only opportunities.
    
    Usage:
        opportunities = await find_opportunities("smart_home", limit=20, min_score=60)
        for opp in opportunities:
            print(f"{opp.product_name}: {opp.opportunity_score}")
    """
    from ospra_os.intelligence.product_discovery import get_discovery_engine
    
    # Discover products
    discovery = get_discovery_engine()
    products = await discovery.discover_products(niche=niche, max_products=limit * 2)
    
    # Score them
    scorer = get_opportunity_scorer()
    scores = await scorer.score_products_batch(products, niche)
    
    # Filter by minimum score
    opportunities = [s for s in scores if s.opportunity_score >= min_score]
    
    return opportunities[:limit]
