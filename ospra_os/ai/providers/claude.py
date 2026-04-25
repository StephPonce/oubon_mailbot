"""
Claude AI Provider Implementation

This module implements the Claude (Anthropic) AI provider using the
claude-sonnet-4 model for product analysis, description generation,
and e-commerce intelligence.

Author: OspraOS
Date: November 2025
"""

from typing import Dict, Any, Optional
import json
import logging
from anthropic import Anthropic, APIError, APIConnectionError, RateLimitError as AnthropicRateLimitError

from ospra_os.ai.providers.base import (
    AIProvider,
    APIKeyError,
    RateLimitError,
    InvalidResponseError
)
from ospra_os.ai.markdown_stripper import strip_markdown

# Configure logging
logger = logging.getLogger(__name__)


class ClaudeProvider(AIProvider):
    """
    Claude AI Provider implementation using Anthropic's API.

    Uses claude-sonnet-4-5-20250929 model for high-quality product analysis,
    description generation, pricing optimization, and conversational AI.

    Attributes:
        client (Anthropic): Anthropic API client
        provider_name (str): "claude"
        model_name (str): "claude-sonnet-4-5-20250929"
        cost_per_1k (float): 0.003 (USD per 1K tokens)
    """

    # Model fallback order (try newer models first, fallback to stable versions)
    MODEL_FALLBACK_ORDER = [
        "claude-sonnet-4-5-20250929",    # Latest Sonnet 4.5
        "claude-3-5-sonnet-20241022",    # Sonnet 3.5 v2
        "claude-3-5-haiku-20241022",     # Haiku 3.5
        "claude-3-haiku-20240307",       # Haiku 3 (stable fallback)
    ]

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Claude provider with API key.

        Args:
            api_key: Anthropic API key (starts with "sk-ant-"). 
                     If not provided, uses ANTHROPIC_API_KEY env var.

        Raises:
            APIKeyError: If API key is invalid or missing
        """
        import os
        api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise APIKeyError("ANTHROPIC_API_KEY not configured")
            
        super().__init__(api_key)

        # Set provider details
        self.provider_name = "claude"
        self.model_name = self.MODEL_FALLBACK_ORDER[0]  # Start with latest
        self.cost_per_1k = 0.003

        # Initialize Anthropic client
        try:
            self.client = Anthropic(api_key=api_key)
            logger.info(f"Initialized Claude provider with model {self.model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize Claude client: {e}")
            raise APIKeyError(f"Failed to initialize Claude client: {e}")

    async def analyze_product(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze product market potential using Claude AI.

        Evaluates market demand, profit potential, competition, target audience,
        and provides actionable recommendations.

        Args:
            product_data: Product information including name, niche, trend_score, etc.

        Returns:
            Comprehensive analysis with score, recommendations, and insights

        Raises:
            InvalidResponseError: If Claude returns invalid data
            RateLimitError: If rate limit is exceeded
        """
        self.validate_product_data(product_data)

        # Build comprehensive analysis prompt
        prompt = self._build_analysis_prompt(product_data)

        try:
            # Call Claude API
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=2048,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            # Extract response text
            response_text = response.content[0].text

            # Track token usage
            tokens_used = response.usage.input_tokens + response.usage.output_tokens
            self.track_usage(tokens_used)

            logger.debug(f"Product analysis complete: {tokens_used} tokens used")

            # Parse structured response
            return self._parse_analysis_response(response_text, product_data)

        except AnthropicRateLimitError as e:
            logger.warning(f"Claude rate limit exceeded: {e}")
            raise RateLimitError("Claude API rate limit exceeded. Please try again later.")

        except APIConnectionError as e:
            logger.error(f"Claude connection error: {e}")
            raise InvalidResponseError(f"Failed to connect to Claude API: {e}")

        except APIError as e:
            logger.error(f"Claude API error: {e}")
            raise InvalidResponseError(f"Claude API error: {e}")

        except Exception as e:
            logger.error(f"Unexpected error in analyze_product: {e}")
            raise InvalidResponseError(f"Failed to analyze product: {e}")

    async def generate_description(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate SEO-optimized product description using Claude AI.

        Creates compelling, conversion-focused descriptions optimized for
        e-commerce platforms and search engines.

        Args:
            product: Product information including name, niche, features, etc.

        Returns:
            SEO-optimized title, description, bullets, meta, tags, and headline

        Raises:
            InvalidResponseError: If Claude returns invalid data
        """
        self.validate_product_data(product)

        # Build description generation prompt
        prompt = self._build_description_prompt(product)

        try:
            # Call Claude API
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=2048,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            # Extract response text
            response_text = response.content[0].text

            # Track token usage
            tokens_used = response.usage.input_tokens + response.usage.output_tokens
            self.track_usage(tokens_used)

            logger.debug(f"Description generation complete: {tokens_used} tokens used")

            # Parse structured response
            return self._parse_description_response(response_text, product)

        except AnthropicRateLimitError as e:
            logger.warning(f"Claude rate limit exceeded: {e}")
            raise RateLimitError("Claude API rate limit exceeded. Please try again later.")

        except APIError as e:
            logger.error(f"Claude API error: {e}")
            raise InvalidResponseError(f"Claude API error: {e}")

        except Exception as e:
            logger.error(f"Unexpected error in generate_description: {e}")
            raise InvalidResponseError(f"Failed to generate description: {e}")

    async def chat(self, message: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Chat interface for dashboard AI assistant using Claude.

        Provides expert e-commerce consulting and actionable advice.

        Args:
            message: User's question or message
            context: Optional context (products, metrics, preferences)
                     - If context["system_prompt"] is a ``str``, used as-is.
                     - If context["system_prompt"] is a ``dict`` with keys
                       ``{"static": str, "dynamic": str}``, the ``static`` chunk
                       is sent as a cached content block (5-minute ephemeral
                       TTL, Anthropic prompt-caching) and the ``dynamic`` chunk
                       is appended as a second, un-cached block. Use this form
                       when the leading chunk is stable across many requests
                       (OiService system prompt, grading rubric, support
                       policy) so Anthropic bills the repeat calls at the 10%
                       cached-read rate instead of full input tokens.
                     - When omitted, falls back to the provider's built-in
                       dashboard consultant prompt.

        Returns:
            AI response as formatted string

        Raises:
            InvalidResponseError: If Claude returns invalid data
        """
        # Build the Anthropic `system` parameter. Three supported shapes:
        #   (a) str            — send as a single text block, no caching
        #   (b) {static, dynamic} dict — split into two blocks; static cached
        #   (c) None           — auto-build from context
        raw_system = None
        if context and "system_prompt" in context:
            raw_system = context["system_prompt"]
            logger.debug("Using system prompt from context (OiService)")
        else:
            raw_system = self._build_chat_system_prompt(context)
            logger.debug("Building system prompt internally")

        system_param = self._build_cached_system_param(raw_system)

        # Temperature — callers that need low-variance, near-deterministic output
        # (e.g. AI product analyzer generating structured JSON) can pass
        # context["temperature"]=0.2. Without this, Anthropic defaults to 1.0
        # which was producing >10% drift between refreshes on the same product.
        temperature = 1.0
        if context and "temperature" in context:
            try:
                temperature = float(context["temperature"])
                # Clamp to Anthropic's valid range [0.0, 1.0]
                temperature = max(0.0, min(1.0, temperature))
            except (TypeError, ValueError):
                logger.warning(
                    f"Invalid temperature in context: {context.get('temperature')!r} "
                    f"— falling back to default 1.0"
                )
                temperature = 1.0

        # Build user message
        user_message = message

        try:
            # Call Claude API with system prompt
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=1024,
                system=system_param,
                temperature=temperature,
                messages=[
                    {
                        "role": "user",
                        "content": user_message
                    }
                ]
            )

            # Extract response text
            response_text = response.content[0].text

            # Track token usage + cache stats. When prompt caching is working,
            # `cache_creation_input_tokens` fires on the first call of a TTL
            # window and `cache_read_input_tokens` fires on every subsequent
            # call — the latter is billed at ~10% of normal input tokens.
            usage = response.usage
            tokens_used = usage.input_tokens + usage.output_tokens
            self.track_usage(tokens_used)

            cache_created = getattr(usage, "cache_creation_input_tokens", 0) or 0
            cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
            if cache_created or cache_read:
                logger.debug(
                    f"Chat response: {tokens_used} tokens "
                    f"(cache_created={cache_created}, cache_read={cache_read})"
                )
            else:
                logger.debug(f"Chat response generated: {tokens_used} tokens used")

            # Strip markdown formatting symbols
            return strip_markdown(response_text)

        except AnthropicRateLimitError as e:
            logger.warning(f"Claude rate limit exceeded: {e}")
            raise RateLimitError("Claude API rate limit exceeded. Please try again later.")

        except APIError as e:
            logger.error(f"Claude API error: {e}")
            raise InvalidResponseError(f"Claude API error: {e}")

        except Exception as e:
            logger.error(f"Unexpected error in chat: {e}")
            raise InvalidResponseError(f"Failed to generate chat response: {e}")

    # --- prompt caching helpers --------------------------------------------

    # Anthropic's cache minimum is 1024 input tokens for Sonnet and 2048 for
    # Haiku. Blocks shorter than this are sent un-cached (Anthropic would
    # otherwise silently ignore the cache_control flag). We approximate with
    # a 4-chars-per-token heuristic — good enough to stay above the threshold
    # after tokenization variability; callers that care about exact token
    # counts can pre-flight via the tokenizer.
    _CACHE_MIN_CHARS = 1024 * 4  # ~1024 tokens worth of English text

    def _build_cached_system_param(self, raw_system):
        """
        Convert the caller-supplied system prompt into the shape Anthropic's
        `messages.create(system=...)` expects.

        Three inputs:
          - ``str``                           — single un-cached text block
          - ``{"static": s, "dynamic": d}``   — cached static + un-cached dynamic
          - already a list of content blocks  — pass through verbatim
        """
        # Pre-built content-block list — caller owns cache_control semantics.
        if isinstance(raw_system, list):
            return raw_system

        # Split form — mark static chunk for ephemeral caching if it's long
        # enough to clear Anthropic's minimum. Under the floor, skip the
        # cache flag (Anthropic would reject or ignore it, and logging
        # cache_creation=0 every call is noise).
        if isinstance(raw_system, dict):
            static = str(raw_system.get("static", "") or "")
            dynamic = str(raw_system.get("dynamic", "") or "")
            blocks = []
            if static:
                block = {"type": "text", "text": static}
                if len(static) >= self._CACHE_MIN_CHARS:
                    block["cache_control"] = {"type": "ephemeral"}
                blocks.append(block)
            if dynamic:
                blocks.append({"type": "text", "text": dynamic})
            # If somehow both were empty, fall through to a safe empty string
            return blocks if blocks else ""

        # Plain string — pass through. Anthropic's SDK accepts either a string
        # or a list of content blocks for the `system` param.
        return raw_system

    async def optimize_pricing(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Suggest optimal pricing strategy using Claude AI.

        Analyzes costs, competition, and market to recommend profitable pricing.

        Args:
            product_data: Product data with costs and competitor prices

        Returns:
            Pricing strategy with suggested price, margin, and reasoning

        Raises:
            InvalidResponseError: If Claude returns invalid data
        """
        # Validate required fields
        required_fields = ["name", "supplier_cost", "competitor_prices", "niche"]
        for field in required_fields:
            if field not in product_data:
                raise ValueError(f"Missing required field for pricing: {field}")

        # Build pricing optimization prompt
        prompt = self._build_pricing_prompt(product_data)

        try:
            # Call Claude API
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            # Extract response text
            response_text = response.content[0].text

            # Track token usage
            tokens_used = response.usage.input_tokens + response.usage.output_tokens
            self.track_usage(tokens_used)

            logger.debug(f"Pricing optimization complete: {tokens_used} tokens used")

            # Parse structured response
            return self._parse_pricing_response(response_text, product_data)

        except AnthropicRateLimitError as e:
            logger.warning(f"Claude rate limit exceeded: {e}")
            raise RateLimitError("Claude API rate limit exceeded. Please try again later.")

        except APIError as e:
            logger.error(f"Claude API error: {e}")
            raise InvalidResponseError(f"Claude API error: {e}")

        except Exception as e:
            logger.error(f"Unexpected error in optimize_pricing: {e}")
            raise InvalidResponseError(f"Failed to optimize pricing: {e}")

    async def test_connection(self) -> bool:
        """
        Test Claude API connection with a simple request.

        Returns:
            True if connection successful, False otherwise

        Raises:
            APIKeyError: If API key is invalid
        """
        try:
            # Send simple test message
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=10,
                messages=[
                    {
                        "role": "user",
                        "content": "Test connection. Reply with 'OK'."
                    }
                ]
            )

            # Check if we got a response
            if response.content and len(response.content) > 0:
                logger.info("Claude API connection test successful")
                return True
            else:
                logger.warning("Claude API returned empty response")
                return False

        except APIError as e:
            if "authentication" in str(e).lower() or "api_key" in str(e).lower():
                logger.error(f"Claude API key invalid: {e}")
                raise APIKeyError(f"Invalid Claude API key: {e}")
            logger.error(f"Claude API connection test failed: {e}")
            return False

        except Exception as e:
            logger.error(f"Claude connection test error: {e}")
            return False

    # ========================================================================
    # PRIVATE HELPER METHODS
    # ========================================================================

    def _build_analysis_prompt(self, product_data: Dict[str, Any]) -> str:
        """Build comprehensive product analysis prompt."""
        name = product_data.get("name", "Unknown Product")
        niche = product_data.get("niche", "general")
        trend_score = product_data.get("trend_score")
        supplier_cost = product_data.get("supplier_cost")
        description = product_data.get("description", "")
        features = product_data.get("features", [])

        prompt = f"""Analyze this product for e-commerce potential:

PRODUCT: {name}
NICHE: {niche}
"""

        if trend_score is not None:
            prompt += f"TREND SCORE: {trend_score}/100\n"

        if supplier_cost is not None:
            prompt += f"SUPPLIER COST: ${supplier_cost:.2f}\n"

        if description:
            prompt += f"DESCRIPTION: {description}\n"

        if features:
            prompt += f"FEATURES: {', '.join(features)}\n"

        prompt += """
Provide a comprehensive analysis in this exact JSON format:
{
    "score": <float 0-10>,
    "explanation": "<detailed explanation of why this product will succeed or fail>",
    "recommendations": ["<recommendation 1>", "<recommendation 2>", "<recommendation 3>"],
    "risks": ["<risk 1>", "<risk 2>", "<risk 3>"],
    "target_audience": "<detailed target audience description>",
    "pricing_suggestion": <float suggested retail price>,
    "confidence": <float 0-1>,
    "market_insights": "<market trends and insights>",
    "competitive_advantage": "<unique selling points>"
}

Be specific, data-driven, and actionable. Focus on profitability and market demand.
"""
        return prompt

    def _build_description_prompt(self, product: Dict[str, Any]) -> str:
        """Build SEO product description generation prompt."""
        name = product.get("name", "Product")
        niche = product.get("niche", "general")
        features = product.get("features", [])
        target_market = product.get("target_market", "US")
        specifications = product.get("specifications", {})
        benefits = product.get("benefits", [])

        prompt = f"""Create an SEO-optimized product description for an e-commerce store:

PRODUCT: {name}
NICHE: {niche}
TARGET MARKET: {target_market}
"""

        if features:
            prompt += f"FEATURES: {', '.join(features)}\n"

        if benefits:
            prompt += f"BENEFITS: {', '.join(benefits)}\n"

        if specifications:
            prompt += f"SPECIFICATIONS: {json.dumps(specifications)}\n"

        prompt += """
Generate in this exact JSON format:
{
    "title": "<SEO title 50-60 characters>",
    "description": "<HTML formatted description with <h2>, <p>, <ul>, <li> tags, 3-4 paragraphs>",
    "bullet_points": ["<emoji> <benefit 1>", "<emoji> <benefit 2>", "<emoji> <benefit 3>", "<emoji> <benefit 4>", "<emoji> <benefit 5>"],
    "meta_description": "<150-160 character meta description>",
    "tags": ["<tag1>", "<tag2>", "<tag3>", "<tag4>", "<tag5>", "<tag6>", "<tag7>", "<tag8>", "<tag9>", "<tag10>"],
    "headline": "<catchy marketing headline>",
    "call_to_action": "<compelling CTA>"
}

Make it compelling, benefit-focused, and conversion-optimized. Use power words and emotional triggers.
"""
        return prompt

    def _build_chat_system_prompt(self, context: Optional[Dict[str, Any]]) -> str:
        """Build system prompt for chat with optional context."""
        system_prompt = """You are an expert e-commerce consultant specializing in dropshipping, product selection, and online store optimization.

Your role is to provide:
- Actionable advice on product selection
- Market insights and trend analysis
- Pricing and profitability strategies
- Marketing and growth recommendations
- Honest assessments of risks and opportunities

FORMATTING RULES:
- NO markdown symbols (no ##, ***, ---, etc.)
- NO headings with # or ##
- NO bold with ** or __
- NO bullet points with *, -, or +
- Use plain text with clear paragraph breaks
- Use numbers (1, 2, 3) for lists

Keep responses concise, specific, and immediately actionable.
"""

        # Handle None or empty context gracefully
        if not context:
            return system_prompt
        
        system_prompt += "\n\nCURRENT CONTEXT:\n"

        # Store metrics - check both key existence AND that value is a dict
        metrics = context.get("store_metrics")
        if metrics and isinstance(metrics, dict):
            system_prompt += f"- Store Niche: {metrics.get('niche', 'N/A')}\n"
            total_revenue = metrics.get('total_revenue', 0) or 0
            conversion_rate = metrics.get('conversion_rate', 0) or 0
            system_prompt += f"- Total Revenue: ${total_revenue:,.2f}\n"
            system_prompt += f"- Conversion Rate: {conversion_rate:.1f}%\n"

        # Current products - check both key existence AND that value is a list
        products = context.get("current_products")
        if products and isinstance(products, list):
            system_prompt += f"- Number of Products: {len(products)}\n"
            if products:
                try:
                    top_product = max(products, key=lambda p: p.get('revenue', 0) if isinstance(p, dict) else 0)
                    if isinstance(top_product, dict):
                        system_prompt += f"- Top Product: {top_product.get('name', 'N/A')} (${top_product.get('revenue', 0):,.2f})\n"
                except (ValueError, TypeError):
                    pass  # Empty list or invalid data

        # Recent activity - check both key existence AND that value is a list
        activities = context.get("recent_activity")
        if activities and isinstance(activities, list):
            activities = activities[:3]  # Last 3 activities
            if activities:
                system_prompt += "- Recent Activity:\n"
                for activity in activities:
                    if activity:  # Skip None/empty
                        system_prompt += f"  • {activity}\n"

        return system_prompt

    def _build_pricing_prompt(self, product_data: Dict[str, Any]) -> str:
        """Build pricing optimization prompt."""
        name = product_data.get("name")
        supplier_cost = product_data.get("supplier_cost")
        competitor_prices = product_data.get("competitor_prices", [])
        niche = product_data.get("niche")
        target_market = product_data.get("target_market", "US")
        desired_margin = product_data.get("desired_margin")

        prompt = f"""Optimize pricing for this product:

PRODUCT: {name}
NICHE: {niche}
TARGET MARKET: {target_market}
SUPPLIER COST: ${supplier_cost:.2f}
COMPETITOR PRICES: {[f'${p:.2f}' for p in competitor_prices]}
"""

        if desired_margin:
            prompt += f"DESIRED MARGIN: {desired_margin}%\n"

        prompt += """
Provide pricing recommendation in this exact JSON format:
{
    "suggested_price": <float with .99 ending>,
    "compare_at_price": <float with .99 ending, 20-30% higher>,
    "profit_margin": <float percentage>,
    "strategy": "<competitive|premium|value>",
    "reasoning": "<detailed explanation of pricing strategy>",
    "price_range": {
        "min": <float minimum viable price>,
        "max": <float maximum market will bear>,
        "optimal": <float optimal price point>
    },
    "market_position": "<where this price sits in the market>"
}

Consider:
- Healthy profit margins (aim for 50%+)
- Competitive positioning
- Psychological pricing (.99 endings)
- Perceived value
- Market demand

Be specific and data-driven.
"""
        return prompt

    def _parse_analysis_response(
        self,
        response_text: str,
        product_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Parse Claude's analysis response into structured dict."""
        try:
            # Try to extract JSON from response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1

            if json_start != -1 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                result = json.loads(json_str)

                # Validate required fields
                required_fields = [
                    "score", "explanation", "recommendations",
                    "risks", "target_audience", "pricing_suggestion", "confidence"
                ]

                for field in required_fields:
                    if field not in result:
                        raise ValueError(f"Missing required field: {field}")

                # Ensure types are correct
                result["score"] = float(result["score"])
                result["confidence"] = float(result["confidence"])
                result["pricing_suggestion"] = float(result["pricing_suggestion"])

                # Ensure lists
                result["recommendations"] = list(result["recommendations"])
                result["risks"] = list(result["risks"])

                return result

            else:
                # Fallback: create structured response from text
                logger.warning("Could not parse JSON from analysis response, using fallback")
                return self._fallback_analysis(response_text, product_data)

        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode error: {e}, using fallback")
            return self._fallback_analysis(response_text, product_data)

        except Exception as e:
            logger.error(f"Error parsing analysis response: {e}")
            raise InvalidResponseError(f"Failed to parse analysis response: {e}")

    def _parse_description_response(
        self,
        response_text: str,
        product: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Parse Claude's description response into structured dict."""
        try:
            # Try to extract JSON from response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1

            if json_start != -1 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                result = json.loads(json_str)

                # Validate required fields
                required_fields = [
                    "title", "description", "bullet_points",
                    "meta_description", "tags", "headline"
                ]

                for field in required_fields:
                    if field not in result:
                        raise ValueError(f"Missing required field: {field}")

                # Ensure lists
                result["bullet_points"] = list(result["bullet_points"])
                result["tags"] = list(result["tags"])

                return result

            else:
                logger.warning("Could not parse JSON from description response, using fallback")
                return self._fallback_description(response_text, product)

        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode error: {e}, using fallback")
            return self._fallback_description(response_text, product)

        except Exception as e:
            logger.error(f"Error parsing description response: {e}")
            raise InvalidResponseError(f"Failed to parse description response: {e}")

    def _parse_pricing_response(
        self,
        response_text: str,
        product_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Parse Claude's pricing response into structured dict."""
        try:
            # Try to extract JSON from response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1

            if json_start != -1 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                result = json.loads(json_str)

                # Validate required fields
                required_fields = [
                    "suggested_price", "compare_at_price", "profit_margin",
                    "strategy", "reasoning", "price_range"
                ]

                for field in required_fields:
                    if field not in result:
                        raise ValueError(f"Missing required field: {field}")

                # Ensure floats
                result["suggested_price"] = float(result["suggested_price"])
                result["compare_at_price"] = float(result["compare_at_price"])
                result["profit_margin"] = float(result["profit_margin"])

                return result

            else:
                logger.warning("Could not parse JSON from pricing response, using fallback")
                return self._fallback_pricing(response_text, product_data)

        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode error: {e}, using fallback")
            return self._fallback_pricing(response_text, product_data)

        except Exception as e:
            logger.error(f"Error parsing pricing response: {e}")
            raise InvalidResponseError(f"Failed to parse pricing response: {e}")

    # Fallback methods for when JSON parsing fails

    def _fallback_analysis(
        self,
        response_text: str,
        product_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Fallback analysis when JSON parsing fails."""
        supplier_cost = product_data.get("supplier_cost", 10.0)
        suggested_price = supplier_cost * 2.5

        return {
            "score": 7.0,
            "explanation": response_text[:500],
            "recommendations": ["Review the full analysis above for details"],
            "risks": ["Market competition", "Pricing pressure"],
            "target_audience": "General consumers in the " + product_data.get("niche", "general") + " market",
            "pricing_suggestion": suggested_price,
            "confidence": 0.7,
            "market_insights": "See detailed analysis above",
            "competitive_advantage": "Product features and quality"
        }

    def _fallback_description(
        self,
        response_text: str,
        product: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Fallback description when JSON parsing fails."""
        name = product.get("name", "Product")

        return {
            "title": name[:60],
            "description": f"<p>{response_text[:500]}</p>",
            "bullet_points": ["Quality product", "Fast shipping", "Great value"],
            "meta_description": response_text[:160],
            "tags": [product.get("niche", "general"), "quality", "trending"],
            "headline": f"Get Your {name} Today",
            "call_to_action": "Order Now - Free Shipping!"
        }

    def _fallback_pricing(
        self,
        response_text: str,
        product_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Fallback pricing when JSON parsing fails."""
        supplier_cost = product_data.get("supplier_cost", 10.0)
        competitor_prices = product_data.get("competitor_prices", [])

        # Calculate suggested price (2.5x supplier cost or competitive)
        suggested_price = supplier_cost * 2.5
        if competitor_prices:
            avg_competitor = sum(competitor_prices) / len(competitor_prices)
            suggested_price = min(suggested_price, avg_competitor * 0.95)

        # Round to .99
        suggested_price = round(suggested_price - 0.01, 2)

        compare_at_price = round(suggested_price * 1.3 - 0.01, 2)
        profit_margin = ((suggested_price - supplier_cost) / suggested_price) * 100

        return {
            "suggested_price": suggested_price,
            "compare_at_price": compare_at_price,
            "profit_margin": profit_margin,
            "strategy": "competitive",
            "reasoning": response_text[:300],
            "price_range": {
                "min": supplier_cost * 2.0,
                "max": supplier_cost * 4.0,
                "optimal": suggested_price
            },
            "market_position": "mid-range"
        }
