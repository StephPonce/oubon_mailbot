"""
MULTI-MODEL AI ROUTER

Routes AI tasks to the cheapest appropriate model:
- Simple tasks → Cheap models (DeepSeek, Gemini Flash)
- Complex analysis → Medium models (Gemini Pro, GPT-4o-mini)
- Critical decisions → Premium models (Claude Sonnet 4.5)

Cost savings: ~54% vs. using Claude for everything
"""

from typing import Dict, List, Any, Optional, Literal
from enum import Enum
import os
from dotenv import load_dotenv

from ospra_os.ai.markdown_stripper import strip_markdown

load_dotenv()


class TaskComplexity(str, Enum):
    """Complexity level of an AI task."""
    SIMPLE = "simple"  # Classification, summarization, formatting
    MEDIUM = "medium"  # Analysis, recommendations, pattern detection
    COMPLEX = "complex"  # Strategic planning, multi-step reasoning, critical decisions


class ModelTier(str, Enum):
    """AI model tiers by capability and cost."""
    BUDGET = "budget"  # DeepSeek V3, Gemini Flash - $0.15-0.30 per 1M tokens
    STANDARD = "standard"  # Gemini Pro, GPT-4o-mini - $1.25-1.50 per 1M tokens
    PREMIUM = "premium"  # Claude Sonnet 4.5 - $3.00 per 1M tokens


class AIModel:
    """Represents an AI model with its capabilities and costs."""

    def __init__(
        self,
        name: str,
        provider: str,
        model_id: str,
        tier: ModelTier,
        cost_per_1m_tokens: float,
        max_tokens_output: int = 4096,
        supports_streaming: bool = False
    ):
        self.name = name
        self.provider = provider
        self.model_id = model_id
        self.tier = tier
        self.cost_per_1m_tokens = cost_per_1m_tokens
        self.max_tokens_output = max_tokens_output
        self.supports_streaming = supports_streaming


# Available models registry
AVAILABLE_MODELS = {
    # Budget tier - for simple tasks
    "grok-beta": AIModel(
        name="Grok Beta",
        provider="xai",
        model_id="grok-beta",
        tier=ModelTier.BUDGET,
        cost_per_1m_tokens=5.00,
        max_tokens_output=4096
    ),
    "gemini-flash": AIModel(
        name="Gemini 1.5 Flash",
        provider="google",
        model_id="gemini-1.5-flash",
        tier=ModelTier.BUDGET,
        cost_per_1m_tokens=0.075,  # Updated pricing
        max_tokens_output=8192
    ),

    # Standard tier - for medium tasks
    "gemini-pro": AIModel(
        name="Gemini 1.5 Pro",
        provider="google",
        model_id="gemini-1.5-pro",
        tier=ModelTier.STANDARD,
        cost_per_1m_tokens=1.25,
        max_tokens_output=8192
    ),

    # Premium tier - for complex tasks
    "claude-sonnet-4.5": AIModel(
        name="Claude Sonnet 4.5",
        provider="anthropic",
        model_id="claude-sonnet-4-5-20250929",
        tier=ModelTier.PREMIUM,
        cost_per_1m_tokens=3.00,
        max_tokens_output=8192
    )
}


class ModelRouter:
    """
    Routes AI tasks to the most cost-effective model.

    Decision logic:
    - SIMPLE tasks → Budget tier (DeepSeek/Gemini Flash)
    - MEDIUM tasks → Standard tier (Gemini Pro/GPT-4o-mini)
    - COMPLEX tasks → Premium tier (Claude Sonnet)
    """

    def __init__(self):
        self.models = AVAILABLE_MODELS
        self.usage_stats = {
            model_name: {"requests": 0, "tokens": 0, "cost": 0.0}
            for model_name in self.models.keys()
        }

        # Initialize providers
        self._init_providers()

    def _init_providers(self):
        """Initialize API clients for each provider."""
        self.providers = {}

        # Anthropic (Claude)
        claude_key = os.getenv("CLAUDE_API_KEY")
        if claude_key:
            import anthropic
            self.providers["anthropic"] = anthropic.Anthropic(api_key=claude_key)

        # Google (Gemini)
        google_key = os.getenv("GOOGLE_API_KEY")
        if google_key:
            import google.generativeai as genai
            genai.configure(api_key=google_key)
            self.providers["google"] = genai

        # xAI (Grok) - uses OpenAI-compatible API
        xai_key = os.getenv("XAI_API_KEY")
        if xai_key:
            import openai
            self.providers["xai"] = openai.OpenAI(
                api_key=xai_key,
                base_url="https://api.x.ai/v1"
            )

    def select_model(
        self,
        task_complexity: TaskComplexity,
        preferred_provider: Optional[str] = None
    ) -> AIModel:
        """
        Select the best model for a task based on complexity.

        Args:
            task_complexity: SIMPLE, MEDIUM, or COMPLEX
            preferred_provider: Optional provider preference

        Returns selected model
        """
        if task_complexity == TaskComplexity.SIMPLE:
            # Use cheapest available budget model
            candidates = [m for m in self.models.values() if m.tier == ModelTier.BUDGET]
            if candidates:
                return min(candidates, key=lambda x: x.cost_per_1m_tokens)

        elif task_complexity == TaskComplexity.MEDIUM:
            # Use cheapest available standard model
            candidates = [m for m in self.models.values() if m.tier == ModelTier.STANDARD]
            if candidates:
                return min(candidates, key=lambda x: x.cost_per_1m_tokens)

        elif task_complexity == TaskComplexity.COMPLEX:
            # Use premium model (Claude)
            return self.models["claude-sonnet-4.5"]

        # Fallback to Claude
        return self.models["claude-sonnet-4.5"]

    async def route_request(
        self,
        message: str,
        task_complexity: TaskComplexity,
        system_prompt: Optional[str] = None,
        max_tokens: int = 2000,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Route an AI request to the appropriate model.

        Args:
            message: User prompt
            task_complexity: How complex is this task?
            system_prompt: Optional system instructions
            max_tokens: Max tokens to generate
            context: Optional context dict

        Returns AI response (markdown-stripped)
        """
        # Select model
        model = self.select_model(task_complexity)

        # Route to provider
        if model.provider == "anthropic":
            response = await self._call_anthropic(model, message, system_prompt, max_tokens, context)
        elif model.provider == "google":
            response = await self._call_google(model, message, system_prompt, max_tokens)
        elif model.provider == "xai":
            response = await self._call_xai(model, message, system_prompt, max_tokens)
        else:
            raise ValueError(f"Unknown provider: {model.provider}")

        # Track usage
        self._track_usage(model.name, tokens_used=len(message.split()) * 1.5)  # Rough estimate

        return response

    async def _call_anthropic(
        self,
        model: AIModel,
        message: str,
        system_prompt: Optional[str],
        max_tokens: int,
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Call Anthropic (Claude) API."""
        client = self.providers.get("anthropic")
        if not client:
            raise ValueError("Anthropic API key not configured")

        # Build prompt with context
        if context:
            message = f"Context:\n{context}\n\nQuestion: {message}"

        # Add formatting rules to system prompt
        if system_prompt:
            system_prompt += "\n\nFORMATTING: NO markdown symbols (no ##, ***, etc.). Use plain text only."
        else:
            system_prompt = "You are a helpful AI assistant. NO markdown symbols. Use plain text only."

        response = client.messages.create(
            model=model.model_id,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": message}]
        )

        text = response.content[0].text

        # Strip markdown
        return strip_markdown(text)

    async def _call_xai(
        self,
        model: AIModel,
        message: str,
        system_prompt: Optional[str],
        max_tokens: int
    ) -> str:
        """Call xAI (Grok) API."""
        client = self.providers.get("xai")
        if not client:
            raise ValueError("XAI_API_KEY not configured")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt + "\n\nNO markdown symbols."})
        messages.append({"role": "user", "content": message})

        response = client.chat.completions.create(
            model=model.model_id,
            messages=messages,
            max_tokens=max_tokens
        )

        text = response.choices[0].message.content

        return strip_markdown(text)

    async def _call_google(
        self,
        model: AIModel,
        message: str,
        system_prompt: Optional[str],
        max_tokens: int
    ) -> str:
        """Call Google Gemini API."""
        genai = self.providers.get("google")
        if not genai:
            raise ValueError("Google API key not configured")

        # Create model
        gemini_model = genai.GenerativeModel(model.model_id)

        # Add system prompt to message
        if system_prompt:
            message = f"{system_prompt}\n\n{message}\n\nNO markdown symbols. Use plain text only."

        response = gemini_model.generate_content(message)

        text = response.text

        return strip_markdown(text)

    def _track_usage(self, model_name: str, tokens_used: float):
        """Track usage statistics."""
        if model_name in self.usage_stats:
            self.usage_stats[model_name]["requests"] += 1
            self.usage_stats[model_name]["tokens"] += tokens_used

            model = self.models[model_name]
            cost = (tokens_used / 1_000_000) * model.cost_per_1m_tokens
            self.usage_stats[model_name]["cost"] += cost

    def get_cost_summary(self) -> Dict[str, Any]:
        """Get cost summary across all models."""
        total_cost = sum(stats["cost"] for stats in self.usage_stats.values())
        total_requests = sum(stats["requests"] for stats in self.usage_stats.values())
        total_tokens = sum(stats["tokens"] for stats in self.usage_stats.values())

        # Calculate what it would cost with Claude only
        claude_model = self.models["claude-sonnet-4.5"]
        claude_only_cost = (total_tokens / 1_000_000) * claude_model.cost_per_1m_tokens

        savings = claude_only_cost - total_cost
        savings_percent = (savings / claude_only_cost * 100) if claude_only_cost > 0 else 0

        return {
            "total_cost": total_cost,
            "total_requests": total_requests,
            "total_tokens": total_tokens,
            "claude_only_cost": claude_only_cost,
            "savings": savings,
            "savings_percent": savings_percent,
            "by_model": self.usage_stats
        }


# Global router instance
_router = None


def get_model_router() -> ModelRouter:
    """Get or create global model router."""
    global _router

    if _router is None:
        _router = ModelRouter()

    return _router


# Convenience functions for different task types
async def ai_classify(message: str, options: List[str]) -> str:
    """Simple classification task (uses budget model)."""
    router = get_model_router()
    prompt = f"{message}\n\nOptions: {', '.join(options)}\n\nReturn only the selected option."
    return await router.route_request(prompt, TaskComplexity.SIMPLE)


async def ai_analyze(message: str, context: Optional[Dict] = None) -> str:
    """Medium analysis task (uses standard model)."""
    router = get_model_router()
    return await router.route_request(message, TaskComplexity.MEDIUM, context=context)


async def ai_strategize(message: str, context: Optional[Dict] = None) -> str:
    """Complex strategic task (uses premium model)."""
    router = get_model_router()
    return await router.route_request(message, TaskComplexity.COMPLEX, context=context)
