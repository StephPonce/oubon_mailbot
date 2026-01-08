"""
AI Factory for Provider Selection

This module provides a factory pattern for instantiating AI providers
and managing provider selection across the OspraOS platform.

SUPPORTED PROVIDERS:
- Claude (Anthropic) - Best for reasoning, analysis, Oi brain
- OpenAI (GPT-4) - Creative content, varied outputs
- Gemini (Google) - Ultra cost-effective, high volume
- Groq (Llama) - Blazing fast inference, real-time tasks

Author: OspraOS
Date: December 2024
"""

from typing import Dict, List, Optional, Type
import logging
import os

from ospra_os.ai.providers.base import AIProvider
from ospra_os.ai.providers.claude import ClaudeProvider
from ospra_os.ai.providers.openai_provider import OpenAIProvider
from ospra_os.ai.providers.gemini import GeminiProvider
from ospra_os.ai.providers.groq_provider import GroqProvider
from ospra_os.ai.providers.xai_provider import XAIProvider

logger = logging.getLogger(__name__)


class AIFactory:
    """
    Factory class for creating and managing AI provider instances.

    This class provides a central registry of all available AI providers
    and methods to instantiate them dynamically based on user preferences.

    Usage:
        >>> provider = AIFactory.get_provider("claude", api_key="sk-...")
        >>> result = await provider.analyze_product(product_data)
    """

    # Provider registry mapping provider names to their classes
    _providers: Dict[str, Type[AIProvider]] = {
        "claude": ClaudeProvider,
        "openai": OpenAIProvider,
        "gemini": GeminiProvider,
        "groq": GroqProvider,      # Llama models via Groq
        "llama": GroqProvider,     # Alias for groq
        "xai": XAIProvider,        # Grok - real-time X/Twitter data
        "grok": XAIProvider,       # Alias for xai
    }

    # Provider display information
    _provider_info: Dict[str, Dict[str, any]] = {
        "claude": {
            "display_name": "Claude (Anthropic)",
            "description": "Best for analytical reasoning, detailed analysis, and instruction-following",
            "model": "claude-sonnet-4-5-20250929",
            "cost_per_1k": 0.003,
            "recommended": True,
            "tier": "premium",
            "strengths": ["Analysis", "Reasoning", "Consistency", "Instruction-following"],
            "best_for": ["Oi brain", "Product analysis", "Market research", "Complex tasks"]
        },
        "openai": {
            "display_name": "OpenAI (GPT-4)",
            "description": "Most creative outputs with diverse writing styles",
            "model": "gpt-4o-mini",
            "cost_per_1k": 0.015,
            "recommended": False,
            "tier": "premium",
            "strengths": ["Creativity", "Diversity", "Latest features"],
            "best_for": ["Creative content", "A/B testing", "Varied outputs"]
        },
        "gemini": {
            "display_name": "Gemini (Google)",
            "description": "Ultra-cost-effective, fast, and production-ready",
            "model": "gemini-2.0-flash",
            "cost_per_1k": 0.00025,
            "recommended": True,
            "tier": "budget",
            "strengths": ["Cost efficiency", "Speed", "Scale", "1M context"],
            "best_for": ["High volume", "Budget-conscious", "Fast operations", "Bulk image gen"]
        },
        "groq": {
            "display_name": "Groq (Llama)",
            "description": "Blazing fast inference using LPU hardware - ideal for real-time",
            "model": "llama-3.3-70b-versatile",
            "cost_per_1k": 0.0006,
            "recommended": True,
            "tier": "speed",
            "strengths": ["Speed", "Real-time", "Low latency", "Open source models"],
            "best_for": ["Email automation", "Real-time chat", "High-volume simple tasks"]
        },
        "llama": {
            "display_name": "Llama (via Groq)",
            "description": "Meta's open-source Llama models via Groq's fast inference",
            "model": "llama-3.3-70b-versatile",
            "cost_per_1k": 0.0006,
            "recommended": False,
            "tier": "speed",
            "strengths": ["Open source", "Speed", "Cost"],
            "best_for": ["Same as Groq - alias"]
        },
        "xai": {
            "display_name": "xAI (Grok)",
            "description": "Real-time knowledge with X/Twitter integration - trend analysis",
            "model": "grok-2-1212",
            "cost_per_1k": 0.002,
            "recommended": True,
            "tier": "premium",
            "strengths": ["Real-time data", "X/Twitter integration", "Current events", "Social sentiment"],
            "best_for": ["Trend analysis", "Social sentiment", "Current events", "Market timing"]
        }
    }

    # Task-specific provider recommendations
    TASK_RECOMMENDATIONS = {
        "oi_brain": "claude",           # Needs reasoning + instruction-following
        "product_analysis": "claude",    # Needs detailed analysis
        "email_automation": "groq",      # Needs speed
        "description_gen": "openai",     # Needs creativity
        "high_volume": "gemini",         # Needs cost efficiency
        "real_time": "groq",             # Needs low latency
        "market_research": "claude",     # Needs accuracy
        "social_trends": "xai",          # Real-time X/Twitter data
        "sentiment_analysis": "xai",     # Social sentiment
        "trend_detection": "xai",        # Current trends
        "image_generation": "openai",    # DALL-E (or gemini for bulk)
    }

    @classmethod
    def get_provider(
        cls,
        provider_name: str,
        api_key: Optional[str] = None,
        **kwargs
    ) -> AIProvider:
        """
        Get an AI provider instance by name.

        Args:
            provider_name: Name of the provider ("claude", "openai", "gemini", "groq", "llama")
            api_key: API key for the provider (falls back to env vars)
            **kwargs: Additional arguments passed to provider constructor

        Returns:
            AIProvider instance

        Raises:
            ValueError: If provider_name is not recognized
        """
        provider_name = provider_name.lower().strip()

        if provider_name not in cls._providers:
            available = ", ".join(cls._providers.keys())
            raise ValueError(
                f"Unknown provider: '{provider_name}'. "
                f"Available providers: {available}"
            )

        # Auto-detect API key from environment if not provided
        if not api_key:
            api_key = cls._get_api_key(provider_name)
        
        if not api_key:
            env_var = cls._get_env_var_name(provider_name)
            raise ValueError(
                f"API key required for {provider_name}. "
                f"Set {env_var} environment variable or pass api_key parameter."
            )

        provider_class = cls._providers[provider_name]

        try:
            instance = provider_class(api_key=api_key, **kwargs)
            logger.info(f"Created {provider_name} provider instance")
            return instance
        except Exception as e:
            logger.error(f"Failed to create {provider_name} provider: {e}")
            raise

    @classmethod
    def _get_api_key(cls, provider_name: str) -> Optional[str]:
        """Get API key from environment variables."""
        env_var = cls._get_env_var_name(provider_name)
        return os.getenv(env_var)
    
    @classmethod
    def _get_env_var_name(cls, provider_name: str) -> str:
        """Get environment variable name for provider."""
        env_vars = {
            "claude": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "gemini": "GOOGLE_API_KEY",
            "groq": "GROQ_API_KEY",
            "llama": "GROQ_API_KEY",  # Llama uses Groq
            "xai": "XAI_API_KEY",
        }
        return env_vars.get(provider_name, f"{provider_name.upper()}_API_KEY")

    @classmethod
    def get_for_task(cls, task: str, api_key: Optional[str] = None) -> AIProvider:
        """
        Get the recommended provider for a specific task.

        Args:
            task: Task type (e.g., "oi_brain", "email_automation", "product_analysis")
            api_key: Optional API key (falls back to env var)

        Returns:
            AIProvider instance optimized for the task
        """
        provider_name = cls.TASK_RECOMMENDATIONS.get(task, "claude")
        
        # If recommended provider isn't available, fall back
        if not cls._get_api_key(provider_name):
            logger.warning(f"Recommended provider {provider_name} not configured, falling back to claude")
            provider_name = "claude"
        
        return cls.get_provider(provider_name, api_key)

    @classmethod
    def get_available_providers(cls, include_inactive: bool = False) -> List[Dict]:
        """
        Get list of all available AI providers with their information.

        Args:
            include_inactive: Include providers not yet implemented

        Returns:
            List of provider info dictionaries
        """
        providers = []

        for name, info in cls._provider_info.items():
            # Skip aliases (like "llama" which is just groq)
            if name == "llama":
                continue
                
            # Skip if provider class doesn't exist and include_inactive is False
            is_active = name in cls._providers and info.get("active", True) != False
            if not include_inactive and not is_active:
                continue
            
            # Check if API key is configured
            has_key = bool(cls._get_api_key(name))

            provider_data = {
                "name": name,
                "display_name": info["display_name"],
                "description": info["description"],
                "model": info["model"],
                "cost_per_1k": info["cost_per_1k"],
                "recommended": info["recommended"],
                "tier": info["tier"],
                "strengths": info["strengths"],
                "best_for": info["best_for"],
                "active": is_active,
                "configured": has_key
            }
            providers.append(provider_data)

        # Sort by cost (cheapest first)
        providers.sort(key=lambda p: p["cost_per_1k"])

        return providers

    @classmethod
    def get_default_provider(cls) -> str:
        """Get the default recommended provider name."""
        return "claude"

    @classmethod
    def get_cheapest_provider(cls) -> str:
        """Get the cheapest available provider."""
        return "gemini"
    
    @classmethod
    def get_fastest_provider(cls) -> str:
        """Get the fastest available provider."""
        return "groq"

    @classmethod
    def validate_provider(cls, provider_name: str) -> bool:
        """Check if a provider name is valid and available."""
        return provider_name.lower().strip() in cls._providers

    @classmethod
    def get_provider_info(cls, provider_name: str) -> Optional[Dict]:
        """Get detailed information about a specific provider."""
        provider_name = provider_name.lower().strip()

        if provider_name not in cls._provider_info:
            return None

        info = cls._provider_info[provider_name].copy()
        info["name"] = provider_name
        info["active"] = provider_name in cls._providers
        info["configured"] = bool(cls._get_api_key(provider_name))

        return info

    @classmethod
    def get_configured_providers(cls) -> List[str]:
        """Get list of providers that have API keys configured."""
        configured = []
        for name in cls._providers.keys():
            if name == "llama":  # Skip alias
                continue
            if cls._get_api_key(name):
                configured.append(name)
        return configured

    @classmethod
    def compare_providers(cls, estimated_tokens: int = 10000) -> List[Dict]:
        """Compare all providers based on estimated token usage."""
        providers = cls.get_available_providers()

        comparisons = []
        for provider in providers:
            monthly_cost = (estimated_tokens / 1000) * provider["cost_per_1k"]

            comparison = {
                "name": provider["name"],
                "display_name": provider["display_name"],
                "cost_per_1k": provider["cost_per_1k"],
                "monthly_cost": round(monthly_cost, 2),
                "recommended": provider["recommended"],
                "tier": provider["tier"],
                "configured": provider["configured"]
            }
            comparisons.append(comparison)

        comparisons.sort(key=lambda p: p["monthly_cost"])
        return comparisons

    @classmethod
    def recommend_provider(
        cls,
        monthly_tokens: int,
        budget: Optional[float] = None,
        priority: str = "balanced"
    ) -> Dict:
        """Recommend the best provider based on usage and preferences."""
        comparisons = cls.compare_providers(monthly_tokens)
        
        # Filter to configured providers
        configured = [p for p in comparisons if p["configured"]]
        if not configured:
            return {
                "provider": None,
                "error": "No AI providers configured. Please set API keys in environment."
            }
        
        comparisons = configured

        if budget:
            affordable = [p for p in comparisons if p["monthly_cost"] <= budget]
            if not affordable:
                return {
                    "provider": comparisons[0]["name"],
                    "display_name": comparisons[0]["display_name"],
                    "estimated_cost": comparisons[0]["monthly_cost"],
                    "reasoning": f"Budget ${budget:.2f} is below minimum. Cheapest: ${comparisons[0]['monthly_cost']:.2f}",
                    "warning": f"Budget exceeded by ${comparisons[0]['monthly_cost'] - budget:.2f}"
                }
            comparisons = affordable

        if priority == "cost":
            selected = comparisons[0]
            reasoning = f"Cheapest: {selected['display_name']} at ${selected['monthly_cost']:.2f}/month"

        elif priority == "quality":
            selected = next((p for p in comparisons if p["name"] == "claude"), comparisons[0])
            reasoning = f"Best quality: {selected['display_name']} at ${selected['monthly_cost']:.2f}/month"

        elif priority == "speed":
            selected = next((p for p in comparisons if p["name"] == "groq"), comparisons[0])
            reasoning = f"Fastest: {selected['display_name']} at ${selected['monthly_cost']:.2f}/month"

        else:  # balanced
            if monthly_tokens < 50000:
                selected = next((p for p in comparisons if p["name"] == "claude"), comparisons[0])
            else:
                selected = next((p for p in comparisons if p["name"] == "gemini"), comparisons[0])
            reasoning = f"Balanced: {selected['display_name']} at ${selected['monthly_cost']:.2f}/month"

        return {
            "provider": selected["name"],
            "display_name": selected["display_name"],
            "estimated_cost": selected["monthly_cost"],
            "cost_per_1k": selected["cost_per_1k"],
            "reasoning": reasoning
        }

    @classmethod
    def register_provider(
        cls,
        name: str,
        provider_class: Type[AIProvider],
        info: Dict
    ) -> None:
        """Register a new provider (for future extensibility)."""
        name = name.lower().strip()

        if not issubclass(provider_class, AIProvider):
            raise ValueError(f"{provider_class} must inherit from AIProvider")

        cls._providers[name] = provider_class
        cls._provider_info[name] = info

        logger.info(f"Registered new AI provider: {name}")


# Convenience function for quick provider access
def get_ai_provider(
    provider_name: Optional[str] = None,
    api_key: Optional[str] = None,
    **kwargs
) -> AIProvider:
    """
    Convenience function to get an AI provider instance.

    Args:
        provider_name: Provider name (defaults to default provider)
        api_key: API key for the provider
        **kwargs: Additional arguments

    Returns:
        AIProvider instance
    """
    if not provider_name:
        provider_name = AIFactory.get_default_provider()

    return AIFactory.get_provider(provider_name, api_key, **kwargs)
