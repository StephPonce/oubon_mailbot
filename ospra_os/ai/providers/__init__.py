"""
AI Providers Package

This package contains AI provider implementations for OspraOS.
All providers implement the AIProvider abstract base class.

Available Providers:
    - Claude (Anthropic)
    - OpenAI (GPT-4)
    - Gemini (Google)
    - Grok (xAI) - Coming Soon

Author: OspraOS
Date: November 2025
"""

from ospra_os.ai.providers.base import (
    AIProvider,
    AIProviderError,
    APIKeyError,
    RateLimitError,
    InvalidResponseError,
    get_available_providers,
    get_provider_info
)

from ospra_os.ai.providers.claude import ClaudeProvider
from ospra_os.ai.providers.openai_provider import OpenAIProvider
from ospra_os.ai.providers.gemini import GeminiProvider

__all__ = [
    "AIProvider",
    "AIProviderError",
    "APIKeyError",
    "RateLimitError",
    "InvalidResponseError",
    "get_available_providers",
    "get_provider_info",
    "ClaudeProvider",
    "OpenAIProvider",
    "GeminiProvider"
]
