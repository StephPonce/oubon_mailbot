"""
Enhanced Trend Analysis System
Integrates Google Trends, Instagram, TikTok for comprehensive product intelligence
"""

import os
import logging
from typing import Dict, Optional, List
from datetime import datetime, timedelta
import asyncio

logger = logging.getLogger(__name__)

# Google Trends
try:
    from pytrends.request import TrendReq
    HAS_PYTRENDS = True
except ImportError:
    HAS_PYTRENDS = False
    logger.warning("pytrends not installed. Run: pip install pytrends")

# Claude AI for product analysis
try:
    from anthropic import Anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False
    logger.warning("anthropic package not installed. AI analysis will be unavailable.")


class TrendAnalyzer:
    """
    Multi-platform trend analysis
    - Google Trends (search momentum)
    - Instagram (hashtag popularity)
    - TikTok (video views)
    """

    def __init__(self):
        # Google Trends
        if HAS_PYTRENDS:
            try:
                self.pytrends = TrendReq(hl='en-US', tz=360)
                logger.info("✅ Google Trends initialized")
            except Exception as e:
                logger.warning(f"⚠️  Google Trends init failed: {e}")
                self.pytrends = None
        else:
            self.pytrends = None

        # Instagram Graph API
        self.instagram_token = os.getenv('INSTAGRAM_ACCESS_TOKEN')
        if self.instagram_token:
            logger.info("✅ Instagram API token found")
        else:
            logger.warning("⚠️  INSTAGRAM_ACCESS_TOKEN not set")

        # TikTok API
        self.tiktok_client_key = os.getenv('TIKTOK_CLIENT_KEY')
        if self.tiktok_client_key:
            logger.info("✅ TikTok API credentials found")
        else:
            logger.warning("⚠️  TIKTOK_CLIENT_KEY not set")

        # Claude AI for product analysis
        self.anthropic_key = os.getenv('ANTHROPIC_API_KEY')
        if HAS_ANTHROPIC and self.anthropic_key:
            try:
                self.claude_client = Anthropic(api_key=self.anthropic_key)
                logger.info("✅ Claude AI initialized for product analysis")
            except Exception as e:
                logger.warning(f"⚠️  Claude AI init failed: {e}")
                self.claude_client = None
        else:
            self.claude_client = None
            if not self.anthropic_key:
                logger.warning("⚠️  ANTHROPIC_API_KEY not set - AI analysis unavailable")

    async def analyze_product_trends(self, product: Dict) -> Dict:
        """
        Comprehensive trend analysis for a product
        Returns enriched data for AI analysis
        """
        product_name = product.get('name', '')
        niche = product.get('niche', '')

        trend_data = {
            'google_trends': await self._get_google_trends(product_name, niche),
            'instagram_data': await self._get_instagram_data(product_name),
            'tiktok_data': await self._get_tiktok_data(product_name),
            'aliexpress_metrics': self._extract_aliexpress_metrics(product),
            'market_signals': self._calculate_market_signals(product)
        }

        return trend_data

    def analyze_product(self, product: Dict) -> Dict:
        """
        AI-powered product analysis using Claude
        Returns investment recommendation and insights
        """
        if not self.claude_client:
            return {
                "status": "error",
                "message": "Claude AI not available. Set ANTHROPIC_API_KEY environment variable.",
                "score": 0,
                "recommendation": "UNAVAILABLE"
            }

        try:
            product_name = product.get('name', 'Unknown Product')
            price = product.get('price', 0)
            cost = product.get('cost', 0)
            velocity_score = product.get('velocity_score', 0)
            profit_margin = product.get('profit_margin', 0)
            estimated_profit = product.get('estimated_profit', 0)
            niche = product.get('niche', 'Unknown')

            # Build analysis prompt
            prompt = f"""You are an expert e-commerce analyst. Analyze this product opportunity:

**Product:** {product_name}
**Niche:** {niche}
**Price:** ${price:.2f}
**Cost:** ${cost:.2f}
**Velocity Score:** {velocity_score}/100
**Profit Margin:** {profit_margin * 100:.1f}%
**Estimated Profit per Sale:** ${estimated_profit:.2f}

Provide a structured analysis with:

1. **Score** (0-10): Overall investment score
2. **Recommendation**: One of STRONG_BUY, BUY, HOLD, PASS
3. **Reasoning**: 3-5 bullet points on marketing angles and opportunities
4. **Risks**: 2-4 bullet points on potential challenges

Format your response as JSON:
{{
  "score": 8.5,
  "recommendation": "STRONG_BUY",
  "reasoning": ["Point 1", "Point 2", "Point 3"],
  "risks": ["Risk 1", "Risk 2"]
}}"""

            logger.info(f"🤖 Analyzing product with Claude: {product_name}")

            response = self.claude_client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}]
            )

            # Parse response
            import json
            response_text = response.content[0].text

            # Try to extract JSON from response
            try:
                # Find JSON in response (might have markdown code blocks)
                import re
                json_match = re.search(r'\{[\s\S]*\}', response_text)
                if json_match:
                    analysis = json.loads(json_match.group())
                else:
                    raise ValueError("No JSON found in response")
            except:
                # Fallback if parsing fails
                logger.warning("Failed to parse Claude response as JSON, using defaults")
                analysis = {
                    "score": 7.0,
                    "recommendation": "HOLD",
                    "reasoning": ["AI analysis parsing failed"],
                    "risks": ["Unable to complete full analysis"]
                }

            logger.info(f"✅ Analysis complete - Score: {analysis.get('score')}/10, Recommendation: {analysis.get('recommendation')}")

            return analysis

        except Exception as e:
            logger.error(f"Product analysis failed: {e}")
            return {
                "status": "error",
                "message": f"Analysis failed: {str(e)}",
                "score": 0,
                "recommendation": "ERROR",
                "reasoning": ["Analysis service unavailable"],
                "risks": ["Technical error occurred"]
            }

    async def _get_google_trends(self, product_name: str, niche: str) -> Dict:
        """
        Get Google Trends data for product/niche
        """
        if not self.pytrends:
            return {'available': False, 'reason': 'pytrends not installed'}

        try:
            # Extract key search terms
            keywords = self._extract_keywords(product_name, niche)[:5]  # Max 5 keywords

            if not keywords:
                return {'available': False, 'reason': 'no keywords'}

            # Build payload (last 90 days)
            self.pytrends.build_payload(
                keywords,
                timeframe='today 3-m',  # Last 3 months
                geo='US'
            )

            # Rate limiting: prevent 429 errors
            await asyncio.sleep(2)

            # Get interest over time
            interest_over_time = self.pytrends.interest_over_time()

            if interest_over_time.empty:
                return {'available': False, 'reason': 'no data'}

            # Calculate trends
            latest_values = {}
            momentum = {}

            for keyword in keywords:
                if keyword in interest_over_time.columns:
                    values = interest_over_time[keyword].values
                    latest_values[keyword] = int(values[-1]) if len(values) > 0 else 0

                    # Calculate momentum (% change over period)
                    if len(values) >= 2:
                        start_avg = values[:len(values)//3].mean()
                        end_avg = values[-len(values)//3:].mean()
                        if start_avg > 0:
                            momentum[keyword] = round(((end_avg - start_avg) / start_avg) * 100, 1)
                        else:
                            momentum[keyword] = 0
                    else:
                        momentum[keyword] = 0

            # Overall trend direction
            primary_keyword = keywords[0]
            trend_direction = 'RISING' if momentum.get(primary_keyword, 0) > 10 else \
                            'FALLING' if momentum.get(primary_keyword, 0) < -10 else 'STABLE'

            return {
                'available': True,
                'keywords': keywords,
                'interest_scores': latest_values,
                'momentum': momentum,
                'trend_direction': trend_direction,
                'primary_momentum': momentum.get(primary_keyword, 0)
            }

        except Exception as e:
            logger.error(f"Google Trends error: {e}")
            return {'available': False, 'reason': str(e)}

    async def _get_instagram_data(self, product_name: str) -> Dict:
        """
        Get Instagram hashtag data
        Note: Requires Instagram Graph API setup
        """
        if not self.instagram_token:
            return {'available': False, 'reason': 'no_token'}

        try:
            import aiohttp

            # Extract hashtags from product name
            hashtags = self._extract_hashtags(product_name)

            # For now, return placeholder - full implementation requires Business account
            # Instagram Graph API requires Business/Creator account with approved permissions
            return {
                'available': False,
                'reason': 'requires_business_account',
                'note': 'Instagram Graph API requires Business account with approved permissions',
                'potential_hashtags': hashtags
            }

        except Exception as e:
            logger.error(f"Instagram API error: {e}")
            return {'available': False, 'reason': str(e)}

    async def _get_tiktok_data(self, product_name: str) -> Dict:
        """
        Get TikTok trending data
        Note: Requires TikTok API setup
        """
        if not self.tiktok_client_key:
            return {'available': False, 'reason': 'no_credentials'}

        # TikTok API requires OAuth flow - placeholder for now
        return {
            'available': False,
            'reason': 'requires_oauth',
            'note': 'TikTok API requires OAuth authentication flow'
        }

    def _extract_aliexpress_metrics(self, product: Dict) -> Dict:
        """
        Extract and format AliExpress metrics
        """
        orders = product.get('orders', 0)
        rating = product.get('rating', 0)
        price = product.get('price', 0)
        supplier_rating = product.get('supplier_rating', 0)

        # Calculate velocity (orders per day estimate)
        # Assuming products have been on sale for ~1 year on average
        estimated_velocity = round(orders / 365, 1) if orders > 0 else 0

        return {
            'total_orders': orders,
            'rating': rating,
            'price': price,
            'supplier_rating': supplier_rating,
            'estimated_daily_orders': estimated_velocity,
            'monthly_orders_estimate': round(estimated_velocity * 30),
            'revenue_estimate_monthly': round(price * estimated_velocity * 30, 2)
        }

    def _calculate_market_signals(self, product: Dict) -> Dict:
        """
        Calculate market opportunity signals
        """
        orders = product.get('orders', 0)
        rating = product.get('rating', 0)
        score = product.get('score', 0)

        # Market saturation estimate (simplified)
        saturation = 'LOW' if orders < 5000 else 'MEDIUM' if orders < 20000 else 'HIGH'

        # Competition level
        competition = 'LOW' if orders < 10000 else 'MEDIUM' if orders < 50000 else 'HIGH'

        # Demand strength
        demand = 'HIGH' if orders > 20000 and rating > 4.5 else \
                'MEDIUM' if orders > 5000 and rating > 4.0 else 'LOW'

        return {
            'saturation_level': saturation,
            'competition_level': competition,
            'demand_strength': demand,
            'overall_opportunity': 'HIGH' if score > 8 else 'MEDIUM' if score > 6 else 'LOW'
        }

    def _extract_keywords(self, product_name: str, niche: str) -> List[str]:
        """
        Extract search keywords from product name and niche
        """
        keywords = []

        # Add niche
        if niche:
            keywords.append(niche.lower())

        # Extract key terms from product name
        name_lower = product_name.lower()

        # Common product type keywords
        product_types = ['smart', 'wifi', 'wireless', 'bluetooth', 'led', 'portable',
                        'mini', 'pro', 'ultra', 'rechargeable', 'solar', 'robot']

        for ptype in product_types:
            if ptype in name_lower:
                keywords.append(ptype)
                break

        # Extract main product category
        categories = ['light', 'camera', 'speaker', 'vacuum', 'thermostat', 'plug',
                     'bulb', 'strip', 'sensor', 'lock', 'doorbell', 'monitor']

        for category in categories:
            if category in name_lower:
                keywords.append(category)
                break

        return list(set(keywords))[:5]  # Return unique, max 5

    def _extract_hashtags(self, product_name: str) -> List[str]:
        """
        Generate potential Instagram hashtags
        """
        name_lower = product_name.lower().replace('-', ' ')
        words = name_lower.split()

        # Remove common words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'with', 'for', 'to', 'of'}
        keywords = [w for w in words if w not in stop_words and len(w) > 3]

        # Generate hashtags
        hashtags = [f"#{w}" for w in keywords[:5]]

        # Add category hashtags
        if 'smart' in name_lower:
            hashtags.append('#smarthome')
        if any(word in name_lower for word in ['light', 'led', 'bulb']):
            hashtags.append('#lighting')
        if 'security' in name_lower or 'camera' in name_lower:
            hashtags.append('#homesecurity')

        return hashtags[:8]  # Max 8 hashtags

    def chat_response(self, message: str, context: Optional[Dict] = None, user_id: Optional[int] = None) -> str:
        """
        Generate a conversational response using Claude AI with smart context building.

        Now uses the scalable memory system to provide unlimited historical knowledge
        without hitting token limits.

        Args:
            message: User's question/message
            context: Optional context about current product, niche, etc.
            user_id: Optional user ID for personalized learning context

        Returns:
            Claude's response as a string
        """
        if not self.claude_client:
            return "I'm currently unavailable. Please make sure ANTHROPIC_API_KEY is set in your environment."

        try:
            # Build system prompt with context
            system_prompt = """You are Ospra, the Chief Operating Officer of the user's e-commerce business. You speak with the authority and clarity of a seasoned executive who respects their CEO's time.

Communication Style:
- Direct and concise - get to the point
- Use data to support insights, not decorate them
- Organize information with clear hierarchy
- NO decorative emoji - Do not use 🎧, 📹, 🔥, 💡, 🚀, 📊, 💰, or any product/category emoji
- ONLY use ✓ and ⚠ when marking status or warnings
- Speak in complete sentences, not bullet-point fragments
- When presenting options, be clear about your recommendation and why

Format Guidelines:
- Use headers sparingly and only for major sections
- Bold for emphasis on key metrics or actions only
- Present numbers cleanly: "$45,678" not "**$45,678** 💰"
- Product names are plain text: "Smart Home Security Camera" NOT "🔥 Smart Home Security Camera 📹"
- If listing items, use clean numbered lists or brief paragraphs
- End with a clear next step or question when appropriate

You have access to:
- Real-time store analytics and revenue data
- Product performance metrics
- Market trends and competitor analysis
- Email/support queue status
- Advertising performance

Your role is to surface what matters, recommend actions, and help the CEO make informed decisions quickly. You're not here to impress - you're here to help run a profitable business."""

            # Build user message with context
            context_str = ""

            # Add current product context if provided (immediate context)
            if context:
                context_str += "\n\n**Current Context:**\n"
                if 'product_name' in context:
                    context_str += f"Product: {context['product_name']}\n"
                if 'product_price' in context:
                    context_str += f"Price: ${context['product_price']}\n"
                if 'velocity_score' in context:
                    context_str += f"Velocity Score: {context['velocity_score']}\n"
                if 'profit_margin' in context:
                    context_str += f"Profit Margin: {context['profit_margin']}%\n"
                if 'niche' in context:
                    context_str += f"Niche: {context['niche']}\n"

            # Add smart learning context if user_id provided (scalable memory system)
            if user_id:
                try:
                    from ospra_os.learning.context_builder import build_claude_context
                    from ospra_os.database.multi_store_models import SessionLocal

                    db = SessionLocal()
                    try:
                        # Use smart context builder - automatically selects relevant data based on query
                        learning_context = build_claude_context(user_id, message, db)
                        context_str += "\n\n" + learning_context
                    finally:
                        db.close()

                except ImportError:
                    logger.warning("Smart context builder not available - falling back to basic context")
                    # Fallback to old method if context_builder not available
                    try:
                        from ospra_os.learning.hybrid_learning_engine import get_learning_engine

                        engine = get_learning_engine()

                        # Get personal learning insights (Soar+ tiers)
                        try:
                            personal = engine.session.query(engine.PersonalLearningWeights).filter_by(user_id=user_id).first()

                            if personal and personal.learning_cycles > 0:
                                context_str += "\n**Your Store's Performance History:**\n"
                                context_str += f"- Products analyzed: {personal.sales_analyzed}\n"

                                if personal.best_performing_niches:
                                    niches = personal.best_performing_niches[:3] if isinstance(personal.best_performing_niches, list) else []
                                    if niches:
                                        context_str += f"- Best performing niches: {', '.join(niches)}\n"

                                if personal.optimal_price_range and isinstance(personal.optimal_price_range, dict):
                                    min_price = personal.optimal_price_range.get('min', 0)
                                    max_price = personal.optimal_price_range.get('max', 0)
                                    if min_price > 0 and max_price > 0:
                                        context_str += f"- Optimal price range: ${min_price:.0f}-${max_price:.0f}\n"
                        except:
                            pass  # Personal weights not available
                    except Exception as e:
                        logger.warning(f"Could not fetch fallback learning context: {e}")

                except Exception as e:
                    logger.warning(f"Could not fetch smart context: {e}")
                    # Continue without learning context

            user_message = context_str + "\n" + message if context_str else message

            # DEBUG: Print what Claude receives
            print("=" * 80)
            print("🔍 CLAUDE RECEIVES THIS CONTEXT:")
            print("=" * 80)
            print(f"System Prompt: {system_prompt[:200]}...")
            print("-" * 80)
            print(f"User Message with Context:\n{user_message}")
            print("=" * 80)

            # Call Claude API
            response = self.claude_client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=1024,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": user_message
                    }
                ]
            )

            # Extract text from response
            return response.content[0].text

        except Exception as e:
            logger.error(f"Claude chat error: {e}")
            return f"Sorry, I encountered an error: {str(e)}"
