"""
Machine Learning Module - GROK RECOMMENDATION #15

Cost-optimized AI system using fine-tuned Llama models to reduce
Claude API costs by 70%+ while maintaining quality.

Components:
- training_data: Collect successful operations for fine-tuning
- model_router: Route tasks to optimal model (local/cheap/premium)
- ai_client: Unified interface for all AI providers
- fine_tuning: Pipeline for fine-tuning Llama models
"""

from ospra_os.ml.model_router import ModelRouter, ModelTier, TaskComplexity, ModelConfig
from ospra_os.ml.ai_client import (
    UnifiedAIClient,
    ai_client,
    AIResponse,
    AIProvider,
    ClaudeProvider,
    OllamaProvider,
    GroqProvider,
    TogetherProvider
)

__all__ = [
    # Routing
    "ModelRouter",
    "ModelTier",
    "TaskComplexity",
    "ModelConfig",
    # AI Client
    "UnifiedAIClient",
    "ai_client",
    "AIResponse",
    # Providers
    "AIProvider",
    "ClaudeProvider",
    "OllamaProvider",
    "GroqProvider",
    "TogetherProvider",
]
