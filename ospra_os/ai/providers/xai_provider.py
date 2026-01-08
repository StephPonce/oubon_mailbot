"""
xAI (Grok) Provider Implementation

Real-time knowledge with X/Twitter integration.
Best for: Trend analysis, social sentiment, current events

Models:
- grok-2: Latest, most capable
- grok-2-mini: Faster, cheaper

Author: OspraOS
Date: December 2024
"""

from typing import Dict, Any, Optional, List
import json
import re
import logging
import os
import httpx

from ospra_os.ai.providers.base import (
    AIProvider,
    APIKeyError,
    RateLimitError,
    InvalidResponseError
)
from ospra_os.ai.markdown_stripper import strip_markdown

logger = logging.getLogger(__name__)


class XAIProvider(AIProvider):
    """
    xAI Grok Provider - Real-time knowledge and X/Twitter integration.
    
    Unique strengths:
    - Access to real-time X/Twitter data
    - Current events knowledge
    - Social sentiment analysis
    - Trend detection
    
    Attributes:
        provider_name (str): "xai"
        model_name (str): Current model (grok-2-1212, grok-beta, grok-4)
    """
    
    BASE_URL = "https://api.x.ai/v1"
    
    # Available models - updated December 2024
    MODELS = {
        "grok-3": {
            "context": 131072,
            "cost_per_1m_input": 2.5,
            "cost_per_1m_output": 12.0,
            "speed": "fast",
            "quality": "high",
            "features": ["real-time", "x-integration", "reasoning"]
        },
        "grok-2-1212": {
            "context": 131072,
            "cost_per_1m_input": 2.0,
            "cost_per_1m_output": 10.0,
            "speed": "medium",
            "quality": "high",
            "features": ["real-time", "x-integration", "reasoning"],
            "deprecated": True
        },
        "grok-beta": {
            "context": 128000,
            "cost_per_1m_input": 2.0,
            "cost_per_1m_output": 10.0,
            "speed": "medium",
            "quality": "high",
            "features": ["real-time", "function-calling"],
            "deprecated": True
        },
        "grok-4": {
            "context": 131072,
            "cost_per_1m_input": 3.0,
            "cost_per_1m_output": 15.0,
            "speed": "medium",
            "quality": "highest",
            "features": ["real-time", "advanced-reasoning", "vision"]
        }
    }

    # Model fallback order - grok-3 is now the primary model
    MODEL_FALLBACK = ["grok-3", "grok-4", "grok-2-1212", "grok-beta"]
    
    def __init__(self, api_key: Optional[str] = None, model: str = "grok-3"):
        """
        Initialize xAI provider.
        
        Args:
            api_key: xAI API key (or uses XAI_API_KEY env var)
            model: Model to use (default: grok-2-1212)
        """
        api_key = api_key or os.getenv("XAI_API_KEY")
        if not api_key:
            raise APIKeyError("XAI_API_KEY not configured")
            
        super().__init__(api_key)
        
        self.provider_name = "xai"
        self.model_name = model
        self.cost_per_1k = self.MODELS.get(model, {}).get("cost_per_1m_input", 2.0) / 1000
        
        # HTTP client for API calls
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            timeout=60.0
        )
        
        logger.info(f"Initialized xAI provider with model {self.model_name}")
    
    async def _call_api(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 2048,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
        retry_with_fallback: bool = True
    ) -> Dict[str, Any]:
        """Make API call to xAI with model fallback."""
        
        # Build messages with system prompt
        full_messages = messages
        if system_prompt:
            full_messages = [
                {"role": "system", "content": system_prompt},
                *messages
            ]
        
        # Try models in fallback order
        models_to_try = [self.model_name] if not retry_with_fallback else self.MODEL_FALLBACK
        last_error = None
        
        for model in models_to_try:
            payload = {
                "model": model,
                "messages": full_messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            
            try:
                logger.debug(f"Trying xAI model: {model}")
                response = await self.client.post("/chat/completions", json=payload)
                response.raise_for_status()
                
                # Success - update model name if we fell back
                if model != self.model_name:
                    logger.info(f"xAI: Fell back from {self.model_name} to {model}")
                    self.model_name = model
                
                return response.json()
                
            except httpx.HTTPStatusError as e:
                last_error = e
                status = e.response.status_code
                
                # Log the actual error response for debugging
                try:
                    error_body = e.response.json()
                    logger.warning(f"xAI error response: {error_body}")
                except:
                    logger.warning(f"xAI error text: {e.response.text[:500]}")
                
                if status == 429:
                    raise RateLimitError(f"xAI rate limit exceeded: {e}")
                elif status == 404:
                    # Model not found or endpoint issue - try next
                    logger.warning(f"xAI 404 for model {model} - may not have API access")
                    continue
                elif status == 401:
                    raise APIKeyError(f"xAI API key invalid: {e}")
                elif status == 403:
                    raise APIKeyError(f"xAI API access denied - check key permissions: {e}")
                else:
                    # Other error - try next model
                    logger.warning(f"xAI error with {model}: {status}")
                    continue
                    
            except Exception as e:
                last_error = e
                logger.warning(f"xAI error with {model}: {e}")
                continue
        
        # All models failed
        raise InvalidResponseError(f"xAI API failed with all models. Last error: {last_error}")
    
    async def analyze_product(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze product with real-time market intelligence.
        
        xAI advantage: Can pull current X/Twitter sentiment and trends.
        """
        self.validate_product_data(product_data)
        
        name = product_data.get("name", "Unknown")
        niche = product_data.get("niche", "general")
        
        system_prompt = """You are an e-commerce analyst with access to real-time social media trends.
Analyze products using current market sentiment from X/Twitter discussions.
Return valid JSON only."""

        user_prompt = f"""Analyze this product for e-commerce potential:

PRODUCT: {name}
NICHE: {niche}
SUPPLIER COST: ${product_data.get('supplier_cost', 'Unknown')}

Consider:
1. Current social media buzz and sentiment
2. Recent trending discussions
3. Competitor landscape
4. Market timing

Return JSON:
{{
    "score": <0-10>,
    "explanation": "<analysis with real-time insights>",
    "social_sentiment": "<positive/neutral/negative>",
    "trending_status": "<rising/stable/declining>",
    "recommendations": ["<rec1>", "<rec2>", "<rec3>"],
    "risks": ["<risk1>", "<risk2>"],
    "target_audience": "<who buys this>",
    "pricing_suggestion": <float>,
    "confidence": <0-1>,
    "real_time_insights": "<any current events/trends affecting this product>"
}}"""

        try:
            response = await self._call_api(
                messages=[{"role": "user", "content": user_prompt}],
                system_prompt=system_prompt,
                max_tokens=2048,
                temperature=0.7
            )
            
            response_text = response["choices"][0]["message"]["content"]
            tokens_used = response.get("usage", {}).get("total_tokens", 0)
            self.track_usage(tokens_used)
            
            return self._parse_json_response(response_text, product_data)
            
        except Exception as e:
            raise InvalidResponseError(f"Failed to analyze product: {e}")
    
    async def get_trending_topics(self, niche: str = "ecommerce") -> Dict[str, Any]:
        """
        Get current trending topics relevant to e-commerce.
        
        This is xAI's unique strength - real-time X/Twitter data.
        """
        system_prompt = """You have access to real-time X/Twitter trends and discussions.
Identify current trending topics relevant to e-commerce and product opportunities.
Return valid JSON only."""

        user_prompt = f"""What's trending right now in the {niche} space?

Return JSON:
{{
    "trending_topics": [
        {{"topic": "<topic>", "momentum": "<rising/peak/declining>", "relevance": <0-10>}},
        ...
    ],
    "product_opportunities": [
        {{"product_type": "<type>", "reason": "<why trending>", "urgency": "<high/medium/low>"}},
        ...
    ],
    "hashtags": ["<relevant hashtag>", ...],
    "sentiment_summary": "<overall market mood>",
    "timestamp": "<current analysis time>"
}}"""

        try:
            response = await self._call_api(
                messages=[{"role": "user", "content": user_prompt}],
                system_prompt=system_prompt,
                max_tokens=2048,
                temperature=0.5
            )
            
            response_text = response["choices"][0]["message"]["content"]
            return self._parse_json_response(response_text, {})
            
        except Exception as e:
            logger.error(f"Failed to get trending topics: {e}")
            return {"error": str(e), "trending_topics": []}
    
    async def analyze_social_sentiment(
        self,
        product_name: str,
        brand_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze social sentiment for a product or brand.
        
        Uses xAI's real-time X/Twitter access.
        """
        target = f"{product_name}" + (f" by {brand_name}" if brand_name else "")
        
        system_prompt = """You have access to real-time X/Twitter discussions and sentiment.
Analyze current social media sentiment for products/brands.
Return valid JSON only."""

        user_prompt = f"""Analyze current social media sentiment for: {target}

Return JSON:
{{
    "overall_sentiment": "<positive/neutral/negative>",
    "sentiment_score": <-1 to 1>,
    "volume": "<high/medium/low>",
    "key_themes": ["<theme1>", "<theme2>", ...],
    "positive_mentions": ["<example>", ...],
    "negative_mentions": ["<example>", ...],
    "influencer_sentiment": "<how influencers feel>",
    "recommendation": "<buy/hold/avoid for e-commerce>",
    "confidence": <0-1>
}}"""

        try:
            response = await self._call_api(
                messages=[{"role": "user", "content": user_prompt}],
                system_prompt=system_prompt,
                max_tokens=1536,
                temperature=0.5
            )
            
            response_text = response["choices"][0]["message"]["content"]
            return self._parse_json_response(response_text, {})
            
        except Exception as e:
            logger.error(f"Failed to analyze sentiment: {e}")
            return {"error": str(e), "overall_sentiment": "unknown"}
    
    async def generate_description(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """Generate product description with trending keywords."""
        self.validate_product_data(product)
        
        name = product.get("name", "Product")
        niche = product.get("niche", "general")
        
        system_prompt = """You are an e-commerce copywriter with access to current trends.
Create product descriptions using trending keywords and current language.
Return valid JSON only."""

        user_prompt = f"""Create SEO-optimized product copy for:

PRODUCT: {name}
NICHE: {niche}

Use current trending keywords and language from social media.

Return JSON:
{{
    "title": "<50-60 chars, SEO optimized>",
    "description": "<HTML with trending keywords>",
    "bullet_points": ["<benefit1>", "<benefit2>", "<benefit3>"],
    "meta_description": "<150 chars>",
    "tags": ["<trending tag>", ...],
    "headline": "<catchy, trend-aware headline>",
    "trending_keywords_used": ["<keyword>", ...]
}}"""

        try:
            response = await self._call_api(
                messages=[{"role": "user", "content": user_prompt}],
                system_prompt=system_prompt,
                max_tokens=2048,
                temperature=0.8
            )
            
            response_text = response["choices"][0]["message"]["content"]
            tokens_used = response.get("usage", {}).get("total_tokens", 0)
            self.track_usage(tokens_used)
            
            return self._parse_json_response(response_text, product)
            
        except Exception as e:
            raise InvalidResponseError(f"Failed to generate description: {e}")
    
    async def chat(self, message: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Chat with real-time knowledge."""
        system_prompt = """You are an expert e-commerce consultant with access to real-time X/Twitter data.
Provide insights using current trends and social sentiment.
Be concise and actionable. No markdown formatting."""

        if context:
            system_prompt += f"\n\nContext: {json.dumps(context)}"
        
        try:
            response = await self._call_api(
                messages=[{"role": "user", "content": message}],
                system_prompt=system_prompt,
                max_tokens=1024,
                temperature=0.7
            )
            
            response_text = response["choices"][0]["message"]["content"]
            tokens_used = response.get("usage", {}).get("total_tokens", 0)
            self.track_usage(tokens_used)
            
            return strip_markdown(response_text)
            
        except Exception as e:
            raise InvalidResponseError(f"Chat failed: {e}")
    
    async def optimize_pricing(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize pricing with market sentiment."""
        required_fields = ["name", "supplier_cost"]
        for field in required_fields:
            if field not in product_data:
                raise ValueError(f"Missing required field: {field}")
        
        system_prompt = """You are a pricing strategist with access to real-time market data.
Consider current market sentiment and competitor activity.
Return valid JSON only."""

        user_prompt = f"""Optimize pricing considering current market conditions:

PRODUCT: {product_data.get('name')}
SUPPLIER COST: ${product_data.get('supplier_cost', 0):.2f}
COMPETITOR PRICES: {product_data.get('competitor_prices', 'Unknown')}

Return JSON:
{{
    "suggested_price": <float ending .99>,
    "compare_at_price": <strikethrough price>,
    "profit_margin": <percentage>,
    "strategy": "<competitive|premium|value>",
    "market_timing": "<good/neutral/bad time to launch>",
    "reasoning": "<explanation with market context>"
}}"""

        try:
            response = await self._call_api(
                messages=[{"role": "user", "content": user_prompt}],
                system_prompt=system_prompt,
                max_tokens=1024,
                temperature=0.5
            )
            
            response_text = response["choices"][0]["message"]["content"]
            return self._parse_json_response(response_text, product_data)
            
        except Exception as e:
            raise InvalidResponseError(f"Pricing optimization failed: {e}")
    
    async def test_connection(self) -> bool:
        """Test xAI API connection with detailed error reporting."""
        try:
            # First, try to list models to verify API access
            try:
                models_response = await self.client.get("/models")
                if models_response.status_code == 200:
                    models_data = models_response.json()
                    available_models = [m.get("id") for m in models_data.get("data", [])]
                    logger.info(f"xAI available models: {available_models}")
                    
                    # Update MODEL_FALLBACK with actually available models
                    if available_models:
                        self.MODEL_FALLBACK = [m for m in available_models if "grok" in m.lower()][:3]
                        if self.MODEL_FALLBACK:
                            self.model_name = self.MODEL_FALLBACK[0]
                            logger.info(f"xAI using model: {self.model_name}")
            except Exception as models_error:
                logger.warning(f"Could not list xAI models: {models_error}")
            
            # Now test chat completion
            response = await self._call_api(
                messages=[{"role": "user", "content": "Reply with OK"}],
                max_tokens=10,
                retry_with_fallback=True
            )
            
            if response.get("choices"):
                logger.info(f"xAI connection successful with model {self.model_name}")
                return True
            return False
            
        except APIKeyError as e:
            logger.error(f"xAI API key error: {e}")
            return False
        except Exception as e:
            logger.error(f"xAI connection test failed: {e}")
            # Log more details for debugging
            if hasattr(e, 'response'):
                try:
                    error_detail = e.response.json() if hasattr(e.response, 'json') else e.response.text
                    logger.error(f"xAI error response: {error_detail}")
                except:
                    pass
            return False
    
    def _parse_json_response(self, text: str, fallback_data: Dict) -> Dict:
        """Parse JSON from response."""
        try:
            # Remove markdown code blocks
            text = re.sub(r'```json\s*', '', text)
            text = re.sub(r'```\s*', '', text)
            
            # Find JSON
            start = text.find('{')
            end = text.rfind('}') + 1
            if start != -1 and end > start:
                return json.loads(text[start:end])
            return json.loads(text)
        except:
            return {
                "raw_response": text[:500],
                "parse_error": True,
                **fallback_data
            }
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, *args):
        await self.client.aclose()
