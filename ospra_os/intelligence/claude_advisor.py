"""
Claude AI Business Advisor Integration

Claude acts as your AI business manager, providing:
- Daily briefings
- Weekly learning reports
- Chat-based business advice
- Data-driven recommendations
"""

import os
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from anthropic import Anthropic
import logging

logger = logging.getLogger(__name__)


class ClaudeBusinessAdvisor:
    """
    Claude AI acts as business manager
    Provides insights, recommendations, weekly reports
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment")

        self.claude = Anthropic(api_key=self.api_key)
        self.conversation_history = []

        # Model to use - Claude 3.5 Sonnet (best balance of speed/quality)
        # Note: Requires credits in Anthropic account
        self.model = "claude-3-5-sonnet-20241022"

    async def daily_briefing(self, date: Optional[str] = None) -> str:
        """
        Generate daily business briefing

        Args:
            date: Date string (YYYY-MM-DD), defaults to today

        Returns:
            Formatted daily briefing text
        """
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')

        logger.info(f"📊 Generating daily briefing for {date}")

        # Gather business metrics
        data = await self._gather_business_metrics(date)

        prompt = f"""
You are the AI business manager for Oubon Shop, a smart home products e-commerce store.

Generate a daily briefing for {date}.

## BUSINESS METRICS TODAY:

**Revenue & Sales:**
- Revenue: ${data.get('revenue', 0):,.2f}
- Orders: {data.get('orders', 0)}
- Average order value: ${data.get('aov', 0):.2f}

**Product Discovery:**
- New products discovered: {data.get('products_discovered', 0)}
- Products added to store: {data.get('products_added', 0)}
- Top scoring product: {data.get('top_product_name', 'N/A')} ({data.get('top_product_score', 0)}/10)

**Marketing:**
- Ad spend: ${data.get('ad_spend', 0):,.2f}
- Ad ROAS: {data.get('roas', 0):.2f}x
- Email campaigns sent: {data.get('emails_sent', 0)}
- Emails processed: {data.get('emails_processed', 0)}

**Customer Satisfaction:**
- Average rating: {data.get('avg_rating', 0):.1f}/5
- Support tickets: {data.get('support_tickets', 0)}
- Resolved today: {data.get('tickets_resolved', 0)}

## YOUR BRIEFING SHOULD INCLUDE:

1. **TL;DR** (2 sentences max)
   - Quick overview of today's performance

2. **✅ What Worked Today**
   - Specific wins and successes
   - What the data tells us is working

3. **⚠️ What Needs Attention**
   - Issues, problems, or concerning trends
   - What requires immediate action

4. **🎯 Top 3 Action Items for Tomorrow**
   - Specific, actionable tasks
   - Prioritized by impact

5. **💡 One Key Learning**
   - What the data taught us today
   - How this improves our strategy

Be specific, data-driven, and actionable. Focus on what matters most.
Use bullet points. Be concise but insightful.
"""

        try:
            response = self.claude.messages.create(
                model=self.model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )

            briefing = response.content[0].text
            logger.info("✅ Daily briefing generated")
            return briefing

        except Exception as e:
            logger.error(f"Failed to generate daily briefing: {e}")
            return f"Error generating briefing: {str(e)}"

    async def weekly_report(self) -> str:
        """
        Generate comprehensive weekly learning report

        Returns:
            Formatted weekly report with AI insights
        """
        logger.info("📈 Generating weekly learning report")

        # Gather weekly metrics
        data = await self._gather_weekly_metrics()

        prompt = f"""
You are the AI business manager for Oubon Shop.

Generate a WEEKLY LEARNING REPORT analyzing what we learned this week.

## WEEK'S PERFORMANCE DATA:

**Financial:**
- Total revenue: ${data.get('total_revenue', 0):,.2f}
- Total orders: {data.get('total_orders', 0)}
- Average order value: ${data.get('aov', 0):.2f}
- Growth vs last week: {data.get('growth_rate', 0):+.1f}%

**Product Intelligence:**
- Products discovered: {data.get('products_discovered', 0)}
- Products launched: {data.get('products_launched', 0)}
- Products that sold: {data.get('products_sold', 0)}
- Products with no sales: {data.get('products_failed', 0)}
- Average product score: {data.get('avg_product_score', 0):.1f}/10

**Marketing Performance:**
- Total ad spend: ${data.get('ad_spend', 0):,.2f}
- Total ROAS: {data.get('roas', 0):.2f}x
- Campaigns run: {data.get('campaigns', 0)}
- Best performing ad: {data.get('best_ad', 'N/A')}
- Worst performing ad: {data.get('worst_ad', 'N/A')}

**Customer Insights:**
- Customer acquisition cost: ${data.get('cac', 0):.2f}
- Average customer lifetime value: ${data.get('ltv', 0):.2f}
- Customer satisfaction: {data.get('csat', 0):.1f}/5
- Repeat customer rate: {data.get('repeat_rate', 0):.1f}%

## PATTERNS OBSERVED:

**Product Performance:**
{self._format_patterns(data.get('product_patterns', []))}

**Customer Behavior:**
{self._format_patterns(data.get('customer_patterns', []))}

**Sales Trends:**
{self._format_patterns(data.get('sales_patterns', []))}

---

## YOUR COMPREHENSIVE REPORT SHOULD INCLUDE:

### 🧠 What We Learned This Week

#### Key Insights
Provide 3-5 major insights from the data. Focus on patterns and correlations.

#### ✅ What Worked
Specific tactics, products, or strategies that succeeded. Explain WHY they worked.

#### ❌ What Didn't Work
What failed and why. What does the data tell us about these failures?

#### 🤖 AI Learning Updates
How is the AI adjusting its recommendations based on this week's results?
- Weight adjustments made
- New patterns discovered
- Confidence score updates

#### 🎯 Recommendations for Next Week
Provide specific, actionable recommendations for the coming week.
Prioritize by expected impact.

#### 📊 Confidence Scores (Updated)
Update confidence scores for:
- Product types (which categories work best)
- Price points (optimal pricing)
- Marketing channels (which ads work)
- Timing strategies (when to launch products)

Be analytical, specific, and forward-looking. This is a learning document.
Focus on continuous improvement and data-driven insights.
"""

        try:
            response = self.claude.messages.create(
                model=self.model,
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )

            report = response.content[0].text
            logger.info("✅ Weekly report generated")
            return report

        except Exception as e:
            logger.error(f"Failed to generate weekly report: {e}")
            return f"Error generating report: {str(e)}"

    async def chat(self, user_message: str, context: Optional[Dict] = None) -> str:
        """
        Chat with Claude about the business

        Args:
            user_message: User's question/message
            context: Optional business context to include

        Returns:
            Claude's response
        """
        logger.info(f"💬 Chat message: {user_message[:50]}...")

        # Get current business context if not provided
        if not context:
            context = await self._get_business_context()

        system_prompt = f"""
You are Claude, the AI business manager for Oubon Shop, a smart home products e-commerce store.

## CURRENT BUSINESS STATE:

**Today's Performance:**
- Revenue: ${context.get('today_revenue', 0):,.2f}
- Orders: {context.get('today_orders', 0)}
- Products in catalog: {context.get('total_products', 0)}

**This Week:**
- Total revenue: ${context.get('week_revenue', 0):,.2f}
- Total orders: {context.get('week_orders', 0)}
- Growth vs last week: {context.get('growth_rate', 0):+.1f}%

**Top Products:**
{self._format_top_products(context.get('top_products', []))}

**Recent Discoveries:**
{self._format_discoveries(context.get('recent_discoveries', []))}

---

Your role is to provide helpful, actionable advice based on real data.
Be conversational but professional.
When appropriate, suggest specific actions the user can take.
Reference the actual data in your responses.
If you don't have enough data to answer, say so honestly.
"""

        # Add user message to conversation
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })

        try:
            response = self.claude.messages.create(
                model=self.model,
                max_tokens=1500,
                system=system_prompt,
                messages=self.conversation_history
            )

            answer = response.content[0].text

            # Add Claude's response to conversation
            self.conversation_history.append({
                "role": "assistant",
                "content": answer
            })

            # Keep conversation history manageable (last 20 messages)
            if len(self.conversation_history) > 20:
                self.conversation_history = self.conversation_history[-20:]

            logger.info("✅ Chat response generated")
            return answer

        except Exception as e:
            logger.error(f"Chat error: {e}")
            return f"I'm having trouble right now: {str(e)}"

    def reset_conversation(self):
        """Reset conversation history"""
        self.conversation_history = []
        logger.info("🔄 Conversation history reset")

    async def _gather_business_metrics(self, date: str) -> Dict:
        """Gather business metrics for a specific date"""
        # This would query your database for actual metrics
        # For now, return sample data
        return {
            'revenue': 1250.00,
            'orders': 15,
            'aov': 83.33,
            'products_discovered': 25,
            'products_added': 3,
            'top_product_name': 'Smart LED Strip Lights',
            'top_product_score': 8.7,
            'ad_spend': 150.00,
            'roas': 8.33,
            'emails_sent': 5,
            'emails_processed': 45,
            'avg_rating': 4.6,
            'support_tickets': 3,
            'tickets_resolved': 3
        }

    async def _gather_weekly_metrics(self) -> Dict:
        """Gather weekly business metrics"""
        # This would query your database
        # For now, return sample data
        return {
            'total_revenue': 8750.00,
            'total_orders': 105,
            'aov': 83.33,
            'growth_rate': 15.5,
            'products_discovered': 175,
            'products_launched': 21,
            'products_sold': 18,
            'products_failed': 3,
            'avg_product_score': 7.8,
            'ad_spend': 1050.00,
            'roas': 8.33,
            'campaigns': 7,
            'best_ad': 'LED Lights - Instagram',
            'worst_ad': 'Security Cameras - Facebook',
            'cac': 10.00,
            'ltv': 250.00,
            'csat': 4.6,
            'repeat_rate': 23.5,
            'product_patterns': [
                'Products with TikTok virality (>1M views) sell 3x better',
                'Price point $20-$50 converts best (68% of sales)',
                'Products with HIGH score (8+) have 85% success rate'
            ],
            'customer_patterns': [
                'Peak buying time: 7-9 PM EST',
                'Mobile devices: 72% of orders',
                'Average time to purchase: 2.3 days'
            ],
            'sales_patterns': [
                'Weekend sales 40% higher than weekdays',
                'Email campaigns have 12% conversion rate',
                'Instagram ads outperform Facebook 2:1'
            ]
        }

    async def _get_business_context(self) -> Dict:
        """Get current business context for chat"""
        # This would query your database
        # For now, return sample data
        return {
            'today_revenue': 1250.00,
            'today_orders': 15,
            'total_products': 48,
            'week_revenue': 8750.00,
            'week_orders': 105,
            'growth_rate': 15.5,
            'top_products': [
                {'name': 'Smart LED Strip Lights', 'sales': 45, 'revenue': 1350.00},
                {'name': 'Security Camera System', 'sales': 12, 'revenue': 1440.00},
                {'name': 'Robot Vacuum', 'sales': 8, 'revenue': 1600.00}
            ],
            'recent_discoveries': [
                {'name': 'Smart Doorbell', 'score': 9.2, 'priority': 'HIGH'},
                {'name': 'Air Purifier', 'score': 8.5, 'priority': 'HIGH'},
                {'name': 'Smart Thermostat', 'score': 7.8, 'priority': 'MEDIUM'}
            ]
        }

    def _format_patterns(self, patterns: List[str]) -> str:
        """Format pattern list for display"""
        if not patterns:
            return "- No patterns detected yet"
        return "\n".join([f"- {p}" for p in patterns])

    def _format_top_products(self, products: List[Dict]) -> str:
        """Format top products list"""
        if not products:
            return "- No sales data yet"

        lines = []
        for i, p in enumerate(products[:5], 1):
            lines.append(
                f"{i}. {p['name']} - {p['sales']} sales, ${p['revenue']:.2f} revenue"
            )
        return "\n".join(lines)

    def _format_discoveries(self, discoveries: List[Dict]) -> str:
        """Format recent discoveries list"""
        if not discoveries:
            return "- No recent discoveries"

        lines = []
        for d in discoveries[:5]:
            lines.append(
                f"- {d['name']} (Score: {d['score']}/10, {d['priority']} priority)"
            )
        return "\n".join(lines)


# Convenience functions for easy integration

async def get_daily_briefing(date: Optional[str] = None) -> str:
    """Get daily briefing"""
    advisor = ClaudeBusinessAdvisor()
    return await advisor.daily_briefing(date)


async def get_weekly_report() -> str:
    """Get weekly learning report"""
    advisor = ClaudeBusinessAdvisor()
    return await advisor.weekly_report()


async def chat_with_claude(message: str, context: Optional[Dict] = None) -> str:
    """Chat with Claude about business"""
    advisor = ClaudeBusinessAdvisor()
    return await advisor.chat(message, context)
