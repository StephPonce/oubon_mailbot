"""
Model Router - GROK RECOMMENDATION #15

Intelligently routes AI tasks to the optimal model based on:
- Task complexity (simple/medium/complex)
- Cost optimization (70% savings target)
- Quality requirements
- Model availability

Architecture:

 Task Router   Local Llama (80% tasks, $0)
  Cheap API (15% tasks, ~$45/mo)
                 Claude (5% tasks, premium quality)
"""

import os
from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class ModelTier(str, Enum):
    """Model cost tiers"""
    LOCAL = "local"       # Self-hosted Llama (free, slower)
    CHEAP = "cheap"       # Together.ai / Groq Llama API (cheap, fast)
    PREMIUM = "premium"   # Claude API (expensive, best quality)


class TaskComplexity(str, Enum):
    """Task complexity levels"""
    SIMPLE = "simple"     # Routine, well-defined tasks
    MEDIUM = "medium"     # Some nuance required
    COMPLEX = "complex"   # Requires deep reasoning


@dataclass
class ModelConfig:
    """Model configuration"""
    name: str
    tier: ModelTier
    cost_per_1k_tokens: float
    max_tokens: int
    supports_functions: bool = False
    supports_vision: bool = False


# Available models with cost data
MODELS = {
    # Local (Ollama) - FREE
    "llama3.1-8b-local": ModelConfig(
        name="llama3.1:8b",
        tier=ModelTier.LOCAL,
        cost_per_1k_tokens=0.0,
        max_tokens=8192
    ),
    "llama3.1-70b-local": ModelConfig(
        name="llama3.1:70b",
        tier=ModelTier.LOCAL,
        cost_per_1k_tokens=0.0,
        max_tokens=8192
    ),

    # Cheap API (Together.ai) - $0.18 per 1M tokens
    "llama3.1-8b-together": ModelConfig(
        name="meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
        tier=ModelTier.CHEAP,
        cost_per_1k_tokens=0.00018,
        max_tokens=8192
    ),
    "llama3.1-70b-together": ModelConfig(
        name="meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
        tier=ModelTier.CHEAP,
        cost_per_1k_tokens=0.00088,
        max_tokens=8192
    ),

    # Cheap API (Groq) - $0.05 per 1M tokens (FASTEST)
    "llama3.1-8b-groq": ModelConfig(
        name="llama-3.1-8b-instant",
        tier=ModelTier.CHEAP,
        cost_per_1k_tokens=0.00005,
        max_tokens=8192
    ),
    "llama3.1-70b-groq": ModelConfig(
        name="llama-3.1-70b-versatile",
        tier=ModelTier.CHEAP,
        cost_per_1k_tokens=0.00059,
        max_tokens=8192
    ),

    # Premium (Claude) - $3.00 per 1M tokens
    "claude-sonnet": ModelConfig(
        name="claude-sonnet-4-20250514",
        tier=ModelTier.PREMIUM,
        cost_per_1k_tokens=0.003,
        max_tokens=8192,
        supports_functions=True,
        supports_vision=True
    ),
    "claude-opus": ModelConfig(
        name="claude-opus-4-20250514",
        tier=ModelTier.PREMIUM,
        cost_per_1k_tokens=0.015,
        max_tokens=8192,
        supports_functions=True,
        supports_vision=True
    ),
}


# Task -> Complexity mapping
# This determines which model tier handles each task type
TASK_COMPLEXITY = {
    # SIMPLE tasks - Local Llama or Groq (80% of tasks)
    "product_description": TaskComplexity.SIMPLE,
    "email_acknowledgment": TaskComplexity.SIMPLE,
    "ad_copy_variation": TaskComplexity.SIMPLE,
    "data_extraction": TaskComplexity.SIMPLE,
    "sentiment_analysis": TaskComplexity.SIMPLE,
    "keyword_extraction": TaskComplexity.SIMPLE,
    "category_classification": TaskComplexity.SIMPLE,
    "price_formatting": TaskComplexity.SIMPLE,

    # MEDIUM tasks - Fine-tuned Llama or Together.ai (15% of tasks)
    "product_scoring": TaskComplexity.MEDIUM,
    "email_response": TaskComplexity.MEDIUM,
    "ad_copy": TaskComplexity.MEDIUM,
    "price_recommendation": TaskComplexity.MEDIUM,
    "trend_analysis": TaskComplexity.MEDIUM,
    "competitor_comparison": TaskComplexity.MEDIUM,
    "seo_optimization": TaskComplexity.MEDIUM,

    # COMPLEX tasks - Claude only (5% of tasks)
    "market_research": TaskComplexity.COMPLEX,
    "strategy_planning": TaskComplexity.COMPLEX,
    "competitor_analysis": TaskComplexity.COMPLEX,
    "anomaly_investigation": TaskComplexity.COMPLEX,
    "multi_step_reasoning": TaskComplexity.COMPLEX,
    "creative_campaign": TaskComplexity.COMPLEX,
    "business_decision": TaskComplexity.COMPLEX,
}


class ModelRouter:
    """
    Intelligent model router for cost optimization.

    Routes AI tasks to the appropriate model based on complexity,
    cost, quality requirements, and availability.

    Target cost breakdown:
    - Local (80% tasks): $0
    - Cheap API (15% tasks): ~$45/month
    - Claude (5% tasks): ~$50/month
    Total: ~$95/month (vs $450/month all-Claude)
    Savings: 78%
    """

    def __init__(self):
        self.local_available = self._check_local_availability()
        self.usage_stats = {
            tier: {"calls": 0, "tokens": 0, "cost": 0}
            for tier in ModelTier
        }

    def _check_local_availability(self) -> bool:
        """Check if local Ollama is available"""
        try:
            import requests
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            available = response.status_code == 200
            logger.info(f"Local Ollama availability: {available}")
            return available
        except Exception as e:
            logger.debug(f"Local Ollama not available: {e}")
            return False

    def route(
        self,
        task_type: str,
        force_tier: Optional[ModelTier] = None,
        require_functions: bool = False,
        require_vision: bool = False,
        quality_threshold: float = 0.8
    ) -> ModelConfig:
        """
        Determine which model to use for a task.

        Args:
            task_type: Type of task (from TASK_COMPLEXITY keys)
            force_tier: Force a specific tier (override routing)
            require_functions: Task requires function calling
            require_vision: Task requires vision capabilities
            quality_threshold: Minimum quality required (0-1)

        Returns:
            ModelConfig for the selected model
        """

        # If forcing a tier, use it
        if force_tier:
            return self._get_best_model_for_tier(
                force_tier, require_functions, require_vision
            )

        # If requires special capabilities, use Claude
        if require_functions or require_vision:
            logger.info(f"Task requires special capabilities, using Claude")
            return MODELS["claude-sonnet"]

        # Get task complexity
        complexity = TASK_COMPLEXITY.get(task_type, TaskComplexity.MEDIUM)
        logger.debug(f"Task '{task_type}' complexity: {complexity.value}")

        # Route based on complexity
        if complexity == TaskComplexity.SIMPLE:
            # Try local first (free), fall back to Groq (cheapest, fastest)
            if self.local_available:
                logger.info(f"Routing to local Llama 8B (free)")
                return MODELS["llama3.1-8b-local"]
            logger.info(f"Routing to Groq Llama 8B ($0.05/1M tokens)")
            return MODELS["llama3.1-8b-groq"]

        elif complexity == TaskComplexity.MEDIUM:
            # Use cheap API for balance of speed/cost/quality
            # Could use local 70B if available and quality allows
            if self.local_available and quality_threshold < 0.9:
                logger.info(f"Routing to local Llama 70B (free, high quality)")
                return MODELS["llama3.1-70b-local"]
            logger.info(f"Routing to Groq Llama 70B ($0.59/1M tokens)")
            return MODELS["llama3.1-70b-groq"]

        else:  # COMPLEX
            # Claude for complex reasoning
            if quality_threshold >= 0.95:
                logger.info(f"Routing to Claude Opus (premium quality)")
                return MODELS["claude-opus"]
            logger.info(f"Routing to Claude Sonnet (balanced)")
            return MODELS["claude-sonnet"]

    def _get_best_model_for_tier(
        self,
        tier: ModelTier,
        require_functions: bool,
        require_vision: bool
    ) -> ModelConfig:
        """Get best model within a tier"""

        candidates = [m for m in MODELS.values() if m.tier == tier]

        if require_functions:
            candidates = [m for m in candidates if m.supports_functions]
        if require_vision:
            candidates = [m for m in candidates if m.supports_vision]

        if not candidates:
            # Fall back to Claude
            logger.warning(f"No models in tier {tier.value} meet requirements, using Claude")
            return MODELS["claude-sonnet"]

        # Return cheapest that meets requirements
        best = min(candidates, key=lambda m: m.cost_per_1k_tokens)
        logger.debug(f"Selected {best.name} in tier {tier.value}")
        return best

    def track_usage(self, model: ModelConfig, tokens: int):
        """Track usage statistics for cost analysis"""
        tier = model.tier
        cost = (tokens / 1000) * model.cost_per_1k_tokens

        self.usage_stats[tier]["calls"] += 1
        self.usage_stats[tier]["tokens"] += tokens
        self.usage_stats[tier]["cost"] += cost

        logger.debug(
            f"Tracked: {model.name} - {tokens} tokens, "
            f"${cost:.4f} ({tier.value})"
        )

    def get_usage_report(self) -> Dict[str, Any]:
        """
        Get usage statistics and cost analysis.

        Returns detailed breakdown by tier and savings calculation.
        """
        total_cost = sum(s["cost"] for s in self.usage_stats.values())
        total_calls = sum(s["calls"] for s in self.usage_stats.values())
        total_tokens = sum(s["tokens"] for s in self.usage_stats.values())

        # Calculate what it would cost if all-Claude
        claude_cost_per_token = MODELS["claude-sonnet"].cost_per_1k_tokens / 1000
        hypothetical_claude_cost = total_tokens * claude_cost_per_token

        savings_amount = hypothetical_claude_cost - total_cost
        savings_percent = (savings_amount / hypothetical_claude_cost * 100) if hypothetical_claude_cost > 0 else 0

        return {
            "summary": {
                "total_cost": round(total_cost, 4),
                "total_calls": total_calls,
                "total_tokens": total_tokens,
                "avg_cost_per_call": round(total_cost / max(total_calls, 1), 6),
                "hypothetical_all_claude_cost": round(hypothetical_claude_cost, 4),
                "savings_amount": round(savings_amount, 4),
                "savings_percent": round(savings_percent, 1),
            },
            "by_tier": {
                tier.value: {
                    "calls": stats["calls"],
                    "tokens": stats["tokens"],
                    "cost": round(stats["cost"], 4),
                    "percent_calls": round(stats["calls"] / max(total_calls, 1) * 100, 1),
                    "percent_cost": round(stats["cost"] / max(total_cost, 0.0001) * 100, 1),
                }
                for tier, stats in self.usage_stats.items()
            },
            "cost_breakdown_formatted": {
                tier.value: f"${stats['cost']:.4f}"
                for tier, stats in self.usage_stats.items()
            }
        }

    def reset_stats(self):
        """Reset usage statistics (for testing or monthly reset)"""
        self.usage_stats = {
            tier: {"calls": 0, "tokens": 0, "cost": 0}
            for tier in ModelTier
        }
        logger.info("Usage statistics reset")
