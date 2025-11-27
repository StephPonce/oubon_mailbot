import os
import logging
from typing import Dict, Optional
from anthropic import Anthropic

logger = logging.getLogger(__name__)

class ProductDescriptionGenerator:
    """Generate SEO-optimized product descriptions using Claude AI"""

    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment")

        self.client = Anthropic(api_key=api_key)

    def generate_shopify_description(self, product: Dict) -> Dict[str, str]:
        """
        Generate premium, SEO-optimized Shopify listing
        """

        prompt = f"""You are an expert e-commerce copywriter for premium brands (think Apple, Tesla, Dyson level).

Create a sophisticated, SEO-optimized product listing:

PRODUCT INFO:
- Name: {product['name']}
- Price: ${product['price']}
- Category: {product.get('category', 'General')}
- Niche: {product.get('niche', 'general')}
- Rating: {product.get('rating', 'N/A')}/5
- Orders: {product.get('orders', 'N/A')}

TONE REQUIREMENTS:
- Premium, elegant, sophisticated
- Confident without being pushy
- Sharp, precise language
- No exclamation marks
- No hype words ("amazing", "incredible", "life-changing")
- Think Braun, B&O, premium Apple product pages

HTML FORMATTING REQUIREMENTS:
- CRITICAL: Use consistent spacing with inline styles
- Every <h3> MUST have: style="margin-top: 24px; margin-bottom: 12px;"
- Every <p> MUST have: style="margin-bottom: 16px;"
- Every <ul> MUST have: style="margin-bottom: 20px;"
- Example: <h3 style="margin-top: 24px; margin-bottom: 12px;">Technical Specifications</h3>

SEO REQUIREMENTS:
- Primary keyword: Extract from product name
- Include keyword in: title, first paragraph, ALL H3 headers (keyword-rich headers)
- Use semantic keywords naturally (don't stuff)
- Optimize for search intent (buyers looking for solutions)
- Include long-tail keywords in body text
- ALL section headers must be SEO keyword-rich

STRUCTURE:

1. SEO Title (55-65 characters)
   - Include primary keyword
   - Benefit-focused but elegant
   - Example: "Premium WiFi Thermostat - Voice Control & Energy Monitoring"

2. Opening Paragraph (2-3 sentences)
   - Start with primary keyword
   - State the problem it solves
   - Sophisticated language
   - Inline style: <p style="margin-bottom: 16px;">
   - Example: "The [Product Name] redefines climate control through intelligent automation. Designed for modern homes, it learns your preferences while reducing energy consumption by up to 30%."

3. Technical Specifications Section
   - H3: "Technical Specifications" or "[Category] Technical Specifications" (SEO keyword-rich)
   - Inline style: <h3 style="margin-top: 24px; margin-bottom: 12px;">
   - 5-7 precise, benefit-focused points with specific numbers/specs
   - <ul style="margin-bottom: 20px;">
   - No fluff, factual

4. Applications Section
   - H3: "Best For" or "Best For [Use Case]" (inclusive, not exclusionary)
   - Inline style: <h3 style="margin-top: 24px; margin-bottom: 12px;">
   - 3-4 specific user scenarios
   - <ul style="margin-bottom: 20px;">
   - Professional language, broad appeal

5. Package Contents
   - H3: "What's Included" or "[Product] Package Contents"
   - Inline style: <h3 style="margin-top: 24px; margin-bottom: 12px;">
   - Clear, factual list
   - <p style="margin-bottom: 16px;"> or <ul style="margin-bottom: 20px;">
   - No marketing speak

6. Closing
   - H3: "Quality Assurance" or "[Brand] Quality Assurance" (premium, not cheap)
   - Inline style: <h3 style="margin-top: 24px; margin-bottom: 12px;">
   - 30-day return policy, warranty details
   - <p style="margin-bottom: 16px;">
   - Factual, assured tone

Return ONLY valid JSON:
{{
  "title": "SEO-optimized title with primary keyword",
  "description": "<p style='margin-bottom: 16px;'>Opening paragraph with keyword...</p><h3 style='margin-top: 24px; margin-bottom: 12px;'>Technical Specifications</h3><ul style='margin-bottom: 20px;'><li>Feature 1</li></ul><h3 style='margin-top: 24px; margin-bottom: 12px;'>Best For</h3><ul style='margin-bottom: 20px;'><li>Use case 1</li></ul><h3 style='margin-top: 24px; margin-bottom: 12px;'>What's Included</h3><p style='margin-bottom: 16px;'>Package contents...</p><h3 style='margin-top: 24px; margin-bottom: 12px;'>Quality Assurance</h3><p style='margin-bottom: 16px;'>30-day returns. Two-year warranty.</p>",
  "bullet_points": [
    "Precise feature 1 with specs",
    "Precise feature 2 with specs",
    "Precise feature 3 with specs",
    "Precise feature 4 with specs",
    "Precise feature 5 with specs"
  ],
  "seo_keywords": ["primary keyword", "semantic keyword 1", "semantic keyword 2", "long-tail keyword 1", "long-tail keyword 2", "buyer intent keyword 1", "buyer intent keyword 2", "category keyword"]
}}

CRITICAL:
- No exclamation marks
- No hype language
- Premium, confident tone
- SEO keywords integrated naturally
- ALL HTML elements must have inline styles as specified
- ALL section headers must be SEO keyword-rich
- Return ONLY JSON, no markdown"""

        try:
            logger.info(f"Generating premium SEO description for: {product['name']}")

            response = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=2000,
                temperature=0.5,  # More consistent, less creative
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            content = response.content[0].text

            # Parse JSON
            import json
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]

            result = json.loads(content.strip())

            logger.info(f"✅ Generated premium SEO description")
            return result

        except Exception as e:
            logger.error(f"Failed to generate description: {e}")
            return self._get_fallback_description(product)

    def _get_fallback_description(self, product: Dict) -> Dict[str, str]:
        """Fallback if AI generation fails"""
        return {
            "title": product['name'],
            "description": f"""
                <h3>{product['name']}</h3>
                <p>High-quality product from trusted suppliers.</p>
                <h3>Shipping & Delivery</h3>
                <p>Free worldwide shipping. Estimated delivery: 10-25 business days.</p>
                <h3>Guarantee</h3>
                <p>30-day money-back guarantee. Not satisfied? Return for a full refund.</p>
            """,
            "bullet_points": [
                "High-quality materials",
                "Fast shipping",
                "30-day guarantee",
                "Trusted by thousands"
            ],
            "seo_keywords": [product.get('category', 'product')]
        }
