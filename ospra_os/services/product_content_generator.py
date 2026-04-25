"""
Ospra Intelligence - AI Product Content Generator

Uses Claude (Anthropic API) to generate professional product content:
- SEO-optimized titles
- Compelling descriptions
- Meta tags and keywords
- Competitive pricing suggestions
- Complete Shopify listings

Model: claude-sonnet-4-5-20250929 (current Sonnet 4.5)
"""

import os
import time
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from anthropic import Anthropic, AsyncAnthropic
import asyncio

logger = logging.getLogger(__name__)


class RateLimiter:
    """Simple rate limiter for API calls"""

    def __init__(self, calls_per_minute: int = 50):
        self.calls_per_minute = calls_per_minute
        self.calls = []

    async def wait_if_needed(self):
        """Wait if we've exceeded rate limit"""
        now = time.time()

        # Remove calls older than 1 minute
        self.calls = [call_time for call_time in self.calls if now - call_time < 60]

        if len(self.calls) >= self.calls_per_minute:
            # Calculate wait time
            oldest_call = self.calls[0]
            wait_time = 60 - (now - oldest_call)

            if wait_time > 0:
                logger.warning(f"Rate limit reached, waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time)

        self.calls.append(now)


class UsageTracker:
    """Track API usage and costs"""

    def __init__(self):
        self.calls = []
        self.total_input_tokens = 0
        self.total_output_tokens = 0

        # Claude Sonnet 4 pricing (per million tokens)
        self.input_cost_per_million = 3.00  # $3/M input tokens
        self.output_cost_per_million = 15.00  # $15/M output tokens

    def track_call(
        self,
        method: str,
        input_tokens: int,
        output_tokens: int,
        success: bool
    ):
        """Record API call"""
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

        call_cost = (
            (input_tokens / 1_000_000) * self.input_cost_per_million +
            (output_tokens / 1_000_000) * self.output_cost_per_million
        )

        self.calls.append({
            "timestamp": datetime.now().isoformat(),
            "method": method,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": call_cost,
            "success": success
        })

    def get_stats(self, last_n_hours: int = 24) -> Dict:
        """Get usage statistics"""
        cutoff = datetime.now() - timedelta(hours=last_n_hours)
        recent_calls = [
            call for call in self.calls
            if datetime.fromisoformat(call["timestamp"]) > cutoff
        ]

        total_cost = sum(call["cost"] for call in recent_calls)
        successful_calls = sum(1 for call in recent_calls if call["success"])

        return {
            "total_calls": len(recent_calls),
            "successful_calls": successful_calls,
            "failed_calls": len(recent_calls) - successful_calls,
            "total_input_tokens": sum(call["input_tokens"] for call in recent_calls),
            "total_output_tokens": sum(call["output_tokens"] for call in recent_calls),
            "total_cost": total_cost,
            "average_cost_per_call": total_cost / len(recent_calls) if recent_calls else 0
        }


class ProductContentGenerator:
    """
    AI-powered product content generator using Claude Sonnet 4.5

    Transforms raw AliExpress/Amazon data into professional Shopify listings
    with SEO optimization, compelling copy, and competitive pricing.
    """

    def __init__(self, api_key: Optional[str] = None, rate_limit: int = 50):
        """
        Initialize content generator

        Args:
            api_key: Anthropic API key (or from ANTHROPIC_API_KEY env)
            rate_limit: Max API calls per minute (default 50)
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")

        if not self.api_key:
            logger.warning("[WARNING]  ANTHROPIC_API_KEY not set - content generation disabled")
            self.client = None
        else:
            self.client = AsyncAnthropic(api_key=self.api_key)
            logger.info("[SUCCESS] ProductContentGenerator initialized with Claude Sonnet 4.5")

        self.model = "claude-sonnet-4-5-20250929"  # Sonnet 4.5 (current)
        self.rate_limiter = RateLimiter(calls_per_minute=rate_limit)
        self.usage_tracker = UsageTracker()

    async def _call_claude(
        self,
        prompt: str,
        system_prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7
    ) -> str:
        """
        Internal method to call Claude API with rate limiting and tracking

        Args:
            prompt: User prompt
            system_prompt: System context
            max_tokens: Maximum response tokens
            temperature: Creativity (0-1)

        Returns:
            Claude's response text
        """
        if not self.client:
            raise ValueError("Anthropic API key not configured")

        # Rate limiting
        await self.rate_limiter.wait_if_needed()

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}]
            )

            # Track usage
            self.usage_tracker.track_call(
                method="generate_content",
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                success=True
            )

            return response.content[0].text

        except Exception as e:
            logger.error(f"Claude API error: {e}")
            self.usage_tracker.track_call(
                method="generate_content",
                input_tokens=0,
                output_tokens=0,
                success=False
            )
            raise

    async def generate_product_title(
        self,
        original_title: str,
        product_category: str,
        brand_voice: str = "modern, minimal, premium"
    ) -> str:
        """
        Transform ugly AliExpress titles into clean, SEO-friendly titles

        Args:
            original_title: Raw title from AliExpress (often messy)
            product_category: Product category (e.g., "Smart Lighting")
            brand_voice: Brand tone (default: "modern, minimal, premium")

        Returns:
            Clean, optimized product title

        Example:
            Input: "2024 New Smart LED Bulb WiFi RGB Color Changing Light E27 Alexa Google Home"
            Output: "Smart WiFi LED Bulb - RGB Color Changing, Works with Alexa & Google Home"
        """
        system_prompt = f"""You are an expert e-commerce copywriter specializing in product titles.

Your brand voice is: {brand_voice}

Create product titles that are:
- Clean and professional (remove spam keywords like "2024 New", "Hot Sale")
- SEO-friendly (include key search terms)
- Under 70 characters (Shopify best practice)
- Easy to read and scan
- Feature-focused (highlight key benefits)

Rules:
- Remove year references (2024, 2023, etc.)
- Remove spam words (New, Hot, Best, Top)
- Use proper capitalization
- Include 1-2 key features
- Use dashes or commas for readability"""

        prompt = f"""Transform this AliExpress title into a professional product title:

Original title: "{original_title}"
Category: {product_category}

Return ONLY the optimized title, nothing else."""

        title = await self._call_claude(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=100,
            temperature=0.5  # Lower temperature for consistency
        )

        return title.strip().strip('"')

    async def generate_product_description(
        self,
        product_name: str,
        features: List[str],
        category: str,
        target_audience: str = "homeowners interested in smart home technology",
        tone: str = "professional yet approachable",
        include_specs: bool = True
    ) -> Dict:
        """
        Generate complete product description with multiple formats

        Args:
            product_name: Product name
            features: List of product features
            category: Product category
            target_audience: Who is this for?
            tone: Writing tone
            include_specs: Include technical specs section

        Returns:
            {
                "short_description": "1-2 sentence preview",
                "long_description": "Full HTML formatted description",
                "bullet_points": ["Feature 1", "Feature 2", ...],
                "meta_description": "SEO meta (155 chars)",
                "generated_at": "2024-12-06T..."
            }
        """
        system_prompt = f"""You are an expert e-commerce copywriter creating product descriptions.

Target audience: {target_audience}
Tone: {tone}

Create descriptions that:
- Lead with benefits, not features
- Use clear, concise language
- Include social proof hooks (e.g., "Join thousands of satisfied customers")
- Have strong call-to-action
- Are scannable (use bullet points, short paragraphs)
- Include relevant keywords naturally

Format the long description in clean HTML:
- Use <h3> for section headers
- Use <p> for paragraphs
- Use <ul> and <li> for lists
- Use <strong> for emphasis
- No code blocks, return raw HTML"""

        features_text = "\n".join([f"- {f}" for f in features])

        prompt = f"""Create a complete product description for:

Product: {product_name}
Category: {category}

Features:
{features_text}

Provide the following (use exactly these labels):

SHORT_DESCRIPTION:
[1-2 sentences for product previews, highlighting main benefit]

LONG_DESCRIPTION:
[Full product page content in HTML format, 150-250 words, including:
- Opening hook (compelling benefit statement)
- Key benefits (3-5 points as prose, not bullet lists)
- Brief usage examples (don't say "Perfect For" - just mention use cases naturally)
- Call to action

IMPORTANT: Do NOT include "Perfect For" sections or list buyer personas - this alienates customers. Keep it universal and benefit-focused.]

BULLET_POINTS:
[5-7 key features as bullets, format: "- Feature text"]

META_DESCRIPTION:
[SEO meta description, exactly 155 characters or less, compelling preview]"""

        response = await self._call_claude(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=1500,
            temperature=0.7
        )

        # Parse response
        result = {
            "short_description": "",
            "long_description": "",
            "bullet_points": [],
            "meta_description": "",
            "generated_at": datetime.now().isoformat()
        }

        # Extract sections
        sections = response.split("\n\n")
        current_section = None

        for section in sections:
            if "SHORT_DESCRIPTION:" in section:
                current_section = "short"
                result["short_description"] = section.split("SHORT_DESCRIPTION:")[1].strip()
            elif "LONG_DESCRIPTION:" in section:
                current_section = "long"
                result["long_description"] = section.split("LONG_DESCRIPTION:")[1].strip()
            elif "BULLET_POINTS:" in section:
                current_section = "bullets"
                bullets_text = section.split("BULLET_POINTS:")[1].strip()
                result["bullet_points"] = [
                    line.strip("- ").strip()
                    for line in bullets_text.split("\n")
                    if line.strip().startswith("-")
                ]
            elif "META_DESCRIPTION:" in section:
                current_section = "meta"
                result["meta_description"] = section.split("META_DESCRIPTION:")[1].strip()
            elif current_section == "long":
                # Continue long description
                result["long_description"] += "\n\n" + section.strip()

        return result

    async def generate_seo_content(
        self,
        product_name: str,
        category: str,
        description: str
    ) -> Dict:
        """
        Generate SEO-optimized metadata

        Args:
            product_name: Product name
            category: Product category
            description: Product description

        Returns:
            {
                "meta_title": "60 chars max",
                "meta_description": "155 chars max",
                "url_slug": "product-name-slug",
                "keywords": {
                    "primary": "main keyword",
                    "secondary": ["keyword1", "keyword2", ...]
                },
                "image_alt_text": "Descriptive alt text"
            }
        """
        system_prompt = """You are an SEO expert specializing in e-commerce product optimization.

Create SEO metadata following these rules:

META TITLE:
- Include primary keyword at start
- Add brand name at end if space allows
- Max 60 characters
- Compelling and click-worthy

META DESCRIPTION:
- Include primary keyword naturally
- Highlight unique value proposition
- Include call-to-action if possible
- Exactly 155 characters or less
- Compelling preview that drives clicks

URL SLUG:
- Lowercase
- Hyphens between words
- Include primary keyword
- No special characters
- Under 60 characters

KEYWORDS:
- Primary: 2-3 word phrase (main search term)
- Secondary: 3-5 related keywords
- Based on search intent and category norms

IMAGE ALT TEXT:
- Descriptive and specific
- Include primary keyword
- Describe what's visible
- Under 125 characters"""

        prompt = f"""Generate SEO metadata for:

Product: {product_name}
Category: {category}
Description: {description[:200]}...

Provide (use exact labels):

META_TITLE:
[60 chars max, keyword-focused, compelling]

META_DESCRIPTION:
[155 chars max, includes keyword + CTA]

URL_SLUG:
[lowercase-with-hyphens]

PRIMARY_KEYWORD:
[2-3 word main search term]

SECONDARY_KEYWORDS:
[keyword1, keyword2, keyword3, keyword4, keyword5]

IMAGE_ALT_TEXT:
[Descriptive alt text for main product image]"""

        response = await self._call_claude(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=500,
            temperature=0.5
        )

        # Parse response
        result = {
            "meta_title": "",
            "meta_description": "",
            "url_slug": "",
            "keywords": {
                "primary": "",
                "secondary": []
            },
            "image_alt_text": ""
        }

        for line in response.split("\n"):
            if "META_TITLE:" in line:
                result["meta_title"] = line.split("META_TITLE:")[1].strip()
            elif "META_DESCRIPTION:" in line:
                result["meta_description"] = line.split("META_DESCRIPTION:")[1].strip()
            elif "URL_SLUG:" in line:
                result["url_slug"] = line.split("URL_SLUG:")[1].strip()
            elif "PRIMARY_KEYWORD:" in line:
                result["keywords"]["primary"] = line.split("PRIMARY_KEYWORD:")[1].strip()
            elif "SECONDARY_KEYWORDS:" in line:
                keywords_text = line.split("SECONDARY_KEYWORDS:")[1].strip()
                result["keywords"]["secondary"] = [
                    kw.strip() for kw in keywords_text.split(",")
                ]
            elif "IMAGE_ALT_TEXT:" in line:
                result["image_alt_text"] = line.split("IMAGE_ALT_TEXT:")[1].strip()

        return result

    async def suggest_competitive_price(
        self,
        cost_price: float,
        category: str,
        competitor_prices: Optional[List[float]] = None,
        target_margin: float = 0.4
    ) -> Dict:
        """
        Suggest optimal pricing with psychological pricing

        Args:
            cost_price: Product cost (AliExpress price)
            category: Product category
            competitor_prices: Optional list of competitor prices
            target_margin: Target profit margin (default 40%)

        Returns:
            {
                "suggested_price": 29.99,
                "min_viable_price": 24.99,
                "premium_price": 39.99,
                "margin_at_suggested": 0.42,
                "pricing_rationale": "Explanation..."
            }
        """
        system_prompt = """You are a pricing strategist for e-commerce products.

Apply psychological pricing principles:
- Use .99 or .97 endings for prices under $100
- Use .95 or round numbers for premium products
- Consider price anchoring
- Factor in perceived value

Analyze:
- Cost structure
- Category norms
- Competitor positioning
- Target margins
- Customer psychology"""

        competitor_text = ""
        if competitor_prices:
            avg_competitor = sum(competitor_prices) / len(competitor_prices)
            min_competitor = min(competitor_prices)
            max_competitor = max(competitor_prices)
            competitor_text = f"""
Competitor prices: ${min_competitor:.2f} - ${max_competitor:.2f}
Average: ${avg_competitor:.2f}"""

        prompt = f"""Suggest pricing for:

Cost price: ${cost_price:.2f}
Category: {category}
Target margin: {target_margin * 100}%{competitor_text}

Provide (use exact labels):

SUGGESTED_PRICE:
[Optimal selling price with psychological pricing]

MIN_VIABLE_PRICE:
[Minimum price to maintain viability]

PREMIUM_PRICE:
[Premium positioning price]

RATIONALE:
[Brief explanation of pricing strategy, 2-3 sentences]"""

        response = await self._call_claude(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=300,
            temperature=0.3  # Lower temperature for pricing
        )

        # Parse response
        suggested_price = cost_price / (1 - target_margin)  # Fallback
        min_viable = cost_price * 1.2
        premium_price = suggested_price * 1.3
        rationale = f"Based on {target_margin * 100}% margin with psychological pricing"

        for line in response.split("\n"):
            if "SUGGESTED_PRICE:" in line:
                try:
                    price_text = line.split("SUGGESTED_PRICE:")[1].strip()
                    suggested_price = float(price_text.replace("$", "").strip())
                except (ValueError, IndexError):
                    pass  # Keep fallback price
            elif "MIN_VIABLE_PRICE:" in line:
                try:
                    price_text = line.split("MIN_VIABLE_PRICE:")[1].strip()
                    min_viable = float(price_text.replace("$", "").strip())
                except (ValueError, IndexError):
                    pass  # Keep fallback price
            elif "PREMIUM_PRICE:" in line:
                try:
                    price_text = line.split("PREMIUM_PRICE:")[1].strip()
                    premium_price = float(price_text.replace("$", "").strip())
                except (ValueError, IndexError):
                    pass  # Keep fallback price
            elif "RATIONALE:" in line:
                rationale = line.split("RATIONALE:")[1].strip()

        margin_at_suggested = (suggested_price - cost_price) / suggested_price if suggested_price > 0 else 0

        return {
            "suggested_price": round(suggested_price, 2),
            "min_viable_price": round(min_viable, 2),
            "premium_price": round(premium_price, 2),
            "margin_at_suggested": round(margin_at_suggested, 2),
            "pricing_rationale": rationale
        }

    async def generate_complete_listing(
        self,
        aliexpress_data: Dict,
        niche: str,
        brand_name: str = "Oubon Shop"
    ) -> Dict:
        """
        One-call method to generate complete Shopify listing

        Args:
            aliexpress_data: {
                "title": "Original AliExpress title",
                "features": ["feature1", "feature2"],
                "category": "Smart Lighting",
                "price": 12.99,
                "images": ["url1", "url2"]
            }
            niche: Product niche (e.g., "smart_home")
            brand_name: Store brand name

        Returns:
            Complete Shopify product data ready for deployment
        """
        logger.info(f"[AI] Generating complete listing for: {aliexpress_data.get('title', 'Unknown')[:50]}")

        # Extract data
        original_title = aliexpress_data.get("title", "Product")
        features = aliexpress_data.get("features", [])
        category = aliexpress_data.get("category", niche)
        cost_price = aliexpress_data.get("price", 0)

        # Generate title
        title = await self.generate_product_title(
            original_title=original_title,
            product_category=category,
            brand_voice="modern, minimal, premium"
        )

        logger.info(f"   [SUCCESS] Title generated: {title}")

        # Generate description
        description_data = await self.generate_product_description(
            product_name=title,
            features=features if features else ["High quality product", "Easy to use", "Durable design"],
            category=category,
            target_audience=f"{niche.replace('_', ' ')} enthusiasts",
            tone="professional yet approachable"
        )

        logger.info(f"   [SUCCESS] Description generated ({len(description_data['long_description'])} chars)")

        # Generate SEO
        seo_data = await self.generate_seo_content(
            product_name=title,
            category=category,
            description=description_data["short_description"]
        )

        logger.info(f"   [SUCCESS] SEO data generated (primary keyword: {seo_data['keywords']['primary']})")

        # Generate pricing
        pricing_data = await self.suggest_competitive_price(
            cost_price=cost_price,
            category=category,
            target_margin=0.4
        )

        logger.info(f"   [SUCCESS] Pricing generated: ${pricing_data['suggested_price']}")

        # Compile complete listing
        listing = {
            "title": title,
            "description_html": description_data["long_description"],
            "short_description": description_data["short_description"],
            "bullet_points": description_data["bullet_points"],
            "seo": seo_data,
            "pricing": pricing_data,
            "tags": [
                niche.replace("_", "-"),
                category.lower().replace(" ", "-"),
                *seo_data["keywords"]["secondary"][:3]  # Top 3 keywords as tags
            ],
            "product_type": category,
            "vendor": brand_name,
            "meta": {
                "generated_at": datetime.now().isoformat(),
                "original_title": original_title,
                "cost_price": cost_price
            }
        }

        logger.info(f"   [SUCCESS] Complete listing generated successfully")

        return listing

    def get_usage_stats(self, last_n_hours: int = 24) -> Dict:
        """
        Get API usage statistics

        Args:
            last_n_hours: Look back period (default 24 hours)

        Returns:
            Usage statistics including costs
        """
        return self.usage_tracker.get_stats(last_n_hours)
