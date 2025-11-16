"""
Ospra OS Self-Learning System

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

from .self_learning_engine import SelfLearningEngine
from .performance_tracker import PerformanceTracker
from .trend_velocity_detector import TrendVelocityDetector

__all__ = [
    'SelfLearningEngine',
    'PerformanceTracker',
    'TrendVelocityDetector'
]
