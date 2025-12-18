"""
ProductIntelligenceEngine V4 - REAL AliExpress API Integration
Fetches ACTUAL products from AliExpress with real prices, images, and data
No more hardcoded demo data!
"""

import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging
import hashlib

logger = logging.getLogger(__name__)

# Import AliExpress client
try:
    from ospra_os.integrations.aliexpress.client import AliExpressClient
    ALIEXPRESS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"AliExpress client not available: {e}")
    ALIEXPRESS_AVAILABLE = False
    AliExpressClient = None

# Import market analyzer (optional)
try:
    from .comprehensive_market_analysis import ComprehensiveMarketAnalyzer
    ANALYZER_AVAILABLE = True
except ImportError:
    ANALYZER_AVAILABLE = False
    ComprehensiveMarketAnalyzer = None

# Import saturation tracker (optional)
try:
    from .saturation_tracker import SaturationTracker
    SATURATION_AVAILABLE = True
except ImportError:
    SATURATION_AVAILABLE = False
    SaturationTracker = None


class ProductIntelligenceEngine:
    """
    V4: Production engine with REAL AliExpress API integration
    
    Features:
    - Fetches real products from AliExpress API
    - Real prices, images, ratings, and order counts
    - Accurate profit calculations with all fees
    - Niche-based discovery with smart keywords
    """

    # Niche to search keyword mapping
    NICHE_KEYWORDS = {
        'smart_home': ['smart home', 'wifi switch', 'smart bulb', 'home automation', 'smart plug', 'led strip wifi', 'smart sensor', 'zigbee'],
        'fitness': ['fitness equipment', 'resistance bands', 'yoga mat', 'home gym', 'exercise', 'workout', 'massage gun', 'foam roller'],
        'tech_accessories': ['phone accessories', 'usb hub', 'wireless charger', 'phone stand', 'cable organizer', 'power bank'],
        'home_office': ['desk accessories', 'monitor stand', 'ergonomic', 'laptop stand', 'desk lamp led', 'webcam'],
        'kitchen': ['kitchen gadgets', 'kitchen organizer', 'food storage', 'cooking tools', 'kitchen accessories'],
        'beauty': ['beauty tools', 'skincare device', 'makeup organizer', 'facial massager', 'led mirror'],
        'pet': ['pet supplies', 'dog accessories', 'cat toys', 'pet feeder', 'pet grooming'],
        'outdoor': ['camping gear', 'hiking accessories', 'outdoor equipment', 'portable', 'travel accessories'],
        'lighting': ['led lights', 'ambient lighting', 'desk lamp', 'night light', 'strip lights'],
        'gaming': ['gaming accessories', 'rgb lights', 'gaming desk', 'controller', 'headset stand'],
    }

    # Shipping cost tiers (China to US via ePacket/AliExpress Standard)
    SHIPPING_TIERS = {
        'small': 2.50,   # < $15 items
        'medium': 4.00,  # $15-$40 items
        'large': 7.00,   # $40-$100 items
        'heavy': 12.00   # > $100 items
    }

    def __init__(self, claude_client=None, database_url: Optional[str] = None, enable_saturation_tracking: bool = True):
        self.claude = claude_client
        
        # Initialize AliExpress client
        self.aliexpress_client = None
        if ALIEXPRESS_AVAILABLE:
            try:
                self.aliexpress_client = AliExpressClient(use_affiliate=True)
                logger.info("✅ AliExpress API client initialized")
            except Exception as e:
                logger.warning(f"⚠️ AliExpress client init failed: {e}")
        
        # Initialize market analyzer
        self.market_analyzer = None
        if ANALYZER_AVAILABLE and ComprehensiveMarketAnalyzer:
            try:
                self.market_analyzer = ComprehensiveMarketAnalyzer()
            except Exception as e:
                logger.warning(f"Market analyzer not available: {e}")

        # Initialize saturation tracker
        self.saturation_tracker = None
        if SATURATION_AVAILABLE and SaturationTracker and database_url and enable_saturation_tracking:
            try:
                self.saturation_tracker = SaturationTracker(database_url)
                logger.info("✅ Saturation tracking enabled")
            except Exception as e:
                logger.warning(f"Saturation tracker not available: {e}")

        # Default markup for profit calculation (2.2x = 55% margin before fees)
        self.default_markup = 2.2

    def _get_shipping_cost(self, price: float) -> float:
        """Determine shipping cost based on item price tier"""
        if price < 15:
            return self.SHIPPING_TIERS['small']
        elif price < 40:
            return self.SHIPPING_TIERS['medium']
        elif price < 100:
            return self.SHIPPING_TIERS['large']
        else:
            return self.SHIPPING_TIERS['heavy']

    def _calculate_profit(self, selling_price: float, cost: float) -> Dict[str, float]:
        """
        Calculate ACCURATE net profit after ALL fees
        
        Fees included:
        - Product cost from supplier
        - Shipping from China (ePacket/AliExpress Standard)
        - Shopify transaction fee (2.9% + $0.30)
        - Payment processing (included in Shopify fee)
        """
        shipping = self._get_shipping_cost(cost)
        shopify_fee = (selling_price * 0.029) + 0.30
        
        total_costs = cost + shipping + shopify_fee
        net_profit = selling_price - total_costs
        profit_margin = (net_profit / selling_price) * 100 if selling_price > 0 else 0
        
        return {
            'selling_price': round(selling_price, 2),
            'product_cost': round(cost, 2),
            'shipping_cost': round(shipping, 2),
            'shopify_fee': round(shopify_fee, 2),
            'total_costs': round(total_costs, 2),
            'net_profit': round(net_profit, 2),
            'profit_margin': round(profit_margin, 1)
        }

    def _calculate_ai_score(self, product: Dict) -> float:
        """
        Calculate AI score (0-10) based on real metrics
        
        Factors:
        - Order volume (40% weight)
        - Rating (30% weight)
        - Profit margin (20% weight)
        - Price point attractiveness (10% weight)
        """
        orders = product.get('orders', 0)
        rating = product.get('rating', 0)
        profit_margin = product.get('profit_margin', 0)
        price = product.get('cost', 0)
        
        # Order score: 0-4 points (logarithmic scale)
        if orders > 0:
            import math
            order_score = min(4.0, math.log10(orders + 1) / 1.5)
        else:
            order_score = 0
        
        # Rating score: 0-3 points (rating out of 5, scaled)
        rating_score = (rating / 5) * 3 if rating > 0 else 0
        
        # Profit margin score: 0-2 points
        margin_score = min(2.0, profit_margin / 25) if profit_margin > 0 else 0
        
        # Price attractiveness: 0-1 point (sweet spot $10-$50)
        if 10 <= price <= 50:
            price_score = 1.0
        elif 5 <= price < 10 or 50 < price <= 100:
            price_score = 0.5
        else:
            price_score = 0.2
        
        total_score = order_score + rating_score + margin_score + price_score
        return round(min(10.0, max(0.0, total_score)), 1)

    def _generate_product_id(self, aliexpress_id: str, name: str) -> str:
        """Generate a unique product ID"""
        if aliexpress_id:
            return f"ae_{aliexpress_id}"
        # Fallback to hash of name
        return f"prod_{hashlib.md5(name.encode()).hexdigest()[:12]}"

    def _parse_aliexpress_product(self, raw_product: Dict, niche: str) -> Dict[str, Any]:
        """
        Parse AliExpress API response into our internal product format
        
        AliExpress API returns fields like:
        - product_id, product_title, product_main_image_url
        - target_sale_price, target_original_price
        - evaluate_rate (rating), lastest_volume (orders)
        - promotion_link (affiliate URL)
        """
        try:
            # Extract basic info
            ae_id = str(raw_product.get('product_id', ''))
            name = raw_product.get('product_title', 'Unknown Product')
            
            # Get image (prefer main image, fallback to small)
            image_url = (
                raw_product.get('product_main_image_url') or
                raw_product.get('product_small_image_urls', {}).get('string', [''])[0] or
                ''
            )
            
            # Get pricing (API returns as string, need to convert)
            cost_str = raw_product.get('target_sale_price', '0')
            cost = float(cost_str) if cost_str else 0
            
            original_price_str = raw_product.get('target_original_price', '0')
            original_price = float(original_price_str) if original_price_str else cost
            
            # Calculate selling price with markup
            selling_price = round(cost * self.default_markup, 2)
            
            # Get metrics
            rating_str = raw_product.get('evaluate_rate', '0')
            # Rating comes as percentage string like "96.5", convert to 0-5 scale
            try:
                rating_pct = float(rating_str.replace('%', '')) if rating_str else 0
                rating = round((rating_pct / 100) * 5, 1)
            except:
                rating = 0
            
            orders_str = raw_product.get('lastest_volume', '0')
            try:
                orders = int(orders_str) if orders_str else 0
            except:
                orders = 0
            
            # Get affiliate/product URL
            affiliate_url = raw_product.get('promotion_link', '')
            product_url = raw_product.get('product_detail_url', f"https://www.aliexpress.com/item/{ae_id}.html")
            
            # Calculate profit breakdown
            profit_data = self._calculate_profit(selling_price, cost)
            
            # Build product object
            product = {
                'id': self._generate_product_id(ae_id, name),
                'aliexpress_id': ae_id,
                'name': name,
                'niche': niche,
                'category': niche.replace('_', ' ').title(),
                
                # Pricing
                'price': profit_data['selling_price'],
                'cost': profit_data['product_cost'],
                'original_price': round(original_price, 2),
                'shipping_cost': profit_data['shipping_cost'],
                'shopify_fee': profit_data['shopify_fee'],
                'total_costs': profit_data['total_costs'],
                'estimated_profit': profit_data['net_profit'],
                'profit_margin': profit_data['profit_margin'],
                
                # Metrics
                'rating': rating,
                'orders': orders,
                'score': 0,  # Will be calculated after
                
                # URLs
                'image_url': image_url,
                'aliexpress_url': affiliate_url or product_url,
                'supplier_url': product_url,
                
                # Metadata
                'source': 'aliexpress_api',
                'created_at': datetime.now().isoformat(),
                'last_updated': datetime.now().isoformat(),
                
                # Store raw data for reference
                'raw_data': raw_product
            }
            
            # Calculate AI score
            product['score'] = self._calculate_ai_score(product)
            
            # Generate AI description
            product['description'] = self._generate_description(product)
            product['ai_reason'] = product['description']
            
            # Add display-friendly data
            product['display_data'] = {
                'name': name,
                'market_price': profit_data['selling_price'],
                'supplier_cost': profit_data['product_cost'],
                'shipping_cost': profit_data['shipping_cost'],
                'shopify_fee': profit_data['shopify_fee'],
                'profit_margin': profit_data['profit_margin'],
                'net_profit': profit_data['net_profit'],
                'supplier_orders': orders,
                'supplier_rating': rating,
                'supplier_url': product_url,
                'aliexpress_url': affiliate_url or product_url
            }
            
            return product
            
        except Exception as e:
            logger.error(f"Error parsing product: {e}")
            return None

    def _generate_description(self, product: Dict) -> str:
        """Generate AI description based on real metrics"""
        score = product.get('score', 0)
        orders = product.get('orders', 0)
        rating = product.get('rating', 0)
        margin = product.get('profit_margin', 0)
        niche = product.get('niche', '').replace('_', ' ').title()
        name = product.get('name', 'This product')
        
        # Score-based assessment
        if score >= 8:
            assessment = "Exceptional opportunity"
            recommendation = "STRONG BUY"
        elif score >= 6:
            assessment = "Strong potential"
            recommendation = "BUY"
        elif score >= 4:
            assessment = "Moderate opportunity"
            recommendation = "CONSIDER"
        else:
            assessment = "Lower priority"
            recommendation = "WATCH"
        
        # Build description
        parts = [f"{assessment} in {niche}."]
        
        if orders > 10000:
            parts.append(f"Proven demand with {orders:,}+ orders.")
        elif orders > 1000:
            parts.append(f"Good traction with {orders:,} orders.")
        elif orders > 0:
            parts.append(f"Emerging product with {orders} orders.")
        
        if rating >= 4.5:
            parts.append(f"Excellent {rating}★ rating indicates quality.")
        elif rating >= 4.0:
            parts.append(f"Solid {rating}★ customer satisfaction.")
        
        if margin >= 40:
            parts.append(f"Strong {margin:.0f}% profit margin.")
        elif margin >= 25:
            parts.append(f"Healthy {margin:.0f}% margin after fees.")
        
        parts.append(f"AI Score: {score}/10 - {recommendation}")
        
        return " ".join(parts)

    async def discover_products_real(self, niche: str, count: int = 20) -> List[Dict[str, Any]]:
        """
        Discover REAL products from AliExpress API
        
        Args:
            niche: Product niche (smart_home, fitness, etc.)
            count: Number of products to fetch
            
        Returns:
            List of parsed product dictionaries with real data
        """
        if not self.aliexpress_client:
            logger.error("AliExpress client not available")
            return []
        
        # Get search keywords for niche
        keywords_list = self.NICHE_KEYWORDS.get(niche, [niche.replace('_', ' ')])
        
        all_products = []
        products_per_keyword = max(5, count // len(keywords_list))
        
        for keyword in keywords_list:
            if len(all_products) >= count:
                break
                
            try:
                logger.info(f"🔍 Searching AliExpress: '{keyword}' for niche '{niche}'")
                
                # Search AliExpress
                raw_products = await self.aliexpress_client.search_products(
                    keywords=keyword,
                    page_size=min(20, products_per_keyword)
                )
                
                if not raw_products:
                    logger.warning(f"No products found for keyword: {keyword}")
                    continue
                
                # Parse each product
                for raw in raw_products:
                    if len(all_products) >= count:
                        break
                        
                    parsed = self._parse_aliexpress_product(raw, niche)
                    if parsed and parsed.get('cost', 0) > 0:
                        all_products.append(parsed)
                
                logger.info(f"✅ Found {len(raw_products)} products for '{keyword}'")
                
            except Exception as e:
                logger.error(f"Error searching '{keyword}': {e}")
                continue
        
        # Sort by score (best first)
        all_products.sort(key=lambda x: x.get('score', 0), reverse=True)
        
        logger.info(f"📦 Total products discovered: {len(all_products)}")
        return all_products[:count]

    async def discover_winning_products(self, niches: List[str] = None, max_per_niche: int = 20) -> List[Dict[str, Any]]:
        """
        Main discovery method - fetches REAL products from AliExpress
        
        Args:
            niches: List of niches to search
            max_per_niche: Max products per niche
            
        Returns:
            List of enriched product dictionaries
        """
        if not niches:
            niches = ['smart_home']
        
        all_products = []
        
        for niche in niches:
            try:
                products = await self.discover_products_real(niche, max_per_niche)
                all_products.extend(products)
                logger.info(f"✅ Discovered {len(products)} products for niche: {niche}")
            except Exception as e:
                logger.error(f"Error discovering {niche}: {e}")
                continue
        
        # Deduplicate by aliexpress_id
        seen_ids = set()
        unique_products = []
        for p in all_products:
            ae_id = p.get('aliexpress_id', '')
            if ae_id and ae_id not in seen_ids:
                seen_ids.add(ae_id)
                unique_products.append(p)
            elif not ae_id:
                unique_products.append(p)
        
        # Sort by score
        unique_products.sort(key=lambda x: x.get('score', 0), reverse=True)
        
        logger.info(f"🎯 Total unique products: {len(unique_products)}")
        return unique_products

    def discover_products_by_niche(self, niche: str, count: int = 20) -> List[Dict[str, Any]]:
        """Sync wrapper for discover_products_real"""
        return asyncio.run(self.discover_products_real(niche, count))

    def discover_products(self, niche: str = None, per_page: int = 20, **kwargs) -> Dict[str, Any]:
        """
        Sync discovery method for backward compatibility
        
        Returns dict with 'products', 'total', 'data_source' keys
        """
        if not niche:
            niche = 'smart_home'
        
        products = self.discover_products_by_niche(niche=niche, count=per_page)
        
        return {
            "data_source": "ALIEXPRESS_API_V4",
            "total": len(products),
            "products": products,
            "niche": niche,
            "timestamp": datetime.now().isoformat()
        }


# Create a simple sync function for easy testing
def discover_real_products(niches: List[str] = None, max_per_niche: int = 10) -> List[Dict]:
    """Quick function to discover real products"""
    engine = ProductIntelligenceEngine()
    return asyncio.run(engine.discover_winning_products(niches or ['smart_home'], max_per_niche))
