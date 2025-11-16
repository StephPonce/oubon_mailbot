"""
AI Provider Abstract Base Class

This module defines the base interface that all AI providers must implement.
Supports multiple AI providers (Claude, OpenAI, Gemini, Grok) with a consistent API.

Author: OspraOS
Date: November 2025
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

# Configure logging
logger = logging.getLogger(__name__)


class AIProviderError(Exception):
    """Base exception for AI provider errors"""
    pass


class APIKeyError(AIProviderError):
    """Raised when API key is invalid or missing"""
    pass


class RateLimitError(AIProviderError):
    """Raised when API rate limit is exceeded"""
    pass


class InvalidResponseError(AIProviderError):
    """Raised when API returns invalid response"""
    pass


class AIProvider(ABC):
    """
    Abstract base class for all AI providers.

    All AI providers (Claude, OpenAI, Gemini, Grok) must inherit from this class
    and implement the abstract methods defined here.

    This ensures a consistent interface across all providers, allowing users to
    switch providers seamlessly without changing application code.

    Attributes:
        api_key (str): API key for the provider
        provider_name (str): Name of the provider (claude, openai, gemini, grok)
        model_name (str): Specific model being used (claude-sonnet-4, gpt-4, etc.)
        cost_per_1k (float): Cost per 1,000 tokens in USD
    """

    def __init__(self, api_key: str):
        """
        Initialize the AI provider.

        Args:
            api_key: API key for the provider

        Raises:
            APIKeyError: If API key is invalid or missing
        """
        if not api_key or not isinstance(api_key, str):
            raise APIKeyError("API key must be a non-empty string")

        self.api_key = api_key
        self.provider_name = "base"
        self.model_name = "unknown"
        self.cost_per_1k = 0.0
        self._total_tokens_used = 0
        self._total_cost = 0.0
        self._request_count = 0

        logger.info(f"Initialized {self.provider_name} provider")

    # ========================================================================
    # ABSTRACT METHODS - Must be implemented by all providers
    # ========================================================================

    @abstractmethod
    async def analyze_product(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a product and return AI-powered intelligence.

        This is the core analysis method that evaluates a product's potential,
        identifies risks, and provides actionable recommendations.

        Args:
            product_data: Product information containing:
                - name (str): Product name
                - niche (str): Product niche/category
                - trend_score (float): Trending score (0-100)
                - supplier_cost (float, optional): Cost from supplier
                - description (str, optional): Product description
                - features (List[str], optional): Product features
                - images (List[str], optional): Image URLs

        Returns:
            Dictionary containing:
                - score (float): Overall product score (0-10)
                - explanation (str): Why this product will succeed/fail
                - recommendations (List[str]): Actionable suggestions
                - risks (List[str]): Potential challenges and risks
                - target_audience (str): Ideal customer profile
                - pricing_suggestion (float): Suggested retail price
                - confidence (float): Confidence level (0-1)
                - market_insights (str, optional): Market trends and insights
                - competitive_advantage (str, optional): Unique selling points

        Raises:
            InvalidResponseError: If API returns invalid data
            RateLimitError: If rate limit is exceeded

        Example:
            >>> provider = ClaudeProvider(api_key="...")
            >>> result = await provider.analyze_product({
            ...     "name": "Smart LED Strip",
            ...     "niche": "smart_home",
            ...     "trend_score": 85.5,
            ...     "supplier_cost": 12.50
            ... })
            >>> print(result["score"])  # 8.5
            >>> print(result["explanation"])  # "This product has strong..."
        """
        pass

    @abstractmethod
    async def generate_description(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate SEO-optimized product description and marketing copy.

        Creates compelling, conversion-focused descriptions optimized for
        search engines and e-commerce platforms (Shopify, Amazon, etc.).

        Args:
            product: Product information containing:
                - name (str): Product name
                - niche (str): Product niche/category
                - features (List[str], optional): Product features
                - target_market (str): Target market (US, CA, UK, EU, AU)
                - specifications (Dict, optional): Technical specs
                - benefits (List[str], optional): Key benefits

        Returns:
            Dictionary containing:
                - title (str): SEO-optimized product title (60-70 chars)
                - description (str): Full HTML-formatted description
                - bullet_points (List[str]): 5-7 key feature bullets
                - meta_description (str): SEO meta description (150-160 chars)
                - tags (List[str]): Relevant product tags/keywords
                - headline (str): Catchy marketing headline
                - call_to_action (str, optional): Conversion-focused CTA

        Raises:
            InvalidResponseError: If API returns invalid data

        Example:
            >>> result = await provider.generate_description({
            ...     "name": "Wireless Earbuds Pro",
            ...     "niche": "electronics",
            ...     "features": ["ANC", "30hr battery", "IPX7"],
            ...     "target_market": "US"
            ... })
            >>> print(result["title"])  # "Wireless Earbuds Pro - 30Hr Battery..."
        """
        pass

    @abstractmethod
    async def chat(self, message: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Chat interface for dashboard AI assistant.

        Provides conversational AI assistance for users, answering questions
        about products, stores, analytics, and providing recommendations.

        Args:
            message: User's message/question
            context: Optional context dictionary containing:
                - current_products (List[Dict]): User's current products
                - store_metrics (Dict): Revenue, conversion rate, etc.
                - recent_activity (List[str]): Recent user actions
                - user_preferences (Dict): User settings and preferences

        Returns:
            AI response as a formatted string

        Raises:
            InvalidResponseError: If API returns invalid data

        Example:
            >>> response = await provider.chat(
            ...     "What products should I add to my smart home store?",
            ...     context={"store_metrics": {"niche": "smart_home"}}
            ... )
            >>> print(response)  # "Based on current trends, I recommend..."
        """
        pass

    @abstractmethod
    async def optimize_pricing(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Suggest optimal pricing strategy for maximum profit.

        Analyzes supplier cost, competitor pricing, market demand, and profit
        margins to recommend the best pricing strategy.

        Args:
            product_data: Product and market data containing:
                - name (str): Product name
                - supplier_cost (float): Cost from supplier
                - competitor_prices (List[float]): Competitor price points
                - niche (str): Product niche/category
                - target_market (str, optional): Target market
                - desired_margin (float, optional): Desired profit margin %

        Returns:
            Dictionary containing:
                - suggested_price (float): Recommended retail price
                - compare_at_price (float): "Was" price for discounts
                - profit_margin (float): Profit margin percentage
                - strategy (str): Pricing strategy (competitive/premium/value)
                - reasoning (str): Explanation of pricing recommendation
                - price_range (Dict): min/max recommended prices
                - market_position (str, optional): Where price sits in market

        Raises:
            InvalidResponseError: If API returns invalid data

        Example:
            >>> result = await provider.optimize_pricing({
            ...     "name": "Yoga Mat",
            ...     "supplier_cost": 8.50,
            ...     "competitor_prices": [19.99, 24.99, 29.99],
            ...     "niche": "fitness"
            ... })
            >>> print(result["suggested_price"])  # 22.99
            >>> print(result["strategy"])  # "competitive"
        """
        pass

    @abstractmethod
    async def test_connection(self) -> bool:
        """
        Test if API credentials are valid and connection works.

        Performs a lightweight API call to verify the API key is valid
        and the provider is accessible.

        Returns:
            True if connection successful, False otherwise

        Raises:
            APIKeyError: If API key is invalid

        Example:
            >>> provider = OpenAIProvider(api_key="sk-...")
            >>> is_valid = await provider.test_connection()
            >>> print(is_valid)  # True
        """
        pass

    # ========================================================================
    # CONCRETE METHODS - Implemented for all providers
    # ========================================================================

    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the current model and provider.

        Returns:
            Dictionary containing:
                - provider (str): Provider name (claude, openai, gemini)
                - model (str): Model name (claude-sonnet-4, gpt-4, etc.)
                - cost_per_1k_tokens (float): Cost per 1,000 tokens in USD
                - total_tokens_used (int): Total tokens used in this session
                - total_cost (float): Total cost incurred in this session
                - request_count (int): Number of API requests made

        Example:
            >>> info = provider.get_model_info()
            >>> print(info)
            {
                "provider": "claude",
                "model": "claude-sonnet-4",
                "cost_per_1k_tokens": 0.003,
                "total_tokens_used": 15420,
                "total_cost": 0.046,
                "request_count": 12
            }
        """
        return {
            "provider": self.provider_name,
            "model": self.model_name,
            "cost_per_1k_tokens": self.cost_per_1k,
            "total_tokens_used": self._total_tokens_used,
            "total_cost": round(self._total_cost, 4),
            "request_count": self._request_count
        }

    def calculate_cost(self, tokens: int) -> float:
        """
        Calculate cost for a given number of tokens.

        Args:
            tokens: Number of tokens

        Returns:
            Cost in USD (rounded to 4 decimal places)

        Example:
            >>> cost = provider.calculate_cost(5000)
            >>> print(cost)  # 0.015 (for Claude at $0.003/1K)
        """
        cost = (tokens / 1000) * self.cost_per_1k
        return round(cost, 4)

    def track_usage(self, tokens: int) -> None:
        """
        Track token usage and cost.

        Updates internal counters for monitoring usage and costs.
        Should be called after each API request.

        Args:
            tokens: Number of tokens used in the request

        Example:
            >>> provider.track_usage(1250)
            >>> info = provider.get_model_info()
            >>> print(info["total_tokens_used"])  # 1250
        """
        self._total_tokens_used += tokens
        self._total_cost += self.calculate_cost(tokens)
        self._request_count += 1

        logger.debug(
            f"Usage tracked: {tokens} tokens, "
            f"${self.calculate_cost(tokens):.4f} cost, "
            f"Total: {self._total_tokens_used} tokens, "
            f"${self._total_cost:.4f} total cost"
        )

    def reset_usage(self) -> None:
        """
        Reset usage statistics.

        Resets token count, cost, and request count to zero.
        Useful for tracking usage over specific time periods.

        Example:
            >>> provider.reset_usage()
            >>> info = provider.get_model_info()
            >>> print(info["total_tokens_used"])  # 0
        """
        self._total_tokens_used = 0
        self._total_cost = 0.0
        self._request_count = 0
        logger.info(f"Usage statistics reset for {self.provider_name}")

    def validate_product_data(self, product_data: Dict[str, Any]) -> None:
        """
        Validate product data before processing.

        Checks that required fields are present and valid.

        Args:
            product_data: Product data to validate

        Raises:
            ValueError: If required fields are missing or invalid

        Example:
            >>> provider.validate_product_data({
            ...     "name": "Test Product",
            ...     "niche": "electronics"
            ... })  # OK
            >>> provider.validate_product_data({})  # Raises ValueError
        """
        required_fields = ["name", "niche"]

        for field in required_fields:
            if field not in product_data:
                raise ValueError(f"Missing required field: {field}")

            if not product_data[field]:
                raise ValueError(f"Field '{field}' cannot be empty")

        # Validate numeric fields if present
        numeric_fields = ["trend_score", "supplier_cost", "pricing_suggestion"]
        for field in numeric_fields:
            if field in product_data:
                value = product_data[field]
                if value is not None and not isinstance(value, (int, float)):
                    raise ValueError(f"Field '{field}' must be numeric, got {type(value)}")

    def __str__(self) -> str:
        """String representation of the provider."""
        return f"{self.provider_name.capitalize()}Provider(model={self.model_name})"

    def __repr__(self) -> str:
        """Detailed string representation."""
        return (
            f"{self.__class__.__name__}("
            f"provider={self.provider_name}, "
            f"model={self.model_name}, "
            f"cost_per_1k=${self.cost_per_1k})"
        )


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_available_providers() -> List[str]:
    """
    Get list of available AI providers.

    Returns:
        List of provider names (lowercase)

    Example:
        >>> providers = get_available_providers()
        >>> print(providers)  # ['claude', 'openai', 'gemini', 'grok']
    """
    return ["claude", "openai", "gemini", "grok"]


def get_provider_info() -> Dict[str, Dict[str, Any]]:
    """
    Get information about all available providers.

    Returns:
        Dictionary mapping provider name to info dict

    Example:
        >>> info = get_provider_info()
        >>> print(info["claude"]["cost_per_1k"])  # 0.003
    """
    return {
        "claude": {
            "name": "Claude Sonnet 4",
            "model": "claude-sonnet-4-20250514",
            "cost_per_1k": 0.003,
            "speed_rating": 5,
            "quality_rating": 5,
            "best_for": ["Product analysis", "Detailed descriptions", "Market research"],
            "available": True
        },
        "openai": {
            "name": "OpenAI GPT-4",
            "model": "gpt-4-turbo",
            "cost_per_1k": 0.03,
            "speed_rating": 4,
            "quality_rating": 5,
            "best_for": ["Complex reasoning", "Code generation", "Creative writing"],
            "available": True
        },
        "gemini": {
            "name": "Google Gemini Pro",
            "model": "gemini-pro",
            "cost_per_1k": 0.00025,
            "speed_rating": 5,
            "quality_rating": 4,
            "best_for": ["Budget-conscious users", "High volume", "Quick responses"],
            "available": True
        },
        "grok": {
            "name": "Grok AI",
            "model": "grok-1",
            "cost_per_1k": 0.005,
            "speed_rating": 4,
            "quality_rating": 4,
            "best_for": ["Real-time data", "News analysis", "Trend detection"],
            "available": False  # Coming soon
        }
    }
