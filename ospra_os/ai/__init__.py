"""
AI Module for OspraOS

This module provides AI-powered functionality for product analysis,
description generation, pricing optimization, and more.

Submodules:
    - providers: AI provider implementations (Claude, OpenAI, Gemini, Grok)
    - factory: Provider factory for dynamic instantiation
    - cost_tracker: Usage tracking and cost analytics

Author: OspraOS
Date: November 2025
"""

from ospra_os.ai.providers import (
    AIProvider,
    AIProviderError,
    APIKeyError,
    RateLimitError,
    InvalidResponseError,
    get_available_providers,
    get_provider_info,
    ClaudeProvider,
    OpenAIProvider,
    GeminiProvider
)

from ospra_os.ai.factory import (
    AIFactory,
    get_ai_provider
)

from ospra_os.ai.cost_tracker import (
    AICostTracker,
    track_ai_call,
    get_cost_tracker
)

__all__ = [
    # Providers
    "AIProvider",
    "AIProviderError",
    "APIKeyError",
    "RateLimitError",
    "InvalidResponseError",
    "get_available_providers",
    "get_provider_info",
    "ClaudeProvider",
    "OpenAIProvider",
    "GeminiProvider",
    # Factory
    "AIFactory",
    "get_ai_provider",
    # Cost Tracking
    "AICostTracker",
    "track_ai_call",
    "get_cost_tracker"
]
