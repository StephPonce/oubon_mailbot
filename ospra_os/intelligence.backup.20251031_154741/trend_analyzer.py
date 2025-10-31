"""
Enhanced Trend Analysis System
Integrates Google Trends, Instagram, TikTok for comprehensive product intelligence
"""

import os
import logging
from typing import Dict, Optional, List
from datetime import datetime, timedelta
import asyncio

logger = logging.getLogger(__name__)

# Google Trends
try:
    from pytrends.request import TrendReq
    HAS_PYTRENDS = True
except ImportError:
    HAS_PYTRENDS = False
    logger.warning("pytrends not installed. Run: pip install pytrends")


class TrendAnalyzer:
    """
    Multi-platform trend analysis
    - Google Trends (search momentum)
    - Instagram (hashtag popularity)
    - TikTok (video views)
    """

    def __init__(self):
        # Google Trends
        if HAS_PYTRENDS:
            try:
                self.pytrends = TrendReq(hl='en-US', tz=360)
                logger.info("✅ Google Trends initialized")
            except Exception as e:
                logger.warning(f"⚠️  Google Trends init failed: {e}")
                self.pytrends = None
        else:
            self.pytrends = None

        # Instagram Graph API
        self.instagram_token = os.getenv('INSTAGRAM_ACCESS_TOKEN')
        if self.instagram_token:
            logger.info("✅ Instagram API token found")
        else:
            logger.warning("⚠️  INSTAGRAM_ACCESS_TOKEN not set")

        # TikTok API
        self.tiktok_client_key = os.getenv('TIKTOK_CLIENT_KEY')
        if self.tiktok_client_key:
            logger.info("✅ TikTok API credentials found")
        else:
            logger.warning("⚠️  TIKTOK_CLIENT_KEY not set")

    async def analyze_product_trends(self, product: Dict) -> Dict:
        """
        Comprehensive trend analysis for a product
        Returns enriched data for AI analysis
        """
        product_name = product.get('name', '')
        niche = product.get('niche', '')

        trend_data = {
            'google_trends': await self._get_google_trends(product_name, niche),
            'instagram_data': await self._get_instagram_data(product_name),
            'tiktok_data': await self._get_tiktok_data(product_name),
            'aliexpress_metrics': self._extract_aliexpress_metrics(product),
            'market_signals': self._calculate_market_signals(product)
        }

        return trend_data

    async def _get_google_trends(self, product_name: str, niche: str) -> Dict:
        """
        Get Google Trends data for product/niche
        """
        if not self.pytrends:
            return {'available': False, 'reason': 'pytrends not installed'}

        try:
            # Extract key search terms
            keywords = self._extract_keywords(product_name, niche)[:5]  # Max 5 keywords

            if not keywords:
                return {'available': False, 'reason': 'no keywords'}

            # Build payload (last 90 days)
            self.pytrends.build_payload(
                keywords,
                timeframe='today 3-m',  # Last 3 months
                geo='US'
            )

            # Get interest over time
            interest_over_time = self.pytrends.interest_over_time()

            if interest_over_time.empty:
                return {'available': False, 'reason': 'no data'}

            # Calculate trends
            latest_values = {}
            momentum = {}

            for keyword in keywords:
                if keyword in interest_over_time.columns:
                    values = interest_over_time[keyword].values
                    latest_values[keyword] = int(values[-1]) if len(values) > 0 else 0

                    # Calculate momentum (% change over period)
                    if len(values) >= 2:
                        start_avg = values[:len(values)//3].mean()
                        end_avg = values[-len(values)//3:].mean()
                        if start_avg > 0:
                            momentum[keyword] = round(((end_avg - start_avg) / start_avg) * 100, 1)
                        else:
                            momentum[keyword] = 0
                    else:
                        momentum[keyword] = 0

            # Overall trend direction
            primary_keyword = keywords[0]
            trend_direction = 'RISING' if momentum.get(primary_keyword, 0) > 10 else \
                            'FALLING' if momentum.get(primary_keyword, 0) < -10 else 'STABLE'

            return {
                'available': True,
                'keywords': keywords,
                'interest_scores': latest_values,
                'momentum': momentum,
                'trend_direction': trend_direction,
                'primary_momentum': momentum.get(primary_keyword, 0)
            }

        except Exception as e:
            logger.error(f"Google Trends error: {e}")
            return {'available': False, 'reason': str(e)}

    async def _get_instagram_data(self, product_name: str) -> Dict:
        """
        Get Instagram hashtag data
        Note: Requires Instagram Graph API setup
        """
        if not self.instagram_token:
            return {'available': False, 'reason': 'no_token'}

        try:
            import aiohttp

            # Extract hashtags from product name
            hashtags = self._extract_hashtags(product_name)

            # For now, return placeholder - full implementation requires Business account
            # Instagram Graph API requires Business/Creator account with approved permissions
            return {
                'available': False,
                'reason': 'requires_business_account',
                'note': 'Instagram Graph API requires Business account with approved permissions',
                'potential_hashtags': hashtags
            }

        except Exception as e:
            logger.error(f"Instagram API error: {e}")
            return {'available': False, 'reason': str(e)}

    async def _get_tiktok_data(self, product_name: str) -> Dict:
        """
        Get TikTok trending data
        Note: Requires TikTok API setup
        """
        if not self.tiktok_client_key:
            return {'available': False, 'reason': 'no_credentials'}

        # TikTok API requires OAuth flow - placeholder for now
        return {
            'available': False,
            'reason': 'requires_oauth',
            'note': 'TikTok API requires OAuth authentication flow'
        }

    def _extract_aliexpress_metrics(self, product: Dict) -> Dict:
        """
        Extract and format AliExpress metrics
        """
        orders = product.get('orders', 0)
        rating = product.get('rating', 0)
        price = product.get('price', 0)
        supplier_rating = product.get('supplier_rating', 0)

        # Calculate velocity (orders per day estimate)
        # Assuming products have been on sale for ~1 year on average
        estimated_velocity = round(orders / 365, 1) if orders > 0 else 0

        return {
            'total_orders': orders,
            'rating': rating,
            'price': price,
            'supplier_rating': supplier_rating,
            'estimated_daily_orders': estimated_velocity,
            'monthly_orders_estimate': round(estimated_velocity * 30),
            'revenue_estimate_monthly': round(price * estimated_velocity * 30, 2)
        }

    def _calculate_market_signals(self, product: Dict) -> Dict:
        """
        Calculate market opportunity signals
        """
        orders = product.get('orders', 0)
        rating = product.get('rating', 0)
        score = product.get('score', 0)

        # Market saturation estimate (simplified)
        saturation = 'LOW' if orders < 5000 else 'MEDIUM' if orders < 20000 else 'HIGH'

        # Competition level
        competition = 'LOW' if orders < 10000 else 'MEDIUM' if orders < 50000 else 'HIGH'

        # Demand strength
        demand = 'HIGH' if orders > 20000 and rating > 4.5 else \
                'MEDIUM' if orders > 5000 and rating > 4.0 else 'LOW'

        return {
            'saturation_level': saturation,
            'competition_level': competition,
            'demand_strength': demand,
            'overall_opportunity': 'HIGH' if score > 8 else 'MEDIUM' if score > 6 else 'LOW'
        }

    def _extract_keywords(self, product_name: str, niche: str) -> List[str]:
        """
        Extract search keywords from product name and niche
        """
        keywords = []

        # Add niche
        if niche:
            keywords.append(niche.lower())

        # Extract key terms from product name
        name_lower = product_name.lower()

        # Common product type keywords
        product_types = ['smart', 'wifi', 'wireless', 'bluetooth', 'led', 'portable',
                        'mini', 'pro', 'ultra', 'rechargeable', 'solar', 'robot']

        for ptype in product_types:
            if ptype in name_lower:
                keywords.append(ptype)
                break

        # Extract main product category
        categories = ['light', 'camera', 'speaker', 'vacuum', 'thermostat', 'plug',
                     'bulb', 'strip', 'sensor', 'lock', 'doorbell', 'monitor']

        for category in categories:
            if category in name_lower:
                keywords.append(category)
                break

        return list(set(keywords))[:5]  # Return unique, max 5

    def _extract_hashtags(self, product_name: str) -> List[str]:
        """
        Generate potential Instagram hashtags
        """
        name_lower = product_name.lower().replace('-', ' ')
        words = name_lower.split()

        # Remove common words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'with', 'for', 'to', 'of'}
        keywords = [w for w in words if w not in stop_words and len(w) > 3]

        # Generate hashtags
        hashtags = [f"#{w}" for w in keywords[:5]]

        # Add category hashtags
        if 'smart' in name_lower:
            hashtags.append('#smarthome')
        if any(word in name_lower for word in ['light', 'led', 'bulb']):
            hashtags.append('#lighting')
        if 'security' in name_lower or 'camera' in name_lower:
            hashtags.append('#homesecurity')

        return hashtags[:8]  # Max 8 hashtags
