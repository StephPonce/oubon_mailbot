"""
[WARNING] DEPRECATED - Use ospra_os.learning.hybrid_learning_engine instead

This file-based learning engine has been replaced by the database-backed
HybridLearningEngine which supports:
- Global Brain (learns from ALL Ospra users)
- Personal Layer (individual user patterns - Soar+ tiers)
- Tier-aware learning rates

Migration:
    # OLD (deprecated)
    from ospra_os.learning.self_learning_engine import SelfLearningEngine
    
    # NEW (use this)
    from ospra_os.learning.hybrid_learning_engine import HybridLearningEngine, get_learning_engine
"""

import warnings
import logging

# Import from new unified system
from ospra_os.learning.hybrid_learning_engine import (
    HybridLearningEngine,
    GlobalLearningWeights,
    PersonalLearningWeights,
    LearningEvent,
    get_learning_engine,
    init_hybrid_learning,
)

logger = logging.getLogger(__name__)

# Emit deprecation warning on import
warnings.warn(
    "ospra_os.learning.self_learning_engine is deprecated. "
    "Use ospra_os.learning.hybrid_learning_engine instead.",
    DeprecationWarning,
    stacklevel=2
)


class SelfLearningEngine:
    """
    DEPRECATED: Legacy wrapper for backward compatibility.
    
    This was a file-based learning engine. The new HybridLearningEngine
    uses the database and supports:
    - Network effects (global learning from all users)
    - Personal learning (Soar+ tiers only)
    - Accelerated learning (Stratosphere tier)
    """
    
    def __init__(self, data_dir=None):
        warnings.warn(
            "File-based SelfLearningEngine is deprecated. "
            "Use database-backed HybridLearningEngine instead.",
            DeprecationWarning,
            stacklevel=2
        )
        self._engine = HybridLearningEngine()
        logger.warning("[WARNING] Using deprecated SelfLearningEngine - migrate to HybridLearningEngine")
    
    @property
    def weights(self):
        """Get current weights from global brain"""
        return self._engine.get_global_weights().get('scoring_weights', {})
    
    async def record_performance(self, product_data: dict, sales_data: dict, user_id: int = 1):
        """Record product performance - forwards to hybrid engine"""
        combined = [{**product_data, **sales_data}]
        return await self._engine.learn_global(combined, user_id)
    
    async def get_adjusted_score(self, product: dict, user_id: int = None):
        """Get AI-adjusted score"""
        return await self._engine.get_adjusted_score(product, user_id)
    
    def get_learning_report(self):
        """Get learning summary"""
        return self._engine.get_global_weights()


# Re-export everything from hybrid engine for migration
__all__ = [
    # Deprecated
    'SelfLearningEngine',
    
    # New (preferred)
    'HybridLearningEngine',
    'GlobalLearningWeights',
    'PersonalLearningWeights', 
    'LearningEvent',
    'get_learning_engine',
    'init_hybrid_learning',
]
