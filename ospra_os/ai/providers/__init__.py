"""
AI Providers Package

This package contains AI provider implementations for OspraOS.
All providers implement the AIProvider abstract base class.

Available Providers:
    - Claude (Anthropic) - Premium reasoning
    - OpenAI (GPT-4) - General purpose
    - Gemini (Google) - Cost-effective
    - Groq (Llama) - Ultra-fast inference

Author: OspraOS
Date: December 2025
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

# Groq - try import, may not have package installed
try:
    from ospra_os.ai.providers.groq_provider import GroqProvider
    _groq_available = True
except ImportError:
    GroqProvider = None
    _groq_available = False

__all__ = [
    # Base classes
    "AIProvider",
    "AIProviderError",
    "APIKeyError",
    "RateLimitError",
    "InvalidResponseError",
    "get_available_providers",
    "get_provider_info",
    # Providers
    "ClaudeProvider",
    "OpenAIProvider",
    "GeminiProvider",
    "GroqProvider",
]
