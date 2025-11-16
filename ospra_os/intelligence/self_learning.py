import logging
from typing import List, Dict, Optional
from collections import defaultdict
import statistics

logger = logging.getLogger(__name__)

class SelfLearningEngine:
    """
    AI-powered self-learning system that:
    - Analyzes product performance patterns
    - Identifies winning/losing characteristics
    - Recommends products based on past success
    - Predicts future performance
    - Suggests products to drop
    """

    def __init__(self, db):
        self.db = db

    def analyze_product_patterns(self, days: int = 30) -> Dict:
        """
        Analyze what makes products successful

        Returns patterns like:
        - Price range of winners
        - Categories that perform well
        - Rating thresholds
        - Order volume patterns
        """

        logger.info(f"🧠 Analyzing product patterns (last {days} days)...")

        # Get all products with performance data
        products = self._get_products_with_performance(days)

        if not products:
            logger.warning("No performance data available")
            return {}

        # Separate winners and losers
        winners = [p for p in products if self._is_winner(p)]
        losers = [p for p in products if self._is_loser(p)]

        logger.info(f"📊 Found {len(winners)} winners, {len(losers)} losers")

        # Analyze patterns
        patterns = {
            'winners': {
                'count': len(winners),
                'avg_price': self._avg([p['price'] for p in winners]) if winners else 0,
                'avg_rating': self._avg([p['rating'] for p in winners]) if winners else 0,
                'avg_orders': self._avg([p['orders'] for p in winners]) if winners else 0,
                'avg_conversion': self._avg([p['conversion_rate'] for p in winners]) if winners else 0,
                'common_categories': self._get_common_values([p['category'] for p in winners]),
                'price_range': self._get_range([p['price'] for p in winners]) if winners else (0, 0)
            },
            'losers': {
                'count': len(losers),
                'avg_price': self._avg([p['price'] for p in losers]) if losers else 0,
                'avg_rating': self._avg([p['rating'] for p in losers]) if losers else 0,
                'avg_orders': self._avg([p['orders'] for p in losers]) if losers else 0,
                'avg_conversion': self._avg([p['conversion_rate'] for p in losers]) if losers else 0,
                'common_categories': self._get_common_values([p['category'] for p in losers]),
                'price_range': self._get_range([p['price'] for p in losers]) if losers else (0, 0)
            },
            'insights': self._generate_insights(winners, losers)
        }

        return patterns

    def recommend_products(self, candidate_products: List[Dict], top_n: int = 10) -> List[Dict]:
        """
        Score and rank products based on learned patterns

        Returns: Top N products most likely to succeed
        """

        logger.info(f"🎯 Scoring {len(candidate_products)} products...")

        # Get learned patterns
        patterns = self.analyze_product_patterns()

        if not patterns or not patterns.get('winners'):
            logger.warning("No patterns learned yet, using basic scoring")
            return sorted(candidate_products, key=lambda x: x.get('score', 0), reverse=True)[:top_n]

        # Score each product
        scored = []
        for product in candidate_products:
            score = self._calculate_success_probability(product, patterns)
            product['predicted_score'] = score
            product['recommendation_reason'] = self._explain_score(product, patterns)
            scored.append(product)

        # Sort by predicted score
        scored.sort(key=lambda x: x['predicted_score'], reverse=True)

        logger.info(f"✅ Top product predicted score: {scored[0]['predicted_score']:.1f}/100")

        return scored[:top_n]

    def identify_products_to_drop(self, min_views: int = 100, days: int = 30) -> List[Dict]:
        """
        Find products performing poorly that should be dropped

        Criteria:
        - Low conversion rate (< 1%)
        - Enough views to be statistically significant
        - Consistently poor performance
        """

        logger.info("🔍 Identifying underperforming products...")

        underperformers = self.db.get_underperformers(threshold_conversion=1.0, days=days)

        # Filter for statistical significance
        significant = [p for p in underperformers if p['views'] >= min_views]

        # Add drop recommendations
        for product in significant:
            product['drop_reason'] = self._generate_drop_reason(product)
            product['replacement_suggestions'] = self._suggest_replacements(product)

        logger.info(f"🎯 Found {len(significant)} products to consider dropping")

        return significant

    def predict_performance(self, product: Dict) -> Dict:
        """
        Predict how a product will perform based on historical patterns

        Returns:
        - predicted_conversion_rate
        - predicted_sales_per_month
        - confidence_score
        - risk_factors
        """

        patterns = self.analyze_product_patterns()

        if not patterns or not patterns.get('winners'):
            return {
                'predicted_conversion_rate': 2.0,
                'predicted_sales_per_month': 10,
                'confidence_score': 30,
                'risk_factors': ['Insufficient historical data']
            }

        # Calculate predictions
        success_probability = self._calculate_success_probability(product, patterns)

        # Estimate conversion based on similar products
        winners = patterns['winners']
        baseline_conversion = winners['avg_conversion']

        # Adjust based on product attributes
        predicted_conversion = baseline_conversion * (success_probability / 50)

        # Estimate monthly sales (views * conversion * typical traffic)
        estimated_monthly_views = 500  # Baseline assumption
        predicted_sales = int(estimated_monthly_views * (predicted_conversion / 100))

        # Identify risk factors
        risk_factors = []

        if product['price'] < patterns['winners']['price_range'][0]:
            risk_factors.append('Price below winning range')
        if product['price'] > patterns['winners']['price_range'][1]:
            risk_factors.append('Price above winning range')
        if product['rating'] < winners['avg_rating']:
            risk_factors.append('Rating below average winners')
        if product['category'] not in winners['common_categories'][:3]:
            risk_factors.append('Category not proven')

        confidence = max(0, min(100, success_probability - len(risk_factors) * 10))

        return {
            'predicted_conversion_rate': round(predicted_conversion, 2),
            'predicted_sales_per_month': predicted_sales,
            'confidence_score': int(confidence),
            'risk_factors': risk_factors,
            'success_probability': int(success_probability)
        }

    def learn_from_outcome(self, product_id: str, actual_performance: Dict):
        """
        Learn from actual product performance to improve future predictions

        This creates a feedback loop for continuous improvement
        """

        logger.info(f"📚 Learning from product {product_id} performance...")

        # Get product details
        product = self.db.get_product_by_id(product_id)
        if not product:
            return

        # Get prediction that was made
        prediction = self.predict_performance(product)

        # Compare prediction vs reality
        predicted_conversion = prediction['predicted_conversion_rate']
        actual_conversion = actual_performance.get('conversion_rate', 0)

        error = abs(predicted_conversion - actual_conversion)

        # Log learning data (could be used to refine algorithms)
        logger.info(f"📊 Prediction accuracy:")
        logger.info(f"   Predicted: {predicted_conversion:.2f}%")
        logger.info(f"   Actual: {actual_conversion:.2f}%")
        logger.info(f"   Error: {error:.2f}%")

        # Store learning data for future model improvements
        # (This would feed into ML model training in advanced version)

        return {
            'product_id': product_id,
            'predicted': predicted_conversion,
            'actual': actual_conversion,
            'error': error,
            'accuracy': max(0, 100 - error * 10)
        }

    # Helper methods

    def _get_products_with_performance(self, days: int) -> List[Dict]:
        """Get all products with performance data"""

        try:
            # Get deployed products
            self.db.cursor.execute("""
                SELECT
                    p.id, p.name, p.price, p.rating, p.orders, p.category,
                    pd.shopify_product_id,
                    COALESCE(SUM(CASE WHEN pp.metric_type = 'views' THEN pp.metric_value ELSE 0 END), 0) as views,
                    COALESCE(SUM(CASE WHEN pp.metric_type = 'sales' THEN pp.metric_value ELSE 0 END), 0) as sales
                FROM products p
                LEFT JOIN product_deployments pd ON p.id = pd.product_id AND pd.status = 'active'
                LEFT JOIN product_performance pp ON p.id = pp.product_id
                    AND pp.date >= date('now', '-' || ? || ' days')
                WHERE pd.product_id IS NOT NULL
                GROUP BY p.id
            """, (days,))

            products = []
            for row in self.db.cursor.fetchall():
                views = row[7]
                sales = row[8]
                conversion = (sales / views * 100) if views > 0 else 0

                products.append({
                    'id': row[0],
                    'name': row[1],
                    'price': row[2],
                    'rating': row[3],
                    'orders': row[4],
                    'category': row[5],
                    'views': views,
                    'sales': sales,
                    'conversion_rate': conversion
                })

            return products

        except Exception as e:
            logger.error(f"Failed to get products with performance: {e}")
            return []

    def _is_winner(self, product: Dict) -> bool:
        """Determine if product is a winner"""
        return (
            product['conversion_rate'] >= 2.5 and
            product['views'] >= 50 and
            product['sales'] >= 2
        )

    def _is_loser(self, product: Dict) -> bool:
        """Determine if product is a loser"""
        return (
            product['conversion_rate'] < 1.0 and
            product['views'] >= 100
        )

    def _avg(self, values: List[float]) -> float:
        """Calculate average"""
        return statistics.mean(values) if values else 0

    def _get_range(self, values: List[float]) -> tuple:
        """Get min/max range"""
        if not values:
            return (0, 0)
        return (min(values), max(values))

    def _get_common_values(self, values: List[str]) -> List[str]:
        """Get most common values"""
        counts = defaultdict(int)
        for v in values:
            counts[v] += 1
        return sorted(counts.keys(), key=lambda x: counts[x], reverse=True)

    def _calculate_success_probability(self, product: Dict, patterns: Dict) -> float:
        """Calculate 0-100 score for success probability"""

        winners = patterns['winners']
        score = 50.0  # Start at neutral

        # Price similarity
        winner_price_avg = winners['avg_price']
        price_diff = abs(product['price'] - winner_price_avg) / winner_price_avg
        score += (1 - min(price_diff, 1.0)) * 15

        # Rating boost
        if product['rating'] >= winners['avg_rating']:
            score += 10

        # Order volume indicator
        if product.get('orders', 0) >= winners['avg_orders']:
            score += 10

        # Category match
        if product.get('category') in winners['common_categories'][:3]:
            score += 15

        return min(100, max(0, score))

    def _explain_score(self, product: Dict, patterns: Dict) -> str:
        """Generate human-readable explanation"""

        reasons = []
        winners = patterns['winners']

        if product['price'] >= winners['price_range'][0] and product['price'] <= winners['price_range'][1]:
            reasons.append("Price in winning range")

        if product['rating'] >= winners['avg_rating']:
            reasons.append("High customer rating")

        if product.get('category') in winners['common_categories'][:3]:
            reasons.append("Proven category")

        return " • ".join(reasons) if reasons else "No strong indicators"

    def _generate_drop_reason(self, product: Dict) -> str:
        """Explain why product should be dropped"""

        reasons = []

        if product['conversion_rate'] < 0.5:
            reasons.append(f"Very low conversion ({product['conversion_rate']:.1f}%)")
        elif product['conversion_rate'] < 1.0:
            reasons.append(f"Low conversion ({product['conversion_rate']:.1f}%)")

        if product['views'] > 200:
            reasons.append(f"Sufficient data ({product['views']} views)")

        if product['sales'] == 0:
            reasons.append("Zero sales")

        return " • ".join(reasons)

    def _suggest_replacements(self, product: Dict) -> List[str]:
        """Suggest what to try instead"""

        suggestions = []

        # Analyze what went wrong
        if product['price'] > 50:
            suggestions.append("Try lower price point ($25-$40)")

        if product['rating'] < 4.0:
            suggestions.append("Find products with 4.5+ ratings")

        suggestions.append(f"Look for proven winners in {product['category']}")

        return suggestions

    def _generate_insights(self, winners: List[Dict], losers: List[Dict]) -> List[str]:
        """Generate actionable insights from patterns"""

        insights = []

        if winners and losers:
            winner_avg_price = self._avg([p['price'] for p in winners])
            loser_avg_price = self._avg([p['price'] for p in losers])

            if winner_avg_price < loser_avg_price * 0.8:
                insights.append(f"Winners average ${winner_avg_price:.2f} vs losers ${loser_avg_price:.2f} - lower prices perform better")
            elif winner_avg_price > loser_avg_price * 1.2:
                insights.append(f"Winners average ${winner_avg_price:.2f} vs losers ${loser_avg_price:.2f} - premium pricing works")

            winner_categories = self._get_common_values([p['category'] for p in winners])
            if winner_categories:
                insights.append(f"Top performing category: {winner_categories[0]}")

            winner_rating = self._avg([p['rating'] for p in winners])
            loser_rating = self._avg([p['rating'] for p in losers])

            if winner_rating > loser_rating + 0.3:
                insights.append(f"Winners have {winner_rating:.1f}★ rating vs losers {loser_rating:.1f}★ - prioritize highly rated products")

        if not insights:
            insights.append("Need more performance data to generate insights")

        return insights
