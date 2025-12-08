"""
Ospra OS Learning System
========================

Two-Layer Hybrid Learning Architecture:
- Global Brain: Learns from ALL Ospra users (network effect)
- Personal Layer: Learns from individual user patterns (Soar+ only)

Learns from:
- Actual Shopify sales data
- Customer behavior (clicks, time on page)
- Ad performance (ROAS, CTR)
- Product predictions vs reality

Adjusts:
- Product scoring weights
- Niche confidence levels
- Price point preferences
- Trend velocity importance
"""

# Primary export - Hybrid Learning Engine (database-backed)
from .hybrid_learning_engine import (
    HybridLearningEngine,
    GlobalLearningWeights,
    PersonalLearningWeights,
    LearningEvent,
    get_learning_engine,
    init_hybrid_learning,
)

# Supporting utilities
from .performance_tracker import PerformanceTracker
from .trend_velocity_detector import TrendVelocityDetector

# Legacy (deprecated - forwards to hybrid)
from .self_learning_engine import SelfLearningEngine

__all__ = [
    # Primary (use these)
    'HybridLearningEngine',
    'GlobalLearningWeights',
    'PersonalLearningWeights',
    'LearningEvent',
    'get_learning_engine',
    'init_hybrid_learning',
    
    # Supporting
    'PerformanceTracker',
    'TrendVelocityDetector',
    
    # Legacy (deprecated)
    'SelfLearningEngine',
]
