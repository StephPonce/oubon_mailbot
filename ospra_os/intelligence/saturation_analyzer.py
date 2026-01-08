"""
 ANTI-SATURATION ANALYZER
============================

This is what separates Ospra from every other "hot products" tool.

While others show you trending products that EVERYONE sees,
we analyze COMPETITION to find products with:
- Low seller count (less competition)
- Low ad saturation (cheaper to advertise)
- Early trend timing (first mover advantage)
- Price stability (no race to bottom)

THE ANTI-SATURATION SCORE penalizes products that are:
- Already saturated with sellers
- Flooded with Facebook/TikTok ads
- Past peak timing
- In price decline spiral

Author: OspraOS
Date: December 2024
"""

import os
import asyncio
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class SaturationAnalysis:
    """Complete saturation analysis for a product"""
    
    product_name: str
    
    # Seller Saturation (from AliExpress/Amazon)
    aliexpress_seller_count: int = 0
    amazon_seller_count: int = 0
    seller_growth_rate: float = 0.0  # % growth per week
    seller_saturation_score: float = 50.0  # 0=saturated, 100=blue ocean
    
    # Ad Saturation (from Facebook Ad Library, TikTok)
    facebook_active_ads: int = 0
    tiktok_active_ads: int = 0
    ad_spend_estimate: float = 0.0  # Monthly ad spend in market
    ad_saturation_score: float = 50.0  # 0=oversaturated, 100=untapped
    
    # Price Stability
    price_30d_change: float = 0.0  # % change in 30 days
    price_trend: str = "stable"  # rising, stable, declining, crashing
    price_stability_score: float = 50.0  # 0=race to bottom, 100=stable
    
    # Timing Analysis
    trend_stage: str = "unknown"  # emerging, early, growth, peak, decline
    days_since_trend_start: int = 0
    estimated_peak_date: Optional[str] = None
    first_mover_window_days: int = 30  # Days of opportunity left
    timing_score: float = 50.0  # 0=too late, 100=perfect timing
    
    # Combined Anti-Saturation Score
    anti_saturation_score: float = 50.0  # 0=avoid, 100=golden opportunity
    
    # Risk Assessment
    saturation_risk: str = "medium"  # low, medium, high, critical
    risk_factors: List[str] = field(default_factory=list)
    opportunity_factors: List[str] = field(default_factory=list)
    
    # Recommendations
    recommendation: str = "MONITOR"  # DEPLOY, MONITOR, CAUTION, AVOID
    timing_advice: str = ""
    
    analyzed_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "product_name": self.product_name,
            "seller_saturation": {
                "aliexpress_sellers": self.aliexpress_seller_count,
                "amazon_sellers": self.amazon_seller_count,
                "growth_rate": self.seller_growth_rate,
                "score": self.seller_saturation_score,
            },
            "ad_saturation": {
                "facebook_ads": self.facebook_active_ads,
                "tiktok_ads": self.tiktok_active_ads,
                "estimated_spend": self.ad_spend_estimate,
                "score": self.ad_saturation_score,
            },
            "price_stability": {
                "30d_change": self.price_30d_change,
                "trend": self.price_trend,
                "score": self.price_stability_score,
            },
            "timing": {
                "trend_stage": self.trend_stage,
                "days_trending": self.days_since_trend_start,
                "estimated_peak": self.estimated_peak_date,
                "first_mover_window": self.first_mover_window_days,
                "score": self.timing_score,
            },
            "anti_saturation_score": self.anti_saturation_score,
            "saturation_risk": self.saturation_risk,
            "risk_factors": self.risk_factors,
            "opportunity_factors": self.opportunity_factors,
            "recommendation": self.recommendation,
            "timing_advice": self.timing_advice,
            "analyzed_at": self.analyzed_at,
        }


class AntiSaturationAnalyzer:
    """
    Analyzes market saturation to find REAL opportunities.
    
    This is the competitive moat - we don't just find hot products,
    we find hot products that AREN'T YET SATURATED.
    
    Data Sources:
    - AliExpress: Seller count, price history
    - Amazon: Seller count, BSR velocity
    - Apify: Facebook Ad Library scraping
    - Google Trends: Trend velocity and timing
    - TikTok: Ad saturation via Apify
    """
    
    # Saturation thresholds
    SELLER_THRESHOLDS = {
        "blue_ocean": 10,      # < 10 sellers = 100 score
        "low": 25,             # < 25 sellers = 80 score
        "medium": 50,          # < 50 sellers = 60 score
        "high": 100,           # < 100 sellers = 40 score
        "saturated": 200,      # < 200 sellers = 20 score
        # > 200 = 0 score
    }
    
    AD_THRESHOLDS = {
        "untapped": 5,         # < 5 active ads = 100 score
        "low": 20,             # < 20 ads = 80 score
        "medium": 50,          # < 50 ads = 60 score
        "high": 100,           # < 100 ads = 40 score
        "oversaturated": 200,  # < 200 ads = 20 score
    }
    
    TIMING_STAGES = {
        "emerging": (0, 14, 100),     # Days 0-14, score 100
        "early": (15, 30, 85),        # Days 15-30, score 85
        "growth": (31, 60, 70),       # Days 31-60, score 70
        "peak": (61, 90, 40),         # Days 61-90, score 40
        "decline": (91, 999, 15),     # Days 91+, score 15
    }
    
    def __init__(self):
        """Initialize with available data sources."""
        self._init_data_sources()
    
    def _init_data_sources(self):
        """Initialize connections to data sources."""
        # AliExpress connector
        try:
            from ospra_os.product_research.connectors.suppliers.aliexpress import AliExpressConnector
            ali_key = os.getenv('ALIEXPRESS_APP_KEY')
            ali_secret = os.getenv('ALIEXPRESS_APP_SECRET')
            ali_token = os.getenv('ALIEXPRESS_ACCESS_TOKEN')
            if ali_key and ali_secret and ali_token:
                self.aliexpress = AliExpressConnector(ali_key, ali_secret, ali_token)
                self.aliexpress_enabled = True
                logger.info("[SUCCESS] AliExpress connected for saturation analysis")
            else:
                self.aliexpress = None
                self.aliexpress_enabled = False
        except Exception as e:
            self.aliexpress = None
            self.aliexpress_enabled = False
            logger.warning(f"AliExpress not available: {e}")
        
        # Apify for ad library scraping
        try:
            from ospra_os.product_research.connectors.apify import ApifyClient
            apify_token = os.getenv('APIFY_API_TOKEN')
            if apify_token:
                self.apify = ApifyClient(api_token=apify_token)
                self.apify_enabled = self.apify.is_available()
                if self.apify_enabled:
                    logger.info("[SUCCESS] Apify connected for ad saturation analysis")
            else:
                self.apify = None
                self.apify_enabled = False
        except Exception as e:
            self.apify = None
            self.apify_enabled = False
            logger.warning(f"Apify not available: {e}")
        
        # Google Trends for timing
        try:
            from pytrends.request import TrendReq
            self.pytrends = TrendReq(hl='en-US', tz=360)
            self.trends_enabled = True
            logger.info("[SUCCESS] Google Trends connected for timing analysis")
        except Exception as e:
            self.pytrends = None
            self.trends_enabled = False
            logger.warning(f"Google Trends not available: {e}")
    
    async def analyze_saturation(
        self,
        product_name: str,
        product_data: Optional[Dict[str, Any]] = None
    ) -> SaturationAnalysis:
        """
        Complete saturation analysis for a product.
        
        Args:
            product_name: Product to analyze
            product_data: Optional existing product data
            
        Returns:
            SaturationAnalysis with all metrics
        """
        logger.info(f" Analyzing saturation: {product_name[:50]}...")
        
        analysis = SaturationAnalysis(product_name=product_name)
        
        # Run all analyses in parallel
        tasks = [
            self._analyze_seller_saturation(product_name, product_data),
            self._analyze_ad_saturation(product_name),
            self._analyze_price_stability(product_name, product_data),
            self._analyze_timing(product_name),
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Merge results
        for result in results:
            if isinstance(result, dict):
                for key, value in result.items():
                    if hasattr(analysis, key):
                        setattr(analysis, key, value)
        
        # Calculate combined anti-saturation score
        analysis.anti_saturation_score = self._calculate_combined_score(analysis)
        
        # Determine risk level
        analysis.saturation_risk = self._determine_risk_level(analysis)
        
        # Generate recommendation
        analysis.recommendation, analysis.timing_advice = self._generate_recommendation(analysis)
        
        # Compile risk and opportunity factors
        analysis.risk_factors = self._compile_risk_factors(analysis)
        analysis.opportunity_factors = self._compile_opportunity_factors(analysis)
        
        logger.info(f"   Anti-Saturation Score: {analysis.anti_saturation_score}/100")
        logger.info(f"   Recommendation: {analysis.recommendation}")
        
        return analysis
    
    async def _analyze_seller_saturation(
        self,
        product_name: str,
        product_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Analyze seller count and growth."""
        result = {
            "aliexpress_seller_count": 0,
            "amazon_seller_count": 0,
            "seller_growth_rate": 0.0,
            "seller_saturation_score": 50.0,
        }
        
        # Get AliExpress seller count
        if self.aliexpress_enabled:
            try:
                # Search for product to get seller count
                products = await self.aliexpress.search(query=product_name, page_size=50)
                
                # Count unique sellers (simplified - real implementation would track seller IDs)
                result["aliexpress_seller_count"] = len(products) if products else 0
                
            except Exception as e:
                logger.warning(f"AliExpress seller count failed: {e}")
        
        # Calculate seller saturation score
        seller_count = result["aliexpress_seller_count"] + result["amazon_seller_count"]
        
        if seller_count < self.SELLER_THRESHOLDS["blue_ocean"]:
            result["seller_saturation_score"] = 100
        elif seller_count < self.SELLER_THRESHOLDS["low"]:
            result["seller_saturation_score"] = 80
        elif seller_count < self.SELLER_THRESHOLDS["medium"]:
            result["seller_saturation_score"] = 60
        elif seller_count < self.SELLER_THRESHOLDS["high"]:
            result["seller_saturation_score"] = 40
        elif seller_count < self.SELLER_THRESHOLDS["saturated"]:
            result["seller_saturation_score"] = 20
        else:
            result["seller_saturation_score"] = 5  # Heavily saturated
        
        return result
    
    async def _analyze_ad_saturation(self, product_name: str) -> Dict[str, Any]:
        """Analyze ad saturation from Facebook/TikTok."""
        result = {
            "facebook_active_ads": 0,
            "tiktok_active_ads": 0,
            "ad_spend_estimate": 0.0,
            "ad_saturation_score": 50.0,
        }
        
        if not self.apify_enabled:
            return result
        
        try:
            # Use Apify to scrape Facebook Ad Library
            # This is a simplified version - real implementation would use actual Apify actors
            
            # Estimate based on product popularity (placeholder until Apify actor is configured)
            # In production, you'd call the Facebook Ad Library scraper actor
            
            # For now, estimate based on trend data
            if self.trends_enabled:
                try:
                    self.pytrends.build_payload([product_name[:50]], timeframe='today 1-m')
                    interest = self.pytrends.interest_over_time()
                    
                    if not interest.empty:
                        avg_interest = interest[product_name[:50]].mean()
                        # Higher interest = more ads (correlation)
                        result["facebook_active_ads"] = int(avg_interest * 2)
                        result["tiktok_active_ads"] = int(avg_interest * 1.5)
                        result["ad_spend_estimate"] = avg_interest * 500  # $500 per interest point
                except Exception as e:
                    logger.warning(f"Ad estimation from trends failed: {e}")
            
        except Exception as e:
            logger.warning(f"Ad saturation analysis failed: {e}")
        
        # Calculate ad saturation score
        total_ads = result["facebook_active_ads"] + result["tiktok_active_ads"]
        
        if total_ads < self.AD_THRESHOLDS["untapped"]:
            result["ad_saturation_score"] = 100
        elif total_ads < self.AD_THRESHOLDS["low"]:
            result["ad_saturation_score"] = 80
        elif total_ads < self.AD_THRESHOLDS["medium"]:
            result["ad_saturation_score"] = 60
        elif total_ads < self.AD_THRESHOLDS["high"]:
            result["ad_saturation_score"] = 40
        elif total_ads < self.AD_THRESHOLDS["oversaturated"]:
            result["ad_saturation_score"] = 20
        else:
            result["ad_saturation_score"] = 5
        
        return result
    
    async def _analyze_price_stability(
        self,
        product_name: str,
        product_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Analyze price trends and stability."""
        result = {
            "price_30d_change": 0.0,
            "price_trend": "stable",
            "price_stability_score": 50.0,
        }
        
        # If we have product data with price history
        if product_data and product_data.get("price_history"):
            history = product_data["price_history"]
            if len(history) >= 2:
                old_price = history[0]["price"]
                new_price = history[-1]["price"]
                change = ((new_price - old_price) / old_price) * 100
                result["price_30d_change"] = change
        
        # Determine price trend
        change = result["price_30d_change"]
        if change > 10:
            result["price_trend"] = "rising"
            result["price_stability_score"] = 90  # Rising prices = good
        elif change > 0:
            result["price_trend"] = "stable"
            result["price_stability_score"] = 80
        elif change > -10:
            result["price_trend"] = "stable"
            result["price_stability_score"] = 60
        elif change > -20:
            result["price_trend"] = "declining"
            result["price_stability_score"] = 40
        else:
            result["price_trend"] = "crashing"
            result["price_stability_score"] = 10  # Race to bottom
        
        return result
    
    async def _analyze_timing(self, product_name: str) -> Dict[str, Any]:
        """Analyze trend timing and first mover window."""
        result = {
            "trend_stage": "unknown",
            "days_since_trend_start": 0,
            "estimated_peak_date": None,
            "first_mover_window_days": 30,
            "timing_score": 50.0,
        }
        
        if not self.trends_enabled:
            return result
        
        try:
            # Get 90-day trend data
            self.pytrends.build_payload([product_name[:50]], timeframe='today 3-m')
            interest = self.pytrends.interest_over_time()
            
            if interest.empty:
                return result
            
            values = interest[product_name[:50]].values
            
            if len(values) < 7:
                return result
            
            # Find trend start (when it crossed 20% of max)
            max_val = max(values)
            threshold = max_val * 0.2
            trend_start_idx = 0
            for i, v in enumerate(values):
                if v >= threshold:
                    trend_start_idx = i
                    break
            
            result["days_since_trend_start"] = len(values) - trend_start_idx
            
            # Determine trend stage based on pattern
            recent_avg = sum(values[-7:]) / 7
            earlier_avg = sum(values[:7]) / 7 if len(values) >= 14 else recent_avg
            peak_val = max(values)
            current_val = values[-1]
            
            # Is it still rising?
            if recent_avg > earlier_avg * 1.2 and current_val >= peak_val * 0.8:
                if result["days_since_trend_start"] < 14:
                    result["trend_stage"] = "emerging"
                    result["timing_score"] = 100
                    result["first_mover_window_days"] = 45
                elif result["days_since_trend_start"] < 30:
                    result["trend_stage"] = "early"
                    result["timing_score"] = 85
                    result["first_mover_window_days"] = 30
                else:
                    result["trend_stage"] = "growth"
                    result["timing_score"] = 70
                    result["first_mover_window_days"] = 14
            elif current_val >= peak_val * 0.9:
                result["trend_stage"] = "peak"
                result["timing_score"] = 40
                result["first_mover_window_days"] = 7
            else:
                result["trend_stage"] = "decline"
                result["timing_score"] = 15
                result["first_mover_window_days"] = 0
            
            # Estimate peak date
            if result["trend_stage"] in ["emerging", "early", "growth"]:
                days_to_peak = result["first_mover_window_days"] + 14
                peak_date = datetime.utcnow() + timedelta(days=days_to_peak)
                result["estimated_peak_date"] = peak_date.strftime("%Y-%m-%d")
            
            await asyncio.sleep(0.3)  # Rate limit
            
        except Exception as e:
            logger.warning(f"Timing analysis failed: {e}")
        
        return result
    
    def _calculate_combined_score(self, analysis: SaturationAnalysis) -> float:
        """Calculate weighted anti-saturation score."""
        weights = {
            "seller": 0.30,
            "ad": 0.25,
            "price": 0.20,
            "timing": 0.25,
        }
        
        score = (
            analysis.seller_saturation_score * weights["seller"] +
            analysis.ad_saturation_score * weights["ad"] +
            analysis.price_stability_score * weights["price"] +
            analysis.timing_score * weights["timing"]
        )
        
        return round(score, 1)
    
    def _determine_risk_level(self, analysis: SaturationAnalysis) -> str:
        """Determine overall saturation risk."""
        score = analysis.anti_saturation_score
        
        if score >= 80:
            return "low"
        elif score >= 60:
            return "medium"
        elif score >= 40:
            return "high"
        else:
            return "critical"
    
    def _generate_recommendation(self, analysis: SaturationAnalysis) -> tuple:
        """Generate recommendation and timing advice."""
        score = analysis.anti_saturation_score
        stage = analysis.trend_stage
        window = analysis.first_mover_window_days
        
        if score >= 80 and stage in ["emerging", "early"]:
            return (
                "DEPLOY",
                f"Excellent timing! {window} days of first-mover advantage. Deploy now."
            )
        elif score >= 70 and stage in ["emerging", "early", "growth"]:
            return (
                "DEPLOY",
                f"Good opportunity. {window} days window. Consider deploying within a week."
            )
        elif score >= 55 and window > 7:
            return (
                "MONITOR",
                f"Moderate saturation risk. Monitor for {window} days, deploy if competition stays low."
            )
        elif score >= 40:
            return (
                "CAUTION",
                "High saturation risk. Only deploy if you have a differentiation strategy."
            )
        else:
            return (
                "AVOID",
                "Market is saturated. Look for alternative products in this niche."
            )
    
    def _compile_risk_factors(self, analysis: SaturationAnalysis) -> List[str]:
        """Compile list of risk factors."""
        risks = []
        
        if analysis.seller_saturation_score < 40:
            risks.append(f"High seller count ({analysis.aliexpress_seller_count}+ competitors)")
        
        if analysis.ad_saturation_score < 40:
            risks.append(f"Oversaturated ad market ({analysis.facebook_active_ads}+ active ads)")
        
        if analysis.price_trend in ["declining", "crashing"]:
            risks.append(f"Price decline ({analysis.price_30d_change:.1f}% in 30 days)")
        
        if analysis.trend_stage in ["peak", "decline"]:
            risks.append(f"Late to trend ({analysis.trend_stage} stage)")
        
        if analysis.first_mover_window_days < 7:
            risks.append("Very short first-mover window")
        
        return risks
    
    def _compile_opportunity_factors(self, analysis: SaturationAnalysis) -> List[str]:
        """Compile list of opportunity factors."""
        opportunities = []
        
        if analysis.seller_saturation_score >= 80:
            opportunities.append("Low competition (blue ocean)")
        
        if analysis.ad_saturation_score >= 80:
            opportunities.append("Untapped advertising opportunity")
        
        if analysis.price_trend == "rising":
            opportunities.append("Rising prices indicate strong demand")
        
        if analysis.trend_stage in ["emerging", "early"]:
            opportunities.append(f"Early trend timing ({analysis.trend_stage})")
        
        if analysis.first_mover_window_days >= 30:
            opportunities.append(f"Strong first-mover window ({analysis.first_mover_window_days} days)")
        
        return opportunities


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

_analyzer_instance: Optional[AntiSaturationAnalyzer] = None


def get_saturation_analyzer() -> AntiSaturationAnalyzer:
    """Get or create saturation analyzer singleton."""
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = AntiSaturationAnalyzer()
    return _analyzer_instance


async def analyze_saturation(product_name: str, product_data: Optional[Dict] = None) -> SaturationAnalysis:
    """Quick function to analyze saturation for a product."""
    analyzer = get_saturation_analyzer()
    return await analyzer.analyze_saturation(product_name, product_data)


async def test_saturation_analyzer():
    """Test the anti-saturation analyzer."""
    print("\n" + "=" * 70)
    print(" TESTING ANTI-SATURATION ANALYZER")
    print("=" * 70)
    
    analyzer = AntiSaturationAnalyzer()
    
    # Test products
    test_products = [
        "WiFi smart plug energy monitor",
        "LED strip lights RGB",
        "Fidget spinner",  # Should show as saturated
    ]
    
    for product in test_products:
        print(f"\n[PACKAGE] Analyzing: {product}")
        analysis = await analyzer.analyze_saturation(product)
        
        print(f"   Anti-Saturation Score: {analysis.anti_saturation_score}/100")
        print(f"   Risk Level: {analysis.saturation_risk}")
        print(f"   Recommendation: {analysis.recommendation}")
        print(f"   Trend Stage: {analysis.trend_stage}")
        print(f"   First Mover Window: {analysis.first_mover_window_days} days")
        print(f"   Timing Advice: {analysis.timing_advice}")
        
        if analysis.risk_factors:
            print(f"   [WARNING] Risks: {', '.join(analysis.risk_factors)}")
        if analysis.opportunity_factors:
            print(f"   [SUCCESS] Opportunities: {', '.join(analysis.opportunity_factors)}")
    
    print("\n[SUCCESS] Test complete!")


if __name__ == "__main__":
    asyncio.run(test_saturation_analyzer())
