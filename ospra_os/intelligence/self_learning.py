"""
[WARNING] DEPRECATED - Use ospra_os.learning.hybrid_learning_engine instead

This file is maintained for backward compatibility only.
All learning logic has been unified in the Hybrid Learning Engine.

Migration:
    # OLD (deprecated)
    from ospra_os.intelligence.self_learning import SelfLearningEngine
    
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
)

logger = logging.getLogger(__name__)

# Emit deprecation warning on import
warnings.warn(
    "ospra_os.intelligence.self_learning is deprecated. "
    "Use ospra_os.learning.hybrid_learning_engine instead.",
    DeprecationWarning,
    stacklevel=2
)


class SelfLearningEngine:
    """
    DEPRECATED: Legacy wrapper that forwards to HybridLearningEngine.
    
    Use HybridLearningEngine directly for:
    - Global Brain (learns from ALL users)
    - Personal Layer (learns from individual user - Soar+ only)
    """
    
    def __init__(self, db=None):
        warnings.warn(
            "SelfLearningEngine is deprecated. Use HybridLearningEngine instead.",
            DeprecationWarning,
            stacklevel=2
        )
        self._engine = HybridLearningEngine()
        logger.warning("[WARNING] Using deprecated SelfLearningEngine - migrate to HybridLearningEngine")
    
    def analyze_product_patterns(self, days: int = 30):
        """Deprecated: Use HybridLearningEngine.get_global_weights()"""
        return self._engine.get_global_weights()
    
    async def learn_from_sales(self, sales_data, user_id: int = None):
        """Deprecated: Use HybridLearningEngine.learn_global() or learn_personal()"""
        if user_id:
            await self._engine.learn_global(sales_data, user_id)
            return await self._engine.learn_personal(user_id, sales_data)
        return {"error": "user_id required for learning"}
    
    async def get_score(self, product: dict, user_id: int = None):
        """Deprecated: Use HybridLearningEngine.get_adjusted_score()"""
        return await self._engine.get_adjusted_score(product, user_id)


# Export for backward compatibility
__all__ = [
    'SelfLearningEngine',
    'HybridLearningEngine', 
    'get_learning_engine',
]
