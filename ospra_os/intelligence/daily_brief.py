"""
DAILY BRIEF GENERATOR - Personalized Morning Summary

Generates a personalized daily brief that includes:
- Pending AI-recommended Actions (from Actions Queue)
- Store performance snapshot (24h + 7d trends)
- Top market opportunities
- Priority recommendations

This is displayed as a dashboard card AND sent as a morning email.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc

from ospra_os.database.action_models import Action, AIActionStatus, AIActionType
from ospra_os.database import Store, Product
from anthropic import Anthropic
from ospra_os.core.settings import get_settings

logger = logging.getLogger(__name__)


class DailyBriefGenerator:
    """
    Generates personalized daily briefs for users.

    Combines:
    - Pending Actions from AI recommendations
    - Performance metrics (revenue, sales, ROAS)
    - Top opportunities from market analysis
    - Prioritized action recommendations
    """

    def __init__(self, db: Session):
        self.db = db
        settings = get_settings()

        # Claude for AI summaries (optional)
        self.claude = None
        if settings.CLAUDE_API_KEY:
            try:
                self.claude = Anthropic(api_key=settings.CLAUDE_API_KEY)
                self.model = "claude-sonnet-4-5-20250929"
            except Exception as e:
                logger.warning(f"Claude not available for daily brief: {e}")

    async def generate_daily_brief(
        self,
        user_id: int,
        store_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate complete daily brief for user.

        Returns:
            {
                "timestamp": "2025-12-09T08:00:00",
                "greeting": "Good morning, Stephen",
                "summary_text": "AI-generated natural language summary",
                "pending_actions": {
                    "count": 4,
                    "high_confidence": 2,
                    "actions": [...]
                },
                "performance": {
                    "today": {...},
                    "week": {...},
                    "trends": {...}
                },
                "opportunities": {
                    "count": 3,
                    "top_products": [...]
                },
                "priorities": [
                    {"title": "...", "description": "...", "urgency": "high"},
                    ...
                ]
            }
        """
        logger.info(f"Generating daily brief for user {user_id}, store {store_id}")

        # Gather all components
        pending_actions = await self._get_pending_actions(user_id, store_id)
        performance = await self._get_performance_snapshot(user_id, store_id)
        opportunities = await self._get_top_opportunities(user_id, store_id)
        priorities = self._generate_priorities(pending_actions, performance, opportunities)

        # Generate AI summary
        summary_text = await self._generate_ai_summary(
            pending_actions, performance, opportunities, priorities
        )

        # Get user greeting
        now = datetime.now(timezone.utc)
        hour = now.hour
        if hour < 12:
            greeting = "Good morning"
        elif hour < 18:
            greeting = "Good afternoon"
        else:
            greeting = "Good evening"

        return {
            "timestamp": now.isoformat(),
            "greeting": greeting,
            "summary_text": summary_text,
            "pending_actions": pending_actions,
            "performance": performance,
            "opportunities": opportunities,
            "priorities": priorities
        }

    async def _get_pending_actions(
        self,
        user_id: int,
        store_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get pending actions from Actions Queue"""

        query = self.db.query(Action).filter(
            Action.user_id == user_id,
            Action.status == AIActionStatus.PENDING
        )

        if store_id:
            query = query.filter(Action.store_id == store_id)

        # Order by confidence desc, created_at desc
        actions = query.order_by(
            desc(Action.confidence),
            desc(Action.created_at)
        ).limit(10).all()

        # Count high confidence actions (>= 85%)
        high_confidence = sum(1 for a in actions if a.confidence >= 85)

        # Group by action type
        by_type = {}
        for action in actions:
            action_type = action.action_type.value
            if action_type not in by_type:
                by_type[action_type] = 0
            by_type[action_type] += 1

        # Serialize actions
        actions_data = []
        for action in actions:
            actions_data.append({
                "id": action.id,
                "type": action.action_type.value,
                "title": action.title,
                "description": action.description,
                "confidence": action.confidence,
                "estimated_impact": action.estimated_impact,
                "product_image": action.product_image,
                "created_at": action.created_at.isoformat(),
                "expires_at": action.expires_at.isoformat() if action.expires_at else None
            })

        return {
            "count": len(actions),
            "high_confidence": high_confidence,
            "by_type": by_type,
            "actions": actions_data
        }

    async def _get_performance_snapshot(
        self,
        user_id: int,
        store_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get performance metrics for today and last 7 days.

        In production, this would query:
        - Shopify sales data
        - Ad platform metrics (Meta, Google)
        - Email metrics

        For now, returns placeholder structure.
        """

        # TODO: Integrate with actual data sources
        # This is a placeholder structure

        return {
            "today": {
                "revenue": 0.0,
                "orders": 0,
                "avg_order_value": 0.0,
                "ad_spend": 0.0,
                "roas": 0.0
            },
            "last_7_days": {
                "revenue": 0.0,
                "orders": 0,
                "avg_order_value": 0.0,
                "ad_spend": 0.0,
                "roas": 0.0
            },
            "trends": {
                "revenue_change": 0.0,  # % change vs previous period
                "orders_change": 0.0,
                "roas_change": 0.0
            },
            "health_score": 75.0  # Overall business health 0-100
        }

    async def _get_top_opportunities(
        self,
        user_id: int,
        store_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get top market opportunities.

        In production, this would query:
        - Product discovery database
        - Trending products
        - Niche analysis

        For now, checks if there are pending deploy_product actions.
        """

        # Get deploy_product actions as opportunities
        query = self.db.query(Action).filter(
            Action.user_id == user_id,
            Action.status == AIActionStatus.PENDING,
            Action.action_type == AIActionType.DEPLOY_PRODUCT
        )

        if store_id:
            query = query.filter(Action.store_id == store_id)

        deploy_actions = query.order_by(desc(Action.confidence)).limit(5).all()

        opportunities = []
        for action in deploy_actions:
            payload = action.payload or {}
            opportunities.append({
                "product_name": payload.get("product_name", "Unknown"),
                "niche": payload.get("niche", "Unknown"),
                "ai_score": payload.get("ai_score", 0),
                "margin": payload.get("margin", 0),
                "estimated_impact": action.estimated_impact,
                "action_id": action.id
            })

        return {
            "count": len(opportunities),
            "top_products": opportunities
        }

    def _generate_priorities(
        self,
        pending_actions: Dict,
        performance: Dict,
        opportunities: Dict
    ) -> List[Dict[str, Any]]:
        """
        Generate prioritized action list based on all data.

        Priorities are ordered by:
        1. Critical issues (low health, negative trends)
        2. High-confidence actions with big impact
        3. New opportunities
        """

        priorities = []

        # Priority 1: Health issues
        health_score = performance.get("health_score", 100)
        if health_score < 60:
            priorities.append({
                "title": "Business Health Alert",
                "description": f"Health score at {health_score:.0f}/100. Review performance metrics.",
                "urgency": "high",
                "action_type": "review_metrics"
            })

        # Priority 2: High confidence actions
        high_conf_count = pending_actions.get("high_confidence", 0)
        if high_conf_count > 0:
            priorities.append({
                "title": f"Review {high_conf_count} High-Confidence Action{'s' if high_conf_count > 1 else ''}",
                "description": f"AI recommends {high_conf_count} action{'s' if high_conf_count > 1 else ''} with 85%+ confidence",
                "urgency": "medium",
                "action_type": "review_actions"
            })

        # Priority 3: Opportunities
        opp_count = opportunities.get("count", 0)
        if opp_count > 0:
            priorities.append({
                "title": f"Explore {opp_count} New Product Opportunit{'ies' if opp_count > 1 else 'y'}",
                "description": f"AI discovered {opp_count} high-potential product{'s' if opp_count > 1 else ''}",
                "urgency": "low",
                "action_type": "view_opportunities"
            })

        # Priority 4: Pending actions by type
        by_type = pending_actions.get("by_type", {})
        for action_type, count in by_type.items():
            if action_type == "pause_ad" and count > 0:
                priorities.insert(0, {  # High urgency
                    "title": f"Review {count} Underperforming Ad{'s' if count > 1 else ''}",
                    "description": f"AI recommends pausing {count} campaign{'s' if count > 1 else ''} losing money",
                    "urgency": "high",
                    "action_type": "review_ads"
                })

        return priorities[:5]  # Top 5 priorities

    async def _generate_ai_summary(
        self,
        pending_actions: Dict,
        performance: Dict,
        opportunities: Dict,
        priorities: List[Dict]
    ) -> str:
        """
        Generate natural language summary using Claude.

        Falls back to template if Claude unavailable.
        """

        if not self.claude:
            return self._generate_template_summary(pending_actions, performance, opportunities)

        system_prompt = """You are a helpful AI assistant generating a personalized morning business brief.

Style:
- Warm, professional, encouraging
- Conversational but concise (2-3 short paragraphs max)
- Focus on what matters TODAY
- End with a motivating note

Tone:
- "Your store has..." not "The store has..."
- "I've found 3 actions for you" not "There are 3 actions"
- Personalized and helpful
"""

        user_prompt = f"""Generate a brief morning summary for the user.

PENDING ACTIONS:
- Total: {pending_actions['count']}
- High Confidence (85%+): {pending_actions['high_confidence']}
- By Type: {pending_actions['by_type']}

PERFORMANCE (Last 7 Days):
- Revenue: ${performance['last_7_days']['revenue']:,.2f}
- Orders: {performance['last_7_days']['orders']}
- Health Score: {performance['health_score']:.0f}/100

OPPORTUNITIES:
- {opportunities['count']} new product opportunities discovered

PRIORITIES TODAY:
{self._format_priorities_for_ai(priorities)}

Write a warm 2-3 paragraph morning brief highlighting what they should focus on today."""

        try:
            response = self.claude.messages.create(
                model=self.model,
                max_tokens=500,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            )

            return response.content[0].text

        except Exception as e:
            logger.error(f"Error generating AI summary: {e}")
            return self._generate_template_summary(pending_actions, performance, opportunities)

    def _format_priorities_for_ai(self, priorities: List[Dict]) -> str:
        """Format priorities for AI prompt"""
        if not priorities:
            return "No urgent priorities"

        formatted = []
        for i, p in enumerate(priorities, 1):
            formatted.append(f"{i}. {p['title']} ({p['urgency']} urgency)")

        return "\n".join(formatted)

    def _generate_template_summary(
        self,
        pending_actions: Dict,
        performance: Dict,
        opportunities: Dict
    ) -> str:
        """Fallback template-based summary"""

        action_count = pending_actions.get("count", 0)
        high_conf = pending_actions.get("high_confidence", 0)
        opp_count = opportunities.get("count", 0)
        health = performance.get("health_score", 0)

        summary = f"Your business health score is {health:.0f}/100. "

        if action_count > 0:
            summary += f"I've queued {action_count} AI-recommended action{'s' if action_count != 1 else ''} "
            if high_conf > 0:
                summary += f"({high_conf} with high confidence) "
            summary += "for your review. "

        if opp_count > 0:
            summary += f"Plus, I've discovered {opp_count} new product opportunit{'ies' if opp_count != 1 else 'y'} worth exploring. "

        if action_count == 0 and opp_count == 0:
            summary += "No urgent actions needed today. Keep monitoring your metrics."
        else:
            summary += "Focus on reviewing high-confidence actions first for maximum impact."

        return summary


# Singleton instance
_daily_brief_generator = None


def get_daily_brief_generator(db: Session) -> DailyBriefGenerator:
    """Get or create daily brief generator instance"""
    global _daily_brief_generator
    if _daily_brief_generator is None:
        _daily_brief_generator = DailyBriefGenerator(db)
    return _daily_brief_generator
