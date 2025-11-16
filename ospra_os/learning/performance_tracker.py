"""
Performance Tracker - Track Real Sales & Customer Behavior

Connects to:
- Shopify API (sales data)
- Google Analytics (customer behavior)
- Ad platforms (Facebook, TikTok, Google Ads)

Feeds data to Self-Learning Engine
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


class PerformanceTracker:
    """
    Tracks real-world performance data for learning
    """
    
    def __init__(self):
        self.sales_cache = []
        self.behavior_cache = []
        self.ad_performance_cache = []
    
    async def fetch_shopify_sales(
        self, 
        shopify_client, 
        days_back: int = 7
    ) -> List[Dict]:
        """
        Fetch recent sales from Shopify
        
        Args:
            shopify_client: ShopifyClient instance
            days_back: How many days of sales to fetch
        
        Returns:
            List of sales in format for learning engine
        """
        try:
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            # Fetch orders from Shopify
            orders = await shopify_client.get_orders(
                created_at_min=start_date.isoformat(),
                status='any'
            )
            
            # Transform to learning format
            sales_data = []
            
            for order in orders:
                for line_item in order.get('line_items', []):
                    product_id = str(line_item.get('product_id'))
                    
                    # Extract product metadata (niche, predicted score)
                    product_meta = line_item.get('properties', {})
                    
                    sale = {
                        'product_id': product_id,
                        'product_name': line_item.get('name'),
                        'niche': product_meta.get('niche', 'unknown'),
                        'price': float(line_item.get('price', 0)),
                        'units_sold': line_item.get('quantity', 1),
                        'revenue': float(line_item.get('price', 0)) * line_item.get('quantity', 1),
                        'predicted_score': float(product_meta.get('ai_score', 0)),
                        'date': order.get('created_at'),
                        'order_id': order.get('id')
                    }
                    
                    sales_data.append(sale)
            
            self.sales_cache = sales_data
            
            logger.info(f"✅ Fetched {len(sales_data)} sales from Shopify ({days_back} days)")
            
            return sales_data
        
        except Exception as e:
            logger.error(f"❌ Failed to fetch Shopify sales: {e}")
            return []
    
    async def fetch_customer_behavior(
        self,
        analytics_client,
        product_ids: List[str],
        days_back: int = 7
    ) -> List[Dict]:
        """
        Fetch customer behavior from Google Analytics
        
        Metrics:
        - Page views per product
        - Time on page
        - Add to cart rate
        - Bounce rate
        
        Args:
            analytics_client: Google Analytics client
            product_ids: List of product IDs to track
            days_back: How many days of data
        
        Returns:
            List of behavior data per product
        """
        try:
            behavior_data = []
            
            for product_id in product_ids:
                metrics = await analytics_client.get_product_metrics(
                    product_id=product_id,
                    days_back=days_back
                )
                
                behavior_data.append({
                    'product_id': product_id,
                    'page_views': metrics.get('pageviews', 0),
                    'avg_time_on_page': metrics.get('avg_time_on_page', 0),
                    'add_to_cart_rate': metrics.get('add_to_cart_rate', 0),
                    'bounce_rate': metrics.get('bounce_rate', 0),
                    'conversion_rate': metrics.get('conversion_rate', 0)
                })
            
            self.behavior_cache = behavior_data
            
            logger.info(f"✅ Fetched behavior data for {len(product_ids)} products")
            
            return behavior_data
        
        except Exception as e:
            logger.error(f"❌ Failed to fetch behavior data: {e}")
            return []
    
    async def fetch_ad_performance(
        self,
        ad_platforms: Dict,
        days_back: int = 7
    ) -> List[Dict]:
        """
        Fetch ad performance from platforms
        
        Platforms:
        - Facebook/Instagram
        - TikTok
        - Google Ads
        
        Args:
            ad_platforms: Dict of platform clients
            days_back: How many days of data
        
        Returns:
            List of ad performance per product
        """
        try:
            ad_data = []
            
            for platform_name, client in ad_platforms.items():
                campaigns = await client.get_campaigns(days_back=days_back)
                
                for campaign in campaigns:
                    product_id = campaign.get('product_id')
                    
                    ad_data.append({
                        'product_id': product_id,
                        'platform': platform_name,
                        'impressions': campaign.get('impressions', 0),
                        'clicks': campaign.get('clicks', 0),
                        'ctr': campaign.get('ctr', 0),
                        'spend': campaign.get('spend', 0),
                        'revenue': campaign.get('revenue', 0),
                        'roas': campaign.get('roas', 0),
                        'conversions': campaign.get('conversions', 0)
                    })
            
            self.ad_performance_cache = ad_data
            
            logger.info(f"✅ Fetched ad performance for {len(ad_data)} campaigns")
            
            return ad_data
        
        except Exception as e:
            logger.error(f"❌ Failed to fetch ad performance: {e}")
            return []
    
    async def get_product_performance_summary(self, product_id: str) -> Dict:
        """
        Get complete performance summary for a product
        
        Combines:
        - Sales data
        - Customer behavior
        - Ad performance
        
        Args:
            product_id: Product to analyze
        
        Returns:
            Complete performance summary
        """
        # Find sales data
        sales = [s for s in self.sales_cache if s['product_id'] == product_id]
        
        # Find behavior data
        behavior = next(
            (b for b in self.behavior_cache if b['product_id'] == product_id),
            None
        )
        
        # Find ad data
        ads = [a for a in self.ad_performance_cache if a['product_id'] == product_id]
        
        # Calculate summary
        total_units = sum(s['units_sold'] for s in sales)
        total_revenue = sum(s['revenue'] for s in sales)
        total_ad_spend = sum(a['spend'] for a in ads)
        
        return {
            'product_id': product_id,
            'sales': {
                'total_units': total_units,
                'total_revenue': round(total_revenue, 2),
                'avg_price': round(total_revenue / total_units, 2) if total_units > 0 else 0,
                'orders': len(sales)
            },
            'behavior': behavior or {},
            'ads': {
                'total_spend': round(total_ad_spend, 2),
                'total_roas': round(total_revenue / total_ad_spend, 2) if total_ad_spend > 0 else 0,
                'platforms': len(set(a['platform'] for a in ads)),
                'campaigns': len(ads)
            },
            'profitability': {
                'net_profit': round(total_revenue - total_ad_spend, 2),
                'profit_margin': round((total_revenue - total_ad_spend) / total_revenue * 100, 1) if total_revenue > 0 else 0
            }
        }
    
    async def get_learning_dataset(self) -> List[Dict]:
        """
        Prepare complete dataset for learning engine
        
        Returns:
            Sales data enriched with behavior and ad performance
        """
        learning_data = []
        
        for sale in self.sales_cache:
            product_id = sale['product_id']
            
            # Find matching behavior
            behavior = next(
                (b for b in self.behavior_cache if b['product_id'] == product_id),
                {}
            )
            
            # Find matching ads
            ads = [a for a in self.ad_performance_cache if a['product_id'] == product_id]
            total_ad_spend = sum(a['spend'] for a in ads)
            avg_roas = sum(a['roas'] for a in ads) / len(ads) if ads else 0
            
            # Enrich sale data
            enriched = {
                **sale,
                'page_views': behavior.get('page_views', 0),
                'conversion_rate': behavior.get('conversion_rate', 0),
                'ad_spend': total_ad_spend,
                'roas': avg_roas
            }
            
            learning_data.append(enriched)
        
        return learning_data
    
    async def generate_performance_report(self) -> Dict:
        """
        Generate comprehensive performance report
        
        For dashboard display and Claude analysis
        """
        # Group by niche
        niche_performance = defaultdict(lambda: {'sales': 0, 'revenue': 0.0})
        
        for sale in self.sales_cache:
            niche = sale['niche']
            niche_performance[niche]['sales'] += 1
            niche_performance[niche]['revenue'] += sale['revenue']
        
        # Top products
        product_totals = defaultdict(lambda: {'units': 0, 'revenue': 0.0})
        
        for sale in self.sales_cache:
            pid = sale['product_id']
            product_totals[pid]['units'] += sale['units_sold']
            product_totals[pid]['revenue'] += sale['revenue']
            product_totals[pid]['name'] = sale['product_name']
        
        top_products = sorted(
            [{'product_id': k, **v} for k, v in product_totals.items()],
            key=lambda x: x['revenue'],
            reverse=True
        )[:10]
        
        # Total ad performance
        total_ad_spend = sum(a['spend'] for a in self.ad_performance_cache)
        total_ad_revenue = sum(a['revenue'] for a in self.ad_performance_cache)
        
        return {
            'summary': {
                'total_sales': len(self.sales_cache),
                'total_revenue': round(sum(s['revenue'] for s in self.sales_cache), 2),
                'total_units': sum(s['units_sold'] for s in self.sales_cache),
                'total_ad_spend': round(total_ad_spend, 2),
                'overall_roas': round(total_ad_revenue / total_ad_spend, 2) if total_ad_spend > 0 else 0
            },
            'by_niche': dict(niche_performance),
            'top_products': top_products,
            'tracking_period_days': 7
        }
