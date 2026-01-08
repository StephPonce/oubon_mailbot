"""
Oi - Ospra Intelligence AI Assistant

The brain of the Ospra Intelligence platform. Oi is a context-aware AI assistant
that can understand your business, execute actions, and provide intelligent
recommendations.

NOW WITH:
- Dashboard context awareness (knows what you're viewing)
- Self-learning system (improves from your interactions)
- Personalized recommendations

USES REAL DATA ONLY - Never fabricates information.

Author: OspraOS
Date: December 2024
"""

from ospra_os.oi.oi_service import OiService, OiResponse, oi_sessions, OiSessionManager
from ospra_os.oi.context_builder import ContextBuilder
from ospra_os.oi.action_executor import ActionExecutor, ActionResult, ActionStatus
from ospra_os.oi.response_validator import ResponseValidator, ValidationResult, get_response_validator
from ospra_os.oi.learning_system import (
    OiLearningSystem, 
    UserInteraction, 
    ConversationFeedback,
    LearnedPattern,
    get_learning_system
)

__all__ = [
    # Core service
    "OiService",
    "OiResponse", 
    "oi_sessions",
    "OiSessionManager",
    
    # Context building
    "ContextBuilder",
    
    # Action execution
    "ActionExecutor",
    "ActionResult",
    "ActionStatus",
    
    # Response validation (hallucination detection)
    "ResponseValidator",
    "ValidationResult",
    "get_response_validator",
    
    # Self-learning system
    "OiLearningSystem",
    "UserInteraction",
    "ConversationFeedback",
    "LearnedPattern",
    "get_learning_system",
]
