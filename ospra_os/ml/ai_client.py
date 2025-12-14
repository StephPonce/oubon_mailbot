"""
Unified AI Client - GROK RECOMMENDATION #15

Single interface for all AI providers with automatic routing and cost optimization.

Providers:
- Ollama (local, free)
- Groq (cheap API, fastest)
- Together.ai (cheap API, more options)
- Claude (premium, best quality)

Usage:
    from ospra_os.ml import ai_client

    # Automatic routing based on task type
    response = ai_client.generate(
        task_type="product_description",
        prompt="Write description for yoga mat..."
    )

    # Helper methods for common tasks
    score = ai_client.score_product(product_data)
    reply = ai_client.generate_email_response(customer_email)
    ad = ai_client.generate_ad_copy(product_data)
"""

import os
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from ospra_os.ml.model_router import ModelRouter, ModelConfig, ModelTier

logger = logging.getLogger(__name__)


@dataclass
class AIResponse:
    """Standardized AI response"""
    content: str
    model: str
    tokens: int
    cost: float
    tier: str
    provider: str


class AIProvider(ABC):
    """Abstract base class for AI providers"""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        model_config: Optional[ModelConfig] = None
    ) -> AIResponse:
        """Generate text completion"""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is available"""
        pass


class ClaudeProvider(AIProvider):
    """Anthropic Claude API provider"""

    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY")

    def is_available(self) -> bool:
        return bool(self.api_key)

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        model_config: Optional[ModelConfig] = None
    ) -> AIResponse:
        """Generate using Claude API"""

        if not self.is_available():
            raise ValueError("ANTHROPIC_API_KEY not set")

        try:
            import anthropic

            client = anthropic.Anthropic(api_key=self.api_key)

            # Build messages
            messages = [{"role": "user", "content": prompt}]

            # Use model from config or default to Sonnet
            model_name = model_config.name if model_config else "claude-sonnet-4-20250514"

            # Call API
            response = client.messages.create(
                model=model_name,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt or "",
                messages=messages
            )

            # Extract content
            content = response.content[0].text if response.content else ""

            # Calculate tokens and cost
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            total_tokens = input_tokens + output_tokens

            # Cost calculation (approximate)
            cost_per_1k = model_config.cost_per_1k_tokens if model_config else 0.003
            cost = (total_tokens / 1000) * cost_per_1k

            logger.info(
                f"Claude API: {model_name} - {total_tokens} tokens, ${cost:.4f}"
            )

            return AIResponse(
                content=content,
                model=model_name,
                tokens=total_tokens,
                cost=cost,
                tier="premium",
                provider="claude"
            )

        except Exception as e:
            logger.error(f"Claude API error: {e}")
            raise


class OllamaProvider(AIProvider):
    """Local Ollama provider (free)"""

    def __init__(self):
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    def is_available(self) -> bool:
        """Check if Ollama is running"""
        try:
            import requests
            response = requests.get(f"{self.base_url}/api/tags", timeout=2)
            return response.status_code == 200
        except Exception:
            return False

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        model_config: Optional[ModelConfig] = None
    ) -> AIResponse:
        """Generate using local Ollama"""

        if not self.is_available():
            raise ValueError("Ollama not available at " + self.base_url)

        try:
            import requests

            # Use model from config or default to Llama 8B
            model_name = model_config.name if model_config else "llama3.1:8b"

            # Build request
            data = {
                "model": model_name,
                "prompt": prompt,
                "system": system_prompt or "",
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            }

            # Call Ollama API
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=data,
                timeout=60
            )
            response.raise_for_status()

            result = response.json()
            content = result.get("response", "")

            # Estimate tokens (rough approximation)
            total_tokens = len(prompt.split()) + len(content.split())

            logger.info(
                f"Ollama: {model_name} - {total_tokens} tokens (free)"
            )

            return AIResponse(
                content=content,
                model=model_name,
                tokens=total_tokens,
                cost=0.0,  # Local is free
                tier="local",
                provider="ollama"
            )

        except Exception as e:
            logger.error(f"Ollama error: {e}")
            raise


class GroqProvider(AIProvider):
    """Groq API provider (cheap, fastest)"""

    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")

    def is_available(self) -> bool:
        return bool(self.api_key)

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        model_config: Optional[ModelConfig] = None
    ) -> AIResponse:
        """Generate using Groq API"""

        if not self.is_available():
            raise ValueError("GROQ_API_KEY not set")

        try:
            import requests

            # Use model from config or default to Llama 8B
            model_name = model_config.name if model_config else "llama-3.1-8b-instant"

            # Build messages
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            # Call Groq API
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model_name,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens
                },
                timeout=30
            )
            response.raise_for_status()

            result = response.json()
            content = result["choices"][0]["message"]["content"]

            # Get token usage
            usage = result.get("usage", {})
            total_tokens = usage.get("total_tokens", 0)

            # Calculate cost
            cost_per_1k = model_config.cost_per_1k_tokens if model_config else 0.00005
            cost = (total_tokens / 1000) * cost_per_1k

            logger.info(
                f"Groq API: {model_name} - {total_tokens} tokens, ${cost:.4f}"
            )

            return AIResponse(
                content=content,
                model=model_name,
                tokens=total_tokens,
                cost=cost,
                tier="cheap",
                provider="groq"
            )

        except Exception as e:
            logger.error(f"Groq API error: {e}")
            raise


class TogetherProvider(AIProvider):
    """Together.ai API provider (cheap, more models)"""

    def __init__(self):
        self.api_key = os.getenv("TOGETHER_API_KEY")

    def is_available(self) -> bool:
        return bool(self.api_key)

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        model_config: Optional[ModelConfig] = None
    ) -> AIResponse:
        """Generate using Together.ai API"""

        if not self.is_available():
            raise ValueError("TOGETHER_API_KEY not set")

        try:
            import requests

            # Use model from config or default
            model_name = model_config.name if model_config else "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"

            # Build messages
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            # Call Together API
            response = requests.post(
                "https://api.together.xyz/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model_name,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens
                },
                timeout=30
            )
            response.raise_for_status()

            result = response.json()
            content = result["choices"][0]["message"]["content"]

            # Get token usage
            usage = result.get("usage", {})
            total_tokens = usage.get("total_tokens", 0)

            # Calculate cost
            cost_per_1k = model_config.cost_per_1k_tokens if model_config else 0.00018
            cost = (total_tokens / 1000) * cost_per_1k

            logger.info(
                f"Together API: {model_name} - {total_tokens} tokens, ${cost:.4f}"
            )

            return AIResponse(
                content=content,
                model=model_name,
                tokens=total_tokens,
                cost=cost,
                tier="cheap",
                provider="together"
            )

        except Exception as e:
            logger.error(f"Together API error: {e}")
            raise


class UnifiedAIClient:
    """
    Unified AI client with intelligent routing.

    Automatically routes tasks to optimal model based on complexity,
    cost, and quality requirements.

    Example:
        client = UnifiedAIClient()

        # Simple task -> local/cheap
        description = client.generate(
            task_type="product_description",
            prompt="Write description for yoga mat"
        )

        # Complex task -> Claude
        strategy = client.generate(
            task_type="market_research",
            prompt="Analyze fitness market trends"
        )
    """

    def __init__(self):
        self.router = ModelRouter()

        # Initialize providers
        self.providers = {
            "ollama": OllamaProvider(),
            "groq": GroqProvider(),
            "together": TogetherProvider(),
            "claude": ClaudeProvider(),
        }

        logger.info("UnifiedAIClient initialized")
        logger.info(f"Available providers: {[p for p, c in self.providers.items() if c.is_available()]}")

    def generate(
        self,
        prompt: str,
        task_type: str = "general",
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        force_tier: Optional[ModelTier] = None,
        quality_threshold: float = 0.8
    ) -> AIResponse:
        """
        Generate AI response with automatic routing.

        Args:
            prompt: User prompt
            task_type: Task type for routing (e.g., "product_description")
            system_prompt: System instructions
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
            force_tier: Force specific tier (override routing)
            quality_threshold: Minimum quality (0-1)

        Returns:
            AIResponse with content, cost, and metadata
        """

        # Route to optimal model
        model_config = self.router.route(
            task_type=task_type,
            force_tier=force_tier,
            quality_threshold=quality_threshold
        )

        logger.info(
            f"Routing '{task_type}' to {model_config.tier.value} "
            f"({model_config.name})"
        )

        # Select provider based on tier
        provider = self._get_provider_for_tier(model_config.tier)

        # Generate response
        response = provider.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            model_config=model_config
        )

        # Track usage for cost analysis
        self.router.track_usage(model_config, response.tokens)

        return response

    def _get_provider_for_tier(self, tier: ModelTier) -> AIProvider:
        """Get available provider for a tier"""

        if tier == ModelTier.LOCAL:
            if self.providers["ollama"].is_available():
                return self.providers["ollama"]
            # Fall back to Groq if local not available
            logger.warning("Local Ollama not available, falling back to Groq")
            if self.providers["groq"].is_available():
                return self.providers["groq"]

        elif tier == ModelTier.CHEAP:
            # Prefer Groq (faster, cheaper)
            if self.providers["groq"].is_available():
                return self.providers["groq"]
            if self.providers["together"].is_available():
                return self.providers["together"]

        elif tier == ModelTier.PREMIUM:
            if self.providers["claude"].is_available():
                return self.providers["claude"]

        # Ultimate fallback
        raise ValueError(
            f"No available provider for tier {tier.value}. "
            "Check API keys and Ollama installation."
        )

    def get_usage_report(self) -> Dict[str, Any]:
        """Get cost tracking report"""
        return self.router.get_usage_report()

    def reset_stats(self):
        """Reset usage statistics"""
        self.router.reset_stats()

    # ========================================================================
    # HELPER METHODS FOR COMMON TASKS
    # ========================================================================

    def score_product(
        self,
        product_name: str,
        category: str,
        price: float,
        competition: str,
        trend_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Score a product's potential (1-100).

        Returns score + reasoning + recommendations.
        """

        prompt = f"""Score this product's e-commerce potential (1-100):

Product: {product_name}
Category: {category}
Price: ${price}
Competition: {competition}
Trend Data: {trend_data or 'Not available'}

Provide:
1. Score (1-100)
2. Reasoning (2-3 sentences)
3. Top 3 recommendations for improvement

Format as JSON:
{{
    "score": 85,
    "reasoning": "...",
    "recommendations": ["...", "...", "..."]
}}
"""

        response = self.generate(
            task_type="product_scoring",
            prompt=prompt,
            temperature=0.3,  # Lower temp for consistency
            max_tokens=500
        )

        # Parse JSON response
        try:
            import json
            result = json.loads(response.content)
            result["_meta"] = {
                "model": response.model,
                "cost": response.cost,
                "tier": response.tier
            }
            return result
        except json.JSONDecodeError:
            # Fallback if not valid JSON
            return {
                "score": 50,
                "reasoning": response.content[:200],
                "recommendations": [],
                "_meta": {
                    "model": response.model,
                    "cost": response.cost,
                    "tier": response.tier
                }
            }

    def generate_email_response(
        self,
        customer_email: str,
        context: Optional[str] = None,
        tone: str = "friendly"
    ) -> str:
        """
        Generate email response to customer inquiry.

        Args:
            customer_email: Customer's email content
            context: Additional context (order status, etc.)
            tone: Response tone (friendly, professional, apologetic)

        Returns:
            Email response text
        """

        system_prompt = f"""You are a customer service agent for an e-commerce store.
Write a {tone} response to customer emails.
Be helpful, clear, and concise.
"""

        prompt = f"""Customer Email:
{customer_email}

{f'Context: {context}' if context else ''}

Write a response:"""

        response = self.generate(
            task_type="email_response",
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.7,
            max_tokens=300
        )

        return response.content

    def generate_ad_copy(
        self,
        product_name: str,
        key_features: List[str],
        target_audience: str,
        platform: str = "facebook"
    ) -> Dict[str, str]:
        """
        Generate ad copy for a product.

        Args:
            product_name: Product name
            key_features: List of key features
            target_audience: Who to target
            platform: Ad platform (facebook, google, tiktok)

        Returns:
            Dict with headline, body, cta
        """

        prompt = f"""Create {platform} ad copy for:

Product: {product_name}
Features: {', '.join(key_features)}
Audience: {target_audience}

Provide:
1. Headline (max 40 chars)
2. Body copy (max 125 chars)
3. Call-to-action (max 20 chars)

Format as JSON:
{{
    "headline": "...",
    "body": "...",
    "cta": "..."
}}
"""

        response = self.generate(
            task_type="ad_copy",
            prompt=prompt,
            temperature=0.8,  # Higher for creativity
            max_tokens=200
        )

        # Parse JSON response
        try:
            import json
            result = json.loads(response.content)
            result["_meta"] = {
                "model": response.model,
                "cost": response.cost
            }
            return result
        except json.JSONDecodeError:
            return {
                "headline": product_name[:40],
                "body": response.content[:125],
                "cta": "Shop Now",
                "_meta": {
                    "model": response.model,
                    "cost": response.cost
                }
            }

    def generate_product_description(
        self,
        product_name: str,
        features: List[str],
        benefits: List[str],
        style: str = "modern"
    ) -> str:
        """
        Generate product description.

        Args:
            product_name: Product name
            features: Technical features
            benefits: Customer benefits
            style: Writing style (modern, luxury, casual)

        Returns:
            Product description (2-3 paragraphs)
        """

        prompt = f"""Write a {style} product description for:

Product: {product_name}
Features: {', '.join(features)}
Benefits: {', '.join(benefits)}

Write 2-3 compelling paragraphs that sell the product.
Focus on benefits over features.
"""

        response = self.generate(
            task_type="product_description",
            prompt=prompt,
            temperature=0.8,
            max_tokens=400
        )

        return response.content


# Global singleton instance
ai_client = UnifiedAIClient()
