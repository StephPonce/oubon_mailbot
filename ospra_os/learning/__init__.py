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
# T116: trend_velocity_detector removed — dead (only ever re-exported here;
# superseded by intelligence/trend_trajectory.py). Re-export deleted so the file
# is orphaned and can be git rm'd.

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

    # Legacy (deprecated)
    'SelfLearningEngine',
]
