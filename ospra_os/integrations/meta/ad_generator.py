"""
AI-Powered Ad Copy Generator
"""
import os
from typing import Dict, List
import anthropic


class AdCopyGenerator:
    """Generate ad copy using Claude AI"""

    def __init__(self):
        self.client = anthropic.Anthropic(
            api_key=os.getenv('ANTHROPIC_API_KEY')
        )

    async def generate_ad_copy(
        self,
        product: Dict,
        target_audience: str = "homeowners aged 25-45",
        tone: str = "exciting and persuasive",
        max_variations: int = 3
    ) -> List[Dict]:
        """
        Generate multiple ad copy variations

        Args:
            product: Product data (name, description, price, etc.)
            target_audience: Target demographic
            tone: Ad tone/style
            max_variations: Number of variations to generate

        Returns:
            List of ad copy variations with headlines and body text
        """
        try:
            print(f"  Generating ad copy for: {product.get('name', 'Product')[:50]}")

            prompt = self._build_prompt(product, target_audience, tone, max_variations)

            # Call Claude API
            message = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=2000,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            response_text = message.content[0].text

            # Parse response into variations
            variations = self._parse_variations(response_text)

            print(f"[SUCCESS] Generated {len(variations)} ad variations")

            return variations

        except Exception as e:
            print(f"[ERROR] Ad generation error: {e}")

            # Return fallback ad copy
            return self._generate_fallback_copy(product)

    def _build_prompt(
        self,
        product: Dict,
        target_audience: str,
        tone: str,
        max_variations: int
    ) -> str:
        """Build prompt for Claude"""

        product_name = product.get('name', 'Product')
        product_price = product.get('price', 29.99)
        product_description = product.get('description', '')
        trend_score = product.get('trend_score', 0)

        prompt = f"""Generate {max_variations} Facebook/Instagram ad copy variations for this product.

PRODUCT DETAILS:
- Name: {product_name}
- Price: ${product_price:.2f}
- Description: {product_description[:200]}
- Trend Score: {trend_score}/100

TARGET AUDIENCE:
{target_audience}

TONE:
{tone}

REQUIREMENTS:
- Headline: 40 characters max (punchy, attention-grabbing)
- Body: 125 characters max (benefit-focused, creates urgency)
- Include specific benefit or pain point
- Use power words that drive clicks
- Create FOMO (fear of missing out)
- Each variation should have different angle

FORMAT YOUR RESPONSE EXACTLY LIKE THIS:

VARIATION 1:
Headline: [40 chars max]
Body: [125 chars max]
Angle: [What makes this variation unique]

VARIATION 2:
Headline: [40 chars max]
Body: [125 chars max]
Angle: [What makes this variation unique]

VARIATION 3:
Headline: [40 chars max]
Body: [125 chars max]
Angle: [What makes this variation unique]

Focus on benefits, not features. Make it scroll-stopping."""

        return prompt

    def _parse_variations(self, response_text: str) -> List[Dict]:
        """Parse AI response into structured variations"""
        variations = []

        try:
            # Split by VARIATION markers
            parts = response_text.split('VARIATION ')

            for part in parts[1:]:  # Skip first empty part
                lines = part.strip().split('\n')

                variation = {
                    'headline': '',
                    'body': '',
                    'angle': ''
                }

                for line in lines:
                    line = line.strip()

                    if line.startswith('Headline:'):
                        variation['headline'] = line.replace('Headline:', '').strip()
                    elif line.startswith('Body:'):
                        variation['body'] = line.replace('Body:', '').strip()
                    elif line.startswith('Angle:'):
                        variation['angle'] = line.replace('Angle:', '').strip()

                if variation['headline'] and variation['body']:
                    variations.append(variation)

            return variations

        except Exception as e:
            print(f"[WARNING]  Parse error: {e}")
            return []

    def _generate_fallback_copy(self, product: Dict) -> List[Dict]:
        """Generate basic fallback copy if AI fails"""

        name = product.get('name', 'Amazing Product')
        price = product.get('price', 29.99)

        return [
            {
                'headline': f"Transform Your Home with {name[:20]}",
                'body': f"[NEW] Trending now! Limited stock. Get yours for just ${price:.2f}. Free shipping!",
                'angle': 'Scarcity + Social Proof'
            },
            {
                'headline': f"Don't Miss Out: {name[:25]}",
                'body': f"[HOT] Thousands sold! Premium quality for only ${price:.2f}. Shop now!",
                'angle': 'FOMO + Value'
            },
            {
                'headline': f"Upgrade Your Space Today",
                'body': f"[STAR] Rated 4.5/5 stars. {name[:30]} at ${price:.2f}. Order now!",
                'angle': 'Social Proof + Urgency'
            }
        ]
