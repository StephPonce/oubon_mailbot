"""
MULTI-MODEL AI ROUTER v2.0

Routes AI tasks to the optimal model based on:
- Task complexity
- Speed requirements
- Cost efficiency

TIERS:
- BUDGET: Groq Llama 8B, Gemini Flash (~$0.05-0.08/1M tokens)
- STANDARD: Groq Llama 70B, Claude Haiku, GPT-4o-mini (~$0.25-1.00/1M tokens)
- PREMIUM: Claude Sonnet 4.5 (~$3.00/1M tokens)

Cost savings: ~70% vs. using Claude Sonnet for everything
"""

from typing import Dict, List, Any, Optional
from enum import Enum
import os
import logging
from dotenv import load_dotenv

from ospra_os.ai.markdown_stripper import strip_markdown

load_dotenv()
logger = logging.getLogger(__name__)


class TaskComplexity(str, Enum):
    """Task complexity levels."""
    SIMPLE = "simple"      # Classification, short responses, formatting
    MEDIUM = "medium"      # Analysis, recommendations, content generation
    COMPLEX = "complex"    # Strategic planning, multi-step reasoning
    REALTIME = "realtime"  # Speed-critical (emails, chat)


class ModelTier(str, Enum):
    """Model tiers by cost."""
    BUDGET = "budget"      # $0.05-0.10 per 1M tokens
    STANDARD = "standard"  # $0.25-1.00 per 1M tokens
    PREMIUM = "premium"    # $3.00+ per 1M tokens


class AIModel:
    """Represents an AI model."""
    
    def __init__(
        self,
        name: str,
        provider: str,
        model_id: str,
        tier: ModelTier,
        cost_per_1m_input: float,
        cost_per_1m_output: float,
        max_tokens: int = 4096,
        speed: str = "normal",  # "blazing", "fast", "normal"
        quality: str = "good"   # "good", "high", "premium"
    ):
        self.name = name
        self.provider = provider
        self.model_id = model_id
        self.tier = tier
        self.cost_per_1m_input = cost_per_1m_input
        self.cost_per_1m_output = cost_per_1m_output
        self.max_tokens = max_tokens
        self.speed = speed
        self.quality = quality
    
    @property
    def avg_cost_per_1m(self) -> float:
        return (self.cost_per_1m_input + self.cost_per_1m_output) / 2


# ============================================================================
# MODEL REGISTRY
# ============================================================================

AVAILABLE_MODELS = {
    # BUDGET TIER - For simple tasks and high volume
    "groq-llama-8b": AIModel(
        name="Groq Llama 3.1 8B",
        provider="groq",
        model_id="llama-3.1-8b-instant",
        tier=ModelTier.BUDGET,
        cost_per_1m_input=0.05,
        cost_per_1m_output=0.08,
        speed="blazing",
        quality="good"
    ),
    "gemini-flash": AIModel(
        name="Gemini 1.5 Flash",
        provider="google",
        model_id="gemini-1.5-flash",
        tier=ModelTier.BUDGET,
        cost_per_1m_input=0.075,
        cost_per_1m_output=0.30,
        speed="fast",
        quality="good"
    ),
    
    # STANDARD TIER - For medium complexity
    "groq-llama-70b": AIModel(
        name="Groq Llama 3.3 70B",
        provider="groq",
        model_id="llama-3.3-70b-versatile",
        tier=ModelTier.STANDARD,
        cost_per_1m_input=0.59,
        cost_per_1m_output=0.79,
        speed="fast",
        quality="high"
    ),
    "claude-haiku": AIModel(
        name="Claude 3.5 Haiku",
        provider="anthropic",
        model_id="claude-3-5-haiku-20241022",
        tier=ModelTier.STANDARD,
        cost_per_1m_input=0.80,
        cost_per_1m_output=4.00,
        speed="fast",
        quality="high"
    ),
    "gpt-4o-mini": AIModel(
        name="GPT-4o Mini",
        provider="openai",
        model_id="gpt-4o-mini",
        tier=ModelTier.STANDARD,
        cost_per_1m_input=0.15,
        cost_per_1m_output=0.60,
        speed="fast",
        quality="high"
    ),
    "gemini-pro": AIModel(
        name="Gemini 1.5 Pro",
        provider="google",
        model_id="gemini-1.5-pro",
        tier=ModelTier.STANDARD,
        cost_per_1m_input=1.25,
        cost_per_1m_output=5.00,
        speed="normal",
        quality="high"
    ),
    
    # PREMIUM TIER - For complex reasoning
    "claude-sonnet": AIModel(
        name="Claude Sonnet 4.5",
        provider="anthropic",
        model_id="claude-sonnet-4-5-20250929",
        tier=ModelTier.PREMIUM,
        cost_per_1m_input=3.00,
        cost_per_1m_output=15.00,
        speed="normal",
        quality="premium"
    ),
    "grok-beta": AIModel(
        name="Grok Beta",
        provider="xai",
        model_id="grok-beta",
        tier=ModelTier.STANDARD,
        cost_per_1m_input=5.00,
        cost_per_1m_output=15.00,
        speed="fast",
        quality="high"
    ),
}


# ============================================================================
# TASK TO MODEL MAPPING
# ============================================================================

TASK_MODEL_MAP = {
    # Email tasks - SPEED is priority, use Groq
    "email_response": "groq-llama-8b",
    "email_classification": None,  # Rule-based, no AI needed
    
    # Product tasks
    "product_analysis": "claude-sonnet",      # Complex reasoning needed
    "product_description": "groq-llama-70b",  # Good quality, fast
    "product_title": "groq-llama-8b",         # Simple task
    
    # Pricing
    "pricing_optimization": "claude-haiku",   # Needs reasoning but not complex
    
    # Ads
    "ad_copy": "groq-llama-70b",              # Creative but not complex
    "ad_strategy": "claude-sonnet",           # Complex strategic thinking
    
    # Chat/Dashboard
    "dashboard_chat": "groq-llama-70b",       # Fast, good quality
    "quick_answer": "groq-llama-8b",          # Speed priority
    
    # Analysis
    "trend_analysis": "claude-sonnet",        # Complex data synthesis
    "market_research": "claude-sonnet",       # Strategic decisions
    "niche_analysis": "claude-haiku",         # Medium complexity
    
    # Summaries
    "summarize": "groq-llama-8b",             # Simple task
    "translate": "groq-llama-8b",             # Simple task
}


class ModelRouter:
    """
    Routes AI tasks to optimal models.
    
    Selection priority:
    1. Task-specific mapping (if exists)
    2. Complexity-based selection
    3. Fallback to Claude Sonnet
    """
    
    def __init__(self):
        self.models = AVAILABLE_MODELS
        self.task_map = TASK_MODEL_MAP
        self.usage_stats = {name: {"requests": 0, "tokens": 0, "cost": 0.0} 
                           for name in self.models}
        self._init_providers()
    
    def _init_providers(self):
        """Initialize API clients for each provider."""
        self.providers = {}
        
        # Anthropic (Claude)
        claude_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")
        if claude_key:
            try:
                import anthropic
                self.providers["anthropic"] = anthropic.Anthropic(api_key=claude_key)
                logger.info("✅ Anthropic provider initialized")
            except Exception as e:
                logger.warning(f"Failed to init Anthropic: {e}")
        
        # Google (Gemini)
        google_key = os.getenv("GOOGLE_API_KEY")
        if google_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=google_key)
                self.providers["google"] = genai
                logger.info("✅ Google provider initialized")
            except Exception as e:
                logger.warning(f"Failed to init Google: {e}")
        
        # Groq
        groq_key = os.getenv("GROQ_API_KEY")
        if groq_key:
            try:
                from groq import Groq
                self.providers["groq"] = Groq(api_key=groq_key)
                logger.info("✅ Groq provider initialized")
            except Exception as e:
                logger.warning(f"Failed to init Groq: {e}")
        
        # OpenAI
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            try:
                import openai
                self.providers["openai"] = openai.OpenAI(api_key=openai_key)
                logger.info("✅ OpenAI provider initialized")
            except Exception as e:
                logger.warning(f"Failed to init OpenAI: {e}")
        
        # xAI (Grok)
        xai_key = os.getenv("XAI_API_KEY")
        if xai_key:
            try:
                import openai
                self.providers["xai"] = openai.OpenAI(
                    api_key=xai_key,
                    base_url="https://api.x.ai/v1"
                )
                logger.info("✅ xAI provider initialized")
            except Exception as e:
                logger.warning(f"Failed to init xAI: {e}")
    
    def get_model_for_task(self, task_type: str) -> Optional[AIModel]:
        """Get the optimal model for a specific task type."""
        model_name = self.task_map.get(task_type)
        if model_name is None:
            return None  # Task doesn't need AI
        return self.models.get(model_name)
    
    def select_model(
        self,
        task_complexity: TaskComplexity,
        prefer_speed: bool = False,
        prefer_quality: bool = False
    ) -> AIModel:
        """
        Select model based on complexity and preferences.
        
        Args:
            task_complexity: SIMPLE, MEDIUM, COMPLEX, or REALTIME
            prefer_speed: Prioritize fast models
            prefer_quality: Prioritize high quality
        """
        # Filter by tier based on complexity
        if task_complexity == TaskComplexity.SIMPLE:
            tier = ModelTier.BUDGET
        elif task_complexity == TaskComplexity.REALTIME:
            tier = ModelTier.BUDGET  # Speed is priority
            prefer_speed = True
        elif task_complexity == TaskComplexity.MEDIUM:
            tier = ModelTier.STANDARD
        else:  # COMPLEX
            tier = ModelTier.PREMIUM
        
        # Get candidates
        candidates = [m for m in self.models.values() 
                     if m.tier == tier and m.provider in self.providers]
        
        if not candidates:
            # Fallback: try any available model
            candidates = [m for m in self.models.values() 
                         if m.provider in self.providers]
        
        if not candidates:
            raise ValueError("No AI providers available!")
        
        # Sort by preference
        if prefer_speed:
            speed_order = {"blazing": 0, "fast": 1, "normal": 2}
            candidates.sort(key=lambda m: (speed_order.get(m.speed, 2), m.avg_cost_per_1m))
        elif prefer_quality:
            quality_order = {"premium": 0, "high": 1, "good": 2}
            candidates.sort(key=lambda m: quality_order.get(m.quality, 2))
        else:
            # Default: sort by cost
            candidates.sort(key=lambda m: m.avg_cost_per_1m)
        
        return candidates[0]
    
    async def route_request(
        self,
        message: str,
        task_type: Optional[str] = None,
        task_complexity: Optional[TaskComplexity] = None,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        prefer_speed: bool = False
    ) -> str:
        """
        Route request to optimal model.
        
        Args:
            message: User prompt
            task_type: Specific task (uses task map)
            task_complexity: General complexity (if no task_type)
            system_prompt: System instructions
            max_tokens: Max output tokens
            temperature: Response temperature
            prefer_speed: Prioritize speed over cost
        """
        # Select model
        if task_type:
            model = self.get_model_for_task(task_type)
            if model is None:
                return ""  # Task doesn't need AI
        else:
            complexity = task_complexity or TaskComplexity.MEDIUM
            model = self.select_model(complexity, prefer_speed=prefer_speed)
        
        # Check if provider is available
        if model.provider not in self.providers:
            # Try fallback
            logger.warning(f"Provider {model.provider} not available, using fallback")
            model = self.select_model(TaskComplexity.MEDIUM)
        
        # Route to provider
        try:
            if model.provider == "anthropic":
                response = await self._call_anthropic(model, message, system_prompt, max_tokens, temperature)
            elif model.provider == "groq":
                response = await self._call_groq(model, message, system_prompt, max_tokens, temperature)
            elif model.provider == "google":
                response = await self._call_google(model, message, system_prompt, max_tokens, temperature)
            elif model.provider == "openai":
                response = await self._call_openai(model, message, system_prompt, max_tokens, temperature)
            elif model.provider == "xai":
                response = await self._call_xai(model, message, system_prompt, max_tokens, temperature)
            else:
                raise ValueError(f"Unknown provider: {model.provider}")
            
            # Track usage (estimate tokens)
            est_tokens = len(message.split()) + len(response.split())
            self._track_usage(model, est_tokens)
            
            return response
            
        except Exception as e:
            logger.error(f"Error with {model.name}: {e}")
            raise
    
    async def _call_anthropic(self, model: AIModel, message: str, 
                              system_prompt: Optional[str], max_tokens: int, temp: float) -> str:
        """Call Anthropic API."""
        client = self.providers["anthropic"]
        
        kwargs = {
            "model": model.model_id,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": message}]
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        
        response = client.messages.create(**kwargs)
        return strip_markdown(response.content[0].text)
    
    async def _call_groq(self, model: AIModel, message: str,
                         system_prompt: Optional[str], max_tokens: int, temp: float) -> str:
        """Call Groq API."""
        client = self.providers["groq"]
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": message})
        
        response = client.chat.completions.create(
            model=model.model_id,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temp
        )
        return strip_markdown(response.choices[0].message.content)
    
    async def _call_google(self, model: AIModel, message: str,
                           system_prompt: Optional[str], max_tokens: int, temp: float) -> str:
        """Call Google Gemini API."""
        genai = self.providers["google"]
        gemini_model = genai.GenerativeModel(model.model_id)
        
        full_prompt = message
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{message}"
        
        response = gemini_model.generate_content(full_prompt)
        return strip_markdown(response.text)
    
    async def _call_openai(self, model: AIModel, message: str,
                           system_prompt: Optional[str], max_tokens: int, temp: float) -> str:
        """Call OpenAI API."""
        client = self.providers["openai"]
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": message})
        
        response = client.chat.completions.create(
            model=model.model_id,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temp
        )
        return strip_markdown(response.choices[0].message.content)
    
    async def _call_xai(self, model: AIModel, message: str,
                        system_prompt: Optional[str], max_tokens: int, temp: float) -> str:
        """Call xAI (Grok) API."""
        client = self.providers["xai"]
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": message})
        
        response = client.chat.completions.create(
            model=model.model_id,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temp
        )
        return strip_markdown(response.choices[0].message.content)
    
    def _track_usage(self, model: AIModel, tokens: int):
        """Track usage statistics."""
        name = [k for k, v in self.models.items() if v == model][0]
        self.usage_stats[name]["requests"] += 1
        self.usage_stats[name]["tokens"] += tokens
        cost = (tokens / 1_000_000) * model.avg_cost_per_1m
        self.usage_stats[name]["cost"] += cost
    
    def get_cost_summary(self) -> Dict[str, Any]:
        """Get cost summary across all models."""
        total_cost = sum(s["cost"] for s in self.usage_stats.values())
        total_requests = sum(s["requests"] for s in self.usage_stats.values())
        total_tokens = sum(s["tokens"] for s in self.usage_stats.values())
        
        # What it would cost with Claude Sonnet only
        sonnet = self.models["claude-sonnet"]
        claude_only_cost = (total_tokens / 1_000_000) * sonnet.avg_cost_per_1m
        
        savings = claude_only_cost - total_cost
        savings_pct = (savings / claude_only_cost * 100) if claude_only_cost > 0 else 0
        
        return {
            "total_cost": round(total_cost, 4),
            "total_requests": total_requests,
            "total_tokens": total_tokens,
            "claude_only_cost": round(claude_only_cost, 4),
            "savings": round(savings, 4),
            "savings_percent": round(savings_pct, 1),
            "by_model": {k: v for k, v in self.usage_stats.items() if v["requests"] > 0}
        }
    
    def get_available_providers(self) -> List[str]:
        """Get list of available providers."""
        return list(self.providers.keys())


# ============================================================================
# GLOBAL INSTANCE
# ============================================================================

_router: Optional[ModelRouter] = None


def get_model_router() -> ModelRouter:
    """Get or create global model router."""
    global _router
    if _router is None:
        _router = ModelRouter()
    return _router


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

async def ai_email_response(
    customer_name: str,
    category: str,
    urgency: str,
    subject: str,
    body: str,
    order_number: Optional[str] = None,
    response_type: str = "full"
) -> str:
    """Generate email response using fastest available model."""
    router = get_model_router()
    
    system_prompt = """You are customer support for Oubon Shop (smart home products).
RULES: Never reveal suppliers. Never say dropshipping. Keep it 3-5 sentences. Be warm but professional."""
    
    order_info = f"\nOrder: #{order_number}" if order_number else ""
    
    if response_type == "acknowledgment":
        message = f"Write 2-sentence acknowledgment for {customer_name} about {category}. Say we'll respond during business hours."
    else:
        message = f"""Customer: {customer_name}
Subject: {subject}
Category: {category}
Urgency: {urgency}{order_info}
Message: {body[:300]}

Write helpful response addressing their concern."""
    
    return await router.route_request(
        message=message,
        task_type="email_response",
        system_prompt=system_prompt,
        max_tokens=300,
        temperature=0.3
    )


async def ai_analyze_product(product_data: Dict[str, Any]) -> str:
    """Analyze product using appropriate model."""
    router = get_model_router()
    
    prompt = f"""Analyze for e-commerce potential:
Product: {product_data.get('name')}
Niche: {product_data.get('niche')}
Trend Score: {product_data.get('trend_score', 'N/A')}
Supplier Cost: ${product_data.get('supplier_cost', 0):.2f}

Provide: score (0-10), explanation, recommendations, risks, target audience, pricing suggestion."""
    
    return await router.route_request(
        message=prompt,
        task_type="product_analysis",
        max_tokens=1500
    )


async def ai_generate_description(product: Dict[str, Any]) -> str:
    """Generate product description."""
    router = get_model_router()
    
    prompt = f"""Create SEO product listing:
Product: {product.get('name')}
Niche: {product.get('niche')}
Features: {product.get('features', [])}

Provide: title, description (HTML), bullet points, meta description, tags."""
    
    return await router.route_request(
        message=prompt,
        task_type="product_description",
        max_tokens=1000
    )


async def ai_quick_chat(message: str, context: Optional[Dict] = None) -> str:
    """Quick dashboard chat response."""
    router = get_model_router()
    
    system = "You are an e-commerce consultant. Be concise and actionable."
    if context:
        system += f"\n\nContext: {context}"
    
    return await router.route_request(
        message=message,
        task_type="dashboard_chat",
        system_prompt=system,
        max_tokens=500
    )
