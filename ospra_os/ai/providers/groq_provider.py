"""
Groq Provider Implementation

Ultra-fast inference using Groq's LPU hardware.
Best for: Real-time responses, high-volume simple tasks

Models:
- llama-3.3-70b-versatile: Best quality/speed balance
- llama-3.1-8b-instant: Fastest, good for simple tasks
- mixtral-8x7b-32768: Good for longer context

Author: OspraOS
Date: December 2025
"""

from typing import Dict, Any, Optional
import json
import re
import logging
import os
from groq import Groq, APIError, RateLimitError as GroqRateLimitError

from ospra_os.ai.providers.base import (
    AIProvider,
    APIKeyError,
    RateLimitError,
    InvalidResponseError
)
from ospra_os.ai.markdown_stripper import strip_markdown

logger = logging.getLogger(__name__)


class GroqProvider(AIProvider):
    """
    Groq AI Provider - Ultra-fast inference.
    
    Uses Groq's LPU (Language Processing Unit) for blazing fast responses.
    Ideal for real-time applications and high-volume tasks.
    
    Attributes:
        client (Groq): Groq API client
        provider_name (str): "groq"
        model_name (str): Current model
        cost_per_1k (float): ~0.0003 (extremely cheap!)
    """
    
    # Available Groq models
    MODELS = {
        "llama-3.3-70b-versatile": {
            "context": 128000,
            "cost_per_1m_input": 0.59,
            "cost_per_1m_output": 0.79,
            "speed": "fast",
            "quality": "high"
        },
        "llama-3.1-8b-instant": {
            "context": 128000,
            "cost_per_1m_input": 0.05,
            "cost_per_1m_output": 0.08,
            "speed": "blazing",
            "quality": "good"
        },
        "mixtral-8x7b-32768": {
            "context": 32768,
            "cost_per_1m_input": 0.24,
            "cost_per_1m_output": 0.24,
            "speed": "fast",
            "quality": "good"
        },
        "gemma2-9b-it": {
            "context": 8192,
            "cost_per_1m_input": 0.20,
            "cost_per_1m_output": 0.20,
            "speed": "blazing",
            "quality": "good"
        }
    }
    
    def __init__(self, api_key: Optional[str] = None, model: str = "llama-3.3-70b-versatile"):
        """
        Initialize Groq provider.
        
        Args:
            api_key: Groq API key (or uses GROQ_API_KEY env var)
            model: Model to use (default: llama-3.3-70b-versatile)
        """
        api_key = api_key or os.getenv("GROQ_API_KEY")
        if not api_key:
            raise APIKeyError("GROQ_API_KEY not configured")
            
        super().__init__(api_key)
        
        self.provider_name = "groq"
        self.model_name = model
        self.cost_per_1k = self.MODELS.get(model, {}).get("cost_per_1m_input", 0.5) / 1000
        
        try:
            self.client = Groq(api_key=api_key)
            logger.info(f"Initialized Groq provider with model {self.model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize Groq client: {e}")
            raise APIKeyError(f"Failed to initialize Groq client: {e}")
    
    async def analyze_product(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze product using Groq's fast inference."""
        self.validate_product_data(product_data)
        prompt = self._build_analysis_prompt(product_data)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are an expert e-commerce analyst. Return valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2048,
                temperature=0.7
            )
            
            response_text = response.choices[0].message.content
            tokens_used = response.usage.total_tokens
            self.track_usage(tokens_used)
            
            return self._parse_analysis_response(response_text, product_data)
            
        except GroqRateLimitError as e:
            raise RateLimitError(f"Groq rate limit exceeded: {e}")
        except APIError as e:
            raise InvalidResponseError(f"Groq API error: {e}")
        except Exception as e:
            raise InvalidResponseError(f"Failed to analyze product: {e}")
    
    async def generate_description(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """Generate product description using Groq."""
        self.validate_product_data(product)
        prompt = self._build_description_prompt(product)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are an expert e-commerce copywriter. Return valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2048,
                temperature=0.8
            )
            
            response_text = response.choices[0].message.content
            tokens_used = response.usage.total_tokens
            self.track_usage(tokens_used)
            
            return self._parse_description_response(response_text, product)
            
        except GroqRateLimitError as e:
            raise RateLimitError(f"Groq rate limit exceeded: {e}")
        except Exception as e:
            raise InvalidResponseError(f"Failed to generate description: {e}")
    
    async def chat(self, message: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Fast chat response using Groq."""
        system_prompt = self._build_chat_system_prompt(context)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                max_tokens=1024,
                temperature=0.7
            )
            
            response_text = response.choices[0].message.content
            tokens_used = response.usage.total_tokens
            self.track_usage(tokens_used)
            
            return strip_markdown(response_text)
            
        except GroqRateLimitError as e:
            raise RateLimitError(f"Groq rate limit exceeded: {e}")
        except Exception as e:
            raise InvalidResponseError(f"Failed to generate response: {e}")
    
    async def generate_email_response(
        self,
        customer_name: str,
        category: str,
        urgency: str,
        subject: str,
        body: str,
        order_number: Optional[str] = None,
        response_type: str = "full"
    ) -> str:
        """
        Generate customer support email response - FAST!
        
        This is optimized for email automation - uses 8b model for speed.
        """
        # Use fastest model for emails
        email_model = "llama-3.1-8b-instant"
        
        system_prompt = """You are a customer support agent for Oubon Shop (smart home products).

STRICT RULES:
- NEVER reveal suppliers (AliExpress, CJ Dropshipping)
- NEVER say "dropshipping"
- Keep responses 3-5 sentences MAX
- Be warm but professional
- Sign as "Oubon Shop Support"

RESPONSE STRUCTURE:
1. Greeting with name
2. Address their concern directly
3. Provide next steps if needed
4. Professional sign-off"""

        if response_type == "acknowledgment":
            user_prompt = f"""Write a 2-sentence acknowledgment email.
Customer: {customer_name}
Subject: {subject}
Category: {category}

Say we received their message and will respond during business hours (7 AM - 9 PM EST)."""
        else:
            order_info = f"\nOrder: #{order_number}" if order_number else ""
            user_prompt = f"""Write a helpful support response.
Customer: {customer_name}
Subject: {subject}
Category: {category}
Urgency: {urgency}{order_info}

Customer Message: {body[:300]}

Address their concern directly. Be helpful and concise."""

        try:
            response = self.client.chat.completions.create(
                model=email_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=300,
                temperature=0.3  # Low temp for consistency
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Groq email generation failed: {e}")
            # Return fallback
            return f"""Hi {customer_name},

Thank you for contacting Oubon Shop! We've received your message and will get back to you shortly.

Best regards,
Oubon Shop Support"""
    
    async def optimize_pricing(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize pricing using Groq."""
        required_fields = ["name", "supplier_cost", "competitor_prices", "niche"]
        for field in required_fields:
            if field not in product_data:
                raise ValueError(f"Missing required field: {field}")
        
        prompt = self._build_pricing_prompt(product_data)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a pricing strategy expert. Return valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1024,
                temperature=0.7
            )
            
            response_text = response.choices[0].message.content
            tokens_used = response.usage.total_tokens
            self.track_usage(tokens_used)
            
            return self._parse_pricing_response(response_text, product_data)
            
        except Exception as e:
            raise InvalidResponseError(f"Failed to optimize pricing: {e}")
    
    async def test_connection(self) -> bool:
        """Test Groq API connection."""
        try:
            response = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",  # Use fastest for test
                messages=[{"role": "user", "content": "Reply OK"}],
                max_tokens=5
            )
            return bool(response.choices)
        except Exception as e:
            logger.error(f"Groq connection test failed: {e}")
            return False
    
    # ========================================================================
    # PROMPT BUILDERS
    # ========================================================================
    
    def _build_analysis_prompt(self, product_data: Dict[str, Any]) -> str:
        name = product_data.get("name", "Unknown")
        niche = product_data.get("niche", "general")
        trend_score = product_data.get("trend_score")
        supplier_cost = product_data.get("supplier_cost")
        
        prompt = f"""Analyze this product for e-commerce:

PRODUCT: {name}
NICHE: {niche}
"""
        if trend_score:
            prompt += f"TREND SCORE: {trend_score}/100\n"
        if supplier_cost:
            prompt += f"SUPPLIER COST: ${supplier_cost:.2f}\n"
        
        prompt += """
Return valid JSON:
{
    "score": <0-10>,
    "explanation": "<why this will succeed/fail>",
    "recommendations": ["<rec1>", "<rec2>", "<rec3>"],
    "risks": ["<risk1>", "<risk2>"],
    "target_audience": "<who buys this>",
    "pricing_suggestion": <float>,
    "confidence": <0-1>
}"""
        return prompt
    
    def _build_description_prompt(self, product: Dict[str, Any]) -> str:
        name = product.get("name", "Product")
        niche = product.get("niche", "general")
        features = product.get("features", [])
        
        prompt = f"""Create SEO product copy:

PRODUCT: {name}
NICHE: {niche}
FEATURES: {', '.join(features) if features else 'N/A'}

Return valid JSON:
{{
    "title": "<50-60 chars>",
    "description": "<HTML with paragraphs>",
    "bullet_points": ["<benefit1>", "<benefit2>", "<benefit3>"],
    "meta_description": "<150 chars>",
    "tags": ["<tag1>", "<tag2>", "<tag3>"],
    "headline": "<catchy headline>"
}}"""
        return prompt
    
    def _build_pricing_prompt(self, product_data: Dict[str, Any]) -> str:
        return f"""Optimize pricing:

PRODUCT: {product_data.get('name')}
SUPPLIER COST: ${product_data.get('supplier_cost', 0):.2f}
COMPETITOR PRICES: {product_data.get('competitor_prices', [])}

Return valid JSON:
{{
    "suggested_price": <float ending .99>,
    "compare_at_price": <20-30% higher>,
    "profit_margin": <percentage>,
    "strategy": "<competitive|premium|value>",
    "reasoning": "<explanation>"
}}"""
    
    def _build_chat_system_prompt(self, context: Optional[Dict[str, Any]]) -> str:
        prompt = """You are an expert e-commerce consultant. Be concise and actionable. No markdown formatting."""
        if context:
            prompt += f"\n\nContext: {json.dumps(context)}"
        return prompt
    
    # ========================================================================
    # RESPONSE PARSERS
    # ========================================================================
    
    def _extract_json(self, text: str) -> str:
        """Extract JSON from response."""
        # Remove markdown code blocks
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        
        # Find JSON
        start = text.find('{')
        end = text.rfind('}') + 1
        if start != -1 and end > start:
            return text[start:end]
        return text
    
    def _parse_analysis_response(self, text: str, product_data: Dict) -> Dict:
        try:
            json_str = self._extract_json(text)
            result = json.loads(json_str)
            result["score"] = float(result.get("score", 7))
            result["confidence"] = float(result.get("confidence", 0.7))
            return result
        except:
            return {
                "score": 7.0,
                "explanation": text[:500],
                "recommendations": ["Review analysis"],
                "risks": ["Market competition"],
                "target_audience": "General consumers",
                "pricing_suggestion": product_data.get("supplier_cost", 10) * 2.5,
                "confidence": 0.7
            }
    
    def _parse_description_response(self, text: str, product: Dict) -> Dict:
        try:
            json_str = self._extract_json(text)
            return json.loads(json_str)
        except:
            return {
                "title": product.get("name", "Product")[:60],
                "description": f"<p>{text[:500]}</p>",
                "bullet_points": ["Quality product", "Fast shipping"],
                "meta_description": text[:160],
                "tags": [product.get("niche", "general")],
                "headline": f"Get Your {product.get('name', 'Product')} Today"
            }
    
    def _parse_pricing_response(self, text: str, product_data: Dict) -> Dict:
        try:
            json_str = self._extract_json(text)
            return json.loads(json_str)
        except:
            cost = product_data.get("supplier_cost", 10)
            price = round(cost * 2.5 - 0.01, 2)
            return {
                "suggested_price": price,
                "compare_at_price": round(price * 1.3, 2),
                "profit_margin": 60,
                "strategy": "competitive",
                "reasoning": text[:300]
            }
