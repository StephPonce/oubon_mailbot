"""
AI-Powered Ad Creative Generator

Generates platform-specific ad copy for Meta, TikTok, and Google Ads
using AI providers via the AI Factory system.

Author: OspraOS
Date: November 2025
"""

from typing import Dict, List, Optional
import os
from ospra_os.ai.factory import AIFactory
from ospra_os.core.settings import get_settings


class AdCreativeGenerator:
    """
    Generate AI-powered ad creatives for multiple platforms.

    Automatically enforces platform-specific character limits:
    - Meta: 40 char headlines, 125 char body
    - TikTok: 100 char headlines, 100 char body
    - Google: 30 char headlines, 90 char descriptions

    Usage:
        >>> generator = AdCreativeGenerator()
        >>> creative = await generator.generate_ad_copy(
        ...     platform='meta',
        ...     product_name='Smart LED Bulbs',
        ...     product_description='WiFi-enabled color changing bulbs'
        ... )
    """

    # Platform character limits
    PLATFORM_LIMITS = {
        'meta': {
            'headline_max': 40,
            'body_max': 125,
            'cta_max': 30
        },
        'tiktok': {
            'headline_max': 100,
            'body_max': 100,
            'cta_max': 20
        },
        'google': {
            'headline_max': 30,
            'description_max': 90,
            'cta_max': 25
        }
    }

    # Platform-specific tone guidance
    PLATFORM_TONES = {
        'meta': 'conversational and engaging, focus on benefits and social proof',
        'tiktok': 'energetic and trendy, use emojis, speak to Gen Z/Millennials',
        'google': 'clear and direct, focus on keywords and value proposition'
    }

    def __init__(self, ai_provider: Optional[str] = None, api_key: Optional[str] = None):
        """
        Initialize the creative generator.

        Args:
            ai_provider: AI provider name (claude, openai, gemini). Defaults to settings.
            api_key: API key for the provider. Defaults to settings.
        """
        settings = get_settings()

        # Determine AI provider
        if not ai_provider:
            ai_provider = settings.AI_PROVIDER or 'claude'

        # Get API key from settings if not provided
        if not api_key:
            if ai_provider.lower() == 'claude':
                api_key = settings.CLAUDE_API_KEY
            elif ai_provider.lower() == 'openai':
                api_key = settings.OPENAI_API_KEY
            elif ai_provider.lower() == 'gemini':
                api_key = settings.GEMINI_API_KEY

        if not api_key:
            raise ValueError(f"API key not found for provider: {ai_provider}")

        # Initialize AI provider via factory
        self.ai_provider = AIFactory.get_provider(ai_provider, api_key=api_key)
        self.provider_name = ai_provider

    async def generate_ad_copy(
        self,
        platform: str,
        product_name: str,
        product_description: str,
        target_audience: Optional[str] = None,
        key_benefits: Optional[List[str]] = None,
        variations: int = 1
    ) -> Dict:
        """
        Generate AI-powered ad copy for a specific platform.

        Args:
            platform: Platform name ('meta', 'tiktok', 'google')
            product_name: Name of the product
            product_description: Detailed product description
            target_audience: Target audience description (optional)
            key_benefits: List of key product benefits (optional)
            variations: Number of variations to generate (1-3)

        Returns:
            Dict containing headlines, body copy, CTAs, and metadata

        Example:
            >>> creative = await generator.generate_ad_copy(
            ...     platform='meta',
            ...     product_name='Smart LED Bulbs',
            ...     product_description='WiFi-enabled color changing bulbs',
            ...     target_audience='tech-savvy homeowners',
            ...     key_benefits=['16 million colors', 'Voice control', 'Energy efficient']
            ... )
        """
        platform = platform.lower()

        if platform not in self.PLATFORM_LIMITS:
            raise ValueError(f"Unsupported platform: {platform}. Choose from: {list(self.PLATFORM_LIMITS.keys())}")

        # Limit variations to 3
        variations = min(max(1, variations), 3)

        try:
            # Build prompt for AI
            prompt = self._build_creative_prompt(
                platform=platform,
                product_name=product_name,
                product_description=product_description,
                target_audience=target_audience,
                key_benefits=key_benefits,
                variations=variations
            )

            # Generate using AI provider
            response = await self.ai_provider.chat(prompt)

            # Parse and validate response
            creative = self._parse_ai_response(response, platform, variations)

            print(f"✅ Generated {variations} ad creative(s) for {platform} using {self.provider_name}")

            return creative

        except Exception as e:
            print(f"❌ AI generation failed: {e}")
            # Fallback to template-based generation
            return self._generate_fallback_copy(platform, product_name, product_description, variations)

    def _build_creative_prompt(
        self,
        platform: str,
        product_name: str,
        product_description: str,
        target_audience: Optional[str],
        key_benefits: Optional[List[str]],
        variations: int
    ) -> str:
        """Build the AI prompt for creative generation."""
        limits = self.PLATFORM_LIMITS[platform]
        tone = self.PLATFORM_TONES[platform]

        # Build benefits section
        benefits_text = ""
        if key_benefits:
            benefits_text = "\n**Key Benefits:**\n" + "\n".join(f"- {b}" for b in key_benefits)

        # Build audience section
        audience_text = ""
        if target_audience:
            audience_text = f"\n**Target Audience:** {target_audience}"

        # Platform-specific instructions
        if platform == 'meta':
            format_instructions = f"""
**Format Requirements:**
- Headline: Max {limits['headline_max']} characters
- Body Text: Max {limits['body_max']} characters
- CTA: Max {limits['cta_max']} characters

Generate {variations} variation(s) in this JSON format:
{{
  "variations": [
    {{
      "headline": "engaging headline here",
      "body": "compelling body copy here",
      "cta": "clear call to action"
    }}
  ]
}}
"""
        elif platform == 'tiktok':
            format_instructions = f"""
**Format Requirements:**
- Headline: Max {limits['headline_max']} characters (use emojis!)
- Body Text: Max {limits['body_max']} characters
- CTA: Max {limits['cta_max']} characters
- Hashtags: 3-5 relevant hashtags

Generate {variations} variation(s) in this JSON format:
{{
  "variations": [
    {{
      "headline": "energetic headline with emojis",
      "body": "trendy body copy",
      "cta": "action-oriented CTA",
      "hashtags": ["#hashtag1", "#hashtag2", "#hashtag3"]
    }}
  ]
}}
"""
        else:  # google
            format_instructions = f"""
**Format Requirements:**
- Headlines: 3 variations, each max {limits['headline_max']} characters
- Descriptions: 2 variations, each max {limits['description_max']} characters
- Focus on keywords and clear value proposition

Generate {variations} set(s) in this JSON format:
{{
  "variations": [
    {{
      "headlines": ["headline 1", "headline 2", "headline 3"],
      "descriptions": ["description 1", "description 2"]
    }}
  ]
}}
"""

        prompt = f"""You are an expert ad copywriter specializing in {platform.upper()} advertising.

**Product:** {product_name}
**Description:** {product_description}{audience_text}{benefits_text}

**Platform:** {platform.upper()}
**Tone:** {tone}

{format_instructions}

IMPORTANT:
- Stay within character limits STRICTLY
- Make copy compelling and conversion-focused
- Use power words and emotional triggers
- Include clear benefits, not just features
- Return ONLY valid JSON, no markdown formatting
"""

        return prompt

    def _parse_ai_response(self, response: str, platform: str, expected_variations: int) -> Dict:
        """
        Parse AI response and validate against platform limits.

        Args:
            response: Raw AI response
            platform: Platform name
            expected_variations: Number of expected variations

        Returns:
            Validated creative dictionary
        """
        import json

        # Clean response (remove markdown code blocks if present)
        response = response.strip()
        if response.startswith('```'):
            # Remove ```json and ``` markers
            lines = response.split('\n')
            response = '\n'.join(lines[1:-1]) if len(lines) > 2 else response

        try:
            data = json.loads(response)
        except json.JSONDecodeError as e:
            print(f"Failed to parse AI response as JSON: {e}")
            raise

        # Validate structure
        if 'variations' not in data:
            raise ValueError("AI response missing 'variations' key")

        variations = data['variations']
        limits = self.PLATFORM_LIMITS[platform]

        # Validate and truncate if needed
        for i, var in enumerate(variations):
            if platform == 'google':
                # Google has headlines array and descriptions array
                if 'headlines' in var:
                    var['headlines'] = [h[:limits['headline_max']] for h in var['headlines'][:3]]
                if 'descriptions' in var:
                    var['descriptions'] = [d[:limits['description_max']] for d in var['descriptions'][:2]]
            else:
                # Meta and TikTok have headline, body, cta
                if 'headline' in var:
                    var['headline'] = var['headline'][:limits['headline_max']]
                if 'body' in var:
                    body_key = 'body_max' if platform == 'meta' else 'body_max'
                    var['body'] = var['body'][:limits[body_key]]
                if 'cta' in var:
                    var['cta'] = var['cta'][:limits['cta_max']]

        return {
            'platform': platform,
            'variations': variations,
            'count': len(variations),
            'ai_provider': self.provider_name
        }

    def _generate_fallback_copy(
        self,
        platform: str,
        product_name: str,
        product_description: str,
        variations: int
    ) -> Dict:
        """Generate fallback creative using templates when AI fails."""
        print(f"🔄 Using fallback template for {platform}")

        limits = self.PLATFORM_LIMITS[platform]
        variations_list = []

        # Simple template-based generation
        if platform == 'meta':
            for i in range(variations):
                headline = f"Discover {product_name}"[:limits['headline_max']]
                body = f"Transform your space with {product_name}. {product_description[:50]}..."[:limits['body_max']]
                cta = "Shop Now"[:limits['cta_max']]
                variations_list.append({
                    'headline': headline,
                    'body': body,
                    'cta': cta
                })

        elif platform == 'tiktok':
            for i in range(variations):
                headline = f"🔥 {product_name} is trending!"[:limits['headline_max']]
                body = f"Get yours now! {product_description[:40]}..."[:limits['body_max']]
                cta = "Tap to buy"[:limits['cta_max']]
                variations_list.append({
                    'headline': headline,
                    'body': body,
                    'cta': cta,
                    'hashtags': ['#trending', '#musthave', '#shopnow']
                })

        else:  # google
            for i in range(variations):
                headlines = [
                    f"Buy {product_name}"[:limits['headline_max']],
                    f"Best {product_name}"[:limits['headline_max']],
                    f"{product_name} Sale"[:limits['headline_max']]
                ]
                descriptions = [
                    f"{product_description[:80]}"[:limits['description_max']],
                    "Shop now with free shipping!"[:limits['description_max']]
                ]
                variations_list.append({
                    'headlines': headlines,
                    'descriptions': descriptions
                })

        return {
            'platform': platform,
            'variations': variations_list,
            'count': len(variations_list),
            'ai_provider': 'fallback_template'
        }

    async def generate_video_script(
        self,
        product_name: str,
        product_description: str,
        duration_seconds: int = 15,
        platform: str = 'tiktok',
        hook: Optional[str] = None
    ) -> Dict:
        """
        Generate video script for TikTok or Instagram Reels.

        Args:
            product_name: Product name
            product_description: Product description
            duration_seconds: Video duration (15, 30, or 60 seconds)
            platform: Platform ('tiktok' or 'instagram')
            hook: Optional opening hook/question

        Returns:
            Dict with script scenes and timing

        Example:
            >>> script = await generator.generate_video_script(
            ...     product_name='Smart LED Bulbs',
            ...     product_description='Color-changing WiFi bulbs',
            ...     duration_seconds=15,
            ...     platform='tiktok'
            ... )
        """
        # Validate duration
        valid_durations = [15, 30, 60]
        if duration_seconds not in valid_durations:
            duration_seconds = 15

        hook_text = f"\n**Opening Hook:** {hook}" if hook else ""

        prompt = f"""You are a viral video script writer for {platform.upper()}.

**Product:** {product_name}
**Description:** {product_description}{hook_text}
**Duration:** {duration_seconds} seconds
**Platform:** {platform.upper()}

Create an engaging video script optimized for {platform}.

Requirements:
- Break into scenes with timing (0-5s, 5-10s, etc.)
- Include visual directions
- Include text overlay suggestions
- Make it engaging and fast-paced
- Focus on problem → solution → CTA structure

Return in this JSON format:
{{
  "duration_seconds": {duration_seconds},
  "scenes": [
    {{
      "time_range": "0-5s",
      "visual": "what viewer sees",
      "text_overlay": "text on screen",
      "narration": "what's being said",
      "music_mood": "upbeat/dramatic/etc"
    }}
  ],
  "cta": "final call to action",
  "hashtags": ["#hashtag1", "#hashtag2"]
}}

Return ONLY valid JSON, no markdown.
"""

        try:
            response = await self.ai_provider.chat(prompt)

            # Parse response
            import json
            response = response.strip()
            if response.startswith('```'):
                lines = response.split('\n')
                response = '\n'.join(lines[1:-1]) if len(lines) > 2 else response

            script = json.loads(response)

            print(f"✅ Generated {duration_seconds}s video script for {platform}")

            return script

        except Exception as e:
            print(f"❌ Video script generation failed: {e}")

            # Fallback script
            return {
                'duration_seconds': duration_seconds,
                'scenes': [
                    {
                        'time_range': '0-5s',
                        'visual': f'Show {product_name} in action',
                        'text_overlay': f'Discover {product_name}',
                        'narration': f'Check out this amazing {product_name}!',
                        'music_mood': 'upbeat'
                    },
                    {
                        'time_range': '5-10s',
                        'visual': 'Demonstrate key features',
                        'text_overlay': product_description[:50],
                        'narration': product_description,
                        'music_mood': 'upbeat'
                    },
                    {
                        'time_range': '10-15s',
                        'visual': 'Show CTA and link',
                        'text_overlay': 'Tap to shop now!',
                        'narration': 'Get yours today!',
                        'music_mood': 'upbeat'
                    }
                ][:duration_seconds // 5],  # Scale scenes to duration
                'cta': 'Shop now!',
                'hashtags': ['#shopnow', '#musthave']
            }

    async def generate_ab_test_variations(
        self,
        platform: str,
        product_name: str,
        product_description: str,
        test_elements: List[str] = None
    ) -> Dict:
        """
        Generate A/B test variations for specific ad elements.

        Args:
            platform: Platform name
            product_name: Product name
            product_description: Product description
            test_elements: Elements to vary ['headline', 'body', 'cta', 'all']

        Returns:
            Dict with A and B variations

        Example:
            >>> ab_test = await generator.generate_ab_test_variations(
            ...     platform='meta',
            ...     product_name='Smart LED Bulbs',
            ...     product_description='WiFi color-changing bulbs',
            ...     test_elements=['headline', 'cta']
            ... )
        """
        if not test_elements:
            test_elements = ['all']

        # Generate 2 distinct variations
        creative = await self.generate_ad_copy(
            platform=platform,
            product_name=product_name,
            product_description=product_description,
            variations=2
        )

        if creative['count'] >= 2:
            return {
                'platform': platform,
                'test_type': 'ab_test',
                'test_elements': test_elements,
                'variation_a': creative['variations'][0],
                'variation_b': creative['variations'][1],
                'ai_provider': creative['ai_provider']
            }
        else:
            return {
                'platform': platform,
                'test_type': 'ab_test',
                'error': 'Failed to generate sufficient variations'
            }

    def validate_creative(self, creative: Dict, platform: str) -> Dict:
        """
        Validate creative against platform requirements.

        Args:
            creative: Creative dictionary to validate
            platform: Platform name

        Returns:
            Validation result with any issues
        """
        issues = []
        limits = self.PLATFORM_LIMITS[platform]

        if platform == 'google':
            headlines = creative.get('headlines', [])
            if len(headlines) < 3:
                issues.append(f"Google requires 3 headlines, got {len(headlines)}")
            for i, h in enumerate(headlines):
                if len(h) > limits['headline_max']:
                    issues.append(f"Headline {i+1} exceeds {limits['headline_max']} chars")

            descriptions = creative.get('descriptions', [])
            if len(descriptions) < 2:
                issues.append(f"Google requires 2 descriptions, got {len(descriptions)}")
            for i, d in enumerate(descriptions):
                if len(d) > limits['description_max']:
                    issues.append(f"Description {i+1} exceeds {limits['description_max']} chars")

        else:  # Meta or TikTok
            headline = creative.get('headline', '')
            if len(headline) > limits['headline_max']:
                issues.append(f"Headline exceeds {limits['headline_max']} chars")

            body = creative.get('body', '')
            body_max = limits.get('body_max', 125)
            if len(body) > body_max:
                issues.append(f"Body exceeds {body_max} chars")

            cta = creative.get('cta', '')
            if len(cta) > limits['cta_max']:
                issues.append(f"CTA exceeds {limits['cta_max']} chars")

        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'platform': platform
        }
