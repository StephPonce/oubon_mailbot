"""
Recently Trending Product Filter

Identifies products in early/peak trend phase:
- Recent spike in Google Trends (last 7-30 days)
- Accelerating order velocity on AliExpress
- Rising social mentions
- NOT yet saturated (under 50k orders)

This catches products BEFORE everyone else jumps in.
"""

from typing import List, Dict, Optional
from datetime import datetime, timedelta
import asyncio
from pytrends.request import TrendReq


class RecentlyTrendingFilter:
    """
    Filters for products trending UP in the last 7-30 days
    
    Trend phases:
    - EMERGING: Just starting (0-7 days trending)
    - RISING: Accelerating (7-30 days trending)
    - PEAK: At maximum (30-60 days trending)
    - DECLINING: Falling off (60+ days trending)
    
    We want EMERGING and RISING only (first movers win)
    """
    
    def __init__(self):
        self.pytrends = TrendReq(hl='en-US', tz=360)
        
        # Thresholds for "recently trending"
        self.RECENT_DAYS = 30  # Look back 30 days
        self.MIN_GROWTH_RATE = 20  # Minimum 20% growth vs previous period
        self.MAX_ORDERS_THRESHOLD = 50000  # Not yet saturated
        
    async def filter_recently_trending(
        self, 
        products: List[Dict],
        min_growth_rate: float = 20.0,
        max_days_trending: int = 30
    ) -> List[Dict]:
        """
        Filter products to only show recently trending ones
        
        Args:
            products: List of product dicts
            min_growth_rate: Minimum % growth required (default: 20%)
            max_days_trending: Maximum days since trend started (default: 30)
        
        Returns:
            Filtered list with only recently trending products
        """
        recently_trending = []
        
        for product in products:
            trend_analysis = await self._analyze_recent_trend(
                product_name=product['name'],
                aliexpress_orders=product.get('orders', 0)
            )
            
            if trend_analysis['is_recently_trending']:
                # Add trend metadata to product
                product['trend_phase'] = trend_analysis['phase']
                product['trend_growth_rate'] = trend_analysis['growth_rate']
                product['days_trending'] = trend_analysis['days_trending']
                product['trend_velocity'] = trend_analysis['velocity']
                
                recently_trending.append(product)
        
        # Sort by velocity (fastest growing first)
        recently_trending.sort(
            key=lambda p: p.get('trend_velocity', 0), 
            reverse=True
        )
        
        return recently_trending
    
    async def _analyze_recent_trend(
        self, 
        product_name: str, 
        aliexpress_orders: int
    ) -> Dict:
        """
        Analyze if product is recently trending
        
        Returns:
            {
                'is_recently_trending': bool,
                'phase': 'EMERGING' | 'RISING' | 'PEAK' | 'DECLINING',
                'growth_rate': float,
                'days_trending': int,
                'velocity': float  # Rate of growth (higher = faster)
            }
        """
        try:
            # Get Google Trends data for last 90 days
            trends_data = await self._get_google_trends_recent(product_name)
            
            if not trends_data:
                return {
                    'is_recently_trending': False,
                    'phase': 'UNKNOWN',
                    'growth_rate': 0,
                    'days_trending': 0,
                    'velocity': 0
                }
            
            # Calculate trend metrics
            recent_30_days = trends_data[-30:]  # Last 30 days
            previous_30_days = trends_data[-60:-30]  # 30-60 days ago
            
            recent_avg = sum(recent_30_days) / len(recent_30_days)
            previous_avg = sum(previous_30_days) / len(previous_30_days) if previous_30_days else recent_avg
            
            # Calculate growth rate
            growth_rate = ((recent_avg - previous_avg) / previous_avg * 100) if previous_avg > 0 else 0
            
            # Calculate velocity (how fast it's accelerating)
            last_7_days = trends_data[-7:]
            previous_7_days = trends_data[-14:-7]
            
            last_week_avg = sum(last_7_days) / len(last_7_days)
            prev_week_avg = sum(previous_7_days) / len(previous_7_days) if previous_7_days else last_week_avg
            
            velocity = ((last_week_avg - prev_week_avg) / prev_week_avg * 100) if prev_week_avg > 0 else 0
            
            # Determine trend phase
            phase = self._determine_trend_phase(
                trends_data=trends_data,
                aliexpress_orders=aliexpress_orders
            )
            
            # Calculate days trending (when did trend start?)
            days_trending = self._calculate_days_trending(trends_data)
            
            # Check if recently trending
            is_recently_trending = (
                growth_rate >= self.MIN_GROWTH_RATE and
                days_trending <= self.RECENT_DAYS and
                aliexpress_orders < self.MAX_ORDERS_THRESHOLD and
                phase in ['EMERGING', 'RISING']
            )
            
            return {
                'is_recently_trending': is_recently_trending,
                'phase': phase,
                'growth_rate': round(growth_rate, 1),
                'days_trending': days_trending,
                'velocity': round(velocity, 1)
            }
            
        except Exception as e:
            print(f"Error analyzing trend for {product_name}: {e}")
            return {
                'is_recently_trending': False,
                'phase': 'ERROR',
                'growth_rate': 0,
                'days_trending': 0,
                'velocity': 0
            }
    
    async def _get_google_trends_recent(self, product_name: str) -> List[int]:
        """
        Get Google Trends data for last 90 days (daily granularity)
        
        Returns list of interest scores [0-100] for each day
        """
        try:
            # Build timeframe: last 90 days
            end_date = datetime.now()
            start_date = end_date - timedelta(days=90)
            timeframe = f"{start_date.strftime('%Y-%m-%d')} {end_date.strftime('%Y-%m-%d')}"
            
            # Get trends data
            await asyncio.sleep(1)  # Rate limit
            
            self.pytrends.build_payload(
                [product_name], 
                cat=0, 
                timeframe=timeframe,
                geo='US'
            )
            
            interest_over_time_df = self.pytrends.interest_over_time()
            
            if interest_over_time_df.empty:
                return []
            
            # Return list of interest scores
            return interest_over_time_df[product_name].tolist()
            
        except Exception as e:
            print(f"Error fetching trends for {product_name}: {e}")
            return []
    
    def _determine_trend_phase(
        self, 
        trends_data: List[int], 
        aliexpress_orders: int
    ) -> str:
        """
        Determine what phase of trend curve product is in
        
        EMERGING: Interest just starting to spike
        RISING: Interest accelerating rapidly
        PEAK: Interest at maximum (might be too late)
        DECLINING: Interest falling off
        """
        if len(trends_data) < 30:
            return 'UNKNOWN'
        
        # Compare recent vs older periods
        last_7_days = sum(trends_data[-7:]) / 7
        days_8_14 = sum(trends_data[-14:-7]) / 7
        days_15_30 = sum(trends_data[-30:-15]) / 15
        
        # EMERGING: Low orders, but interest spiking
        if aliexpress_orders < 5000 and last_7_days > days_8_14 * 1.5:
            return 'EMERGING'
        
        # RISING: Moderate orders, strong upward trajectory
        if aliexpress_orders < 20000 and last_7_days > days_15_30 * 1.3:
            return 'RISING'
        
        # PEAK: High orders, interest plateauing
        if aliexpress_orders > 30000 or abs(last_7_days - days_8_14) < 5:
            return 'PEAK'
        
        # DECLINING: Interest dropping
        if last_7_days < days_8_14 * 0.8:
            return 'DECLINING'
        
        return 'STABLE'
    
    def _calculate_days_trending(self, trends_data: List[int]) -> int:
        """
        Calculate how many days ago the trend started
        
        Looks for the inflection point where interest started rising
        """
        if len(trends_data) < 14:
            return 0
        
        # Find the point where interest started consistently rising
        baseline = sum(trends_data[:30]) / 30 if len(trends_data) >= 30 else sum(trends_data) / len(trends_data)
        
        # Look backwards from today to find when trend started
        for i in range(len(trends_data) - 1, 0, -1):
            if trends_data[i] < baseline * 1.2:
                # Found the start of trend
                return len(trends_data) - i
        
        return len(trends_data)  # Trending for entire period
    
    async def get_emerging_products(self, products: List[Dict]) -> List[Dict]:
        """
        Get ONLY emerging products (just starting to trend)
        
        Perfect for first movers - catch products before everyone else
        """
        filtered = await self.filter_recently_trending(products)
        
        # Only return EMERGING phase
        emerging = [p for p in filtered if p.get('trend_phase') == 'EMERGING']
        
        return emerging
    
    async def get_rising_products(self, products: List[Dict]) -> List[Dict]:
        """
        Get ONLY rising products (accelerating fast)
        
        Still early enough to profit, but with more validation
        """
        filtered = await self.filter_recently_trending(products)
        
        # Only return RISING phase
        rising = [p for p in filtered if p.get('trend_phase') == 'RISING']
        
        return rising


# Convenience functions for API integration

async def filter_emerging_products(products: List[Dict]) -> List[Dict]:
    """Filter for EMERGING products only (just starting to trend)"""
    filter_engine = RecentlyTrendingFilter()
    return await filter_engine.get_emerging_products(products)


async def filter_rising_products(products: List[Dict]) -> List[Dict]:
    """Filter for RISING products only (accelerating fast)"""
    filter_engine = RecentlyTrendingFilter()
    return await filter_engine.get_rising_products(products)


async def filter_recently_trending(products: List[Dict]) -> List[Dict]:
    """Filter for all recently trending products (EMERGING + RISING)"""
    filter_engine = RecentlyTrendingFilter()
    return await filter_engine.filter_recently_trending(products)
