"""
AI Providers Package

This package contains AI provider implementations for OspraOS.
All providers implement the AIProvider abstract base class.

Available Providers:
    - Claude (Anthropic) - Premium reasoning, Oi brain
    - OpenAI (GPT-4) - Creative content, DALL-E images
    - Gemini (Google) - Cost-effective, bulk operations
    - Groq (Llama) - Ultra-fast inference, email automation
    - xAI (Grok) - Real-time X/Twitter data, trend analysis

Author: OspraOS
Date: December 2024
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

# xAI - try import
try:
    from ospra_os.ai.providers.xai_provider import XAIProvider
    _xai_available = True
except ImportError:
    XAIProvider = None
    _xai_available = False

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
    "XAIProvider",
]
