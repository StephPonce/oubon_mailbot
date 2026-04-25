"""
Marketing Angle Generator - Create unique positioning for products

This module generates unique marketing angles to help users differentiate
their product positioning and avoid direct competition when selling the
same products.

Example: Smart LED Strips can be marketed as:
- "Home Automation" (tech-savvy homeowners)
- "Party Lights" (young adults, entertainment)
- "Sleep Therapy" (wellness-focused consumers)
"""

from typing import Dict, List, Optional
import random
import json
import logging

from ospra_os.ai.factory import AIFactory

logger = logging.getLogger(__name__)


class MarketingAngleGenerator:
    """Generate unique marketing angles to differentiate users selling same products"""

    # Marketing angle templates by niche
    ANGLE_TEMPLATES = {
        'smart_home': [
            'home_automation',
            'energy_saving',
            'security',
            'convenience',
            'modernization',
            'luxury',
            'elderly_care',
            'child_safety'
        ],
        'fitness': [
            'weight_loss',
            'muscle_building',
            'recovery',
            'performance',
            'health_monitoring',
            'convenience',
            'home_workout',
            'professional_results'
        ],
        'pet_tech': [
            'pet_safety',
            'convenience',
            'pet_health',
            'entertainment',
            'training',
            'bonding',
            'anxiety_relief',
            'remote_monitoring'
        ],
        'kitchen': [
            'time_saving',
            'healthy_cooking',
            'convenience',
            'professional_results',
            'family_bonding',
            'sustainability',
            'meal_prep',
            'entertaining'
        ],
        'beauty': [
            'anti_aging',
            'convenience',
            'professional_results',
            'self_care',
            'confidence',
            'time_saving',
            'natural_beauty',
            'skin_health'
        ],
        'tech': [
            'productivity',
            'entertainment',
            'connectivity',
            'innovation',
            'portability',
            'performance',
            'simplicity',
            'future_proof'
        ]
    }

    # Angle-specific configuration
    ANGLE_CONFIGS = {
        'home_automation': {
            'title_template': 'Smart {product} - Automate Your Home',
            'target_audience': 'tech-savvy homeowners aged 25-45',
            'pain_point': 'manual home management and inefficiency',
            'cta': 'Upgrade Your Home',
            'tone': 'innovative, modern, sophisticated'
        },
        'energy_saving': {
            'title_template': 'Save $200/Year with {product}',
            'target_audience': 'cost-conscious homeowners',
            'pain_point': 'high utility bills and energy waste',
            'cta': 'Start Saving Today',
            'tone': 'practical, eco-friendly, budget-conscious'
        },
        'security': {
            'title_template': '{product} - Protect What Matters Most',
            'target_audience': 'security-focused families',
            'pain_point': 'home security concerns and safety fears',
            'cta': 'Secure Your Home',
            'tone': 'trustworthy, protective, reliable'
        },
        'convenience': {
            'title_template': '{product} - Life Made Easy',
            'target_audience': 'busy professionals and parents',
            'pain_point': 'time constraints and daily hassles',
            'cta': 'Simplify Your Life',
            'tone': 'helpful, friendly, accessible'
        },
        'weight_loss': {
            'title_template': 'Lose Weight Fast with {product}',
            'target_audience': 'people seeking weight loss solutions',
            'pain_point': 'struggling with weight and fitness goals',
            'cta': 'Transform Your Body',
            'tone': 'motivational, results-focused, supportive'
        },
        'luxury': {
            'title_template': 'Premium {product} - Elevate Your Lifestyle',
            'target_audience': 'affluent consumers seeking quality',
            'pain_point': 'settling for inferior products',
            'cta': 'Experience Luxury',
            'tone': 'elegant, exclusive, sophisticated'
        }
    }

    def __init__(self, ai_provider: str = 'claude', api_key: Optional[str] = None):
        """
        Initialize Marketing Angle Generator

        Args:
            ai_provider: AI provider to use ('claude', 'openai', 'gemini')
            api_key: Optional API key (uses env vars if not provided)
        """
        self.ai = AIFactory.get_provider(ai_provider, api_key)
        logger.info(f"[SUCCESS] MarketingAngleGenerator initialized with {ai_provider}")

    async def generate_unique_angle(
        self,
        product_name: str,
        product_description: str,
        user_brand_voice: str = 'professional',
        user_target_audience: str = 'general',
        niche: str = 'smart_home',
        avoid_angles: List[str] = None,
        user_id: Optional[int] = None
    ) -> Dict:
        """
        Generate unique marketing angle for a product

        Args:
            product_name: Name of the product
            product_description: Product description
            user_brand_voice: User's brand voice (professional, casual, luxury, etc.)
            user_target_audience: User's target demographic
            niche: Product niche/category
            avoid_angles: List of angles to avoid (already used)
            user_id: Optional user ID for personalization

        Returns:
            Dictionary with marketing angle details:
            {
                'angle': 'energy_saving',
                'title': 'Save $200/Year on Electric Bills',
                'description': '...',
                'target_audience': 'homeowners',
                'pain_point': 'high electricity costs',
                'benefits': [...],
                'cta': 'Start Saving Today',
                'ad_copy': '...',
                'hashtags': [...]
            }
        """
        avoid_angles = avoid_angles or []

        # Get available angles for niche
        available_angles = self.ANGLE_TEMPLATES.get(niche, ['convenience', 'quality'])

        # Remove already-used angles
        available_angles = [a for a in available_angles if a not in avoid_angles]

        if not available_angles:
            logger.warning(f"No available angles for niche {niche}, using fallback")
            available_angles = ['general_appeal']

        # Pick a random angle
        angle = random.choice(available_angles)

        logger.info(f"Generating {angle} angle for {product_name} (niche: {niche})")

        # Generate angle-specific copy with AI
        try:
            angle_data = await self._generate_ai_angle(
                product_name=product_name,
                product_description=product_description,
                angle=angle,
                user_brand_voice=user_brand_voice,
                user_target_audience=user_target_audience,
                niche=niche
            )

            logger.info(f"[SUCCESS] Generated AI angle: {angle}")
            return angle_data

        except Exception as e:
            logger.warning(f"AI generation failed: {e}, using template fallback")
            # Fallback to template-based angle
            return self._generate_template_angle(
                product_name=product_name,
                angle=angle,
                niche=niche,
                user_brand_voice=user_brand_voice
            )

    async def _generate_ai_angle(
        self,
        product_name: str,
        product_description: str,
        angle: str,
        user_brand_voice: str,
        user_target_audience: str,
        niche: str
    ) -> Dict:
        """Generate marketing angle using AI"""

        # Get angle configuration
        config = self.ANGLE_CONFIGS.get(angle, self.ANGLE_CONFIGS['convenience'])

        prompt = f"""You are a master copywriter creating a unique marketing angle for an e-commerce product.

PRODUCT: {product_name}
DESCRIPTION: {product_description}

MARKETING ANGLE: {angle}
BRAND VOICE: {user_brand_voice}
TARGET AUDIENCE: {user_target_audience}
NICHE: {niche}
TONE: {config.get('tone', 'professional')}

Create a unique marketing angle that positions this product around the "{angle}" theme.
Focus on the pain point: "{config.get('pain_point', 'customer needs')}"

Generate compelling copy that:
1. Highlights benefits related to {angle}
2. Speaks directly to {user_target_audience}
3. Uses {user_brand_voice} brand voice
4. Creates urgency and desire

Return ONLY valid JSON (no markdown, no code blocks, no extra text) with this exact structure:
{{
    "angle": "{angle}",
    "title": "Compelling product title focused on {angle} (max 60 chars)",
    "description": "150-word product description emphasizing {angle} benefits",
    "target_audience": "Specific demographic this angle targets",
    "pain_point": "Main pain point this angle addresses",
    "benefits": ["Benefit 1", "Benefit 2", "Benefit 3", "Benefit 4", "Benefit 5"],
    "cta": "Powerful call-to-action phrase",
    "ad_copy": "Compelling 30-word Facebook ad focusing on {angle}",
    "hashtags": ["#hashtag1", "#hashtag2", "#hashtag3", "#hashtag4", "#hashtag5"]
}}

IMPORTANT: Return ONLY the JSON object, nothing else."""

        # Audit fix: ``self.ai.generate_content`` doesn't exist on any
        # provider class — the marketing-angle AI path was silently
        # raising AttributeError on every call and falling through to
        # ``_generate_template_angle``. Every angle in production was
        # template-generated. The provider interface exposes ``chat`` for
        # generic prompt → text calls; that's what we use here.
        response = await self.ai.chat(message=prompt)

        # Clean response (remove markdown if present)
        response = (response or "").strip()
        if response.startswith('```'):
            # Remove markdown code blocks
            lines = response.split('\n')
            response = '\n'.join([l for l in lines if not l.startswith('```')])

        # Parse JSON response
        angle_data = json.loads(response)

        # Validate required fields
        required_fields = ['angle', 'title', 'description', 'target_audience',
                          'pain_point', 'benefits', 'cta']
        for field in required_fields:
            if field not in angle_data:
                raise ValueError(f"Missing required field: {field}")

        return angle_data

    def _generate_template_angle(
        self,
        product_name: str,
        angle: str,
        niche: str,
        user_brand_voice: str = 'professional'
    ) -> Dict:
        """Fallback template-based angle generation"""

        logger.info(f"Using template fallback for {angle} angle")

        # Get angle configuration
        config = self.ANGLE_CONFIGS.get(angle, {
            'title_template': f'{product_name} - Premium Quality',
            'target_audience': 'general consumers',
            'pain_point': 'finding quality products',
            'cta': 'Shop Now',
            'tone': 'professional'
        })

        title = config['title_template'].replace('{product}', product_name)

        return {
            'angle': angle,
            'title': title,
            'description': f"Discover the benefits of {product_name}. {config['pain_point'].capitalize()} is a thing of the past. This product is designed for {config['target_audience']} who demand quality and results.",
            'target_audience': config['target_audience'],
            'pain_point': config['pain_point'],
            'benefits': [
                f'Solves {config["pain_point"]}',
                'High quality construction',
                'Easy to use',
                'Backed by reviews',
                'Great value'
            ],
            'cta': config['cta'],
            'ad_copy': f"{title}. Perfect for {config['target_audience']}. {config['cta']}!",
            'hashtags': [f'#{niche}', f'#{angle}', '#ecommerce', '#shopnow', '#deals']
        }

    async def generate_multiple_angles(
        self,
        product_name: str,
        product_description: str,
        niche: str = 'smart_home',
        num_angles: int = 3,
        user_brand_voice: str = 'professional',
        user_target_audience: str = 'general'
    ) -> List[Dict]:
        """
        Generate multiple different angles for A/B testing

        Args:
            product_name: Name of the product
            product_description: Product description
            niche: Product niche
            num_angles: Number of angles to generate
            user_brand_voice: User's brand voice
            user_target_audience: User's target audience

        Returns:
            List of angle dictionaries
        """
        logger.info(f"Generating {num_angles} angles for {product_name}")

        angles = []
        used_angles = []

        for i in range(num_angles):
            try:
                angle = await self.generate_unique_angle(
                    product_name=product_name,
                    product_description=product_description,
                    user_brand_voice=user_brand_voice,
                    user_target_audience=user_target_audience,
                    niche=niche,
                    avoid_angles=used_angles
                )
                angles.append(angle)
                used_angles.append(angle['angle'])

            except Exception as e:
                logger.error(f"Failed to generate angle {i+1}: {e}")
                continue

        logger.info(f"[SUCCESS] Generated {len(angles)} unique angles")
        return angles

    def get_available_angles(self, niche: str) -> List[str]:
        """Get list of available marketing angles for a niche"""
        return self.ANGLE_TEMPLATES.get(niche, ['convenience', 'quality', 'value'])

    def get_angle_description(self, angle: str) -> Dict:
        """Get detailed description of a marketing angle"""
        config = self.ANGLE_CONFIGS.get(angle, {})
        return {
            'angle': angle,
            'target_audience': config.get('target_audience', 'general consumers'),
            'pain_point': config.get('pain_point', 'common problems'),
            'tone': config.get('tone', 'professional'),
            'recommended_for': config.get('target_audience', 'all users')
        }
