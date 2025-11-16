"""
OpenAI Provider Implementation

This module implements the OpenAI (GPT-4) AI provider using the
gpt-4o-mini model for product analysis, description generation,
and e-commerce intelligence.

Author: OspraOS
Date: November 2025
"""

from typing import Dict, Any, Optional
import json
import re
import logging
from openai import OpenAI, APIError, APIConnectionError, RateLimitError as OpenAIRateLimitError

from ospra_os.ai.providers.base import (
    AIProvider,
    APIKeyError,
    RateLimitError,
    InvalidResponseError
)

# Configure logging
logger = logging.getLogger(__name__)


class OpenAIProvider(AIProvider):
    """
    OpenAI AI Provider implementation using OpenAI's GPT-4 API.

    Uses gpt-4o-mini model for cost-effective, high-quality product analysis,
    description generation, pricing optimization, and conversational AI.

    Attributes:
        client (OpenAI): OpenAI API client
        provider_name (str): "openai"
        model_name (str): "gpt-4o-mini"
        cost_per_1k (float): 0.015 (USD per 1K tokens)
    """

    def __init__(self, api_key: str):
        """
        Initialize OpenAI provider with API key.

        Args:
            api_key: OpenAI API key (starts with "sk-")

        Raises:
            APIKeyError: If API key is invalid or missing
        """
        super().__init__(api_key)

        # Set provider details
        self.provider_name = "openai"
        self.model_name = "gpt-4o-mini"
        self.cost_per_1k = 0.015

        # Initialize OpenAI client
        try:
            self.client = OpenAI(api_key=api_key)
            logger.info(f"Initialized OpenAI provider with model {self.model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            raise APIKeyError(f"Failed to initialize OpenAI client: {e}")

    async def analyze_product(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze product market potential using OpenAI GPT-4.

        Evaluates market demand, profit potential, competition, target audience,
        and provides actionable recommendations.

        Args:
            product_data: Product information including name, niche, trend_score, etc.

        Returns:
            Comprehensive analysis with score, recommendations, and insights

        Raises:
            InvalidResponseError: If OpenAI returns invalid data
            RateLimitError: If rate limit is exceeded
        """
        self.validate_product_data(product_data)

        # Build system and user messages
        system_message = "You are an expert e-commerce product analyst with deep knowledge of market trends, consumer behavior, and profitable product selection."
        user_message = self._build_analysis_prompt(product_data)

        try:
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=2048,
                temperature=0.7
            )

            # Extract response text
            response_text = response.choices[0].message.content

            # Track token usage
            tokens_used = response.usage.total_tokens
            self.track_usage(tokens_used)

            logger.debug(f"Product analysis complete: {tokens_used} tokens used")

            # Parse structured response
            return self._parse_analysis_response(response_text, product_data)

        except OpenAIRateLimitError as e:
            logger.warning(f"OpenAI rate limit exceeded: {e}")
            raise RateLimitError("OpenAI API rate limit exceeded. Please try again later.")

        except APIConnectionError as e:
            logger.error(f"OpenAI connection error: {e}")
            raise InvalidResponseError(f"Failed to connect to OpenAI API: {e}")

        except APIError as e:
            logger.error(f"OpenAI API error: {e}")
            raise InvalidResponseError(f"OpenAI API error: {e}")

        except Exception as e:
            logger.error(f"Unexpected error in analyze_product: {e}")
            raise InvalidResponseError(f"Failed to analyze product: {e}")

    async def generate_description(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate SEO-optimized product description using OpenAI GPT-4.

        Creates compelling, conversion-focused descriptions optimized for
        e-commerce platforms and search engines.

        Args:
            product: Product information including name, niche, features, etc.

        Returns:
            SEO-optimized title, description, bullets, meta, tags, and headline

        Raises:
            InvalidResponseError: If OpenAI returns invalid data
        """
        self.validate_product_data(product)

        # Build system and user messages
        system_message = "You are an expert copywriter specializing in e-commerce product descriptions. You create compelling, SEO-optimized content that converts browsers into buyers."
        user_message = self._build_description_prompt(product)

        try:
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=2048,
                temperature=0.8
            )

            # Extract response text
            response_text = response.choices[0].message.content

            # Track token usage
            tokens_used = response.usage.total_tokens
            self.track_usage(tokens_used)

            logger.debug(f"Description generation complete: {tokens_used} tokens used")

            # Parse structured response
            return self._parse_description_response(response_text, product)

        except OpenAIRateLimitError as e:
            logger.warning(f"OpenAI rate limit exceeded: {e}")
            raise RateLimitError("OpenAI API rate limit exceeded. Please try again later.")

        except APIError as e:
            logger.error(f"OpenAI API error: {e}")
            raise InvalidResponseError(f"OpenAI API error: {e}")

        except Exception as e:
            logger.error(f"Unexpected error in generate_description: {e}")
            raise InvalidResponseError(f"Failed to generate description: {e}")

    async def chat(self, message: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Chat interface for dashboard AI assistant using OpenAI GPT-4.

        Provides expert e-commerce consulting and actionable advice.

        Args:
            message: User's question or message
            context: Optional context (products, metrics, preferences)

        Returns:
            AI response as formatted string

        Raises:
            InvalidResponseError: If OpenAI returns invalid data
        """
        # Build system message with context
        system_message = self._build_chat_system_prompt(context)

        try:
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": message}
                ],
                max_tokens=1024,
                temperature=0.7
            )

            # Extract response text
            response_text = response.choices[0].message.content

            # Track token usage
            tokens_used = response.usage.total_tokens
            self.track_usage(tokens_used)

            logger.debug(f"Chat response generated: {tokens_used} tokens used")

            return response_text.strip()

        except OpenAIRateLimitError as e:
            logger.warning(f"OpenAI rate limit exceeded: {e}")
            raise RateLimitError("OpenAI API rate limit exceeded. Please try again later.")

        except APIError as e:
            logger.error(f"OpenAI API error: {e}")
            raise InvalidResponseError(f"OpenAI API error: {e}")

        except Exception as e:
            logger.error(f"Unexpected error in chat: {e}")
            raise InvalidResponseError(f"Failed to generate chat response: {e}")

    async def optimize_pricing(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Suggest optimal pricing strategy using OpenAI GPT-4.

        Analyzes costs, competition, and market to recommend profitable pricing.

        Args:
            product_data: Product data with costs and competitor prices

        Returns:
            Pricing strategy with suggested price, margin, and reasoning

        Raises:
            InvalidResponseError: If OpenAI returns invalid data
        """
        # Validate required fields
        required_fields = ["name", "supplier_cost", "competitor_prices", "niche"]
        for field in required_fields:
            if field not in product_data:
                raise ValueError(f"Missing required field for pricing: {field}")

        # Build system and user messages
        system_message = "You are a pricing strategy expert specializing in e-commerce and dropshipping. You analyze market data to recommend profitable, competitive pricing."
        user_message = self._build_pricing_prompt(product_data)

        try:
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=1024,
                temperature=0.7
            )

            # Extract response text
            response_text = response.choices[0].message.content

            # Track token usage
            tokens_used = response.usage.total_tokens
            self.track_usage(tokens_used)

            logger.debug(f"Pricing optimization complete: {tokens_used} tokens used")

            # Parse structured response
            return self._parse_pricing_response(response_text, product_data)

        except OpenAIRateLimitError as e:
            logger.warning(f"OpenAI rate limit exceeded: {e}")
            raise RateLimitError("OpenAI API rate limit exceeded. Please try again later.")

        except APIError as e:
            logger.error(f"OpenAI API error: {e}")
            raise InvalidResponseError(f"OpenAI API error: {e}")

        except Exception as e:
            logger.error(f"Unexpected error in optimize_pricing: {e}")
            raise InvalidResponseError(f"Failed to optimize pricing: {e}")

    async def test_connection(self) -> bool:
        """
        Test OpenAI API connection with a simple request.

        Returns:
            True if connection successful, False otherwise

        Raises:
            APIKeyError: If API key is invalid
        """
        try:
            # Send simple test message
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "user", "content": "Test connection. Reply with 'OK'."}
                ],
                max_tokens=10
            )

            # Check if we got a response
            if response.choices and len(response.choices) > 0:
                logger.info("OpenAI API connection test successful")
                return True
            else:
                logger.warning("OpenAI API returned empty response")
                return False

        except APIError as e:
            error_str = str(e).lower()
            if "authentication" in error_str or "api_key" in error_str or "invalid" in error_str:
                logger.error(f"OpenAI API key invalid: {e}")
                raise APIKeyError(f"Invalid OpenAI API key: {e}")
            logger.error(f"OpenAI API connection test failed: {e}")
            return False

        except Exception as e:
            logger.error(f"OpenAI connection test error: {e}")
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
Respond with ONLY valid JSON in this exact format (no markdown, no code blocks):
{
    "score": <float 0-10>,
    "explanation": "<detailed explanation>",
    "recommendations": ["<rec 1>", "<rec 2>", "<rec 3>"],
    "risks": ["<risk 1>", "<risk 2>", "<risk 3>"],
    "target_audience": "<detailed description>",
    "pricing_suggestion": <float>,
    "confidence": <float 0-1>,
    "market_insights": "<insights>",
    "competitive_advantage": "<advantages>"
}

Be specific and data-driven.
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

        prompt = f"""Create an SEO-optimized product description:

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
Respond with ONLY valid JSON (no markdown, no code blocks):
{
    "title": "<SEO title 50-60 chars>",
    "description": "<HTML with h2, p, ul, li tags>",
    "bullet_points": ["<emoji> <benefit 1>", "<emoji> <benefit 2>", "<emoji> <benefit 3>", "<emoji> <benefit 4>", "<emoji> <benefit 5>"],
    "meta_description": "<150-160 chars>",
    "tags": ["<tag1>", "<tag2>", "<tag3>", "<tag4>", "<tag5>", "<tag6>", "<tag7>", "<tag8>", "<tag9>", "<tag10>"],
    "headline": "<catchy headline>",
    "call_to_action": "<CTA>"
}

Make it compelling and conversion-focused.
"""
        return prompt

    def _build_chat_system_prompt(self, context: Optional[Dict[str, Any]]) -> str:
        """Build system prompt for chat with optional context."""
        system_prompt = """You are an expert e-commerce consultant specializing in dropshipping, product selection, and online store optimization.

Provide:
- Actionable advice on product selection
- Market insights and trend analysis
- Pricing and profitability strategies
- Marketing and growth recommendations
- Honest assessments of risks

Keep responses concise and actionable. Use bullet points for lists.
"""

        if context:
            system_prompt += "\n\nCURRENT CONTEXT:\n"

            if "store_metrics" in context:
                metrics = context["store_metrics"]
                system_prompt += f"- Store Niche: {metrics.get('niche', 'N/A')}\n"
                system_prompt += f"- Total Revenue: ${metrics.get('total_revenue', 0):,.2f}\n"
                system_prompt += f"- Conversion Rate: {metrics.get('conversion_rate', 0):.1f}%\n"

            if "current_products" in context:
                products = context["current_products"]
                system_prompt += f"- Number of Products: {len(products)}\n"
                if products:
                    top_product = max(products, key=lambda p: p.get('revenue', 0))
                    system_prompt += f"- Top Product: {top_product.get('name', 'N/A')} (${top_product.get('revenue', 0):,.2f})\n"

            if "recent_activity" in context:
                activities = context["recent_activity"][:3]
                if activities:
                    system_prompt += "- Recent Activity:\n"
                    for activity in activities:
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
Respond with ONLY valid JSON (no markdown, no code blocks):
{
    "suggested_price": <float with .99>,
    "compare_at_price": <float with .99>,
    "profit_margin": <float percentage>,
    "strategy": "<competitive|premium|value>",
    "reasoning": "<explanation>",
    "price_range": {
        "min": <float>,
        "max": <float>,
        "optimal": <float>
    },
    "market_position": "<position>"
}

Aim for 50%+ margins and .99 endings.
"""
        return prompt

    def _extract_json_from_response(self, response_text: str) -> str:
        """
        Extract JSON from response, handling markdown code blocks.

        OpenAI sometimes wraps JSON in ```json...``` or ```...``` blocks.
        This method strips those and returns clean JSON.
        """
        # Remove markdown code blocks if present
        # Pattern: ```json\n{...}\n``` or ```\n{...}\n```
        json_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
        match = re.search(json_pattern, response_text, re.DOTALL)

        if match:
            return match.group(1)

        # Try to find JSON object directly
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1

        if json_start != -1 and json_end > json_start:
            return response_text[json_start:json_end]

        # Return as-is if no JSON found
        return response_text

    def _parse_analysis_response(
        self,
        response_text: str,
        product_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Parse OpenAI's analysis response into structured dict."""
        try:
            # Extract JSON (handles markdown code blocks)
            json_str = self._extract_json_from_response(response_text)
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

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"JSON parse error: {e}, using fallback")
            return self._fallback_analysis(response_text, product_data)

        except Exception as e:
            logger.error(f"Error parsing analysis response: {e}")
            raise InvalidResponseError(f"Failed to parse analysis response: {e}")

    def _parse_description_response(
        self,
        response_text: str,
        product: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Parse OpenAI's description response into structured dict."""
        try:
            # Extract JSON (handles markdown code blocks)
            json_str = self._extract_json_from_response(response_text)
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

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"JSON parse error: {e}, using fallback")
            return self._fallback_description(response_text, product)

        except Exception as e:
            logger.error(f"Error parsing description response: {e}")
            raise InvalidResponseError(f"Failed to parse description response: {e}")

    def _parse_pricing_response(
        self,
        response_text: str,
        product_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Parse OpenAI's pricing response into structured dict."""
        try:
            # Extract JSON (handles markdown code blocks)
            json_str = self._extract_json_from_response(response_text)
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

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"JSON parse error: {e}, using fallback")
            return self._fallback_pricing(response_text, product_data)

        except Exception as e:
            logger.error(f"Error parsing pricing response: {e}")
            raise InvalidResponseError(f"Failed to parse pricing response: {e}")

    # Fallback methods (reuse from Claude provider pattern)

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

        # Calculate suggested price
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
