"""
Self-Learning Product Intelligence Engine

This engine learns from ACTUAL RESULTS to improve predictions over time.

Learning Sources:
1. Shopify sales data (what actually sold)
2. Customer behavior (clicks, cart adds, time on page)
3. Ad performance (ROAS, CTR, conversions)
4. Prediction accuracy (did high-scored products sell well?)

Adjustments Made:
- Product scoring weights (which signals matter most)
- Niche confidence (which categories convert best)
- Price point preferences (optimal pricing ranges)
- Trend velocity importance (how much to trust recent spikes)
"""

import json
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

logger = logging.getLogger(__name__)


class SelfLearningEngine:
    """
    AI that learns from real-world performance to improve product recommendations
    """
    
    def __init__(self, data_dir: Optional[Path] = None):
        """
        Initialize learning engine
        
        Args:
            data_dir: Directory to store learning data
        """
        self.data_dir = data_dir or Path("data/learning")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Load current weights or initialize defaults
        self.weights = self._load_weights()
        
        # Track learning progress
        self.learning_history = self._load_learning_history()
        
        logger.info("✅ Self-Learning Engine initialized")
    
    def _load_weights(self) -> Dict:
        """Load current AI confidence weights"""
        weights_file = self.data_dir / "confidence_weights.json"
        
        if weights_file.exists():
            with open(weights_file) as f:
                weights = json.load(f)
                logger.info(f"📊 Loaded existing weights (last updated: {weights.get('last_updated')})")
                return weights
        
        # Default starting weights
        default_weights = {
            "version": "1.0",
            "last_updated": datetime.now().isoformat(),
            "total_learning_cycles": 0,
            
            # Product scoring weights (sum = 1.0)
            "scoring_weights": {
                "google_trends_weight": 0.25,      # Search volume importance
                "reddit_mentions_weight": 0.15,    # Social proof importance
                "aliexpress_orders_weight": 0.35,  # Supplier credibility
                "price_competitiveness_weight": 0.15,  # Competitive pricing
                "trend_velocity_weight": 0.10      # How fast it's rising
            },
            
            # Niche-specific confidence (learned over time)
            "niche_confidence": {
                "smart_home": 0.5,       # Start neutral
                "fitness": 0.5,
                "tech_accessories": 0.5,
                "home_office": 0.5
            },
            
            # Price point confidence (which price ranges sell best)
            "price_point_confidence": {
                "under_20": 0.5,
                "20_to_50": 0.5,
                "50_to_100": 0.5,
                "over_100": 0.5
            },
            
            # Trend velocity thresholds
            "trend_velocity": {
                "early_spike_threshold": 50,  # Trend score increase to trigger "early"
                "sustained_growth_days": 7,   # Days of growth to trust trend
                "decay_threshold": -20        # Decline to trigger warning
            },
            
            # Performance tracking
            "accuracy_tracking": {
                "predictions_made": 0,
                "predictions_correct": 0,
                "accuracy_rate": 0.0
            }
        }
        
        logger.info("🆕 Initialized default weights (learning from scratch)")
        return default_weights
    
    def _load_learning_history(self) -> List[Dict]:
        """Load historical learning cycles"""
        history_file = self.data_dir / "learning_history.json"
        
        if history_file.exists():
            with open(history_file) as f:
                return json.load(f)
        
        return []
    
    def save_weights(self):
        """Save updated weights to disk"""
        self.weights["last_updated"] = datetime.now().isoformat()
        
        weights_file = self.data_dir / "confidence_weights.json"
        with open(weights_file, 'w') as f:
            json.dump(self.weights, f, indent=2)
        
        logger.info("💾 Saved updated weights")
    
    def save_learning_history(self):
        """Save learning history"""
        history_file = self.data_dir / "learning_history.json"
        with open(history_file, 'w') as f:
            json.dump(self.learning_history, f, indent=2)
    
    async def learn_from_sales(self, sales_data: List[Dict]):
        """
        PRIMARY LEARNING METHOD - Learn from actual Shopify sales
        
        Updates confidence weights based on:
        - Which products actually sold
        - Which niches performed best
        - Which price points converted
        - Predicted score vs actual performance
        
        Args:
            sales_data: List of sales from Shopify API
                [
                    {
                        'product_id': str,
                        'product_name': str,
                        'niche': str,
                        'price': float,
                        'units_sold': int,
                        'revenue': float,
                        'predicted_score': float,  # What we predicted
                        'date': str
                    },
                    ...
                ]
        """
        if not sales_data:
            logger.warning("⚠️ No sales data to learn from")
            return
        
        logger.info(f"🧠 Learning from {len(sales_data)} sales...")
        
        # 1. Learn niche performance
        niche_performance = self._analyze_niche_performance(sales_data)
        self._update_niche_confidence(niche_performance)
        
        # 2. Learn optimal price points
        price_performance = self._analyze_price_points(sales_data)
        self._update_price_confidence(price_performance)
        
        # 3. Learn prediction accuracy
        accuracy = self._calculate_prediction_accuracy(sales_data)
        self._update_scoring_weights(accuracy)
        
        # 4. Increment learning cycle counter
        self.weights["total_learning_cycles"] += 1
        
        # 5. Record this learning cycle
        learning_cycle = {
            "cycle": self.weights["total_learning_cycles"],
            "timestamp": datetime.now().isoformat(),
            "sales_analyzed": len(sales_data),
            "total_revenue": sum(s['revenue'] for s in sales_data),
            "accuracy_rate": accuracy['accuracy_rate'],
            "adjustments_made": {
                "niche_confidence": niche_performance,
                "price_confidence": price_performance,
                "accuracy": accuracy
            }
        }
        
        self.learning_history.append(learning_cycle)
        
        # 6. Save everything
        self.save_weights()
        self.save_learning_history()
        
        logger.info(f"✅ Learning cycle {self.weights['total_learning_cycles']} complete")
        logger.info(f"   Current accuracy: {accuracy['accuracy_rate']:.1%}")
    
    def _analyze_niche_performance(self, sales_data: List[Dict]) -> Dict:
        """Calculate which niches are actually selling"""
        niche_stats = defaultdict(lambda: {'sales': 0, 'revenue': 0.0, 'units': 0})
        
        for sale in sales_data:
            niche = sale['niche']
            niche_stats[niche]['sales'] += 1
            niche_stats[niche]['revenue'] += sale['revenue']
            niche_stats[niche]['units'] += sale['units_sold']
        
        # Calculate performance ratios
        total_sales = sum(s['sales'] for s in niche_stats.values())
        
        performance = {}
        for niche, stats in niche_stats.items():
            performance[niche] = {
                'sales_share': stats['sales'] / total_sales if total_sales > 0 else 0,
                'avg_revenue': stats['revenue'] / stats['sales'] if stats['sales'] > 0 else 0,
                'total_units': stats['units']
            }
        
        return performance
    
    def _update_niche_confidence(self, performance: Dict):
        """Update niche confidence based on performance"""
        for niche, stats in performance.items():
            # Higher sales share = higher confidence
            # But don't swing too wildly (0.8 weight on new data, 0.2 on old)
            sales_share = stats['sales_share']
            new_confidence = (sales_share * 0.8) + 0.2
            
            # Smooth update (70% old, 30% new)
            old_confidence = self.weights['niche_confidence'].get(niche, 0.5)
            updated = (old_confidence * 0.7) + (new_confidence * 0.3)
            
            self.weights['niche_confidence'][niche] = round(updated, 2)
            
            logger.info(f"   {niche}: {old_confidence:.2f} → {updated:.2f} ({stats['sales_share']:.1%} of sales)")
    
    def _analyze_price_points(self, sales_data: List[Dict]) -> Dict:
        """Calculate which price points convert best"""
        price_buckets = {
            "under_20": [],
            "20_to_50": [],
            "50_to_100": [],
            "over_100": []
        }
        
        for sale in sales_data:
            price = sale['price']
            units = sale['units_sold']
            
            if price < 20:
                price_buckets["under_20"].append(units)
            elif price < 50:
                price_buckets["20_to_50"].append(units)
            elif price < 100:
                price_buckets["50_to_100"].append(units)
            else:
                price_buckets["over_100"].append(units)
        
        # Calculate performance
        total_units = sum(sum(bucket) for bucket in price_buckets.values())
        
        performance = {}
        for bucket, units_list in price_buckets.items():
            units_sold = sum(units_list)
            performance[bucket] = {
                'units_share': units_sold / total_units if total_units > 0 else 0,
                'avg_units_per_sale': sum(units_list) / len(units_list) if units_list else 0
            }
        
        return performance
    
    def _update_price_confidence(self, performance: Dict):
        """Update price point confidence"""
        for bucket, stats in performance.items():
            # More units sold = higher confidence in this price range
            units_share = stats['units_share']
            new_confidence = (units_share * 0.8) + 0.2
            
            # Smooth update
            old_confidence = self.weights['price_point_confidence'].get(bucket, 0.5)
            updated = (old_confidence * 0.7) + (new_confidence * 0.3)
            
            self.weights['price_point_confidence'][bucket] = round(updated, 2)
    
    def _calculate_prediction_accuracy(self, sales_data: List[Dict]) -> Dict:
        """
        Calculate how accurate our predictions were
        
        High score (8-10) should = high sales
        Low score (0-5) should = low sales
        """
        accurate = 0
        total = len(sales_data)
        
        for sale in sales_data:
            predicted_score = sale.get('predicted_score', 0)
            units_sold = sale.get('units_sold', 0)
            
            # Define accuracy criteria
            if predicted_score >= 8 and units_sold >= 10:
                accurate += 1  # Predicted high, sold high ✅
            elif predicted_score >= 8 and units_sold >= 5:
                accurate += 0.5  # Predicted high, sold medium 🤷
            elif predicted_score < 6 and units_sold < 5:
                accurate += 1  # Predicted low, sold low ✅
            elif predicted_score >= 6 and predicted_score < 8 and units_sold >= 5:
                accurate += 1  # Predicted medium, sold medium ✅
        
        accuracy_rate = accurate / total if total > 0 else 0.5
        
        return {
            'predictions_made': total,
            'predictions_correct': accurate,
            'accuracy_rate': accuracy_rate
        }
    
    def _update_scoring_weights(self, accuracy: Dict):
        """Adjust scoring weights based on prediction accuracy"""
        accuracy_rate = accuracy['accuracy_rate']
        
        # Update accuracy tracking
        self.weights['accuracy_tracking'] = accuracy
        
        # If accuracy is low (<60%), adjust weights
        if accuracy_rate < 0.6:
            logger.warning(f"⚠️ Low accuracy ({accuracy_rate:.1%}) - adjusting weights...")
            
            # Trust trends more, social signals less
            weights = self.weights['scoring_weights']
            weights['google_trends_weight'] = min(0.35, weights['google_trends_weight'] * 1.1)
            weights['reddit_mentions_weight'] = max(0.10, weights['reddit_mentions_weight'] * 0.9)
            
            # Normalize to sum to 1.0
            total = sum(weights.values())
            for key in weights:
                weights[key] = round(weights[key] / total, 2)
    
    async def get_adjusted_score(self, product: Dict) -> float:
        """
        Calculate product score using learned weights
        
        This is the MAGIC - scores improve over time based on what actually works
        
        Args:
            product: Product dict with base score, niche, price, etc.
        
        Returns:
            Adjusted score (0-10) based on learned confidence
        """
        base_score = product.get('score', 0)
        niche = product.get('niche', 'general')
        price = product.get('price', 0)
        
        # Get niche confidence multiplier
        niche_confidence = self.weights['niche_confidence'].get(niche, 0.5)
        
        # Get price point confidence
        if price < 20:
            price_confidence = self.weights['price_point_confidence']['under_20']
        elif price < 50:
            price_confidence = self.weights['price_point_confidence']['20_to_50']
        elif price < 100:
            price_confidence = self.weights['price_point_confidence']['50_to_100']
        else:
            price_confidence = self.weights['price_point_confidence']['over_100']
        
        # Adjust score based on learned confidence
        # High confidence niches/prices get boosted
        # Low confidence get penalized
        adjusted_score = base_score * (
            (niche_confidence * 0.6) +       # 60% weight on niche confidence
            (price_confidence * 0.4)         # 40% weight on price confidence
        )
        
        return round(min(10.0, adjusted_score), 1)
    
    async def get_learning_report(self) -> Dict:
        """
        Generate comprehensive learning report
        
        This is what Claude AI analyzes to provide insights
        """
        return {
            "status": "active",
            "version": self.weights.get("version", "1.0"),
            "last_updated": self.weights.get("last_updated"),
            "total_learning_cycles": self.weights.get("total_learning_cycles", 0),
            
            "current_weights": self.weights['scoring_weights'],
            
            "niche_performance": {
                "confidence_levels": self.weights['niche_confidence'],
                "most_confident": max(
                    self.weights['niche_confidence'].items(),
                    key=lambda x: x[1]
                ),
                "least_confident": min(
                    self.weights['niche_confidence'].items(),
                    key=lambda x: x[1]
                )
            },
            
            "price_optimization": {
                "confidence_levels": self.weights['price_point_confidence'],
                "best_price_range": max(
                    self.weights['price_point_confidence'].items(),
                    key=lambda x: x[1]
                )
            },
            
            "prediction_accuracy": self.weights.get('accuracy_tracking', {}),
            
            "recent_history": self.learning_history[-5:] if self.learning_history else []
        }
    
    async def simulate_learning_cycle(self):
        """
        DEMO: Simulate a learning cycle with sample data
        
        Use this to test the system before real sales data
        """
        sample_sales = [
            {
                'product_id': '001',
                'product_name': 'Smart LED Strip',
                'niche': 'smart_home',
                'price': 29.99,
                'units_sold': 15,
                'revenue': 449.85,
                'predicted_score': 8.5,
                'date': '2025-11-04'
            },
            {
                'product_id': '002',
                'product_name': 'Wireless Charger',
                'niche': 'tech_accessories',
                'price': 19.99,
                'units_sold': 8,
                'revenue': 159.92,
                'predicted_score': 7.2,
                'date': '2025-11-04'
            },
            {
                'product_id': '003',
                'product_name': 'Resistance Bands',
                'niche': 'fitness',
                'price': 24.99,
                'units_sold': 3,
                'revenue': 74.97,
                'predicted_score': 6.8,
                'date': '2025-11-04'
            }
        ]
        
        logger.info("🎭 Running DEMO learning cycle with sample data...")
        await self.learn_from_sales(sample_sales)
        
        return await self.get_learning_report()
