"""
BRIEFING ENGINE - PROFESSIONAL AI BRIEFINGS

Professional tone, no emojis, Bloomberg analyst style.
Uses unified context to generate executive briefings.

Key features:
- Morning briefings (6 AM user timezone)
- On-demand briefings
- Attention items (requires immediate action)
- Professional tone (no "let's", no emojis, data-driven)
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
from anthropic import Anthropic
from sqlalchemy.orm import Session

from ospra_os.intelligence.unified_context import get_unified_context_builder
from ospra_os.core.settings import get_settings
from ospra_os.ai.markdown_stripper import strip_markdown

logger = logging.getLogger(__name__)


class BriefingEngine:
    """
    Generates professional AI briefings using unified context.

    Style: Bloomberg analyst - concise, data-driven, actionable.
    NO emojis, NO "let's do this", NO fluff.
    """

    def __init__(self, db: Session):
        self.db = db
        settings = get_settings()

        if not settings.CLAUDE_API_KEY:
            raise ValueError("CLAUDE_API_KEY not configured")

        self.claude = Anthropic(api_key=settings.CLAUDE_API_KEY)
        self.model = "claude-sonnet-4-5-20250929"
        self.context_builder = get_unified_context_builder(db)

    async def generate_morning_briefing(
        self,
        user_id: Optional[int] = None,
        store_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate morning briefing for user.

        Called automatically at 6 AM user timezone.
        Shows what needs attention TODAY.

        Returns:
            {
                "timestamp": "2025-11-27T06:00:00",
                "briefing_text": "...",
                "attention_items": [...],
                "key_metrics": {...},
                "recommended_actions": [...]
            }
        """
        logger.info(f"Generating morning briefing for user {user_id}, store {store_id}")

        # Get unified context (ALL data)
        context = await self.context_builder.build_full_context(user_id, store_id)

        # Extract attention items
        attention_items = self._extract_attention_items(context)

        # Generate AI briefing
        briefing_text = await self._generate_ai_briefing(context, attention_items)

        # Extract key metrics
        key_metrics = context.get("summary", {})

        # Get recommended actions
        recommended_actions = self._get_recommended_actions(context, attention_items)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "briefing_text": briefing_text,
            "attention_items": attention_items,
            "key_metrics": key_metrics,
            "recommended_actions": recommended_actions
        }

    async def generate_on_demand_briefing(
        self,
        user_id: Optional[int] = None,
        store_id: Optional[int] = None,
        focus_area: Optional[str] = None
    ) -> str:
        """
        Generate on-demand briefing.

        User can request briefing at any time, optionally focused on:
        - "products" - Product performance analysis
        - "ads" - Ad campaign performance
        - "emails" - Customer signals from emails
        - "competitors" - Competitive intelligence

        Args:
            user_id: User ID
            store_id: Store ID
            focus_area: Optional focus area

        Returns:
            Briefing text
        """
        logger.info(f"Generating on-demand briefing (focus: {focus_area})")

        # Get unified context
        context = await self.context_builder.build_full_context(user_id, store_id)

        # Generate focused briefing
        if focus_area:
            return await self._generate_focused_briefing(context, focus_area)
        else:
            return await self._generate_full_briefing(context)

    def _extract_attention_items(self, context: Dict) -> List[Dict[str, Any]]:
        """
        Extract items that require IMMEDIATE attention.

        Attention items are:
        - Critical correlations (severity: high)
        - Failed campaigns (ROAS < 1.0, spend > $100)
        - Products underperforming (>30 days, <10 sales)
        - Quality issues (high sales + complaints)

        Returns list sorted by priority.
        """
        attention_items = []

        # Critical correlations
        correlations = context.get("correlations", [])
        for corr in correlations:
            if corr.get("severity") == "high":
                attention_items.append({
                    "type": "critical_issue",
                    "priority": 1,
                    "title": corr.get("type", "").replace("_", " ").title(),
                    "description": corr.get("signal", ""),
                    "action": corr.get("action", ""),
                    "data": corr
                })

        # Failed ad campaigns
        ad_data = context.get("ads", {})
        worst_campaigns = ad_data.get("worst_campaigns", [])
        for campaign in worst_campaigns:
            if campaign.get("roas", 0) < 1.0 and campaign.get("spend", 0) > 100:
                attention_items.append({
                    "type": "underperforming_ad",
                    "priority": 2,
                    "title": f"Campaign Burning Budget: {campaign.get('name', 'Unknown')}",
                    "description": f"ROAS {campaign.get('roas', 0):.2f} with ${campaign.get('spend', 0):.2f} spend",
                    "action": "Pause campaign or adjust targeting",
                    "data": campaign
                })

        # Underperforming products
        product_data = context.get("products", {})
        underperformers = product_data.get("underperformers", [])
        for product in underperformers[:5]:  # Top 5 worst
            if product.get("days_active", 0) > 30:
                attention_items.append({
                    "type": "underperforming_product",
                    "priority": 3,
                    "title": f"Product Stalled: {product.get('title', 'Unknown')}",
                    "description": f"{product.get('days_active', 0)} days active, {product.get('sales', 0)} sales",
                    "action": "Discontinue or launch ad campaign",
                    "data": product
                })

        # Sort by priority
        attention_items.sort(key=lambda x: x["priority"])

        return attention_items

    async def _generate_ai_briefing(
        self,
        context: Dict,
        attention_items: List[Dict]
    ) -> str:
        """
        Generate AI briefing text using Claude.

        Professional Bloomberg analyst tone:
        - No emojis
        - No "let's", "awesome", "great"
        - Data-driven
        - Concise
        - Actionable
        """
        summary = context.get("summary", {})

        system_prompt = """You are a professional business analyst providing executive briefings.

TONE REQUIREMENTS:
- Professional, concise, data-driven
- Bloomberg analyst style
- NO emojis, NO exclamation marks, NO "let's" or "awesome"
- Focus on facts, metrics, and actionable insights
- Direct, clear language

FORMATTING REQUIREMENTS:
- NO markdown symbols (no ##, ***, ---, etc.)
- NO headings with # or ##
- NO bold with ** or __
- NO bullet points with *, -, or +
- Use plain text with clear paragraph breaks
- Use numbers (1, 2, 3) for lists instead of bullets
- Use colons and indentation for structure

Your briefing should:
1. Start with overall business health
2. Highlight critical issues requiring immediate attention
3. Note key metrics and trends
4. Provide specific, actionable recommendations
5. Be under 300 words

Format in plain text with clear paragraph breaks."""

        user_prompt = f"""Generate morning briefing for today.

BUSINESS METRICS:
- Total Revenue: ${summary.get('total_revenue', 0):,.2f}
- Active Products: {summary.get('active_products', 0)}
- Ad Spend: ${summary.get('ad_spend', 0):,.2f}
- Average ROAS: {summary.get('avg_roas', 0):.2f}x
- Health Score: {summary.get('health_score', 0):.1f}/100

ATTENTION ITEMS ({len(attention_items)}):
{self._format_attention_items(attention_items)}

CORRELATIONS DETECTED:
{len(context.get('correlations', []))} patterns detected across product sales, ad performance, and customer signals.

Generate a professional executive briefing."""

        try:
            response = self.claude.messages.create(
                model=self.model,
                max_tokens=1500,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            )

            # Strip markdown formatting symbols
            return strip_markdown(response.content[0].text)

        except Exception as e:
            logger.error(f"Error generating AI briefing: {e}")
            # Fallback to template
            return self._generate_fallback_briefing(summary, attention_items)

    async def _generate_focused_briefing(
        self,
        context: Dict,
        focus_area: str
    ) -> str:
        """Generate briefing focused on specific area"""

        area_prompts = {
            "products": """Analyze product performance. Focus on:
- Top performers and why they succeed
- Underperformers requiring action
- Product portfolio health
- Recommendations for product mix optimization""",

            "ads": """Analyze advertising performance. Focus on:
- Campaign efficiency (ROAS, CPC, CTR)
- Budget allocation recommendations
- Winning vs losing campaigns
- Optimization opportunities""",

            "emails": """Analyze customer signals from emails. Focus on:
- Common complaints or issues
- Feature requests
- Refund patterns
- Customer satisfaction trends""",

            "competitors": """Analyze competitive landscape. Focus on:
- New competitor products
- Price changes
- Market share shifts
- Strategic recommendations"""
        }

        prompt = area_prompts.get(focus_area, "Provide general business analysis")

        system_prompt = """You are a professional business analyst.
Provide concise, data-driven analysis in Bloomberg style.
NO emojis, NO fluff, just facts and actionable insights.
NO markdown formatting symbols (no ##, ***, ---, etc.).
Use plain text with clear paragraph breaks only."""

        try:
            response = self.claude.messages.create(
                model=self.model,
                max_tokens=1000,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": f"{prompt}\n\nContext:\n{json.dumps(context.get(focus_area, {}), indent=2)}"}
                ]
            )

            # Strip markdown formatting symbols
            return strip_markdown(response.content[0].text)

        except Exception as e:
            logger.error(f"Error generating focused briefing: {e}")
            return f"Unable to generate {focus_area} briefing at this time."

    async def _generate_full_briefing(self, context: Dict) -> str:
        """Generate complete business briefing"""
        attention_items = self._extract_attention_items(context)
        return await self._generate_ai_briefing(context, attention_items)

    def _format_attention_items(self, items: List[Dict]) -> str:
        """Format attention items for AI prompt"""
        if not items:
            return "None - no immediate issues detected"

        formatted = []
        for i, item in enumerate(items[:5], 1):  # Top 5
            formatted.append(
                f"{i}. {item['title']}\n"
                f"   {item['description']}\n"
                f"   Action: {item['action']}"
            )

        return "\n".join(formatted)

    def _get_recommended_actions(
        self,
        context: Dict,
        attention_items: List[Dict]
    ) -> List[Dict[str, Any]]:
        """
        Get recommended actions based on context and attention items.

        Returns list of one-click actions user can take.
        """
        actions = []

        # From attention items
        for item in attention_items[:3]:  # Top 3
            action_type = item["type"]

            if action_type == "underperforming_ad":
                actions.append({
                    "id": f"pause_campaign_{item['data'].get('id')}",
                    "type": "pause_campaign",
                    "title": f"Pause Campaign: {item['data'].get('name')}",
                    "description": f"Immediately stop spending on ROAS {item['data'].get('roas', 0):.2f} campaign",
                    "params": {
                        "campaign_id": item['data'].get('id')
                    }
                })

            elif action_type == "underperforming_product":
                actions.append({
                    "id": f"discontinue_product_{item['data'].get('id')}",
                    "type": "discontinue_product",
                    "title": f"Discontinue: {item['data'].get('title')}",
                    "description": f"Remove product after {item['data'].get('days_active', 0)} days with minimal sales",
                    "params": {
                        "product_id": item['data'].get('id')
                    }
                })

        return actions

    def _generate_fallback_briefing(
        self,
        summary: Dict,
        attention_items: List[Dict]
    ) -> str:
        """Generate template-based briefing if AI fails"""

        briefing = f"""# Business Briefing - {datetime.now(timezone.utc).strftime('%Y-%m-%d')}

## Overview

Health Score: {summary.get('health_score', 0):.1f}/100

Current metrics:
- Total Revenue: ${summary.get('total_revenue', 0):,.2f}
- Active Products: {summary.get('active_products', 0)}
- Ad Spend: ${summary.get('ad_spend', 0):,.2f}
- Average ROAS: {summary.get('avg_roas', 0):.2f}x

## Attention Required

{len(attention_items)} items require immediate attention:

"""

        for i, item in enumerate(attention_items[:5], 1):
            briefing += f"{i}. **{item['title']}**\n"
            briefing += f"   {item['description']}\n"
            briefing += f"   Action: {item['action']}\n\n"

        return briefing


# Singleton instance
_briefing_engine = None


def get_briefing_engine(db: Session) -> BriefingEngine:
    """Get or create briefing engine instance"""
    global _briefing_engine
    if _briefing_engine is None:
        _briefing_engine = BriefingEngine(db)
    return _briefing_engine
