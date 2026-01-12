"""
Hybrid Learning Engine for Ospra OS
====================================

Two-Layer Learning Architecture:
1. GLOBAL BRAIN - Learns from ALL Ospra users (network effect)
   - Available to ALL tiers
   - "47 users tried this product, 38 had sales"
   - Shared intelligence makes the platform smarter for everyone

2. PERSONAL LAYER - Learns from individual user's patterns
   - Available to Soar+ tiers only
   - "Your store sells 3x more at $29.99 vs $39.99"
   - Custom model fine-tuned to YOUR business

Why This Architecture?
- Nest/Flight users benefit from collective intelligence
- Soar+ users get personalized predictions
- Network effect creates competitive moat (more users = smarter AI)
- Stratosphere users can customize weight adjustments
"""

import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from collections import defaultdict
from enum import Enum

from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Boolean, ForeignKey, Text
from sqlalchemy.orm import Session

from ospra_os.database import Base, SessionLocal, engine, User
from ospra_os.core.tiers import SubscriptionTier, get_tier_definition

logger = logging.getLogger(__name__)


# ============================================================================
# DATABASE MODELS FOR LEARNING
# ============================================================================

class GlobalLearningWeights(Base):
    """Global AI weights learned from ALL users"""
    __tablename__ = "global_learning_weights"
    
    id = Column(Integer, primary_key=True)
    
    # Version tracking
    version = Column(String(20), default="1.0")
    learning_cycles = Column(Integer, default=0)
    
    # Scoring weights (JSON)
    scoring_weights = Column(JSON, nullable=False)
    
    # Niche confidence (JSON)
    niche_confidence = Column(JSON, nullable=False)
    
    # Price point confidence (JSON)
    price_confidence = Column(JSON, nullable=False)
    
    # Trend velocity thresholds (JSON)
    trend_velocity = Column(JSON, nullable=False)
    
    # Accuracy tracking (JSON)
    accuracy = Column(JSON, nullable=False)
    
    # Aggregate stats
    total_users_contributing = Column(Integer, default=0)
    total_sales_analyzed = Column(Integer, default=0)
    total_revenue_analyzed = Column(Float, default=0.0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PersonalLearningWeights(Base):
    """Per-user AI weights (Soar+ only)"""
    __tablename__ = "personal_learning_weights"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    
    # Version tracking
    version = Column(String(20), default="1.0")
    learning_cycles = Column(Integer, default=0)
    
    # Personal adjustments (deltas from global)
    scoring_adjustments = Column(JSON, default=dict)  # +/- adjustments to global weights
    niche_adjustments = Column(JSON, default=dict)
    price_adjustments = Column(JSON, default=dict)
    
    # User-specific patterns
    best_performing_niches = Column(JSON, default=list)
    optimal_price_range = Column(JSON, default=dict)
    peak_selling_days = Column(JSON, default=list)  # ["Monday", "Friday"]
    
    # Custom weights (Stratosphere only)
    custom_weights_enabled = Column(Boolean, default=False)
    custom_weights = Column(JSON, default=dict)
    
    # Accuracy for this user
    predictions_made = Column(Integer, default=0)
    predictions_correct = Column(Float, default=0)
    accuracy_rate = Column(Float, default=0.5)
    
    # Stats
    sales_analyzed = Column(Integer, default=0)
    revenue_analyzed = Column(Float, default=0.0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class LearningEvent(Base):
    """Log of learning events for analytics"""
    __tablename__ = "learning_events"
    
    id = Column(Integer, primary_key=True)
    
    # Event type
    event_type = Column(String(50), nullable=False, index=True)  # "global_cycle", "personal_cycle", "weight_adjustment"
    
    # Who triggered it
    user_id = Column(Integer, nullable=True)  # NULL for global events
    
    # What happened
    details = Column(JSON, nullable=False)
    
    # Impact
    accuracy_before = Column(Float)
    accuracy_after = Column(Float)
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


# ============================================================================
# DEFAULT WEIGHTS
# ============================================================================

DEFAULT_SCORING_WEIGHTS = {
    "google_trends_weight": 0.25,
    "reddit_mentions_weight": 0.15,
    "aliexpress_orders_weight": 0.35,
    "price_competitiveness_weight": 0.15,
    "trend_velocity_weight": 0.10
}

DEFAULT_NICHE_CONFIDENCE = {
    "smart_home": 0.5,
    "fitness": 0.5,
    "tech_accessories": 0.5,
    "home_office": 0.5,
    "beauty": 0.5,
    "kitchen": 0.5,
    "outdoor": 0.5,
    "pet": 0.5
}

DEFAULT_PRICE_CONFIDENCE = {
    "under_20": 0.5,
    "20_to_50": 0.5,
    "50_to_100": 0.5,
    "over_100": 0.5
}

DEFAULT_TREND_VELOCITY = {
    "early_spike_threshold": 50,
    "sustained_growth_days": 7,
    "decay_threshold": -20
}

DEFAULT_ACCURACY = {
    "predictions_made": 0,
    "predictions_correct": 0,
    "accuracy_rate": 0.5
}


# ============================================================================
# HYBRID LEARNING ENGINE
# ============================================================================

class HybridLearningEngine:
    """
    Two-layer learning system:
    - Global Brain: Learns from ALL Ospra users
    - Personal Layer: Fine-tuned to individual user (Soar+ only)
    """
    
    def __init__(self, session: Session = None):
        self.session = session or SessionLocal()
        self._ensure_global_weights_exist()
    
    def _ensure_global_weights_exist(self):
        """Create global weights row if not exists"""
        global_weights = self.session.query(GlobalLearningWeights).first()
        
        if not global_weights:
            global_weights = GlobalLearningWeights(
                version="1.0",
                learning_cycles=0,
                scoring_weights=DEFAULT_SCORING_WEIGHTS,
                niche_confidence=DEFAULT_NICHE_CONFIDENCE,
                price_confidence=DEFAULT_PRICE_CONFIDENCE,
                trend_velocity=DEFAULT_TREND_VELOCITY,
                accuracy=DEFAULT_ACCURACY
            )
            self.session.add(global_weights)
            self.session.commit()
            logger.info("[BRAIN] Initialized Global Brain with default weights")
    
    # ==================== GLOBAL BRAIN ====================
    
    def get_global_weights(self) -> Dict[str, Any]:
        """Get current global AI weights"""
        global_weights = self.session.query(GlobalLearningWeights).first()
        
        return {
            "version": global_weights.version,
            "learning_cycles": global_weights.learning_cycles,
            "scoring_weights": global_weights.scoring_weights,
            "niche_confidence": global_weights.niche_confidence,
            "price_confidence": global_weights.price_confidence,
            "trend_velocity": global_weights.trend_velocity,
            "accuracy": global_weights.accuracy,
            "total_users_contributing": global_weights.total_users_contributing,
            "total_sales_analyzed": global_weights.total_sales_analyzed,
            "last_updated": global_weights.updated_at.isoformat() if global_weights.updated_at else None
        }
    
    async def learn_global(self, sales_data: List[Dict], user_id: int):
        """
        Contribute to Global Brain learning.
        
        ALL tiers contribute to this - it's the network effect.
        Higher tiers get accelerated contribution (their data is weighted more).
        """
        if not sales_data:
            return {"success": False, "reason": "No sales data provided"}
        
        global_weights = self.session.query(GlobalLearningWeights).first()
        
        # Get user tier for contribution weighting
        user = self.session.query(User).filter(User.id == user_id).first()
        tier = user.subscription_tier.value if user else "nest"
        
        # Tier contribution multiplier (higher tiers have more weight)
        contribution_weight = {
            "nest": 1.0,
            "flight": 1.2,
            "soar": 1.5,
            "stratosphere": 2.0
        }.get(tier, 1.0)
        
        try:
            # Analyze performance
            niche_performance = self._analyze_niche_performance(sales_data)
            price_performance = self._analyze_price_points(sales_data)
            accuracy = self._calculate_prediction_accuracy(sales_data)
            
            # Update global weights with contribution weighting
            self._update_global_niche_confidence(global_weights, niche_performance, contribution_weight)
            self._update_global_price_confidence(global_weights, price_performance, contribution_weight)
            self._update_global_accuracy(global_weights, accuracy)
            
            # Update stats
            global_weights.learning_cycles += 1
            global_weights.total_users_contributing += 1
            global_weights.total_sales_analyzed += len(sales_data)
            global_weights.total_revenue_analyzed += sum(s.get('revenue', 0) for s in sales_data)
            
            self.session.commit()
            
            # Log event
            self._log_learning_event(
                event_type="global_cycle",
                user_id=user_id,
                details={
                    "sales_count": len(sales_data),
                    "contribution_weight": contribution_weight,
                    "tier": tier
                }
            )
            
            logger.info(f"[BRAIN] Global Brain updated: {len(sales_data)} sales from {tier} user")
            
            return {
                "success": True,
                "learning_cycle": global_weights.learning_cycles,
                "contribution_weight": contribution_weight,
                "global_accuracy": global_weights.accuracy.get("accuracy_rate", 0)
            }
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Global learning failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _update_global_niche_confidence(self, global_weights, performance: Dict, weight: float):
        """Update global niche confidence with weighted contribution"""
        current = global_weights.niche_confidence.copy()
        
        for niche, stats in performance.items():
            sales_share = stats.get('sales_share', 0)
            new_confidence = (sales_share * 0.8) + 0.2
            
            old_confidence = current.get(niche, 0.5)
            
            # Weight the update by contribution weight
            update_strength = 0.3 * weight
            updated = (old_confidence * (1 - update_strength)) + (new_confidence * update_strength)
            
            current[niche] = round(max(0.1, min(0.9, updated)), 3)
        
        global_weights.niche_confidence = current
    
    def _update_global_price_confidence(self, global_weights, performance: Dict, weight: float):
        """Update global price confidence"""
        current = global_weights.price_confidence.copy()
        
        for bucket, stats in performance.items():
            units_share = stats.get('units_share', 0)
            new_confidence = (units_share * 0.8) + 0.2
            
            old_confidence = current.get(bucket, 0.5)
            
            update_strength = 0.3 * weight
            updated = (old_confidence * (1 - update_strength)) + (new_confidence * update_strength)
            
            current[bucket] = round(max(0.1, min(0.9, updated)), 3)
        
        global_weights.price_confidence = current
    
    def _update_global_accuracy(self, global_weights, accuracy: Dict):
        """Update global accuracy tracking"""
        current = global_weights.accuracy.copy()
        
        current['predictions_made'] = current.get('predictions_made', 0) + accuracy.get('predictions_made', 0)
        current['predictions_correct'] = current.get('predictions_correct', 0) + accuracy.get('predictions_correct', 0)
        
        if current['predictions_made'] > 0:
            current['accuracy_rate'] = round(
                current['predictions_correct'] / current['predictions_made'], 3
            )
        
        global_weights.accuracy = current
    
    # ==================== PERSONAL LAYER ====================
    
    def get_personal_weights(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get personal learning weights for a user.
        Returns None if user doesn't have Soar+ tier.
        """
        # Check tier
        user = self.session.query(User).filter(User.id == user_id).first()
        if not user:
            return None
        
        tier = user.subscription_tier.value if hasattr(user.subscription_tier, 'value') else str(user.subscription_tier)
        
        if tier not in ['soar', 'stratosphere']:
            return {
                "available": False,
                "reason": "Personal learning requires Soar tier or higher",
                "upgrade_to": "soar"
            }
        
        # Get or create personal weights
        personal = self.session.query(PersonalLearningWeights).filter(
            PersonalLearningWeights.user_id == user_id
        ).first()
        
        if not personal:
            personal = PersonalLearningWeights(
                user_id=user_id,
                version="1.0",
                learning_cycles=0
            )
            self.session.add(personal)
            self.session.commit()
        
        return {
            "available": True,
            "version": personal.version,
            "learning_cycles": personal.learning_cycles,
            "scoring_adjustments": personal.scoring_adjustments or {},
            "niche_adjustments": personal.niche_adjustments or {},
            "price_adjustments": personal.price_adjustments or {},
            "best_performing_niches": personal.best_performing_niches or [],
            "optimal_price_range": personal.optimal_price_range or {},
            "peak_selling_days": personal.peak_selling_days or [],
            "accuracy_rate": personal.accuracy_rate,
            "sales_analyzed": personal.sales_analyzed,
            "custom_weights_enabled": personal.custom_weights_enabled,
            "last_updated": personal.updated_at.isoformat() if personal.updated_at else None
        }
    
    async def learn_personal(self, user_id: int, sales_data: List[Dict]) -> Dict[str, Any]:
        """
        Update personal learning layer for a user.
        
        Soar tier: Standard personal learning
        Stratosphere tier: Accelerated learning + custom weights
        """
        # Check tier
        user = self.session.query(User).filter(User.id == user_id).first()
        if not user:
            return {"success": False, "reason": "User not found"}
        
        tier = user.subscription_tier.value if hasattr(user.subscription_tier, 'value') else str(user.subscription_tier)
        
        if tier not in ['soar', 'stratosphere']:
            return {
                "success": False,
                "reason": "Personal learning requires Soar tier or higher",
                "upgrade_to": "soar"
            }
        
        if not sales_data:
            return {"success": False, "reason": "No sales data provided"}
        
        # Get or create personal weights
        personal = self.session.query(PersonalLearningWeights).filter(
            PersonalLearningWeights.user_id == user_id
        ).first()
        
        if not personal:
            personal = PersonalLearningWeights(user_id=user_id)
            self.session.add(personal)
        
        try:
            # Learning rate (Stratosphere gets 2x)
            learning_rate = 2.0 if tier == 'stratosphere' else 1.0
            
            # Analyze user's specific patterns
            niche_perf = self._analyze_niche_performance(sales_data)
            price_perf = self._analyze_price_points(sales_data)
            accuracy = self._calculate_prediction_accuracy(sales_data)
            
            # Update personal adjustments
            self._update_personal_niche_adjustments(personal, niche_perf, learning_rate)
            self._update_personal_price_adjustments(personal, price_perf, learning_rate)
            self._update_personal_patterns(personal, sales_data)
            
            # Update accuracy
            personal.predictions_made += accuracy.get('predictions_made', 0)
            personal.predictions_correct += accuracy.get('predictions_correct', 0)
            if personal.predictions_made > 0:
                personal.accuracy_rate = round(personal.predictions_correct / personal.predictions_made, 3)
            
            # Update stats
            personal.learning_cycles += 1
            personal.sales_analyzed += len(sales_data)
            personal.revenue_analyzed += sum(s.get('revenue', 0) for s in sales_data)
            
            self.session.commit()
            
            # Log event
            self._log_learning_event(
                event_type="personal_cycle",
                user_id=user_id,
                details={
                    "sales_count": len(sales_data),
                    "learning_rate": learning_rate,
                    "tier": tier
                }
            )
            
            logger.info(f" Personal layer updated for user {user_id}: {len(sales_data)} sales")
            
            return {
                "success": True,
                "learning_cycle": personal.learning_cycles,
                "learning_rate": learning_rate,
                "accuracy_rate": personal.accuracy_rate,
                "best_niches": personal.best_performing_niches[:3]
            }
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Personal learning failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _update_personal_niche_adjustments(self, personal, performance: Dict, learning_rate: float):
        """Calculate personal niche adjustments vs global"""
        global_weights = self.session.query(GlobalLearningWeights).first()
        global_niche = global_weights.niche_confidence
        
        adjustments = personal.niche_adjustments or {}
        
        for niche, stats in performance.items():
            sales_share = stats.get('sales_share', 0)
            personal_confidence = (sales_share * 0.8) + 0.2
            
            global_confidence = global_niche.get(niche, 0.5)
            
            # Calculate delta from global
            delta = (personal_confidence - global_confidence) * learning_rate
            
            # Smooth update
            old_adjustment = adjustments.get(niche, 0)
            new_adjustment = (old_adjustment * 0.6) + (delta * 0.4)
            
            adjustments[niche] = round(max(-0.3, min(0.3, new_adjustment)), 3)
        
        personal.niche_adjustments = adjustments
        
        # Update best performing niches
        sorted_niches = sorted(
            adjustments.items(),
            key=lambda x: x[1],
            reverse=True
        )
        personal.best_performing_niches = [n[0] for n in sorted_niches[:5]]
    
    def _update_personal_price_adjustments(self, personal, performance: Dict, learning_rate: float):
        """Calculate personal price adjustments"""
        global_weights = self.session.query(GlobalLearningWeights).first()
        global_price = global_weights.price_confidence
        
        adjustments = personal.price_adjustments or {}
        
        for bucket, stats in performance.items():
            units_share = stats.get('units_share', 0)
            personal_confidence = (units_share * 0.8) + 0.2
            
            global_confidence = global_price.get(bucket, 0.5)
            
            delta = (personal_confidence - global_confidence) * learning_rate
            
            old_adjustment = adjustments.get(bucket, 0)
            new_adjustment = (old_adjustment * 0.6) + (delta * 0.4)
            
            adjustments[bucket] = round(max(-0.3, min(0.3, new_adjustment)), 3)
        
        personal.price_adjustments = adjustments
        
        # Find optimal price range
        best_bucket = max(adjustments.items(), key=lambda x: x[1]) if adjustments else ("20_to_50", 0)
        personal.optimal_price_range = {
            "bucket": best_bucket[0],
            "adjustment": best_bucket[1]
        }
    
    def _update_personal_patterns(self, personal, sales_data: List[Dict]):
        """Identify user-specific patterns (peak days, etc.)"""
        # Analyze day of week patterns
        day_sales = defaultdict(int)
        
        for sale in sales_data:
            sale_date = sale.get('date')
            if sale_date:
                try:
                    dt = datetime.fromisoformat(sale_date) if isinstance(sale_date, str) else sale_date
                    day_name = dt.strftime('%A')
                    day_sales[day_name] += sale.get('units_sold', 1)
                except:
                    pass
        
        # Find peak days
        if day_sales:
            avg_sales = sum(day_sales.values()) / len(day_sales)
            peak_days = [day for day, sales in day_sales.items() if sales > avg_sales * 1.2]
            personal.peak_selling_days = peak_days
    
    # ==================== SCORING ====================
    
    async def get_adjusted_score(
        self,
        product: Dict,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Calculate product score using hybrid learning.
        
        Returns:
            - score: Final adjusted score (0-10)
            - global_score: Score from global brain only
            - personal_adjustment: Delta from personal layer
            - confidence: How confident we are in this score
            - reasoning: Why this score
        """
        base_score = product.get('score', 5.0)
        niche = product.get('niche', 'general')
        price = product.get('price', 30)
        
        # Get global weights
        global_weights = self.get_global_weights()
        
        # Calculate global score
        global_niche_conf = global_weights['niche_confidence'].get(niche, 0.5)
        
        price_bucket = self._get_price_bucket(price)
        global_price_conf = global_weights['price_confidence'].get(price_bucket, 0.5)
        
        global_score = base_score * (
            (global_niche_conf * 0.6) + (global_price_conf * 0.4)
        )
        global_score = round(min(10.0, global_score), 1)
        
        # Check for personal adjustments
        personal_adjustment = 0.0
        has_personal = False
        
        if user_id:
            personal = self.get_personal_weights(user_id)
            
            if personal and personal.get('available', False):
                has_personal = True
                
                # Apply personal niche adjustment
                niche_adj = personal.get('niche_adjustments', {}).get(niche, 0)
                price_adj = personal.get('price_adjustments', {}).get(price_bucket, 0)
                
                personal_adjustment = (niche_adj * 0.6 + price_adj * 0.4) * base_score
                personal_adjustment = round(personal_adjustment, 2)
        
        # Final score
        final_score = round(min(10.0, max(0.0, global_score + personal_adjustment)), 1)
        
        # Calculate confidence based on learning cycles
        cycles = global_weights.get('learning_cycles', 0)
        base_confidence = min(0.9, 0.5 + (cycles * 0.01))  # +1% per cycle, max 90%
        
        return {
            "score": final_score,
            "global_score": global_score,
            "personal_adjustment": personal_adjustment if has_personal else None,
            "has_personal_learning": has_personal,
            "confidence": round(base_confidence, 2),
            "reasoning": self._generate_score_reasoning(
                niche, price_bucket, global_niche_conf, global_price_conf, has_personal
            )
        }
    
    def _get_price_bucket(self, price: float) -> str:
        """Get price bucket for a price"""
        if price < 20:
            return "under_20"
        elif price < 50:
            return "20_to_50"
        elif price < 100:
            return "50_to_100"
        else:
            return "over_100"
    
    def _generate_score_reasoning(
        self,
        niche: str,
        price_bucket: str,
        niche_conf: float,
        price_conf: float,
        has_personal: bool
    ) -> str:
        """Generate human-readable reasoning for score"""
        parts = []
        
        # Niche analysis
        if niche_conf > 0.6:
            parts.append(f"'{niche}' is performing well across Ospra users")
        elif niche_conf < 0.4:
            parts.append(f"'{niche}' has been underperforming recently")
        else:
            parts.append(f"'{niche}' shows average performance")
        
        # Price analysis
        price_labels = {
            "under_20": "under $20",
            "20_to_50": "$20-50",
            "50_to_100": "$50-100",
            "over_100": "over $100"
        }
        
        if price_conf > 0.6:
            parts.append(f"products {price_labels[price_bucket]} are converting well")
        elif price_conf < 0.4:
            parts.append(f"products {price_labels[price_bucket]} have lower conversion")
        
        # Personal note
        if has_personal:
            parts.append("adjusted based on your store's patterns")
        
        return "; ".join(parts)
    
    # ==================== STRATOSPHERE: CUSTOM WEIGHTS ====================
    
    async def set_custom_weights(
        self,
        user_id: int,
        custom_weights: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Set custom scoring weights for Stratosphere users.
        
        Args:
            custom_weights: {
                "google_trends_weight": 0.30,
                "reddit_mentions_weight": 0.10,
                ...
            }
        """
        # Check tier
        user = self.session.query(User).filter(User.id == user_id).first()
        if not user:
            return {"success": False, "reason": "User not found"}
        
        tier = user.subscription_tier.value if hasattr(user.subscription_tier, 'value') else str(user.subscription_tier)
        
        if tier != 'stratosphere':
            return {
                "success": False,
                "reason": "Custom weights require Stratosphere tier",
                "upgrade_to": "stratosphere"
            }
        
        # Validate weights sum to ~1.0
        total = sum(custom_weights.values())
        if abs(total - 1.0) > 0.01:
            return {
                "success": False,
                "reason": f"Weights must sum to 1.0 (current: {total})"
            }
        
        # Get or create personal weights
        personal = self.session.query(PersonalLearningWeights).filter(
            PersonalLearningWeights.user_id == user_id
        ).first()
        
        if not personal:
            personal = PersonalLearningWeights(user_id=user_id)
            self.session.add(personal)
        
        personal.custom_weights_enabled = True
        personal.custom_weights = custom_weights
        
        self.session.commit()
        
        logger.info(f" Custom weights set for user {user_id}")
        
        return {
            "success": True,
            "custom_weights": custom_weights
        }
    
    # ==================== UTILITIES ====================
    
    def _analyze_niche_performance(self, sales_data: List[Dict]) -> Dict:
        """Calculate which niches are selling"""
        niche_stats = defaultdict(lambda: {'sales': 0, 'revenue': 0.0, 'units': 0})
        
        for sale in sales_data:
            niche = sale.get('niche', 'general')
            niche_stats[niche]['sales'] += 1
            niche_stats[niche]['revenue'] += sale.get('revenue', 0)
            niche_stats[niche]['units'] += sale.get('units_sold', 0)
        
        total_sales = sum(s['sales'] for s in niche_stats.values())
        
        return {
            niche: {
                'sales_share': stats['sales'] / total_sales if total_sales > 0 else 0,
                'avg_revenue': stats['revenue'] / stats['sales'] if stats['sales'] > 0 else 0
            }
            for niche, stats in niche_stats.items()
        }
    
    def _analyze_price_points(self, sales_data: List[Dict]) -> Dict:
        """Calculate price point performance"""
        buckets = {
            "under_20": [],
            "20_to_50": [],
            "50_to_100": [],
            "over_100": []
        }
        
        for sale in sales_data:
            price = sale.get('price', 0)
            units = sale.get('units_sold', 1)
            bucket = self._get_price_bucket(price)
            buckets[bucket].append(units)
        
        total_units = sum(sum(b) for b in buckets.values())
        
        return {
            bucket: {
                'units_share': sum(units) / total_units if total_units > 0 else 0,
                'avg_units': sum(units) / len(units) if units else 0
            }
            for bucket, units in buckets.items()
        }
    
    def _calculate_prediction_accuracy(self, sales_data: List[Dict]) -> Dict:
        """Calculate prediction accuracy"""
        accurate = 0
        total = len(sales_data)
        
        for sale in sales_data:
            predicted = sale.get('predicted_score', 5)
            units = sale.get('units_sold', 0)
            
            if predicted >= 8 and units >= 10:
                accurate += 1
            elif predicted >= 8 and units >= 5:
                accurate += 0.5
            elif predicted < 6 and units < 5:
                accurate += 1
            elif 6 <= predicted < 8 and units >= 5:
                accurate += 1
        
        return {
            'predictions_made': total,
            'predictions_correct': accurate,
            'accuracy_rate': accurate / total if total > 0 else 0.5
        }
    
    def _log_learning_event(self, event_type: str, user_id: int = None, details: Dict = None):
        """Log a learning event"""
        event = LearningEvent(
            event_type=event_type,
            user_id=user_id,
            details=details or {}
        )
        self.session.add(event)
        # Don't commit here - let caller handle transaction
    
    # ==================== REPORTS ====================
    
    async def get_learning_report(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Get comprehensive learning report"""
        global_weights = self.get_global_weights()
        
        report = {
            "global_brain": {
                "learning_cycles": global_weights['learning_cycles'],
                "users_contributing": global_weights['total_users_contributing'],
                "sales_analyzed": global_weights['total_sales_analyzed'],
                "accuracy_rate": global_weights['accuracy'].get('accuracy_rate', 0),
                "best_niches": sorted(
                    global_weights['niche_confidence'].items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:3],
                "best_price_range": max(
                    global_weights['price_confidence'].items(),
                    key=lambda x: x[1]
                )
            }
        }
        
        if user_id:
            personal = self.get_personal_weights(user_id)
            if personal and personal.get('available'):
                report["personal_layer"] = {
                    "learning_cycles": personal['learning_cycles'],
                    "accuracy_rate": personal['accuracy_rate'],
                    "best_niches": personal['best_performing_niches'][:3],
                    "optimal_price": personal['optimal_price_range'],
                    "peak_days": personal['peak_selling_days']
                }
            else:
                report["personal_layer"] = personal  # Contains upgrade info
        
        return report


# ============================================================================
# INITIALIZATION
# ============================================================================

def init_hybrid_learning():
    """Initialize hybrid learning tables"""
    Base.metadata.create_all(bind=engine)
    logger.info("[SUCCESS] Hybrid learning tables created")


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def get_learning_engine(session: Session = None) -> HybridLearningEngine:
    """Get a HybridLearningEngine instance"""
    return HybridLearningEngine(session)


# Initialize on import
if __name__ == "__main__":
    init_hybrid_learning()
    print("[SUCCESS] Hybrid Learning Engine initialized")
