"""
AI-Powered Pricing Generator
Uses Claude AI to generate realistic pricing based on product type and market research
"""

import os
import json
import random
from typing import Dict, Optional
import anthropic

class AIPricingGenerator:
    """Generate realistic product pricing using AI analysis"""

    def __init__(self):
        self.client = None
        api_key = os.getenv("ANTHROPIC_API_KEY")

        if api_key:
            try:
                self.client = anthropic.Anthropic(api_key=api_key)
                print("[SUCCESS] AI Pricing Generator initialized with Claude")
            except Exception as e:
                print(f"[WARNING]  Claude API initialization failed: {e}")
                self.client = None
        else:
            print("[WARNING]  ANTHROPIC_API_KEY not found - using rule-based pricing")

    def generate_realistic_pricing(self, product_name: str, niche: str) -> Dict:
        """
        Generate realistic pricing for a product

        Args:
            product_name: Product name/keyword (e.g., "LED Strip Lights")
            niche: Product niche (e.g., "smart_lighting")

        Returns:
            {
                "cost": 8.50,  # Supplier cost
                "price": 24.99,  # Retail price
                "profit_margin": 66,  # Percentage
                "estimated_profit": 16.49,  # Dollar amount
                "rating": 4.3,  # Out of 5
                "orders": 1250  # Estimated monthly orders
            }
        """

        # If AI is available, use it for smart pricing
        if self.client:
            try:
                return self._ai_powered_pricing(product_name, niche)
            except Exception as e:
                print(f"[WARNING]  AI pricing failed for {product_name}: {e}")
                # Fall back to rule-based

        # Rule-based fallback pricing
        return self._rule_based_pricing(product_name, niche)

    def _ai_powered_pricing(self, product_name: str, niche: str) -> Dict:
        """Use Claude AI to generate intelligent pricing"""

        prompt = f"""Analyze this dropshipping product and provide realistic pricing data:

Product: {product_name}
Niche: {niche}

Based on typical AliExpress supplier costs and US retail market prices, provide:

1. **Supplier Cost (AliExpress)**: What would this cost from a Chinese supplier?
2. **Retail Price**: What should this sell for in the US market?
3. **Customer Rating**: Typical rating (1-5 stars)
4. **Monthly Orders**: Estimated monthly sales volume

Return ONLY a JSON object with no additional text:
{{
    "cost": <float>,
    "price": <float>,
    "rating": <float>,
    "orders": <integer>
}}

Consider:
- Similar products on Amazon/eBay
- Typical dropshipping margins (40-70%)
- Product category price ranges
- Market demand indicators"""

        response = self.client.messages.create(
            model="claude-sonnet-4-5-20250929",  # Latest Sonnet 4.5 for better pricing intelligence
            max_tokens=500,
            temperature=0.3,  # More deterministic
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        # Parse JSON response
        content = response.content[0].text.strip()

        # Remove markdown code blocks if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        data = json.loads(content)

        # Calculate derived values
        cost = float(data["cost"])
        price = float(data["price"])
        profit = price - cost
        margin = (profit / price) * 100 if price > 0 else 0

        return {
            "cost": round(cost, 2),
            "price": round(price, 2),
            "profit_margin": round(margin, 1),
            "estimated_profit": round(profit, 2),
            # T59: keep the model's estimate when it actually returns one, but
            # do NOT default to 4.2/500 when it's absent — that silently
            # fabricates market metrics. None = unknown.
            "rating": float(data["rating"]) if data.get("rating") is not None else None,
            "orders": int(data["orders"]) if data.get("orders") is not None else None,
        }

    def _rule_based_pricing(self, product_name: str, niche: str) -> Dict:
        """
        Intelligent rule-based pricing when AI is unavailable
        Uses product category and name to estimate realistic prices
        """

        # Product category price ranges (cost, price_min, price_max)
        price_categories = {
            # Electronics & Tech
            "camera": (15.0, 35.0, 89.99),
            "security": (12.0, 29.99, 79.99),
            "speaker": (8.0, 19.99, 49.99),
            "earbuds": (5.0, 14.99, 39.99),
            "charger": (3.0, 9.99, 24.99),
            "cable": (2.0, 7.99, 19.99),
            "adapter": (4.0, 12.99, 29.99),
            "hub": (6.0, 16.99, 39.99),

            # Smart Home
            "bulb": (4.0, 12.99, 29.99),
            "light": (7.0, 19.99, 49.99),
            "plug": (5.0, 14.99, 34.99),
            "switch": (8.0, 19.99, 44.99),
            "sensor": (6.0, 16.99, 39.99),
            "thermostat": (25.0, 59.99, 129.99),
            "lock": (30.0, 69.99, 159.99),

            # Kitchen & Home
            "vacuum": (45.0, 89.99, 249.99),
            "air fryer": (35.0, 69.99, 149.99),
            "blender": (20.0, 39.99, 89.99),
            "kettle": (12.0, 29.99, 69.99),
            "scale": (8.0, 19.99, 49.99),
            "organizer": (6.0, 14.99, 34.99),

            # Fitness & Health
            "resistance": (5.0, 14.99, 34.99),
            "yoga": (8.0, 19.99, 49.99),
            "dumbbell": (12.0, 29.99, 69.99),
            "tracker": (15.0, 34.99, 79.99),
            "massage": (18.0, 39.99, 89.99),

            # Default
            "default": (8.0, 19.99, 49.99)
        }

        # Find matching category
        product_lower = product_name.lower()
        matched_category = "default"

        for category in price_categories:
            if category in product_lower:
                matched_category = category
                break

        cost_base, price_min, price_max = price_categories[matched_category]

        # Add variation to make products unique
        variation = random.uniform(0.85, 1.15)
        cost = round(cost_base * variation, 2)
        price = round(random.uniform(price_min, price_max), 2)

        # Calculate metrics
        profit = price - cost
        margin = (profit / price) * 100

        # T59: rating and orders are real-world MARKET metrics this rule-based
        # fallback cannot know. It used to return random.uniform values in the
        # same shape as the real path, so fabricated numbers rendered as genuine
        # market data. Return None (unknown) — callers/UI must treat None as
        # "not available", never as a real rating/order count.
        return {
            "cost": cost,
            "price": price,
            "profit_margin": round(margin, 1),
            "estimated_profit": round(profit, 2),
            "rating": None,
            "orders": None,
        }


# Singleton instance
_pricing_generator = None

def get_pricing_generator() -> AIPricingGenerator:
    """Get or create pricing generator instance"""
    global _pricing_generator
    if _pricing_generator is None:
        _pricing_generator = AIPricingGenerator()
    return _pricing_generator


# Convenience function
def generate_product_pricing(product_name: str, niche: str) -> Dict:
    """Generate realistic pricing for a product"""
    generator = get_pricing_generator()
    return generator.generate_realistic_pricing(product_name, niche)
