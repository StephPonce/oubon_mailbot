"""
AI Factory for Provider Selection

This module provides a factory pattern for instantiating AI providers
and managing provider selection across the OspraOS platform.

Author: OspraOS
Date: November 2025
"""

from typing import Dict, List, Optional, Type
import logging

from ospra_os.ai.providers.base import AIProvider
from ospra_os.ai.providers.claude import ClaudeProvider
from ospra_os.ai.providers.openai_provider import OpenAIProvider
from ospra_os.ai.providers.gemini import GeminiProvider

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
        # "grok": GrokProvider,  # Coming soon
    }

    # Provider display information
    _provider_info: Dict[str, Dict[str, any]] = {
        "claude": {
            "display_name": "Claude (Anthropic)",
            "description": "Best for analytical reasoning and detailed analysis",
            "model": "claude-sonnet-4-20250514",
            "cost_per_1k": 0.003,
            "recommended": True,
            "tier": "premium",
            "strengths": ["Analysis", "Reasoning", "Consistency"],
            "best_for": ["Product analysis", "Market research", "Detailed reports"]
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
            "model": "gemini-1.5-flash",
            "cost_per_1k": 0.00025,
            "recommended": True,
            "tier": "budget",
            "strengths": ["Cost efficiency", "Speed", "Scale"],
            "best_for": ["High volume", "Budget-conscious", "Fast operations"]
        }
    }

    @classmethod
    def get_provider(
        cls,
        provider_name: str,
        api_key: str,
        **kwargs
    ) -> AIProvider:
        """
        Get an AI provider instance by name.

        Args:
            provider_name: Name of the provider ("claude", "openai", "gemini")
            api_key: API key for the provider
            **kwargs: Additional arguments passed to provider constructor

        Returns:
            AIProvider instance

        Raises:
            ValueError: If provider_name is not recognized

        Example:
            >>> provider = AIFactory.get_provider("claude", api_key="sk-...")
            >>> result = await provider.analyze_product(data)
        """
        provider_name = provider_name.lower().strip()

        if provider_name not in cls._providers:
            available = ", ".join(cls._providers.keys())
            raise ValueError(
                f"Unknown provider: '{provider_name}'. "
                f"Available providers: {available}"
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
    def get_available_providers(cls, include_inactive: bool = False) -> List[Dict]:
        """
        Get list of all available AI providers with their information.

        Args:
            include_inactive: Include providers not yet implemented

        Returns:
            List of provider info dictionaries

        Example:
            >>> providers = AIFactory.get_available_providers()
            >>> for p in providers:
            ...     print(f"{p['display_name']}: ${p['cost_per_1k']}/1K")
        """
        providers = []

        for name, info in cls._provider_info.items():
            # Skip if provider class doesn't exist and include_inactive is False
            if not include_inactive and name not in cls._providers:
                continue

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
                "active": name in cls._providers
            }
            providers.append(provider_data)

        # Sort by cost (cheapest first)
        providers.sort(key=lambda p: p["cost_per_1k"])

        return providers

    @classmethod
    def get_default_provider(cls) -> str:
        """
        Get the default recommended provider name.

        Returns:
            Provider name string

        Example:
            >>> default = AIFactory.get_default_provider()
            >>> print(default)  # "claude"
        """
        # Return Claude as the recommended default (best balance of quality/cost)
        return "claude"

    @classmethod
    def get_cheapest_provider(cls) -> str:
        """
        Get the cheapest available provider.

        Returns:
            Provider name string

        Example:
            >>> cheapest = AIFactory.get_cheapest_provider()
            >>> print(cheapest)  # "gemini"
        """
        return "gemini"

    @classmethod
    def validate_provider(cls, provider_name: str) -> bool:
        """
        Check if a provider name is valid and available.

        Args:
            provider_name: Name to validate

        Returns:
            True if provider exists, False otherwise

        Example:
            >>> AIFactory.validate_provider("claude")
            True
            >>> AIFactory.validate_provider("unknown")
            False
        """
        return provider_name.lower().strip() in cls._providers

    @classmethod
    def get_provider_info(cls, provider_name: str) -> Optional[Dict]:
        """
        Get detailed information about a specific provider.

        Args:
            provider_name: Name of the provider

        Returns:
            Provider info dictionary or None if not found

        Example:
            >>> info = AIFactory.get_provider_info("gemini")
            >>> print(info["cost_per_1k"])  # 0.00025
        """
        provider_name = provider_name.lower().strip()

        if provider_name not in cls._provider_info:
            return None

        info = cls._provider_info[provider_name].copy()
        info["name"] = provider_name
        info["active"] = provider_name in cls._providers

        return info

    @classmethod
    def compare_providers(
        cls,
        estimated_tokens: int = 10000
    ) -> List[Dict]:
        """
        Compare all providers based on estimated token usage.

        Args:
            estimated_tokens: Estimated monthly token usage

        Returns:
            List of providers with cost projections, sorted by cost

        Example:
            >>> comparison = AIFactory.compare_providers(estimated_tokens=50000)
            >>> for p in comparison:
            ...     print(f"{p['name']}: ${p['monthly_cost']:.2f}")
        """
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
                "tier": provider["tier"]
            }
            comparisons.append(comparison)

        # Sort by monthly cost (cheapest first)
        comparisons.sort(key=lambda p: p["monthly_cost"])

        return comparisons

    @classmethod
    def recommend_provider(
        cls,
        monthly_tokens: int,
        budget: Optional[float] = None,
        priority: str = "balanced"
    ) -> Dict:
        """
        Recommend the best provider based on usage and preferences.

        Args:
            monthly_tokens: Estimated monthly token usage
            budget: Optional monthly budget limit (USD)
            priority: "cost", "quality", or "balanced"

        Returns:
            Recommendation dictionary with provider and reasoning

        Example:
            >>> rec = AIFactory.recommend_provider(
            ...     monthly_tokens=100000,
            ...     budget=50.00,
            ...     priority="balanced"
            ... )
            >>> print(rec["provider"])  # "claude" or "gemini"
            >>> print(rec["reasoning"])
        """
        comparisons = cls.compare_providers(monthly_tokens)

        # If budget constraint
        if budget:
            affordable = [p for p in comparisons if p["monthly_cost"] <= budget]
            if not affordable:
                return {
                    "provider": comparisons[0]["name"],  # Cheapest
                    "display_name": comparisons[0]["display_name"],
                    "estimated_cost": comparisons[0]["monthly_cost"],
                    "reasoning": (
                        f"Your budget of ${budget:.2f} is below the minimum cost. "
                        f"We recommend {comparisons[0]['display_name']} at "
                        f"${comparisons[0]['monthly_cost']:.2f}/month (cheapest option)."
                    ),
                    "warning": f"Budget exceeded by ${comparisons[0]['monthly_cost'] - budget:.2f}"
                }
            comparisons = affordable

        # Priority-based selection
        if priority == "cost":
            # Cheapest option
            selected = comparisons[0]
            reasoning = (
                f"Based on your cost priority, we recommend {selected['display_name']}. "
                f"Estimated monthly cost: ${selected['monthly_cost']:.2f} "
                f"for {monthly_tokens:,} tokens."
            )

        elif priority == "quality":
            # Highest quality (Claude)
            selected = next((p for p in comparisons if p["name"] == "claude"), comparisons[0])
            reasoning = (
                f"Based on your quality priority, we recommend {selected['display_name']}. "
                f"Best analytical reasoning and consistency. "
                f"Estimated monthly cost: ${selected['monthly_cost']:.2f}."
            )

        else:  # balanced
            # If budget allows, use Claude; otherwise Gemini
            if monthly_tokens < 50000:
                # Low volume - Claude is affordable
                selected = next((p for p in comparisons if p["name"] == "claude"), comparisons[0])
                reasoning = (
                    f"For your usage level ({monthly_tokens:,} tokens/month), "
                    f"we recommend {selected['display_name']} for best quality. "
                    f"Estimated monthly cost: ${selected['monthly_cost']:.2f}."
                )
            else:
                # High volume - Gemini for cost efficiency
                selected = next((p for p in comparisons if p["name"] == "gemini"), comparisons[0])
                reasoning = (
                    f"For high-volume usage ({monthly_tokens:,} tokens/month), "
                    f"we recommend {selected['display_name']} for cost efficiency. "
                    f"Estimated monthly cost: ${selected['monthly_cost']:.2f}. "
                    f"Consider using Claude for critical tasks only."
                )

        return {
            "provider": selected["name"],
            "display_name": selected["display_name"],
            "estimated_cost": selected["monthly_cost"],
            "cost_per_1k": selected["cost_per_1k"],
            "reasoning": reasoning,
            "alternative": None if len(comparisons) < 2 else {
                "provider": comparisons[1]["name"],
                "display_name": comparisons[1]["display_name"],
                "estimated_cost": comparisons[1]["monthly_cost"]
            }
        }

    @classmethod
    def register_provider(
        cls,
        name: str,
        provider_class: Type[AIProvider],
        info: Dict
    ) -> None:
        """
        Register a new provider (for future extensibility).

        Args:
            name: Provider name (lowercase)
            provider_class: Provider class implementing AIProvider
            info: Provider information dictionary

        Example:
            >>> AIFactory.register_provider("grok", GrokProvider, {...})
        """
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

    Example:
        >>> ai = get_ai_provider("gemini", api_key="...")
        >>> result = await ai.chat("What's trending?")
    """
    if not provider_name:
        provider_name = AIFactory.get_default_provider()

    if not api_key:
        raise ValueError("api_key is required")

    return AIFactory.get_provider(provider_name, api_key, **kwargs)
