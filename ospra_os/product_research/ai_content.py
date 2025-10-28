"""AI-powered product description and content generation."""

from openai import OpenAI
from ospra_os.core.settings import get_settings
from typing import Dict
import json


class AIContentGenerator:
    """Generate product descriptions, titles, and marketing copy using AI."""

    def __init__(self):
        self.settings = get_settings()
        self.openai = OpenAI(api_key=self.settings.OPENAI_API_KEY)

    async def generate_product_content(
        self,
        product_name: str,
        niche: str,
        trend_score: float = 0
    ) -> Dict[str, str]:
        """
        Generate complete product content for Shopify listing.

        Args:
            product_name: Name of the product
            niche: Product category/niche
            trend_score: Google Trends score (0-100)

        Returns:
            {
                "title": "SEO-optimized product title",
                "description": "Compelling HTML description",
                "bullet_points": ["Feature 1", "Feature 2", ...],
                "meta_description": "SEO meta description",
                "tags": ["tag1", "tag2", ...],
                "headline": "Marketing headline"
            }
        """

        print(f"📝 Generating AI content for: {product_name}")

        prompt = f"""
You are an expert e-commerce copywriter for a dropshipping store.

Product: {product_name}
Category: {niche}
Trend Score: {trend_score}/100 (Google Trends popularity - higher = more demand)

Write compelling product content that:
1. Highlights BENEFITS over features (solve problems, save time, feel confident)
2. Uses emotional triggers and storytelling
3. Includes social proof ("thousands love this", "best-seller")
4. Creates urgency without being pushy
5. Is SEO-optimized for Google search
6. Speaks directly to the customer ("you", "your")

Format your response as JSON:
{{
    "title": "50-60 character SEO-optimized title with key benefit (e.g., 'LED Strip Lights - Transform Any Room with Color')",
    "description": "300-500 word HTML description with <p>, <ul>, <strong>, <em> tags. Make it conversational, benefit-focused, and include a clear call-to-action. Start with a hook, explain benefits, address objections, end with CTA.",
    "bullet_points": ["5-7 specific benefit-focused bullets (not just features)", "Example: 'Save $200/year on electricity bills' instead of 'LED technology'"],
    "meta_description": "150 character SEO meta description for Google search results",
    "tags": ["relevant", "searchable", "keywords", "for", "seo"],
    "headline": "Attention-grabbing 10-word headline for Facebook/TikTok ads"
}}

Make it persuasive, benefit-focused, and optimized for conversions.
"""

        try:
            response = self.openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert e-commerce copywriter specializing in high-converting product descriptions for dropshipping stores."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,  # Creative but not too random
                response_format={"type": "json_object"}
            )

            content = json.loads(response.choices[0].message.content)

            print(f"✅ Generated content for {product_name}")
            print(f"   Title: {content['title'][:60]}...")
            print(f"   Bullets: {len(content['bullet_points'])} points")

            return content

        except Exception as e:
            print(f"❌ Content generation failed: {e}")
            # Return fallback content instead of failing
            return {
                "title": f"{product_name} - Premium Quality",
                "description": f"<p>Discover the amazing <strong>{product_name}</strong> that's taking {niche} by storm!</p><p>Perfect for anyone looking to upgrade their {niche} experience.</p>",
                "bullet_points": [
                    "Premium quality materials",
                    "Fast shipping",
                    "Money-back guarantee",
                    "Easy to use",
                    "Perfect gift"
                ],
                "meta_description": f"Buy {product_name} - Premium quality {niche} product with fast shipping and money-back guarantee.",
                "tags": [product_name.lower(), niche, "premium", "quality", "trending"],
                "headline": f"Get Your {product_name} Today - Limited Stock!"
            }
